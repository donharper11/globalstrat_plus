"""Focused regressions for product retirement state.

**R18** (V2-070): a product retired `end_of_round` **sells through the round it
was retired in** and retires at that round's end. `immediate` stops sales at
once, as it always did.

Why the split matters, and why it is a competition rule rather than a tidy-up:
`costs.calculate_retirement_costs` recovers **50%** of unsold stock for
`end_of_round` against **25%** for `immediate`. Before R18 the two timings had
*identical* market timing -- `_process_product_retires` ran the same three
statements for both -- so `immediate` was strictly dominated: worse recovery,
no compensating benefit, and no reason for any team ever to choose it. Giving
`end_of_round` its own market timing is what turns the authored rates into a
real trade-off: sell through at 50%, or exit now at 25%.

Each test below fails against the pre-R18 engine. The load-bearing one is
`test_end_of_round_retirement_keeps_selling_in_its_round`: before the change
`_process_product_retires` deactivated every market row for both timings, so
the product was off sale the moment retirement was processed.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.engine.rd_processing import (
    _process_product_retires, apply_end_of_round_retirements,
)
from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionProductRetire
from core.models.scenario import PlatformGenerationDefinition
from core.models.team_state import TeamPlatform, TeamProduct, TeamProductMarket
from core.tests.test_operator_concurrency import build_minimal_game


class _RetirementContext:
    """The minimum the two retirement steps read.

    Built by hand rather than by resolving a round, so these tests isolate the
    retirement rule from every other engine input.
    """

    def __init__(self, game, teams, round_number):
        self.game = game
        self.scenario = game.scenario
        self.teams = list(teams)
        self.round_number = round_number
        self.log = []


class ProductRetirementBase(TestCase):

    def setUp(self):
        self.game, teams = build_minimal_game(f'product-retirement-{id(self)}')
        self.team = teams[0]
        self.market = self.team.home_market
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='locked')
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen', description='d',
            generation_order=1, unlock_round=0, development_cost=D('0'),
            license_cost=D('0'), development_rounds=0)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='Platform',
            status='active')
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='Product',
            positioning='mainstream', status='active', created_round=0)
        self.product_market = TeamProductMarket.objects.create(
            team_product=self.product, market=self.market,
            first_offered_round=0, is_active=True)

    def retire(self, timing):
        return DecisionProductRetire.objects.create(
            submission=self.submission, team_product=self.product,
            timing=timing)

    def context(self, round_number=1):
        return _RetirementContext(self.game, [self.team], round_number)

    def refresh(self):
        self.product.refresh_from_db()
        self.product_market.refresh_from_db()


class ImmediateRetirementTests(ProductRetirementBase):

    def test_immediate_retirement_stops_sales_at_once(self):
        """`immediate` keeps its behaviour exactly: off sale in this round."""
        self.retire('immediate')

        _process_product_retires(self.team, self.submission, current_round=1)

        self.refresh()
        self.assertEqual(self.product.status, 'retired')
        self.assertEqual(self.product.retired_round, 1)
        self.assertFalse(self.product_market.is_active)

    def test_immediate_retirement_is_not_deferred_to_the_end_of_the_round(self):
        """The deferred step must not be the only thing that retires it.

        If `immediate` were moved into the end-of-round step it would sell
        through the round too, and the two timings would collapse back into one
        again -- the defect from the other direction.
        """
        self.retire('immediate')

        _process_product_retires(self.team, self.submission, current_round=1)

        self.refresh()
        self.assertEqual(self.product.status, 'retired')
        self.assertFalse(self.product_market.is_active)


class EndOfRoundRetirementTests(ProductRetirementBase):

    def test_end_of_round_retirement_keeps_selling_in_its_round(self):
        """R18, the load-bearing property.

        Retirement is processed before adoption and revenue
        (`advance_round` runs `process_rd` at step 3, scoring from step 9). So
        if this step retired the product or deactivated its market rows, the
        product would be filtered out of demand and readiness -- both of which
        require `status='active'` and `is_active=True` -- and would sell
        nothing in the round the team chose to sell through.

        Before the change this assertion fails on every line: the pre-R18
        `end_of_round` branch set the product retired and deactivated every
        market row, byte-for-byte as `immediate` did.
        """
        self.retire('end_of_round')

        _process_product_retires(self.team, self.submission, current_round=1)

        self.refresh()
        self.assertEqual(self.product.status, 'active')
        self.assertIsNone(self.product.retired_round)
        self.assertTrue(self.product_market.is_active)

    def test_it_is_still_offered_to_the_demand_engine_in_its_retirement_round(self):
        """The same property, asserted through the code that decides sales.

        `preference_engine._get_team_products_in_market` is the query that
        turns an offered product into demand. Asserting the two flags is
        necessary; asserting that the demand engine still sees the product is
        what makes "it sells through the round" true rather than merely
        plausible.
        """
        from core.engine.preference_engine import _get_team_products_in_market

        self.retire('end_of_round')
        _process_product_retires(self.team, self.submission, current_round=1)

        offered = list(_get_team_products_in_market(self.team, self.market))
        self.assertEqual([p.id for p in offered], [self.product.id])

    def test_it_retires_once_the_round_has_resolved(self):
        """And the other half: at the round's end it is retired and off sale."""
        self.retire('end_of_round')
        _process_product_retires(self.team, self.submission, current_round=1)

        apply_end_of_round_retirements(self.context(round_number=1))

        self.refresh()
        self.assertEqual(self.product.status, 'retired')
        self.assertEqual(self.product.retired_round, 1)
        self.assertFalse(self.product_market.is_active)

    def test_it_is_gone_from_the_demand_engine_the_round_after(self):
        """The round after its retirement round, it is not offered at all."""
        from core.engine.preference_engine import _get_team_products_in_market

        self.retire('end_of_round')
        _process_product_retires(self.team, self.submission, current_round=1)
        apply_end_of_round_retirements(self.context(round_number=1))

        self.assertEqual(
            list(_get_team_products_in_market(self.team, self.market)), [])

    def test_the_deferred_step_ignores_an_immediate_retirement(self):
        """Only the `end_of_round` rows are deferred; nothing else is touched."""
        other_product = TeamProduct.objects.create(
            team=self.team, team_platform=self.product.team_platform,
            name='Kept', positioning='mainstream', status='active',
            created_round=0)
        kept_market = TeamProductMarket.objects.create(
            team_product=other_product, market=self.market,
            first_offered_round=0, is_active=True)
        self.retire('end_of_round')

        apply_end_of_round_retirements(self.context(round_number=1))

        other_product.refresh_from_db()
        kept_market.refresh_from_db()
        self.assertEqual(other_product.status, 'active')
        self.assertTrue(kept_market.is_active)

    def test_a_retirement_from_another_round_is_not_applied(self):
        """The deferred step retires this round's decisions, not every one."""
        self.retire('end_of_round')

        apply_end_of_round_retirements(self.context(round_number=2))

        self.refresh()
        self.assertEqual(self.product.status, 'active')
        self.assertTrue(self.product_market.is_active)


