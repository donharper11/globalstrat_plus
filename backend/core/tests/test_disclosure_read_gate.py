"""V2-026 — the progressive-disclosure registry governs reads, not only writes.

`_reject_locked_fields` gated every write against `get_effective_unlock_round`.
The read serializers declared `fields = '__all__'` and consulted nothing, so a
value written legally while an instructor override was in force stayed readable
after the override was removed, in a round where the field was locked. Measured
at `progressive-disclosure-probe.json`: `inventory.buffer_days`, authored to
unlock at round 3, returned at round 1 by two surfaces.

The gate default-denies. Without a game and a round in the serializer context
there is no way to know whether a field is unlocked, and the safe answer to "I
cannot tell" is to withhold it.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.models import Game, Round, Scenario, Team
from core.models.overrides import ClassProgressiveDisclosureOverride
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.sc_decisions import InventoryDecision
from core.models.team_state import TeamPlatform, TeamProduct
from core.serializers.sc_serializers import InventoryDecisionReadSerializer
from core.utils.disclosure import get_effective_unlock_round

FIELD_PATH = 'inventory.buffer_days'
GATED = 'buffer_days'
COMPANION = 'safety_stock_trigger_pct'
SENTINEL = 4242


class DisclosureFixture(TestCase):
    def setUp(self):
        from core.engine.utils import _config_cache
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.owner = DjangoUser.objects.create(username=f'own-dg-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Disclosure {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=8)
        for key, value in (('reference_price_budget', '250'),
                           ('reference_price_mainstream', '420'),
                           ('reference_price_premium', '700'),
                           ('reference_price_ultra_premium', '1000'),
                           ('high_price_elasticity', '1.5'),
                           ('rd_spend_target', '2000000'),
                           ('optimal_rd_headcount', '60'),
                           ('optimal_commercial_headcount', '40'),
                           ('optimal_operations_headcount', '50')):
            ScenarioConfig.objects.create(
                scenario=self.scenario, config_key=key, config_value=value,
                description=key)
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Disclosure game', current_round=1,
            status='active', created_by=self.owner)
        self.other_game = Game.objects.create(
            scenario=self.scenario, name='Other class', current_round=1,
            status='active', created_by=self.owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        self.other_team = Team.objects.create(
            game=self.game, name='T2', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen', description='d',
            generation_order=1, unlock_round=1, development_cost=0,
            development_rounds=1, license_cost=0, annual_maintenance_cost=0,
            is_starting_platform=True)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='P',
            status='active')
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='Prod',
            positioning='mainstream', status='active', created_round=1)
        self.decision = InventoryDecision.objects.create(
            team=self.team, round=self.round, product=self.product,
            market=self.market, buffer_days=SENTINEL,
            safety_stock_trigger_pct=77)

    def render(self, game=None, round_number=None, omit_context=False):
        context = {} if omit_context else {
            'game': game if game is not None else self.game,
            'round_number': (round_number if round_number is not None
                             else self.round.round_number)}
        return InventoryDecisionReadSerializer(
            self.decision, context=context).data

    def override(self, game, unlock):
        return ClassProgressiveDisclosureOverride.objects.create(
            game=game, field_path=FIELD_PATH, override_unlock_round=unlock,
            created_by=self.owner)


class TheReadGate(DisclosureFixture):
    def test_the_field_is_hidden_before_its_unlock_round(self):
        self.assertEqual(get_effective_unlock_round(self.game, FIELD_PATH), 3)
        self.assertNotIn(GATED, self.render())

    def test_the_companion_gated_field_is_hidden_too(self):
        """Every registry key under the family is gated, not just one."""
        self.assertNotIn(COMPANION, self.render())

    def test_ungated_fields_are_still_returned(self):
        """The gate withholds what the registry names and nothing else."""
        rendered = self.render()
        for key in ('id', 'team', 'round', 'product', 'market'):
            self.assertIn(key, rendered)

    def test_the_value_appears_after_its_legitimate_unlock(self):
        rendered = self.render(round_number=3)
        self.assertEqual(rendered[GATED], SENTINEL)

    def test_missing_context_denies_by_default(self):
        """Cannot tell means withhold, not expose."""
        self.assertNotIn(GATED, self.render(omit_context=True))

    def test_partial_context_denies_by_default(self):
        for context in ({'game': self.game}, {'round_number': 5}):
            with self.subTest(context=sorted(context)):
                rendered = InventoryDecisionReadSerializer(
                    self.decision, context=context).data
                self.assertNotIn(GATED, rendered)


class OverrideBehaviour(DisclosureFixture):
    def test_an_override_unlocks_it_for_that_class(self):
        entry = self.override(self.game, 1)
        self.addCleanup(entry.delete)
        self.assertEqual(self.render()[GATED], SENTINEL)

    def test_restoring_the_schedule_re_hides_the_value(self):
        """The exact sequence the probe used to produce the leak."""
        entry = self.override(self.game, 1)
        self.assertEqual(self.render()[GATED], SENTINEL)
        entry.delete()
        self.assertNotIn(GATED, self.render())

    def test_another_class_override_cannot_expose_it(self):
        entry = self.override(self.other_game, 1)
        self.addCleanup(entry.delete)
        self.assertEqual(get_effective_unlock_round(self.game, FIELD_PATH), 3)
        self.assertNotIn(GATED, self.render())


class DirectObjectAccess(DisclosureFixture):
    def test_a_single_object_is_gated_exactly_as_a_list_is(self):
        """Direct-object access must not bypass what list rendering hides."""
        listed = InventoryDecisionReadSerializer(
            [self.decision], many=True,
            context={'game': self.game,
                     'round_number': self.round.round_number}).data
        single = self.render()
        self.assertNotIn(GATED, listed[0])
        self.assertNotIn(GATED, single)
        self.assertEqual(set(listed[0]), set(single))

    def test_another_teams_row_is_gated_by_the_same_round(self):
        other = InventoryDecision.objects.create(
            team=self.other_team, round=self.round, product=self.product,
            market=self.market, buffer_days=SENTINEL,
            safety_stock_trigger_pct=77)
        rendered = InventoryDecisionReadSerializer(
            other, context={'game': self.game,
                            'round_number': self.round.round_number}).data
        self.assertNotIn(GATED, rendered)


class EverySurfaceIsCovered(DisclosureFixture):
    def test_every_sc_read_serializer_declares_a_family(self):
        """A new read serializer without a family would be an open door."""
        from core.serializers import sc_serializers as mod
        from core.serializers.sc_serializers import DisclosureGatedReadMixin
        missing = []
        for name in dir(mod):
            if not name.endswith('ReadSerializer'):
                continue
            cls = getattr(mod, name)
            if not isinstance(cls, type):
                continue
            if not issubclass(cls, DisclosureGatedReadMixin):
                missing.append(name)
            elif cls.disclosure_family is None:
                missing.append(name)
        self.assertEqual(missing, [])

    def test_no_serializer_anywhere_exposes_a_gated_field_ungated(self):
        """The contract that matters: exposure implies gating.

        `esg` and `plants` fields are gated on write and are currently absent
        from every serializer's field list, so nothing exposes them. That is
        incidental rather than enforced -- adding one name to one list would
        reopen the hole silently. This walks every serializer in the package
        and fails if any renders a registry-gated field without the gate.
        """
        import importlib
        import inspect
        import pkgutil
        from rest_framework import serializers as drf
        from core.serializers.sc_serializers import DisclosureGatedReadMixin
        from core.utils.disclosure import DEFAULT_UNLOCK_ROUNDS
        import core.serializers as package

        gated_by_family = {}
        for path in DEFAULT_UNLOCK_ROUNDS:
            family, _, name = path.partition('.')
            gated_by_family.setdefault(family, set()).add(name)
        every_gated_name = {n for names in gated_by_family.values()
                            for n in names}

        offenders = []
        for module_info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(
                f'core.serializers.{module_info.name}')
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if not issubclass(cls, drf.ModelSerializer):
                    continue
                if cls.__module__ != module.__name__:
                    continue
                # Write serializers are gated at validate() by
                # _reject_locked_fields, which refuses a locked field outright
                # rather than hiding it. That is a different control with its
                # own tests; this contract is about what a read renders.
                if name.endswith('WriteSerializer'):
                    continue
                try:
                    rendered = set(cls().fields.keys())
                except Exception:
                    # A serializer that cannot be built renders nothing and so
                    # exposes nothing. Fall back to its declared field list,
                    # which is what it would render if it were repaired, so a
                    # gated field named there is still caught.
                    # core.serializers.core.UserSerializer is one of these: it
                    # declares `team`, which is not a field on User, and raises
                    # ImproperlyConfigured. That is a real defect and unrelated
                    # to disclosure; it is recorded in the CRV2-06 report
                    # rather than repaired here, where the budget is focused
                    # authorization work.
                    declared = getattr(getattr(cls, 'Meta', None), 'fields', None)
                    rendered = (set(declared)
                                if isinstance(declared, (list, tuple)) else set())
                risky = rendered & every_gated_name
                if not risky:
                    continue
                family = getattr(cls, 'disclosure_family', None)
                if (not issubclass(cls, DisclosureGatedReadMixin)
                        or family is None
                        or not risky <= gated_by_family.get(family, set())):
                    offenders.append(
                        f'{module.__name__}.{name} renders {sorted(risky)} '
                        f'with disclosure_family={family!r}')
        self.assertEqual(offenders, [])
