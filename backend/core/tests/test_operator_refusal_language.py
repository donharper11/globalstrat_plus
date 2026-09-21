"""An instructor working in Chinese is refused in Chinese (D3 of 2026-09-21).

Nearly every operator route refused in English only, several naming storage
fields. The console shows the server's reason first in its error toasts, so a
zh-CN instructor read English there. The refusals on the routes the console
calls during a live round now come from `core.utils.operator_messages`, in the
request's language, each with a stable `code`.

Three kinds of test:

* the catalogue is whole (both languages, same placeholders) and its codes are
  exactly the codes the console has been told it may show verbatim;
* a source scan, so a converted route cannot quietly grow a new English literal;
* behaviour: the same refusal asked for in zh-CN and in en, and the audit row
  recording English whichever was asked for.
"""
import ast
import re
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import OperatorAuditEvent, Round, User
from core.models.course import Course, Enrollment, Section
from core.tests.test_operator_concurrency import build_minimal_game
from core.utils import operator_messages
from core.utils.operator_messages import (
    MESSAGES, bilingual_codes, operator_message)

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
CONSOLE_ALLOWLIST = (REPO / 'frontend/globalstrat-frontend/src/pages'
                     / 'bilingualServerReason.js')


def has_cjk(text):
    return any('\u4e00' <= ch <= '\u9fff' for ch in str(text))


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------

class OperatorCatalogueTests(TestCase):

    def test_every_sentence_exists_in_both_languages(self):
        placeholder = re.compile(r'\{(\w+)\}')
        self.assertGreaterEqual(len(MESSAGES), 60)
        for key, entry in MESSAGES.items():
            with self.subTest(key=key):
                self.assertEqual(set(entry), {'en', 'zh-CN'})
                self.assertTrue(entry['en'].strip())
                self.assertTrue(has_cjk(entry['zh-CN']), entry['zh-CN'])
                self.assertEqual(set(placeholder.findall(entry['en'])),
                                 set(placeholder.findall(entry['zh-CN'])))

    def test_every_guidance_line_belongs_to_a_refusal(self):
        shared = {'state_moved_guidance', 'schedule_rejected_guidance',
                  'competition_course_unowned_guidance'}
        for key in MESSAGES:
            if key.endswith('_guidance') and key not in shared:
                with self.subTest(key=key):
                    self.assertIn(key[:-len('_guidance')], MESSAGES)

    def test_a_status_is_rendered_in_the_sentences_language(self):
        zh = operator_message('round_not_open', language='zh-CN', round=2,
                              status=operator_messages.round_status('closed'))
        en = operator_message('round_not_open', language='en', round=2,
                              status=operator_messages.round_status('closed'))
        self.assertNotIn('closed', zh)
        self.assertIn('closed', en)

    def test_the_console_allowlist_is_exactly_the_bilingual_codes(self):
        """The console shows a server sentence verbatim only for these codes.

        A code missing from the console hides a bilingual sentence behind a
        generic one; a code present there but not bilingual here shows English
        to a Chinese-language instructor. Either way this fails.
        """
        source = CONSOLE_ALLOWLIST.read_text(encoding='utf-8')
        block = re.search(
            r'BILINGUAL_REFUSAL_CODES = Object\.freeze\(\[(.*?)\]\)',
            source, re.S)
        self.assertIsNotNone(block, 'could not find the console allowlist')
        listed = re.findall(r"^\s*'([a-z0-9_]+)',", block.group(1), re.M)
        self.assertEqual(len(listed), len(set(listed)), 'duplicate code')
        self.assertEqual(sorted(listed), bilingual_codes())


# ---------------------------------------------------------------------------
# The source scan
# ---------------------------------------------------------------------------

