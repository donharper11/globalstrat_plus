"""R47: compliance investment costs money, charged from cash at resolution.

V2-137's repair made `ComplianceInvestment` saveable for the first time, and
the silent-saves record (§6) found the lever was free: the amount raised
`TeamMarketCompliance.compliance_level` but appeared in neither
`funding_need.decision_outlays` nor `costs.calculate_operating_expenses`. The
owner ruled that it costs money, from cash.

These tests are written against the properties the ruling names, one each,
in the shape `test_org_transition_charge` (R36) and `test_paid_research`
(R23) already use for the two nearest precedents:

* one shared function totals the rows, and *both* calculators read it;
* the parity assertion in `calculate_operating_expenses` is widened to
  cover the line, so removing the charge from one side stops the round;
* committed spend, the lock refusal, the Decision Summary and the Finance
  context all carry it, so a team sees the charge before it locks;
* the equity funding rule (V2-024) counts it;
* a resolved round books it on the statements and takes it from cash.

Every test here fails against the tree at `90b2dea`: there is no
`compliance` line in `decision_outlays`, no `compliance_expense` in
`context.opex`, and the round resolves with the money still in the bank.
"""
from decimal import Decimal as D
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.cc31_models import ComplianceInvestment
from core.models.decisions import (DecisionBudgetAllocation,
                                   DecisionFinancing)
from core.models.results_financials import RoundResultFinancials
from core.models.scenario import EntryModeDefinition, MarketDefinition
from core.models.team_state import TeamMarketPresence
from core.services.funding_need import (compliance_investment_total,
                                        decision_outlays, funding_requirement)
from core.services.rd_costs import budget_assessment
from core.tests.test_operator_concurrency import build_minimal_game
from core.utils.participant_messages import participant_message

OPENING_CASH = D('1000000')          # what `build_minimal_game` gives a team
INVESTMENT = D('600000')             # affordable against that cash
UNAFFORDABLE = D('1500000')          # not


class _Context:
    """The minimum `calculate_operating_expenses` reads.

    Built by hand rather than by resolving a round, so the one-calculator
    tests isolate the charge from every other engine input -- the same
    harness `test_org_transition_charge` and `test_paid_research` use.
    """

    def __init__(self, scenario, game, teams, round_number):
        self.scenario = scenario
        self.game = game
        self.teams = list(teams)
        self.round_number = round_number
        self.market_revenue = {}
        self.opex = {}
        self.log = []
        self.interest = {}
        self.tax = {}
        self.cogs = {}
        self.logistics = {}
        self.inventory_costs = {}
        self.market_profit = {}
        self.revenue = {}


class ComplianceChargeBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'cic-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.eu = MarketDefinition.objects.create(
            scenario=self.scenario, name='Europe', code='EU', description='d',
            currency_code='EUR', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        # Both teams operate in both markets, so the only thing that differs
        # between them in a resolved round is the decision under test.
        for team in self.teams:
            for market in (self.home, self.eu):
                TeamMarketPresence.objects.create(
                    team=team, market=market, entry_mode=mode,
                    established_round=0, initial_investment=0,
                    status='active')
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now() + timezone.timedelta(hours=4)})
        self.client = self.client_for(self.team)

    # -- helpers ------------------------------------------------------------

    def client_for(self, team):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'cic-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'CIC{id(self) % 10000}{Course.objects.count()}',
            course_name='CIC', instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    @property
    def base(self):
        return f'/api/games/{self.game.id}/teams/{self.team.id}'

    def url(self, decision_type=None):
        base = f'{self.base}/decisions/round/1/'
        return f'{base}{decision_type}/' if decision_type else base

    def invest(self, rows, language='en'):
        """Through the real per-type route, as the Market Strategy page does."""
        response = self.client.patch(
            self.url('compliance-investments'),
            {'compliance_investments': [
                {'market': market.id, 'investment_amount': str(amount)}
                for market, amount in rows]},
            format='json', HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def submission(self, team=None):
        return DecisionSubmission.objects.filter(
            team=team or self.team, round=self.round).first()

    def cash(self, team):
        team.refresh_from_db()
        return team.cash_on_hand

    def opex_for(self, team):
        from core.engine.costs import calculate_operating_expenses
        context = _Context(self.scenario, self.game, [team], 1)
        calculate_operating_expenses(context)
        return context.opex[team.id]


class OneCalculatorTests(ComplianceChargeBase):

    def test_the_shared_function_totals_every_market_row(self):
        self.invest([(self.home, D('100000')), (self.eu, D('250000'))])
        self.assertEqual(compliance_investment_total(self.submission()),
                         D('350000'))
        self.assertEqual(compliance_investment_total(None), D('0'))

    def test_the_charge_appears_in_both_calculators(self):
        """The funding rule and the engine must charge the same outlay.

        `calculate_operating_expenses` raises `AssertionError` if
        `decision_outlays` and the engine's own lines disagree, and R47 widens
        that assertion to cover this line. The guard *not* firing on a
        correctly wired tree is as much the point as the two equalities.
        """
        self.invest([(self.eu, INVESTMENT)])
        outlays = decision_outlays(self.scenario, self.team,
                                   self.submission(), 1)
        self.assertEqual(outlays['compliance'], INVESTMENT)

        opex = self.opex_for(self.team)
        self.assertEqual(opex['compliance_expense'], INVESTMENT)

    def test_the_parity_assertion_covers_the_new_line(self):
        """Enforced, not merely satisfied.

        If the engine booked the investment and `decision_outlays` did not,
        the round has to stop rather than resolve with the two sides pricing
        different things. Patching the shared calculator to forget the line
        demonstrates that without waiting for a future edit to make the
        mistake for real.
        """
        from core.engine.costs import calculate_operating_expenses

        self.invest([(self.eu, INVESTMENT)])
        context = _Context(self.scenario, self.game, [self.team], 1)

        def forgetful(*args, **kwargs):
            lines = decision_outlays(*args, **kwargs)
            lines['compliance'] = D('0')
            return lines

        with patch('core.services.funding_need.decision_outlays', forgetful):
            with self.assertRaisesRegex(AssertionError, 'decision_outlays'):
                calculate_operating_expenses(context)

    def test_a_round_with_no_investment_charges_nothing(self):
        """Control: the lever unused costs nothing, on both sides."""
        DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        outlays = decision_outlays(self.scenario, self.team,
                                   self.submission(), 1)
        self.assertEqual(outlays['compliance'], D('0'))
        self.assertEqual(self.opex_for(self.team)['compliance_expense'],
                         D('0'))

    def test_undoing_the_decision_removes_the_charge(self):
        self.invest([(self.eu, INVESTMENT)])
        self.invest([])
        self.assertFalse(ComplianceInvestment.objects.filter(
            submission=self.submission()).exists())
        self.assertEqual(compliance_investment_total(self.submission()),
                         D('0'))
        self.assertEqual(self.opex_for(self.team)['compliance_expense'],
                         D('0'))

    def test_it_is_deducted_from_taxable_profit(self):
        """`calculate_tax` sums the same opex lines the statement charges."""
        from core.engine.costs import calculate_tax

        self.invest([(self.eu, INVESTMENT)])
        context = _Context(self.scenario, self.game, [self.team], 1)
        context.opex = {self.team.id: {
            'rd_expense': D('0'), 'marketing_expense': D('0'),
            'strategy_expense': D('0'), 'research_expense': D('0'),
            'admin_overhead': D('0'), 'platform_switch_write_off': D('0'),
            'compliance_expense': INVESTMENT}}
        # Enough profit in the home market for the deduction to bite.
        MarketDefinition.objects.filter(pk=self.home.pk).update(
            tax_rate=D('0.25'))
        self.home.refresh_from_db()
        context.market_revenue = {(self.team.id, self.home.id): {
            'market': self.home, 'home_revenue': D('1000000'),
            'local_revenue': D('1000000')}}
        calculate_tax(context)
        # Deductions are allocated to markets by revenue share; one market
        # takes all of it, so taxable profit is revenue less the investment.
        self.assertEqual(context.tax[self.team.id],
                         ((D('1000000') - INVESTMENT) * D('0.25')).quantize(
                             D('0.01')))


class CommittedSpendTests(ComplianceChargeBase):

    def test_committed_spend_includes_it(self):
        """The team's own spending figure must show money it has committed."""
        self.invest([(self.eu, INVESTMENT)])
        assessment = budget_assessment(self.submission(), self.team)
        self.assertEqual(D(assessment['lines']['compliance_investment']),
                         INVESTMENT)
        self.assertEqual(D(assessment['committed_total']), INVESTMENT)

    def test_the_equity_funding_rule_counts_it(self):
        """V2-024's eligible uses include every decision-driven outlay.

        With the investment above opening cash, the shortfall -- and so the
        equity the team may raise -- is exactly the part cash cannot cover.
        """
        self.invest([(self.eu, UNAFFORDABLE)])
        assessment = funding_requirement(
            self.scenario, self.team, self.submission(), 1)
        self.assertEqual(D(assessment['outlays']['compliance']), UNAFFORDABLE)
        self.assertEqual(D(assessment['eligible_uses']), UNAFFORDABLE)
        self.assertEqual(D(assessment['maximum_new_equity']),
                         UNAFFORDABLE - OPENING_CASH)

    def test_an_affordable_investment_is_no_shortfall(self):
        self.invest([(self.eu, INVESTMENT)])
        assessment = funding_requirement(
            self.scenario, self.team, self.submission(), 1)
        self.assertEqual(D(assessment['maximum_new_equity']), D('0'))


class AffordabilityTests(ComplianceChargeBase):
    """A team cannot commit more compliance investment than it can fund.

    Through the existing refusal path -- `committed_spend_exceeds_cash`, the
    sentence the lock, the Decision Summary and the Finance context already
    share (V2-057) -- rather than a new rule or a new sentence.
    """

    def commit_unaffordable(self):
        self.invest([(self.eu, UNAFFORDABLE)])
        submission = self.submission()
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('0'), marketing_budget=D('0'),
            strategy_budget=D('0'), research_budget=D('0'))
        DecisionFinancing.objects.create(submission=submission)
        return submission

    def expected_refusal(self, language):
        return participant_message(
            'committed_spend_exceeds_cash', language=language,
            committed=f'${UNAFFORDABLE:,.2f}', cash=f'${OPENING_CASH:,.2f}',
            platform='$0.00')

    def test_the_lock_is_refused_and_nothing_is_locked(self):
        self.commit_unaffordable()
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                lock = self.client.post(f'{self.url()}lock/', format='json',
                                        HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(lock.status_code, 400, lock.data)
                self.assertIn(self.expected_refusal(language), str(lock.data))
        self.assertEqual(self.submission().status, 'draft')
        self.assertEqual(self.cash(self.team), OPENING_CASH)

    def test_the_summary_and_finance_context_agree_with_the_refusal(self):
        """V2-057: the three surfaces show one committed figure."""
        self.commit_unaffordable()

        summary = self.client.get(f'{self.url()}summary/')
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertIn(self.expected_refusal('en'),
                      str(summary.data['lock_blockers']))
        budget_summary = summary.data['budget_summary']
        self.assertEqual(budget_summary['committed_total'],
                         float(UNAFFORDABLE))
        self.assertEqual(budget_summary['compliance_committed'],
                         float(UNAFFORDABLE))
        self.assertEqual(budget_summary['unallocated'],
                         float(OPENING_CASH - UNAFFORDABLE))

        finance = self.client.get(f'{self.base}/context/finance/')
        self.assertEqual(finance.status_code, 200, finance.data)
        status = finance.data['budget_status']
        self.assertEqual(status['committed_total'], float(UNAFFORDABLE))
        self.assertEqual(status['compliance_committed'], float(UNAFFORDABLE))
        self.assertEqual(status['projected_ending_cash'],
                         float(OPENING_CASH - UNAFFORDABLE))
        self.assertEqual(status['unallocated'],
                         float(OPENING_CASH - UNAFFORDABLE))

    def test_an_affordable_investment_is_not_refused_for_cash(self):
        """Control: the same route, the same rule, an amount cash covers.

        The minimal fixture carries no portfolio, so the lock still refuses on
        those unrelated items; what this proves is that the cash sentence is
        the investment's and not the fixture's.
        """
        self.invest([(self.eu, INVESTMENT)])
        submission = self.submission()
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('0'), marketing_budget=D('0'),
            strategy_budget=D('0'), research_budget=D('0'))
        DecisionFinancing.objects.create(submission=submission)
        lock = self.client.post(f'{self.url()}lock/', format='json')
        self.assertNotIn('Committed spend', str(lock.data))
        summary = self.client.get(f'{self.url()}summary/')
        self.assertNotIn('Committed spend', str(summary.data['lock_blockers']))
        self.assertEqual(summary.data['budget_summary']['compliance_committed'],
                         float(INVESTMENT))
        self.assertEqual(summary.data['budget_summary']['unallocated'],
                         float(OPENING_CASH - INVESTMENT))


