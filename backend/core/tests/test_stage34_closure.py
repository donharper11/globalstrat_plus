"""Stage 3 and Stage 4 together: the only route to a better product.

The per-item suites prove each rule. This one asks the question closure turns
on, which none of them asks: after Ruling 1 retired the upgrade path, does a
team still have a way through?

The two stages are load-bearing for each other. Stage 3B removed the route a
team used to take, so Stage 4's re-basing is not a convenience -- it is the
whole remaining path. If either half were wrong, a team would be stuck with
the product it started with, and no per-item test would say so, because each
one passes on its own.

So this walks the journey end to end, across rounds, through the engine:

    round 1  upgrade the ready platform      -> refused (Stage 3B)
             request a new generation        -> priced, funded, clock starts
    round 2  still in development            -> authored lead time honoured
    round 3  ready; re-base onto it          -> write-off charged once
             past rounds                     -> still resolve to the old platform

and asserts the destination as well as the refusal.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionPlatformDevelopment,
                                   DecisionRDInvestment)
from core.models.results_financials import (RoundResultFinancials,
                                            RoundResultProductMarket)
from core.models.scenario import (FeatureDefinition, MarketDefinition,
                                  PlatformFeatureCeiling,
                                  PlatformGenerationDefinition)
from core.models.team_state import (TeamPlatform, TeamPlatformFeatureLevel,
                                    TeamProduct, TeamProductPlatformHistory)
from core.services import product_platform, product_rebase
from core.tests.test_operator_concurrency import build_minimal_game


class Stage34JourneyTests(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'closure-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()

        self.gen1 = self.generation(1, rounds=0)
        self.gen2 = self.generation(2, rounds=2)
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='CLS', name='Closure feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'),
            default_value=D('3'), max_value=D('10'))
        for g in (self.gen1, self.gen2):
            PlatformFeatureCeiling.objects.create(
                platform_generation=g, feature=self.feature,
                ceiling_value=D('10'), starting_value=D('3'))

        # Where the team starts: one ready platform, one product on it.
        self.old = TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen1,
            name='Founding Platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.old, feature=self.feature,
            current_level=D('3'))
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=self.old, name='Aurora',
            positioning='mainstream', status='active', created_round=1)

    def generation(self, order, rounds):
        return PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name=f'Gen {order}', description='d',
            generation_order=order, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=rounds)

    def submission_for(self, round_number):
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=round_number,
            defaults={'status': 'open'})
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        return submission

    def advance_rd(self, round_number):
        from core.engine.rd_processing import _process_platform_development
        _process_platform_development(
            self.team, self.submission_for(round_number), round_number)

    # -- the journey --------------------------------------------------------

    def test_the_old_route_is_closed_and_the_new_route_completes(self):
        # Round 1: the upgrade a team would previously have bought.
        from core.services.rd_costs import frozen_platform_problem
        self.assertIsNotNone(
            frozen_platform_problem(self.old),
            'Stage 3B: a ready platform must refuse a feature upgrade.')

        # Round 1: so they build instead. Authored lead time is 2 rounds.
        submission = self.submission_for(1)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen2,
            method='in_house', committed_cost=self.gen2.development_cost,
            platform_name='Successor', feature_levels={})
        self.advance_rd(1)

        successor = TeamPlatform.objects.get(team=self.team, name='Successor')
        self.assertEqual(successor.status, 'in_development')
        self.assertEqual(successor.funded_round, 1,
                         'Stage 3A: payment lands in the funding round.')

        # Round 2: still building. The lead time is the competitive content of
        # the decision; if it collapsed, a rival would have no window to react.
        self.advance_rd(2)
        successor.refresh_from_db()
        self.assertEqual(successor.status, 'in_development')

        # Round 3: ready.
        self.advance_rd(3)
        successor.refresh_from_db()
        self.assertEqual(successor.status, 'active')

        # Round 3: and now the only remaining route to a better product.
        result = product_rebase.rebase(self.product, successor, self.team, 3)
        self.assertEqual(result['from_platform'], self.old.id)
        self.assertEqual(result['to_platform'], successor.id)

        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, successor.id)

    def test_the_journey_leaves_earlier_rounds_where_they_were_scored(self):
        """The switch must not reach backwards into rounds already resolved."""
        before = {r: product_platform.platform_as_of_round(self.product, r).id
                  for r in (1, 2)}

        submission = self.submission_for(1)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen2,
            method='in_house', committed_cost=self.gen2.development_cost,
            platform_name='Successor', feature_levels={})
        for r in (1, 2, 3):
            self.advance_rd(r)
        successor = TeamPlatform.objects.get(team=self.team, name='Successor')
        product_rebase.rebase(self.product, successor, self.team, 3)

        after = {r: product_platform.platform_as_of_round(self.product, r).id
                 for r in (1, 2)}
        self.assertEqual(after, before)
        self.assertEqual(
            product_platform.platform_as_of_round(self.product, 3).id,
            successor.id)

    def test_the_switch_costs_the_team_exactly_once(self):
        """Stage 4's write-off is the price of the route Stage 3B left open."""
        RoundResultProductMarket.objects.create(
            game=self.game, round_number=2, team=self.team,
            team_product=self.product, market=self.market,
            units_produced=100, units_sold=D('0'), units_unsold=D('100'),
            unit_cost=D('50'))

        submission = self.submission_for(1)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen2,
            method='in_house', committed_cost=self.gen2.development_cost,
            platform_name='Successor', feature_levels={})
        for r in (1, 2, 3):
            self.advance_rd(r)
        successor = TeamPlatform.objects.get(team=self.team, name='Successor')

        result = product_rebase.rebase(self.product, successor, self.team, 3)
        self.assertEqual(D(result['write_off']), D('750.00'))
        self.assertEqual(
            product_rebase.write_offs_for_round(self.team, 3), D('750.00'))
        # No other round is charged for it.
        for r in (1, 2, 4):
            self.assertEqual(
                product_rebase.write_offs_for_round(self.team, r), D('0'))

    def test_a_stored_upgrade_still_cannot_reach_the_engine(self):
        """The retired route stays closed at the boundary, not only the API."""
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=1, defaults={'status': 'closed'})
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        DecisionRDInvestment.objects.create(
            submission=DecisionSubmission.objects.get(team=self.team,
                                                      round=rnd),
            team_platform=self.old, feature=self.feature,
            method='in_house', target_level=8, amount=D('500000'))

        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)

        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)
        self.assertEqual(
            TeamPlatformFeatureLevel.objects.get(
                team_platform=self.old, feature=self.feature).current_level,
            D('3'))

    def test_the_history_a_switch_writes_is_in_the_competitive_envelope(self):
        """Closure crosses the CRV2-01 boundary; the section must be enumerated."""
        from core.services.manifest_sections import OUTPUT_SECTIONS
        names = {s.name for s in OUTPUT_SECTIONS}
        self.assertIn('team_product_platform_history', names)

    def test_a_team_that_never_switches_is_unaffected(self):
        """The control: the new route is available, not compulsory."""
        steady = TeamProduct.objects.create(
            team=self.team, team_platform=self.old, name='Steady',
            positioning='mainstream', status='active', created_round=1)

        submission = self.submission_for(1)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen2,
            method='in_house', committed_cost=self.gen2.development_cost,
            platform_name='Successor', feature_levels={})
        for r in (1, 2, 3):
            self.advance_rd(r)
        successor = TeamPlatform.objects.get(team=self.team, name='Successor')
        product_rebase.rebase(self.product, successor, self.team, 3)

        steady.refresh_from_db()
        self.assertEqual(steady.team_platform_id, self.old.id)
        self.assertEqual(
            product_platform.platform_as_of_round(steady, 3).id, self.old.id)
        self.assertFalse(TeamProductPlatformHistory.objects.filter(
            team_product=steady).exists())