# (file, classes) -- `None` means the whole file. These are the routes the
# instructor console calls during a live round.
CONVERTED = [
    ('core/services/lifecycle.py', None),
    ('core/views/round_control.py', None),
    ('core/views/grading.py', None),
    ('core/views/team_config.py', None),
    ('core/views/course.py',
     {'RosterViewSet', 'TeamManagementView', 'GameRoundScheduleView'}),
    ('core/views/scenario_views.py',
     {'GameActivateView', 'GamePauseView', 'GameResumeView', 'GameResetView',
      'GameArchiveView'}),
    ('core/views/results_api.py',
     {'InstructorAdvanceRoundView', 'InstructorInjectEventView',
      'InstructorExtendDeadlineView'}),
]
LIFECYCLE_ERRORS = {'LifecycleError', 'LifecycleConflict',
                    'LifecyclePrecondition'}


def _is_literal_text(node):
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(re.search(r'[A-Za-z]', node.value))
    if isinstance(node, ast.BinOp):
        return _is_literal_text(node.left) or _is_literal_text(node.right)
    return False


def english_refusal_literals(source, classes=None):
    """`{'error': '<literal>'}` and `LifecycleX('<literal>')` in `source`."""
    tree = ast.parse(source)
    scopes = [tree] if classes is None else [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name in classes]
    found = []
    for scope in scopes:
        for node in ast.walk(scope):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant) and key.value == 'error'
                            and _is_literal_text(value)):
                        found.append((node.lineno, 'error literal'))
            elif isinstance(node, ast.Call):
                name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
                if (name in LIFECYCLE_ERRORS and node.args
                        and _is_literal_text(node.args[0])):
                    found.append((node.lineno, f'{name} literal'))
    return found


