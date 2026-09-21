"""V2-116 — the CRV2-01 determinism fixture must stay runnable at head.

`handoff_readiness_v2/determinism_fixture.py` generates the round the
four-environment replay evidence is taken from. It drifted: it went on seeding
feature-level `DecisionRDInvestment` rows after owner ruling R10 retired them,
the engine refuses any round that carries one, and nobody noticed until a
different fixture was being written -- because nothing in the suite ever ran
this one.

These tests run it. They import the checked-in script and drive its own
`seed_round` against a real scenario, then resolve the round, so the next rule
change that makes the fixture unresolvable fails here rather than on the day
the release evidence is due.

This is NOT replay evidence. It shows the fixture's decisions are admissible
under the rules in force and nothing more.
"""
import importlib.util
import io
import pathlib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Game, Round
from core.models.decisions import (DecisionPlatformDevelopment,
                                   DecisionRDInvestment)
from core.models.scenario import Scenario
from core.services import rd_costs

FIXTURE_PATH = (pathlib.Path(settings.BASE_DIR).parent
                / 'handoff_readiness_v2' / 'determinism_fixture.py')


def load_fixture_module():
    spec = importlib.util.spec_from_file_location(
        'crv2_determinism_fixture', FIXTURE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeterminismFixtureIsRunnableAtHead(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Not in setUpTestData: Django deep-copies what is assigned there, and
        # a module cannot be copied.
        cls.fixture = load_fixture_module()

    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario',
                     file='scenarios/consumer_electronics_2026.yaml',
                     stdout=io.StringIO())
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        get_user_model().objects.create_superuser(
            'v2-116-fixture-owner', 'fixture@example.com', 'x')

    def setUp(self):
        call_command('initialize_game', scenario=self.scenario.id, teams=4,
                     name='V2-116 fixture', stdout=io.StringIO())
        self.game = Game.objects.filter(
            name='V2-116 fixture').order_by('-id').first()
        self.game.section_id = 91160
        self.game.save(update_fields=['section_id'])
        self.round = Round.objects.get(game=self.game, round_number=1)

    def assert_no_engine_refusal(self, round_obj):
        """Every R&D precondition `_run_phase_1` asks, asked of the fixture."""
        for check in (rd_costs.persisted_retired_rd_violations,
                      rd_costs.persisted_cost_violations,
                      rd_costs.persisted_unlock_violations,
                      rd_costs.persisted_ownership_violations,
                      rd_costs.persisted_feature_cap_violations,
                      rd_costs.persisted_duplicate_generation_violations,
                      rd_costs.persisted_held_generation_violations):
            self.assertEqual(check(self.game, round_obj), [], check.__name__)

    def test_the_fixture_seeds_no_retired_rd_decision(self):
        self.fixture.seed_round(self.game, self.round, self.scenario)

        self.assertEqual(
            DecisionRDInvestment.objects.filter(
                submission__team__game=self.game).count(), 0,
            'R10 retired feature-level R&D; the engine refuses every stored row.')
        self.assert_no_engine_refusal(self.round)

    def test_the_round_the_fixture_builds_resolves(self):
        """The defect itself: at head this raised InvalidPersistedDecisionError
        ("16 stored R&D investment(s) remain ... retired (R10)")."""
        from core.engine.advance_round import close_round, process_round

        self.fixture.seed_round(self.game, self.round, self.scenario)
        self.round.deadline = timezone.now()
        self.round.save(update_fields=['deadline'])
        close_round(self.game.id, reason='v2-116-test')
        process_round(self.game.id)

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertTrue(self.round.resolution_manifest.output_sha256)

    def test_platform_development_is_seeded_only_where_the_rules_allow(self):
        """R&D under R10 is a platform development. The shipped scenario
        unlocks its first non-starting generation in round 2, so round 1 must
        carry none and a round-2 row must be admissible as stored."""
        developments = self.fixture.seed_round(
            self.game, self.round, self.scenario)
        self.assertEqual(developments, 0)
        self.assertFalse(DecisionPlatformDevelopment.objects.filter(
            submission__team__game=self.game).exists())

        round2, _ = Round.objects.get_or_create(
            game=self.game, round_number=2, defaults={'status': 'open'})
        developments = self.fixture.seed_round(self.game, round2, self.scenario)

        self.assertGreater(developments, 0)
        rows = list(DecisionPlatformDevelopment.objects.filter(
            submission__round=round2))
        self.assertEqual(len(rows), developments)
        self.assertEqual({row.method for row in rows}, {'in_house', 'license'})
        for row in rows:
            self.assertEqual(
                row.committed_cost,
                rd_costs.platform_development_cost(
                    row.platform_generation, row.method))
            self.assertTrue(row.feature_levels)
        self.assert_no_engine_refusal(round2)
