"""
CC-9: Supply Chain Decision API hardening tests.

Covers the cases enumerated in CC-09-decision-api-hardening.md §5:
  - successful GET and POST/GET round trips for sourcing, logistics,
    trade finance/FX, and inventory/contingency
  - invalid modal mix (does not sum to 100) and unavailable-mode rejection
  - invalid sourcing allocation total (does not sum to 100 per category)
  - locked progressive-disclosure fields rejected
  - override-enabled field access permitted
  - writes to a non-open round rejected
  - unauthorized (non-member) user rejected

Auth is exercised through the codebase's X-User-Id header path
(`core.views.decisions._get_user_from_header`), matching production.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from core.models.core import Game, Team, Round
from core.models.overrides import ClassProgressiveDisclosureOverride
from core.models.scenario import (
    Scenario, FirmStarterProfile, MarketDefinition, SegmentDefinition,
    PlatformGenerationDefinition,
)
from core.models.sc_models import Supplier, ShippingLane, TradeFinanceInstrument
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, LogisticsDecision,
    TradeFinanceDecision, FXHedgeDecision, InventoryDecision, ContingencyPlan,
)
from core.models import User as CoreUser  # legacy header-auth user (table `users`)
from core.views.sc_views import (
    SourcingView, LogisticsView, TradeFinanceView, InventoryView,
)


def _make_user(username, role):
    # Header auth (`_get_user_from_header`) resolves the legacy core.User by
    # user_id; this is a different model from AUTH_USER_MODEL (auth.User).
    return CoreUser.objects.create(username=username, password_hash='x', role=role)


class SCApiTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.instructor = _make_user('cc09_inst', 'instructor')
        cls.student = _make_user('cc09_student', 'student')
        # Game.created_by targets AUTH_USER_MODEL (auth.User), distinct from
        # the legacy header-auth users above.
        cls.creator = get_user_model().objects.create_user('cc09_creator', password='x')

        scenario = Scenario.objects.create(
            name='CC09 Scenario', starting_cash=Decimal('1000000.00'),
        )
        cls.scenario = scenario
        cls.market = MarketDefinition.objects.create(
            scenario=scenario, name='North America', code='NA',
            description='t', currency_code='USD',
            exchange_rate_base=Decimal('1.000'), base_growth_rate=Decimal('0.05'),
            entry_cost_base=Decimal('100.00'), tax_rate=Decimal('0.25'),
            regulatory_difficulty=Decimal('5.0'), infrastructure_quality=Decimal('5.0'),
        )
        cls.segment = SegmentDefinition.objects.create(
            scenario=scenario, name='Premium Buyers', segment_type='customer',
            description='t', population_size=1000000,
            bass_p=Decimal('0.03'), bass_q=Decimal('0.38'),
            performance_index_weight=Decimal('1.00'), market=cls.market,
        )
        cls.supplier = Supplier.objects.create(
            scenario=scenario, supplier_id='tsmc', name='TSMC', country='TW',
            tier=1, capacity_units_per_round=100000,
            base_unit_price_usd=Decimal('45.00'),
            quality_rating=Decimal('0.950'), reliability_rating=Decimal('0.920'),
            lead_time_days_baseline=45,
        )
        cls.supplier2 = Supplier.objects.create(
            scenario=scenario, supplier_id='samsung', name='Samsung', country='KR',
            tier=1, capacity_units_per_round=100000,
            base_unit_price_usd=Decimal('42.00'),
            quality_rating=Decimal('0.940'), reliability_rating=Decimal('0.910'),
            lead_time_days_baseline=42,
        )
        cls.lane = ShippingLane.objects.create(
            scenario=scenario, lane_id='cn_to_us', origin_country='CN',
            origin_port='shanghai', destination_country='US',
            destination_port='long_beach', zone='transpacific',
            customs_processing_days_baseline=4,
            modes={
                'sea': {'baseline_cost_per_teu_usd': 2500, 'baseline_lead_time_days': 28},
                'air': {'baseline_cost_per_kg_usd': 8.5, 'baseline_lead_time_days': 3},
                'rail': {'available': False},
                'road': {'available': False},
            },
        )
        cls.instrument = TradeFinanceInstrument.objects.create(
            scenario=scenario, instrument_id='letter_of_credit',
            display_name='Letter of Credit', seller_protection='high',
            buyer_cash_requirement='high',
        )
        cls.fx = TradeFinanceInstrument.objects.create(
            scenario=scenario, instrument_id='fx_forward',
            display_name='FX Forward', seller_protection='medium',
            buyer_cash_requirement='low',
            currency_pairs_available=['USD_CNY', 'EUR_CNY'],
        )
        cls.profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='P', description='t',
            home_market=cls.market,
        )
        cls.game = Game.objects.create(
            scenario=scenario, name='CC09 Game', created_by=cls.creator,
        )
        cls.team = Team.objects.create(
            game=cls.game, name='Alpha', firm_starter_profile=cls.profile,
            performance_index=Decimal('100.00'), cash_on_hand=Decimal('1000000.00'),
            total_equity=Decimal('1000000.00'),
        )
        # Rounds 1..6 — status set per test as needed. Default all open here;
        # individual tests flip specific rounds to test the round-open guard.
        cls.rounds = {
            n: Round.objects.create(game=cls.game, round_number=n, status='open')
            for n in range(1, 7)
        }

        # Product chain for inventory round-trip.
        gen = PlatformGenerationDefinition.objects.create(
            scenario=scenario, name='Gen1', description='t', generation_order=1,
            development_cost=Decimal('1000.00'), license_cost=Decimal('100.00'),
        )
        from core.models.team_state import TeamPlatform, TeamProduct
        platform = TeamPlatform.objects.create(
            team=cls.team, platform_generation=gen, status='active',
        )
        cls.product = TeamProduct.objects.create(
            team=cls.team, team_platform=platform, name='Phone X',
            positioning='premium', created_round=1,
        )

    def setUp(self):
        self.factory = APIRequestFactory()

    # -- helpers ---------------------------------------------------------
    def _post(self, view, body, round_number, user=None):
        user = user or self.instructor
        req = self.factory.post(
            '/x/', body, format='json', HTTP_X_USER_ID=str(user.user_id),
        )
        return view.as_view()(
            req, game_id=self.game.pk, team_id=self.team.pk,
            round_number=round_number,
        )

    def _get(self, view, round_number, user=None):
        user = user or self.instructor
        req = self.factory.get('/x/', HTTP_X_USER_ID=str(user.user_id))
        return view.as_view()(
            req, game_id=self.game.pk, team_id=self.team.pk,
            round_number=round_number,
        )


class SourcingTests(SCApiTestBase):
    def test_get_empty(self):
        resp = self._get(SourcingView, 1)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['decision'])
        self.assertEqual(resp.data['allocations'], [])

    def test_post_get_roundtrip(self):
        body = {
            'tier_2_3_visibility_investment': 'comprehensive',  # unlocks R5
            'multi_sourcing_strategy': 'dual_source',           # unlocks R3
            'allocations': [
                {'critical_input_category': 'semiconductor',
                 'supplier': self.supplier.pk, 'allocation_pct': 60,
                 'payment_terms': 'letter_of_credit'},           # unlocks R4
                {'critical_input_category': 'semiconductor',
                 'supplier': self.supplier2.pk, 'allocation_pct': 40},
            ],
        }
        resp = self._post(SourcingView, body, 5)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(SourcingAllocation.objects.filter(team=self.team).count(), 2)
        # GET rehydrates
        g = self._get(SourcingView, 5)
        self.assertEqual(g.data['decision']['tier_2_3_visibility_investment'], 'comprehensive')
        self.assertEqual(len(g.data['allocations']), 2)

    def test_invalid_allocation_total_rejected(self):
        body = {'allocations': [
            {'critical_input_category': 'semiconductor',
             'supplier': self.supplier.pk, 'allocation_pct': 60},
        ]}
        resp = self._post(SourcingView, body, 1)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('allocations', str(resp.data).lower())
        self.assertFalse(SourcingDecision.objects.filter(team=self.team).exists())

    def test_locked_field_rejected(self):
        body = {'tier_2_3_visibility_investment': 'comprehensive'}  # unlocks R5
        resp = self._post(SourcingView, body, 1)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tier_2_3_visibility_investment', str(resp.data))

    def test_override_unlocks_field(self):
        ClassProgressiveDisclosureOverride.objects.create(
            game=self.game,
            field_path='sourcing.tier_2_3_visibility_investment',
            override_unlock_round=1, created_by=self.creator,
        )
        body = {'tier_2_3_visibility_investment': 'comprehensive'}
        resp = self._post(SourcingView, body, 1)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_non_open_round_rejected(self):
        self.rounds[2].status = 'pending'
        self.rounds[2].save()
        resp = self._post(SourcingView, {'allocations': []}, 2)
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_user_rejected(self):
        # A request whose header does not resolve to a valid user is rejected
        # by IsTeamMember before any team-membership lookup. (The legacy
        # `enrollment`/`team_member` tables are managed=False and not in the
        # test migration graph, so the student-enrollment branch cannot be
        # exercised in-process; this covers the rejection path that does not
        # depend on those tables. See acceptance report.)
        req = self.factory.post('/x/', {'allocations': []}, format='json',
                                HTTP_X_USER_ID='99999999')  # nonexistent user
        resp = SourcingView.as_view()(
            req, game_id=self.game.pk, team_id=self.team.pk, round_number=1,
        )
        self.assertEqual(resp.status_code, 403)

        # And a request with no auth header at all is likewise rejected.
        req2 = self.factory.post('/x/', {'allocations': []}, format='json')
        resp2 = SourcingView.as_view()(
            req2, game_id=self.game.pk, team_id=self.team.pk, round_number=1,
        )
        self.assertEqual(resp2.status_code, 403)


class LogisticsTests(SCApiTestBase):
    def test_post_get_roundtrip(self):
        body = {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 100, 'mode_air_pct': 0,
             'mode_rail_pct': 0, 'mode_road_pct': 0},
        ]}
        resp = self._post(LogisticsView, body, 3)  # modal_mix unlocks R3
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(LogisticsDecision.objects.filter(team=self.team).count(), 1)
        g = self._get(LogisticsView, 3)
        self.assertEqual(len(g.data['logistics']), 1)
        self.assertEqual(g.data['logistics'][0]['mode_sea_pct'], 100)

    def test_invalid_modal_mix_rejected(self):
        body = {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 60, 'mode_air_pct': 0,
             'mode_rail_pct': 0, 'mode_road_pct': 0},
        ]}
        resp = self._post(LogisticsView, body, 3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('100', str(resp.data))

    def test_unavailable_mode_rejected(self):
        body = {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 0, 'mode_air_pct': 0,
             'mode_rail_pct': 100, 'mode_road_pct': 0},  # rail unavailable
        ]}
        resp = self._post(LogisticsView, body, 3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rail', str(resp.data).lower())

    def test_available_mode_accepted(self):
        # sea/air carry params but no explicit `available: true` — must be usable.
        body = {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 50, 'mode_air_pct': 50,
             'mode_rail_pct': 0, 'mode_road_pct': 0},
        ]}
        resp = self._post(LogisticsView, body, 3)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_modal_mix_locked_before_round_3(self):
        body = {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 100, 'mode_air_pct': 0,
             'mode_rail_pct': 0, 'mode_road_pct': 0},
        ]}
        resp = self._post(LogisticsView, body, 2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('logistics.modal_mix', str(resp.data))
        self.assertFalse(LogisticsDecision.objects.filter(team=self.team).exists())


class TradeFinanceTests(SCApiTestBase):
    def test_trade_finance_roundtrip(self):
        body = {'trade_finance': [
            {'segment': self.segment.pk, 'market': self.market.pk,
             'buyer_payment_instrument': 'letter_of_credit'},  # unlocks R4
        ]}
        resp = self._post(TradeFinanceView, body, 4)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(TradeFinanceDecision.objects.filter(team=self.team).count(), 1)
        g = self._get(TradeFinanceView, 4)
        self.assertEqual(len(g.data['trade_finance']), 1)

    def test_invalid_instrument_rejected(self):
        body = {'trade_finance': [
            {'segment': self.segment.pk, 'market': self.market.pk,
             'buyer_payment_instrument': 'bogus_instrument'},
        ]}
        resp = self._post(TradeFinanceView, body, 4)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('buyer_payment_instrument', str(resp.data))

    def test_fx_valid_currency_pair(self):
        body = {'fx_hedges': [
            {'currency_pair': 'USD_CNY', 'hedge_ratio': 50, 'tenor_days': 90},
        ]}
        resp = self._post(TradeFinanceView, body, 5)  # fx_hedging unlocks R5
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(FXHedgeDecision.objects.filter(team=self.team).count(), 1)

    def test_fx_invalid_currency_pair(self):
        body = {'fx_hedges': [
            {'currency_pair': 'XXX_YYY', 'hedge_ratio': 50, 'tenor_days': 90},
        ]}
        resp = self._post(TradeFinanceView, body, 5)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('currency_pair', str(resp.data))


class InventoryTests(SCApiTestBase):
    def test_inventory_post_get_roundtrip(self):
        body = {'inventory': [
            {'product': self.product.pk, 'market': self.market.pk,
             'buffer_days': 45, 'safety_stock_trigger_pct': 25},  # unlocks R3
        ]}
        resp = self._post(InventoryView, body, 3)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(InventoryDecision.objects.filter(team=self.team).count(), 1)
        g = self._get(InventoryView, 3)
        self.assertEqual(len(g.data['inventory']), 1)
        self.assertEqual(g.data['inventory'][0]['buffer_days'], 45)

    def test_contingency_roundtrip(self):
        # CC-19 §2: structured, engine-executable contingency rules.
        body = {'contingency': {
            'alt_supplier_activation_rules': [{
                'input_category': 'semiconductor', 'trigger': 'disruption',
                'backup_supplier_id': self.supplier2.pk, 'shift_pct': 50,
            }],
            'mode_switch_triggers': [],
        }}
        resp = self._post(InventoryView, body, 5)  # contingency_plans unlocks R5
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(ContingencyPlan.objects.filter(team=self.team).exists())
        g = self._get(InventoryView, 5)
        self.assertIsNotNone(g.data['contingency'])

    def test_contingency_locked_before_round_5(self):
        body = {'contingency': {'disruption_response_playbook': 'x'}}
        resp = self._post(InventoryView, body, 3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('inventory.contingency_plans', str(resp.data))
