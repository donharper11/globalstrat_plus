"""The marketing row a pricing screen can actually save.

GSP-CRV2-13 finding F7: `MarketingPage` builds every fresh row with
`campaign_focus_feature_ids: []`, and the serializer demanded one to three
features on every row, so the screen's own default payload was refused with
400. Because the PATCH validates every item before writing any of them, one
unprimed row took every other row in the same request down with it -- a team
could leave the screen believing a whole round's pricing was saved when the
server held nothing at all.

The contract change these tests pin is narrow and follows from the rulings
rather than from the screen: R15 and R24 require a marketing row to be storable
purely to carry a price -- including a blank one, which the deadline then fills
at the band floor or marks not-for-sale. A row that cannot be stored cannot
carry a blank price. A campaign focus, meanwhile, is a real decision only when
there is a campaign to aim, so the "choose one to three" rule now applies where
promotion is actually funded.
"""
from decimal import Decimal as D

from core.serializers.decisions import DecisionMarketingSerializer
from core.tests.test_price_band import PriceBandFixture


class MarketingDefaultRowSerializer(PriceBandFixture):
    """The payload shapes the pricing surface actually sends."""

    def row(self, **overrides):
        """Exactly what MarketingPage builds for a fresh row."""
        data = {
            'team_product': self.product.id,
            'market': self.market.id,
            'retail_price': D('400'),
            'promotion_budget': D('0'),
            'campaign_focus_feature_ids': [],
            'channel_digital_pct': D('0.34'),
            'channel_traditional_pct': D('0.33'),
            'channel_trade_pct': D('0.33'),
            'distribution_strategy': 'mass_retail',
            'distribution_investment': D('0'),
            'sales_team_count': 0,
            'distribution_channel_detail': {},
            'production_volume': 0,
            'production_source_market': self.market.id,
            'demand_estimate': 0,
        }
        data.update(overrides)
        return data

    def test_the_screens_own_default_row_is_accepted(self):
        # F7. This exact payload returned 400 on both
        # campaign_focus_feature_ids and production_source_market.
        serializer = DecisionMarketingSerializer(data=self.row())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_a_row_carrying_only_a_blank_price_is_accepted(self):
        # R15/R24: "submitted blank" has to be representable, or the floor and
        # not-for-sale branches have nothing to act on.
        serializer = DecisionMarketingSerializer(
            data=self.row(retail_price=None))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_funded_promotion_still_requires_a_campaign_focus(self):
        # The rule is kept where it means something: money is being spent on a
        # campaign, so the team must say what the campaign is about.
        serializer = DecisionMarketingSerializer(
            data=self.row(promotion_budget=D('250000')))
        self.assertFalse(serializer.is_valid())
        self.assertIn('campaign_focus_feature_ids', serializer.errors)

    def test_funded_promotion_with_a_campaign_focus_is_accepted(self):
        serializer = DecisionMarketingSerializer(
            data=self.row(promotion_budget=D('250000'),
                          campaign_focus_feature_ids=[1]))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_more_than_three_focus_features_is_still_refused(self):
        serializer = DecisionMarketingSerializer(
            data=self.row(campaign_focus_feature_ids=[1, 2, 3, 4]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('campaign_focus_feature_ids', serializer.errors)

    def test_a_stated_price_of_zero_is_still_refused(self):
        # Unchanged: zero is a decision to give the product away, not a blank.
        serializer = DecisionMarketingSerializer(
            data=self.row(retail_price=D('0')))
        self.assertFalse(serializer.is_valid())
        self.assertIn('retail_price', serializer.errors)

    def test_the_refusal_never_names_a_storage_field(self):
        serializer = DecisionMarketingSerializer(
            data=self.row(promotion_budget=D('250000')))
        serializer.is_valid()
        sentence = str(serializer.errors['campaign_focus_feature_ids'][0])
        self.assertNotIn('campaign_focus_feature_ids', sentence)
        self.assertIn('campaign focus', sentence.lower())
