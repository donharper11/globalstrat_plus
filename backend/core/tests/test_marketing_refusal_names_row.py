"""W-CE-04: a refused marketing row is named.

The marketing save replaces the whole section in one request, and every
row is judged before any is stored, so one row without a campaign focus
made the whole page's save fail -- by contract, and rightly: a partial
replace would delete the rows it did not reach. But the refusal said only
"Choose one to three campaign focus features." A team with two products
saw that sentence on the tab of a product whose focus WAS set.

The contract stays: nothing is stored unless every row is accepted. The
refusal now names the product and the market of the row it objects to, in
the reader's language, in front of the server's own sentence.
"""
from decimal import Decimal as D

from core.models.decisions import DecisionMarketing
from core.models.scenario import PlatformGenerationDefinition
from core.models.team_state import (TeamPlatform, TeamProduct,
                                    TeamProductMarket)
from core.tests.test_committed_spend_one_calculator import CommittedSpendBase


class MarketingRefusalNamesRowTests(CommittedSpendBase):

    def setUp(self):
        super().setUp()
        self.declare(marketing=D('2500000'))
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation,
            name='Atlas', status='active', development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0)
        self.one, self.lite = (
            TeamProduct.objects.create(
                team=self.team, team_platform=platform, name=name,
                positioning='mainstream', status='active', created_round=0)
            for name in ('Nexus One', 'Nexus Lite'))
        for product in (self.one, self.lite):
            TeamProductMarket.objects.create(
                team_product=product, market=self.home, first_offered_round=0)
        # The market has a Chinese name, as scenario markets do.
        self.home.name_zh = '本土市场'
        self.home.save(update_fields=['name_zh'])

    def row(self, product, **overrides):
        data = {
            'team_product': product.id, 'market': self.home.id,
            'retail_price': '400', 'promotion_budget': '0',
            'campaign_focus_feature_ids': [], 'channel_digital_pct': '0.34',
            'channel_traditional_pct': '0.33', 'channel_trade_pct': '0.33',
            'distribution_strategy': 'mass_retail',
            'distribution_investment': '0', 'sales_team_count': 0,
            'distribution_channel_detail': {}, 'production_volume': 0,
            'production_source_market': self.home.id, 'demand_estimate': 0,
        }
        data.update(overrides)
        return data

    def save(self, rows, language='en'):
        return self.client.patch(
            self.url('marketing'), {'marketing_decisions': rows},
            format='json', HTTP_ACCEPT_LANGUAGE=language)

    def stored(self):
        return list(DecisionMarketing.objects.filter(
            submission=self.submission).order_by('id')
            .values_list('team_product__name', 'retail_price'))

    def test_the_refusal_names_the_product_and_the_market(self):
        good = self.row(self.one)
        bad = self.row(self.lite, promotion_budget='250000')   # no focus

        response = self.save([good, bad])

        self.assertEqual(response.status_code, 400, response.data)
        text = str(response.data)
        self.assertIn('Nexus Lite in Home: Choose one to three campaign '
                      'focus features.', text)
        self.assertNotIn('Nexus One', text)

    def test_in_chinese_the_market_is_named_in_chinese(self):
        bad = self.row(self.lite, promotion_budget='250000')

        response = self.save([self.row(self.one), bad], language='zh-CN')

        self.assertEqual(response.status_code, 400, response.data)
        text = str(response.data)
        self.assertIn('Nexus Lite（本土市场）：请选择一到三个营销活动重点功能。', text)
        self.assertNotIn('Home', text)

    def test_nothing_is_stored_and_what_was_stored_stays(self):
        """The contract: all rows or none, and a refusal changes nothing."""
        first = self.save([self.row(self.one, retail_price='450')])
        self.assertEqual(first.status_code, 200, first.data)
        before = self.stored()
        self.assertEqual(before, [('Nexus One', D('450.00'))])

        response = self.save([self.row(self.one, retail_price='460'),
                              self.row(self.lite, promotion_budget='250000')])

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.stored(), before)

    def test_every_valid_row_is_stored_when_none_is_refused(self):
        response = self.save([
            self.row(self.one, retail_price='450'),
            self.row(self.lite, promotion_budget='250000',
                     campaign_focus_feature_ids=[1]),
        ])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.stored(),
            [('Nexus One', D('450.00')), ('Nexus Lite', D('400.00'))])
