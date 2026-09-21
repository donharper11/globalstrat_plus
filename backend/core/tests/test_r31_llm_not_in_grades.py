"""R31: no language-model output reaches a graded number.

Before 2026-09-16 a student's written communication was scored 0-1 by a model at
submit time, stored as `coherence_contribution`, and blended into
`RoundResultCoherence.blended_score` as `0.9 x formula + 0.1 x communication`.
That row is graded by `services/grading.py`, published, and inside the hashed
`coherence` manifest section -- so model output reached a competitive result,
contradicting V2-016's recorded closure. R31 severed it.

These tests hold the sever in place from both ends: the arithmetic, and the
source. The arithmetic test matters most, because the old blend's defect was
that it *lowered* the score of any team that did the assignment.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from core.engine import coherence as C
from core.models.cc32_models import CommunicationAssignment, TeamCommunication
from core.models import DecisionSubmission
from core.models.core import Round
from core.models.results_financials import RoundResultCoherence
from core.tests.test_durable_narratives import build_game


class SeveredFromGradingTests(TestCase):
    """A scored communication must not move the graded number, at all.

    This runs the real resolution, not a re-implementation of the blend: the
    defect being pinned was in what `calculate_coherence` stored, so a test that
    recomputed the arithmetic itself would have proved nothing.
    """

    def setUp(self):
        self.game, self.teams = build_game(f'r31-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now())
        for team in self.teams:
            DecisionSubmission.objects.create(
                team=team, round=self.round, status='locked',
                locked_at=timezone.now())
        self.assignment = CommunicationAssignment.objects.create(
            scenario=self.game.scenario, code='memo', name='Memo',
            trigger_type='ROUND_MILESTONE', audience='BOARD',
            prompt_text='Write a memo.', word_limit=300,
            trigger_condition={'round': 1}, evaluation_criteria=[],
            coherence_weight=Decimal('0.05'))

    def submit(self, team, overall_score):
        """Store a scored submission exactly as evaluate_communication does."""
        contribution = Decimal(str(round(
            overall_score * float(self.assignment.coherence_weight) * 100, 2)))
        return TeamCommunication.objects.create(
            game=self.game, team=team, round=self.round,
            assignment=self.assignment, content='A memo.', word_count=2,
            is_draft=False, submitted_at=timezone.now(),
            evaluation={'overall_score': overall_score},
            coherence_contribution=contribution)

    def resolve(self):
        from core.engine.advance_round import process_round
        with patch('core.engine.advance_round._run_phase_2'):
            process_round(self.game.id)

    def coherence_rows(self):
        return {row.team_id: row for row in RoundResultCoherence.objects.filter(
            game=self.game, round_number=1)}

    def test_a_perfect_communication_does_not_change_the_graded_score(self):
        author, silent = self.teams[0], self.teams[1]
        self.submit(author, 1.0)
        self.resolve()
        rows = self.coherence_rows()
        self.assertTrue(rows, 'resolution stored no coherence rows')
        for team_id, row in rows.items():
            with self.subTest(team=team_id):
                # The graded number is the formula score, for author and
                # non-author alike. Under the old blend the author's would have
                # been 0.9 x formula + 0.1 x 5 -- strictly lower.
                self.assertEqual(row.blended_score, row.formula_score)
                self.assertNotIn('communication_coherence', row.breakdown or {})

    def test_the_evaluation_survives_as_feedback(self):
        author = self.teams[0]
        self.submit(author, 0.9)
        self.resolve()
        stored = TeamCommunication.objects.get(team=author, round=self.round)
        self.assertEqual(stored.evaluation['overall_score'], 0.9)
        self.assertEqual(float(stored.coherence_contribution), 4.5)
        self.assertEqual(
            C.communication_feedback_total(self.game, author, 1), 4.5)


class SourceTests(TestCase):
    """The blend must not learn to read a model-scored number again."""

    def test_no_blend_arithmetic_mentions_the_communication_component(self):
        import inspect
        source = inspect.getsource(C.calculate_coherence)
        self.assertNotIn('comm_score', source)
        self.assertNotIn('communication_coherence', source)
        self.assertNotIn('0.10 *', source)

    def test_the_feedback_helper_is_display_only(self):
        """It may be read for display; it may not be read by the blend."""
        import inspect
        blend = inspect.getsource(C.calculate_coherence)
        self.assertNotIn('communication_feedback_total', blend)

    def test_the_rag_commentary_no_longer_folds_communication_in(self):
        import inspect
        source = inspect.getsource(C.update_coherence_with_rag)
        self.assertNotIn('comm_score', source)
        self.assertNotIn('0.55 *', source)


class GradingSurfaceTests(TestCase):
    """The second route to a grade, recorded rather than silently changed.

    `communication_quality` averages the model's own `overall_score` straight
    from each submission. R31 ruled on the coherence blend; this component was
    not put to the owner, so it is left as it is and pinned here so a reader
    cannot mistake the sever for covering it. No rubric in the live database
    selects it (0 rows in GradingRubric at the time of writing).
    """

    def test_the_component_still_exists_and_still_reads_model_output(self):
        from core.services import grading
        self.assertIn('communication_quality', grading.COMPONENT_EXTRACTORS)
        import inspect
        source = inspect.getsource(grading._extract_communication_quality)
        self.assertIn("evaluation.get('overall_score')", source)


class ModelRetrievalScoreCannotBeBlendedTests(TestCase):
    """The other blend: `0.6 x formula + 0.4 x model retrieval score`.

    R31's sever removed the communication blend. The retrieval blend survived
    beside it in `calculate_coherence`, reachable by any caller that passed
    `skip_rag=False` -- which was also the *default*. Production's one caller
    passes `skip_rag=True`, so nothing was ever graded this way; the defect was
    that one argument, or one new caller forgetting it, put a model's number
    into a hashed, published, graded row (2026-09-16 re-audit, under A-01).

    These run the real function against real rows with the model stubbed to
    answer, because the question is what gets stored when a model *does*
    answer.
    """

    def setUp(self):
        from core.engine.utils import RoundContext
        self.game, self.teams = build_game(f'r31-rag-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now())
        for team in self.teams:
            DecisionSubmission.objects.create(
                team=team, round=self.round, status='locked',
                locked_at=timezone.now())
        self.context = RoundContext(self.game, 1)
        self.context.teams = list(self.teams)

    def assert_rows_are_formula_only(self):
        rows = list(RoundResultCoherence.objects.filter(
            game=self.game, round_number=1))
        for row in rows:
            with self.subTest(team=row.team_id):
                self.assertEqual(row.blended_score, row.formula_score)
                self.assertIsNone(row.rag_score)
                self.assertNotIn('rag_evaluation', row.breakdown or {})
        return rows

    def test_asking_for_the_model_blend_is_refused_and_stores_nothing_graded(self):
        with patch.object(C, '_calculate_rag_coherence',
                          return_value=(5.0, 'the model has opinions')) as model:
            with self.assertRaisesRegex(RuntimeError, 'R31'):
                C.calculate_coherence(self.context, skip_rag=False)
        model.assert_not_called()
        # Refused before any write, so there is no half-scored round.
        self.assertEqual(self.assert_rows_are_formula_only(), [])

    def test_the_default_call_never_consults_a_model(self):
        """The default used to be `skip_rag=False`: forgetting the argument was
        enough to grade a model's output."""
        with patch.object(C, '_calculate_rag_coherence',
                          return_value=(5.0, 'the model has opinions')) as model:
            C.calculate_coherence(self.context)
        model.assert_not_called()
        self.assertEqual(len(self.assert_rows_are_formula_only()),
                         len(self.teams))

    def test_the_graded_function_has_no_route_to_the_model(self):
        import inspect
        source = inspect.getsource(C.calculate_coherence)
        self.assertNotIn('_calculate_rag_coherence(', source)
        self.assertNotIn('0.4 *', source)
        self.assertNotIn('0.6 *', source)

    def test_the_commentary_path_is_still_there_and_still_display_only(self):
        """What survives: Phase 2 records the model's view for the instructor."""
        import json
        C.calculate_coherence(self.context, skip_rag=True)
        team = self.teams[0]
        before = RoundResultCoherence.objects.get(
            game=self.game, round_number=1, team=team)
        C.update_coherence_with_rag(
            self.game, 1, team, json.dumps({'score': 5, 'feedback': 'weak'}))
        after = RoundResultCoherence.objects.get(pk=before.pk)
        self.assertEqual(after.blended_score, before.blended_score)
        self.assertIsNone(after.rag_score)
        self.assertEqual(after.breakdown, before.breakdown)
