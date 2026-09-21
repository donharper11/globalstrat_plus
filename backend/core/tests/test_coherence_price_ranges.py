"""N3 — positioning-price coherence is scored in the scenario's own prices.

``core/engine/coherence.py`` scored every retail price against a hard-coded
dollar ladder (``PRICE_RANGES``: budget 100-300, mainstream 250-550, premium
500-900, ultra-premium 800-1500). Those dollars fit Consumer Electronics only.
Clean Energy starter products are authored at $850-$12,000 and Media's at
$55-$340, so the component was 0.0 for every Clean Energy product and most
Media products whatever the team decided -- V2-114's defect in a second place.

THE DERIVATION RULE these tests pin (a proposal, pending owner confirmation):
each bound of the old ladder is read as a ratio of the Consumer Electronics
reference price for its tier, and the same ratio is applied to the running
scenario's own reference price for that tier::

    bound(scenario, tier) = old_bound(tier) * reference(scenario, tier)
                                            / reference(Consumer Electronics, tier)

No number is introduced: the ladder and the Consumer Electronics references
(250 / 420 / 700 / 1000, V2-023) both already existed.

Consumer Electronics must come out byte-identical, because the range is written
into ``RoundResultCoherence.breakdown`` and that row is inside the hashed
``coherence`` manifest section. ``_legacy_score_positioning_price`` below is the
function as it stood before the change, kept verbatim as the oracle.
"""
import io
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.test import TestCase

from core.engine import coherence
from core.engine.utils import (InvalidScenarioConfiguration, _config_cache,
                               scenario_reference_prices)
from core.models import DecisionSubmission, Game, Round, Team
from core.models.decisions import DecisionMarketing
from core.models.scenario import FirmStarterProduct, Scenario, ScenarioConfig
from core.models.team_state import TeamProduct, TeamProductMarket

SCENARIO_DIR = Path(__file__).resolve().parents[2] / 'scenarios'
CONSUMER_ELECTRONICS = 'consumer_electronics_2026.yaml'
CLEAN_ENERGY = 'clean_energy_tech_2026.yaml'
MEDIA = 'media_entertainment_2026.yaml'

# The ladder exactly as it was hard-coded before N3. Deliberately a second copy:
# if someone edits `coherence.PRICE_RANGES`, this is what notices.
LEGACY_PRICE_RANGES = {
    'budget': (100, 300),
    'mainstream': (250, 550),
    'premium': (500, 900),
    'ultra_premium': (800, 1500),
}


def _legacy_score_positioning_price(team, submission):
    """`_score_positioning_price` as it stood at f46d173, verbatim."""
    score = 0.0
    max_possible = 0.0
    details = []

    if not submission:
        return score, max_possible, details

    for md in (submission.marketing_decisions.all()
               .select_related('team_product', 'market')
               .order_by('team_product__name', 'market__code')):
        if md.retail_price is None:
            continue
        positioning = md.team_product.positioning
        price = float(md.retail_price)
        price_range = LEGACY_PRICE_RANGES.get(positioning, (0, 9999))
        min_p, max_p = price_range

        if min_p <= price <= max_p:
            s = 1.0
            aligned = True
        elif price < min_p * 0.8 or price > max_p * 1.2:
            s = 0.0
            aligned = False
        else:
            s = 0.5
            aligned = False

        score += s
        max_possible += 1.0
        details.append({
            'product': md.team_product.name,
            'market': md.market.name,
            'price': price,
            'range': f'{min_p}-{max_p}',
            'aligned': aligned,
        })

    return score, max_possible, details


class _ScenarioFixture(TestCase):

    @classmethod
    def setUpTestData(cls):
        DjangoUser.objects.create_superuser(
            'coherence-range-fixture-owner', 'fixture@example.com', 'x')

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)

    def _load(self, filename):
        call_command('load_scenario', file=str(SCENARIO_DIR / filename),
                     verbosity=0, stdout=io.StringIO())
        _config_cache.clear()
        return Scenario.objects.order_by('-id').first()

    def _game(self, scenario):
        name = f'coherence-range-fixture-{scenario.id}'
        call_command('initialize_game', scenario=scenario.id, teams=3,
                     name=name, stdout=io.StringIO())
        game = Game.objects.filter(name=name).order_by('-id').first()
        return game, Round.objects.get(game=game, round_number=1)

    def _price(self, submission, product, price):
        """One marketing row for `product` in the first market it is sold in."""
        market = (TeamProductMarket.objects.filter(team_product=product)
                  .order_by('market__code').first().market)
        DecisionMarketing.objects.update_or_create(
            submission=submission, team_product=product, market=market,
            defaults=dict(
                retail_price=price, promotion_budget=Decimal('0'),
                campaign_focus_feature_ids=[],
                channel_digital_pct=Decimal('1'),
                channel_traditional_pct=Decimal('0'),
                channel_trade_pct=Decimal('0'),
                distribution_strategy='hybrid',
                distribution_investment=Decimal('0'),
                sales_team_count=1, production_volume=0, demand_estimate=0,
                production_source_market=market))


