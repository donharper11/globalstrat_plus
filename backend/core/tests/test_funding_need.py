"""V2-024 — equity may finance a funding shortfall, and nothing else.

The Stage 3 tournament demonstrated an opponent-independent dominant strategy:
the documented baseline plus an unused $20,000,000 raise won 9 of 9 holdout
cells with near-identical advantage against every opponent population, because
equity lowers debt-to-equity and the index never charges for dilution. Raising
equity and paying it straight out as dividends won all nine cells too.

The adopted rule::

    eligible_uses      = operating and strategic cash outlays + debt repayment
    available_funding  = opening cash + new debt
    maximum_new_equity = max(0, eligible_uses - available_funding)

Rejected, never clamped. These tests are written against the acceptance points
the disposition names, one test each.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.services import funding_need
from core.models import DecisionSubmission, Game, Round, Scenario, Team
from core.models.decisions import (DecisionESG, DecisionFinancing,
                                   DecisionMarketing)
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.talent import DecisionTalent
from core.models.team_state import TeamPlatform, TeamProduct

OPENING_CASH = D('1000000')


class FundingFixture(TestCase):
    def setUp(self):
        from core.engine.utils import _config_cache
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        owner = DjangoUser.objects.create(username=f'owner-fn-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Funding {id(self)}', industry_label='T', description='d',
            starting_cash=OPENING_CASH, num_rounds=4)
        for key, value in (('reference_price_budget', '250'),
                           ('reference_price_mainstream', '420'),
                           ('reference_price_premium', '700'),
                           ('reference_price_ultra_premium', '1000'),
                           ('high_price_elasticity', '1.5'),
                           ('rd_spend_target', '2000000'),
                           ('sales_rep_cost_per_round', '100000')):
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
            home_market=self.market, starting_cash=OPENING_CASH,
            starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Funding game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen', description='d',
            generation_order=1, unlock_round=1, development_cost=0,
            development_rounds=1, license_cost=0, annual_maintenance_cost=0,
            is_starting_platform=True)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='P',
            status='active')
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=self.platform, name='Prod',
            positioning='mainstream', status='active', created_round=1)
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionTalent.objects.create(
            submission=self.submission, rd_headcount=0,
            commercial_headcount=0, operations_headcount=0,
            rd_salary_level=1, commercial_salary_level=1,
            operations_salary_level=1, rd_training_budget=D('0'),
            commercial_training_budget=D('0'),
            operations_training_budget=D('0'))

    def spend(self, amount):
        """Create a single, exactly known outlay: an ESG investment."""
        DecisionESG.objects.filter(submission=self.submission).delete()
        DecisionESG.objects.create(
            submission=self.submission,
            environmental_investment=D(str(amount)), social_investment=D('0'))

    def financing(self, new_equity='0', new_debt='0', debt_repayment='0',
                  dividend_per_share='0'):
        DecisionFinancing.objects.filter(submission=self.submission).delete()
        return DecisionFinancing.objects.create(
            submission=self.submission, new_debt=D(new_debt),
            debt_repayment=D(debt_repayment), new_equity=D(new_equity),
            dividend_per_share=D(dividend_per_share))

    def assess(self, **override):
        return funding_need.assess_submission(
            self.submission, financing_override=override or None)


class TheFormula(FundingFixture):
    def test_baseline_plus_an_unused_raise_is_rejected(self):
        """The exploit itself: no outlays beyond cash, so no shortfall."""
        self.spend(0)
        self.financing(new_equity='20000000')
        assessment = self.assess()
        self.assertEqual(D(assessment['maximum_new_equity']), D('0'))
        self.assertFalse(assessment['within_limit'])

    def test_equity_used_solely_for_dividends_is_rejected(self):
        """Dividends are not an eligible use, so they create no headroom."""
        self.spend(0)
        self.financing(new_equity='20000000', dividend_per_share='5')
        assessment = self.assess()
        self.assertEqual(D(assessment['maximum_new_equity']), D('0'))
        self.assertFalse(assessment['within_limit'])

    def test_a_raise_exactly_equal_to_the_shortfall_is_accepted(self):
        self.spend(OPENING_CASH + D('500000'))
        self.financing(new_equity='500000')
        assessment = self.assess()
        self.assertEqual(D(assessment['maximum_new_equity']), D('500000'))
        self.assertTrue(assessment['within_limit'])

    def test_one_cent_above_the_shortfall_is_rejected(self):
        self.spend(OPENING_CASH + D('500000'))
        self.financing(new_equity='500000.01')
        self.assertFalse(self.assess()['within_limit'])

    def test_opening_cash_reduces_the_allowable_raise(self):
        self.spend(OPENING_CASH + D('500000'))
        before = D(self.assess(new_equity='0')['maximum_new_equity'])
        self.team.cash_on_hand = OPENING_CASH + D('200000')
        self.team.save(update_fields=['cash_on_hand'])
        after = D(self.assess(new_equity='0')['maximum_new_equity'])
        self.assertEqual(before - after, D('200000'))

    def test_new_debt_reduces_the_allowable_raise(self):
        self.spend(OPENING_CASH + D('500000'))
        before = D(self.assess(new_equity='0')['maximum_new_equity'])
        after = D(self.assess(new_equity='0',
                              new_debt='300000')['maximum_new_equity'])
        self.assertEqual(before - after, D('300000'))

    def test_debt_repayment_is_an_eligible_use(self):
        self.spend(0)
        without = D(self.assess(new_equity='0')['maximum_new_equity'])
        withrepay = D(self.assess(
            new_equity='0', debt_repayment='750000')['maximum_new_equity'])
        self.assertEqual(without, D('0'))
        # Repayment raises eligible uses; opening cash still covers the first
        # million of it, so the shortfall is what exceeds available funding.
        self.assertEqual(withrepay, D('0'))
        bigger = D(self.assess(
            new_equity='0', debt_repayment='1500000')['maximum_new_equity'])
        self.assertEqual(bigger, D('500000'))

    def test_a_rejection_is_not_a_clamp(self):
        """The stored value is left alone; nothing silently rewrites it."""
        self.spend(0)
        row = self.financing(new_equity='20000000')
        self.assertFalse(self.assess()['within_limit'])
        row.refresh_from_db()
        self.assertEqual(row.new_equity, D('20000000'))


class OneCalculator(FundingFixture):
    def test_outlay_lines_come_from_the_engine_s_own_expressions(self):
        """Marketing outlay must equal promotion plus the engine's rep cost."""
        DecisionMarketing.objects.create(
            submission=self.submission, team_product=self.product,
            market=self.market, retail_price=D('420'),
            promotion_budget=D('250000'), campaign_focus_feature_ids=[],
            channel_digital_pct=0, channel_traditional_pct=0,
            channel_trade_pct=0, distribution_strategy='hybrid',
            distribution_investment=D('0'), sales_team_count=3,
            production_volume=0, production_source_market=self.market,
            demand_estimate=0)
        lines = funding_need.decision_outlays(
            self.scenario, self.team, self.submission, 1)
        self.assertEqual(lines['marketing'], D('250000') + D('100000') * 3)

    def test_talent_cost_matches_the_engine_salary_table(self):
        talent = self.submission.talent
        talent.rd_headcount = 10
        talent.rd_salary_level = 3
        talent.save()
        lines = funding_need.decision_outlays(
            self.scenario, self.team, self.submission, 1)
        # Level 3 is $30,000; ten new hires at $10,000 recruitment each.
        self.assertEqual(lines['talent'], D('300000') + D('100000'))


