"""R11 — round-0 adopters are derived from the authored starter sales.

The rule under test (competition owner, 2026-09-11): the round-zero segment
adoption table is an apportionment of each team's **authored** starting unit
sales across its home market's customer segments, so that the two round-0
numbers a student can see side by side — segment adopters and product unit
sales — reconcile to the cent.  No unauthored scale constant participates.

These tests pin the *authored source*, which is the standing requirement D6
carried: they assert against figures computed from the scenario rows
(``FirmStarterProduct.unit_volume``, ``SegmentDefinition.bass_p`` and
``population_size``), never against a number embedded in the test.
"""
from decimal import Decimal as D
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase

from core.engine.bootstrap import bootstrap_round_zero
from core.models.core import Game, Team
from core.models.results import RoundResultAdoption
from core.models.results_financials import RoundResultProductMarket
from core.models.scenario import (
    EntryModeDefinition, FeatureDefinition, FirmStarterProduct,
    FirmStarterProfile, MarketDefinition, PlatformGenerationDefinition,
    Scenario, SegmentDefinition, SegmentPreference,
)
from core.models.team_state import (
    TeamMarketPresence, TeamPlatform, TeamPlatformFeatureLevel, TeamProduct,
    TeamProductMarket,
)


SCENARIO_DIR = Path(__file__).resolve().parents[2] / 'scenarios'


class RoundZeroFixture:
    """Builds a scenario small enough that the arithmetic is checkable by hand."""

    @classmethod
    def build_scenario(cls, name):
        scenario = Scenario.objects.create(
            name=name, industry_label='R11', description='R11',
            starting_cash=D('1000000'), performance_index_base=D('50.00'))
        home = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HOME', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=0, entry_cost_base=0,
            tax_rate=D('0.20'), regulatory_difficulty=1, infrastructure_quality=1,
            base_manufacturing_cost=D('1.00'))
        away = MarketDefinition.objects.create(
            scenario=scenario, name='Away', code='AWAY', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=0, entry_cost_base=0,
            tax_rate=D('0.20'), regulatory_difficulty=1, infrastructure_quality=1,
            base_manufacturing_cost=D('1.00'))
        gen1 = PlatformGenerationDefinition.objects.create(
            scenario=scenario, name='Gen 1', description='Gen 1',
            generation_order=1, unlock_round=0, development_cost=0,
            license_cost=0, is_starting_platform=True)
        PlatformGenerationDefinition.objects.create(
            scenario=scenario, name='Gen 2', description='Gen 2',
            generation_order=2, unlock_round=2, development_cost=0,
            license_cost=0)
        entry_mode = EntryModeDefinition.objects.create(
            scenario=scenario, name='Direct', code='direct', description='d',
            capital_requirement=0, control_level=1, risk_level=1,
            local_presence_score=1)
        feature = FeatureDefinition.objects.create(
            scenario=scenario, layer='platform', category='Core', name='Speed',
            description='Speed', code='speed', min_value=0, max_value=20,
            default_value=1, cost_curve_type='linear', cost_base=1000)
        return scenario, home, away, gen1, entry_mode, feature

    @classmethod
    def add_segment(cls, scenario, market, name, population, bass_p, feature,
                    ideal, tolerance=D('5.00'), min_generation=None):
        segment = SegmentDefinition.objects.create(
            scenario=scenario, market=market, name=name,
            segment_type='customer', description=name,
            population_size=population, bass_p=bass_p, bass_q=D('0.300000'),
            performance_index_weight=D('0.1000'),
            min_generation_required=min_generation)
        SegmentPreference.objects.create(
            segment=segment, feature=feature, ideal_value=ideal,
            weight=D('1.0000'), tolerance=tolerance)
        return segment

    @classmethod
    def add_team(cls, scenario, game, home, gen1, entry_mode, feature,
                 profile_name, volumes, level=D('10.00')):
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name=profile_name, description='p',
            home_market=home, starting_cash=D('1000000'), starting_debt=0,
            starting_revenue=D('100000'))
        for index, volume in enumerate(volumes):
            FirmStarterProduct.objects.create(
                firm_starter_profile=profile, product_name=f'{profile_name} P{index}',
                positioning_label='mainstream', base_price=D('100.00'),
                market=home, unit_volume=volume, market_share_pct=D('0.0500'))
        team = Team.objects.create(
            game=game, name=f'{profile_name} team', firm_starter_profile=profile,
            home_market=home, performance_index=D('50.00'),
            cash_on_hand=D('1000000.00'), total_debt=D('0.00'),
            total_equity=D('1000000.00'))
        platform = TeamPlatform.objects.create(
            team=team, platform_generation=gen1, name=f'{profile_name} base',
            status='active', activated_round=0)
        TeamPlatformFeatureLevel.objects.create(
            team_platform=platform, feature=feature, current_level=level)
        for index, _volume in enumerate(volumes):
            product = TeamProduct.objects.create(
                team=team, team_platform=platform,
                name=f'{profile_name} P{index}', positioning='mainstream',
                created_round=0)
            TeamProductMarket.objects.create(
                team_product=product, market=home, first_offered_round=0)
        TeamMarketPresence.objects.create(
            team=team, market=home, entry_mode=entry_mode, established_round=0,
            initial_investment=0, status='active')
        return team

    @staticmethod
    def adopters(game, team, segment):
        return RoundResultAdoption.objects.get(
            game=game, round_number=0, team=team, segment=segment).new_adopters

    @staticmethod
    def units_sold(game, team, market):
        return RoundResultProductMarket.objects.filter(
            game=game, round_number=0, team=team, market=market,
        ).aggregate(total=Sum('units_sold'))['total']


