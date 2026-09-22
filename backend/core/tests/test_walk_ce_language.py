"""The language defects of the 2026-09-22 Consumer Electronics walkthrough.

Each class pins one defect id from
`handoff_readiness_v2/completion/WALKTHROUGH_CE_2026-09-22.md` (c). Every
test here was red on `4b152f8` and is green after the repair the completion
report `WALK_CE_LANGUAGE_2026-09-22.md` names for that id.

Fixture: `build_minimal_game` (one market, two teams), an instructor who owns
the game's course, and one student enrolled on team 1 -- the smallest game the
ticker, the news page, the drill-down and the summary all answer for.
"""
import re
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import Round, User
from core.models.course import Course, Enrollment, Section
from core.models.results import EventInstance
from core.models.scenario import EventTemplateDefinition
from core.tests.test_operator_concurrency import build_minimal_game

CJK = re.compile(r'[一-鿿]')
LATIN_WORD = re.compile(r'[A-Za-z]{3,}')


def has_cjk(text):
    return bool(CJK.search(str(text)))


class WalkCEBase(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'walkce-{id(self)}')
        self.team = self.teams[0]
        self.market = self.team.home_market
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.instructor = User.objects.create(
            username=f'walk-instr-{id(self)}', role='instructor',
            password_hash='x')
        self.course = Course.objects.create(
            course_code=f'WC{id(self) % 100000}', course_name='Walk',
            instructor_id=self.instructor.user_id, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='S1',
            section_name='S1', max_teams=4, team_size_min=1, team_size_max=4,
            is_active=True)
        self.game.section_id = self.section.section_id
        self.game.save(update_fields=['section_id'])
        self.student = User.objects.create(
            username=f'walk-student-{id(self)}', role='student',
            password_hash='x')
        self.enrollment = Enrollment.objects.create(
            user_id=self.student.user_id, section_id=self.section.section_id,
            team_id=self.team.id, is_active=True)

    def client_for(self, user, language=None):
        client = APIClient()
        credentials = {'HTTP_AUTHORIZATION': f'Bearer {create_access_token(user)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        return client

    def event_template(self, **overrides):
        values = dict(
            scenario=self.game.scenario,
            name='Major Competitor Product Launch',
            name_zh='主要竞争对手产品发布',
            description_template=(
                'An AI competitor has launched an aggressively priced Gen 2 '
                'product in {market}. Market share dynamics shift.'),
            description_template_zh='一家主要竞争对手在{market}发布了定价激进的第二代产品。',
            category='Competitive', severity='medium',
            probability_per_round=D('0'), earliest_round=1, max_occurrences=3)
        values.update(overrides)
        return EventTemplateDefinition.objects.create(**values)


# ---------------------------------------------------------------------------
# W-CE-06 -- a literal `{market}` in the ticker after an all-markets injection
# ---------------------------------------------------------------------------

class TickerPlaceholderTests(WalkCEBase):

    def _inject(self, template, market_id=None):
        body = {'event_template_id': template.id}
        if market_id:
            body['target_market_id'] = market_id
        response = self.client_for(self.instructor, 'en').post(
            f'/api/games/{self.game.id}/instructor/inject-event/',
            body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return EventInstance.objects.get(id=response.data['event_id'])

    def _ticker(self, language):
        response = self.client_for(self.student, language).get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/ticker/')
        self.assertEqual(response.status_code, 200, response.data)
        return [item['text'] for item in response.data['items']
                if item['type'] == 'event']

    def test_an_event_injected_for_every_market_stores_no_placeholder(self):
        event = self._inject(self.event_template())
        self.assertNotIn('{market}', event.narrative)
        self.assertIn('global markets', event.narrative)

    def test_an_event_injected_for_one_market_names_it(self):
        event = self._inject(self.event_template(), market_id=self.market.id)
        self.assertIn(self.market.name, event.narrative)
        self.assertNotIn('{', event.narrative)

    def test_the_ticker_shows_no_placeholder_in_either_language(self):
        self._inject(self.event_template())
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                texts = self._ticker(language)
                self.assertEqual(len(texts), 1, texts)
                self.assertNotIn('{market}', texts[0])
                self.assertNotIn('{value}', texts[0])

    def test_an_event_stored_before_the_fix_is_still_rendered(self):
        """A row written as the raw template (the walkthrough's game)."""
        template = self.event_template()
        EventInstance.objects.create(
            game=self.game, event_template=template, round_number=1,
            target_market=None, narrative=template.description_template)
        texts = self._ticker('en')
        self.assertEqual(len(texts), 1, texts)
        self.assertNotIn('{market}', texts[0])
        # The ticker keeps 80 characters of the narrative.
        self.assertIn('in global', texts[0])


# ---------------------------------------------------------------------------
# W-CE-16 (news) -- an event's narrative reaches a Chinese reader in Chinese
# ---------------------------------------------------------------------------

class EventNarrativeLanguageTests(WalkCEBase):

    def setUp(self):
        super().setUp()
        self.market.name_zh = '本土市场'
        self.market.save(update_fields=['name_zh'])
        self.template = self.event_template()

    def _fired(self, target_market=None):
        # As the engine stores it: English, already rendered.
        from core.engine.events import generate_event_narrative
        return EventInstance.objects.create(
            game=self.game, event_template=self.template, round_number=1,
            target_market=target_market,
            narrative=generate_event_narrative(
                self.template, target_market, 1, self.game.scenario))

    def test_the_news_page_renders_the_authored_chinese_template(self):
        self._fired(self.market)
        response = self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/news/round/1/')
        self.assertEqual(response.status_code, 200, response.data)
        narrative = response.data['events'][0]['narrative']
        self.assertTrue(has_cjk(narrative), narrative)
        self.assertIn('本土市场', narrative)
        self.assertNotIn('aggressively', narrative)
        self.assertNotIn('{market}', narrative)

    def test_the_english_reader_still_gets_the_stored_narrative(self):
        event = self._fired(self.market)
        response = self.client_for(self.student, 'en').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/news/round/1/')
        self.assertEqual(response.data['events'][0]['narrative'], event.narrative)

    def test_the_ticker_headline_is_chinese_for_a_chinese_reader(self):
        self._fired(None)
        response = self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/ticker/')
        texts = [item['text'] for item in response.data['items']
                 if item['type'] == 'event']
        self.assertEqual(len(texts), 1, texts)
        self.assertTrue(has_cjk(texts[0]), texts[0])
        self.assertIn('全球市场', texts[0])
        self.assertIsNone(LATIN_WORD.search(texts[0]), texts[0])

    def test_a_scenario_without_a_chinese_template_falls_back_to_english(self):
        self.template.description_template_zh = ''
        self.template.save(update_fields=['description_template_zh'])
        event = self._fired(self.market)
        response = self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/news/round/1/')
        self.assertEqual(response.data['events'][0]['narrative'], event.narrative)


# ---------------------------------------------------------------------------
# W-CE-08 -- the drill-down's origin label reads in the instructor's language
# ---------------------------------------------------------------------------

class DrillDownStatusLabelTests(WalkCEBase):

    def _drill(self, language):
        response = self.client_for(self.instructor, language).get(
            f'/api/games/{self.game.id}/instructor/teams/{self.team.id}/decisions/',
            {'round': 1})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_no_submission_is_labelled_in_both_languages(self):
        self.assertEqual(self._drill('en')['submission_origin_label'], 'No submission')
        zh = self._drill('zh-CN')
        self.assertEqual(zh['submission_origin'], 'no_submission')
        self.assertTrue(has_cjk(zh['submission_origin_label']), zh)
        self.assertIsNone(LATIN_WORD.search(zh['submission_origin_label']), zh)

    def test_a_draft_is_labelled_in_both_languages(self):
        from core.models import DecisionSubmission
        DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        self.assertEqual(self._drill('en')['submission_origin_label'],
                         'Draft (not locked)')
        zh = self._drill('zh-CN')
        self.assertEqual(zh['submission_origin'], 'draft')
        self.assertTrue(has_cjk(zh['submission_origin_label']), zh)

    def test_every_origin_the_classifier_can_return_has_both_labels(self):
        import ast
        from pathlib import Path
        from core.utils.operator_messages import SUBMISSION_ORIGIN_LABELS
        source = (Path(__file__).resolve().parents[1]
                  / 'views/results_api.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        classifier = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.FunctionDef)
                          and node.name == 'classify_submission_origin')
        returned = {node.value.value for node in ast.walk(classifier)
                    if isinstance(node, ast.Return)
                    and isinstance(node.value, ast.Constant)}
        self.assertTrue(returned)
        self.assertEqual(returned - set(SUBMISSION_ORIGIN_LABELS), set())
        for origin, labels in SUBMISSION_ORIGIN_LABELS.items():
            self.assertTrue(has_cjk(labels['zh-CN']), origin)
            self.assertFalse(has_cjk(labels['en']), origin)


# ---------------------------------------------------------------------------
# W-CE-22 -- the plant cost the page shows is the authored one, or none
# ---------------------------------------------------------------------------

class PlantCostContextTests(WalkCEBase):

    def _market_payload(self):
        response = self.client_for(self.student, 'en').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/context/strategy/')
        self.assertEqual(response.status_code, 200, response.data)
        return next(m for m in response.data['markets'] if m['id'] == self.market.id)

    def test_an_authored_cost_travels_with_the_market(self):
        self.market.plant_build_cost = D('12000000')
        self.market.plant_build_rounds = 3
        self.market.plant_capacity_units = 80000
        self.market.save(update_fields=[
            'plant_build_cost', 'plant_build_rounds', 'plant_capacity_units'])
        payload = self._market_payload()
        self.assertEqual(payload['plant_build_cost'], 12000000.0)
        self.assertEqual(payload['plant_build_rounds'], 3)
        self.assertEqual(payload['plant_capacity_units'], 80000)

    def test_an_unauthored_cost_is_null_not_zero(self):
        self.assertIsNone(self.market.plant_build_cost)
        payload = self._market_payload()
        self.assertIn('plant_build_cost', payload)
        self.assertIsNone(payload['plant_build_cost'])
        self.assertIsNone(payload['plant_capacity_units'])


# ---------------------------------------------------------------------------
# W-CE-13 -- the supply-chain sections of the Summary are not lock requirements
# ---------------------------------------------------------------------------

class SummaryOptionalSectionTests(WalkCEBase):

    SUPPLY_CHAIN = ('sourcing', 'logistics', 'trade_finance', 'inventory')

    def _summary(self, language):
        response = self.client_for(self.student, language).get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/summary/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_each_supply_chain_section_is_marked_optional_and_says_so(self):
        from core.models import DecisionSubmission
        DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                categories = self._summary(language)['categories']
                for key in self.SUPPLY_CHAIN:
                    category = categories[key]
                    self.assertTrue(category.get('optional'), key)
                    self.assertEqual(category['status'], 'empty')
                    self.assertEqual(len(category['warnings']), 1, category)
                    self.assertEqual(has_cjk(category['warnings'][0]),
                                     language == 'zh-CN', category)

    def test_the_optional_sections_are_exactly_the_ones_the_lock_ignores(self):
        """The lock's own preconditions, read from the view: whatever it
        requires is not optional, and whatever it never mentions is."""
        import ast
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1]
                  / 'views/decisions.py').read_text(encoding='utf-8')
        summary = next(node for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.ClassDef)
                       and node.name == 'DecisionSummaryView')
        required = next(
            ast.literal_eval(node.value) for node in ast.walk(summary)
            if isinstance(node, ast.Assign)
            and getattr(node.targets[0], 'id', '') == 'required_lock_categories')
        self.assertEqual(set(required), {'products', 'marketing', 'strategy'})
        from core.models import DecisionSubmission
        DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        categories = self._summary('en')['categories']
        optional = {key for key, value in categories.items() if value.get('optional')}
        self.assertEqual(optional & set(required), set())
        self.assertEqual(set(self.SUPPLY_CHAIN) - optional, set())

    def test_a_saved_supply_chain_decision_reads_configured_and_still_optional(self):
        from core.models import DecisionSubmission
        from core.models.sc_decisions import ContingencyPlan
        DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        ContingencyPlan.objects.create(team=self.team, round=self.round)
        category = self._summary('en')['categories']['inventory']
        self.assertEqual(category['status'], 'configured')
        self.assertTrue(category['optional'])
        self.assertEqual(category['warnings'], [])


