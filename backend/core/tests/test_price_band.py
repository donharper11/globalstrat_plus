"""Stage 5 — the price band, and the receipt every adjustment leaves.

V2-041: in one open round the same product was priced at 99999 and then at 1,
both accepted, and 1.00 is what was stored. There was no anchor, no alert, no
adjustment and nothing written down. These tests are the rule the owner ruled
on (Ruling 2, 2026-08-31, narrowed 2026-09-12), stated as behaviour:

  * in band            -> used as entered, silently;
  * out of band        -> ALERTED while the round is open, the team's number
                          kept, and moved to the NEARER edge at the deadline;
  * blank              -> alerted, then priced at the band floor -- but ONLY
                          for a product the team is actually selling, i.e. one
                          that had a price in this market last round;
  * every adjustment   -> an audit event with actor `system` carrying the
                          submitted value, the applied value and the rule.

THE NARROWING IS LOAD-BEARING, so it has tests of its own. A product-market the
team never marketed is not "blank", it is absent. `bass_engine` builds its price
map from `DecisionMarketing` rows alone and gives a product with no row an
attractiveness of 0.0; inventing a floor-priced row would put an unsellable
product into the attractiveness denominator at a very competitive price, take
share from every rival, and book the lot as lost demand because `reported_sold`
is capped by available production. `NoRowIsInvented` is what keeps that out.
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
        self.rival = self.teams[1]
        self.scenario = self.game.scenario
        self._clear_config_cache()
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()

        self.generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        self.product = self.product_for(self.team, 'Aurora')
        self.round1 = Round.objects.create(
            game=self.game, round_number=1, status='open')

    def _clear_config_cache(self):
        engine_utils._config_cache.pop(self.scenario.id, None)

    def product_for(self, team, name):
        platform = TeamPlatform.objects.create(
            team=team, platform_generation=self.generation,
            name=f'{name} platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)
        product = TeamProduct.objects.create(
            team=team, team_platform=platform, name=name,
            positioning='mainstream', status='active', created_round=0)
        TeamProductMarket.objects.create(
            team_product=product, market=self.market, first_offered_round=0)
        return product

    def sold_at(self, round_number, price, team=None, product=None):
        """A published result row — what the product was selling at."""
        return RoundResultProductMarket.objects.create(
            game=self.game, round_number=round_number, team=team or self.team,
            team_product=product or self.product, market=self.market,
            retail_price=D(str(price)))

    def submission(self, team=None, round_obj=None):
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team or self.team, round=round_obj or self.round1,
            defaults={'status': 'draft'})
        return submission

    def priced(self, price, team=None, product=None, round_obj=None):
        """A marketing decision, priced or (price=None) deliberately blank."""
        return DecisionMarketing.objects.create(
            submission=self.submission(team, round_obj),
            team_product=product or self.product,
            market=self.market,
            retail_price=None if price is None else D(str(price)),
            promotion_budget=D('0'), campaign_focus_feature_ids=[],
            channel_digital_pct=D('0.34'), channel_traditional_pct=D('0.33'),
            channel_trade_pct=D('0.33'), distribution_strategy='mass_retail',
            distribution_investment=D('0'), sales_team_count=0,
            distribution_channel_detail={}, production_volume=100,
            production_source_market=self.market, demand_estimate=100)

    def band(self, round_number=1, team=None, product=None):
        return band_rules.price_band(
            self.scenario, team or self.team, product or self.product,
            self.market, round_number)

    def adjustments(self, team=None):
        return list(DecisionAuditEvent.objects.filter(
            game=self.game, team=team or self.team,
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
        self.sold_at(0, 400)
        band = self.band(round_number=1)
        self.assertEqual(band['anchor'], D('400.00'))
        self.assertEqual(band['anchor_source'], band_rules.ANCHOR_PREVIOUS_ROUND)
        self.assertEqual(band['anchor_round_number'], 0)

    def test_the_anchor_is_the_most_recent_earlier_round(self):
        self.sold_at(0, 400)
        self.sold_at(2, 800)
        self.assertEqual(self.band(round_number=3)['anchor'], D('800.00'))
        self.assertEqual(self.band(round_number=1)['anchor'], D('400.00'))

    def test_a_product_that_never_sold_here_anchors_to_the_authored_reference(self):
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
        self.assertNotIn('retail_price', alert)

    def test_the_alert_is_available_in_chinese(self):
        self.sold_at(0, 400)
        alert = band_rules.alert_for(
            D('99999'), self.band(), product_name='Aurora',
            market_name='Home', language='zh-CN')
        self.assertIn('$280', alert)
        self.assertIn('$520', alert)
        self.assertIn('本回合', alert)

    def test_a_blank_price_on_a_selling_product_is_warned_about_the_floor(self):
        self.sold_at(0, 400)
        alert = band_rules.alert_for(
            None, self.band(), product_name='Aurora', market_name='Home',
            language='en')
        self.assertIn('$280', alert)

    def test_a_blank_price_with_no_previous_price_asks_the_team_to_set_one(self):
        # No prior-round row, so the floor will NOT arrive. Promising one
        # would be worse than saying nothing.
        alert = band_rules.alert_for(
            None, self.band(), product_name='Aurora', market_name='Home',
            language='en')
        self.assertIn('Aurora', alert)
        self.assertNotIn('$294', alert)   # the reference-derived floor
        self.assertIn('unit price', alert)

    def test_the_teams_number_is_kept_while_the_round_is_open(self):
        self.sold_at(0, 400)
        decision = self.priced(99999)
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('99999.00'))

    def test_the_serializer_carries_the_band_alert_to_both_write_surfaces(self):
        from core.serializers.decisions import DecisionMarketingSerializer
        self.sold_at(0, 400)
        decision = self.priced(99999)
        warnings = DecisionMarketingSerializer(decision).data['warnings']
        self.assertTrue(any('$520' in w for w in warnings), warnings)


class BlankIsRepresentable(PriceBandFixture):
    """A team must be able to submit a row with the price left out.

    Before this, `retail_price` was NOT NULL and the serializer refused
    anything <= 0, so the blank branch of the ruling had nothing to act on --
    the state it describes could not be stored.
    """

    def test_a_marketing_row_can_be_stored_with_no_price(self):
        decision = self.priced(None)
        decision.refresh_from_db()
        self.assertIsNone(decision.retail_price)

    def test_the_serializer_accepts_an_absent_price(self):
        from core.serializers.decisions import DecisionMarketingSerializer
        serializer = DecisionMarketingSerializer(data={
            'team_product': self.product.id, 'market': self.market.id,
            'retail_price': None, 'promotion_budget': '0',
            'campaign_focus_feature_ids': [1],
            'channel_digital_pct': '0.34', 'channel_traditional_pct': '0.33',
            'channel_trade_pct': '0.33', 'distribution_strategy': 'mass_retail',
            'distribution_investment': '0', 'sales_team_count': 0,
            'production_volume': 10, 'production_source_market': self.market.id,
            'demand_estimate': 10,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get('retail_price'))

    def test_a_stated_price_of_zero_is_still_refused(self):
        from core.serializers.decisions import DecisionMarketingSerializer
        serializer = DecisionMarketingSerializer(data={
            'team_product': self.product.id, 'market': self.market.id,
            'retail_price': '0', 'promotion_budget': '0',
            'campaign_focus_feature_ids': [1],
            'channel_digital_pct': '0.34', 'channel_traditional_pct': '0.33',
            'channel_trade_pct': '0.33', 'distribution_strategy': 'mass_retail',
            'distribution_investment': '0', 'sales_team_count': 0,
            'production_volume': 10, 'production_source_market': self.market.id,
            'demand_estimate': 10,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('retail_price', serializer.errors)

    def test_a_negative_price_is_still_refused(self):
        from core.serializers.decisions import DecisionMarketingSerializer
        serializer = DecisionMarketingSerializer(data={
            'team_product': self.product.id, 'market': self.market.id,
            'retail_price': '-5', 'promotion_budget': '0',
            'campaign_focus_feature_ids': [1],
            'channel_digital_pct': '0.34', 'channel_traditional_pct': '0.33',
            'channel_trade_pct': '0.33', 'distribution_strategy': 'mass_retail',
            'distribution_investment': '0', 'sales_team_count': 0,
            'production_volume': 10, 'production_source_market': self.market.id,
            'demand_estimate': 10,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('retail_price', serializer.errors)


class NoRowIsInvented(PriceBandFixture):
    """The 2026-09-12 narrowing: the floor reaches only a selling product."""

    def test_an_unmarketed_product_market_gets_no_row_and_no_price(self):
        # The team sold here last round but submitted NO marketing decision
        # this round: no promotion, no channel, nothing. That is absence, not
        # a blank price, and the deadline must not invent a decision for it.
        self.sold_at(0, 400)
        self.submission()
        close_round(self.game.id, reason='deadline')
        self.assertFalse(
            DecisionMarketing.objects.filter(submission__team=self.team).exists(),
            'the deadline fabricated a marketing decision the team never made')
        self.assertEqual(self.adjustments(), [])

    def test_a_team_with_no_submission_at_all_is_left_alone(self):
        self.sold_at(0, 400)
        close_round(self.game.id, reason='deadline')
        self.assertFalse(
            DecisionMarketing.objects.filter(submission__team=self.team).exists())
        self.assertEqual(self.adjustments(), [])

    def test_the_floor_is_withheld_without_a_real_prior_round_price(self):
        # Anchored only to the authored positioning reference: enough to state
        # a legal range, deliberately not enough to price on the team's behalf.
        band = self.band()
        self.assertEqual(band['anchor_source'],
                         band_rules.ANCHOR_POSITIONING_REFERENCE)
        self.assertIsNotNone(band['min'])
        self.assertIsNone(band_rules.blank_price(band))

    def test_a_blank_on_a_never_sold_product_survives_the_deadline_unpriced(self):
        decision = self.priced(None)
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertIsNone(decision.retail_price)
        self.assertEqual(self.adjustments(), [])

    def test_an_unresolved_blank_is_refused_before_any_competitive_write(self):
        """The engine precondition, in V2-018's fail-closed shape.

        `bass_engine` calls float() on this value, so a surviving null must
        stop the round rather than raise halfway through one that has already
        mutated state.
        """
        from core.engine.advance_round import RoundNotReadyError, _run_phase_1
        # The realistic path: the product never sold here, so the deadline
        # locks the submission but deliberately cannot resolve the blank.
        self.priced(None)
        close_round(self.game.id, reason='deadline')
        with self.assertRaises(RoundNotReadyError) as caught:
            _run_phase_1(self.game.id)
        self.assertIn('no unit price', str(caught.exception))
        self.assertIn('Aurora', str(caught.exception))


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

    def test_a_blank_price_on_a_selling_product_is_filled_at_the_floor(self):
        # The owner's case: priced $400 last round, this round the number was
        # left out on a row the team is otherwise still submitting.
        self.sold_at(0, 400)
        decision = self.priced(None)
        close_round(self.game.id, reason='deadline')
        decision.refresh_from_db()
        self.assertEqual(decision.retail_price, D('280.00'))   # 400 - 30%

    def test_a_team_that_locked_early_is_still_subject_to_the_rule(self):
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
        self.assertIsNone(events[0].user_id)
        self.assertEqual(events[0].action, band_rules.ACTION_ADJUSTED)

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
        self.priced(None)
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


class AdjustmentsDoNotLeakAcrossTeams(PriceBandFixture):
    """`RoundResultsView` now reads DecisionAuditEvent. Prove the blast radius.

    The read-inventory change that made this endpoint a logged audit read is
    only safe if the payloads it serves belong to the team in the URL.
    """

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Enrollment, Section

        self.rival_product = self.product_for(self.rival, 'Rival')

        course = Course.objects.create(
            course_code=f'PB{id(self) % 100000}', course_name='Band',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.student = User.objects.create(
            username=f'band-student-{id(self)}', role='student',
            password_hash='x')
        self.rival_student = User.objects.create(
            username=f'band-rival-{id(self)}', role='student',
            password_hash='x')
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        Enrollment.objects.create(
            user_id=self.rival_student.user_id, section_id=section.section_id,
            team_id=self.rival.id, is_active=True)

        # Both teams mis-price, so both have something to leak.
        self.sold_at(0, 400)
        self.sold_at(0, 400, team=self.rival, product=self.rival_product)
        self.priced(99999)
        self.priced(99999, team=self.rival, product=self.rival_product)
        close_round(self.game.id, reason='deadline')

    def client_for(self, user):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def url(self, team):
        return (f'/api/games/{self.game.id}/teams/{team.id}'
                f'/results/round/1/')

    def test_both_teams_were_adjusted_so_the_test_can_actually_leak(self):
        self.assertEqual(len(self.adjustments()), 1)
        self.assertEqual(len(self.adjustments(team=self.rival)), 1)

    def test_a_team_sees_only_its_own_price_adjustments(self):
        response = self.client_for(self.student).get(self.url(self.team))
        self.assertEqual(response.status_code, 200, response.data)
        adjustments = response.data['price_adjustments']
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0]['product_name'], 'Aurora')
        self.assertNotIn('Rival', str(response.data))

    def test_a_team_with_no_adjustments_gets_an_empty_list_not_a_missing_key(self):
        # A third round nobody was adjusted in: the key must still be present,
        # so the client renders "nothing happened" rather than crashing on a
        # missing field.
        Round.objects.create(game=self.game, round_number=2, status='open')
        response = self.client_for(self.student).get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/results/round/2/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('price_adjustments', response.data)
        self.assertEqual(response.data['price_adjustments'], [])

    def test_a_rivals_student_cannot_read_this_teams_adjustment_payloads(self):
        """The disclosure question the read-inventory widening raises.

        `RoundResultsView` declares no permission class, so what actually
        stops a rival is `TeamScopeGuardMiddleware`, which refuses any view
        whose URL carries a `team_id` the caller is not enrolled against. The
        status code is asserted explicitly: a bare "the rival did not see
        'Aurora'" would also pass on a 500, which would prove nothing about
        the guard.
        """
        response = self.client_for(self.rival_student).get(self.url(self.team))
        self.assertEqual(
            response.status_code, 403,
            f'expected the team-scope guard to refuse, got '
            f'{response.status_code}: {getattr(response, "data", None)!r}')
        self.assertNotIn(
            'Aurora', str(getattr(response, 'data', '')),
            'a rival account read this team\'s price-adjustment payloads')

    def test_the_owning_teams_student_is_allowed_through_the_same_guard(self):
        """The control for the test above: the 403 is about team scope, not a
        blanket refusal that would make the leakage test vacuous."""
        response = self.client_for(self.student).get(self.url(self.team))
        self.assertEqual(response.status_code, 200, response.data)
