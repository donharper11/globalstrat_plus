"""V2-114 — each scenario's reference prices fit that scenario's own prices.

``reference_price_budget/mainstream/premium/ultra_premium`` were authored as
250 / 420 / 700 / 1000 in all three shipped scenarios. Those are the Consumer
Electronics starting prices. Clean Energy's starter products are authored at
$850-$12,000 and Media's at $55-$340, so against that ladder:

* ``price_competitiveness = clamp(f_max * (1.5 - price / reference))`` is only
  *live* for ``0.5 < price / reference < 1.5``. Every Clean Energy starter
  product sat at or beyond 2.0 (clamped to the floor) and every Media starter
  product at or below 0.49 (clamped to the ceiling): 32 of 32 products on a
  clamp, so a price change moved nothing.
* a newly launched product is banded +/-30% around its tier's reference
  (``price_band``), so a new Clean Energy mainstream product was legal only
  between $294 and $546.

THE DERIVATION RULE these tests pin, for Clean Energy and Media (Consumer
Electronics is deliberately left byte-unchanged — its ladder is the V2-023
anchor and fits its own data):

1. A tier with authored starter products takes the **mean of their authored
   starting prices**, to 2 significant figures. The mean, because the score is
   linear in price: at ``reference = mean`` the field's average price
   competitiveness at the authored starting prices is exactly the neutral 0.5.
2. A tier with no authored starter product (budget and ultra-premium, in both
   scenarios) extends the scenario's own ladder by the Consumer Electronics
   step for that tier — budget = mainstream x 250/420, ultra-premium =
   premium x 1000/700 — to 2 significant figures.

Everything is measured through the engine's own functions against scenarios
loaded by the real ``load_scenario``; no price is embedded here except the
Consumer Electronics pin and the named residual below.

THE RESIDUAL, named rather than hidden. One reference per tier can hold a tier
live only if its authored prices span less than 3x (the window is 0.5-1.5).
Clean Energy's *mainstream* tier spans 9.4x ($850 home packs to $8,000 grid
modules), so **no** single reference makes all ten live; the most any
reference reaches is six. Media's mainstream spans 3.09x, so one product
remains on the ceiling under every reference. These are listed in
``KNOWN_RESIDUAL_CLAMPS`` so that they cannot grow silently, and are an open
question for the competition owner — see the completion report.
"""
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase

from core.engine.preference_engine import _derive_price_competitiveness
from core.engine.utils import (_config_cache, high_price_demand_multiplier,
                               scenario_high_price_elasticity,
                               scenario_reference_prices)
from core.models.scenario import FirmStarterProduct, Scenario
from core.services import price_band

SCENARIO_DIR = Path(__file__).resolve().parents[2] / 'scenarios'
F_MIN, F_MAX = 0.0, 1.0

CONSUMER_ELECTRONICS = 'consumer_electronics_2026.yaml'
RE_AUTHORED = ('clean_energy_tech_2026.yaml', 'media_entertainment_2026.yaml')

# The V2-023 anchor. Consumer Electronics is not re-derived by V2-114.
CONSUMER_ELECTRONICS_LADDER = {
    'budget': 250.0, 'mainstream': 420.0, 'premium': 700.0,
    'ultra_premium': 1000.0}

# (from tier, to tier): the Consumer Electronics step used for an empty tier.
LADDER_STEPS = {
    'budget': ('mainstream', 250 / 420),
    'ultra_premium': ('premium', 1000 / 700),
}

# Starter products that stay on a clamp under ANY single per-tier reference.
# Not accepted as correct: bounded, so the set cannot grow unnoticed.
KNOWN_RESIDUAL_CLAMPS = {
    'clean_energy_tech_2026.yaml': {
        # 9.4x spread in one tier: four home products on the ceiling...
        'EcoCell Home', 'BaseCell Lite', 'HomeVolt', 'HomeVolt Compact',
        # ...and two grid modules on the floor.
        'GridCell Standard', 'AxisStore',
    },
    'media_entertainment_2026.yaml': {'OmniPass Lite'},
    CONSUMER_ELECTRONICS: set(),
}


def two_significant_figures(value):
    exponent = math.floor(math.log10(abs(value))) - 1
    return round(value / 10 ** exponent) * 10 ** exponent


def _tier(starter_product):
    return (starter_product.positioning_label.lower()
            .replace('-', '_').replace(' ', '_'))