class ResolvedRoundTests(ComplianceChargeBase):
    """The money leaves at resolution, and the statement says so.

    Two teams, identical in every respect but the investment, resolved in one
    round: the rival is the control, so every difference between the two
    statements is the charge and nothing else.
    """

    def resolve(self):
        from core.engine.advance_round import process_round
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        process_round(self.game.id)

    def statements(self):
        return tuple(RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team)
            for team in (self.team, self.rival))

    def test_the_statement_and_cash_carry_the_charge(self):
        self.invest([(self.eu, INVESTMENT)])
        self.resolve()
        mine, control = self.statements()

        # Its own line (owner's amendment); strategy expense is untouched.
        self.assertEqual(mine.compliance_expense - control.compliance_expense,
                         INVESTMENT)
        self.assertEqual(mine.strategy_expense, control.strategy_expense)
        self.assertEqual(control.net_income - mine.net_income, INVESTMENT)
        self.assertEqual(control.cash_closing - mine.cash_closing, INVESTMENT)
        self.assertEqual(self.cash(self.rival) - self.cash(self.team),
                         INVESTMENT)

    def test_the_control_round_moves_no_cash(self):
        """Nothing saved: the two statements are identical, so the test
        above is about the investment and not about the fixture."""
        self.resolve()
        mine, control = self.statements()
        self.assertEqual(mine.strategy_expense, control.strategy_expense)
        self.assertEqual(mine.cash_closing, control.cash_closing)
        self.assertEqual(self.cash(self.team), self.cash(self.rival))


