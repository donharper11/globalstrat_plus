"""
CC-22: End-to-end supply-chain simulation test.

Proves the SC process works end to end against the REAL Consumer Electronics
scenario seed data (loaded into the test DB): submit all four SC decision
families through the real views, read them back (dashboard-equivalent), lock,
and advance the round with SC data present without a runtime exception.

Covers CC-22 §2.1-2.10, §4.3, §4.4, §4.5.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, MarketDefinition, SegmentDefinition, FirmStarterProfile,
    PlatformGenerationDefinition,
)
from core.models.sc_models import Supplier, ShippingLane, TradeFinanceInstrument
from core.models.sc_decisions import (
    SourcingAllocation, LogisticsDecision, TradeFinanceDecision, InventoryDecision,
)
from core.models.decisions import DecisionSubmission
from core.models import User as CoreUser
from core.views.sc_views import (
    SourcingView, LogisticsView, TradeFinanceView, InventoryView,
)
from rest_framework.test import APIRequestFactory


def _mode_available(lane, mode):
    e = (lane.modes or {}).get(mode)
    return bool(e) and e.get('available', True) is not False


class CC22E2ETest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Load the real Consumer Electronics scenario with SC seed data.
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')

        cls.instructor = CoreUser.objects.create(
            username='cc22_inst', password_hash='x', role='instructor')
        cls.creator = get_user_model().objects.create_user('cc22_creator', password='x')

        cls.market = MarketDefinition.objects.filter(scenario=cls.scenario, code='NA').first()
        cls.segment = SegmentDefinition.objects.filter(
            scenario=cls.scenario, segment_type='customer').first()
        semis = list(Supplier.objects.filter(
            scenario=cls.scenario, specialization__contains=['semiconductor'])[:2])
        cls.sup_a, cls.sup_b = semis[0], semis[1]
        cls.lane = next(l for l in ShippingLane.objects.filter(scenario=cls.scenario)
                        if _mode_available(l, 'sea'))
        cls.instrument = TradeFinanceInstrument.objects.filter(
            scenario=cls.scenario, instrument_id='letter_of_credit').first()

        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(
            scenario=cls.scenario, name='CC22 E2E Game', created_by=cls.creator,
            status='active')
        cls.team = Team.objects.create(
            game=cls.game, name='Team E2E', firm_starter_profile=profile,
            performance_index=Decimal('100.00'), cash_on_hand=Decimal('50000000.00'),
            total_equity=Decimal('50000000.00'))
        cls.round = Round.objects.create(game=cls.game, round_number=5, status='open')

        # Product chain for inventory decisions.
        gen = PlatformGenerationDefinition.objects.filter(scenario=cls.scenario).order_by('generation_order').first()
        from core.models.team_state import TeamPlatform, TeamProduct
        platform = TeamPlatform.objects.create(team=cls.team, platform_generation=gen, status='active')
        cls.product = TeamProduct.objects.create(
            team=cls.team, team_platform=platform, name='E2E Phone', positioning='premium', created_round=1)

        cls.factory = APIRequestFactory()

    # -- helpers ---------------------------------------------------------
    def _post(self, view, body):
        req = self.factory.post('/x/', body, format='json', HTTP_X_USER_ID=str(self.instructor.user_id))
        return view.as_view()(req, game_id=self.game.pk, team_id=self.team.pk, round_number=5)

    def _get(self, view):
        req = self.factory.get('/x/', HTTP_X_USER_ID=str(self.instructor.user_id))
        return view.as_view()(req, game_id=self.game.pk, team_id=self.team.pk, round_number=5)

    # -- §2.1 seed data present -----------------------------------------
    def test_01_scenario_seed_present(self):
        self.assertGreaterEqual(Supplier.objects.filter(scenario=self.scenario).count(), 20)
        self.assertGreaterEqual(ShippingLane.objects.filter(scenario=self.scenario).count(), 18)

    # -- §2.3-§2.6 submit all four SC decision families ------------------
    def test_02_submit_sourcing(self):
        r = self._post(SourcingView, {'allocations': [
            {'critical_input_category': 'semiconductor', 'supplier': self.sup_a.pk, 'allocation_pct': 60},
            {'critical_input_category': 'semiconductor', 'supplier': self.sup_b.pk, 'allocation_pct': 40},
        ]})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(SourcingAllocation.objects.filter(team=self.team).count(), 2)

    def test_03_submit_logistics(self):
        # Round 5: modal mix (R3) is unlocked -> must persist.
        r = self._post(LogisticsView, {'logistics': [
            {'lane': self.lane.pk, 'mode_sea_pct': 100, 'mode_air_pct': 0, 'mode_rail_pct': 0, 'mode_road_pct': 0},
        ]})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(LogisticsDecision.objects.filter(team=self.team, lane=self.lane).count(), 1)

    def test_04_submit_trade_finance_and_inventory(self):
        # Round 5: trade finance (R4) and inventory buffer (R3) are unlocked.
        rt = self._post(TradeFinanceView, {'trade_finance': [
            {'segment': self.segment.pk, 'market': self.market.pk, 'buyer_payment_instrument': 'letter_of_credit'}]})
        self.assertEqual(rt.status_code, 201, rt.data)
        self.assertEqual(TradeFinanceDecision.objects.filter(team=self.team).count(), 1)
        ri = self._post(InventoryView, {'inventory': [
            {'product': self.product.pk, 'market': self.market.pk, 'buffer_days': 45, 'safety_stock_trigger_pct': 25}]})
        self.assertEqual(ri.status_code, 201, ri.data)
        self.assertEqual(InventoryDecision.objects.filter(team=self.team).count(), 1)

    # -- §2.7 dashboard-equivalent reads --------------------------------
    def test_05_dashboard_reads_submitted_sourcing(self):
        self._post(SourcingView, {'allocations': [
            {'critical_input_category': 'semiconductor', 'supplier': self.sup_a.pk, 'allocation_pct': 100}]})
        g = self._get(SourcingView)
        self.assertEqual(g.status_code, 200)
        self.assertEqual(len(g.data['allocations']), 1)
        self.assertEqual(g.data['allocations'][0]['allocation_pct'], 100)

    # -- §2.8-§2.10 lock + advance round, no crash with SC data ----------
    def test_06_advance_requires_lock(self):
        from core.engine.advance_round import advance_round
        with self.assertRaises(ValueError):
            advance_round(self.game.id)  # team not locked yet

    def test_07_lock_and_advance_no_crash(self):
        # Submit a sourcing decision so SC data is present, then lock + advance.
        self._post(SourcingView, {'allocations': [
            {'critical_input_category': 'semiconductor', 'supplier': self.sup_a.pk, 'allocation_pct': 100}]})
        DecisionSubmission.objects.update_or_create(
            team=self.team, round=self.round, defaults={'status': 'locked'})
        from core.engine.advance_round import advance_round
        # dry_run runs Phase 1 synchronously (Phase 2 is an async background thread);
        # this proves round advancement does not crash with SC data present.
        result = advance_round(self.game.id, dry_run=True)
        self.assertIsInstance(result, dict)

    # -- §2.12 / §4.5 determinism of seeded data ------------------------
    def test_08_seed_determinism(self):
        fingerprint = {
            'suppliers': Supplier.objects.filter(scenario=self.scenario).count(),
            'lanes': ShippingLane.objects.filter(scenario=self.scenario).count(),
            'tf': TradeFinanceInstrument.objects.filter(scenario=self.scenario).count(),
            'tsmc_price': str(Supplier.objects.get(scenario=self.scenario, supplier_id='tsmc_taiwan').base_unit_price_usd),
        }
        # Same YAML seed must reproduce the same fingerprint deterministically.
        self.assertEqual(fingerprint, {'suppliers': 25, 'lanes': 20, 'tf': 6, 'tsmc_price': '45.00'})

    # -- UX #8: starting SC posture is seeded (fired at game start) ----------
    def test_09_starting_posture_seed(self):
        from core.services.sc_posture import seed_starting_posture
        from core.models.sc_decisions import LogisticsDecision
        r6 = Round.objects.create(game=self.game, round_number=6, status='pending')
        self.assertEqual(SourcingAllocation.objects.filter(team=self.team, round=r6).count(), 0)
        n = seed_starting_posture(self.game, r6)
        self.assertEqual(n, 1)  # the game's single team
        self.assertGreater(SourcingAllocation.objects.filter(team=self.team, round=r6).count(), 0)
        self.assertGreater(LogisticsDecision.objects.filter(team=self.team, round=r6).count(), 0)
        # idempotent — reseeding does not duplicate
        before = SourcingAllocation.objects.filter(team=self.team, round=r6).count()
        seed_starting_posture(self.game, r6)
        self.assertEqual(SourcingAllocation.objects.filter(team=self.team, round=r6).count(), before)