class ScenarioReferencePriceTests(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)

    def _load(self, filename):
        call_command('load_scenario', file=str(SCENARIO_DIR / filename),
                     verbosity=0)
        _config_cache.clear()
        return Scenario.objects.order_by('-id').first()

    @staticmethod
    def _starter_products(scenario):
        return list(FirmStarterProduct.objects.filter(
            firm_starter_profile__scenario=scenario).order_by('id'))

    def _price_score(self, scenario, tier, price):
        """The engine's own price-competitiveness, on a 0..1 feature range."""
        return _derive_price_competitiveness(
            SimpleNamespace(scenario=scenario), None,
            SimpleNamespace(positioning=tier), None,
            SimpleNamespace(retail_price=price), F_MIN, F_MAX)

    def _clamped(self, scenario):
        """Starter products whose authored price scores on a clamp."""
        return {
            sp.product_name for sp in self._starter_products(scenario)
            if self._price_score(scenario, _tier(sp), sp.base_price)
            in (F_MIN, F_MAX)}

    def test_authored_starting_prices_are_not_on_a_clamp(self):
        """The finding itself: at its authored price, is the lever alive?"""
        for filename, residual in KNOWN_RESIDUAL_CLAMPS.items():
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                products = self._starter_products(scenario)
                clamped = self._clamped(scenario)
                self.assertEqual(
                    clamped - residual, set(),
                    f'{filename}: {len(clamped)} of {len(products)} starter '
                    f'products score price competitiveness on a clamp at their '
                    f'own authored price, so re-pricing them moves nothing')
                # The residual list must not outlive the defect it names.
                self.assertEqual(
                    residual - clamped, set(),
                    f'{filename}: listed as residual but no longer clamped — '
                    f'remove from KNOWN_RESIDUAL_CLAMPS')

    def test_the_premium_tier_is_live_for_every_authored_product(self):
        """The register's own example: "a premium product clamps to zero"."""
        for filename in RE_AUTHORED:
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                elasticity = scenario_high_price_elasticity(scenario)
                reference = scenario_reference_prices(scenario)['premium']
                for sp in self._starter_products(scenario):
                    if _tier(sp) != 'premium':
                        continue
                    score = self._price_score(scenario, 'premium',
                                              sp.base_price)
                    self.assertTrue(
                        F_MIN < score < F_MAX,
                        f'{sp.product_name} at {sp.base_price}: {score}')
                    # ...and the high-price elasticity does not gut it either:
                    # before, the mildest case kept 3.5% of its demand.
                    self.assertGreater(
                        high_price_demand_multiplier(
                            sp.base_price, reference, elasticity), 0.6,
                        sp.product_name)

    def test_references_are_derived_from_the_scenarios_own_starter_prices(self):
        for filename in RE_AUTHORED:
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                references = scenario_reference_prices(scenario)
                by_tier = defaultdict(list)
                for sp in self._starter_products(scenario):
                    by_tier[_tier(sp)].append(float(sp.base_price))

                for tier, prices in sorted(by_tier.items()):
                    self.assertEqual(
                        references[tier], two_significant_figures(mean(prices)),
                        f'{filename} {tier}: reference is not the mean of the '
                        f'{len(prices)} authored starting prices (2 s.f.)')
                for tier, (source, step) in LADDER_STEPS.items():
                    if tier in by_tier:
                        continue
                    self.assertEqual(
                        references[tier],
                        two_significant_figures(references[source] * step),
                        f'{filename} {tier}: an empty tier extends the '
                        f"scenario's own {source} reference")
                ladder = [references[t] for t in (
                    'budget', 'mainstream', 'premium', 'ultra_premium')]
                self.assertEqual(ladder, sorted(set(ladder)),
                                 f'{filename}: tiers are not strictly rising')

    def test_a_new_product_is_banded_around_its_own_scenarios_prices(self):
        """``price_band`` anchors a never-sold product on the tier reference.

        Before, a new Clean Energy mainstream product was legal only between
        $294 and $546 and a new Media premium product only between $490 and
        $910 — bands that exclude every price the scenario authors.
        """
        for filename in RE_AUTHORED:
            with self.subTest(scenario=filename):
                scenario = self._load(filename)
                by_tier = defaultdict(list)
                for sp in self._starter_products(scenario):
                    by_tier[_tier(sp)].append(Decimal(sp.base_price))
                for tier, prices in sorted(by_tier.items()):
                    reference = price_band._positioning_reference_price(
                        scenario, SimpleNamespace(positioning=tier))
                    pct = Decimal(str(price_band.band_pct(scenario)))
                    band = {'min': price_band.money(reference * (1 - pct)),
                            'max': price_band.money(reference * (1 + pct))}
                    typical = sum(prices) / len(prices)
                    self.assertEqual(
                        price_band.evaluate(typical, band), price_band.IN_BAND,
                        f'{filename} {tier}: the tier\'s mean authored price '
                        f'{typical:.2f} is outside the new-product band '
                        f'{band["min"]}-{band["max"]}')

    def test_consumer_electronics_is_unchanged(self):
        scenario = self._load(CONSUMER_ELECTRONICS)
        self.assertEqual(scenario_reference_prices(scenario),
                         CONSUMER_ELECTRONICS_LADDER)