# ---------------------------------------------------------------------------
# W-CE-16 (b) -- sentences a view wrote as f-strings reach a student in
# the request's language: dashboard signals, M&A reasons, the R&D budget
# source, and the research reports' rating words
# ---------------------------------------------------------------------------

class ViewSentenceLanguageTests(WalkCEBase):

    def _get(self, path, language):
        response = self.client_for(self.student, language).get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/{path}')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def assert_language(self, text, language):
        self.assertEqual(has_cjk(text), language == 'zh-CN', text)
        if language == 'zh-CN':
            self.assertIsNone(LATIN_WORD.search(text), text)

    def test_the_dashboard_signals_follow_the_reader(self):
        # A team with no results yet reads the R&D signal (0% of revenue).
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                signals = self._get('dashboard/scorecard/', language)['signals']
                self.assertTrue(signals)
                for signal in signals:
                    self.assert_language(signal['text'], language)

    def test_the_acquisition_reasons_follow_the_reader(self):
        from core.models.scenario import AcquisitionTarget
        fields = {f.name for f in AcquisitionTarget._meta.get_fields()}
        values = dict(scenario=self.game.scenario, market=self.market,
                      target_name='Rival Ltd', target_name_zh='对手公司',
                      description='d', base_acquisition_cost=D('1000000'),
                      market_share_gained=D('0.05'),
                      min_round_available=5, requires_market_presence=True)
        values = {k: v for k, v in values.items() if k in fields}
        AcquisitionTarget.objects.create(**values)
        self.market.name_zh = '本土市场'
        self.market.save(update_fields=['name_zh'])
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                targets = self._get('context/strategy/', language)['acquisition_targets']
                self.assertEqual(len(targets), 1)
                reasons = targets[0]['locked_reasons']
                self.assertTrue(reasons, targets[0])
                for reason in reasons:
                    self.assert_language(reason, language)
        self.assertIn('Available from Round 5',
                      self._get('context/strategy/', 'en')['acquisition_targets'][0]['locked_reasons'])

    def test_the_rd_budget_source_follows_the_reader(self):
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                source = self._get('context/rd/', language)['budget_source']
                self.assert_language(source, language)
        self.assertRegex(self._get('context/rd/', 'en')['budget_source'],
                         r'^20% of previous round net profit \(')

    def test_the_research_rating_words_follow_the_reader(self):
        from core.views import research_reports as rr
        for language in ('en', 'zh-CN'):
            with self.subTest(language=language):
                for text in (
                        rr._fit_label(0.9, language), rr._fit_label(0.1, language),
                        rr._growth_label(0.1, language), rr._growth_label(0.0, language),
                        rr._growth_label(0.04, language, short=True),
                        rr._importance_label(0.2, language),
                        rr._price_sensitivity_label(0.2, language),
                        rr._opportunity_signal({'growth_rate': 0.1, 'your_share': 0}, language)):
                    self.assert_language(text, language)
        self.assertEqual(rr._fit_label(0.9), 'Strong')
        self.assertEqual(rr._growth_label(0.04, short=True), 'Moderate')
        self.assertEqual(rr._growth_label(0.04), 'Moderate growth')

    def test_the_research_rules_compare_codes_not_words(self):
        """The opportunity rules used to compare English words; a translated
        word would have silently switched every rule off."""
        from core.views import research_reports as rr
        eroding = {'growth_rate': 0.0, 'your_share': 0.5, 'your_fit_score_code': 'weak'}
        self.assertEqual(rr._opportunity_signal(eroding, 'en'),
                         'Your lead may be eroding. Check competitor moves.')
        self.assertTrue(has_cjk(rr._opportunity_signal(eroding, 'zh-CN')))
        thin = {'growth_rate': 0.0, 'your_share': 0.5, 'your_fit_score_code': 'strong',
                'price_sensitivity_code': 'very_high'}
        self.assertEqual(rr._opportunity_signal(thin, 'en'),
                         'Dominated by price competition. Margins thin.')


