"""W-CE3-01 / decision 15: $2,000,000 that left a team between rounds.

The third walkthrough's money reconciliation found the same figure on four
teams. Aurora Devices' round-2 statement closes at **$13,523,631.84** and its
round-3 statement opens at **$11,523,631.84**. Meridian Tech: $18,296,607.20 ->
$16,296,607.20. Solaris Consumer: $24,566,940.00 -> $22,566,940.00. The amount
is always exactly the tax structure's `setup_cost` (`regional_hub: 2000000`).

The cause is R36 / V2-088 in a second place. `costs.process_tax_structure_costs`
did `team.cash_on_hand -= structure.setup_cost` during Phase 1, **before**
`financials` reads `cash_opening = team.cash_on_hand`, so the statement's own
identity (`opening + OCF + ICF + FCF == closing`) closed perfectly on every
team in every round and the money was simply not there any more. No calculator
could see it: not `funding_need.decision_outlays`, not
`rd_costs.budget_assessment`, not the engine's own opex.

The charge is now booked at resolution with every other decision-driven outlay,
through one shared function both sides read, covered by the parity assertion
that stops the round if they ever disagree.

The recurring `annual_maintenance_cost` was checked for the same defect and
does not have it -- `TheMaintenanceCostIsNotTheSameDefectTests` below is the
evidence, and the completion report states the finding.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.cc32c_models import TaxStructureType, TeamTaxStructure
from core.models.decisions import DecisionBudgetAllocation, DecisionFinancing
from core.models.results_financials import RoundResultFinancials
from core.models.scenario import EntryModeDefinition, MarketDefinition
from core.models.team_state import TeamMarketPresence
from core.services.funding_need import (decision_outlays,
                                        tax_structure_setup_charge)
from core.services.rd_costs import budget_assessment
from core.tests.test_compliance_investment_charge import _Context
from core.tests.test_operator_concurrency import build_minimal_game

SETUP_COST = D('2000000')        # `regional_hub` in the shipped scenario
MAINTENANCE = D('400000')        # its per-round cost


class TaxStructureChargeBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'tx-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        for team in self.teams:
            TeamMarketPresence.objects.create(
                team=team, market=self.home, entry_mode=self.mode,
                established_round=0, initial_investment=0, status='active')
        self.structure = TaxStructureType.objects.create(
            scenario=self.scenario, code='regional_hub', name='Regional Hub',
            description='d', setup_cost=SETUP_COST,
            annual_maintenance_cost=MAINTENANCE,
            effective_tax_reduction_pct=D('0.05'),
            repatriation_cost_reduction_pct=D('0.5'),
            audit_probability_per_round=D('0'),
            audit_penalty_multiplier=D('1.0'))
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=self.submission, rd_budget=D('0'),
            marketing_budget=D('0'), strategy_budget=D('0'),
            research_budget=D('0'))
        DecisionFinancing.objects.create(submission=self.submission)

    def adopt(self, round_number=1, team=None):
        """What `views/cc32c_views` writes when a team switches structure."""
        return TeamTaxStructure.objects.update_or_create(
            game=self.game, team=team or self.team,
            defaults={'current_structure': self.structure,
                      'adopted_round': round_number,
                      'setup_cost_paid': False})[0]

    def engine_opex(self, team=None):
        from core.engine.costs import calculate_operating_expenses
        context = _Context(self.scenario, self.game, [team or self.team], 1)
        calculate_operating_expenses(context)
        return context.opex[(team or self.team).id]

    def close_and_process(self):
        from core.engine.advance_round import close_round, process_round
        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

    def statement(self, team=None):
        return RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team or self.team)


class TheChargeIsBookedAtResolutionTests(TaxStructureChargeBase):

    def test_the_shared_calculator_totals_it(self):
        self.adopt()

        outlays = decision_outlays(self.scenario, self.team, self.submission, 1)

        self.assertEqual(outlays['tax_setup'], SETUP_COST)

    def test_the_engine_books_it_where_it_books_the_structure_switch(self):
        self.adopt()

        opex = self.engine_opex()

        self.assertEqual(opex['strategy_expense'], SETUP_COST)

    def test_a_round_with_no_switch_costs_nothing(self):
        opex = self.engine_opex()

        self.assertEqual(opex['strategy_expense'], D('0'))
        self.assertEqual(
            decision_outlays(self.scenario, self.team, self.submission, 1)
            ['tax_setup'], D('0'))

    def test_a_switch_made_in_an_earlier_round_is_not_charged_again(self):
        self.adopt(round_number=0)

        self.assertEqual(tax_structure_setup_charge(self.team, 1), D('0'))
        self.assertEqual(self.engine_opex()['strategy_expense'], D('0'))

    def test_the_charge_is_idempotent_rather_than_cumulative(self):
        self.adopt()

        first = self.engine_opex()['strategy_expense']
        second = self.engine_opex()['strategy_expense']

        self.assertEqual(first, second)
        self.assertEqual(first, SETUP_COST)

    def test_it_is_charged_even_in_a_round_the_team_never_submitted_in(self):
        """A structure is switched from a Finance screen; it writes no row."""
        DecisionSubmission.objects.filter(pk=self.submission.pk).delete()
        self.adopt()

        self.assertEqual(self.engine_opex()['strategy_expense'], SETUP_COST)


class TheMoneyIsOnTheStatementTests(TaxStructureChargeBase):

    def test_the_cash_no_longer_leaves_before_the_statement_is_read(self):
        self.adopt()

        self.close_and_process()

        # The whole defect, stated as the check the walkthrough ran: the round
        # opens at the cash the previous round closed at.
        self.assertEqual(self.statement().cash_opening, D('1000000'))

    def test_the_charge_appears_as_an_expense_the_statement_prints(self):
        self.adopt()

        self.close_and_process()

        mine, control = self.statement(), self.statement(self.rival)
        self.assertEqual(mine.strategy_expense - control.strategy_expense,
                         SETUP_COST)

    def test_the_cash_still_leaves_the_company(self):
        self.adopt()

        self.close_and_process()

        mine, control = self.statement(), self.statement(self.rival)
        self.assertLess(mine.cash_closing, control.cash_closing)

    def test_the_statement_identity_still_closes(self):
        self.adopt()

        self.close_and_process()

        row = self.statement()
        self.assertEqual(
            row.cash_opening + row.operating_cash_flow
            + row.investing_cash_flow + row.financing_cash_flow,
            row.cash_closing)

    def test_the_engine_no_longer_touches_cash_on_hand_directly(self):
        """Read from the code, not the comments that explain the removal."""
        import ast
        import inspect
        from core.engine import costs
        tree = ast.parse(inspect.getsource(costs.process_tax_structure_costs))
        assignments = [
            ast.unparse(node.target) for node in ast.walk(tree)
            if isinstance(node, ast.AugAssign)]
        self.assertNotIn('team.cash_on_hand', assignments)

    def test_the_paid_flag_is_still_recorded_for_the_finance_screen(self):
        self.adopt()

        self.close_and_process()

        self.assertTrue(TeamTaxStructure.objects.get(
            game=self.game, team=self.team).setup_cost_paid)


class TheCommittedSpendSeesItTests(TaxStructureChargeBase):

    def test_it_counts_toward_committed_spend(self):
        self.adopt()

        assessment = budget_assessment(self.submission, self.team)

        self.assertEqual(D(assessment['lines']['tax_setup']), SETUP_COST)
        self.assertEqual(D(assessment['committed_total']), SETUP_COST)

    def test_a_team_that_cannot_fund_the_switch_is_refused_at_lock(self):
        self.team.cash_on_hand = D('1000000')
        self.team.save(update_fields=['cash_on_hand'])
        self.adopt()

        from core.views.decisions import lock_blockers_for
        blockers = lock_blockers_for(self.submission, language='en')

        # Nothing about a completed switch can be cut, so the refusal is the
        # one that names the raise needed rather than a line to reduce.
        self.assertTrue(
            any('Nothing committed can be cut any further' in b
                for b in blockers), blockers)
        self.assertTrue(any('$1,000,000.00' in b for b in blockers), blockers)

    def test_the_equity_funding_rule_counts_it_as_an_eligible_use(self):
        from core.services.funding_need import assess_submission
        self.adopt()

        assessment = assess_submission(self.submission)

        self.assertEqual(D(assessment['eligible_uses']), SETUP_COST)


class TheParityAssertionCoversItTests(TaxStructureChargeBase):

    def test_charging_on_one_side_only_stops_the_round(self):
        """The assertion is enforced over the new line, not merely satisfied."""
        from unittest.mock import patch
        self.adopt()

        def _shared_without_it(scenario, team, submission, current_round,
                               capitalize_platform=False):
            lines = decision_outlays(scenario, team, submission,
                                     current_round, capitalize_platform)
            lines['tax_setup'] = D('0')
            return lines

        with patch('core.services.funding_need.decision_outlays',
                   side_effect=_shared_without_it):
            with self.assertRaises(AssertionError) as raised:
                self.engine_opex()

        self.assertIn('decision_outlays disagrees with the cost engine',
                      str(raised.exception))


class TheMaintenanceCostIsNotTheSameDefectTests(TaxStructureChargeBase):
    """Decision 15 asked; this is the answer, with the evidence.

    The recurring cost is inside `operating_income`, so it reaches net income,
    operating cash flow and the cash a student reads. It does not vanish
    between rounds, which is what W-CE3-01 is about. Moving it into an opex
    line would also move it inside `calculate_tax`'s deduction total and change
    a team's published tax -- calibration, not a bug (R48). What it lacks is a
    line of its own on the served statement, which is W-CE3-04.
    """

    def test_it_is_inside_operating_income(self):
        self.adopt()

        self.close_and_process()

        mine, control = self.statement(), self.statement(self.rival)
        gap = (control.operating_income - mine.operating_income) - SETUP_COST
        self.assertEqual(gap, MAINTENANCE)

    def test_it_does_not_leave_cash_outside_the_statement(self):
        self.adopt()

        self.close_and_process()

        row = self.statement()
        self.assertEqual(
            row.cash_opening + row.operating_cash_flow
            + row.investing_cash_flow + row.financing_cash_flow,
            row.cash_closing)

    def test_it_is_deliberately_not_in_the_shared_outlay_calculator(self):
        self.adopt()

        outlays = decision_outlays(self.scenario, self.team, self.submission, 1)

        self.assertNotIn('tax_maintenance', outlays)
        self.assertEqual(outlays['tax_setup'], SETUP_COST)
