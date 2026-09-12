"""Stage 5 — the price band, and the receipt every adjustment leaves.

V2-041: in one open round the same product was priced at 99999 and then at 1,
both accepted, and 1.00 is what was stored. There was no anchor, no alert, no
adjustment and nothing written down. These tests are the rule the owner ruled
on (Ruling 2, 2026-08-31), stated as behaviour:

  * in band            -> used as entered, silently;
  * out of band        -> ALERTED while the round is open, the team's number
                          kept, and moved to the NEARER edge at the deadline;
  * blank              -> alerted, then priced at the band floor;
  * every adjustment   -> an audit event with actor `system` carrying the
                          submitted value, the applied value and the rule.

Every test here fails on the baseline: `core.services.price_band` does not
exist there and `close_round` adjusts nothing.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.engine import utils as engine_utils
from core.engine.advance_round import close_round
from core.models import DecisionAuditEvent, DecisionSubmission, Round
from core.models.decisions import DecisionMarketing
from core.models.results_financials import RoundResultProductMarket
from core.models.scenario import (MarketDefinition,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.team_state import TeamPlatform, TeamProduct, TeamProductMarket
from core.services import price_band as band_rules
from core.tests.test_operator_concurrency import build_minimal_game


class PriceBandFixture(TestCase):
    """One team, one mainstream product, one market, one open round."""

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'band-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario
        self._clear_config_cache()
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()

        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='Platform',
            status='active', development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0)
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=self.platform, name='Aurora',
            positioning='mainstream', status='active', created_round=0)
        self.product_market = TeamProductMarket.objects.create(
            team_product=self.product, market=self.market,
            first_offered_round=0)
        self.round1 = Round.objects.create(
            game=self.game, round_number=1, status='open')

    def _clear_config_cache(self):
        engine_utils._config_cache.pop(self.scenario.id, None)

    def sold_at(self, round_number, price):
        """A published result row — what the product was selling at."""
        return RoundResultProductMarket.objects.create(
            game=self.game, round_number=round_number, team=self.team,
            team_product=self.product, market=self.market,
            retail_price=D(str(price)))

    def submission(self, round_obj=None):
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=round_obj or self.round1,
            defaults={'status': 'draft'})
        return submission

    def priced(self, price, round_obj=None):
        """A marketing decision carrying a price, as a team would submit it."""
        return DecisionMarketing.objects.create(
            submission=self.submission(round_obj), team_product=self.product,
            market=self.market, retail_price=D(str(price)),
            promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('0.34'), channel_traditional_pct=D('0.33'),
            channel_trade_pct=D('0.33'), distribution_strategy='mass_retail',
            distribution_investment=D('0'), sales_team_count=0,
            distribution_channel_detail={}, production_volume=100,
            production_source_market=self.market, demand_estimate=100)

    def band(self, round_number=1):
        return band_rules.price_band(
            self.scenario, self.team, self.product, self.market, round_number)

    def adjustments(self):
        return list(DecisionAuditEvent.objects.filter(
            game=self.game, team=self.team,
            action__in=(band_rules.ACTION_ADJUSTED,
                        band_rules.ACTION_BLANK_DEFAULTED),
        ).order_by('id'))


class BandWidthIsAuthored(PriceBandFixture):
    """The band is a scenario parameter, not a constant in the code."""

    def test_the_default_band_is_thirty_percent_of_last_round(self):
        self.sold_at(0, 400)
        band = self.band()
        self.assertEqual(band['min'], D('280.00'))
        self.assertEqual(band['max'], D('520.00'))
        self.assertEqual(band['band_pct'], 0.30)

    def test_the_width_comes_from_the_scenario_not_a_constant(self):
        self.sold_at(0, 400)
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='price_band_pct',
            config_value='0.10', description='Stage 5')
        self._clear_config_cache()
        band = self.band()
        # Moves with the authored value, and is not the 0.30 default.
        self.assertEqual(band['min'], D('360.00'))
        self.assertEqual(band['max'], D('440.00'))
        self.assertNotEqual(band['band_pct'],
                            band_rules.PRICE_BAND_PCT_DEFAULT)

    def test_an_authored_zero_means_no_band_rather_than_an_inverted_one(self):
        self.sold_at(0, 400)
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='price_band_pct',
            config_value='0', description='Stage 5')
        self._clear_config_cache()
        self.assertIsNone(self.band()['min'])


class TheAnchor(PriceBandFixture):
    """What the band is measured from, round 1 included."""

    def test_round_one_anchors_to_the_authored_starting_price(self):
        # bootstrap_round_zero writes exactly this row from the authored
        # FirmStarterProduct.base_price, so round 1 is not a special case: it
        # takes the same lookup every later round takes.
        self.sold_at(0, 400)
        band = self.band(round_number=1)
        self.assertEqual(band['anchor'], D('400.00'))
        self.assertEqual(band['anchor_source'], band_rules.ANCHOR_PREVIOUS_ROUND)
        self.assertEqual(band['anchor_round_number'], 0)

    def test_the_anchor_is_the_most_recent_earlier_round(self):
        self.sold_at(0, 400)
        self.sold_at(2, 800)
        self.assertEqual(self.band(round_number=3)['anchor'], D('800.00'))
        # Pricing round 1 still sees only round 0 — a later round cannot
        # reach back and re-anchor a round that has already been priced.
        self.assertEqual(self.band(round_number=1)['anchor'], D('400.00'))

    def test_a_product_that_never_sold_here_anchors_to_the_authored_reference(self):
        # No result row at all: a newly launched product, or a market just
        # entered. RULES-OWNER QUESTION — the default chosen is the authored
        # per-tier reference price, so the exploit V2-041 names (launch a
        # product, price it at 1) is closed rather than left open.
        band = self.band()
        self.assertEqual(band['anchor'], D('420.00'))  # reference_price_mainstream
        self.assertEqual(band['anchor_source'],
                         band_rules.ANCHOR_POSITIONING_REFERENCE)

    def test_with_nothing_authored_and_nothing_sold_there_is_no_band(self):
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key__startswith='reference_price_').delete()
        self._clear_config_cache()
        band = self.band()
        self.assertIsNone(band['min'])
        self.assertEqual(band['anchor_source'], band_rules.ANCHOR_NONE)


class WhileTheRoundIsOpen(PriceBandFixture):
    """Alert, and keep the team's number."""

    def test_an_in_band_price_says_nothing(self):
        self.sold_at(0, 400)
        self.assertIsNone(band_rules.alert_for(
            D('450'), self.band(), product_name='Aurora',
            market_name='Home', language='en'))

    def test_an_out_of_band_price_alerts_and_names_the_legal_range(self):
        self.sold_at(0, 400)
        alert = band_rules.alert_for(
            D('99999'), self.band(), product_name='Aurora',
            market_name='Home', language='en')
        self.assertIsNotNone(alert)
        self.assertIn('$280', alert)
        self.assertIn('$520', alert)
        self.assertIn('Aurora', alert)
        # Names the business object, never the column.
        self.assertNotIn('retail_price', alert)

    def test_the_alert_is_available_in_chinese(self):
        self.sold_at(0, 400)
        alert = band_rules.alert_for(
            D('99999'), self.band(), product_name='Aurora',
            market_name='Home', language='zh-CN')
        self.assertIn('$280', alert)
        self.assertIn('$520', alert)
        self.assertIn('本回合', alert)

    def test_a_blank_price_is_warned_about_the_floor(self):
        self.sold_at(0, 400)
        alert = band_rules.alert_for(
            None, self.band(), product_name='Aurora', market_name='Home',
            language='en')
        self.assertIn('$280', alert)

    def test_the_teams_number_is_kept_while_the_round_is_open(self):
        self.sold_at(0, 400)
        decision = self.priced(99999)
        decision.refresh_from_db()
        # Accepted and stored as entered. The deadline is the only place the
        # stored value changes.
        self.assertEqual(decision.retail_price, D('99999.00'))

    def test_the_serializer_carries_the_band_alert_to_both_write_surfaces(self):
        from core.serializers.decisions import DecisionMarketingSerializer
        self.sold_at(0, 400)
        decision = self.priced(99999)
        warnings = DecisionMarketingSerializer(decision).data['warnings']
        self.assertTrue(any('$520' in w for w in warnings), warnings)


