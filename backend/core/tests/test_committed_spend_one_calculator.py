"""W-CE-18 / W-CE-23: one calculator for what a round's decisions will cost.

The walkthrough saw three spend figures on one Decision Summary, a budget
bar that disagreed with the statement the round then produced, and a team
that locked an $18M acquisition against a $1.5M strategy budget with $18M
of cash, was charged in full at resolution, and could not lock the next
round because its cash was negative.

The cause is one omission written four times. `rd_costs.committed_outlay`
-- the single answer to "can this team afford what it has committed"
(V2-038, V2-057) -- counted the three *declared* budget lines plus the four
extras later rulings added (platform development, bought research, the
structure switch, compliance). What the engine actually charges from cash
for the round's decisions -- `funding_need.decision_outlays`, the calculator
the engine books from (V2-024) -- was in no affordability figure: not the
acquisition, not the market entries, partnerships or ESG spend, not the
sales reps, not payroll, not a plant. So an acquisition could exceed the
declared strategy budget by any amount and nothing objected, because the
strategy line is a declaration and, unlike R&D and marketing, its spend is
not held to it at lock. Meanwhile the Decision Summary and the Finance
context each carried their own private "spent" arithmetic (entries,
partnerships, acquisitions, ESG; promotion plus a field the engine never
charges), so the bar showed one number and the statement another.

R47's consequence names the rule this enforces: "charged from cash means it
counts toward committed spend, so the affordability check and the equity
funding rule see it". Committed spend now counts, per budget line, the
greater of the declared budget and the decision outlays the engine charges
under it -- the acquisition at its authored price, since the summary and the
finance page already showed it as strategy spend -- plus payroll and plant
capex, which have no budget line at all, as committed rows in the position
compliance and platform development occupy. Every "spent" figure a student
reads comes from that one assessment.

Nothing here changes what the engine charges, and no scenario number moves.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionBudgetAllocation, DecisionESG,
                                   DecisionFinancing, DecisionMarketEntry,
                                   DecisionMarketing)
from core.models.scenario import (AcquisitionTarget, EntryModeDefinition,
                                  MarketDefinition,
                                  PlatformGenerationDefinition)
from core.models.talent import DecisionTalent
from core.models.team_state import (TeamMarketPresence, TeamPlatform,
                                    TeamProduct, TeamProductMarket)
from core.services.funding_need import decision_outlays
from core.services.rd_costs import budget_assessment
from core.tests.test_compliance_investment_charge import _Context
from core.tests.test_operator_concurrency import build_minimal_game

OPENING_CASH = D('1000000')          # what `build_minimal_game` gives a team
ACQUISITION = D('1500000')           # more than the cash, far more than the budget
STRATEGY_BUDGET = D('100000')


class CommittedSpendBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'cs-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.eu = MarketDefinition.objects.create(
            scenario=self.scenario, name='Europe', code='EU', description='d',
            currency_code='EUR', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        self.mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        for team in self.teams:
            TeamMarketPresence.objects.create(
                team=team, market=self.home, entry_mode=self.mode,
                established_round=0, initial_investment=0, status='active')
        self.target = AcquisitionTarget.objects.create(
            scenario=self.scenario, market=self.home, target_name='Orbit',
            description='d', base_acquisition_cost=ACQUISITION,
            market_share_gained=D('0.05'), min_round_available=1)
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now() + timezone.timedelta(hours=4)})
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        self.client = self.client_for(self.team)

    def client_for(self, team):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'cs-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'CS{id(self) % 10000}{Course.objects.count()}',
            course_name='CS', instructor_id=None, is_active=True)
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

    def declare(self, rd=D('0'), marketing=D('0'), strategy=D('0')):
        DecisionBudgetAllocation.objects.create(
            submission=self.submission, rd_budget=rd,
            marketing_budget=marketing, strategy_budget=strategy,
            research_budget=D('0'))
        DecisionFinancing.objects.create(submission=self.submission)

    def queue_acquisition(self):
        """Through the real per-type route, as the Corporate Strategy page does."""
        response = self.client.patch(
            self.url('acquisitions'),
            {'acquisitions': [{'acquisition_target': self.target.id}]},
            format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def summary(self):
        response = self.client.get(f'{self.url()}summary/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def finance(self):
        response = self.client.get(f'{self.base}/context/finance/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['budget_status']

    def engine_opex(self):
        from core.engine.costs import calculate_operating_expenses
        context = _Context(self.scenario, self.game, [self.team], 1)
        calculate_operating_expenses(context)
        return context.opex[self.team.id]


class AcquisitionAffordabilityTests(CommittedSpendBase):
    """W-CE-23: the money an acquisition will take is committed money."""

    def test_the_acquisition_counts_toward_committed_spend(self):
        self.declare(strategy=STRATEGY_BUDGET)
        self.queue_acquisition()

        assessment = budget_assessment(self.submission, self.team)
        self.assertEqual(D(assessment['strategy_spent']), ACQUISITION)
        # The declared line is a floor, not a cap: spend beyond it is
        # committed too, so the strategy line commits the acquisition.
        self.assertEqual(D(assessment['committed_total']), ACQUISITION)
        self.assertFalse(assessment['within_cash'])

    def test_the_lock_is_refused_and_nothing_is_locked(self):
        self.declare(strategy=STRATEGY_BUDGET)
        self.queue_acquisition()

        lock = self.client.post(f'{self.url()}lock/', format='json')
        self.assertEqual(lock.status_code, 400, lock.data)
        self.assertIn('Committed spend of $1,500,000.00 exceeds available '
                      'cash of $1,000,000.00', str(lock.data))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'draft')

    def test_the_summary_and_finance_context_show_the_same_figures(self):
        """V2-057: lock, Summary and Finance agree, before the lock."""
        self.declare(strategy=STRATEGY_BUDGET)
        self.queue_acquisition()

        summary = self.summary()
        self.assertFalse(summary['can_lock'])
        self.assertIn('Committed spend of $1,500,000.00 exceeds available '
                      'cash of $1,000,000.00', str(summary['lock_blockers']))
        bar = summary['budget_summary']
        self.assertEqual(bar['strategy_spent'], float(ACQUISITION))
        self.assertEqual(bar['strategy_allocated'], float(STRATEGY_BUDGET))
        self.assertEqual(bar['committed_total'], float(ACQUISITION))
        self.assertEqual(bar['unallocated'], float(OPENING_CASH - ACQUISITION))

        status = self.finance()
        self.assertEqual(status['strategy_spent'], float(ACQUISITION))
        self.assertEqual(status['committed_total'], float(ACQUISITION))
        self.assertEqual(status['unallocated'], float(OPENING_CASH - ACQUISITION))
        self.assertEqual(status['projected_ending_cash'],
                         float(OPENING_CASH - ACQUISITION))

    def test_an_acquisition_the_team_can_afford_is_not_refused_for_cash(self):
        self.target.base_acquisition_cost = D('400000')
        self.target.save(update_fields=['base_acquisition_cost'])
        self.declare(strategy=STRATEGY_BUDGET)
        self.queue_acquisition()

        assessment = budget_assessment(self.submission, self.team)
        self.assertEqual(D(assessment['committed_total']), D('400000'))
        self.assertTrue(assessment['within_cash'])
        summary = self.summary()
        self.assertNotIn('Committed spend', str(summary['lock_blockers']))

    def test_a_declared_budget_larger_than_the_spend_still_counts_in_full(self):
        """V2-057's rule is kept: what is declared is committed."""
        self.target.base_acquisition_cost = D('400000')
        self.target.save(update_fields=['base_acquisition_cost'])
        self.declare(strategy=D('600000'))
        self.queue_acquisition()

        assessment = budget_assessment(self.submission, self.team)
        self.assertEqual(D(assessment['committed_total']), D('600000'))


