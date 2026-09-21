"""A student working in Chinese is never refused in English (2026-09-21 remainder).

After the decision forms and the analyst route were made bilingual, 48 refusal
literals on student-facing routes were still English only -- login first among
them -- and several named a storage field (`team_id is required`). They now come
from `core.utils.participant_messages`, in the request's language, each with a
stable `code`.

Two kinds of test:

* behaviour: the same refusal driven through the real route in zh-CN and in en,
  compared with the catalogue, with the HTTP status unchanged;
* the refusals raised below a view (`services/persona_engine`,
  `services/r_and_d`), which know no request, are re-rendered by the view.

The source scan that keeps these routes from regrowing an English literal is in
`test_operator_refusal_language.WholeTreeRefusalScanTests`: it covers every
view module, not a list of converted ones.
"""
import re
from unittest import mock

from django.utils import timezone

from core.models import Round, User
from core.models.course import Enrollment
from core.tests.test_paid_research import PaidResearchBase
from core.utils.participant_messages import (
    MESSAGES, localise_refusal, participant_message, service_refusal)
from core.utils.passwords import hash_password

LANGUAGES = ('zh-CN', 'en')
STORAGE_NAME = re.compile(r'\b[a-z]+_(id|key|type|code|text)\b')


def has_cjk(text):
    return any('一' <= ch <= '鿿' for ch in str(text))


class StudentRefusalBase(PaidResearchBase):

    def call(self, method, url, body=None, language='zh-CN', client=None):
        return getattr(client or self.client, method)(
            url, body or {}, format='json', HTTP_ACCEPT_LANGUAGE=language)

    def assert_refused(self, response, status_code, key, language,
                       field='error', **values):
        self.assertEqual(response.status_code, status_code,
                         getattr(response, 'data', response.content))
        data = response.data if hasattr(response, 'data') else response.json()
        self.assertEqual(data.get('code'), key, data)
        self.assertEqual(
            data[field], participant_message(key, language=language, **values))
        self.assertEqual(has_cjk(data[field]), language == 'zh-CN', data[field])
        self.assertIsNone(STORAGE_NAME.search(data[field]), data[field])

    def both(self, make_request, status_code, key, field='error', **values):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_refused(make_request(language), status_code, key,
                                    language, field=field, **values)

    def team_url(self, tail):
        return f'/api/games/{self.game.id}/teams/{self.team.id}/{tail}'


class LoginRefusalLanguageTests(StudentRefusalBase):
    """The first sentence a student can be refused with."""

    def login(self, body, language):
        from rest_framework.test import APIClient
        return self.call('post', '/api/auth/login/', body, language,
                         client=APIClient())

    def test_no_username(self):
        self.both(lambda language: self.login({'password': 'x'}, language),
                  400, 'login_username_required')

    def test_no_password(self):
        self.both(lambda language: self.login({'username': 'someone'}, language),
                  400, 'login_password_required')

    def test_an_unknown_account(self):
        self.both(lambda language: self.login(
            {'username': 'nobody-at-all', 'password': 'wrong'}, language),
            401, 'login_invalid')

    def test_a_wrong_password_reads_the_same_as_an_unknown_account(self):
        User.objects.filter(user_id=self.user.user_id).update(
            password_hash=hash_password('right-password'))
        self.both(lambda language: self.login(
            {'username': self.user.username, 'password': 'wrong'}, language),
            401, 'login_invalid')

    def test_an_account_with_no_password(self):
        User.objects.filter(user_id=self.user.user_id).update(password_hash='')
        self.both(lambda language: self.login(
            {'username': self.user.username, 'password': 'anything'}, language),
            403, 'login_no_password')

    def test_a_student_with_no_team(self):
        User.objects.filter(user_id=self.user.user_id).update(
            password_hash=hash_password('right-password'))
        Enrollment.objects.filter(user_id=self.user.user_id).update(team_id=None)
        self.both(lambda language: self.login(
            {'username': self.user.username, 'password': 'right-password'},
            language), 403, 'login_no_team')

    def test_an_unsupported_language_preference(self):
        self.both(lambda language: self.call(
            'put', '/api/user/preferences/', {'language': 'fr'}, language),
            400, 'language_unsupported')