class EnginePrecondition(FundingFixture):
    def test_resolution_refuses_before_any_competitive_write(self):
        from core.engine.advance_round import (EquityExceedsFundingNeedError,
                                               _run_phase_1)
        self.spend(0)
        self.financing(new_equity='20000000')
        self.submission.status = 'locked'
        self.submission.locked_at = timezone.now()
        self.submission.save(update_fields=['status', 'locked_at'])
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        with self.assertRaises(EquityExceedsFundingNeedError):
            _run_phase_1(self.game.id)
        self.round.refresh_from_db()
        self.assertNotEqual(
            self.round.processing_status, 'PROCESSING',
            'the round was marked processing before financing was checked')

    def test_a_legitimate_raise_does_not_trip_the_precondition(self):
        self.spend(OPENING_CASH + D('500000'))
        self.financing(new_equity='500000')
        self.assertEqual(
            funding_need.violations(self.game, self.round), [])


class ManifestReconstructability(FundingFixture):
    def test_every_input_to_the_rule_is_a_manifest_section(self):
        """The funding requirement is derived, so its inputs must be recorded."""
        from core.services.manifest_sections import INPUT_SECTIONS
        names = {section.name for section in INPUT_SECTIONS}
        for required in ('decision_financing', 'decision_esg', 'decision_talent',
                         'decision_marketing', 'decision_rd',
                         'team', 'team_talent_state', 'scenario_config'):
            with self.subTest(section=required):
                self.assertIn(required, names)

    def test_the_assessment_records_both_sides_of_the_comparison(self):
        self.spend(OPENING_CASH + D('500000'))
        self.financing(new_equity='500000')
        assessment = self.assess()
        for key in ('outlays', 'debt_repayment', 'eligible_uses',
                    'opening_cash', 'new_debt', 'available_funding',
                    'maximum_new_equity', 'requested_new_equity'):
            self.assertIn(key, assessment)
