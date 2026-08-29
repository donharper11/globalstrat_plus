"""V2-023 — retail price is scored against a scenario-authored reference.

The adopted rule::

    price_ratio = team_retail_price / scenario_reference_price
    price_competitiveness = clamp(f_max * (1.5 - price_ratio), f_min, f_max)

The rule it replaced averaged over the teams sharing a product's positioning in
a market and then appended the team's own price to that average. A team alone
in its positioning was compared against itself, so the ratio was exactly 1.0 at
every price and price stopped affecting demand entirely: 3600.37 units sold at
$50, $420 and $2,000 alike, with revenue rising fortyfold and no volume
penalty. These tests are written against the properties that failure violated,
not against the arithmetic of the replacement.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.engine.preference_engine import _derive_price_competitiveness
from core.engine.utils import (InvalidScenarioConfiguration, RoundContext,
                               _config_cache, high_price_demand_multiplier,
                               scenario_high_price_elasticity,
                               scenario_reference_price,
                               scenario_reference_prices)
from core.models import Game, Round, Scenario, Team
from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.team_state import TeamPlatform, TeamProduct

F_MIN, F_MAX = 0.0, 1.0
# The authored tier references: the starting price schedule, promoted into
# scenario configuration. A single global reference scored a premium product at
# its own authored price as 1.667x, clamping its competitiveness to zero and
# taking 53% of its demand -- the tiers were penalised for existing.
TIERS = {'budget': '250', 'mainstream': '420', 'premium': '700',
         'ultra_premium': '1000'}
REFERENCE = TIERS['mainstream']
ELASTICITY = '1.5'


class ReferencePriceFixture(TestCase):
    """Two teams: one alone in its positioning, one sharing it.

    The same shape as the confirmation gate that measured the exploit, so a
    regression reproduces here rather than only in a disposable database.
    """

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        owner = DjangoUser.objects.create(username=f'owner-rp-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Reference {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        self.tier_config = {
            positioning: ScenarioConfig.objects.create(
                scenario=self.scenario,
                config_key=f'reference_price_{positioning}',
                config_value=value, description=f'{positioning} reference')
            for positioning, value in TIERS.items()}
        self.config = self.tier_config['mainstream']
        self.elasticity_config = ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='high_price_elasticity',
            config_value=ELASTICITY, description='elasticity')
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Reference game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())

        self.generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen', description='d',
            generation_order=1, unlock_round=1, development_cost=0,
            development_rounds=1, license_cost=0, annual_maintenance_cost=0,
            is_starting_platform=True)

        # `alone` holds 'premium' by itself; `shared` and `rival` both hold
        # 'mainstream'. Under the old rule these two groups scored differently
        # at the same price; that is the property the disposition removes.
        self.alone = self._team('Alone', profile)
        self.shared = self._team('Shared', profile)
        self.rival = self._team('Rival', profile)
        self.alone_product = self._product(self.alone, 'Solo', 'premium')
        self.shared_product = self._product(self.shared, 'Crowd', 'mainstream')
        self.rival_product = self._product(self.rival, 'Rival', 'mainstream')
        self.tier_products = {
            positioning: self._product(self.alone, f'P-{positioning}',
                                       positioning)
            for positioning in TIERS}
        self.context = RoundContext(self.game, 1)

    def _team(self, name, profile):
        return Team.objects.create(
            game=self.game, name=name, firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)

    def _product(self, team, name, positioning):
        platform = TeamPlatform.objects.create(
            team=team, platform_generation=self.generation, name='P',
            status='active')
        return TeamProduct.objects.create(
            team=team, team_platform=platform, name=name,
            positioning=positioning, status='active', created_round=1)

    def _decision(self, team, product, price):
        submission, _ = DecisionSubmission.objects.get_or_create(
            round=self.round, team=team, defaults={'status': 'submitted'})
        decision, _ = DecisionMarketing.objects.update_or_create(
            submission=submission, team_product=product, market=self.market,
            defaults=dict(
                retail_price=price, promotion_budget=0,
                campaign_focus_feature_ids=[], channel_digital_pct=0,
                channel_traditional_pct=0, channel_trade_pct=0,
                distribution_strategy='hybrid', distribution_investment=0,
                production_volume=0, production_source_market=self.market,
                demand_estimate=0))
        return decision

    def score(self, team, product, price):
        decision = self._decision(team, product, price)
        return _derive_price_competitiveness(
            self.context, team, product, self.market, decision, F_MIN, F_MAX)


class PriceResponse(ReferencePriceFixture):
    def test_the_three_gate_prices_are_strictly_decreasing(self):
        """$50, $420 and $2,000 must not score the same, in that order."""
        scores = [self.score(self.alone, self.alone_product, price)
                  for price in ('50', '420', '2000')]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(scores[0] > scores[1] > scores[2],
                        f'price competitiveness did not fall: {scores}')

    def test_every_tier_scores_exactly_average_at_its_own_reference(self):
        for positioning, price in TIERS.items():
            with self.subTest(positioning=positioning):
                self.assertAlmostEqual(
                    self.score(self.alone, self.tier_products[positioning],
                               price),
                    (F_MAX + F_MIN) / 2, places=9)

    def test_every_authored_starting_price_has_multiplier_one(self):
        for positioning, price in TIERS.items():
            with self.subTest(positioning=positioning):
                self.assertEqual(
                    high_price_demand_multiplier(
                        float(price), float(TIERS[positioning]),
                        float(ELASTICITY)),
                    1.0)

    def test_equal_relative_deviations_are_treated_equally_across_tiers(self):
        """The tiers differ in price and must not differ in treatment."""
        for factor in (0.6, 0.8, 1.0, 1.25, 1.6):
            scores, multipliers = set(), set()
            for positioning, price in TIERS.items():
                deviated = str(round(float(price) * factor, 2))
                scores.add(round(self.score(
                    self.alone, self.tier_products[positioning], deviated), 9))
                multipliers.add(round(high_price_demand_multiplier(
                    float(deviated), float(price), float(ELASTICITY)), 9))
            with self.subTest(factor=factor):
                self.assertEqual(len(scores), 1, f'{factor}: {scores}')
                self.assertEqual(len(multipliers), 1, f'{factor}: {multipliers}')

    def test_the_high_price_tail_is_bounded_within_every_tier(self):
        for positioning, price in TIERS.items():
            reference = float(price)
            revenue = [p * high_price_demand_multiplier(
                p, reference, float(ELASTICITY))
                for p in (reference, reference * 1.5, reference * 5,
                          reference * 50, reference * 500)]
            with self.subTest(positioning=positioning):
                for earlier, later in zip(revenue, revenue[1:]):
                    self.assertLess(later, earlier)

    def test_the_isolated_exploit_probe_fails(self):
        """The original exploit: 40x the price, unchanged competitiveness."""
        cheap = self.score(self.alone, self.alone_product, '50')
        dear = self.score(self.alone, self.alone_product, '2000')
        self.assertNotAlmostEqual(
            cheap, dear, places=6,
            msg='a team alone in its positioning still scores the same at $50 '
                'and $2,000 -- V2-023 has regressed')
        self.assertGreater(cheap - dear, 0.4)


class IndependenceOfOtherTeams(ReferencePriceFixture):
    def test_isolated_and_shared_teams_are_treated_alike(self):
        """Sharing a positioning must not change how a price is scored.

        The two subjects sit in different tiers -- alone is premium, shared is
        mainstream -- so the comparison is at equal *relative* prices, which is
        what equal treatment means once each tier has its own reference. The
        earlier version compared equal absolute prices and passed only because
        every tier shared one reference; under the revised rule that comparison
        asks a premium product and a mainstream product to score the same at
        $420, which is the incoherence this revision removes.
        """
        for factor in (0.25, 0.5, 1.0, 1.5, 3.0):
            alone_price = str(round(float(TIERS['premium']) * factor, 2))
            shared_price = str(round(float(TIERS['mainstream']) * factor, 2))
            with self.subTest(factor=factor):
                self.assertAlmostEqual(
                    self.score(self.alone, self.alone_product, alone_price),
                    self.score(self.shared, self.shared_product, shared_price),
                    places=9)

    def test_adding_a_team_does_not_move_an_existing_score(self):
        before = self.score(self.alone, self.alone_product, '900')
        newcomer = self._team('Newcomer', self.alone.firm_starter_profile)
        product = self._product(newcomer, 'Late', 'solo')
        self._decision(newcomer, product, '75')
        after = self.score(self.alone, self.alone_product, '900')
        self.assertAlmostEqual(before, after, places=9)

    def test_removing_a_team_does_not_move_an_existing_score(self):
        self._decision(self.rival, self.rival_product, '90')
        before = self.score(self.shared, self.shared_product, '900')
        DecisionMarketing.objects.filter(team_product=self.rival_product).delete()
        after = self.score(self.shared, self.shared_product, '900')
        self.assertAlmostEqual(before, after, places=9)

    def test_repricing_a_rival_does_not_move_an_existing_score(self):
        rival_decision = self._decision(self.rival, self.rival_product, '100')
        before = self.score(self.shared, self.shared_product, '900')
        rival_decision.retail_price = 3000
        rival_decision.save(update_fields=['retail_price'])
        after = self.score(self.shared, self.shared_product, '900')
        self.assertAlmostEqual(before, after, places=9)

    def test_repositioning_a_rival_does_not_move_an_existing_score(self):
        self._decision(self.rival, self.rival_product, '100')
        before = self.score(self.shared, self.shared_product, '900')
        self.rival_product.positioning = 'premium'
        self.rival_product.save(update_fields=['positioning'])
        after = self.score(self.shared, self.shared_product, '900')
        self.assertAlmostEqual(before, after, places=9)

    def test_collective_inflation_cannot_preserve_demand(self):
        """Every team raising price together must cost every team.

        Under the old relative rule a cartel was invisible: if everyone
        doubled, the average doubled and nobody's score moved.
        """
        cheap = [self.score(team, product, '200') for team, product in (
            (self.alone, self.alone_product),
            (self.shared, self.shared_product),
            (self.rival, self.rival_product))]
        DecisionMarketing.objects.all().delete()
        dear = [self.score(team, product, '1600') for team, product in (
            (self.alone, self.alone_product),
            (self.shared, self.shared_product),
            (self.rival, self.rival_product))]
        for before, after in zip(cheap, dear):
            self.assertGreater(before, after)


class ConfigurationFailsClosed(ReferencePriceFixture):
    def test_every_legal_positioning_must_have_a_reference(self):
        for positioning in TIERS:
            with self.subTest(positioning=positioning):
                row = self.tier_config[positioning]
                value = row.config_value
                row.delete()
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_reference_prices(self.scenario)
                self.tier_config[positioning] = ScenarioConfig.objects.create(
                    scenario=self.scenario,
                    config_key=f'reference_price_{positioning}',
                    config_value=value, description='restored')
                _config_cache.clear()
        self.config = self.tier_config['mainstream']

    def test_zero_negative_and_non_finite_references_are_refused(self):
        for value in ('0', '-1', '-420.5', 'nan', 'inf'):
            with self.subTest(value=value):
                self.config.config_value = value
                self.config.save(update_fields=['config_value'])
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_reference_prices(self.scenario)

    def test_scoring_refuses_rather_than_falling_back_to_a_team_price(self):
        """The fallback is the defect; there must not be one."""
        self.config.delete()
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfiguration):
            self.score(self.alone, self.alone_product, '420')

    def test_resolution_refuses_before_any_competitive_write(self):
        from core.engine.advance_round import (
            InvalidScenarioConfigurationError, _run_phase_1)
        # Satisfy every earlier precondition, so the refusal under test is the
        # configuration one and not a round that was never ready.
        for team, product in ((self.alone, self.alone_product),
                              (self.shared, self.shared_product),
                              (self.rival, self.rival_product)):
            self._decision(team, product, '420')
        DecisionSubmission.objects.filter(round=self.round).update(
            status='locked')
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        self.config.delete()
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfigurationError):
            _run_phase_1(self.game.id)
        self.round.refresh_from_db()
        self.assertNotEqual(
            self.round.processing_status, 'PROCESSING',
            'the round was marked processing before configuration was checked')


class DeterministicInputEnvelope(ReferencePriceFixture):
    def test_the_complete_mapping_and_elasticity_are_in_the_manifest(self):
        from core.services.manifest_sections import (CONFIG_SECTION_NAMES,
                                                     INPUT_SECTIONS)
        from core.services.manifest_snapshot import build_snapshot
        sections = tuple(s for s in INPUT_SECTIONS
                         if s.name in CONFIG_SECTION_NAMES)
        rows = build_snapshot(sections, 'input', self.scenario.id,
                              self.game.id).rows['scenario_config']
        keys = {row.get('config_key') for row in rows}
        for positioning in TIERS:
            with self.subTest(positioning=positioning):
                self.assertIn(f'reference_price_{positioning}', keys)
        self.assertIn('high_price_elasticity', keys)

    def test_the_reference_price_is_in_the_input_manifest(self):
        from core.services.manifest_sections import (CONFIG_SECTION_NAMES,
                                                     INPUT_SECTIONS)
        names = {section.name for section in INPUT_SECTIONS}
        self.assertIn('scenario_config', names)
        self.assertIn('scenario_config', CONFIG_SECTION_NAMES)

    def test_changing_the_reference_changes_the_config_digest(self):
        from core.services.manifest_sections import (CONFIG_SECTION_NAMES,
                                                     INPUT_SECTIONS)
        from core.services.manifest_snapshot import build_snapshot
        sections = tuple(s for s in INPUT_SECTIONS
                         if s.name in CONFIG_SECTION_NAMES)

        def digest():
            snapshot = build_snapshot(sections, 'input', self.scenario.id,
                                      self.game.id)
            return snapshot.section_digests()['scenario_config']

        before = digest()
        self.config.config_value = '999'
        self.config.save(update_fields=['config_value'])
        _config_cache.clear()
        self.assertNotEqual(before, digest())


class HighPriceTail(ReferencePriceFixture):
    """Above the price-fit clamp, demand must still fall.

    `price_competitiveness` is a bounded feature: with f_max 1.0 it reaches
    zero at 1.5x the reference -- $630 here -- and clamps. Every price above
    that scores identically, so fit alone cannot bound the tail, and revenue
    went on multiplying by price. These tests probe above the clamp, which the
    first round of V2-023 evidence did not: it stopped at $2,000 and reported a
    response measured entirely below the point where the response stops.
    """

    def multiplier(self, price):
        return high_price_demand_multiplier(
            float(price), float(REFERENCE), float(ELASTICITY))

    def test_price_fit_really_does_clamp_above_the_floor(self):
        """The premise of the defect, asserted rather than assumed.

        The clamp point is 1.5x the product's *own* tier reference. This test
        previously used $630 against the alone product, which is premium: $630
        is below the $700 premium reference, so it scored 0.6 rather than
        clamping. The old figure was the clamp point of a single global $420
        reference that no longer exists.
        """
        reference = float(TIERS['premium'])
        clamped = [self.score(self.alone, self.alone_product, str(price))
                   for price in (reference * 1.5, reference * 5,
                                 reference * 50, reference * 500)]
        self.assertEqual(clamped, [0.0, 0.0, 0.0, 0.0])

    def test_demand_keeps_falling_above_the_clamp_point(self):
        prices = ('630', '2000', '20000', '200000')
        multipliers = [self.multiplier(p) for p in prices]
        self.assertEqual(multipliers, sorted(multipliers, reverse=True))
        for earlier, later in zip(multipliers, multipliers[1:]):
            self.assertLess(later, earlier)

    def test_revenue_falls_as_price_rises_above_the_reference(self):
        """Revenue is price x multiplier x whatever fit leaves; the first two
        terms alone must already be falling, or the tail is unbounded."""
        revenue = [float(price) * self.multiplier(price)
                   for price in ('420', '630', '2000', '20000', '200000')]
        for earlier, later in zip(revenue, revenue[1:]):
            self.assertLess(later, earlier)

    def test_revenue_is_bounded_over_an_unbounded_price_range(self):
        """No price, however large, beats the reference on revenue."""
        at_reference = float(REFERENCE) * self.multiplier(REFERENCE)
        for price in ('1000', '10000', '1000000', '100000000'):
            with self.subTest(price=price):
                self.assertLess(float(price) * self.multiplier(price),
                                at_reference)

    def test_the_multiplier_is_one_at_and_below_the_reference(self):
        for price in ('1', '50', '419', '420'):
            with self.subTest(price=price):
                self.assertEqual(self.multiplier(price), 1.0)

    def test_the_multiplier_is_continuous_at_the_reference(self):
        just_above = self.multiplier('420.01')
        self.assertLess(just_above, 1.0)
        self.assertAlmostEqual(just_above, 1.0, places=4)

    def test_the_multiplier_ignores_every_other_team(self):
        """Absolute, not a share adjustment: nothing about rivals enters it."""
        before = self.multiplier('2000')
        self._decision(self.rival, self.rival_product, '2000')
        self._decision(self.shared, self.shared_product, '50')
        self.assertEqual(self.multiplier('2000'), before)


class ElasticityConfiguration(ReferencePriceFixture):
    def test_a_valid_elasticity_is_returned(self):
        self.assertEqual(scenario_high_price_elasticity(self.scenario), 1.5)

    def test_missing_elasticity_is_refused(self):
        self.elasticity_config.delete()
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfiguration):
            scenario_high_price_elasticity(self.scenario)

    def test_an_elasticity_of_one_or_less_is_refused(self):
        """At exactly 1 revenue is flat above the reference, not falling."""
        for value in ('1', '1.0', '0.5', '0', '-2'):
            with self.subTest(value=value):
                self.elasticity_config.config_value = value
                self.elasticity_config.save(update_fields=['config_value'])
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_high_price_elasticity(self.scenario)

    def test_a_non_finite_elasticity_is_refused(self):
        for value in ('inf', '-inf', 'nan'):
            with self.subTest(value=value):
                self.elasticity_config.config_value = value
                self.elasticity_config.save(update_fields=['config_value'])
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_high_price_elasticity(self.scenario)

    def test_resolution_refuses_before_any_competitive_write(self):
        from core.engine.advance_round import (
            InvalidScenarioConfigurationError, _run_phase_1)
        for team, product in ((self.alone, self.alone_product),
                              (self.shared, self.shared_product),
                              (self.rival, self.rival_product)):
            self._decision(team, product, '420')
        DecisionSubmission.objects.filter(round=self.round).update(
            status='locked')
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        self.elasticity_config.config_value = '0.9'
        self.elasticity_config.save(update_fields=['config_value'])
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfigurationError):
            _run_phase_1(self.game.id)
        self.round.refresh_from_db()
        self.assertNotEqual(
            self.round.processing_status, 'PROCESSING',
            'the round was marked processing before configuration was checked')

    def test_the_elasticity_is_in_the_deterministic_input_envelope(self):
        from core.services.manifest_sections import (CONFIG_SECTION_NAMES,
                                                     INPUT_SECTIONS)
        from core.services.manifest_snapshot import build_snapshot
        sections = tuple(s for s in INPUT_SECTIONS
                         if s.name in CONFIG_SECTION_NAMES)

        def digest():
            return build_snapshot(sections, 'input', self.scenario.id,
                                  self.game.id).section_digests()['scenario_config']

        before = digest()
        self.elasticity_config.config_value = '2.75'
        self.elasticity_config.save(update_fields=['config_value'])
        _config_cache.clear()
        self.assertNotEqual(before, digest())