class StudentRouteRefusalLanguageTests(StudentRefusalBase):

    # -- communications ------------------------------------------------------

    def assignment(self, word_limit=300):
        from decimal import Decimal
        from core.models import CommunicationAssignment
        return CommunicationAssignment.objects.create(
            scenario=self.scenario, code='memo', name='Memo',
            trigger_type='ROUND_MILESTONE', audience='BOARD',
            prompt_text='Write a memo.', word_limit=word_limit,
            trigger_condition={'round': 1}, evaluation_criteria=[],
            coherence_weight=Decimal('0.05'))

    def test_submitting_an_empty_communication(self):
        url = self.team_url(f'communications/{self.assignment().id}/submit/')
        self.both(lambda language: self.call(
            'post', url, {'content': '   '}, language),
            400, 'communication_empty', field='detail')

    def test_submitting_a_communication_over_the_word_limit(self):
        url = self.team_url(f'communications/{self.assignment(10).id}/submit/')
        self.both(lambda language: self.call(
            'post', url, {'content': 'word ' * 20}, language),
            400, 'communication_over_word_limit', field='detail',
            limit=10, count=20)

    def test_submitting_a_communication_twice(self):
        from core.models import TeamCommunication
        assignment = self.assignment()
        TeamCommunication.objects.create(
            game=self.game, team=self.team, round=self.round,
            assignment=assignment, content='A memo.', word_count=2,
            is_draft=False, submitted_at=timezone.now())
        url = self.team_url(f'communications/{assignment.id}/submit/')
        self.both(lambda language: self.call('post', url, {}, language),
                  400, 'communication_already_submitted', field='detail')

    # -- organisation and tax structure --------------------------------------

    def structure(self, code='matrix'):
        from decimal import Decimal as D
        from core.models import OrganizationalStructureType
        return OrganizationalStructureType.objects.create(
            scenario=self.scenario, code=code, name=code.title(),
            description='d', base_overhead_per_round=D('0'),
            per_market_coordination_cost=D('0'), transition_cost=D('0'),
            transition_disruption_rounds=0, display_order=1)

    def test_a_structure_switch_that_names_no_structure(self):
        url = self.team_url('context/org-structure/')
        self.both(lambda language: self.call('post', url, {}, language),
                  400, 'request_incomplete')

    def test_a_structure_that_is_not_in_this_game(self):
        url = self.team_url('context/org-structure/')
        self.both(lambda language: self.call(
            'post', url, {'structure_id': 99999999}, language),
            404, 'org_structure_not_found')

    def test_switching_to_the_structure_the_team_already_has(self):
        structure = self.structure()
        url = self.team_url('context/org-structure/')
        first = self.call('post', url, {'structure_id': structure.id})
        self.assertEqual(first.status_code, 400, first.data)  # adopted by default
        self.both(lambda language: self.call(
            'post', url, {'structure_id': structure.id}, language),
            400, 'org_structure_same')

    def test_a_structure_the_team_cannot_afford(self):
        from decimal import Decimal as D
        from core.models import OrganizationalStructureType
        self.structure('centralized')
        self.call('post', self.team_url('context/org-structure/'),
                  {'structure_id': OrganizationalStructureType.objects.get(
                      code='centralized').id})
        costly = self.structure('costly')
        OrganizationalStructureType.objects.filter(pk=costly.pk).update(
            transition_cost=D('99999999'))
        url = self.team_url('context/org-structure/')
        for language in LANGUAGES:
            with self.subTest(language=language):
                refused = self.call('post', url, {'structure_id': costly.id},
                                    language)
                self.assertEqual(refused.status_code, 400, refused.data)
                self.assertEqual(refused.data['code'],
                                 'org_structure_unaffordable')
                self.assertEqual(has_cjk(refused.data['error']),
                                 language == 'zh-CN', refused.data['error'])
        english = self.call('post', url, {'structure_id': costly.id}, 'en')
        self.assertIn('Insufficient cash', english.data['error'])

    def test_a_tax_structure_switch_that_names_no_structure(self):
        url = self.team_url('context/tax-structure/')
        self.both(lambda language: self.call('post', url, {}, language),
                  400, 'request_incomplete')

    # -- tools, research, resources ------------------------------------------

    def test_saving_an_analysis_with_no_framework(self):
        url = self.team_url('tools/analysis/')
        self.both(lambda language: self.call(
            'post', url, {'analysis_data': {}}, language),
            400, 'framework_required')

    def test_asking_for_a_report_that_does_not_exist(self):
        self.both(lambda language: self.call(
            'get', self.read_url('no-such-report'), language=language),
            400, 'research_report_unknown')

    def test_searching_the_resources_for_nothing(self):
        self.both(lambda language: self.call(
            'post', '/api/resources/search/', {'query': '  '}, language),
            400, 'resource_query_required')

    # -- onboarding, round status, legacy team routes ------------------------

    def test_onboarding_asked_for_without_saying_which_team(self):
        self.both(lambda language: self.call(
            'get', '/api/onboarding/', language=language),
            400, 'request_incomplete')

    def test_finishing_onboarding_with_no_enrolment(self):
        self.both(lambda language: self.call(
            'post', '/api/onboarding/complete/', {'user_id': 99999999},
            language), 404, 'enrollment_not_found')

    def test_round_status_of_a_game_with_no_current_round(self):
        Round.objects.filter(game=self.game).delete()
        url = f'/api/games/{self.game.id}/round-status/'
        self.both(lambda language: self.call('get', url, language=language),
                  404, 'no_active_round')

    def test_the_legacy_points_route_without_a_team(self):
        self.both(lambda language: self.call(
            'get', '/api/qicoin/', language=language),
            400, 'request_incomplete')

    # -- the team scope guard (middleware, before any view) ------------------

    def test_another_teams_route_is_refused_in_the_students_language(self):
        from core.models import Team
        other = Team.objects.create(
            game=self.game, name='Other',
            firm_starter_profile=self.team.firm_starter_profile,
            performance_index=100, cash_on_hand=1, total_equity=1,
            shares_outstanding=1000)
        url = f'/api/games/{self.game.id}/teams/{other.id}/context/org-structure/'
        self.both(lambda language: self.call('get', url, language=language),
                  403, 'team_access_denied', field='detail')

    # -- advisors: refusals raised below the view ----------------------------

    def test_a_blank_advisor_question(self):
        self.both(lambda language: self.call(
            'post', '/api/persona/consult/',
            {'team_id': self.team.id, 'persona_key': 'cfo', 'question': '  '},
            language), 400, 'persona_question_required')

    def test_the_consultation_limit_is_said_in_the_students_language(self):
        from core.services import persona_engine
        with mock.patch.object(persona_engine, '_count_consultations_this_round',
                               return_value=10 ** 6), \
                mock.patch.object(persona_engine, '_get_current_round',
                                  return_value=1):
            persona_key = next(iter(persona_engine.PERSONAS))
            self.both(lambda language: self.call(
                'post', '/api/persona/consult/',
                {'team_id': self.team.id, 'persona_key': persona_key,
                 'question': 'What now?'}, language),
                400, 'persona_consultation_limit',
                maximum=persona_engine.MAX_CONSULTATIONS_PER_ROUND)