class OwnLineTests(ComplianceChargeBase):
    """The owner's amendment: its own line on the income statement.

    A column of its own on `RoundResultFinancials`, no longer carried inside
    `strategy_expense`; the envelope moves to schema version 7 because the
    hashed `financials` section gains a field; and every statement a student
    reads publishes the line.
    """

    def resolve(self):
        from core.engine.advance_round import process_round
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        process_round(self.game.id)

    def statements(self):
        return tuple(RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team)
            for team in (self.team, self.rival))

    def test_the_statement_has_its_own_column_and_strategy_is_untouched(self):
        self.invest([(self.eu, INVESTMENT)])
        self.resolve()
        mine, control = self.statements()
        self.assertEqual(mine.compliance_expense, INVESTMENT)
        self.assertEqual(control.compliance_expense, D('0'))
        # Not folded: strategy expense is the same for both teams.
        self.assertEqual(mine.strategy_expense, control.strategy_expense)
        # And the totals still carry it.
        self.assertEqual(control.net_income - mine.net_income, INVESTMENT)
        self.assertEqual(control.cash_closing - mine.cash_closing, INVESTMENT)

    def test_the_envelope_is_version_7_and_hashes_the_column(self):
        from core.services.manifest_schema import build_schema_inventory
        from core.services.manifest_version import MANIFEST_SCHEMA_VERSION
        self.assertEqual(MANIFEST_SCHEMA_VERSION, 7)
        financials = build_schema_inventory()['output']['financials']
        self.assertIn('compliance_expense', financials['hashed'])
        self.assertNotIn('compliance_expense', financials['dropped'])

    def test_the_statement_endpoints_publish_the_line(self):
        self.invest([(self.eu, INVESTMENT)])
        self.resolve()
        results = self.client.get(f'{self.base}/results/round/1/')
        self.assertEqual(results.status_code, 200, results.data)
        self.assertEqual(D(str(results.data['financials']['compliance_expense'])),
                         INVESTMENT)
        # research_expense had a column since v6 and no statement surface
        # published it; it rides the same one-line pattern now.
        self.assertIn('research_expense', results.data['financials'])

        history = self.client.get(f'{self.base}/financial-reports/history/')
        self.assertEqual(history.status_code, 200, history.data)
        rows = {row['round_number']: row for row in history.data['rounds']}
        self.assertEqual(D(str(rows[1]['compliance_expense'])), INVESTMENT)
        self.assertIn('research_expense', rows[1])