class AtTheDeadline(PriceBandFixture):
    """The stored price becomes a legal one."""

    def test_a_price_above_the_band_moves_to_the_upper_edge(self):
        self.sold_at(0, 400)
        decision = self.priced(99999)
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('520.00'))

    def test_a_price_below_the_band_moves_to_the_lower_edge(self):
        self.sold_at(0, 400)
        decision = self.priced(1)
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('280.00'))

    def test_the_nearer_edge_is_chosen_not_always_the_floor(self):
        self.sold_at(0, 400)
        decision = self.priced(600)          # above by 80, below by 320
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('520.00'))

    def test_an_in_band_price_is_used_as_entered_and_audits_nothing(self):
        self.sold_at(0, 400)
        decision = self.priced(450)
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('450.00'))
        self.assertEqual(self.adjustments(), [])

    def test_a_blank_product_market_is_priced_at_the_floor(self):
        self.sold_at(0, 400)
        self.submission()                    # a submission, but no price row
        close_round(self.game.id, reason='deadline')
        decision = DecisionMarketing.objects.get(
            submission__team=self.team, team_product=self.product,
            market=self.market)
        self.assertEqual(decision.retail_price, D('280.00'))  # 400 - 30%

    def test_a_team_that_locked_early_is_still_subject_to_the_rule(self):
        # _lock_all_submissions skips an already-locked submission, so an
        # adjustment folded into that loop would exempt exactly the teams
        # that submitted on time.
        self.sold_at(0, 400)
        decision = self.priced(99999)
        submission = self.submission()
        submission.status = 'locked'
        submission.save(update_fields=['status'])
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('520.00'))


