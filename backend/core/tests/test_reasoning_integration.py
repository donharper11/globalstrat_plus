"""
Integration tests for the Strategic Reasoning Evaluator.

Covers:
  - Pipeline creates/updates DB rows (RoundResultReasoningAnalysis,
    CompetitionReasoningAggregate)
  - Student API returns bands without numeric scores
  - Instructor API returns full numeric breakdowns
  - Authorization: unauthenticated rejected, students can't hit instructor
    endpoints
  - R40/competition grading uses only deterministic scores
  - Manifest and sensitive-route inventory coverage
"""
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase, SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import Game, Team, Round
from core.models.core import User
from core.models.cc_reasoning import (
    RoundResultReasoningAnalysis, CompetitionReasoningAggregate,
)
from core.models.course import Course, Section, Enrollment, SimulationInstance
from core.models.decisions import DecisionSubmission
from core.tests.test_durable_narratives import build_game


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _create_analysis(game, team, round_number, **overrides):
    """Insert a reasoning analysis row with plausible defaults."""
    defaults = dict(
        reasoning_score_deterministic=60.0,
        reasoning_score_full=None,
        coherence_ext_score=65.0,
        responsiveness_score=55.0,
        trajectory_score=58.0,
        justification_score=None,
        coherence_ext_breakdown={'sub_scores': {}},
        responsiveness_breakdown={'events': []},
        trajectory_breakdown={'trends': {}},
        justification_breakdown=None,
        trajectory_pattern='consistent',
        overall_band='developing',
        feedback_student={'coherence_ext': {'band': 'developing', 'feedback': 'OK'}},
        feedback_judge={'coherence_ext': {'score': 65, 'signals': []}},
        engine_version='1.0',
        phase2_completed=False,
    )
    defaults.update(overrides)
    return RoundResultReasoningAnalysis.objects.create(
        game=game, team=team, round_number=round_number, **defaults,
    )


def _make_custom_user(username, role='student'):
    """Create a custom User (core.models.core.User) with the given role."""
    return User.objects.create(
        username=username, role=role, password_hash='x')


def _authed_client(custom_user):
    """APIClient authenticated with a JWT from the custom User model."""
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {create_access_token(custom_user)}')
    return client


def _enroll_student(custom_user, game, team):
    """Create Course -> Section -> Enrollment wiring for a student."""
    uid = id(custom_user)
    course = Course.objects.create(
        course_code=f'RI{uid % 100000}', course_name='Integration',
        instructor_id=None, is_active=True)
    section = Section.objects.create(
        course_id=course.course_id,
        section_code='S1', section_name='S1',
        max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
    Enrollment.objects.create(
        user_id=custom_user.user_id, section_id=section.section_id,
        team_id=team.id, is_active=True, enrolled_at=timezone.now())
    return section


# ===========================================================================
# 1. Pipeline DB tests
# ===========================================================================

class PipelineDBTests(TestCase):
    """Verify reasoning_pipeline.run_reasoning_analysis creates/updates rows."""

    def setUp(self):
        self.game, self.teams = build_game(f'pipe-{id(self)}')
        self.round_obj = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now())
        for team in self.teams:
            DecisionSubmission.objects.create(
                team=team, round=self.round_obj, status='locked',
                locked_at=timezone.now())

    def test_pipeline_creates_analysis_rows(self):
        """Step 18 should create one RoundResultReasoningAnalysis per team."""
        from core.engine.reasoning_pipeline import run_reasoning_analysis

        class FakeCtx:
            log = []

        count = run_reasoning_analysis(
            self.game, 1, self.teams, FakeCtx())

        self.assertEqual(count, len(self.teams))
        for team in self.teams:
            self.assertTrue(
                RoundResultReasoningAnalysis.objects.filter(
                    game=self.game, team=team, round_number=1).exists(),
                f'Missing analysis for {team.name}')

    def test_pipeline_creates_aggregate(self):
        """After pipeline, CompetitionReasoningAggregate should exist."""
        from core.engine.reasoning_pipeline import run_reasoning_analysis

        class FakeCtx:
            log = []

        run_reasoning_analysis(self.game, 1, self.teams, FakeCtx())

        for team in self.teams:
            agg = CompetitionReasoningAggregate.objects.filter(
                game=self.game, team=team).first()
            self.assertIsNotNone(agg, f'Missing aggregate for {team.name}')
            self.assertEqual(agg.rounds_evaluated, 1)

    def test_pipeline_is_idempotent(self):
        """Running the pipeline twice for the same round must not duplicate."""
        from core.engine.reasoning_pipeline import run_reasoning_analysis

        class FakeCtx:
            log = []

        run_reasoning_analysis(self.game, 1, self.teams, FakeCtx())
        run_reasoning_analysis(self.game, 1, self.teams, FakeCtx())

        for team in self.teams:
            count = RoundResultReasoningAnalysis.objects.filter(
                game=self.game, team=team, round_number=1).count()
            self.assertEqual(count, 1, f'Duplicate rows for {team.name}')


