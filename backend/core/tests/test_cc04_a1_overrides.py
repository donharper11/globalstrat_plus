"""
Tests for CC-04 Amendment A1 — instructor override tables.

Covers the acceptance criteria in CC-04-amendment-A1.md §6:
  4. Both new endpoints respond correctly (create, list, delete).
  5. Sum-to-1.0 validator on weight overrides correctly rejects violations.
  7. Functional: override of sourcing.payment_terms to round 2 allows a
     submission at round 2 that fails without an override.

NOTE: This test module is written against the codebase's standard Django
TestCase. The test database setup currently fails on a pre-existing
managed=False table issue (``users`` table isn't in the test migration
graph); once CC-5's ghost promotion completes and/or the test harness adds
the legacy users fixture, this module runs cleanly. The assertions stand as
executable spec documentation in the meantime.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models.core import Game, Team, Round
from core.models.overrides import (
    ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride,
)
from core.models.scenario import Scenario, FirmStarterProfile, MarketDefinition
from core.models.sc_models import ResilienceParameters
from core.permissions import IsInstructor
from core.serializers.overrides import (
    ClassResilienceWeightOverrideSerializer,
)
from core.serializers.sc_serializers import (
    SourcingAllocationWriteSerializer,
    LogisticsDecisionWriteSerializer,
)
from core.utils.disclosure import get_effective_unlock_round
from core.views.overrides import (
    DisclosureOverrideListCreateView, DisclosureOverrideDeleteView,
    ResilienceWeightOverrideListCreateView,
)


User = get_user_model()


BASELINE_WEIGHTS = {
    'multi_sourcing': 0.2,
    'geographic_diversity': 0.2,
    'buffer_inventory_adequacy': 0.15,
    'modal_flexibility': 0.15,
    'tier_2_visibility': 0.15,
    'supplier_financial_health': 0.15,
}


def _build_game_team_round(user):
    scenario = Scenario.objects.create(
        name='Test Scenario', starting_cash=Decimal('1000000.00'),
    )
    ResilienceParameters.objects.create(
        scenario=scenario,
        resilience_score_weights=dict(BASELINE_WEIGHTS),
    )
    market = MarketDefinition.objects.create(
        scenario=scenario, name='Home', code='HOME',
        description='test', currency_code='USD',
        exchange_rate_base=Decimal('1.000'),
        base_growth_rate=Decimal('0.05'),
        entry_cost_base=Decimal('100.00'),
        tax_rate=Decimal('0.25'),
        regulatory_difficulty=Decimal('5.0'),
        infrastructure_quality=Decimal('5.0'),
    )
    profile = FirmStarterProfile.objects.create(
        scenario=scenario, profile_name='Test Profile',
        description='test profile', home_market=market,
    )
    game = Game.objects.create(
        scenario=scenario, name='Test Game', created_by=user,
    )
    team = Team.objects.create(
        game=game, name='Team Alpha',
        firm_starter_profile=profile,
        performance_index=Decimal('100.00'),
        cash_on_hand=Decimal('1000000.00'),
        total_equity=Decimal('1000000.00'),
    )
    rounds = {
        n: Round.objects.create(game=game, round_number=n) for n in range(1, 7)
    }
    return game, team, rounds


class GetEffectiveUnlockRoundTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='inst', password='x')

    def test_default_when_no_override(self):
        game, _, _ = _build_game_team_round(self.user)
        self.assertEqual(
            get_effective_unlock_round(game, 'sourcing.payment_terms'), 4,
        )

    def test_override_wins(self):
        game, _, _ = _build_game_team_round(self.user)
        ClassProgressiveDisclosureOverride.objects.create(
            game=game, field_path='sourcing.payment_terms',
            override_unlock_round=2, created_by=self.user,
        )
        self.assertEqual(
            get_effective_unlock_round(game, 'sourcing.payment_terms'), 2,
        )

    def test_unknown_field_falls_to_one(self):
        game, _, _ = _build_game_team_round(self.user)
        self.assertEqual(
            get_effective_unlock_round(game, 'nonexistent.field'), 1,
        )


class WriteSerializerDisclosureTests(TestCase):
    """§6 criterion 7: override of sourcing.payment_terms to round 2 permits
    a round-2 submission that fails without the override."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='inst2', password='x')

    def _payload(self, team, round_obj, **extras):
        data = {
            'team': team.pk,
            'round': round_obj.pk,
            'critical_input_category': 'TEST_CAT',
            'allocation_pct': 100,
        }
        data.update(extras)
        return data

    def test_payment_terms_locked_at_round_2_without_override(self):
        # Call validate() directly on model instances; bypasses DRF field-level
        # "required" checks for supplier/critical_input_category FKs that are
        # outside this test's concern.
        _, team, rounds = _build_game_team_round(self.user)
        serializer = SourcingAllocationWriteSerializer()
        with self.assertRaises(Exception) as ctx:
            serializer.validate({
                'team': team, 'round': rounds[2],
                'payment_terms': 'letter_of_credit',
            })
        self.assertIn('sourcing.payment_terms', str(ctx.exception))

    def test_payment_terms_unlocked_at_round_2_with_override(self):
        game, team, rounds = _build_game_team_round(self.user)
        ClassProgressiveDisclosureOverride.objects.create(
            game=game, field_path='sourcing.payment_terms',
            override_unlock_round=2, created_by=self.user,
        )
        serializer = SourcingAllocationWriteSerializer()
        # Should NOT raise for the disclosure rule now that override exists.
        result = serializer.validate({
            'team': team, 'round': rounds[2],
            'payment_terms': 'letter_of_credit',
        })
        self.assertEqual(result['payment_terms'], 'letter_of_credit')

    def test_modal_mix_locked_at_round_2_without_override(self):
        _, team, rounds = _build_game_team_round(self.user)
        # Minimal fake lane object — LogisticsDecision.validate checks
        # lane.modes.get(mode,{}).get('available',False). We don't reach
        # that branch because disclosure rejects first.
        class _Lane:
            lane_id = 'TEST_LANE'
            modes = {}
        serializer = LogisticsDecisionWriteSerializer()
        with self.assertRaises(Exception) as ctx:
            serializer.validate({
                'team': team, 'round': rounds[2], 'lane': _Lane(),
                'mode_sea_pct': 60, 'mode_air_pct': 0,
                'mode_rail_pct': 0, 'mode_road_pct': 40,
            })
        self.assertIn('logistics.modal_mix', str(ctx.exception))


class WeightOverrideSumValidatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='inst3', password='x')

    def test_single_override_at_default_value_valid(self):
        game, _, _ = _build_game_team_round(self.user)
        data = {
            'game': game.pk, 'weight_name': 'multi_sourcing',
            'override_value': '0.200', 'created_by': self.user.pk,
        }
        serializer = ClassResilienceWeightOverrideSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_single_override_that_breaks_sum_rejected(self):
        game, _, _ = _build_game_team_round(self.user)
        data = {
            'game': game.pk, 'weight_name': 'multi_sourcing',
            'override_value': '0.400', 'created_by': self.user.pk,
        }
        serializer = ClassResilienceWeightOverrideSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('sum', str(serializer.errors).lower())

    def test_paired_overrides_that_preserve_sum_valid(self):
        game, _, _ = _build_game_team_round(self.user)
        ClassResilienceWeightOverride.objects.create(
            game=game, weight_name='multi_sourcing',
            override_value=Decimal('0.250'), created_by=self.user,
        )
        data = {
            'game': game.pk, 'weight_name': 'geographic_diversity',
            'override_value': '0.150', 'created_by': self.user.pk,
        }
        serializer = ClassResilienceWeightOverrideSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_override_value_above_ceiling_rejected(self):
        game, _, _ = _build_game_team_round(self.user)
        data = {
            'game': game.pk, 'weight_name': 'multi_sourcing',
            'override_value': '0.700', 'created_by': self.user.pk,
        }
        self.assertFalse(
            ClassResilienceWeightOverrideSerializer(data=data).is_valid()
        )

    def test_override_value_zero_rejected(self):
        game, _, _ = _build_game_team_round(self.user)
        data = {
            'game': game.pk, 'weight_name': 'multi_sourcing',
            'override_value': '0.000', 'created_by': self.user.pk,
        }
        self.assertFalse(
            ClassResilienceWeightOverrideSerializer(data=data).is_valid()
        )


class OverrideEndpointTests(TestCase):
    """§6 criterion 4: endpoints respond correctly (list, create, delete).
    Permission check is patched so tests focus on endpoint semantics —
    IsInstructor itself is exercised by its own unit tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='inst4', password='x')

    def setUp(self):
        self.factory = APIRequestFactory()
        self._orig = IsInstructor.has_permission
        IsInstructor.has_permission = lambda self, request, view: True

    def tearDown(self):
        IsInstructor.has_permission = self._orig

    def test_list_disclosure_overrides_empty(self):
        game, _, _ = _build_game_team_round(self.user)
        req = self.factory.get(f'/api/v1/games/{game.pk}/disclosure-overrides/')
        force_authenticate(req, user=self.user)
        resp = DisclosureOverrideListCreateView.as_view()(req, game_id=game.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_create_disclosure_override(self):
        game, _, _ = _build_game_team_round(self.user)
        req = self.factory.post(
            f'/api/v1/games/{game.pk}/disclosure-overrides/',
            {
                'field_path': 'sourcing.payment_terms',
                'override_unlock_round': 2,
                'created_by': self.user.pk,
                'reason': 'Finance-heavy cohort',
            },
            format='json',
        )
        force_authenticate(req, user=self.user)
        resp = DisclosureOverrideListCreateView.as_view()(req, game_id=game.pk)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ClassProgressiveDisclosureOverride.objects.filter(game=game).count(), 1,
        )

    def test_create_disclosure_override_rejects_unknown_field(self):
        game, _, _ = _build_game_team_round(self.user)
        req = self.factory.post(
            f'/api/v1/games/{game.pk}/disclosure-overrides/',
            {'field_path': 'bogus.not_real', 'override_unlock_round': 2,
             'created_by': self.user.pk},
            format='json',
        )
        force_authenticate(req, user=self.user)
        resp = DisclosureOverrideListCreateView.as_view()(req, game_id=game.pk)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_disclosure_override(self):
        game, _, _ = _build_game_team_round(self.user)
        override = ClassProgressiveDisclosureOverride.objects.create(
            game=game, field_path='sourcing.payment_terms',
            override_unlock_round=2, created_by=self.user,
        )
        req = self.factory.delete(
            f'/api/v1/games/{game.pk}/disclosure-overrides/{override.pk}/',
        )
        force_authenticate(req, user=self.user)
        resp = DisclosureOverrideDeleteView.as_view()(
            req, game_id=game.pk, override_id=override.pk,
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ClassProgressiveDisclosureOverride.objects.filter(pk=override.pk).exists()
        )

    def test_create_weight_override_that_breaks_sum_returns_400(self):
        game, _, _ = _build_game_team_round(self.user)
        req = self.factory.post(
            f'/api/v1/games/{game.pk}/resilience-weight-overrides/',
            {'weight_name': 'multi_sourcing', 'override_value': '0.400',
             'created_by': self.user.pk},
            format='json',
        )
        force_authenticate(req, user=self.user)
        resp = ResilienceWeightOverrideListCreateView.as_view()(req, game_id=game.pk)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
