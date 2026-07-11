"""
Gap-closure tests (post-CC-22 audit):

1. CC-1 §8 supply-chain loader validation (`validate_scenario_yaml`) — the loader
   must halt on malformed SC cross-references. Previously unenforced.
2. Scenario-content list endpoints added in CC-12/13 (`ScenarioMarketsView`,
   `ScenarioSegmentsView`) — response shape + segment_type filter + empty state.
"""
import copy
from decimal import Decimal

import yaml
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from core.management.commands.load_scenario import validate_scenario_yaml
from core.models.scenario import Scenario, MarketDefinition, SegmentDefinition
from core.views.sc_views import ScenarioMarketsView, ScenarioSegmentsView


class CC01SupplyChainValidationTests(TestCase):
    """CC-1 §8 cross-reference validation, exercised against the real CE YAML."""

    @classmethod
    def setUpTestData(cls):
        with open('scenarios/consumer_electronics_2026.yaml') as f:
            cls.ce = yaml.safe_load(f)

    def test_real_scenario_passes(self):
        self.assertEqual(validate_scenario_yaml(self.ce), [])

    def test_no_sc_sections_is_skipped(self):
        d = copy.deepcopy(self.ce)
        for k in ('suppliers', 'shipping_lanes', 'trade_finance_instruments',
                  'compliance_regimes', 'resilience_parameters', 'freight_market'):
            d.pop(k, None)
        self.assertEqual(validate_scenario_yaml(d), [])  # non-SC scenario unaffected

    def test_supplier_country_not_a_lane_origin_rejected(self):
        d = copy.deepcopy(self.ce)
        d['suppliers'][0]['country'] = 'ZZ'
        errs = validate_scenario_yaml(d)
        self.assertTrue(any('is not a declared shipping_lane origin' in e for e in errs))

    def test_resilience_weights_must_sum_to_one(self):
        d = copy.deepcopy(self.ce)
        d['resilience_parameters']['resilience_score_weights']['multi_sourcing'] = 0.9
        errs = validate_scenario_yaml(d)
        self.assertTrue(any('resilience_score_weights sum' in e for e in errs))

    def test_dangling_substitutability_rejected(self):
        d = copy.deepcopy(self.ce)
        d['suppliers'][0]['multi_source_substitutability'] = [
            {'supplier_id': 'ghost_supplier', 'substitution_fraction': 0.5}]
        errs = validate_scenario_yaml(d)
        self.assertTrue(any("unknown supplier 'ghost_supplier'" in e for e in errs))

    def test_unknown_trade_finance_instrument_rejected(self):
        d = copy.deepcopy(self.ce)
        d['suppliers'][0]['accepts_trade_finance'] = ['bogus_instrument']
        errs = validate_scenario_yaml(d)
        self.assertTrue(any("unknown instrument 'bogus_instrument'" in e for e in errs))

    def test_single_source_category_rejected(self):
        d = copy.deepcopy(self.ce)
        # Give a brand-new specialization to exactly one supplier -> count 1.
        d['suppliers'][0].setdefault('specialization', []).append('unicorn_horns')
        errs = validate_scenario_yaml(d)
        self.assertTrue(any("Critical input category 'unicorn_horns'" in e for e in errs))

    def test_event_unknown_lane_rejected(self):
        d = copy.deepcopy(self.ce)
        d.setdefault('events', []).append({'name': 'Bogus SC Event', 'category': 'supply_chain',
                                           'affected_lanes': ['no_such_lane']})
        errs = validate_scenario_yaml(d)
        self.assertTrue(any("unknown lane 'no_such_lane'" in e for e in errs))


class ScenarioContentEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scenario = Scenario.objects.create(name='Gap Scenario', starting_cash=Decimal('1000000.00'))
        cls.m1 = MarketDefinition.objects.create(
            scenario=cls.scenario, name='North America', code='NA', description='t',
            currency_code='USD', exchange_rate_base=Decimal('1.000'), base_growth_rate=Decimal('0.05'),
            entry_cost_base=Decimal('100.00'), tax_rate=Decimal('0.25'),
            regulatory_difficulty=Decimal('5.0'), infrastructure_quality=Decimal('5.0'), display_order=1)
        cls.seg_cust = SegmentDefinition.objects.create(
            scenario=cls.scenario, name='Premium', segment_type='customer', description='t',
            population_size=1000, bass_p=Decimal('0.03'), bass_q=Decimal('0.38'),
            performance_index_weight=Decimal('1.00'), market=cls.m1, display_order=1)
        cls.seg_noncust = SegmentDefinition.objects.create(
            scenario=cls.scenario, name='Regulator', segment_type='non_customer', description='t',
            population_size=10, bass_p=Decimal('0.01'), bass_q=Decimal('0.10'),
            performance_index_weight=Decimal('1.00'), market=cls.m1, display_order=2)
        cls.f = APIRequestFactory()

    def test_markets_endpoint_shape(self):
        resp = ScenarioMarketsView.as_view()(self.f.get('/x'), scenario_id=self.scenario.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [{'id': self.m1.id, 'code': 'NA', 'name': 'North America', 'currency_code': 'USD'}])

    def test_segments_endpoint_and_filter(self):
        allr = ScenarioSegmentsView.as_view()(self.f.get('/x'), scenario_id=self.scenario.pk)
        self.assertEqual(len(allr.data), 2)
        cust = ScenarioSegmentsView.as_view()(self.f.get('/x?segment_type=customer'), scenario_id=self.scenario.pk)
        self.assertEqual([s['name'] for s in cust.data], ['Premium'])
        self.assertEqual(cust.data[0]['market_id'], self.m1.id)

    def test_empty_scenario_returns_empty(self):
        other = Scenario.objects.create(name='Empty', starting_cash=Decimal('1.00'))
        resp = ScenarioMarketsView.as_view()(self.f.get('/x'), scenario_id=other.pk)
        self.assertEqual(resp.data, [])