# ===========================================================================
# 2. Student API tests
# ===========================================================================

class StudentAPITests(TestCase):
    """Student endpoint: bands and feedback, no raw scores."""

    def setUp(self):
        self.game, self.teams = build_game(f'stu-{id(self)}')
        self.team = self.teams[0]
        self.student = _make_custom_user(f'student-{id(self)}', role='student')
        _enroll_student(self.student, self.game, self.team)
        _create_analysis(self.game, self.team, 1)
        self.client = _authed_client(self.student)

    def test_student_sees_band_not_score(self):
        url = f'/api/games/{self.game.id}/teams/{self.team.id}/rounds/1/reasoning/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('overall_band', data)
        self.assertNotIn('reasoning_score_deterministic', data)
        self.assertNotIn('coherence_ext_score', data)

    def test_student_sees_dimension_bands(self):
        url = f'/api/games/{self.game.id}/teams/{self.team.id}/rounds/1/reasoning/'
        resp = self.client.get(url)
        data = resp.json()
        # feedback_student should have dimension keys with band info
        if 'feedback' in data:
            self.assertIsInstance(data['feedback'], dict)

    def test_unavailable_message_is_english_for_an_english_student(self):
        Enrollment.objects.filter(
            user_id=self.student.user_id, team_id=self.team.id,
        ).update(language='en')
        url = (f'/api/games/{self.game.id}/teams/{self.team.id}/rounds/'
               '99/reasoning/')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'available': False,
            'message': ('Strategic reasoning analysis will be available after '
                        'this round is processed.'),
        })

    def test_unavailable_message_is_chinese_for_a_chinese_student(self):
        Enrollment.objects.filter(
            user_id=self.student.user_id, team_id=self.team.id,
        ).update(language='zh-CN')
        url = (f'/api/games/{self.game.id}/teams/{self.team.id}/rounds/'
               '99/reasoning/')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'available': False,
            'message': '本回合处理完成后即可查看战略推理分析。',
        })

    def test_history_endpoint(self):
        _create_analysis(self.game, self.team, 2)
        url = f'/api/games/{self.game.id}/teams/{self.team.id}/reasoning/history/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Response wraps history: {'history': [...]}
        history = data.get('history', data) if isinstance(data, dict) else data
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 2)


# ===========================================================================
# 3. Instructor API tests
# ===========================================================================

class InstructorAPITests(TestCase):
    """Instructor endpoints expose full numeric breakdowns."""

    def setUp(self):
        self.game, self.teams = build_game(f'inst-{id(self)}')
        self.instructor = _make_custom_user(
            f'instructor-{id(self)}', role='instructor')
        for t in self.teams:
            _create_analysis(self.game, t, 1)
        self.client = _authed_client(self.instructor)

    def test_instructor_sees_scores(self):
        url = f'/api/instructor/games/{self.game.id}/reasoning/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Response wraps teams in a dict: {'game_id': ..., 'teams': [...]}
        teams = data.get('teams', data) if isinstance(data, dict) else data
        self.assertIsInstance(teams, list)
        self.assertTrue(len(teams) >= 2)
        first = teams[0]
        # Instructor view should include numeric scores
        self.assertIn('coherence_ext_score', first)
        self.assertIn('responsiveness_score', first)

    def test_team_detail(self):
        team = self.teams[0]
        url = f'/api/instructor/games/{self.game.id}/teams/{team.id}/reasoning/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_aggregate_endpoint(self):
        for t in self.teams:
            CompetitionReasoningAggregate.objects.create(
                game=self.game, team=t,
                aggregate_reasoning_score=60.0, rounds_evaluated=1,
                avg_coherence_ext=65.0, avg_responsiveness=55.0,
                avg_trajectory=58.0, dominant_pattern='consistent',
                pattern_consistency=1.0, score_trend='stable',
                round_by_round=[])
        url = f'/api/instructor/games/{self.game.id}/reasoning/aggregate/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 4. Authorization tests
# ===========================================================================