class RoundZeroReconciliationTests(TestCase, RoundZeroFixture):
    """The reconciliation R11 exists to produce."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user('r11-reconcile')
        (cls.scenario, cls.home, cls.away, gen1, entry_mode,
         cls.feature) = cls.build_scenario('R11 reconciliation')
        # Two segments with identical preferences and pools in a 1:2 ratio, so
        # the apportionment is exact arithmetic rather than a rounded figure.
        cls.small = cls.add_segment(cls.scenario, cls.home, 'Twin Small',
                                    1000000, D('0.020000'), cls.feature, D('10.00'))
        cls.large = cls.add_segment(cls.scenario, cls.home, 'Twin Large',
                                    2000000, D('0.020000'), cls.feature, D('10.00'))
        # Authored but unreachable at round 0: needs a generation the team has
        # not got.  It must take no adopters at all.
        cls.gen_two_only = cls.add_segment(
            cls.scenario, cls.home, 'Gen Two Only', 1000000, D('0.020000'),
            cls.feature, D('10.00'), min_generation=2)
        # Authored in another market: not the team's home market.
        cls.elsewhere = cls.add_segment(cls.scenario, cls.away, 'Away Buyers',
                                        1000000, D('0.020000'), cls.feature, D('10.00'))
        cls.game = Game.objects.create(
            scenario=cls.scenario, name='R11 game', created_by=user,
            status='active', current_round=0)
        # 25,000 + 35,000 = 60,000 authored units; pools are 20,000 and 40,000.
        cls.team = cls.add_team(cls.scenario, cls.game, cls.home, gen1,
                                entry_mode, cls.feature, 'Even', [25000, 35000])
        # A volume that does not divide evenly by the pool ratio, to prove the
        # cent settlement rather than a lucky round number.
        cls.awkward = cls.add_team(cls.scenario, cls.game, cls.home, gen1,
                                   entry_mode, cls.feature, 'Awkward', [25000])
        bootstrap_round_zero(cls.game)

    def test_segment_adopters_sum_to_the_authored_units_sold_to_the_cent(self):
        """The reconciliation is the point of the ruling."""
        for team in (self.team, self.awkward):
            with self.subTest(team=team.name):
                adopted = RoundResultAdoption.objects.filter(
                    game=self.game, round_number=0, team=team,
                    market=self.home,
                ).aggregate(total=Sum('new_adopters'))['total']
                sold = self.units_sold(self.game, team, self.home)
                authored = FirmStarterProduct.objects.filter(
                    firm_starter_profile=team.firm_starter_profile,
                ).aggregate(total=Sum('unit_volume'))['total']
                self.assertEqual(sold, D(str(authored)))
                self.assertEqual(adopted, sold)

    def test_apportionment_follows_the_authored_bass_pool(self):
        """Identical preferences, pools 1:2 — so adopters are 1:2."""
        small_pool = D(str(self.small.bass_p)) * D(str(self.small.population_size))
        large_pool = D(str(self.large.bass_p)) * D(str(self.large.population_size))
        authored_units = D('60000')
        self.assertEqual(
            self.adopters(self.game, self.team, self.small),
            (authored_units * small_pool / (small_pool + large_pool)).quantize(D('0.01')))
        self.assertEqual(
            self.adopters(self.game, self.team, self.large),
            (authored_units * large_pool / (small_pool + large_pool)).quantize(D('0.01')))

    def test_a_segment_the_team_cannot_serve_takes_no_adopters(self):
        self.assertEqual(
            self.adopters(self.game, self.team, self.gen_two_only), D('0.00'))
        self.assertEqual(
            self.adopters(self.game, self.team, self.elsewhere), D('0.00'))

    def test_no_unauthored_scale_factor_survives(self):
        """The retired rule was bass_p x population x avg_starter_share x 10."""
        retired = (float(self.small.bass_p) * float(self.small.population_size)
                   * 0.05 * 10)
        self.assertNotEqual(
            float(self.adopters(self.game, self.team, self.small)), retired)

    def test_round_zero_cumulative_equals_new_adopters(self):
        """Pinned, not endorsed — see the CRV2-12 note in the completion report.

        Round-0 `cumulative_adopters` does not carry into round 1 (bass_engine
        returns 0.0 for `prev_round < 1`), so a student sees Cumulative *fall*
        between round 0 and round 1.  That is a presentation matter and is
        reported rather than repaired here; this assertion makes the current
        behaviour explicit so a later change to it is deliberate.
        """
        row = RoundResultAdoption.objects.get(
            game=self.game, round_number=0, team=self.team, segment=self.small)
        self.assertEqual(row.cumulative_adopters, row.new_adopters)


class RoundZeroFitWeightingTests(TestCase, RoundZeroFixture):
    """Equal pools, different authored preference match — different adopters."""

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user('r11-fit')
        (cls.scenario, cls.home, _away, gen1, entry_mode,
         cls.feature) = cls.build_scenario('R11 fit weighting')
        # Same population and bass_p, so the only thing separating them is how
        # well the team's authored starting feature level matches their ideal.
        cls.matched = cls.add_segment(cls.scenario, cls.home, 'Matched',
                                      1000000, D('0.020000'), cls.feature, D('10.00'))
        cls.mismatched = cls.add_segment(cls.scenario, cls.home, 'Mismatched',
                                         1000000, D('0.020000'), cls.feature, D('1.00'))
        cls.game = Game.objects.create(
            scenario=cls.scenario, name='R11 fit game', created_by=user,
            status='active', current_round=0)
        cls.team = cls.add_team(cls.scenario, cls.game, cls.home, gen1,
                                entry_mode, cls.feature, 'Specialist', [40000],
                                level=D('10.00'))
        bootstrap_round_zero(cls.game)

    def test_the_better_matched_segment_takes_more_of_the_authored_units(self):
        self.assertGreater(
            self.adopters(self.game, self.team, self.matched),
            self.adopters(self.game, self.team, self.mismatched))

    def test_the_split_still_reconciles(self):
        self.assertEqual(
            self.adopters(self.game, self.team, self.matched)
            + self.adopters(self.game, self.team, self.mismatched),
            self.units_sold(self.game, self.team, self.home))


class RoundZeroAuthoringErrorTests(TestCase, RoundZeroFixture):
    """Unsupported authored data fails loudly rather than defaulting."""

    def test_starter_units_with_no_reachable_customer_segment_raises(self):
        user = get_user_model().objects.create_user('r11-loud')
        (scenario, home, _away, gen1, entry_mode,
         feature) = self.build_scenario('R11 unsupported')
        # The only customer segment in the home market needs Gen 2, which no
        # team starts on — so there is no authored basis for the apportionment.
        self.add_segment(scenario, home, 'Gen Two Only', 1000000,
                         D('0.020000'), feature, D('10.00'), min_generation=2)
        game = Game.objects.create(
            scenario=scenario, name='R11 unsupported game', created_by=user,
            status='active', current_round=0)
        self.add_team(scenario, game, home, gen1, entry_mode, feature,
                      'Stranded', [25000])

        with self.assertRaises(ValueError) as caught:
            bootstrap_round_zero(game)
        message = str(caught.exception)
        self.assertIn('Stranded', message)
        self.assertIn('HOME', message)
        self.assertIn('no authored basis', message)


class ShippedScenarioRoundZeroTests(TestCase):
    """Acceptance: all three shipped scenarios, not only consumer electronics."""

    SCENARIOS = (
        ('consumer_electronics_2026.yaml', 'Consumer Electronics 2026'),
        ('clean_energy_tech_2026.yaml', 'Clean Energy Technology 2026'),
        ('media_entertainment_2026.yaml', 'Media & Entertainment 2026'),
    )

    def test_every_shipped_scenario_reconciles_round_zero_adoption(self):
        get_user_model().objects.create_superuser(
            'r11-shipped', 'r11@example.com', 'x')
        for filename, _name in self.SCENARIOS:
            with self.subTest(scenario=filename):
                call_command('load_scenario', file=str(SCENARIO_DIR / filename),
                             verbosity=0)
                scenario = Scenario.objects.order_by('-id').first()
                call_command('initialize_game', scenario=scenario.id, teams=4,
                             name=f'R11 {filename}', verbosity=0)
                game = Game.objects.order_by('-id').first()

                teams = list(Team.objects.filter(game=game).order_by('id'))
                self.assertEqual(len(teams), 4)
                for team in teams:
                    market = team.home_market
                    adopted = RoundResultAdoption.objects.filter(
                        game=game, round_number=0, team=team, market=market,
                    ).aggregate(total=Sum('new_adopters'))['total']
                    sold = RoundResultProductMarket.objects.filter(
                        game=game, round_number=0, team=team, market=market,
                    ).aggregate(total=Sum('units_sold'))['total']
                    authored = FirmStarterProduct.objects.filter(
                        firm_starter_profile=team.firm_starter_profile,
                    ).aggregate(total=Sum('unit_volume'))['total']
                    self.assertEqual(
                        sold, D(str(authored)),
                        f'{filename}: {team.name} round-0 units are not the '
                        f'authored starter volumes')
                    self.assertEqual(
                        adopted, sold,
                        f'{filename}: {team.name} round-0 adopters do not '
                        f'reconcile to round-0 units sold')
                    self.assertGreater(adopted, D('0'))
