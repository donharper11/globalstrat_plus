"""GSP-CRV2-03: Phase-2 narrative work that survives a restart.

V2-006 was that Phase 2 ran in a daemon thread with no record of its own: a
worker restart between dispatch and completion abandoned the work silently, and
an abrupt death could not even set `narrative_error`. The tests below are
written against the failure modes the handoff names — worker killed after the
Phase-1 commit, worker killed mid-call, provider timeout / 429 / 500 /
malformed output, and no API key at all — and in every one they assert the same
two things: the competitive hash did not move, and the work is either recovered
or visibly terminal.
"""
import hashlib
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User as DjangoUser
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from core.models import Game, Round, Scenario, Team
from core.models.narrative_jobs import NarrativeJob
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  SegmentDefinition)
from core.services import narrative_jobs
from core.services.canonical_json import canonical_sha256


def build_game(name):
    owner = DjangoUser.objects.create(username=f'owner-{name}')
    scenario = Scenario.objects.create(
        name=f'Narrative {name}', industry_label='Test', description='d',
        starting_cash=1000000, num_rounds=50, performance_index_base=100)
    market = MarketDefinition.objects.create(
        scenario=scenario, name='Home', code='HM', description='d',
        currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
        entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
        infrastructure_quality=1)
    SegmentDefinition.objects.create(
        scenario=scenario, market=market, name='Mass', segment_type='customer',
        description='d', population_size=1000, population_growth_rate=0,
        bass_p=D('0.03'), bass_q=D('0.38'), performance_index_weight=D('1.0'),
        revenue_per_unit=D('100'), min_generation_required=1)
    profile = FirmStarterProfile.objects.create(
        scenario=scenario, profile_name='Starter', description='d',
        home_market=market, starting_cash=1000000, starting_debt=0)
    game = Game.objects.create(scenario=scenario, name=name, current_round=1,
                               status='active', created_by=owner, section_id=88)
    teams = [Team.objects.create(
        game=game, name=f'Team {i}', firm_starter_profile=profile,
        performance_index=D('100'), cash_on_hand=D('1000000'),
        total_equity=D('1000000'), home_market=market) for i in range(2)]
    return game, teams


class StubLLM:
    """A provider that answers exactly as a test asks it to.

    These tests must never reach a real endpoint: a shell that happens to have
    DASHSCOPE_API_KEY set would otherwise make them slow, costly and dependent
    on someone else's uptime — which is how the first run of this suite
    accidentally behaved.
    """

    def __init__(self, content='Stubbed narrative.', error=None,
                 success=True):
        self.content = content
        self.error = error
        self.success = success
        self.batches = 0

    def __call__(self, calls):
        self.batches += 1
        if self.error is not None:
            raise self.error
        return {call['id']: {'success': self.success,
                             'content': self.content if self.success else '',
                             'error': '' if self.success else 'stubbed failure'}
                for call in calls}


