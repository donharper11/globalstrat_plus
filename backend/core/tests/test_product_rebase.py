"""Re-basing a product, and the history that keeps past rounds reconstructable.

Stage 4. The feature is small; the trap it opens is not. BECSR recorded it as
defect B: its demand side resolved platforms as of the round while its supply
side resolved them as of now, so a re-based program's demand reconciled to
nothing — no sale, no lost sale, no inventory row and no error, because the
standing `demand - sold - lost == 0` check summed only rows that existed. It
measured zero units purely because no cohort had used the feature.

GlobalStrat's shape was different and, for determinism, worse: every consumer
read one live pointer, so a switch would have silently re-resolved rounds
already scored and published — the boundary GSP-CRV2-01 certified.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.models import DecisionSubmission, Round
from core.models.results_financials import RoundResultProductMarket
from core.models.scenario import (FeatureDefinition, FeatureLevelCost,
                                  MarketDefinition, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.team_state import (TeamPlatform, TeamPlatformFeatureLevel,
                                    TeamProduct, TeamProductPlatformHistory)
from core.services import product_platform, product_rebase
from core.tests.test_operator_concurrency import build_minimal_game


class RebaseFixture(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'rebase-{id(self)}')
        self.team = self.teams[0]
        self.other_team = self.teams[1]
        self.scenario = self.game.scenario
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()

        self.old_gen = self.generation(1)
        self.new_gen = self.generation(2)
        self.old_platform = self.platform(self.old_gen, 'Old Platform')
        self.new_platform = self.platform(self.new_gen, 'New Platform')

        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='REB', name='Rebase feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'))
        # The two platforms differ on the feature, so a round resolving to the
        # wrong one is visible rather than coincidentally equal.
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.old_platform, feature=self.feature,
            current_level=D('3'))
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.new_platform, feature=self.feature,
            current_level=D('9'))

        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=self.old_platform,
            name='Aurora', positioning='mainstream', status='active',
            created_round=1)

    def generation(self, order):
        return PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name=f'Gen {order}', description='d',
            generation_order=order, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)

    def platform(self, generation, name, team=None, status='active'):
        return TeamPlatform.objects.create(
            team=team or self.team, platform_generation=generation, name=name,
            status=status, development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0)

    def stock(self, round_number, unsold, unit_cost):
        return RoundResultProductMarket.objects.create(
            game=self.game, round_number=round_number, team=self.team,
            team_product=self.product, market=self.market,
            units_produced=int(unsold), units_sold=D('0'),
            units_unsold=D(str(unsold)), unit_cost=D(str(unit_cost)))


class RebaseRefusalTests(RebaseFixture):
    """Fail-closed: ownership, readiness, and the no-op switch."""

    def test_another_teams_platform_is_refused(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, theirs, self.team, 2)
        self.assertIn('belongs to another team', str(caught.exception))
        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.old_platform.id)
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)

    def test_a_platform_still_in_development_is_refused(self):
        building = self.platform(self.new_gen, 'Building',
                                 status='in_development')
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, building, self.team, 2)
        self.assertIn('only be re-based onto a ready platform',
                      str(caught.exception))
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)

    def test_an_unfunded_draft_is_refused(self):
        draft = self.platform(self.new_gen, 'Draft', status='unfunded_draft')
        with self.assertRaises(product_rebase.RebaseRefused):
            product_rebase.rebase(self.product, draft, self.team, 2)

    def test_another_teams_product_is_refused(self):
        theirs = TeamProduct.objects.create(
            team=self.other_team, team_platform=self.old_platform,
            name='Not mine', positioning='mainstream', status='active',
            created_round=1)
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(theirs, self.new_platform, self.team, 2)
        self.assertIn('belongs to another team', str(caught.exception))

    def test_re_basing_onto_the_current_platform_is_refused(self):
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, self.old_platform, self.team, 2)
        self.assertIn('already based on', str(caught.exception))

    def test_a_refusal_charges_nothing_and_writes_no_history(self):
        self.stock(1, unsold=100, unit_cost=50)
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        with self.assertRaises(product_rebase.RebaseRefused):
            product_rebase.rebase(self.product, theirs, self.team, 2)
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)
        self.assertEqual(
            product_rebase.write_offs_for_round(self.team, 2), D('0'))


class RebaseWriteOffTests(RebaseFixture):
    """Authoritative and exactly once."""

    def test_the_write_off_is_the_authored_percentage_of_stock(self):
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='platform_switch_write_off_pct',
            config_value='0.15', description='Stage 4')
        self.stock(1, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(result['units_written_off'], 100)
        self.assertEqual(D(result['write_off']), D('750.00'))   # 100*50*0.15

    def test_the_percentage_comes_from_the_scenario(self):
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='platform_switch_write_off_pct',
            config_value='0.40', description='Stage 4')
        from core.engine import utils as engine_utils
        engine_utils._config_cache.pop(self.scenario.id, None)
        self.stock(1, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(D(result['write_off']), D('2000.00'))

    def test_no_stock_costs_nothing(self):
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(result['units_written_off'], 0)
        self.assertEqual(D(result['write_off']), D('0'))

    def test_only_the_latest_closing_position_is_written_off(self):
        """Summing older rows would write off stock sold rounds ago."""
        self.stock(1, unsold=500, unit_cost=50)
        self.stock(2, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(result['units_written_off'], 100)

    def test_the_charge_is_read_once_from_the_history_row(self):
        self.stock(1, unsold=100, unit_cost=50)
        product_rebase.rebase(self.product, self.new_platform, self.team, 2)
        self.assertEqual(product_rebase.write_offs_for_round(self.team, 2),
                         D('750.00'))
        # Not charged again in a later round.
        self.assertEqual(product_rebase.write_offs_for_round(self.team, 3),
                         D('0'))

    def test_a_second_switch_in_one_round_updates_rather_than_adds(self):
        third_gen = self.generation(3)
        third = self.platform(third_gen, 'Third Platform')
        self.stock(1, unsold=100, unit_cost=50)
        product_rebase.rebase(self.product, self.new_platform, self.team, 2)
        product_rebase.rebase(self.product, third, self.team, 2)
        rows = TeamProductPlatformHistory.objects.filter(
            team_product=self.product, effective_from_round=2)
        self.assertEqual(rows.count(), 1, 'a second switch added a second row')
        self.assertEqual(rows.first().team_platform_id, third.id)


class RebaseHistoryTests(RebaseFixture):
    """Atomic switch, seeded history, and round-correct resolution."""

    def test_the_prior_association_is_seeded_on_the_first_switch(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        rows = list(TeamProductPlatformHistory.objects
                    .filter(team_product=self.product)
                    .order_by('effective_from_round')
                    .values_list('effective_from_round', 'team_platform_id'))
        self.assertEqual(rows, [(1, self.old_platform.id),
                                (4, self.new_platform.id)])

    def test_earlier_rounds_still_resolve_to_the_old_platform(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 2, 3):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id,
                self.old_platform.id,
                f'round {round_number} re-attributed to the new platform')
        for round_number in (4, 5):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id,
                self.new_platform.id)

    def test_the_batched_resolution_agrees_with_the_single_one(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 3, 4, 6):
            batched = product_platform.platform_ids_as_of_round(
                [self.product], round_number)[self.product.id]
            single = product_platform.platform_as_of_round(
                self.product, round_number).id
            self.assertEqual(batched, single,
                             f'batched and single disagree in round {round_number}')

    def test_the_live_pointer_moves_with_the_switch(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.new_platform.id)

    def test_a_product_without_history_resolves_to_its_pointer(self):
        for round_number in (0, 1, 9):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id, self.old_platform.id)


class MissingResolutionTests(RebaseFixture):
    """The check that fails on an absent row rather than summing present ones."""

    def test_a_healthy_game_reports_nothing(self):
        self.assertEqual(
            product_platform.missing_platform_resolutions(self.game, 1), [])

    def test_a_product_resolving_to_another_teams_platform_is_named(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        product_platform.record_association(self.product, theirs, 1)
        problems = product_platform.missing_platform_resolutions(self.game, 1)
        self.assertEqual(len(problems), 1)
        self.assertIn('owned by another team', problems[0]['detail'])
        self.assertIn('Aurora',
                      product_platform.describe_missing_resolutions(problems))

    def test_the_check_reads_the_round_it_is_asked_about(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        product_platform.record_association(self.product, self.old_platform, 1)
        product_platform.record_association(self.product, theirs, 5)
        self.assertEqual(
            product_platform.missing_platform_resolutions(self.game, 1), [])
        self.assertEqual(
            len(product_platform.missing_platform_resolutions(self.game, 5)), 1)


class SwitchThenReplayTests(RebaseFixture):
    """A round scored before a switch must replay to the same answer.

    This is the GSP-CRV2-01 boundary. Before Stage 4 every consumer read
    `TeamProduct.team_platform`, a single live pointer, so re-basing would have
    changed what an already-resolved round resolved to -- a different feature
    level, a different fit score, a different competitive hash for a round the
    cohort had already been shown.

    The engine now resolves through `resolved_platform`, so these tests ask the
    resolution question the way the engine asks it, before and after a switch.
    """

    def resolve_via_engine(self, round_number):
        """What the engine's own helper answers for this round."""
        from core.engine.utils import resolved_platform
        return resolved_platform(self.product, round_number).id

    def feature_level_seen(self, round_number):
        """The platform feature level the demand side would score with."""
        from core.engine.preference_engine import _get_platform_value
        return _get_platform_value(self.team, self.product, self.feature,
                                   round_number)

    def test_the_engine_helper_resolves_as_of_the_round(self):
        before = {r: self.resolve_via_engine(r) for r in (1, 2, 3)}
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        after = {r: self.resolve_via_engine(r) for r in (1, 2, 3)}
        self.assertEqual(before, after,
                         'a resolved round changed platform after a switch')
        self.assertEqual(self.resolve_via_engine(4), self.new_platform.id)

    def test_the_feature_level_a_past_round_scored_with_is_unchanged(self):
        """The value that actually feeds the fit score, not just the FK."""
        before = {r: self.feature_level_seen(r) for r in (1, 2, 3)}
        self.assertEqual(set(before.values()), {3.0},
                         'fixture did not score on the old platform')
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        after = {r: self.feature_level_seen(r) for r in (1, 2, 3)}
        self.assertEqual(before, after,
                         'a past round would now score on the new platform')
        self.assertEqual(self.feature_level_seen(4), 9.0,
                         'the switch round did not pick up the new platform')

    def test_demand_and_supply_resolve_identically(self):
        """Defect B in one assertion: the two sides cannot disagree."""
        from core.engine.utils import resolved_platform
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 2, 3, 4, 5):
            demand_side = resolved_platform(self.product, round_number).id
            supply_side = product_platform.platform_ids_as_of_round(
                [self.product], round_number)[self.product.id]
            self.assertEqual(demand_side, supply_side,
                             f'demand and supply disagree in round {round_number}')

    def test_a_switch_does_not_disturb_an_unswitched_product(self):
        other = TeamProduct.objects.create(
            team=self.team, team_platform=self.old_platform, name='Steady',
            positioning='mainstream', status='active', created_round=1)
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 4, 6):
            self.assertEqual(
                product_platform.platform_as_of_round(other, round_number).id,
                self.old_platform.id,
                'an unswitched product moved with another product\'s switch')