class DerivedRangesTests(_ScenarioFixture):

    def test_basis_references_are_the_shipped_consumer_electronics_ones(self):
        """The denominators are the scenario's numbers, not a private copy."""
        scenario = self._load(CONSUMER_ELECTRONICS)
        self.assertEqual(
            scenario_reference_prices(scenario),
            {tier: float(value) for tier, value
             in coherence.PRICE_RANGE_BASIS_REFERENCES.items()})

    def test_basis_ladder_is_the_ladder_that_was_hard_coded(self):
        self.assertEqual(coherence.PRICE_RANGES, LEGACY_PRICE_RANGES)

    def test_consumer_electronics_ranges_are_the_old_constants_exactly(self):
        scenario = self._load(CONSUMER_ELECTRONICS)
        ranges = coherence.scenario_price_ranges(scenario)
        self.assertEqual(ranges, LEGACY_PRICE_RANGES)
        # `==` would accept 100.0 for 100; the stored string would not.
        self.assertEqual(repr(ranges), repr(LEGACY_PRICE_RANGES))
        for low, high in ranges.values():
            self.assertIs(type(low), int)
            self.assertIs(type(high), int)

    def test_other_scenarios_take_the_same_ratios_of_their_own_references(self):
        for filename in (CLEAN_ENERGY, MEDIA):
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                references = scenario_reference_prices(scenario)
                ranges = coherence.scenario_price_ranges(scenario)
                self.assertEqual(set(ranges), set(LEGACY_PRICE_RANGES))
                for tier, (old_low, old_high) in LEGACY_PRICE_RANGES.items():
                    basis = coherence.PRICE_RANGE_BASIS_REFERENCES[tier]
                    low, high = ranges[tier]
                    self.assertAlmostEqual(
                        low / references[tier], old_low / basis, places=12)
                    self.assertAlmostEqual(
                        high / references[tier], old_high / basis, places=12)
                    # Every tier's own reference price is inside its range.
                    self.assertTrue(low <= references[tier] <= high)
                self.assertNotEqual(ranges, LEGACY_PRICE_RANGES)

    def _set(self, scenario, key, value):
        """Set (or, with None, remove) one config value; restore on cleanup."""
        row = ScenarioConfig.objects.get(scenario=scenario, config_key=key)
        original = row.config_value

        def restore():
            ScenarioConfig.objects.update_or_create(
                scenario=scenario, config_key=key,
                defaults={'config_value': original,
                          'description': row.description})
            _config_cache.clear()
        if value is None:
            ScenarioConfig.objects.filter(pk=row.pk).delete()
        else:
            ScenarioConfig.objects.filter(pk=row.pk).update(config_value=value)
        _config_cache.clear()
        return restore

    def test_a_missing_reference_price_refuses(self):
        for filename in (CONSUMER_ELECTRONICS, CLEAN_ENERGY):
            scenario = self._load(filename)
            for key in ('reference_price_budget', 'reference_price_premium'):
                with self.subTest(scenario=filename, key=key):
                    restore = self._set(scenario, key, None)
                    with self.assertRaises(InvalidScenarioConfiguration) as ctx:
                        coherence.scenario_price_ranges(scenario)
                    self.assertIn(key, str(ctx.exception))
                    restore()
            # Restored, it derives again: the refusal was the missing key.
            coherence.scenario_price_ranges(scenario)

    def test_an_unusable_reference_price_refuses(self):
        scenario = self._load(CONSUMER_ELECTRONICS)
        for bad in ('0', '-420', 'nan', 'inf'):
            with self.subTest(value=bad):
                restore = self._set(scenario, 'reference_price_mainstream', bad)
                with self.assertRaises(InvalidScenarioConfiguration):
                    coherence.scenario_price_ranges(scenario)
                restore()

    def test_scoring_refuses_rather_than_scoring_against_the_old_dollars(self):
        """The refusal reaches the scorer: no score comes back at all."""
        scenario = self._load(CLEAN_ENERGY)
        game, round_one = self._game(scenario)
        team = Team.objects.filter(game=game).order_by('id').first()
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_one, defaults={'status': 'draft'})
        product = TeamProduct.objects.filter(team=team).order_by('id').first()
        self._price(submission, product, Decimal('400'))
        ScenarioConfig.objects.filter(
            scenario=scenario,
            config_key='reference_price_ultra_premium').delete()
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfiguration):
            coherence._score_positioning_price(team, submission, scenario)