class RetirementRecoveryRateTests(ProductRetirementBase):
    """The authored rates stand, and each applies to its own branch.

    R18 leaves `retirement_endofround_recovery_pct` (0.50) and
    `retirement_immediate_recovery_pct` (0.25) as authored. What changes is
    that they are no longer the *only* difference between the two timings, so
    neither option dominates. These tests pin the rates to their branches so a
    later edit cannot quietly swap them.
    """

    UNSOLD = 100
    UNIT_COST = D('10.00')          # $1,000.00 of stranded inventory

    def seed_prior_inventory(self):
        from core.models.results_financials import RoundResultProductMarket
        RoundResultProductMarket.objects.create(
            game=self.game, team=self.team, team_product=self.product,
            market=self.market, round_number=0, units_produced=self.UNSOLD,
            units_sold=0, units_unsold=self.UNSOLD, retail_price=D('100.00'),
            unit_cost=self.UNIT_COST,
            total_cogs=self.UNIT_COST * self.UNSOLD)

    def recovery_for(self, timing):
        from core.engine.costs import calculate_retirement_costs
        self.seed_prior_inventory()
        self.retire(timing)
        context = self.context(round_number=1)
        calculate_retirement_costs(context)
        return (context.retirement_revenue.get(self.team.id, D('0')),
                context.retirement_costs.get(self.team.id, D('0')))

    def test_end_of_round_recovers_half_the_stranded_inventory(self):
        recovery, write_off = self.recovery_for('end_of_round')
        self.assertEqual(write_off, D('1000.00'))
        self.assertEqual(recovery, D('500.00'))

    def test_immediate_recovers_a_quarter_of_it(self):
        recovery, write_off = self.recovery_for('immediate')
        self.assertEqual(write_off, D('1000.00'))
        self.assertEqual(recovery, D('250.00'))

    def test_end_of_round_recovers_strictly_more_than_immediate(self):
        """The trade-off R18 creates, stated as the property it has to hold.

        Selling through is worth more per stranded unit than exiting now. That
        is the compensating benefit `immediate` did not have while the two
        timings shared one market timing -- and the reason `immediate` is now a
        real choice (exit this round) rather than a dominated one.
        """
        end_of_round, _ = self.recovery_for('end_of_round')
        DecisionProductRetire.objects.all().delete()
        from core.models.results_financials import RoundResultProductMarket
        RoundResultProductMarket.objects.all().delete()
        self.product.refresh_from_db()
        immediate, _ = self.recovery_for('immediate')
        self.assertGreater(end_of_round, immediate)
