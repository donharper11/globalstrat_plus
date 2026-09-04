"""GSP-CRV2-11 calibration contracts.

These checks keep the measurement conclusions from becoming regressions: market
growth compounds, invisible AI share is published but does not alter Fix A's
diffusion rule, and malformed stakeholder preferences cannot be loaded.
"""
import copy
from decimal import Decimal as D
from pathlib import Path

import yaml
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.engine.bass_engine import _get_total_cumulative, run_bass_adoption
from core.engine.events import update_market_conditions
from core.engine.utils import RoundContext, SegmentEffectiveState
from core.management.commands.load_scenario import (
    scenario_validation_warnings, validate_scenario_yaml,
)
from core.models.core import Game, Round, Team
from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.results import (
    RoundResultAdoption, RoundResultAIAdoption,
    RoundResultDemandReconciliation,
)
from core.models.scenario import (
    AICompetitorDefinition, AICompetitorFitByRound, FirmStarterProfile,
    MarketDefinition, PlatformGenerationDefinition, Scenario, ScenarioConfig,
    SegmentDefinition,
)
from core.models.team_state import TeamPlatform, TeamProduct


SCENARIO_DIR = Path(__file__).resolve().parents[2] / 'scenarios'


class ScenarioPreferenceValidationTests(TestCase):
    def _scenario(self, name):
        return yaml.safe_load((SCENARIO_DIR / name).read_text())

    def test_all_shipped_scenarios_pass_the_preference_contract(self):
        for name in (
            'consumer_electronics_2026.yaml',
            'clean_energy_tech_2026.yaml',
            'media_entertainment_2026.yaml',
        ):
            with self.subTest(name=name):
                self.assertEqual(validate_scenario_yaml(self._scenario(name)), [])

    def test_out_of_range_ideal_refuses_load(self):
        data = copy.deepcopy(self._scenario('consumer_electronics_2026.yaml'))
        data['segment_preferences']['Value Seekers']['NA'][0][1] = 999
        errors = validate_scenario_yaml(data)
        self.assertTrue(any('outside feature range' in error for error in errors))

    def test_negative_preference_weight_refuses_load(self):
        data = copy.deepcopy(self._scenario('consumer_electronics_2026.yaml'))
        data['segment_preferences']['Value Seekers']['NA'][0][2] = -0.01
        errors = validate_scenario_yaml(data)
        self.assertTrue(any('weight must not be negative' in error for error in errors))

    def test_non_numeric_preference_values_refuse_load(self):
        data = copy.deepcopy(self._scenario('consumer_electronics_2026.yaml'))
        data['segment_preferences']['Value Seekers']['NA'][0][3] = 'not-a-number'
        errors = validate_scenario_yaml(data)
        self.assertTrue(any('must be numeric' in error for error in errors))

    def test_globally_unreachable_platform_feature_refuses_load(self):
        data = copy.deepcopy(self._scenario('consumer_electronics_2026.yaml'))
        for generation in data['platform_generations']:
            generation['ceilings']['processing_power'] = 0
        errors = validate_scenario_yaml(data)
        self.assertTrue(any('unreachable in every generation' in error for error in errors))

    def test_gen_one_upgrade_pressure_is_loudly_reported_not_silently_accepted(self):
        warnings = scenario_validation_warnings(
            self._scenario('consumer_electronics_2026.yaml'))
        self.assertTrue(any('ai_features' in warning and 'unreachable on Gen 1' in warning
                            for warning in warnings))


class CalibrationDemandAccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('calibration', password='x')
        cls.scenario = Scenario.objects.create(
            name='Calibration Test', industry_label='Test', description='Test',
            starting_cash=D('1000000'),
        )
        ScenarioConfig.objects.bulk_create([
            ScenarioConfig(scenario=cls.scenario, config_key='competition_sharpness', config_value='1.5'),
            ScenarioConfig(scenario=cls.scenario, config_key='high_price_elasticity', config_value='1.5'),
            ScenarioConfig(scenario=cls.scenario, config_key='reference_price_budget', config_value='250'),
            ScenarioConfig(scenario=cls.scenario, config_key='reference_price_mainstream', config_value='420'),
            ScenarioConfig(scenario=cls.scenario, config_key='reference_price_premium', config_value='500'),
            ScenarioConfig(scenario=cls.scenario, config_key='reference_price_ultra_premium', config_value='1000'),
        ])
        cls.market = MarketDefinition.objects.create(
            scenario=cls.scenario, name='Home', code='HM', description='Test',
            currency_code='USD', exchange_rate_base=D('1'), base_growth_rate=D('0.10'),
            entry_cost_base=D('0'), tax_rate=D('0.2'), regulatory_difficulty=D('1'),
            infrastructure_quality=D('1'),
        )
        cls.segment = SegmentDefinition.objects.create(
            scenario=cls.scenario, market=cls.market, name='Customers',
            segment_type='customer', description='Test', population_size=1000,
            bass_p=D('0.1'), bass_q=D('0'), performance_index_weight=D('1'),
            revenue_per_unit=D('500'),
        )
        cls.profile = FirmStarterProfile.objects.create(
            scenario=cls.scenario, profile_name='Starter', description='Test',
            home_market=cls.market, starting_cash=D('1000000'),
        )
        cls.generation = PlatformGenerationDefinition.objects.create(
            scenario=cls.scenario, name='Gen 1', description='Test',
            generation_order=1, unlock_round=0, development_cost=D('0'),
            license_cost=D('0'), is_starting_platform=True,
        )

    def _game_with_team(self, round_number=1):
        game = Game.objects.create(
            name=f'Calibration game {round_number}', scenario=self.scenario,
            created_by=self.user, status='active', current_round=round_number,
        )
        team = Team.objects.create(
            game=game, name='Human', firm_starter_profile=self.profile,
            performance_index=D('55'), cash_on_hand=D('1000000'), total_equity=D('1000000'),
        )
        platform = TeamPlatform.objects.create(team=team, platform_generation=self.generation,
                                               name='Platform', status='active')
        product = TeamProduct.objects.create(team=team, team_platform=platform,
                                             name='Product', positioning='premium', created_round=1)
        round_obj = Round.objects.create(game=game, round_number=round_number, status='open')
        submission = DecisionSubmission.objects.create(team=team, round=round_obj, status='locked')
        DecisionMarketing.objects.create(
            submission=submission, team_product=product, market=self.market,
            retail_price=D('500'), promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('1'), channel_traditional_pct=D('0'), channel_trade_pct=D('0'),
            distribution_strategy='hybrid', distribution_investment=D('0'),
            demand_estimate=1000, production_volume=1000, production_source_market=self.market,
        )
        return game, team, product

    def test_population_growth_compounds_through_the_current_round(self):
        game, _team, _product = self._game_with_team(round_number=3)
        context = RoundContext(game, 3)
        update_market_conditions(context)
        self.assertAlmostEqual(
            context.segments[self.segment.id].effective_population, 1331.0,
        )

    def test_ai_take_is_recorded_and_the_pool_reconciles_without_entering_n(self):
        game, team, product = self._game_with_team()
        ai = AICompetitorDefinition.objects.create(scenario=self.scenario, name='Benchmark')
        AICompetitorFitByRound.objects.create(
            ai_competitor=ai, segment=self.segment, market=self.market,
            round_number=1, fit_score=D('0.6'),
        )
        context = RoundContext(game, 1)
        context.teams = [team]
        context.segments = {self.segment.id: SegmentEffectiveState(self.segment)}
        context.segments[self.segment.id].effective_population = 1000
        key = (team.id, self.segment.id, self.market.id)
        context.fit_scores[key] = 0.8
        context.adjusted_fit_scores[key] = 0.8
        context.best_products[key] = product
        context.readiness[(team.id, product.id, self.market.id)] = 1.0
        context.compliance_freezes = set()

        run_bass_adoption(context)

        human = RoundResultAdoption.objects.get(game=game, round_number=1, team=team)
        ai_take = RoundResultAIAdoption.objects.get(game=game, round_number=1, ai_competitor=ai)
        reconciliation = RoundResultDemandReconciliation.objects.get(
            game=game, round_number=1, segment=self.segment, market=self.market,
        )
        self.assertGreater(ai_take.new_adopters, D('0'))
        self.assertEqual(reconciliation.adoption_pool,
                         reconciliation.human_adopters + reconciliation.ai_adopters
                         + reconciliation.unserved_adopters)
        self.assertEqual(reconciliation.human_adopters, human.new_adopters)
        # Fix A is observational: only human result rows enter Bass N.
        self.assertEqual(_get_total_cumulative(game, self.segment, self.market, 2),
                         float(human.cumulative_adopters))