class ConsumerElectronicsUnchangedTests(_ScenarioFixture):

    # Inside, both edges, the 20% shoulder on each side and its edges, beyond,
    # and a cent either side of every boundary that is not a whole number.
    PRICES = ['1', '79.99', '80', '99.99', '100', '199.99', '200', '250',
              '300', '300.01', '360', '360.01', '399.99', '400', '420',
              '499.99', '500', '550', '550.01', '639.99', '640', '660',
              '660.01', '700', '800', '900', '900.01', '1000', '1080',
              '1080.01', '1500', '1500.01', '1800', '1800.01', '9999', '12000']

    def test_component_is_identical_to_the_function_it_replaced(self):
        scenario = self._load(CONSUMER_ELECTRONICS)
        game, round_one = self._game(scenario)
        positionings = set()
        compared = 0
        for team in Team.objects.filter(game=game).order_by('id'):
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=round_one, defaults={'status': 'draft'})
            products = list(TeamProduct.objects.filter(team=team).order_by('id'))
            for price in self.PRICES + [None]:
                for product in products:
                    positionings.add(product.positioning)
                    self._price(submission, product,
                                None if price is None else Decimal(price))
                new = coherence._score_positioning_price(
                    team, submission, scenario)
                old = _legacy_score_positioning_price(team, submission)
                self.assertEqual(new, old, f'{team.name} at {price}')
                # What is stored and hashed is the serialisation.
                self.assertEqual(json.dumps(new, sort_keys=True),
                                 json.dumps(old, sort_keys=True))
                compared += 1
        self.assertGreater(len(positionings), 1)
        self.assertEqual(compared, 3 * (len(self.PRICES) + 1))

    def test_every_tier_is_identical_not_only_the_tiers_starters_use(self):
        scenario = self._load(CONSUMER_ELECTRONICS)
        game, round_one = self._game(scenario)
        team = Team.objects.filter(game=game).order_by('id').first()
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_one, defaults={'status': 'draft'})
        product = TeamProduct.objects.filter(team=team).order_by('id').first()
        for tier in LEGACY_PRICE_RANGES:
            TeamProduct.objects.filter(pk=product.pk).update(positioning=tier)
            for price in self.PRICES:
                self._price(submission, product, Decimal(price))
                new = coherence._score_positioning_price(
                    team, submission, scenario)
                old = _legacy_score_positioning_price(team, submission)
                self.assertEqual(json.dumps(new, sort_keys=True),
                                 json.dumps(old, sort_keys=True),
                                 f'{tier} at {price}')