class ServiceRefusalTests(StudentRefusalBase):
    """A service knows no request; the view gives its refusal a language."""

    def test_a_service_refusal_is_english_until_a_view_localises_it(self):
        refusal = service_refusal('persona_reply_limit', maximum=3)
        self.assertEqual(refusal['error'], participant_message(
            'persona_reply_limit', language='en', maximum=3))
        self.assertEqual(refusal['code'], 'persona_reply_limit')

        class Request:
            headers = {'Accept-Language': 'zh-CN'}
        localised = localise_refusal(Request(), refusal)
        self.assertEqual(localised, {
            'error': participant_message(
                'persona_reply_limit', language='zh-CN', maximum=3),
            'code': 'persona_reply_limit'})

    def test_every_service_refusal_names_a_catalogue_sentence(self):
        import ast
        from pathlib import Path
        services = Path(__file__).resolve().parents[1] / 'services'
        for name in ('persona_engine.py', 'r_and_d.py'):
            tree = ast.parse((services / name).read_text(encoding='utf-8'))
            keys = [node.args[0].value for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and getattr(node.func, 'id', '') == 'service_refusal']
            with self.subTest(file=name):
                self.assertTrue(keys, 'no service refusal found')
                self.assertEqual([key for key in keys if key not in MESSAGES],
                                 [])


class GovernanceNoticeLanguageTests(StudentRefusalBase):
    """The governance page's standing notices were English f-strings.

    Not refusals, but sentences a student reads -- and the page priced the
    anti-corruption commitment by counting the commas in one of them, which
    only the English sentence has.
    """

    def setUp(self):
        super().setUp()
        from core.models.scenario import EntryModeDefinition, MarketDefinition
        from core.models.team_state import TeamMarketPresence
        venture = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='JV', code='jv', description='d',
            capital_requirement=0, control_level=1, risk_level=1,
            local_presence_score=1)
        MarketDefinition.objects.filter(pk=self.market.pk).update(
            name_zh='本土市场')
        away = MarketDefinition.objects.create(
            scenario=self.scenario, name='Away', name_zh='海外市场', code='AW',
            description='d', currency_code='USD', exchange_rate_base=1,
            base_growth_rate=0, entry_cost_base=0, tax_rate=0,
            regulatory_difficulty=1, infrastructure_quality=1)
        for market in (self.market, away):
            TeamMarketPresence.objects.create(
                team=self.team, market=market, entry_mode=venture,
                established_round=0, initial_investment=0, status='active')

    def notices(self, language):
        answered = self.call('get', self.team_url('context/governance/'),
                             language=language)
        self.assertEqual(answered.status_code, 200, answered.data)
        return answered.data['interaction_warnings']

    def test_the_english_notices_are_what_they_always_were(self):
        notices = self.notices('en')
        self.assertEqual(
            notices['anti_corruption']['message'],
            'You have JV partnerships in Home, Away. Anti-corruption '
            'monitoring adds $100K/round per JV market.')
        self.assertEqual(
            notices['public_esg_reporting']['message'],
            'Total ESG investment is only $0. Reporting without substance is '
            'seen as greenwashing. Increase environmental/social investment '
            'above $1M or remove this commitment.')

    def test_a_chinese_student_reads_chinese_and_the_markets_by_their_names(self):
        notices = self.notices('zh-CN')
        for code, notice in notices.items():
            with self.subTest(notice=code):
                self.assertTrue(has_cjk(notice['message']), notice)
                self.assertIsNone(re.search(r'[A-Za-z]{4,}', notice['message']),
                                  notice['message'])
        self.assertIn('本土市场、海外市场',
                      notices['anti_corruption']['message'])

    def test_the_jv_count_does_not_depend_on_the_sentence(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(
                    self.notices(language)['anti_corruption']['count'], 2)
