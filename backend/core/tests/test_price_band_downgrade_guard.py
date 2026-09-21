"""Downgrade guard for migration 0085_price_band_blank_price (V2-041).

Under the not-for-sale rule a resolved round can legitimately hold a null
`decision_marketing.retail_price`. Reversing 0085 restores NOT NULL, so it must
refuse while such a row exists -- naming the rows, changing nothing -- rather
than fail with a bare NotNullViolation, and rather than "make it safe" by
inventing a price or deleting a team's stored decision.

The suite builds its schema from the models with migrations disabled
(`globalstrat.test_runner`), so a migration cannot be reversed inside it. What
is tested here is the guard the reverse path calls, and that it is wired where
it runs BEFORE the column change. The real forward/backward run, with and
without null rows, is recorded in
`handoff_readiness_v2/completion/FIXTURE_DOWNGRADE_RESET_2026-09-21.md`.
"""
import importlib

from django.apps import apps as live_apps
from django.db import migrations
from django.test import SimpleTestCase

from decimal import Decimal as D

from django.test import TestCase

from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionMarketing
from core.models.scenario import (MarketDefinition,
                                  PlatformGenerationDefinition)
from core.models.team_state import TeamPlatform, TeamProduct
from core.tests.test_operator_concurrency import build_minimal_game

migration_module = importlib.import_module(
    'core.migrations.0085_price_band_blank_price')


class ReverseOf0085RefusesWhileNullPricesExist(TestCase):

    def setUp(self):
        # The same minimal shape `test_price_band.PriceBandFixture` builds.
        # Not subclassed: that class carries tests of its own, and importing
        # it here would run them a second time under this module.
        self.game, teams = build_minimal_game(f'downgrade-{id(self)}')
        self.team = teams[0]
        self.market = MarketDefinition.objects.filter(
            scenario=self.game.scenario).first()
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation,
            name='Aurora platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='Aurora',
            positioning='mainstream', status='active', created_round=0)
        self.round1 = Round.objects.create(
            game=self.game, round_number=1, status='processed')

    def priced(self, price):
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=self.round1, defaults={'status': 'locked'})
        return DecisionMarketing.objects.create(
            submission=submission, team_product=self.product,
            market=self.market,
            retail_price=None if price is None else D(str(price)),
            promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('0.34'), channel_traditional_pct=D('0.33'),
            channel_trade_pct=D('0.33'), distribution_strategy='mass_retail',
            distribution_investment=D('0'), sales_team_count=0,
            distribution_channel_detail={}, production_volume=100,
            production_source_market=self.market, demand_estimate=100)

    def guard(self):
        return migration_module.refuse_downgrade_while_null_prices_exist(
            live_apps, None)

    def test_priced_rows_do_not_block_the_downgrade(self):
        self.priced(250)
        self.assertIsNone(self.guard())

    def test_a_null_price_blocks_the_downgrade_and_names_the_row(self):
        row = self.priced(None)

        with self.assertRaises(
                migration_module.NullPricesBlockDowngrade) as caught:
            self.guard()

        message = str(caught.exception)
        self.assertIn('REFUSED', message)
        self.assertIn('0085_price_band_blank_price', message)
        self.assertIn(f'decision_marketing #{row.pk}', message)
        self.assertIn(f'game {self.game.pk}', message)
        self.assertIn('round 1 [processed]', message)
        self.assertIn(self.team.name, message)
        self.assertIn('1 decision_marketing row(s)', message)

    def test_the_guard_changes_nothing(self):
        """It must not make the reversal "safe" by pricing or deleting."""
        row = self.priced(None)
        with self.assertRaises(migration_module.NullPricesBlockDowngrade):
            self.guard()
        row.refresh_from_db()
        self.assertIsNone(row.retail_price)
        self.assertEqual(DecisionMarketing.objects.count(), 1)


class TheGuardIsWiredIntoTheReversePathOnly(SimpleTestCase):
    """0085 is applied in production: only its reverse path may differ."""

    def setUp(self):
        self.operations = migration_module.Migration.operations

    def test_the_forward_schema_operation_is_untouched(self):
        first = self.operations[0]
        self.assertIsInstance(first, migrations.AlterField)
        self.assertEqual((first.model_name, first.name),
                         ('decisionmarketing', 'retail_price'))
        self.assertTrue(first.field.null)
        self.assertEqual(
            [type(op) for op in self.operations].count(migrations.AlterField), 1)
        self.assertEqual(migration_module.Migration.dependencies,
                         [('core', '0084_product_level_demand')])

    def test_the_guard_runs_before_not_null_is_restored(self):
        """Operations reverse last-to-first, so the guard must come last."""
        last = self.operations[-1]
        self.assertIsInstance(last, migrations.RunPython)
        self.assertIs(last.reverse_code,
                      migration_module.refuse_downgrade_while_null_prices_exist)
        self.assertIs(last.code, migrations.RunPython.noop)
