"""V2-021 and V2-022 — the adopted scoring rules, and the exploits they close.

**V2-021.** `rd_score = clamp01(rd_spend / scenario_rd_spend_target)`. The
denominator is a scenario constant the team cannot choose. Deliberately not the
cohort maximum: that would hand $1 full credit whenever $1 was the largest
spend in the room.

**V2-022.** A team is commercially inactive when its realised revenue is below
`max($1, 0.01 x highest positive team revenue this round)`. One classification,
consumed by both the composite cap and the ranking guard, so the two controls
cannot disagree about who competed.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.engine.performance import (InvalidScenarioConfiguration,
                                     is_commercially_inactive,
                                     material_revenue_floor,
                                     scenario_rd_spend_target)
from core.models import (DecisionSubmission, Game, Round, Scenario, Team)
from core.models.decisions import (DecisionBudgetAllocation,
                                   DecisionRDInvestment)
from core.models.scenario import (FeatureDefinition, FirmStarterProfile,
                                  MarketDefinition, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.team_state import TeamPlatform


class ScoringFixture(TestCase):
    def setUp(self):
        from core.engine.utils import _config_cache
        _config_cache.clear()
        owner = DjangoUser.objects.create(username=f'owner-sc-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Scoring {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='rd_spend_target',
            config_value='2000000', description='target')
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Scoring game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen', description='d',
            generation_order=1, unlock_round=1, development_cost=0,
            development_rounds=1, license_cost=0, annual_maintenance_cost=0,
            is_starting_platform=True)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='P',
            status='active')
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, name='F', code='F1', description='d',
            layer='core', category='performance', min_value=0, max_value=10,
            default_value=0, cost_curve_type='linear', cost_base=1)
        PlatformFeatureCeiling.objects.create(
            platform_generation=generation, feature=self.feature,
            ceiling_value=10, starting_value=0)

    def capability(self, declared_budget, rd_spend):
        from core.engine.performance import _strategic_capability_component
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=self.round, defaults={'status': 'locked'})
        DecisionBudgetAllocation.objects.filter(submission=sub).delete()
        DecisionBudgetAllocation.objects.create(
            submission=sub, rd_budget=D(declared_budget),
            marketing_budget=D('0'), strategy_budget=D('0'),
            research_budget=D('0'))
        DecisionRDInvestment.objects.filter(submission=sub).delete()
        if rd_spend is not None:
            DecisionRDInvestment.objects.create(
                submission=sub, team_platform=self.platform,
                feature=self.feature, method='in_house',
                amount=D(rd_spend), target_level=1)
        target = scenario_rd_spend_target(self.scenario)
        return _strategic_capability_component(self.team, 1, target)


class RdSpendTargetTests(ScoringFixture):

    def test_a_dollar_against_a_dollar_no_longer_earns_full_credit(self):
        """The V2-021 exploit, run against the adopted rule."""
        exploit = self.capability(declared_budget='1', rd_spend='1')
        honest = self.capability(declared_budget='2000000', rd_spend='2000000')
        self.assertLess(exploit, honest)
        # $1 of $2,000,000 is 0.0000005; the R&D term contributes 0.40 of the
        # component, so the exploit must sit near the no-spend floor.
        self.assertLess(exploit, D('0.7'))

    def test_equal_spend_scores_equally_whatever_budget_was_declared(self):
        """The denominator is no longer the team's to choose."""
        modest = self.capability(declared_budget='1', rd_spend='500000')
        grand = self.capability(declared_budget='99000000', rd_spend='500000')
        self.assertEqual(modest, grand)

    def test_zero_spend_earns_zero_for_the_rd_term(self):
        none_spent = self.capability(declared_budget='2000000', rd_spend='0')
        at_target = self.capability(declared_budget='2000000', rd_spend='2000000')
        self.assertLess(none_spent, at_target)
        self.assertEqual(none_spent, self.capability('2000000', None))

    def test_spend_at_or_above_the_target_caps_at_one(self):
        at_target = self.capability(declared_budget='2000000', rd_spend='2000000')
        far_above = self.capability(declared_budget='2000000', rd_spend='50000000')
        self.assertEqual(at_target, far_above)

    def test_a_missing_or_unusable_target_fails_closed(self):
        from core.engine.utils import _config_cache
        for value in (None, '0', '-1'):
            with self.subTest(value=value):
                _config_cache.clear()
                ScenarioConfig.objects.filter(
                    scenario=self.scenario, config_key='rd_spend_target').delete()
                if value is not None:
                    ScenarioConfig.objects.create(
                        scenario=self.scenario, config_key='rd_spend_target',
                        config_value=value, description='invalid')
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_rd_spend_target(self.scenario)

    def test_the_target_is_in_the_manifest(self):
        """A scoring input outside the envelope is not replayable."""
        from core.services.resolution_manifest import build_input_manifest
        body, _snapshot = build_input_manifest(self.game, self.round)
        rendered = str(body['sections'].get('scenario_config'))
        self.assertIn('rd_spend_target', rendered)
        self.assertIn('2000000', rendered)


class MaterialRevenueFloorTests(TestCase):
    """V2-022. Pure classification: no engine run needed."""

    def test_the_floor_is_one_percent_of_the_largest_positive_revenue(self):
        self.assertEqual(
            material_revenue_floor([D('1000000'), D('500000'), D('0')]),
            D('10000.00'))

    def test_the_floor_never_falls_below_a_dollar(self):
        self.assertEqual(material_revenue_floor([D('0'), D('0')]), D('1'))
        self.assertEqual(material_revenue_floor([]), D('1'))
        self.assertEqual(material_revenue_floor([D('50')]), D('1'))

    def test_no_revenue_and_token_revenue_are_both_inactive(self):
        floor = material_revenue_floor([D('1000000')])  # floor 10,000
        self.assertTrue(is_commercially_inactive(D('0'), floor))
        self.assertTrue(is_commercially_inactive(D('420'), floor),
                        'a token sale must not buy an exemption')

    def test_the_boundary_is_inclusive_at_the_floor(self):
        floor = material_revenue_floor([D('1000000')])  # 10,000
        self.assertTrue(is_commercially_inactive(floor - D('0.01'), floor),
                        'immediately below the floor is inactive')
        self.assertFalse(is_commercially_inactive(floor, floor),
                         'at the floor is active')
        self.assertFalse(is_commercially_inactive(floor + D('0.01'), floor))

    def test_a_normal_selling_team_is_unaffected(self):
        floor = material_revenue_floor([D('1000000'), D('800000')])
        self.assertFalse(is_commercially_inactive(D('800000'), floor))
        self.assertFalse(is_commercially_inactive(D('1000000'), floor))


class SharedClassificationTests(ScoringFixture):
    """Both controls must consume the same classification."""

    def test_the_ranking_guard_uses_the_same_classification(self):
        from core.engine.performance import _enforce_inactive_revenue_invariant
        inactive = {'new_index': D('90'), 'commercially_inactive': True,
                    'guard_applied': False}
        active = {'new_index': D('60'), 'commercially_inactive': False,
                  'guard_applied': False}
        _enforce_inactive_revenue_invariant([inactive, active])
        self.assertTrue(inactive['guard_applied'])
        self.assertLess(inactive['new_index'], active['new_index'])

    def test_the_guard_reads_no_revenue_field_of_its_own(self):
        """The two controls disagreed because they tested different things."""
        import inspect
        from core.engine import performance
        source = inspect.getsource(
            performance._enforce_inactive_revenue_invariant)
        self.assertNotIn("item['revenue']", source,
                         'the ranking guard is testing revenue directly again')
        self.assertIn('commercially_inactive', source)
