"""Walkthrough 4, item 2: the round that could not be scored, by our own hand.

Decision 14's deadline close makes an unaffordable draft fit by reducing what a
team commits. It left the equity raise sized against the commitments it had
just removed, so the engine refused to score the round under V2-024::

    Round 6 cannot be scored: 4 equity raise(s) exceed the funding shortfall
    they claim to finance ... Aurora Devices: equity raise of $23,433,933.40
    exceeds the funding shortfall of $23,283,933.40

Immediately before the close every team was inside the cap by $100,000;
immediately after, all four were outside it by $150,000, with no team acting in
between. Two rounds in a row, six team-rounds, and the operator's only way out
was a hand-written reopen-resize-relock-reclose loop.

The last class here is the whole-game proof: eight rounds, one of them
deadline-closed for a team that raised equity and one of them carrying a
partnership dissolution, every round processed and scored with no operator
intervention.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
from core.models.decisions import (DecisionBudgetAllocation, DecisionFinancing,
                                   DecisionPlant)
from core.models.competition_audit import DecisionAuditEvent
from core.models.messaging import TeamNotification
from core.models.results_financials import RoundResultFinancials
from core.models.scenario import MarketDefinition, StrategyOptionDefinition
from core.models.talent import DecisionTalent
from core.models.team_state import TeamPartnership
from core.tests.test_operator_concurrency import build_minimal_game


PLANT_COST = D('2000000')
DECLARED_STRATEGY_BUDGET = D('100000')


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
# Item 2 — the close must leave a draft the engine will score
# ---------------------------------------------------------------------------

class DeadlineCloseResizesTheEquityItMadeTooLargeTests(RoundStopperBase):
    """The walkthrough's exact sequence, with the walkthrough's own shape.

    A team is short, raises the equity the Decision Summary asks for, does not
    lock, and the close reduces its draft. Before the repair the round could
    not be scored; nothing the team did moved the figure.
    """

    def build_the_walkthrough_draft(self, team):
        """Short by $100,000, financed at exactly the cap the Summary quotes.

        * talent — payroll the team cannot withdraw from any screen;
        * one plant build — the first thing the close withdraws;
        * a declared strategy budget of $100,000 with nothing spent under it,
          which is committed (V2-057) but is not an eligible use, so the draft
          does not fit by exactly that much.
        """
        from core.services.funding_need import assess_submission

        submission = self.draft(team)
        DecisionTalent.objects.create(submission=submission)
        DecisionPlant.objects.create(
            submission=submission, market=self.home, action='build',
            capacity_units=1000)
        DecisionBudgetAllocation.objects.filter(submission=submission).update(
            strategy_budget=DECLARED_STRATEGY_BUDGET)
        financing = DecisionFinancing.objects.create(submission=submission)
        # Re-read: `.update()` above does not refresh the cached related row,
        # and the close reads this submission from the database.
        submission = DecisionSubmission.objects.get(pk=submission.pk)

        # The team raises exactly what the Summary tells it it may raise.
        maximum = D(assess_submission(submission)['maximum_new_equity'])
        financing.new_equity = maximum
        financing.save(update_fields=['new_equity'])
        return submission, maximum

    def test_the_draft_is_inside_the_cap_before_the_close(self):
        """The pre-flight the walkthrough took from the platform's figures."""
        from core.services.funding_need import assess_submission
        from core.services.rd_costs import budget_assessment

        submission, maximum = self.build_the_walkthrough_draft(self.team)

        self.assertTrue(assess_submission(submission)['within_limit'])
        self.assertGreater(maximum, D('0'))
        # ...and it does not fit, which is what makes the close act on it.
        self.assertFalse(budget_assessment(submission, self.team)['within_cash'])

    def test_the_close_leaves_a_draft_the_engine_will_score(self):
        from core.engine.advance_round import close_round
        from core.services.funding_need import assess_submission, violations

        submission, _ = self.build_the_walkthrough_draft(self.team)

        close_round(self.game.id, reason='deadline')

        submission.refresh_from_db()
        assessment = assess_submission(submission)
        self.assertTrue(
            assessment['within_limit'],
            f'equity {assessment["requested_new_equity"]} vs maximum '
            f'{assessment["maximum_new_equity"]}')
        self.assertEqual(violations(self.game, self.round), [])

    def test_the_round_scores_with_no_operator_intervention(self):
        from core.engine.advance_round import close_round, process_round

        self.build_the_walkthrough_draft(self.team)

        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertTrue(RoundResultFinancials.objects.filter(
            game=self.game, round_number=1, team=self.team).exists())

    def test_the_raise_is_resized_to_the_cap_and_not_to_zero(self):
        """The close resizes; it does not confiscate.

        The team keeps the raise the reduced draft actually justifies, which is
        what it would have got had it locked that same reduced draft itself.
        """
        from core.engine.advance_round import close_round
        from core.services.funding_need import assess_submission

        submission, before = self.build_the_walkthrough_draft(self.team)

        close_round(self.game.id, reason='deadline')

        submission.refresh_from_db()
        after = D(submission.financing.new_equity)
        assessment = assess_submission(submission)
        self.assertLess(after, before)
        self.assertGreater(after, D('0'))
        self.assertEqual(after, D(assessment['maximum_new_equity']))

    def test_the_team_is_told_its_raise_was_reduced(self):
        from core.engine.advance_round import close_round

        self.build_the_walkthrough_draft(self.team)

        close_round(self.game.id, reason='deadline')

        texts = list(TeamNotification.objects.filter(
            team_id=self.team.id).values_list('notification_text', flat=True))
        self.assertTrue(any('equity' in text.lower() for text in texts), texts)

    def test_a_team_that_locked_its_own_draft_is_not_resized(self):
        from core.engine.advance_round import close_round

        submission, before = self.build_the_walkthrough_draft(self.rival)
        DecisionSubmission.objects.filter(pk=submission.pk).update(
            status='locked', locked_at=timezone.now())

        close_round(self.game.id, reason='deadline')

        submission.refresh_from_db()
        self.assertEqual(D(submission.financing.new_equity), before)