# ---------------------------------------------------------------------------
# W-CE-15 -- the analyst refusal follows the team's stated language, and the
# language chosen at sign-in is what the team states
# ---------------------------------------------------------------------------

class AnalystRefusalLanguageTests(WalkCEBase):
    """The walkthrough's team 3 chose Chinese on the login page and was refused
    in English: the choice was written to the browser only, the enrolment kept
    its default 'en', and under R43 the enrolment is the team's language. The
    sign-in now records the choice through the preference route; this is the
    server half of that flow.
    """

    def setUp(self):
        super().setUp()
        from core.models.scenario import ScenarioConfig
        ScenarioConfig.objects.create(
            scenario=self.game.scenario, config_key='rag_enabled',
            config_value='false', description='no analyst in this game')

    def _ask(self, header_language):
        return self.client_for(self.student, header_language).post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/research/query/',
            {'query': 'q'}, format='json')

    def test_the_walkthrough_as_it_was(self):
        """Browser says zh-CN, enrolment still says the default: English."""
        self.assertEqual(self.enrollment.language, 'en')
        response = self._ask('zh-CN')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(has_cjk(response.data['error']), response.data)

    def test_the_sign_in_choice_recorded_through_the_preference_route_governs(self):
        """What AuthContext.login now does at sign-in, then the refusal."""
        recorded = self.client_for(self.student, 'zh-CN').put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        self.assertEqual(recorded.status_code, 200, recorded.data)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.language, 'zh-CN')
        response = self._ask('zh-CN')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertTrue(has_cjk(response.data['error']), response.data)
        self.assertIsNone(LATIN_WORD.search(response.data['error']), response.data)

    def test_the_teams_language_governs_over_the_header(self):
        """R43: one language per team, whatever the browser sends."""
        Enrollment.objects.filter(pk=self.enrollment.pk).update(language='zh-CN')
        self.assertTrue(has_cjk(self._ask('en').data['error']))