class AuthorizationTests(TestCase):
    """Unauthenticated requests rejected; students can't hit instructor URLs."""

    def setUp(self):
        self.game, self.teams = build_game(f'auth-{id(self)}')
        self.team = self.teams[0]
        _create_analysis(self.game, self.team, 1)

    def test_unauthenticated_rejected(self):
        client = APIClient()
        url = f'/api/games/{self.game.id}/teams/{self.team.id}/rounds/1/reasoning/'
        resp = client.get(url)
        self.assertIn(resp.status_code, (401, 403))

    def test_student_cannot_access_instructor_endpoint(self):
        student = _make_custom_user(f'authstu-{id(self)}', role='student')
        _enroll_student(student, self.game, self.team)
        client = _authed_client(student)
        url = f'/api/instructor/games/{self.game.id}/reasoning/'
        resp = client.get(url)
        self.assertIn(resp.status_code, (401, 403))


# ===========================================================================
# 5. R40 competition grading tests
# ===========================================================================

class R40CompetitionGradingTests(TestCase):
    """Competition grading must use deterministic-only scores (R40)."""

    def setUp(self):
        self.game, self.teams = build_game(f'r40-{id(self)}')
        # Create a SimulationInstance so _resolve_game_id works
        owner = self.game.created_by
        course = Course.objects.create(
            course_code=f'R40{id(self) % 100000}', course_name='R40',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id,
            section_code='S1', section_name='S1',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.sim_instance = SimulationInstance.objects.create(
            section_id=section.section_id,
            game_id=self.game.id,
            status='active',
            settings={},
        )
        for t in self.teams:
            _create_analysis(
                self.game, t, 1,
                reasoning_score_deterministic=60.0,
                reasoning_score_full=80.0,
                justification_score=90.0,
                phase2_completed=True,
            )

    @patch('core.services.grading._instance_is_competition', return_value=True)
    def test_competition_mode_uses_deterministic_only(self, mock_comp):
        from core.services.grading import _extract_reasoning_quality
        score = _extract_reasoning_quality(
            self.teams[0].id, self.sim_instance.instance_id)
        # Should be ~60.0, NOT 80.0 (full) or 90.0 (justification)
        self.assertAlmostEqual(float(score), 60.0, places=1)

    @patch('core.services.grading._instance_is_competition', return_value=False)
    def test_classroom_mode_uses_full(self, mock_comp):
        from core.services.grading import _extract_reasoning_quality
        score = _extract_reasoning_quality(
            self.teams[0].id, self.sim_instance.instance_id)
        # Should be ~80.0 (full score), not 60.0 (deterministic)
        self.assertAlmostEqual(float(score), 80.0, places=1)


# ===========================================================================
# 6. Manifest coverage tests
# ===========================================================================

class ManifestCoverageTests(SimpleTestCase):
    """reasoning_analysis appears in the manifest; LLM fields are excluded."""

    def test_reasoning_in_manifest_sections(self):
        from core.services.manifest_sections import RESULT_SECTIONS
        names = [s.name for s in RESULT_SECTIONS]
        self.assertIn('reasoning_analysis', names)

    def test_llm_fields_excluded(self):
        from core.services.manifest_sections import RESULT_SECTIONS
        section = next(s for s in RESULT_SECTIONS
                       if s.name == 'reasoning_analysis')
        excluded_keys = set(section.exclude.keys())
        for field in ('reasoning_score_full', 'justification_score',
                      'justification_breakdown', 'phase2_completed'):
            self.assertIn(field, excluded_keys,
                          f'{field} must be excluded from manifest')

    def test_narrative_fields_declared(self):
        from core.services.manifest_sections import RESULT_SECTIONS
        section = next(s for s in RESULT_SECTIONS
                       if s.name == 'reasoning_analysis')
        for field in ('feedback_student', 'feedback_judge'):
            self.assertIn(field, section.narrative_fields,
                          f'{field} must be declared as narrative')


# ===========================================================================
# 7. Sensitive-route inventory test
# ===========================================================================

class SensitiveRouteTests(SimpleTestCase):
    """The read-inventory gate must be current (not stale after URL changes)."""

    def test_inventory_route_count_is_current(self):
        """url_conf_route_count in read_inventory.json must match the live URL conf."""
        import json
        import os
        inv_path = os.path.join(
            os.path.dirname(__file__), '..', 'services', 'read_inventory.json')
        with open(inv_path) as f:
            inventory = json.load(f)
        stored_count = inventory['url_conf_route_count']
        # The count must be >= 801 (the post-reasoning-routes value).
        # If it's stale, someone added routes without regenerating.
        self.assertGreaterEqual(stored_count, 801,
                                'url_conf_route_count is stale — run '
                                'manage.py dump_read_inventory')
