"""
CC-19 / CC-19B: SC engine tests — event firing + state, Liebig capacity factor,
contingency rerouting, two-channel disruption economics (lost sales via revenue,
real costs via the P&L), resilience scoring, determinism.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, FirmStarterProfile, EventTemplateDefinition, MarketDefinition,
    PlatformGenerationDefinition,
)
from core.models.sc_models import Supplier, ShippingLane
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, ContingencyPlan, LogisticsDecision,
)
from core.models.sc_state import SupplierState, LaneState, SCEventInstance, ResilienceScoreHistory
from core.models.team_state import TeamPlatform, TeamProduct
from core.models.decisions import DecisionSubmission, DecisionMarketing
from core.models.results import RoundResultAdoption
from core.engine.sc_engine import (
    run_sc_state, calculate_sc_disruption_costs, score_sc_resilience,
    _capacity_factor, _seed,
)
from core.engine.revenue import calculate_revenue


class _Ctx:
    """Minimal RoundContext stand-in for the SC steps + calculate_revenue."""
    def __init__(self, game, round_number, teams, scenario):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.scenario = scenario
        self.markets = {}
        self.log = []


class CC19SCEngineTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        EventTemplateDefinition.objects.filter(
            scenario=cls.scenario, category='supply_chain').update(probability_per_round=0)
        cls.creator = get_user_model().objects.create_user('cc19', password='x')
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.market = MarketDefinition.objects.filter(scenario=cls.scenario, code='NA').first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC19 Game', created_by=cls.creator, status='active')
        cls.teamA = Team.objects.create(game=cls.game, name='A', firm_starter_profile=profile,
                                        performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
        cls.teamB = Team.objects.create(game=cls.game, name='B', firm_starter_profile=profile,
                                        performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
        semis = list(Supplier.objects.filter(scenario=cls.scenario, specialization__contains=['semiconductor']))
        cls.primary, cls.backup = semis[0], semis[1]
        # A product chain for Team A (for the Channel-1 revenue test).
        gen = PlatformGenerationDefinition.objects.filter(scenario=cls.scenario).order_by('generation_order').first()
        platform = TeamPlatform.objects.create(team=cls.teamA, platform_generation=gen, status='active')
        cls.product = TeamProduct.objects.create(team=cls.teamA, team_platform=platform,
                                                 name='Phone', positioning='premium', created_round=1)

    # -- helpers --------------------------------------------------------
    def _round(self, n, status='open'):
        return Round.objects.create(game=self.game, round_number=n, status=status)

    def _source(self, team, rnd, supplier, category='semiconductor', pct=100):
        SourcingDecision.objects.get_or_create(team=team, round=rnd,
            defaults=dict(multi_sourcing_strategy='single_source', tier_2_3_visibility_investment='none'))
        SourcingAllocation.objects.create(team=team, round=rnd, critical_input_category=category,
                                          supplier=supplier, allocation_pct=pct, payment_terms='', volume_commitment_units=0)

    def _disrupt(self, rnd, supplier, cap='0.4'):
        return SupplierState.objects.create(round=rnd, supplier=supplier, capacity_multiplier=D(cap),
            quality_modifier=D('0'), reliability_modifier=D('0'), additional_lead_time_days=30,
            disruption_cost_multiplier=D('1.5'), recovery_rounds_remaining=2)

    # -- tests ----------------------------------------------------------
    def test_state_generation_fires_and_populates(self):
        rnd = self._round(6)
        tmpl = EventTemplateDefinition.objects.get(scenario=self.scenario, name__icontains='earthquake')
        EventTemplateDefinition.objects.filter(pk=tmpl.pk).update(probability_per_round=1, earliest_round=1)
        self._source(self.teamA, rnd, self.primary)
        ctx = _Ctx(self.game, 6, [self.teamA, self.teamB], self.scenario)
        run_sc_state(ctx)
        self.assertTrue(SCEventInstance.objects.filter(round=rnd, event_template=tmpl).exists())
        tsmc = Supplier.objects.get(scenario=self.scenario, supplier_id='tsmc_taiwan')
        st = SupplierState.objects.filter(round=rnd, supplier=tsmc).first()
        self.assertIsNotNone(st)
        self.assertLess(float(st.capacity_multiplier), 1.0)
        self.assertIn(self.teamA.id, ctx.sc_capacity_factor)

    def test_capacity_factor_liebig(self):
        rnd = self._round(3)
        # semiconductor single-source disrupted to 0.4; a second healthy category full.
        self._source(self.teamA, rnd, self.primary, category='semiconductor', pct=100)
        self._source(self.teamA, rnd, self.backup, category='display', pct=100)
        disrupted = {self.primary.id: self._disrupt(rnd, self.primary, '0.4')}
        cf, detail = _capacity_factor(self.teamA, rnd, disrupted)
        self.assertAlmostEqual(cf, 0.4, places=3)          # weakest link, not averaged
        self.assertAlmostEqual(detail['display'], 1.0, places=3)
        # No disruption → cf == 1.0
        cf2, _ = _capacity_factor(self.teamA, rnd, {})
        self.assertEqual(cf2, 1.0)

    def test_capacity_factor_contingency_restores(self):
        rnd = self._round(4)
        self._source(self.teamA, rnd, self.primary, pct=100)
        disrupted = {self.primary.id: self._disrupt(rnd, self.primary, '0.4')}
        # Reroute 50% to a healthy backup → cf = 0.5*1 + 0.5*0.4 = 0.7
        ContingencyPlan.objects.create(team=self.teamA, round=rnd, mode_switch_triggers=[],
            alt_supplier_activation_rules=[{'input_category': 'semiconductor', 'trigger': 'disruption',
                                            'backup_supplier_id': self.backup.id, 'shift_pct': 50}])
        cf, _ = _capacity_factor(self.teamA, rnd, disrupted)
        self.assertAlmostEqual(cf, 0.7, places=3)

    def test_channel1_lost_sales_throttles_revenue(self):
        rnd = self._round(7)
        sub = DecisionSubmission.objects.create(team=self.teamA, round=rnd, status='locked')
        DecisionMarketing.objects.create(submission=sub, team_product=self.product, market=self.market,
            retail_price=D('500'), promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('1'), channel_traditional_pct=D('0'), channel_trade_pct=D('0'),
            distribution_strategy='hybrid', distribution_investment=D('0'), demand_estimate=1000,
            production_volume=1000, production_source_market=self.market)
        from core.models.scenario import SegmentDefinition
        seg = SegmentDefinition.objects.filter(scenario=self.scenario, segment_type='customer').first()
        RoundResultAdoption.objects.create(game=self.game, round_number=7, team=self.teamA,
            market=self.market, best_product=self.product, segment=seg,
            fit_score=D('0.5'), adjusted_fit_score=D('0.5'), market_readiness_pct=D('1'),
            adoption_pool=D('1000'), team_attractiveness=D('1'), team_share_pct=D('1'),
            new_adopters=D('1000'), cumulative_adopters=D('1000'))
        ctx = _Ctx(self.game, 7, [self.teamA], self.scenario)
        ctx.sc_capacity_factor = {self.teamA.id: D('0.6')}  # 40% shortfall
        calculate_revenue(ctx)
        rev = ctx.revenue[(self.teamA.id, self.product.id, self.market.id)]
        self.assertEqual(rev['units_sold'], D('600'))              # 1000 × 0.6
        self.assertEqual(rev['units_produced'], D('600'))          # didn't build the 400 lost
        self.assertGreater(ctx.sc_lost_revenue[self.teamA.id], 0)
        # No disruption (cf defaults to 1) → units unchanged.
        ctx2 = _Ctx(self.game, 7, [self.teamA], self.scenario)
        calculate_revenue(ctx2)
        rev2 = ctx2.revenue[(self.teamA.id, self.product.id, self.market.id)]
        self.assertEqual(rev2['units_sold'], D('1000'))
        self.assertEqual(rev2['units_produced'], 1000)

    def test_channel2_disruption_costs_booked(self):
        rnd = self._round(8)
        lane = next(l for l in ShippingLane.objects.filter(scenario=self.scenario))
        LogisticsDecision.objects.create(team=self.teamA, round=rnd, lane=lane,
            mode_sea_pct=100, mode_air_pct=0, mode_rail_pct=0, mode_road_pct=0)
        LaneState.objects.create(round=rnd, lane=lane, active_disruption='freight shock',
            current_rate_modifier=D('2.0'))
        self._source(self.teamA, rnd, self.primary, pct=100)
        self._disrupt(rnd, self.primary, '0.4')
        ContingencyPlan.objects.create(team=self.teamA, round=rnd, mode_switch_triggers=[],
            alt_supplier_activation_rules=[{'input_category': 'semiconductor', 'trigger': 'disruption',
                                            'backup_supplier_id': self.backup.id, 'shift_pct': 50}])
        ctx = _Ctx(self.game, 8, [self.teamA], self.scenario)
        calculate_sc_disruption_costs(ctx)
        self.assertGreater(ctx.sc_freight_costs[self.teamA.id], 0)      # freight surcharge
        self.assertGreater(ctx.sc_mitigation_costs[self.teamA.id], 0)   # reroute premium
        self.assertEqual(ctx.sc_disruption_costs[self.teamA.id],
                         ctx.sc_freight_costs[self.teamA.id] + ctx.sc_mitigation_costs[self.teamA.id])
        # No disruption for Team B (no decisions) → zero cost.
        ctxB = _Ctx(self.game, 8, [self.teamB], self.scenario)
        calculate_sc_disruption_costs(ctxB)
        self.assertEqual(ctxB.sc_disruption_costs[self.teamB.id], D('0'))

    def test_resilience_scored_and_recorded(self):
        rnd = self._round(9)
        self._source(self.teamA, rnd, self.primary, pct=100)
        ctx = _Ctx(self.game, 9, [self.teamA], self.scenario)
        ctx.sc_fired = []
        ctx.sc_lost_revenue = {self.teamA.id: D('12345')}
        ctx.sc_disruption_costs = {self.teamA.id: D('6789')}
        ctx.sc_capacity_factor = {self.teamA.id: D('0.6')}
        score_sc_resilience(ctx)
        rs = ResilienceScoreHistory.objects.filter(team=self.teamA, round=rnd).first()
        self.assertIsNotNone(rs)
        self.assertIn('multi_sourcing', rs.components)

    def test_seed_deterministic(self):
        self.assertEqual(_seed(1, 2, 3), _seed(1, 2, 3))
        self.assertNotEqual(_seed(1, 2, 3), _seed(1, 3, 3))