class DurableNarrativeBase(TestCase):
    def stub_llm(self, **kwargs):
        """Install a stub provider and a key, and return the stub."""
        stub = StubLLM(**kwargs)
        patcher = patch('core.engine.llm_runner.run_llm_batch_sync', stub)
        patcher.start()
        self.addCleanup(patcher.stop)
        key = patch.object(settings, 'DASHSCOPE_API_KEY', 'test-key-not-real')
        key.start()
        self.addCleanup(key.stop)
        return stub

    def setUp(self):
        # No test in this module may reach a real provider, whatever the shell
        # has configured.
        no_key = patch.object(settings, 'DASHSCOPE_API_KEY', '')
        no_key.start()
        self.addCleanup(no_key.stop)
        from core.models import DecisionSubmission
        self.game, self.teams = build_game(f'narr-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now())
        for team in self.teams:
            DecisionSubmission.objects.create(
                team=team, round=self.round, status='locked',
                locked_at=timezone.now())

    def resolve(self):
        """Run Phase 1 without letting the convenience thread drain the queue.

        The thread is patched out precisely so these tests can act as the
        worker: that is the whole point — the durable rows, not the thread, are
        what carries the work.
        """
        from core.engine.advance_round import process_round
        with patch('core.engine.advance_round._run_phase_2'):
            process_round(self.game.id)
        self.round.refresh_from_db()
        return self.round

    def competitive_hash(self):
        from core.services.resolution_manifest import build_output_manifest
        competitive, _narrative = build_output_manifest(self.round)
        return canonical_sha256(competitive)


class EnqueueTests(DurableNarrativeBase):
    """The record exists the moment the numbers do."""

    def test_phase_1_commits_the_jobs_with_the_results(self):
        self.resolve()
        jobs = NarrativeJob.objects.filter(round=self.round)
        self.assertEqual(
            set(jobs.values_list('narrative_type', flat=True)),
            set(narrative_jobs.ENQUEUED_TYPES))
        self.assertTrue(all(job.state == NarrativeJob.PENDING for job in jobs))
        # Numbers are available while the narratives are still outstanding.
        from core.models.results_financials import LeaderboardEntry
        self.assertEqual(
            LeaderboardEntry.objects.filter(
                game=self.game, round_number=1).count(), len(self.teams))

    def test_a_rolled_back_resolution_leaves_no_jobs(self):
        """The jobs share the resolution's transaction, so they share its fate."""
        from core.engine.advance_round import process_round
        with patch('core.services.competition_backup.backup_before_resolution',
                   side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                process_round(self.game.id)
        self.assertFalse(NarrativeJob.objects.filter(round=self.round).exists())

    def test_re_enqueueing_does_not_duplicate(self):
        self.resolve()
        before = NarrativeJob.objects.filter(round=self.round).count()
        narrative_jobs.enqueue_round(self.game, self.round)
        self.assertEqual(
            NarrativeJob.objects.filter(round=self.round).count(), before)


class ClaimAndRecoveryTests(DurableNarrativeBase):
    """Killing a worker must not lose work."""

    def test_a_worker_killed_after_the_phase_1_commit_loses_nothing(self):
        """The web worker dies the instant Phase 1 commits: no thread ever ran."""
        self.resolve()
        competitive_before = self.competitive_hash()

        # A fresh process, with nothing in memory, asks the database.
        processed = narrative_jobs.drain(game_id=self.game.id)
        self.assertEqual(len(processed), len(narrative_jobs.ENQUEUED_TYPES))
        self.assertTrue(all(job.state == NarrativeJob.SUCCEEDED
                            for job in processed))
        self.assertEqual(self.competitive_hash(), competitive_before)

    def test_a_worker_killed_mid_call_leaves_a_lease_that_expires(self):
        self.resolve()
        job = narrative_jobs.claim_next(worker='doomed-worker')
        self.assertEqual(job.state, NarrativeJob.CLAIMED)

        # The worker dies here. Nothing marks the job; the lease simply runs out.
        NarrativeJob.objects.filter(pk=job.pk).update(
            claim_expires_at=timezone.now() - timezone.timedelta(seconds=1))

        reclaimed = narrative_jobs.claim_next(worker='replacement-worker')
        self.assertEqual(reclaimed.pk, job.pk)
        self.assertEqual(reclaimed.claimed_by, 'replacement-worker')

    def test_a_live_claim_is_not_stolen(self):
        """A slow LLM call is not a dead worker."""
        self.resolve()
        held = narrative_jobs.claim_next(worker='busy-worker')
        other = narrative_jobs.claim_next(worker='second-worker')
        self.assertIsNotNone(other)
        self.assertNotEqual(other.pk, held.pk)

    def test_two_workers_never_take_the_same_job(self):
        self.resolve()
        taken = set()
        for index in range(len(narrative_jobs.ENQUEUED_TYPES)):
            job = narrative_jobs.claim_next(worker=f'worker-{index}')
            self.assertNotIn(job.pk, taken)
            taken.add(job.pk)
        self.assertIsNone(narrative_jobs.claim_next(worker='one-too-many'))


class ProviderFailureTests(DurableNarrativeBase):
    """Timeout, 429, 500, malformed output, and no key at all.

    In every case the competitive hash must not move, and the job must end up
    either recovered or visibly terminal — never quietly abandoned, which was
    the whole of V2-006.
    """

    def _one_job(self, narrative_type='briefing'):
        return NarrativeJob.objects.get(round=self.round,
                                        narrative_type=narrative_type)

    def test_a_transient_provider_error_retries_then_gives_up_visibly(self):
        self.resolve()
        competitive_before = self.competitive_hash()
        self.stub_llm(error=TimeoutError('Read timed out after 30s'))

        job = self._one_job()
        for attempt in range(1, job.max_attempts + 1):
            claimed = narrative_jobs.claim_next()
            while claimed.narrative_type != 'briefing':
                # Put anything else back so this test drives one job.
                NarrativeJob.objects.filter(pk=claimed.pk).update(
                    state=NarrativeJob.PENDING, claimed_by='',
                    claim_expires_at=None)
                claimed = narrative_jobs.claim_next()
            narrative_jobs.run_job(claimed)
            job.refresh_from_db()
            self.assertEqual(job.attempts, attempt)
            expected = (NarrativeJob.FAILED if attempt == job.max_attempts
                        else NarrativeJob.PENDING)
            self.assertEqual(job.state, expected)

        self.assertEqual(job.state, NarrativeJob.FAILED)
        self.assertIn('timed out', job.last_error.lower())
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(self.competitive_hash(), competitive_before)

    def test_a_429_is_retryable_and_recorded(self):
        self.resolve()
        self.stub_llm(error=RuntimeError('HTTP 429 Too Many Requests'))
        job = narrative_jobs.run_job(self._one_job())
        self.assertEqual(job.state, NarrativeJob.PENDING)
        self.assertEqual(job.attempts, 1)
        self.assertIn('429', job.last_error)

    def test_a_500_is_retryable_and_recorded(self):
        self.resolve()
        self.stub_llm(error=RuntimeError('HTTP 500 upstream error'))
        job = narrative_jobs.run_job(self._one_job())
        self.assertEqual(job.state, NarrativeJob.PENDING)
        self.assertIn('500', job.last_error)

    def test_malformed_output_does_not_fail_the_job_or_move_the_hash(self):
        """A provider that answers with nonsense degrades the prose only."""
        self.resolve()
        competitive_before = self.competitive_hash()
        self.stub_llm(content='{"not": "what a briefing looks like"')
        processed = narrative_jobs.drain(game_id=self.game.id)
        self.assertTrue(all(job.state == NarrativeJob.SUCCEEDED
                            for job in processed))
        self.assertEqual(self.competitive_hash(), competitive_before)

    def test_no_api_key_produces_fallbacks_and_succeeds(self):
        """`setUp` leaves the key blank, so this is the default path here."""
        self.resolve()
        competitive_before = self.competitive_hash()
        processed = narrative_jobs.drain(game_id=self.game.id)
        self.assertTrue(all(job.state == NarrativeJob.SUCCEEDED
                            for job in processed))
        from core.models.cc27_models import StrategicBriefing
        self.assertEqual(
            StrategicBriefing.objects.filter(
                game=self.game, round_number=1).count(), len(self.teams))
        self.assertEqual(self.competitive_hash(), competitive_before)

    def test_a_stored_error_never_contains_a_credential(self):
        """Provider errors quote the request, and the request carries a key."""
        self.resolve()
        self.stub_llm(error=RuntimeError(
            "401 Unauthorized for request with Authorization: Bearer "
            "sk-abcdef0123456789 and api_key=sk-secret-value"))
        job = narrative_jobs.run_job(self._one_job())
        self.assertNotIn('sk-abcdef0123456789', job.last_error)
        self.assertNotIn('sk-secret-value', job.last_error)
        self.assertIn('[redacted]', job.last_error)


class IsolationAndIdempotencyTests(DurableNarrativeBase):
    def test_running_every_narrative_leaves_the_competitive_hash_alone(self):
        self.resolve()
        before = self.competitive_hash()
        self.stub_llm(content='A full narrative from a working model.')
        narrative_jobs.drain(game_id=self.game.id)
        self.assertEqual(self.competitive_hash(), before)

    def test_the_rag_evaluation_is_recorded_without_scoring_with_it(self):
        """V2-016: the commentary is visible; the graded number is not moved."""
        from core.models.cc21_models import InstructorAlert
        from core.models.results_financials import RoundResultCoherence
        self.resolve()
        coherence = RoundResultCoherence.objects.filter(
            game=self.game, round_number=1).first()
        blended_before = coherence.blended_score

        self.stub_llm(content='{"score": 20, "feedback": "Weak alignment."}')
        narrative_jobs.drain(game_id=self.game.id)

        coherence.refresh_from_db()
        self.assertEqual(coherence.blended_score, blended_before)
        self.assertIsNone(coherence.rag_score)
        commentary = InstructorAlert.objects.filter(
            game=self.game, alert_type='coherence_rag', source='narrative')
        self.assertTrue(commentary.exists())
        self.assertIn('Weak alignment', commentary.first().detail)

    def test_the_blend_can_be_restored_by_a_rules_decision(self):
        from django.test import override_settings
        from core.models.results_financials import RoundResultCoherence
        self.resolve()
        self.stub_llm(content='{"score": 20, "feedback": "Weak alignment."}')
        with override_settings(COMPETITION_RAG_AFFECTS_COHERENCE=True):
            narrative_jobs.drain(game_id=self.game.id)
        coherence = RoundResultCoherence.objects.filter(
            game=self.game, round_number=1).first()
        self.assertEqual(float(coherence.rag_score), 20.0)

    def test_narrative_alerts_stay_out_of_the_competitive_section(self):
        from core.models.cc21_models import InstructorAlert
        self.resolve()
        before = self.competitive_hash()
        self.stub_llm(content='Coaching note.')
        narrative_jobs.drain(game_id=self.game.id)
        self.assertTrue(InstructorAlert.objects.filter(
            game=self.game, source='narrative').exists())
        self.assertEqual(self.competitive_hash(), before)

    def test_sc_event_prose_no_longer_lands_in_a_competitive_field(self):
        """`resolution_data` decides whether an injected event fires."""
        from core.models.scenario import EventTemplateDefinition
        from core.models.sc_state import SCEventInstance
        template = EventTemplateDefinition.objects.create(
            scenario=self.game.scenario, name='Probe shock',
            description_template='A shock.', category='supply_chain',
            severity='moderate', probability_per_round=D('0'), earliest_round=1,
            max_occurrences=1)
        instance = SCEventInstance.objects.create(
            round=self.round, event_template=template,
            resolution_data={'pending': False, 'applied': True})
        self.resolve()
        before = self.competitive_hash()
        self.stub_llm(content='The shock disrupted supply.')
        narrative_jobs.drain(game_id=self.game.id)
        instance.refresh_from_db()
        self.assertEqual(instance.narrative, 'The shock disrupted supply.')
        self.assertEqual(instance.resolution_data,
                         {'pending': False, 'applied': True})
        self.assertEqual(self.competitive_hash(), before)

    def test_a_retry_overwrites_its_own_rows_rather_than_duplicating(self):
        from core.models.cc27_models import StrategicBriefing
        self.resolve()
        self.stub_llm(content='First narrative.')
        narrative_jobs.drain(game_id=self.game.id)
        first = StrategicBriefing.objects.filter(game=self.game, round_number=1)
        self.assertEqual(first.count(), len(self.teams))

        NarrativeJob.objects.filter(round=self.round).update(
            state=NarrativeJob.PENDING, attempts=0, claimed_by='',
            claim_expires_at=None, completed_at=None)
        self.stub_llm(content='Second narrative.')
        narrative_jobs.drain(game_id=self.game.id)
        again = StrategicBriefing.objects.filter(game=self.game, round_number=1)
        self.assertEqual(again.count(), len(self.teams))
        self.assertIn('Second narrative', again.first().executive_summary)


class OperatorVisibilityTests(DurableNarrativeBase):
    def test_numbers_stay_available_while_narratives_are_outstanding(self):
        from core.models.results_financials import LeaderboardEntry
        self.resolve()
        self.assertEqual(
            NarrativeJob.objects.filter(
                round=self.round, state=NarrativeJob.PENDING).count(),
            len(narrative_jobs.ENQUEUED_TYPES))
        self.assertEqual(
            LeaderboardEntry.objects.filter(
                game=self.game, round_number=1).count(), len(self.teams))
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')

    def test_a_failed_job_is_visible_on_the_round_without_downgrading_it(self):
        from core.engine.advance_round import update_round_narrative_status
        self.resolve()
        NarrativeJob.objects.filter(round=self.round).update(
            state=NarrativeJob.FAILED, attempts=3,
            last_error='provider unavailable')
        update_round_narrative_status(self.round.id)
        self.round.refresh_from_db()
        self.assertFalse(self.round.narrative_generated)
        self.assertIn('provider unavailable', self.round.narrative_error)
        # The numbers are still published.
        self.assertEqual(self.round.processing_status, 'RESULTS_AVAILABLE')
        self.assertEqual(self.round.status, 'processed')

    def test_an_operator_retries_narratives_without_rerunning_scoring(self):
        from django.core.management import call_command
        from io import StringIO
        self.resolve()
        competitive_before = self.competitive_hash()
        manifest_before = self.round.resolution_manifest.output_sha256
        NarrativeJob.objects.filter(round=self.round).update(
            state=NarrativeJob.FAILED, attempts=3, last_error='gave up')

        call_command('retry_narrative_jobs', game_id=self.game.id,
                     stdout=StringIO())
        self.assertEqual(
            NarrativeJob.objects.filter(
                round=self.round, state=NarrativeJob.PENDING).count(),
            len(narrative_jobs.ENQUEUED_TYPES))

        self.stub_llm(content='Recovered narrative.')
        narrative_jobs.drain(game_id=self.game.id)
        self.round.refresh_from_db()
        self.assertEqual(self.round.resolution_manifest.output_sha256,
                         manifest_before)
        self.assertEqual(self.competitive_hash(), competitive_before)

    def test_provenance_is_observable_and_holds_no_secret(self):
        self.resolve()
        self.stub_llm(content='Narrative.')
        processed = narrative_jobs.drain(game_id=self.game.id)
        job = processed[0]
        self.assertEqual(job.model_name, settings.DASHSCOPE_MODEL)
        self.assertTrue(job.result_sha256)
        for value in (job.model_name, job.model_endpoint, job.last_error):
            self.assertNotIn('test-key-not-real', value)

    def test_the_backlog_is_reportable(self):
        self.resolve()
        report = narrative_jobs.backlog(self.game.id)
        self.assertEqual(report['pending'], len(narrative_jobs.ENQUEUED_TYPES))
        self.assertEqual(report['failed'], 0)
        self.stub_llm(content='Narrative.')
        narrative_jobs.drain(game_id=self.game.id)
        report = narrative_jobs.backlog(self.game.id)
        self.assertEqual(report['pending'], 0)
        self.assertEqual(report['succeeded'], len(narrative_jobs.ENQUEUED_TYPES))


class DegradedCompletionTests(DurableNarrativeBase):
    """Succeeding on fallbacks is not the same as succeeding.

    The drills found this: with an unreachable provider every job reported
    `succeeded`, because each producer falls back to a template. Right for the
    students, who still get a briefing; wrong for the operator, who saw no sign
    the model never answered.
    """

    def test_a_provider_that_never_answers_is_recorded_as_degraded(self):
        self.resolve()
        self.stub_llm(success=False)
        processed = narrative_jobs.drain(game_id=self.game.id)
        with_calls = [job for job in processed if job.result_sha256]
        self.assertTrue(with_calls)
        degraded = [job for job in with_calls if job.degraded]
        self.assertTrue(degraded, 'A total provider failure left no trace')
        for job in degraded:
            self.assertEqual(job.state, NarrativeJob.SUCCEEDED)
            self.assertIn('fell back to templates', job.last_error)

    def test_a_working_provider_is_not_marked_degraded(self):
        self.resolve()
        self.stub_llm(content='A real narrative.')
        processed = narrative_jobs.drain(game_id=self.game.id)
        self.assertTrue(all(not job.degraded for job in processed))
        self.assertTrue(all(job.last_error == '' for job in processed))

    def test_degradation_is_in_the_backlog_report(self):
        self.resolve()
        self.stub_llm(success=False)
        narrative_jobs.drain(game_id=self.game.id)
        report = narrative_jobs.backlog(self.game.id)
        self.assertEqual(report['failed'], 0)
        self.assertGreater(report['degraded'], 0)

    def test_a_degraded_job_still_leaves_the_competitive_hash_alone(self):
        self.resolve()
        before = self.competitive_hash()
        self.stub_llm(success=False)
        narrative_jobs.drain(game_id=self.game.id)
        self.assertEqual(self.competitive_hash(), before)


# ---------------------------------------------------------------------------
# R1 — instructor observability
# ---------------------------------------------------------------------------

class NarrativeStatusEndpointTests(DurableNarrativeBase):
    """The job rows carried everything an instructor needs and nothing read them.

    A management command served the operator retrying a queue; it did not answer
    an instructor asking why a team's briefing is missing, late, or written by
    the engine rather than the model.
    """

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Section
        self.course = Course.objects.create(
            course_code=f'C{id(self) % 100000}', course_name='Owned course',
            instructor_id=None, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='S1',
            section_name='Section 1', max_teams=4, team_size_min=1,
            team_size_max=4, is_active=True)
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)
        self.game.refresh_from_db()

        self.owner = User.objects.create(
            username=f'owner-inst-{id(self)}', role='instructor',
            password_hash='x')
        self.other = User.objects.create(
            username=f'other-inst-{id(self)}', role='instructor',
            password_hash='x')
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        Course.objects.filter(course_id=self.course.course_id).update(
            instructor_id=self.owner.user_id)

    def _get(self, user):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client.get(f'/api/games/{self.game.id}/round-control/')

    def test_the_games_instructor_sees_every_job_field(self):
        self.resolve()
        response = self._get(self.owner)
        self.assertEqual(response.status_code, 200)
        narratives = response.data['narratives']
        self.assertEqual(narratives['summary']['total'],
                         len(narrative_jobs.ENQUEUED_TYPES))
        self.assertEqual(narratives['summary']['pending'],
                         len(narrative_jobs.ENQUEUED_TYPES))
        row = narratives['jobs'][0]
        for field in ('narrative_type', 'label', 'state', 'state_label',
                      'degraded', 'attempts', 'max_attempts',
                      'attempts_remaining', 'template_version', 'model_name',
                      'last_error', 'created_at', 'claimed_at',
                      'claim_expires_at', 'completed_at'):
            self.assertIn(field, row)
        self.assertEqual(row['state'], 'pending')
        self.assertEqual(row['attempts'], 0)
        self.assertEqual(row['max_attempts'], 3)
        self.assertEqual(row['template_version'], narrative_jobs.TEMPLATE_VERSION)

    def test_a_student_is_refused(self):
        self.resolve()
        self.assertEqual(self._get(self.student).status_code, 403)

    def test_an_unrelated_instructor_is_refused(self):
        self.resolve()
        response = self._get(self.other)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('narratives', response.data)

    def test_an_unowned_cohort_stays_visible_to_any_instructor(self):
        """Course.instructor_id is genuinely NULL for the live pilot; scoping
        strictly would hide those games from everyone."""
        from core.models.course import Course
        Course.objects.filter(course_id=self.course.course_id).update(
            instructor_id=None)
        self.resolve()
        self.assertEqual(self._get(self.other).status_code, 200)

    def test_degraded_and_failed_jobs_are_represented(self):
        self.resolve()
        NarrativeJob.objects.filter(
            round=self.round, narrative_type='briefing').update(
            state=NarrativeJob.SUCCEEDED, degraded=True, attempts=1,
            last_error='3/3 calls fell back to templates: no response',
            model_name='qwen-max', completed_at=timezone.now())
        NarrativeJob.objects.filter(
            round=self.round, narrative_type='coaching').update(
            state=NarrativeJob.FAILED, attempts=3,
            last_error='HTTP 500 upstream error', completed_at=timezone.now())

        narratives = self._get(self.owner).data['narratives']
        by_type = {row['narrative_type']: row for row in narratives['jobs']}

        briefing = by_type['briefing']
        self.assertEqual(briefing['state'], 'succeeded')
        self.assertTrue(briefing['degraded'])
        self.assertIn('fell back to templates', briefing['last_error'])
        self.assertEqual(briefing['model_name'], 'qwen-max')
        self.assertIsNotNone(briefing['completed_at'])

        coaching = by_type['coaching']
        self.assertEqual(coaching['state'], 'failed')
        self.assertEqual(coaching['attempts'], 3)
        self.assertEqual(coaching['attempts_remaining'], 0)
        self.assertIn('500', coaching['last_error'])

        self.assertEqual(narratives['summary']['degraded'], 1)
        self.assertEqual(narratives['summary']['failed'], 1)
        self.assertEqual(narratives['summary']['pending'],
                         len(narrative_jobs.ENQUEUED_TYPES) - 2)

    def test_no_credential_reaches_the_response(self):
        """A provider error quotes the failing request, and that request
        carries an Authorization header."""
        import json as _json
        self.resolve()
        self.stub_llm(error=RuntimeError(
            '401 for request with Authorization: Bearer sk-abcdef0123456789 '
            'and api_key=sk-secret-value'))
        for _ in range(3):
            job = narrative_jobs.claim_next()
            if job is None:
                break
            narrative_jobs.run_job(job)

        body = _json.dumps(self._get(self.owner).data, default=str)
        for secret in ('sk-abcdef0123456789', 'sk-secret-value',
                       'test-key-not-real', 'Bearer '):
            self.assertNotIn(secret, body)
        self.assertIn('[redacted]', body)

    def test_a_round_with_no_jobs_reports_an_empty_set_not_an_error(self):
        response = self._get(self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['narratives']['summary']['total'], 0)


# ---------------------------------------------------------------------------
# R2 — no configuration lets Phase 2 reach a grade
# ---------------------------------------------------------------------------

class CoherenceIsolationTests(DurableNarrativeBase):
    """The switch is gone, not defaulted off.

    A default-off setting is not a safe configuration: a supported deployment
    could flip it and silently reintroduce V2-015 and V2-016.
    """

    def test_no_configuration_lets_phase_2_change_a_grade_or_the_manifest(self):
        from django.test import override_settings
        from core.models.results_financials import RoundResultCoherence
        from core.services.narrative_jobs import UnsafeRagConfiguration

        self.resolve()
        coherence = RoundResultCoherence.objects.filter(
            game=self.game, round_number=1).first()
        graded_before = coherence.blended_score
        rag_before = coherence.rag_score
        hash_before = self.competitive_hash()
        self.stub_llm(content='{"score": 12, "feedback": "Incoherent."}')

        # 1. The supported configuration: the flag unset.
        narrative_jobs.drain(game_id=self.game.id)
        coherence.refresh_from_db()
        self.assertEqual(coherence.blended_score, graded_before)
        self.assertEqual(coherence.rag_score, rag_before)
        self.assertEqual(self.competitive_hash(), hash_before)

        # 2. The retired flag set: running the job still cannot move the grade,
        #    because the write path no longer exists.
        with override_settings(COMPETITION_RAG_AFFECTS_COHERENCE=True):
            NarrativeJob.objects.filter(round=self.round).update(
                state=NarrativeJob.PENDING, attempts=0, degraded=False,
                claimed_by='', claim_expires_at=None, completed_at=None)
            narrative_jobs.drain(game_id=self.game.id)
            coherence.refresh_from_db()
            self.assertEqual(coherence.blended_score, graded_before)
            self.assertEqual(coherence.rag_score, rag_before)
            self.assertEqual(self.competitive_hash(), hash_before)

            # 3. And resolution refuses to run at all, so nobody is left
            #    believing retrieval is being graded when it is not.
            with self.assertRaises(UnsafeRagConfiguration):
                self.resolve()

        # The evaluation is still visible to instructors as commentary.
        from core.models.cc21_models import InstructorAlert
        commentary = InstructorAlert.objects.filter(
            game=self.game, alert_type='coherence_rag', source='narrative')
        self.assertTrue(commentary.exists())
        self.assertIn('Incoherent', commentary.first().detail)
