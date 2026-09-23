"""Walkthrough 4, item 1: the round that crashed when a partner walked away.

In round 8 a partnership's satisfaction fell far enough for the partner to
leave and Phase 1 raised::

    TypeError: ActiveModifier() got unexpected keyword arguments:
               'team', 'modifier_key', 'source', 'round_applied'

`core/engine/alliance_engine.py:392`, in `_process_dissolution`. Four of the
eight keywords are not fields on the model, so *every* partnership dissolution
crashed the round; the alliance row was never saved, so the crash recurred on
every retry and the game could not pass the round.

`POST /api/games/1/round-control/process/` answered 500 three times and the
console showed the operator nothing at all -- no toast, no modal, no line on
the page. The Operator Log did carry a reason, but the reason it carried was
the Python argument list above, in Chinese, mid-round.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
from core.models.decisions import DecisionBudgetAllocation
from core.models.scenario import MarketDefinition, StrategyOptionDefinition
from core.models.team_state import TeamPartnership
from core.tests.test_operator_concurrency import build_minimal_game


PLANT_COST = D('2000000')


class RoundStopperBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'ce4-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.home.plant_build_cost = PLANT_COST
        self.home.save(update_fields=['plant_build_cost'])
        self.round = self._open_round(1)

    def _open_round(self, number):
        round_obj, _ = Round.objects.get_or_create(
            game=self.game, round_number=number,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        return round_obj

    def draft(self, team, round_obj=None):
        submission = DecisionSubmission.objects.create(
            team=team, round=round_obj or self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('0'), marketing_budget=D('0'),
            strategy_budget=D('0'), research_budget=D('0'))
        return submission


# ---------------------------------------------------------------------------
# Item 1 — a partnership dissolution must not crash the round
# ---------------------------------------------------------------------------

class PartnershipDissolutionResolvesTheRoundTests(RoundStopperBase):
    """A real partnership, driven to dissolution through the engine."""

    def setUp(self):
        super().setUp()
        self.option = StrategyOptionDefinition.objects.create(
            scenario=self.scenario, category='partnership',
            name='Distribution partner', code='distribution_partner',
            description='d', capital_cost_base=D('0'),
            recurring_cost_per_round=D('0'))
        self.partnership = TeamPartnership.objects.create(
            team=self.team, market=self.home, strategy_option=self.option,
            annual_investment=D('0'), established_round=0, status='active')
        # A partner nothing this team does can satisfy: every preference is
        # evaluated against state the minimal game does not have, so the
        # weighted satisfaction lands below the floor immediately, and one
        # round of patience is all it takes.
        self.profile = AlliancePartnerProfile.objects.create(
            scenario=self.scenario, partnership_code='distribution_partner',
            market=self.home, name='Meridian Logistics',
            name_zh='子午物流', partner_type='DISTRIBUTION',
            description='d',
            preferences=[{'feature': 'market_investment', 'weight': 1,
                          'description': 'spend in this market'}],
            satisfaction_floor=D('0.95'),
            renegotiation_threshold=D('0.99'),
            patience_rounds=1, benefit_curve='LINEAR')

    def test_the_partner_leaves_and_the_round_still_resolves(self):
        from core.engine.advance_round import close_round, process_round

        self.draft(self.team)
        self.draft(self.rival)

        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

        alliance = TeamAllianceState.objects.get(
            game=self.game, team=self.team, partner_profile=self.profile)
        self.assertEqual(alliance.status, 'DISSOLVED')
        self.assertEqual(alliance.dissolved_round, 1)
        self.assertEqual(alliance.benefit_delivery_pct, D('0'))
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')

    def test_the_partnership_row_is_terminated(self):
        from core.engine.advance_round import close_round, process_round

        self.draft(self.team)
        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

        self.partnership.refresh_from_db()
        self.assertEqual(self.partnership.status, 'terminated')
        self.assertEqual(self.partnership.terminated_round, 1)

    def test_the_dissolution_is_processed_once_and_not_again_every_round(self):
        """A dissolution that never reaches a terminal state re-fires forever.

        `_update_status` returns early only for `DISSOLVED`; a row left
        `DISSOLVING` is re-dissolved, re-logged and re-penalised in every
        later round.
        """
        from core.engine.advance_round import (advance_to_next_round,
                                               close_round, process_round)

        self.draft(self.team)
        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)
        advance_to_next_round(self.game.id)
        second = Round.objects.get(game=self.game, round_number=2)
        self.draft(self.team, second)

        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

        alliance = TeamAllianceState.objects.get(
            game=self.game, team=self.team, partner_profile=self.profile)
        self.assertEqual(alliance.dissolved_round, 1)
        second.refresh_from_db()
        self.assertEqual(second.status, 'processed')


# ---------------------------------------------------------------------------
# Item 1(b) — a Phase-1 crash the operator can see
# ---------------------------------------------------------------------------

class TheConsoleIsToldTheRoundCouldNotBeScoredTests(TestCase):
    """The console showed the operator nothing at all.

    The route answered 500 three times; the sentence existed only in the body,
    which no screen printed, and a reload left `processing_status: FAILED` as a
    one-word tag with the reason nowhere on the page. The Operator Log had the
    reason but read a Python argument list to an instructor.
    """

    def setUp(self):
        from core.models import User
        from core.models.core import Round
        from django.utils import timezone

        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'ce4c-{id(self)}')
        self.instructor = User.objects.create(
            username=f'ce4-instr-{id(self)}', role='instructor',
            password_hash='x')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now(), closed_at=timezone.now(),
            processing_status='FAILED')

    def client_for(self, language=None):
        from core.authentication import create_access_token
        from rest_framework.test import APIClient

        client = APIClient()
        credentials = {
            'HTTP_AUTHORIZATION': f'Bearer {create_access_token(self.instructor)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        return client

    def record_a_phase_1_fault(self):
        """Exactly what `RoundProcessView` does when Phase 1 raises."""
        from core.authentication import JWTUser
        from core.services.lifecycle import operator_action
        from django.test import RequestFactory

        request = RequestFactory().post('/')
        request.user = JWTUser(self.instructor)
        request.data = {}
        with operator_action(request, self.game.id, 'process_round') as action:
            action.require_round()
            event = action.record_fault(
                TypeError("ActiveModifier() got unexpected keyword arguments: "
                          "'team', 'modifier_key', 'source', 'round_applied'"),
                message_key='processing_failed')
        return event

    def test_a_round_that_did_not_fail_says_nothing(self):
        from core.models.core import Round

        Round.objects.filter(pk=self.round.pk).update(
            processing_status='FULLY_COMPLETE')
        response = self.client_for('en').get(
            f'/api/games/{self.game.id}/round-control/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['processing_failure'])

    def test_the_console_is_told_that_processing_failed_and_why(self):
        event = self.record_a_phase_1_fault()

        response = self.client_for('en').get(
            f'/api/games/{self.game.id}/round-control/')

        self.assertEqual(response.status_code, 200, response.data)
        failure = response.data['processing_failure']
        self.assertEqual(failure['code'], 'processing_failed')
        self.assertEqual(failure['reference'], event.request_id)
        self.assertIn('Post-round processing failed', failure['message'])
        self.assertIn(event.request_id, failure['message'])

    def test_the_console_is_told_in_chinese_too(self):
        from core.tests.test_walk_ce_language import has_cjk

        event = self.record_a_phase_1_fault()

        response = self.client_for('zh-CN').get(
            f'/api/games/{self.game.id}/round-control/')

        failure = response.data['processing_failure']
        self.assertTrue(has_cjk(failure['message']), failure)
        self.assertIn(event.request_id, failure['message'])

    def test_no_raw_python_exception_reaches_the_operator(self):
        self.record_a_phase_1_fault()

        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                response = self.client_for(language).get(
                    f'/api/games/{self.game.id}/round-control/')
                message = response.data['processing_failure']['message']
                self.assertNotIn('ActiveModifier', message)
                self.assertNotIn('keyword argument', message)

    def test_the_operator_log_carries_the_reason_and_the_reference(self):
        event = self.record_a_phase_1_fault()

        response = self.client_for('en').get(
            f'/api/games/{self.game.id}/instructor/operator-events/')

        self.assertEqual(response.status_code, 200, response.data)
        rejected = [e for e in response.data['events']
                    if e['outcome'] == 'rejected']
        self.assertTrue(rejected, response.data)
        conflict = rejected[0]['conflict']
        self.assertEqual(conflict['code'], 'processing_failed')
        self.assertEqual(conflict['reference'], event.request_id)
        self.assertIn(event.request_id, conflict['detail'])
        self.assertNotIn('ActiveModifier', conflict['detail'])
        # The technical cause is still on the row for whoever investigates.
        self.assertIn('ActiveModifier', conflict['cause'])