class OneSpendFigureTests(CommittedSpendBase):
    """W-CE-18: the bar, the Summary and the statement read one calculator."""

    def setUp(self):
        super().setUp()
        self.declare(rd=D('0'), marketing=D('200'), strategy=D('300'))
        DecisionMarketEntry.objects.create(
            submission=self.submission, market=self.eu, entry_mode=self.mode,
            initial_investment=D('400000'), action='enter')
        DecisionESG.objects.create(
            submission=self.submission, environmental_investment=D('50000'),
            social_investment=D('25000'))
        DecisionTalent.objects.create(
            submission=self.submission,
            rd_headcount=10, rd_salary_level=1, rd_training_budget=D('5000'),
            commercial_headcount=10, commercial_salary_level=1,
            commercial_training_budget=D('0'),
            operations_headcount=10, operations_salary_level=1,
            operations_training_budget=D('0'))
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation,
            name='Aurora platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)
        product = TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='Aurora',
            positioning='mainstream', status='active', created_round=0)
        TeamProductMarket.objects.create(
            team_product=product, market=self.home, first_offered_round=0)
        DecisionMarketing.objects.create(
            submission=self.submission, team_product=product, market=self.home,
            retail_price=D('400'), promotion_budget=D('60000'),
            campaign_focus_feature_ids=[1], channel_digital_pct=D('0.34'),
            channel_traditional_pct=D('0.33'), channel_trade_pct=D('0.33'),
            distribution_strategy='mass_retail',
            # The field the old private arithmetic summed and the engine
            # never charges; the reps are what it charges.
            distribution_investment=D('999999'), sales_team_count=2,
            distribution_channel_detail={}, production_volume=0,
            production_source_market=self.home, demand_estimate=0)
        self.outlays = decision_outlays(
            self.scenario, self.team, self.submission, 1)

    def test_every_surface_reads_the_engine_calculator(self):
        expected = {
            'rd_spent': D('0'),
            'marketing_spent': self.outlays['marketing'],
            'strategy_spent': self.outlays['strategy'],
            'talent_committed': self.outlays['talent'],
        }
        self.assertEqual(expected['marketing_spent'], D('260000'))
        self.assertEqual(expected['strategy_spent'], D('475000'))
        self.assertGreater(expected['talent_committed'], D('0'))

        assessment = budget_assessment(self.submission, self.team)
        for key, value in expected.items():
            self.assertEqual(D(assessment[key]), value, key)

        bar = self.summary()['budget_summary']
        status = self.finance()
        for key, value in expected.items():
            self.assertEqual(bar[key], float(value), key)
            self.assertEqual(status[key], float(value), key)
        total = float(sum(expected[k] for k in
                          ('rd_spent', 'marketing_spent', 'strategy_spent')))
        self.assertEqual(status['total_spent'], total)

    def test_committed_spend_is_what_the_engine_will_charge(self):
        """Every decision-driven line the engine books is in the figure."""
        assessment = budget_assessment(self.submission, self.team)
        charged = sum(self.outlays.values(), D('0'))
        # Declared budgets are floors: with each line's spend above its
        # declared budget here, committed spend is exactly the engine's
        # decision-driven charge.
        self.assertEqual(D(assessment['committed_total']), charged)
        self.assertEqual(D(assessment['budget_total']), D('500'))

    def test_the_bar_agrees_with_the_statement_lines(self):
        """The marketing and strategy lines the round will book, before it
        is resolved, are the bar's marketing and strategy spend. Payroll is
        booked into strategy expense by the engine; on the bar it is its
        own committed row, so the two together are the statement's line."""
        opex = self.engine_opex()
        bar = self.summary()['budget_summary']
        self.assertEqual(float(opex['marketing_expense']), bar['marketing_spent'])
        self.assertEqual(float(opex['strategy_expense']),
                         bar['strategy_spent'] + bar['talent_committed'])
