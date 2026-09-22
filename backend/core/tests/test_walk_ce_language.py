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