class OtherScenariosAreScorableTests(_ScenarioFixture):

    def _scores_at_authored_prices(self, filename):
        """(old, new) component for every team priced at its authored prices."""
        scenario = self._load(filename)
        game, round_one = self._game(scenario)
        authored = {
            sp.product_name: sp.base_price
            for sp in FirmStarterProduct.objects.filter(
                firm_starter_profile__scenario=scenario)}
        old_total = new_total = possible = 0.0
        for team in Team.objects.filter(game=game).order_by('id'):
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=round_one, defaults={'status': 'draft'})
            for product in TeamProduct.objects.filter(team=team).order_by('id'):
                self._price(submission, product, authored[product.name])
            old = _legacy_score_positioning_price(team, submission)
            new = coherence._score_positioning_price(team, submission, scenario)
            self.assertEqual(old[1], new[1])
            old_total += old[0]
            new_total += new[0]
            possible += new[1]
        return old_total, new_total, possible

    def test_clean_energy_at_its_authored_prices_scored_nothing_and_now_scores(self):
        old, new, possible = self._scores_at_authored_prices(CLEAN_ENERGY)
        self.assertGreater(possible, 0)
        self.assertEqual(old, 0.0)
        self.assertGreater(new, 0.0)

    def test_media_at_its_authored_prices_scores_more_than_it_did(self):
        old, new, possible = self._scores_at_authored_prices(MEDIA)
        self.assertGreater(possible, 0)
        self.assertGreater(new, old)

    def test_the_products_still_scoring_nothing_are_the_known_v2_114_residual(self):
        """Named, so the set cannot grow silently.

        One range per tier cannot hold a tier whose authored prices span more
        than the range does. Clean Energy's mainstream tier spans 9.4x ($850
        home packs to $8,000 grid modules) and Media's one outlier is $55
        against a $120 reference. They are the same products V2-114 already
        lists as on a price-competitiveness clamp under any single reference,
        and the same open question for the owner -- not a new one.
        """
        from core.tests.test_scenario_reference_prices import (
            KNOWN_RESIDUAL_CLAMPS)
        for filename in (CONSUMER_ELECTRONICS, CLEAN_ENERGY, MEDIA):
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                ranges = coherence.scenario_price_ranges(scenario)
                products = list(FirmStarterProduct.objects.filter(
                    firm_starter_profile__scenario=scenario))
                self.assertEqual(len(products), 16)
                zero = set()
                for sp in products:
                    tier = (sp.positioning_label.lower()
                            .replace('-', '_').replace(' ', '_'))
                    low, high = ranges[tier]
                    price = float(sp.base_price)
                    if price < low * 0.8 or price > high * 1.2:
                        zero.add(sp.product_name)
                self.assertEqual(zero, KNOWN_RESIDUAL_CLAMPS[filename])

    def test_a_product_priced_at_its_tier_reference_scores_full_marks(self):
        """The plainest sensible price there is, in either scenario."""
        for filename in (CLEAN_ENERGY, MEDIA):
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                references = scenario_reference_prices(scenario)
                game, round_one = self._game(scenario)
                team = Team.objects.filter(game=game).order_by('id').first()
                submission, _ = DecisionSubmission.objects.get_or_create(
                    team=team, round=round_one, defaults={'status': 'draft'})
                products = list(
                    TeamProduct.objects.filter(team=team).order_by('id'))
                for product in products:
                    self._price(
                        submission, product,
                        Decimal(str(references[product.positioning])))
                old = _legacy_score_positioning_price(team, submission)
                new = coherence._score_positioning_price(
                    team, submission, scenario)
                self.assertEqual(old[0], 0.0, 'scored 0.0 before N3')
                self.assertEqual(new[0], float(len(products)))
                self.assertTrue(all(row['aligned'] for row in new[2]))


class ResolvedRoundTests(_ScenarioFixture):
    """Through `_run_phase_1`, so the wiring is proved and not only the helper.

    Signature-independent on purpose: this is the test that is red against the
    engine as it stood, by value (0.0) rather than by a missing name.
    """

    def test_consumer_electronics_round_publishes_what_it_always_did(self):
        from core.models.results_financials import RoundResultCoherence
        self._resolved_component(CONSUMER_ELECTRONICS)
        rows = list(RoundResultCoherence.objects.filter(round_number=1)
                    .order_by('team_id')
                    .select_related('team'))
        self.assertEqual(len(rows), 3)
        for row in rows:
            submission = DecisionSubmission.objects.get(
                team=row.team, round__round_number=1)
            score, possible, details = _legacy_score_positioning_price(
                row.team, submission)
            self.assertGreater(possible, 0)
            self.assertEqual(
                json.dumps(row.breakdown['positioning_price'], sort_keys=True),
                json.dumps({'score': score / max(possible, 1),
                            'details': details}, sort_keys=True))

    def _resolved_component(self, filename):
        from django.utils import timezone
        from core.engine.advance_round import _run_phase_1
        from core.models.results_financials import RoundResultCoherence

        scenario = self._load(filename)
        game, round_one = self._game(scenario)
        authored = {
            sp.product_name: sp.base_price
            for sp in FirmStarterProduct.objects.filter(
                firm_starter_profile__scenario=scenario)}
        for team in Team.objects.filter(game=game).order_by('id'):
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=round_one, defaults={'status': 'draft'})
            for product in TeamProduct.objects.filter(team=team).order_by('id'):
                self._price(submission, product, authored[product.name])
        DecisionSubmission.objects.filter(round=round_one).update(
            status='locked', locked_at=timezone.now())
        _run_phase_1(game.id)
        rows = list(RoundResultCoherence.objects.filter(
            game=game, round_number=1).order_by('team_id'))
        self.assertEqual(len(rows), 3)
        return [row.breakdown['positioning_price'] for row in rows]

    def test_clean_energy_round_publishes_a_positioning_price_score(self):
        components = self._resolved_component(CLEAN_ENERGY)
        self.assertTrue(all(c['details'] for c in components))
        self.assertGreater(sum(c['score'] for c in components), 0.0)

    def test_media_round_publishes_a_positioning_price_score(self):
        components = self._resolved_component(MEDIA)
        self.assertTrue(all(c['details'] for c in components))
        self.assertTrue(all(c['score'] > 0.0 for c in components))