class TheAuditReceipt(PriceBandFixture):
    """What makes the substitution answerable instead of a silent clamp."""

    def test_an_adjustment_is_recorded_with_actor_system(self):
        self.sold_at(0, 400)
        self.priced(99999)
        close_round(self.game.id, reason='deadline')
        events = self.adjustments()
        self.assertEqual(len(events), 1)
        event = events[0]
        # `user is None` is exactly what the instructor drill-down renders as
        # actor 'system' (results_api.InstructorTeamDecisionsView).
        self.assertIsNone(event.user_id)
        self.assertEqual(event.action, band_rules.ACTION_ADJUSTED)

    def test_the_payload_carries_the_submitted_value_the_applied_value_and_the_rule(self):
        self.sold_at(0, 400)
        self.priced(99999)
        close_round(self.game.id, reason='deadline')
        payload = self.adjustments()[0].payload
        self.assertEqual(payload['submitted_price'], '99999.00')
        self.assertEqual(payload['applied_price'], '520.00')
        self.assertEqual(payload['rule'], band_rules.RULE_OUT_OF_BAND)
        self.assertEqual(payload['band_min'], '280.00')
        self.assertEqual(payload['band_max'], '520.00')
        self.assertEqual(payload['anchor_price'], '400.00')
        self.assertEqual(payload['product_name'], 'Aurora')

    def test_a_blank_default_is_recorded_under_its_own_rule(self):
        self.sold_at(0, 400)
        self.submission()
        close_round(self.game.id, reason='deadline')
        events = self.adjustments()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, band_rules.ACTION_BLANK_DEFAULTED)
        self.assertIsNone(events[0].payload['submitted_price'])
        self.assertEqual(events[0].payload['rule'], band_rules.RULE_BLANK)

    def test_the_adjustment_reads_back_to_the_team_in_both_languages(self):
        self.sold_at(0, 400)
        self.priced(99999)
        close_round(self.game.id, reason='deadline')
        payload = self.adjustments()[0].payload
        english = band_rules.adjustment_notice(payload, 'en')
        chinese = band_rules.adjustment_notice(payload, 'zh-CN')
        for notice in (english, chinese):
            self.assertIn('$99,999', notice)
            self.assertIn('$520', notice)
            self.assertIn('Aurora', notice)
        self.assertNotEqual(english, chinese)

    def test_the_audit_row_cannot_be_edited_afterwards(self):
        self.sold_at(0, 400)
        self.priced(99999)
        close_round(self.game.id, reason='deadline')
        event = self.adjustments()[0]
        event.payload = {'tampered': True}
        with self.assertRaises(ValueError):
            event.save()


class PublishedRoundsAreNotRewritten(PriceBandFixture):
    """A round that has already closed or been scored is left alone."""

    def test_a_processed_round_is_not_repriced(self):
        self.sold_at(0, 400)
        decision = self.priced(99999)
        self.round1.status = 'processed'
        self.round1.save(update_fields=['status'])
        result = close_round(self.game.id, reason='deadline')
        self.assertFalse(result['changed'])
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('99999.00'))
        self.assertEqual(self.adjustments(), [])

    def test_closing_twice_adjusts_once(self):
        self.sold_at(0, 400)
        decision = self.priced(99999)
        close_round(self.game.id, reason='deadline')
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('520.00'))
        self.assertEqual(len(self.adjustments()), 1)
