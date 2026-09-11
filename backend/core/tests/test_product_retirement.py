"""Focused regressions for product retirement state."""
from decimal import Decimal as D

from django.test import TestCase

from core.engine.rd_processing import _process_product_retires
from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionProductRetire
from core.models.scenario import PlatformGenerationDefinition
from core.models.team_state import TeamPlatform, TeamProduct, TeamProductMarket
from core.tests.test_operator_concurrency import build_minimal_game


class ProductRetirementTests(TestCase):

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

    def test_end_of_round_retirement_deactivates_product_market(self):
        """An end-of-round retirement must not leave the product on sale."""
        DecisionProductRetire.objects.create(
            submission=self.submission, team_product=self.product,
            timing='end_of_round')

        _process_product_retires(self.team, self.submission, current_round=1)

        self.product.refresh_from_db()
        self.product_market.refresh_from_db()
        self.assertEqual(self.product.status, 'retired')
        self.assertEqual(self.product.retired_round, 1)
        self.assertFalse(self.product_market.is_active)
