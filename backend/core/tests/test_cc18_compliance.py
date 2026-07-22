"""
CC-18 — Compliance enforcement tests.

Proves the detention → freeze → cost → reputation loop: a regime whose trigger has
a real signal (UFLPA Xinjiang exposure; customs docs) fires, books a remediation
cost, freezes the market, and records a reputation impact — and a frozen market
blocks that round's sales in calculate_revenue and hits net income.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, MarketDefinition, SegmentDefinition, FirmStarterProfile,
    PlatformGenerationDefinition, EntryModeDefinition,
)
from core.models.sc_models import Supplier, ComplianceRegime
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, CustomsClassificationDecision,
)
from core.models.sc_state import ComplianceEnforcementEvent
from core.models.team_state import TeamMarketPresence, TeamPlatform, TeamProduct
from core.models.decisions import DecisionSubmission, DecisionMarketing
from core.models.results import RoundResultAdoption
from core.engine.compliance_engine import enforce_compliance, _trigger_applies, _mitigation_reduction_pct
from core.engine.revenue import calculate_revenue
from core.engine.bass_engine import run_bass_adoption
from core.engine.performance import calculate_performance_index


class _Ctx:
    def __init__(self, game, round_number, teams, scenario):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.scenario = scenario
        self.markets = {}
        self.log = []


class CC18ComplianceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        cls.creator = get_user_model().objects.create_user('cc18', password='x')
        cls.na = MarketDefinition.objects.get(scenario=cls.scenario, code='NA')
        cls.segment = SegmentDefinition.objects.filter(scenario=cls.scenario, segment_type='customer').first()
        cls.tsmc = Supplier.objects.get(scenario=cls.scenario, supplier_id='tsmc_taiwan')       # TW, clean
        cls.smic = Supplier.objects.get(scenario=cls.scenario, supplier_id='smic_china')         # CN, xinjiang_adjacent
        cls.uflpa = ComplianceRegime.objects.get(scenario=cls.scenario, regime_id='uflpa')
        cls.customs = ComplianceRegime.objects.get(scenario=cls.scenario, regime_id='customs_documentation')
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC18', created_by=cls.creator, status='active')
        cls.team = Team.objects.create(game=cls.game, name='T', firm_starter_profile=profile,
                                       performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
        gen = PlatformGenerationDefinition.objects.filter(scenario=cls.scenario).order_by('generation_order').first()
        platform = TeamPlatform.objects.create(team=cls.team, platform_generation=gen, status='active')
        cls.product = TeamProduct.objects.create(team=cls.team, team_platform=platform, name='Phone',
                                                 positioning='premium', created_round=1)

    def _round(self, n):
        return Round.objects.create(game=self.game, round_number=n, status='open')

    def _source(self, rnd, supplier, pct=100, visibility='none'):
        SourcingDecision.objects.update_or_create(team=self.team, round=rnd, defaults=dict(
            multi_sourcing_strategy='single_source', tier_2_3_visibility_investment=visibility))
        SourcingAllocation.objects.create(team=self.team, round=rnd, critical_input_category='semiconductor',
                                          supplier=supplier, allocation_pct=pct, payment_terms='', volume_commitment_units=0)

    # -- UFLPA -----------------------------------------------------------
    def test_uflpa_fires_on_xinjiang_exposure(self):
        self.uflpa.baseline_enforcement_probability_per_round = D('1.0')  # force fire
        self.uflpa.save()
        # Isolate UFLPA: the customs regime ('all' markets) would otherwise also
        # fire wherever docs are missing and inflate the aggregate cost.
        self.customs.baseline_enforcement_probability_per_round = D('0')
        self.customs.save()
        rnd = self._round(1)
        self._source(rnd, self.smic, 100)   # 100% Xinjiang-adjacent
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)
        enforce_compliance(ctx)
        ev = ComplianceEnforcementEvent.objects.get(team=self.team, round=rnd, regime=self.uflpa)
        self.assertEqual(ev.cost_usd, D('500000'))               # remediation_cost_usd
        self.assertEqual(ev.freeze_until_round, 2)               # freeze 2 rounds: R1..R2
        self.assertEqual(float(ev.reputation_impact), 1.0)       # shipment_value_loss 100%
        self.assertEqual(ctx.compliance_costs[self.team.id], D('500000'))
        self.assertIn((self.team.id, self.na.id), ctx.compliance_freezes)

    def test_no_xinjiang_exposure_no_uflpa(self):
        self.uflpa.baseline_enforcement_probability_per_round = D('1.0')
        self.uflpa.save()
        rnd = self._round(1)
        self._source(rnd, self.tsmc, 100)   # TW only — clean
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)
        enforce_compliance(ctx)
        self.assertFalse(ComplianceEnforcementEvent.objects.filter(
            team=self.team, round=rnd, regime=self.uflpa).exists())

    def test_uflpa_mitigated_flag_and_reduction(self):
        rnd = self._round(1)
        self._source(rnd, self.smic, 100, visibility='comprehensive')
        applies, mitigated, _ = _trigger_applies(self.uflpa, self.team, rnd, self.na)
        self.assertTrue(applies)
        self.assertTrue(mitigated)                               # comprehensive visibility mitigates
        self.assertEqual(_mitigation_reduction_pct(self.uflpa), 70.0)

    # -- customs documentation ------------------------------------------
    def test_customs_fires_when_docs_missing(self):
        self.customs.baseline_enforcement_probability_per_round = D('1.0')
        self.customs.save()
        self.uflpa.baseline_enforcement_probability_per_round = D('0')  # isolate customs
        self.uflpa.save()
        rnd = self._round(1)
        self._source(rnd, self.tsmc, 100)   # clean sourcing so only customs can fire
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)
        enforce_compliance(ctx)
        ev = ComplianceEnforcementEvent.objects.filter(team=self.team, round=rnd, regime=self.customs).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.cost_usd, D('120000'))               # reclassification_penalty_usd
        self.assertEqual(ev.freeze_until_round, 1)               # shipment_hold 1 round

    def test_customs_not_fired_when_docs_present(self):
        rnd = self._round(1)
        CustomsClassificationDecision.objects.create(
            team=self.team, round=rnd, destination_market=self.na, classification='general_trade')
        applies, mitigated, _ = _trigger_applies(self.customs, self.team, rnd, self.na)
        self.assertFalse(applies)

    # -- integration: freeze blocks revenue + cost hits P&L -------------
    def test_freeze_blocks_revenue(self):
        rnd = self._round(1)
        sub = DecisionSubmission.objects.create(team=self.team, round=rnd, status='locked')
        DecisionMarketing.objects.create(submission=sub, team_product=self.product, market=self.na,
            retail_price=D('500'), promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('1'), channel_traditional_pct=D('0'), channel_trade_pct=D('0'),
            distribution_strategy='hybrid', distribution_investment=D('0'), demand_estimate=1000,
            production_volume=1000, production_source_market=self.na)
        RoundResultAdoption.objects.create(game=self.game, round_number=1, team=self.team, market=self.na,
            best_product=self.product, segment=self.segment, fit_score=D('0.5'), adjusted_fit_score=D('0.5'),
            market_readiness_pct=D('1'), adoption_pool=D('1000'), team_attractiveness=D('1'),
            team_share_pct=D('1'), new_adopters=D('1000'), cumulative_adopters=D('1000'))
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)
        ctx.compliance_freezes = {(self.team.id, self.na.id)}   # NA frozen
        calculate_revenue(ctx)
        # No revenue booked for the frozen market; lost revenue recorded.
        self.assertNotIn((self.team.id, self.product.id, self.na.id), ctx.revenue)
        self.assertGreater(ctx.compliance_lost_revenue[self.team.id], 0)

    def test_freeze_blocks_customer_adoption_credit(self):
        from core.engine.utils import RoundContext, SegmentEffectiveState

        rnd = self._round(2)
        segment = SegmentDefinition.objects.filter(
            scenario=self.scenario, market=self.na, segment_type='customer'
        ).first()
        sub = DecisionSubmission.objects.create(team=self.team, round=rnd, status='locked')
        DecisionMarketing.objects.create(submission=sub, team_product=self.product, market=self.na,
            retail_price=D('500'), promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('1'), channel_traditional_pct=D('0'), channel_trade_pct=D('0'),
            distribution_strategy='hybrid', distribution_investment=D('0'), demand_estimate=1000,
            production_volume=1000, production_source_market=self.na)
        ctx = RoundContext(self.game, 2)
        ctx.teams = [self.team]
        ctx.segments = {segment.id: SegmentEffectiveState(segment)}
        key = (self.team.id, segment.id, self.na.id)
        ctx.fit_scores[key] = 0.9
        ctx.adjusted_fit_scores[key] = 0.9
        ctx.best_products[key] = self.product
        ctx.readiness[(self.team.id, self.product.id, self.na.id)] = 1.0
        ctx.compliance_freezes = {(self.team.id, self.na.id)}

        run_bass_adoption(ctx)

        adoption = RoundResultAdoption.objects.get(
            game=self.game, round_number=2, team=self.team, segment=segment, market=self.na,
        )
        self.assertEqual(adoption.new_adopters, D('0.00'))
        self.assertEqual(adoption.adjusted_fit_score, D('0.0000'))
        self.assertIsNone(adoption.best_product)
        self.assertEqual(ctx.adjusted_fit_scores[key], 0.0)

    def test_compliance_cost_hits_net_income(self):
        from core.engine.financials import generate_financial_statements
        from core.models.results_financials import RoundResultFinancials
        self._round(2)
        ctx = _Ctx(self.game, 2, [self.team], self.scenario)
        ctx.opex = {}; ctx.interest = {}; ctx.tax = {}
        ctx.cogs = {}; ctx.logistics = {}; ctx.inventory_costs = {}
        ctx.revenue = {}; ctx.market_revenue = {}
        ctx.compliance_costs = {self.team.id: D('120000.00')}
        generate_financial_statements(ctx)
        fin = RoundResultFinancials.objects.get(game=self.game, team=self.team, round_number=2)
        self.assertEqual(fin.net_income, D('-120000.00'))        # cost only → negative net income

    def test_performance_index_composite_rewards_financials_and_penalizes_freeze(self):
        from core.models.results_financials import RoundResultPerformanceIndex

        rnd = self._round(3)
        peer = Team.objects.create(
            game=self.game, name='Peer', firm_starter_profile=self.team.firm_starter_profile,
            performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'),
        )
        entry_mode = EntryModeDefinition.objects.filter(scenario=self.scenario).first()
        TeamMarketPresence.objects.create(
            team=self.team, market=self.na, entry_mode=entry_mode, established_round=1,
            initial_investment=D('0'), status='active',
        )
        TeamMarketPresence.objects.create(
            team=peer, market=self.na, entry_mode=entry_mode, established_round=1,
            initial_investment=D('0'), status='active',
        )

        ctx = _Ctx(self.game, 3, [self.team, peer], self.scenario)
        ctx.fit_scores = {}
        ctx.adjusted_fit_scores = {}
        ctx.financials = {
            self.team.id: {
                'total_revenue': D('10000000'), 'net_income': D('3000000'),
                'debt_to_equity': D('0.40'),
            },
            peer.id: {
                'total_revenue': D('2000000'), 'net_income': D('-1000000'),
                'debt_to_equity': D('0.40'),
            },
        }
        ctx.compliance_freezes = set()
        ctx.compliance_costs = {}
        ctx.sc_capacity_factor = {}
        ctx.sc_disruption_costs = {}

        for segment in SegmentDefinition.objects.filter(scenario=self.scenario):
            market_id = segment.market_id if segment.market_id == self.na.id else None
            if segment.market_id and segment.market_id != self.na.id and segment.segment_type == 'customer':
                continue
            key_self = (self.team.id, segment.id, market_id)
            key_peer = (peer.id, segment.id, market_id)
            ctx.fit_scores[key_self] = 0.7
            ctx.adjusted_fit_scores[key_self] = 0.7
            ctx.fit_scores[key_peer] = 0.7
            ctx.adjusted_fit_scores[key_peer] = 0.7

        calculate_performance_index(ctx)
        high_result = RoundResultPerformanceIndex.objects.get(game=self.game, round_number=3, team=self.team)
        peer_result = RoundResultPerformanceIndex.objects.get(game=self.game, round_number=3, team=peer)
        self.assertGreater(high_result.index_value, peer_result.index_value)
        unfrozen_high_index = high_result.index_value

        self.team.performance_index = D('100')
        self.team.save()
        peer.performance_index = D('100')
        peer.save()
        RoundResultPerformanceIndex.objects.filter(game=self.game, round_number=3).delete()
        ctx.compliance_freezes = {(self.team.id, self.na.id)}
        ctx.compliance_costs = {self.team.id: D('2000000')}
        for segment in SegmentDefinition.objects.filter(
            scenario=self.scenario, market=self.na, segment_type='customer',
        ):
            ctx.adjusted_fit_scores[(self.team.id, segment.id, self.na.id)] = 0.0

        calculate_performance_index(ctx)
        frozen_result = RoundResultPerformanceIndex.objects.get(game=self.game, round_number=3, team=self.team)
        self.assertLess(frozen_result.index_value, unfrozen_high_index)