# ---------------------------------------------------------------------------
# W-CE-16 (d) -- the Phase-2 template fallbacks exist in Chinese and are
# selected by the team's (or the instructor's) language
# ---------------------------------------------------------------------------

class NarrativeFallbackLanguageTests(WalkCEBase):

    def _team_speaks(self, language):
        Enrollment.objects.filter(pk=self.enrollment.pk).update(language=language)

    def _instructor_speaks(self, language):
        # `get_instructor_language` reads the enrolment of `game.created_by`,
        # a Django auth user in this fixture; enrol that id.
        Enrollment.objects.update_or_create(
            user_id=self.game.created_by_id, section_id=self.section.section_id,
            defaults={'is_active': True, 'language': language})

    def test_the_briefing_fallback_follows_the_team(self):
        from core.engine.narratives import _build_briefing_fields
        english = _build_briefing_fields(self.game, 1, self.team)
        self.assertEqual(
            english['executive_summary'],
            '**Quarter 1 Results**\n\nRevenue: $0. Net income: $0. Cash position: $0.'
            '\n\nCash position below $1M — financial distress risk.')
        self._team_speaks('zh-CN')
        chinese = _build_briefing_fields(self.game, 1, self.team)
        self.assertTrue(has_cjk(chinese['executive_summary']), chinese)
        self.assertIsNone(LATIN_WORD.search(chinese['executive_summary']), chinese)
        for item in chinese['strategic_recommendations']['items']:
            self.assertTrue(has_cjk(item), item)
        for alert in chinese['risk_alerts']:
            self.assertTrue(has_cjk(alert['message']), alert)
        self.assertEqual(len(chinese['risk_alerts']), len(english['risk_alerts']))

    def test_the_compliance_fallback_follows_the_team(self):
        from types import SimpleNamespace
        from core.engine.narratives import _compliance_fallback
        event = SimpleNamespace(
            regime=SimpleNamespace(name='UFLPA'), market=None,
            triggered_by='audit', cost_usd=D('500000'), freeze_until_round=2)
        english = _compliance_fallback(event, self.round)
        self.assertEqual(
            english, 'UFLPA enforcement in all markets: audit. '
            'Remediation/penalty cost $500,000. '
            'Market access is frozen through round 2.')
        chinese = _compliance_fallback(event, self.round, 'zh-CN')
        self.assertTrue(has_cjk(chinese), chinese)
        self.assertIn('$500,000', chinese)
        self.assertIn('UFLPA', chinese)

    def test_the_supply_chain_event_fallback_follows_the_instructor(self):
        from types import SimpleNamespace
        from core.engine.narratives import _sc_event_fallback
        template = self.event_template()
        instance = SimpleNamespace(event_template=template)
        self.assertEqual(_sc_event_fallback(instance), template.description_template.strip())
        self.assertEqual(_sc_event_fallback(instance, 'zh-CN'),
                         template.description_template_zh.strip())
        template.description_template = ''
        template.description_template_zh = ''
        self.assertTrue(has_cjk(_sc_event_fallback(instance, 'zh-CN')))
        self.assertIn('supply-chain event', _sc_event_fallback(instance, 'en'))

    def test_the_memo_evaluation_fallback_follows_the_team(self):
        from types import SimpleNamespace
        from core.rag.communication_eval import _fallback_evaluation
        memo = SimpleNamespace(
            team=self.team, word_count=280,
            assignment=SimpleNamespace(
                word_limit=300,
                evaluation_criteria=[{'criterion': 'strategic_consistency'}]))
        english = _fallback_evaluation(memo)
        self.assertEqual(
            english['criteria_scores']['strategic_consistency']['feedback'],
            'Automated evaluation unavailable. Score based on submission completeness.')
        self._team_speaks('zh-CN')
        chinese = _fallback_evaluation(memo)
        self.assertEqual(chinese['overall_score'], english['overall_score'])
        for text in (chinese['criteria_scores']['strategic_consistency']['feedback'],
                     chinese['overall_feedback'], *chinese['strengths'], *chinese['gaps']):
            self.assertTrue(has_cjk(text), text)

    def test_every_coach_alert_exists_in_both_languages_with_the_same_values(self):
        from core.engine.instructor_alerts import _ALERT_TEXT, _alert_text
        placeholder = re.compile(r'\{(\w+)')
        self.assertEqual(set(_ALERT_TEXT), {'en', 'zh-CN'})
        self.assertEqual(set(_ALERT_TEXT['en']), set(_ALERT_TEXT['zh-CN']))
        for key, english in _ALERT_TEXT['en'].items():
            chinese = _ALERT_TEXT['zh-CN'][key]
            en_parts = (english,) if isinstance(english, str) else english
            zh_parts = (chinese,) if isinstance(chinese, str) else chinese
            self.assertEqual(len(en_parts), len(zh_parts), key)
            for en_part, zh_part in zip(en_parts, zh_parts):
                self.assertEqual(set(placeholder.findall(en_part)),
                                 set(placeholder.findall(zh_part)), key)
                if en_part:
                    self.assertTrue(has_cjk(zh_part), (key, zh_part))
        # Rendered, with every value in place.
        title, detail, note = _alert_text(
            'zh-CN', 'cash_crisis', team='极光', cash=D('1234'), debt=D('5'),
            net_income=D('-6'))
        self.assertIn('极光', title)
        self.assertIn('$1,234', title)
        self.assertTrue(has_cjk(detail) and has_cjk(note))

    def test_the_coach_alerts_are_written_in_the_instructors_language(self):
        from core.engine.instructor_alerts import generate_post_round_alerts
        from core.models.cc21_models import InstructorAlert
        from core.models.results_financials import RoundResultFinancials
        fields = {f.name for f in RoundResultFinancials._meta.get_fields()}
        values = {
            'game': self.game, 'team': self.team, 'round_number': 1,
            'cash_closing': D('1000'), 'total_debt': D('0'), 'net_income': D('-5'),
            'total_revenue': D('0'), 'debt_to_equity': D('0'), 'interest_expense': D('0'),
            'total_equity': D('1000'),
        }
        values = {k: v for k, v in values.items() if k in fields}
        RoundResultFinancials.objects.create(**values)
        self._instructor_speaks('zh-CN')
        generate_post_round_alerts(self.game, 1)
        alerts = list(InstructorAlert.objects.filter(game=self.game, team=self.team))
        self.assertTrue(alerts)
        for alert in alerts:
            self.assertTrue(has_cjk(alert.title), alert.title)
            self.assertTrue(has_cjk(alert.detail), alert.detail)