# ---------------------------------------------------------------------------
# The whole-game proof
# ---------------------------------------------------------------------------

class AWholeGameCarriesBothDefectsTests(RoundStopperBase):
    """Eight rounds, one deadline-closed equity round, one dissolution.

    Unit tests missed both stoppers, so the proof is a game: every round is
    closed at its deadline and resolved with no operator intervention, no
    reopen-resize-relock-reclose loop and no forced processing.
    """

    DISSOLUTION_ROUND = 5
    EQUITY_ROUND = 3
    ROUNDS = 8

    def setUp(self):
        super().setUp()
        self.option = StrategyOptionDefinition.objects.create(
            scenario=self.scenario, category='partnership',
            name='Distribution partner', code='distribution_partner',
            description='d', capital_cost_base=D('0'),
            recurring_cost_per_round=D('0'))
        self.profile = AlliancePartnerProfile.objects.create(
            scenario=self.scenario, partnership_code='distribution_partner',
            market=self.home, name='Meridian Logistics',
            name_zh='子午物流', partner_type='DISTRIBUTION', description='d',
            preferences=[{'feature': 'market_investment', 'weight': 1,
                          'description': 'spend in this market'}],
            satisfaction_floor=D('0.95'), renegotiation_threshold=D('0.99'),
            patience_rounds=1, benefit_curve='LINEAR')
        self.outcomes = []

    def _short_draft_financed_at_the_cap(self, team, round_obj):
        """The item-2 shape: short, financed at the cap, never locked."""
        from core.services.funding_need import assess_submission

        submission = self.draft(team, round_obj)
        DecisionTalent.objects.create(submission=submission)
        DecisionPlant.objects.create(
            submission=submission, market=self.home, action='build',
            capacity_units=1000)
        DecisionBudgetAllocation.objects.filter(submission=submission).update(
            strategy_budget=DECLARED_STRATEGY_BUDGET)
        financing = DecisionFinancing.objects.create(submission=submission)
        submission = DecisionSubmission.objects.get(pk=submission.pk)
        financing.new_equity = D(
            assess_submission(submission)['maximum_new_equity'])
        financing.save(update_fields=['new_equity'])
        return submission

    def test_eight_rounds_process_and_score_with_no_intervention(self):
        from core.engine.advance_round import (advance_to_next_round,
                                               close_round, process_round)

        for number in range(1, self.ROUNDS + 1):
            round_obj = Round.objects.get(game=self.game, round_number=number)

            if number == self.EQUITY_ROUND:
                # One team short, financed at the cap, left as a draft.
                self._short_draft_financed_at_the_cap(self.team, round_obj)
                self.draft(self.rival, round_obj)
            else:
                for team in self.teams:
                    self.draft(team, round_obj)

            if number == self.DISSOLUTION_ROUND:
                # The partner arrives, and is dissatisfied from its first
                # evaluation: patience is one round, so it leaves in this one.
                TeamPartnership.objects.create(
                    team=self.team, market=self.home,
                    strategy_option=self.option, annual_investment=D('0'),
                    established_round=number, status='active')

            close_round(self.game.id, reason='deadline')
            result = process_round(self.game.id)
            round_obj.refresh_from_db()

            self.outcomes.append({
                'round': number,
                'status': round_obj.status,
                'processing_status': round_obj.processing_status,
                'scored': RoundResultFinancials.objects.filter(
                    game=self.game, round_number=number).count(),
            })
            # No operator intervention: no round was reopened, forced or
            # re-closed, and nothing was resized by hand.
            self.assertEqual(round_obj.status, 'processed',
                             f'round {number}: {self.outcomes[-1]}')
            self.assertEqual(result['processed_round'], number)
            self.assertEqual(
                RoundResultFinancials.objects.filter(
                    game=self.game, round_number=number).count(),
                len(self.teams), f'round {number} was not scored for everyone')

            if number < self.ROUNDS:
                advance_to_next_round(self.game.id)

        # (a) a round was deadline-closed for a team that raised equity...
        equity_event = DecisionAuditEvent.objects.filter(
            game=self.game, action='deadline_withdrew_commitments',
            round__round_number=self.EQUITY_ROUND, team=self.team).first()
        self.assertIsNotNone(equity_event, 'the close did not trim the draft')
        self.assertIn('equity_resized', equity_event.payload)

        # ...(b) and a partnership dissolved.
        alliance = TeamAllianceState.objects.get(
            game=self.game, team=self.team, partner_profile=self.profile)
        self.assertEqual(alliance.status, 'DISSOLVED')
        self.assertEqual(alliance.dissolved_round, self.DISSOLUTION_ROUND)

        # Every round, on the record.
        self.assertEqual(
            [o['status'] for o in self.outcomes],
            ['processed'] * self.ROUNDS, self.outcomes)