class OperatorRefusalSourceScanTests(TestCase):

    def test_the_scanner_finds_what_it_is_looking_for(self):
        sample = (
            "class A:\n"
            "    def get(self):\n"
            "        return Response({'error': 'section_id is required.'})\n"
            "    def put(self):\n"
            "        return Response({'error': f'Round {x} not found.'})\n"
            "    def post(self):\n"
            "        raise LifecyclePrecondition('Could not parse deadline.')\n"
            "    def ok(self):\n"
            "        return Response(operator_refusal(request, 'k'))\n"
            "class B:\n"
            "    def get(self):\n"
            "        return Response({'error': 'ignored'})\n")
        self.assertEqual(len(english_refusal_literals(sample)), 4)
        self.assertEqual(len(english_refusal_literals(sample, {'A'})), 3)
        self.assertEqual(english_refusal_literals(sample, {'Missing'}), [])

    def test_the_live_round_routes_carry_no_english_refusal_literal(self):
        for relative, classes in CONVERTED:
            with self.subTest(file=relative):
                source = (BACKEND / relative).read_text(encoding='utf-8')
                if classes:
                    present = {node.name for node in ast.walk(ast.parse(source))
                               if isinstance(node, ast.ClassDef)}
                    self.assertEqual(classes - present, set(),
                                     'a scanned class was renamed or removed')
                self.assertEqual(
                    english_refusal_literals(source, classes), [],
                    f'{relative}: an operator refusal bypasses '
                    f'core.utils.operator_messages')


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class OperatorRefusalLanguageTests(TestCase):

    def setUp(self):
        self.game, _ = build_minimal_game(f'oplang-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.instructor = User.objects.create(
            username=f'op-{id(self)}', role='instructor', password_hash='x')
        self.course = Course.objects.create(
            course_code=f'OP{id(self) % 100000}', course_name='Operator',
            instructor_id=self.instructor.user_id, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='S1',
            section_name='S1', max_teams=4, team_size_min=1, team_size_max=4,
            is_active=True)
        self.game.section_id = self.section.section_id
        self.game.save(update_fields=['section_id'])
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.instructor)}')

    def call(self, method, url, body=None, language='zh-CN'):
        return getattr(self.client, method)(
            url, body or {}, format='json', HTTP_ACCEPT_LANGUAGE=language)

    def assert_refused(self, response, status_code, code, language):
        self.assertEqual(response.status_code, status_code, response.data)
        self.assertEqual(response.data.get('code'), code, response.data)
        self.assertIn(code, bilingual_codes())
        self.assertEqual(has_cjk(response.data['error']), language == 'zh-CN',
                         response.data['error'])
        if 'guidance' in response.data:
            self.assertEqual(has_cjk(response.data['guidance']),
                             language == 'zh-CN', response.data['guidance'])

    def both(self, make_request, status_code, code):
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                self.assert_refused(make_request(language), status_code, code,
                                    language)

    # -- round control -------------------------------------------------------

    def test_closing_a_closed_round(self):
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])
        url = f'/api/games/{self.game.id}/round-control/close/'
        self.both(lambda language: self.call('post', url, language=language),
                  409, 'round_already_closed')

    def test_the_audit_row_records_english_whatever_the_operator_read(self):
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])
        refused = self.call(
            'post', f'/api/games/{self.game.id}/round-control/close/')
        self.assertTrue(has_cjk(refused.data['error']))

        row = OperatorAuditEvent.objects.get(outcome='rejected')
        self.assertEqual(row.conflict['code'], 'round_already_closed')
        self.assertFalse(has_cjk(row.conflict['detail']), row.conflict)
        self.assertEqual(row.conflict['detail'], operator_message(
            'round_already_closed', round=1,
            status=operator_messages.round_status('closed')))

    def test_a_deadline_request_that_names_no_deadline(self):
        url = f'/api/games/{self.game.id}/round-control/deadline/'
        self.both(lambda language: self.call('post', url, language=language),
                  400, 'deadline_required')

    def test_a_deadline_that_is_not_a_date(self):
        url = f'/api/games/{self.game.id}/round-control/deadline/'
        self.both(lambda language: self.call(
            'post', url, {'deadline': 'next tuesday'}, language=language),
            400, 'deadline_unparseable')

    def test_the_console_was_looking_at_a_different_state(self):
        url = f'/api/games/{self.game.id}/round-control/close/'
        self.both(lambda language: self.call(
            'post', url, {'expected_status': 'closed'}, language=language),
            409, 'state_moved')
        zh = self.call('post', url, {'expected_status': 'closed'})
        self.assertNotIn('closed', zh.data['error'])
        self.assertNotIn('open', zh.data['error'])

    def test_processing_an_open_round_without_force(self):
        url = f'/api/games/{self.game.id}/round-control/process/'
        self.both(lambda language: self.call('post', url, language=language),
                  400, 'round_still_open')

    def test_a_forced_action_without_a_reason(self):
        url = f'/api/games/{self.game.id}/round-control/process/'
        self.both(lambda language: self.call(
            'post', url, {'force': True}, language=language),
            400, 'reason_required')

    # -- pause / resume ------------------------------------------------------

    def test_resuming_a_game_that_is_not_paused(self):
        url = f'/api/games/{self.game.id}/resume/'
        self.both(lambda language: self.call('post', url, language=language),
                  409, 'game_not_paused')
        zh = self.call('post', url)
        self.assertNotIn('active', zh.data['error'])

    def test_pausing_a_paused_game(self):
        self.game.status = 'paused'
        self.game.save(update_fields=['status'])
        url = f'/api/games/{self.game.id}/pause/'
        self.both(lambda language: self.call('post', url, language=language),
                  409, 'game_not_active')

    # -- schedule ------------------------------------------------------------

    def test_a_schedule_naming_a_round_from_another_game(self):
        url = f'/api/games/{self.game.id}/round-schedule/'
        body = {'rounds': [{'round_id': 99999999,
                            'deadline': '2030-01-01T00:00:00Z'}]}
        self.both(lambda language: self.call('post', url, body,
                                             language=language),
                  400, 'schedule_rejected')
        en = self.call('post', url, body, language='en')
        self.assertNotIn('99999999', en.data['error'])

    def test_an_empty_schedule(self):
        url = f'/api/games/{self.game.id}/round-schedule/'
        self.both(lambda language: self.call('post', url, language=language),
                  400, 'schedule_rounds_required')

    # -- roster --------------------------------------------------------------

    def test_a_roster_update_that_names_no_student(self):
        self.both(lambda language: self.call(
            'put', '/api/roster/', {'action': 'update'}, language=language),
            400, 'roster_student_required')
        en = self.call('put', '/api/roster/', {'action': 'update'},
                       language='en')
        self.assertNotIn('enrollment_id', en.data['error'])

    def test_a_roster_upload_with_no_section(self):
        self.both(lambda language: self.call(
            'post', '/api/roster/', {'action': 'upload', 'csv': 'x'},
            language=language), 400, 'section_required')

    def test_a_refused_csv_row_carries_a_reason_in_the_instructors_language(self):
        csv_text = 'student_id,display_name,email\n,No Identity,\nS-1,Ann,a@x.edu\n'
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                answered = self.call('post', '/api/roster/', {
                    'action': 'upload', 'section_id': self.section.section_id,
                    'csv': csv_text}, language=language)
                self.assertEqual(answered.status_code, 201, answered.data)
                self.assertEqual(len(answered.data['errors']), 1)
                row = answered.data['errors'][0]
                self.assertEqual(row['row'], 2)
                self.assertEqual(row['code'], 'roster_row_needs_identity')
                self.assertEqual(has_cjk(row['error']), language == 'zh-CN')
        self.assertTrue(Enrollment.objects.filter(
            section_id=self.section.section_id).exists())

    def test_a_csv_row_that_raises_tells_the_instructor_nothing_about_the_server(self):
        secret = 'duplicate key value violates unique constraint "users_pkey"'
        from core.views.course import RosterViewSet
        with mock.patch.object(RosterViewSet, '_find_or_create_user',
                               side_effect=RuntimeError(secret)), \
                self.assertLogs('core.views.course', level='ERROR') as logs:
            answered = self.call('post', '/api/roster/', {
                'action': 'upload', 'section_id': self.section.section_id,
                'csv': 'student_id,display_name,email\nS-9,Bo,b@x.edu\n'})
        self.assertEqual(answered.status_code, 201, answered.data)
        row = answered.data['errors'][0]
        self.assertEqual(row['code'], 'roster_row_failed')
        self.assertTrue(has_cjk(row['error']))
        self.assertNotIn('users_pkey', str(answered.data))
        self.assertIn(secret, '\n'.join(logs.output))

    def test_adding_a_student_that_raises_tells_the_instructor_nothing_either(self):
        secret = 'relation "users" does not exist'
        from core.views.course import RosterViewSet
        with mock.patch.object(RosterViewSet, '_find_or_create_user',
                               side_effect=RuntimeError(secret)), \
                self.assertLogs('core.views.course', level='ERROR'):
            refused = self.call('post', '/api/roster/', {
                'action': 'add', 'section_id': self.section.section_id,
                'student_id': 'S-2'})
        self.assert_refused(refused, 400, 'roster_add_failed', 'zh-CN')
        self.assertNotIn('relation', str(refused.data))

    # -- team assignment -----------------------------------------------------

    def test_an_assignment_request_with_no_assignments(self):
        self.both(lambda language: self.call(
            'put', '/api/team-management/', {'action': 'assign'},
            language=language), 400, 'assignments_required')

    def test_renaming_a_team_that_does_not_exist(self):
        self.both(lambda language: self.call(
            'put', '/api/team-management/',
            {'action': 'rename', 'team_id': 99999999, 'team_name': 'N'},
            language=language), 404, 'team_not_found')

    # -- grading -------------------------------------------------------------

    def test_seeding_a_rubric_with_no_course(self):
        self.both(lambda language: self.call(
            'post', '/api/grades/seed-rubric/', language=language),
            400, 'grading_course_required')

    def test_calculating_grades_with_no_game(self):
        self.both(lambda language: self.call(
            'post', '/api/grades/calculate/', language=language),
            400, 'grading_game_and_course_required')

    # -- team configuration --------------------------------------------------

    def test_saving_a_team_configuration_with_no_teams(self):
        self.game.status = 'setup'
        self.game.save(update_fields=['status'])
        url = f'/api/games/{self.game.id}/instructor/team-config/'
        self.both(lambda language: self.call('put', url, language=language),
                  400, 'team_config_no_teams')
