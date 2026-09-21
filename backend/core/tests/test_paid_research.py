"""Market research is a paid mechanic.

Research reports were free and unlimited, and `research_expense` was a P&L line
the engine hardcoded to zero. These tests are written against the properties
the mechanic has to hold, one test each.

The load-bearing one is `test_a_purchase_appears_in_both_calculators`: a charge
that reached only the funding rule, or only the engine, is the divergence the
one-calculator rule exists to prevent. It asserts the two agree by running both.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.engine.utils import _config_cache
from core.models import (DecisionSubmission, Enrollment, Game, Round, Scenario,
                         Team, User)
from core.models.competition_audit import DecisionAuditEvent
from core.models.course import Course, Section
from core.models.research import DecisionResearchPurchase
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  ScenarioConfig)
from core.services import research_catalogue
from core.services.funding_need import decision_outlays

OPENING_CASH = D('1000000')
PRICE = D('50000')


class PaidResearchBase(TestCase):
    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)

        owner = DjangoUser.objects.create(username=f'owner-pr-{id(self)}')
        self.user = User.objects.create(
            username=f'student-pr-{id(self)}', role='student', password_hash='x')
        self.scenario = Scenario.objects.create(
            name=f'Paid research {id(self)}', industry_label='T',
            description='d', starting_cash=OPENING_CASH, num_rounds=4)
        for key in research_catalogue.PRICE_CONFIG_KEYS.values():
            ScenarioConfig.objects.create(
                scenario=self.scenario, config_key=key,
                config_value=str(PRICE), description=key)
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=OPENING_CASH,
            starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Paid research game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)

        section = Section.objects.create(
            course_id=Course.objects.create(
                course_code=f'PR{id(self) % 100000}', course_name='Research',
                instructor_id=None, is_active=True).course_id,
            section_code='S1', section_name='S1', max_teams=4,
            team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True, enrolled_at=timezone.now())

        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.user)}')

    def buy_url(self, report_type):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/reports/{report_type}/purchase/')

    def read_url(self, report_type, query=''):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/reports/{report_type}/{query}')

    def submission(self):
        return DecisionSubmission.objects.filter(
            team=self.team, round=self.round).first()


class PurchaseChargeTests(PaidResearchBase):
    def test_a_purchase_appears_in_both_calculators(self):
        """The funding rule and the engine must charge the same outlay."""
        from core.engine.costs import calculate_operating_expenses

        response = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        submission = self.submission()
        outlays = decision_outlays(self.scenario, self.team, submission, 1)
        self.assertEqual(outlays['research'], PRICE)

        context = _Context(self.scenario, self.game, self.team, 1)
        # Raises AssertionError if the two sides disagree; that guard is the
        # point of the test as much as the equality below.
        calculate_operating_expenses(context)
        self.assertEqual(context.opex[self.team.id]['research_expense'], PRICE)

    def test_a_purchase_is_charged_exactly_once(self):
        self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(
            DecisionResearchPurchase.objects.filter(
                submission=self.submission()).count(), 1)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)

    def test_reopening_a_bought_report_charges_nothing(self):
        first = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(first.status_code, 201)

        # Re-reading it, then asking to buy it again, must not charge twice.
        self.client.get(self.read_url('products'))
        second = self.client.post(self.buy_url('products'), {}, format='json')

        self.assertEqual(second.status_code, 200)
        self.assertIs(second.data['charged'], False)
        self.assertEqual(
            DecisionResearchPurchase.objects.filter(
                submission=self.submission()).count(), 1)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)

    def test_a_market_scoped_report_is_bought_per_market(self):
        other = MarketDefinition.objects.create(
            scenario=self.scenario, name='Away', code='AW', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        self.client.post(self.buy_url('segments'), {'market': 'HM'},
                         format='json')
        again = self.client.post(self.buy_url('segments'), {'market': 'HM'},
                                 format='json')
        self.assertIs(again.data['charged'], False)

        second_market = self.client.post(
            self.buy_url('segments'), {'market': other.code}, format='json')
        self.assertEqual(second_market.status_code, 201)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE * 2)


class AffordabilityTests(PaidResearchBase):
    def test_an_unaffordable_purchase_is_refused_and_delivers_nothing(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.status_code, 400)
        # Nothing was written: no purchase row, and the report stays locked.
        self.assertFalse(DecisionResearchPurchase.objects.exists())
        report = self.client.get(self.read_url('products'))
        self.assertIs(report.data['purchased'], False)

    def test_the_refusal_is_in_business_language(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        detail = self.client.post(
            self.buy_url('products'), {}, format='json').data['detail']

        self.assertIn('$50,000.00', detail)
        self.assertIn('$1,000.00', detail)
        for leak in ('research_purchases', 'cash_on_hand', 'within_cash',
                     'DecisionResearchPurchase', 'report_type'):
            self.assertNotIn(leak, detail)

    def test_the_refusal_is_localised(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        detail = self.client.post(
            self.buy_url('products'), {}, format='json',
            HTTP_ACCEPT_LANGUAGE='zh-CN').data['detail']

        self.assertIn('承诺支出', detail)
        self.assertIn('可用现金', detail)
        self.assertIn('$50,000.00', detail)
        # The English template must not leak through the Chinese one.
        self.assertNotIn('available cash', detail)


class AuthoredPriceTests(PaidResearchBase):
    def test_the_price_comes_from_the_scenario_not_a_constant(self):
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_report_price_products',
        ).update(config_value='12345')
        _config_cache.clear()

        self.assertEqual(
            research_catalogue.price_for(self.scenario, 'products'),
            D('12345'))

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.data['price'], '12345')
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), D('12345'))
        self.assertNotEqual(
            D('12345'), research_catalogue.DEFAULT_RESEARCH_PRICE,
            'the test would prove nothing if it used the fallback figure')

    def test_the_price_is_shown_before_buying(self):
        locked = self.client.get(self.read_url('products'))

        self.assertIs(locked.data['purchased'], False)
        self.assertEqual(locked.data['price'], str(PRICE))
        self.assertEqual(locked.data['products'], [])

    def test_the_charged_price_is_frozen_against_later_calibration(self):
        self.client.post(self.buy_url('products'), {}, format='json')
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_report_price_products',
        ).update(config_value='999999')
        _config_cache.clear()

        # An already-resolved round must not be restated by a price change.
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)


class AnalystQueryBase(PaidResearchBase):
    """A scenario with the analyst switched on, a price and a quota of 3."""
    ANALYST_PRICE = D('12345')

    def setUp(self):
        super().setUp()
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_analyst_query_price',
        ).update(config_value=str(self.ANALYST_PRICE))
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='rag_enabled',
            config_value='true', description='rag')
        ScenarioConfig.objects.create(
            scenario=self.scenario,
            config_key='max_research_queries_per_round',
            config_value='3', description='quota')
        _config_cache.clear()

    def queries_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/queries/')

    def ask_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/query/')


class AnalystQueryPriceTests(AnalystQueryBase):
    """V2-094: the analyst query is the one purchase whose price no payload named.

    The reports endpoint names a price per *report type*, and the analyst tab
    never fetches a report, so a team was charged per question without having
    been shown the figure. The tab already loads `research/queries/`; the
    price is published there, from `price_for()` -- the same calculator the
    charge reads -- so the figure shown and the figure charged cannot differ.
    """

    def test_the_analyst_price_is_published_before_any_question_is_asked(self):
        response = self.client.get(self.queries_url())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['queries'], [])
        offer = response.data['analyst_query']
        self.assertEqual(offer['price'], str(self.ANALYST_PRICE))
        self.assertNotEqual(
            self.ANALYST_PRICE, research_catalogue.DEFAULT_RESEARCH_PRICE,
            'the test would prove nothing if it used the fallback figure')
        # Reading the price is not a purchase.
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def test_the_quota_published_is_the_quota_enforced(self):
        """The page multiplied a hardcoded 5 by nothing; the rule is authored."""
        offer = self.client.get(self.queries_url()).data['analyst_query']

        self.assertEqual(offer['max_queries_per_round'], 3)
        self.assertEqual(offer['queries_remaining'], 3)

    def test_the_price_shown_is_the_price_charged(self):
        from unittest import mock

        shown = self.client.get(self.queries_url()).data['analyst_query']['price']
        with mock.patch('core.rag.embeddings.get_embedding',
                        return_value=[0.0]), \
                mock.patch('core.rag.embeddings.translate_query_if_needed',
                           side_effect=lambda text, language: text), \
                mock.patch('core.rag.client.search_articles',
                           return_value=[{'title': 'Home market sizing', 'tags': ['market']}]), \
                mock.patch('core.rag.views.synthesize_research_brief',
                           return_value='An answer.'):
            asked = self.client.post(
                self.ask_url(), {'query': 'How large is the home market?'},
                format='json')

        self.assertEqual(asked.status_code, 200, asked.data)
        charged = DecisionResearchPurchase.objects.get(
            submission=self.submission(),
            report_type=research_catalogue.ANALYST_QUERY)
        self.assertEqual(str(charged.price.normalize()),
                         str(D(shown).normalize()))
        after = self.client.get(self.queries_url()).data['analyst_query']
        self.assertEqual(after['queries_remaining'], 2)


class AnalystRefusalTests(AnalystQueryBase):
    """The two refusals a student can meet after pressing Ask.

    Both were English-only, and the 503 interpolated `str(exception)` into the
    sentence a student reads -- a host name, a connection string, whatever the
    embedding or vector client happened to raise. The wording now comes from
    `participant_messages` in the request's language, the exception goes to the
    server log, and neither refusal leaves a charge behind.
    """
    SECRET = 'qdrant http://10.9.8.7:6333 refused api_key=sk-not-for-students'

    def ask(self, language=None):
        headers = {'HTTP_ACCEPT_LANGUAGE': language} if language else {}
        # R43: the team's language governs what the analyst route says.
        Enrollment.objects.filter(team_id=self.team.id).update(
            language=language or 'en')
        return self.client.post(
            self.ask_url(), {'query': 'How large is the home market?'},
            format='json', **headers)

    def use_up_the_quota(self):
        from core.models.rag import ResearchQueryLog
        for index in range(3):
            ResearchQueryLog.objects.create(
                team=self.team, round_number=self.game.current_round,
                query_text=f'q{index}', response_text='a')

    def test_the_quota_refusal_is_in_the_students_language(self):
        from core.utils.participant_messages import participant_message
        self.use_up_the_quota()

        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                refused = self.ask(language)
                self.assertEqual(refused.status_code, 429, refused.data)
                self.assertEqual(refused.data['error'], participant_message(
                    'analyst_query_limit_reached', language=language,
                    maximum=3))
                self.assertIn('3', refused.data['error'])
        self.assertTrue(any('\u4e00' <= ch <= '\u9fff'
                            for ch in self.ask('zh-CN').data['error']))
        # A refusal at the quota is not a purchase.
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def _ask_while_the_research_system_is_down(self, language):
        from unittest import mock
        with mock.patch('core.rag.embeddings.translate_query_if_needed',
                        side_effect=lambda text, language: text), \
                mock.patch('core.rag.embeddings.get_embedding',
                           side_effect=RuntimeError(self.SECRET)):
            return self.ask(language)

    def test_an_outage_tells_the_student_nothing_about_the_server(self):
        from core.utils.participant_messages import participant_message

        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                with self.assertLogs('core.rag.views', level='ERROR') as logs:
                    refused = self._ask_while_the_research_system_is_down(
                        language)
                self.assertEqual(refused.status_code, 503, refused.data)
                self.assertEqual(refused.data['error'], participant_message(
                    'analyst_unavailable', language=language))
                for fragment in ('qdrant', '10.9.8.7', 'sk-not-for-students',
                                 'RuntimeError'):
                    self.assertNotIn(fragment, str(refused.data))
                # The operator still gets the reason; the student does not.
                self.assertIn(self.SECRET, '\n'.join(logs.output))

    def test_an_unanswered_question_is_not_charged(self):
        """Contract pin: this already held at head and had no test."""
        from core.models.rag import ResearchQueryLog
        refused = self._ask_while_the_research_system_is_down('en')

        self.assertEqual(refused.status_code, 503, refused.data)
        self.assertFalse(DecisionResearchPurchase.objects.filter(
            report_type=research_catalogue.ANALYST_QUERY).exists())
        self.assertFalse(ResearchQueryLog.objects.exists())
        offer = self.client.get(self.queries_url()).data['analyst_query']
        self.assertEqual(offer['queries_remaining'], 3)


class AnalystAuditTruthTests(AnalystQueryBase):
    """The audit trail and the ledger must tell one story about an analyst query.

    D1 of 2026-09-21: the purchase audit event was written with the charge,
    before the answer existed. When the research system then failed, the
    purchase row was deleted and the event stayed -- an append-only, chained
    record of a purchase the ledger never shows. In a dispute that reads as a
    charge that vanished. The event is now written only once the answer is
    delivered, in one savepoint with the question log, so every outcome leaves
    the purchase row, the question log and the audit event all present or all
    absent.
    """
    SECRET = 'embedding host down'

    def _events(self):
        return DecisionAuditEvent.objects.filter(
            action='purchase_research_report',
            payload__report_type=research_catalogue.ANALYST_QUERY)

    def _purchases(self):
        return DecisionResearchPurchase.objects.filter(
            report_type=research_catalogue.ANALYST_QUERY)

    def _ask(self, *, embedding_fails=False):
        from unittest import mock
        embedding = (mock.patch('core.rag.embeddings.get_embedding',
                                side_effect=RuntimeError(self.SECRET))
                     if embedding_fails else
                     mock.patch('core.rag.embeddings.get_embedding',
                                return_value=[0.0]))
        with embedding, \
                mock.patch('core.rag.embeddings.translate_query_if_needed',
                           side_effect=lambda text, language: text), \
                mock.patch('core.rag.client.search_articles',
                           return_value=[{'title': 'Home market sizing', 'tags': ['market']}]), \
                mock.patch('core.rag.views.synthesize_research_brief',
                           return_value='An answer.'):
            return self.client.post(
                self.ask_url(), {'query': 'How large is the home market?'},
                format='json')

    def test_an_unanswered_question_leaves_no_purchase_audit_event(self):
        refused = self._ask(embedding_fails=True)

        self.assertEqual(refused.status_code, 503, refused.data)
        self.assertFalse(self._purchases().exists())
        self.assertEqual(
            self._events().count(), 0,
            'the audit trail records an analyst purchase the ledger does not')

    def test_an_answered_question_is_audited_exactly_once(self):
        answered = self._ask()

        self.assertEqual(answered.status_code, 200, answered.data)
        self.assertEqual(self._purchases().count(), 1)
        event = self._events().get()
        self.assertEqual(event.team_id, self.team.id)
        self.assertEqual(event.round_id, self.round.id)
        self.assertEqual(D(event.payload['price']), self.ANALYST_PRICE)

    def test_a_failure_then_a_success_audits_only_the_success(self):
        from core.services import audit_chain
        self.assertEqual(self._ask(embedding_fails=True).status_code, 503)
        self.assertEqual(self._ask().status_code, 200)

        self.assertEqual(self._purchases().count(), 1)
        self.assertEqual(self._events().count(), 1)
        # Nothing was deleted or rewritten to get here, so the chain seals and
        # verifies with no unsealed remainder.
        audit_chain.seal_pending()
        report = audit_chain.verify_chain()
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['unsealed_total'], 0)

    def test_a_failed_audit_write_charges_nothing_and_logs_no_question(self):
        """Audit failures are fail-closed: no record, no charge, no answer."""
        from unittest import mock
        from core.models.rag import ResearchQueryLog
        with mock.patch('core.services.competition_audit.record_decision_event',
                        side_effect=RuntimeError('audit table unavailable')), \
                self.assertLogs('core.rag.views', level='ERROR'):
            refused = self._ask()

        self.assertEqual(refused.status_code, 503, refused.data)
        self.assertFalse(self._purchases().exists())
        self.assertFalse(ResearchQueryLog.objects.exists())
        offer = self.client.get(self.queries_url()).data['analyst_query']
        self.assertEqual(offer['queries_remaining'], 3)


class AnalystRouteLanguageTests(AnalystQueryBase):
    """D2 of 2026-09-21: every sentence the analyst route can say is bilingual.

    The 429 and the 503 were repaired earlier. These are the rest: the three
    remaining refusals, and the 200 "nothing relevant found" answer -- which is
    a charged answer, so a zh-CN team was paying full price for an English
    sentence.
    """

    def _post(self, body, language, url=None):
        # R43: the team's language governs once the team is known. The header
        # still decides the one refusal that comes before it is (unknown game).
        Enrollment.objects.filter(team_id=self.team.id).update(language=language)
        return self.client.post(url or self.ask_url(), body, format='json',
                                HTTP_ACCEPT_LANGUAGE=language)

    def assert_catalogue(self, response, status_code, key, language):
        from core.utils.participant_messages import participant_message
        self.assertEqual(response.status_code, status_code, response.data)
        text = response.data.get('error', response.data.get('response'))
        self.assertEqual(text, participant_message(key, language=language))
        has_cjk = any('一' <= ch <= '鿿' for ch in text)
        self.assertEqual(has_cjk, language == 'zh-CN', text)

    def test_an_empty_question_is_refused_in_the_students_language(self):
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                self.assert_catalogue(
                    self._post({'query': '   '}, language), 400,
                    'analyst_question_required', language)
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def test_a_scenario_without_the_analyst_refuses_in_the_students_language(self):
        ScenarioConfig.objects.filter(
            scenario=self.scenario, config_key='rag_enabled',
        ).update(config_value='false')
        _config_cache.clear()
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                self.assert_catalogue(
                    self._post({'query': 'q'}, language), 400,
                    'analyst_not_enabled', language)

    def test_an_unknown_game_is_refused_in_the_students_language(self):
        url = (f'/api/games/{self.game.id + 9999}/teams/{self.team.id}'
               f'/research/query/')
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                self.assert_catalogue(
                    self._post({'query': 'q'}, language, url=url), 404,
                    'analyst_game_or_team_not_found', language)

    def test_the_nothing_found_answer_is_in_the_students_language(self):
        from unittest import mock
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                with mock.patch('core.rag.embeddings.get_embedding',
                                return_value=[0.0]), \
                        mock.patch(
                            'core.rag.embeddings.translate_query_if_needed',
                            side_effect=lambda text, language: text), \
                        mock.patch('core.rag.client.search_articles',
                                   return_value=[]):
                    answered = self._post({'query': 'anything'}, language)
                self.assert_catalogue(
                    answered, 200, 'analyst_no_relevant_research', language)

    def test_an_unsupported_enrolment_language_is_refused_not_crashed(self):
        """D5: the round-state refusal looked its language up unguarded."""
        from core.utils.participant_messages import participant_message
        Enrollment.objects.filter(user_id=self.user.user_id).update(
            language='fr')
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        refused = self.client.post(self.ask_url(), {'query': 'q'},
                                   format='json')

        self.assertEqual(refused.status_code, 403, refused.data)
        self.assertEqual(refused.data['error'], participant_message(
            'round_not_open', language='en'))


class AnalystRulingsTests(AnalystQueryBase):
    """R42 and R43, 2026-09-21."""

    def _ask_and_find_nothing(self, **extra):
        from unittest import mock
        with mock.patch('core.rag.embeddings.get_embedding',
                        return_value=[0.0]), \
                mock.patch('core.rag.embeddings.translate_query_if_needed',
                           side_effect=lambda text, language: text), \
                mock.patch('core.rag.client.search_articles', return_value=[]):
            return self.client.post(self.ask_url(), {'query': 'anything'},
                                    format='json', **extra)

    def test_r42_a_question_that_finds_nothing_costs_nothing(self):
        from core.models.rag import ResearchQueryLog
        before = self.client.get(self.queries_url()).data['analyst_query']

        answered = self._ask_and_find_nothing()

        self.assertEqual(answered.status_code, 200, answered.data)
        self.assertIs(answered.data['charged'], False)
        self.assertFalse(DecisionResearchPurchase.objects.exists())
        self.assertFalse(ResearchQueryLog.objects.exists())
        self.assertFalse(DecisionAuditEvent.objects.filter(
            action='purchase_research_report').exists())
        after = self.client.get(self.queries_url()).data['analyst_query']
        self.assertEqual(after['queries_remaining'], before['queries_remaining'])
        self.assertEqual(answered.data['queries_remaining'],
                         before['queries_remaining'])

    def test_r42_the_sentence_no_longer_says_it_was_charged(self):
        from core.utils.participant_messages import participant_message
        for language, charged_words in (('en', 'and was charged'), ('zh-CN', '并已收费')):
            text = participant_message('analyst_no_relevant_research',
                                       language=language)
            self.assertNotIn(charged_words, text)

    def test_r43_the_teams_language_governs_not_the_requests(self):
        from core.utils.participant_messages import participant_message
        for team_language, header in (('zh-CN', 'en'), ('en', 'zh-CN')):
            with self.subTest(team=team_language, request=header):
                Enrollment.objects.filter(team_id=self.team.id).update(
                    language=team_language)
                answered = self._ask_and_find_nothing(
                    HTTP_ACCEPT_LANGUAGE=header)
                self.assertEqual(answered.data['response'], participant_message(
                    'analyst_no_relevant_research', language=team_language))

    def test_r43_a_team_with_no_usable_language_follows_the_request(self):
        from core.utils.participant_messages import participant_message
        for stored in ('', 'fr'):
            with self.subTest(stored=stored):
                Enrollment.objects.filter(team_id=self.team.id).update(
                    language=stored)
                answered = self._ask_and_find_nothing(
                    HTTP_ACCEPT_LANGUAGE='zh-CN')
                self.assertEqual(answered.data['response'], participant_message(
                    'analyst_no_relevant_research', language='zh-CN'))


class AuditTests(PaidResearchBase):
    def test_a_purchase_is_audited(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        event = DecisionAuditEvent.objects.filter(
            action='purchase_research_report').first()

        self.assertIsNotNone(event, 'the purchase wrote no audit event')
        self.assertEqual(event.team_id, self.team.id)
        self.assertEqual(event.round_id, self.round.id)
        self.assertEqual(event.payload['report_type'], 'products')
        self.assertTrue(event.payload_sha256)

    def test_a_refused_purchase_writes_no_audit_event(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        self.client.post(self.buy_url('products'), {}, format='json')

        self.assertFalse(DecisionAuditEvent.objects.filter(
            action='purchase_research_report').exists())


class PostCloseReadabilityTests(PaidResearchBase):
    def test_a_bought_report_is_still_readable_after_the_round_closes(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        self.round.status = 'processed'
        self.round.closed_at = timezone.now()
        self.round.save(update_fields=['status', 'closed_at'])
        self.game.current_round = 2
        self.game.save(update_fields=['current_round'])
        Round.objects.create(game=self.game, round_number=2, status='open',
                             opened_at=timezone.now())

        # Round 1's report, read back after close, from round 2.
        report = self.client.get(self.read_url('products', '?round=0'))

        self.assertIs(report.data['purchased'], True)

    def test_a_report_bought_in_an_earlier_round_is_not_free_in_a_later_one(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        self.round.status = 'processed'
        self.round.save(update_fields=['status'])
        self.game.current_round = 2
        self.game.save(update_fields=['current_round'])
        Round.objects.create(game=self.game, round_number=2, status='open',
                             opened_at=timezone.now())

        # The current round's edition is a different report and costs again.
        current = self.client.get(self.read_url('products'))

        self.assertIs(current.data['purchased'], False)


class ProfitAndLossTests(PaidResearchBase):
    """`research_expense` was a P&L line the engine hardcoded to zero."""

    def test_the_pnl_and_cash_move_by_the_authored_price(self):
        """Two identical teams; one bought a report. Nothing else differs.

        Asserting against a control team rather than an absolute figure means
        the test measures the charge itself, not the rest of the round.
        """
        from core.engine.costs import calculate_operating_expenses
        from core.engine.financials import generate_financial_statements
        from core.models.results_financials import RoundResultFinancials

        control = Team.objects.create(
            game=self.game, name='Control',
            firm_starter_profile=self.team.firm_starter_profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)
        DecisionSubmission.objects.create(
            team=control, round=self.round, status='draft')

        bought = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(bought.status_code, 201, bought.data)

        context = _Context(self.scenario, self.game, self.team, 1)
        context.teams = [self.team, control]
        calculate_operating_expenses(context)
        generate_financial_statements(context)

        mine = RoundResultFinancials.objects.get(
            game=self.game, team=self.team, round_number=1)
        theirs = RoundResultFinancials.objects.get(
            game=self.game, team=control, round_number=1)

        self.assertEqual(mine.research_expense, PRICE)
        self.assertEqual(theirs.research_expense, D('0'))
        # The report cost the team exactly its authored price, in the P&L...
        self.assertEqual(theirs.operating_income - mine.operating_income, PRICE)
        # ...and in cash, which is the constraint teams actually plan against.
        self.assertEqual(theirs.cash_closing - mine.cash_closing, PRICE)


class RoundGateTests(PaidResearchBase):
    def test_a_closed_round_refuses_the_purchase(self):
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.status_code, 403)
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def test_an_unknown_report_is_refused(self):
        response = self.client.post(self.buy_url('nonsense'), {},
                                    format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(DecisionResearchPurchase.objects.exists())


class _Context:
    """The minimum `calculate_operating_expenses` reads.

    Built by hand rather than by resolving a round, so the test isolates the
    research charge from every other engine input.
    """

    def __init__(self, scenario, game, team, round_number):
        self.scenario = scenario
        self.game = game
        self.teams = [team]
        self.round_number = round_number
        self.market_revenue = {}
        self.opex = {}
        self.log = []
        # What `generate_financial_statements` reads that is not getattr-guarded.
        # Empty: this round has no trading, so the only expense either team
        # carries is admin overhead, and the one difference between them is the
        # report one of them bought.
        self.interest = {}
        self.tax = {}
        self.cogs = {}
        self.logistics = {}
        self.inventory_costs = {}
        self.market_profit = {}
        self.revenue = {}
