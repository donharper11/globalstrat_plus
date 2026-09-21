"""0086's reversal drops what teams paid for. It must refuse while any exists.

The runner disables migrations, so this pins the guard and its wiring;
`scripts/check-downgrade-guards` reverses the real migrations on a disposable
database and is the proof by execution.
"""
import importlib

from django.apps import apps
from django.db import migrations
from django.test import TestCase

from core.models import Round
from core.models.decisions import DecisionSubmission
from core.models.research import DecisionResearchPurchase
from core.tests.test_operator_concurrency import build_minimal_game

module = importlib.import_module('core.migrations.0086_paid_research_reports')


class PaidResearchDowngradeGuardTests(TestCase):

    def test_the_guard_is_the_first_thing_a_reversal_runs(self):
        last = module.Migration.operations[-1]
        self.assertIsInstance(last, migrations.RunPython)
        self.assertIs(last.reverse_code,
                      module.refuse_downgrade_while_purchases_exist)
        self.assertIs(last.code, migrations.RunPython.noop)

    def test_no_purchases_no_refusal(self):
        module.refuse_downgrade_while_purchases_exist(apps, None)

    def test_a_stored_purchase_refuses_and_is_named(self):
        game, teams = build_minimal_game('r0086')
        round_obj = Round.objects.filter(game=game).first() or Round.objects.create(
            game=game, round_number=1, status='open')
        submission = DecisionSubmission.objects.create(
            team=teams[0], round=round_obj, status='draft')
        purchase = DecisionResearchPurchase.objects.create(
            submission=submission, report_type='analyst_query',
            scope_key='1', price=1000)
        with self.assertRaises(module.ResearchPurchasesBlockDowngrade) as refused:
            module.refuse_downgrade_while_purchases_exist(apps, None)
        self.assertIn(f'#{purchase.pk} ', str(refused.exception))
        self.assertTrue(
            DecisionResearchPurchase.objects.filter(pk=purchase.pk).exists())
