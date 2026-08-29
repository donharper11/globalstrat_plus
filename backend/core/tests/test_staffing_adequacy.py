"""V2-025 — strategic capability is multiplied by staffing adequacy.

`skeleton-crew` -- zero headcount, zero ESG, zero strategy budget -- won 9 of 9
holdout cells at +0.22, independently of opponents. Attribution isolated the
cause: emptying all three talent pools saved $1,200,000 of payroll and moved
strategic capability by exactly 0.0000, because `performance.py` never read
headcount. The saving converted straight into net income with nothing charging
for it.

The adopted rule::

    staffing_adequacy = mean over pools of clamp01(headcount / optimal)
    capability        = earned_capability * staffing_adequacy

The optima are scenario-authored and validated positive before competitive
mutation. `talent.py` read the same three keys with hardcoded 60/40/50
fallbacks; a silent default is not acceptable for a competition denominator, so
both consumers now fail closed.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.engine.performance import _strategic_capability_component
from core.engine.utils import (InvalidScenarioConfiguration, _config_cache,
                               scenario_optimal_headcounts, staffing_adequacy)
from core.models import DecisionSubmission, Game, Round, Scenario, Team
from core.models.decisions import DecisionBudgetAllocation, DecisionRDInvestment
from core.models.scenario import (FeatureDefinition, FirmStarterProfile,
                                  MarketDefinition, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.talent import DecisionTalent
from core.models.team_state import TeamPlatform

OPTIMA = {'rd': 60, 'commercial': 40, 'operations': 50}
RD_TARGET = D('2000000')


class StaffingFixture(TestCase):
    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        owner = DjangoUser.objects.create(username=f'owner-sa-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Staffing {id(self)}', industry_label='T', description='d',
            starting_cash=1000000, num_rounds=4)
        self.config = {}
        for key, value in (('reference_price_budget', '250'),
                           ('reference_price_mainstream', '420'),
                           ('reference_price_premium', '700'),
                           ('reference_price_ultra_premium', '1000'),
                           ('high_price_elasticity', '1.5'),
                           ('rd_spend_target', '2000000'),
                           ('optimal_rd_headcount', '60'),
                           ('optimal_commercial_headcount', '40'),
                           ('optimal_operations_headcount', '50')):
            self.config[key] = ScenarioConfig.objects.create(
                scenario=self.scenario, config_key=key, config_value=value,
                description=key)
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=1000000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Staffing game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000000, total_equity=1000000)
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
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=self.submission, rd_budget=D('2000000'),
            marketing_budget=D('0'), strategy_budget=D('0'),
            research_budget=D('0'))
        self.talent = DecisionTalent.objects.create(
            submission=self.submission,
            rd_headcount=OPTIMA['rd'],
            commercial_headcount=OPTIMA['commercial'],
            operations_headcount=OPTIMA['operations'],
            rd_salary_level=3, commercial_salary_level=3,
            operations_salary_level=3, rd_training_budget=D('0'),
            commercial_training_budget=D('0'),
            operations_training_budget=D('0'))

    def set_rd_spend(self, amount):
        DecisionRDInvestment.objects.filter(submission=self.submission).delete()
        if amount is not None:
            DecisionRDInvestment.objects.create(
                submission=self.submission, team_platform=self.platform,
                feature=self.feature, method='in_house', amount=D(str(amount)),
                target_level=1)

    def capability(self):
        return _strategic_capability_component(
            self.team, 1, RD_TARGET, scenario_optimal_headcounts(self.scenario))

    def set_headcounts(self, **pools):
        for pool, value in pools.items():
            setattr(self.talent, f'{pool}_headcount', value)
        self.talent.save()


class TheRule(StaffingFixture):
    def test_all_zero_headcount_produces_zero_capability(self):
        self.set_rd_spend(RD_TARGET)
        self.set_headcounts(rd=0, commercial=0, operations=0)
        self.assertEqual(self.capability(), D('0'))

    def test_zeroing_each_pool_removes_exactly_its_contribution(self):
        """Each pool is a third of the factor, so capability falls to 2/3."""
        self.set_rd_spend(RD_TARGET)
        full = self.capability()
        for pool in ('rd', 'commercial', 'operations'):
            with self.subTest(pool=pool):
                self.set_headcounts(**{p: OPTIMA[p] for p in OPTIMA})
                self.set_headcounts(**{pool: 0})
                reduced = self.capability()
                self.assertAlmostEqual(
                    float(reduced), float(full) * 2 / 3, places=3)

    def test_staffing_at_each_optimum_preserves_capability(self):
        """The factor is exactly 1, so the earned score passes through."""
        self.set_rd_spend(RD_TARGET)
        self.set_headcounts(**{p: OPTIMA[p] for p in OPTIMA})
        # Earned score with a full R&D ratio and both action bonuses absent.
        self.assertEqual(self.capability(), D('0.6700'))

    def test_staffing_above_optimum_creates_no_extra_capability(self):
        self.set_rd_spend(RD_TARGET)
        self.set_headcounts(**{p: OPTIMA[p] for p in OPTIMA})
        at_optimum = self.capability()
        self.set_headcounts(rd=6000, commercial=4000, operations=5000)
        self.assertEqual(self.capability(), at_optimum)

    def test_the_factor_is_the_mean_of_clamped_ratios(self):
        optima = {'rd': 60.0, 'commercial': 40.0, 'operations': 50.0}
        self.assertEqual(staffing_adequacy(
            {'rd': 0, 'commercial': 0, 'operations': 0}, optima), 0.0)
        self.assertEqual(staffing_adequacy(
            {'rd': 60, 'commercial': 40, 'operations': 50}, optima), 1.0)
        self.assertAlmostEqual(staffing_adequacy(
            {'rd': 30, 'commercial': 40, 'operations': 50}, optima),
            (0.5 + 1 + 1) / 3)


class RDStillMatters(StaffingFixture):
    def test_actual_rd_spend_still_moves_capability(self):
        """The staffing factor scales the score; it must not flatten it."""
        self.set_headcounts(**{p: OPTIMA[p] for p in OPTIMA})
        self.set_rd_spend(0)
        none = self.capability()
        self.set_rd_spend(RD_TARGET / 2)
        half = self.capability()
        self.set_rd_spend(RD_TARGET)
        full = self.capability()
        self.assertLess(none, half)
        self.assertLess(half, full)

    def test_changing_the_declared_rd_budget_remains_inert(self):
        """V2-021 holds: the denominator is a scenario constant, not a choice."""
        self.set_headcounts(**{p: OPTIMA[p] for p in OPTIMA})
        self.set_rd_spend(RD_TARGET / 2)
        before = self.capability()
        budget = DecisionBudgetAllocation.objects.get(submission=self.submission)
        for declared in ('0', '1', '50000000'):
            with self.subTest(declared=declared):
                budget.rd_budget = D(declared)
                budget.save(update_fields=['rd_budget'])
                _config_cache.clear()
                self.assertEqual(self.capability(), before)


class ConfigurationFailsClosed(StaffingFixture):
    def test_valid_optima_are_returned(self):
        self.assertEqual(
            scenario_optimal_headcounts(self.scenario),
            {'rd': 60.0, 'commercial': 40.0, 'operations': 50.0})

    def test_each_missing_optimum_is_refused(self):
        for key in ('optimal_rd_headcount', 'optimal_commercial_headcount',
                    'optimal_operations_headcount'):
            with self.subTest(key=key):
                row = self.config[key]
                value = row.config_value
                row.delete()
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_optimal_headcounts(self.scenario)
                self.config[key] = ScenarioConfig.objects.create(
                    scenario=self.scenario, config_key=key,
                    config_value=value, description=key)
                _config_cache.clear()

    def test_zero_negative_and_non_finite_optima_are_refused(self):
        row = self.config['optimal_rd_headcount']
        for value in ('0', '-60', 'nan', 'inf'):
            with self.subTest(value=value):
                row.config_value = value
                row.save(update_fields=['config_value'])
                _config_cache.clear()
                with self.assertRaises(InvalidScenarioConfiguration):
                    scenario_optimal_headcounts(self.scenario)

    def test_resolution_refuses_before_any_competitive_write(self):
        from core.engine.advance_round import (
            InvalidScenarioConfigurationError, _run_phase_1)
        self.submission.status = 'locked'
        self.submission.locked_at = timezone.now()
        self.submission.save(update_fields=['status', 'locked_at'])
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])
        self.config['optimal_commercial_headcount'].delete()
        _config_cache.clear()
        with self.assertRaises(InvalidScenarioConfigurationError):
            _run_phase_1(self.game.id)
        self.round.refresh_from_db()
        self.assertNotEqual(
            self.round.processing_status, 'PROCESSING',
            'the round was marked processing before configuration was checked')


class DeterministicInputEnvelope(StaffingFixture):
    def test_the_three_optima_are_in_the_manifest_configuration(self):
        from core.services.manifest_sections import (CONFIG_SECTION_NAMES,
                                                     INPUT_SECTIONS)
        from core.services.manifest_snapshot import build_snapshot
        self.assertIn('scenario_config', CONFIG_SECTION_NAMES)
        sections = tuple(s for s in INPUT_SECTIONS
                         if s.name in CONFIG_SECTION_NAMES)
        snapshot = build_snapshot(sections, 'input', self.scenario.id,
                                  self.game.id)
        rows = snapshot.rows['scenario_config']
        keys = {row.get('config_key') for row in rows}
        for key in ('optimal_rd_headcount', 'optimal_commercial_headcount',
                    'optimal_operations_headcount'):
            with self.subTest(key=key):
                self.assertIn(key, keys)
