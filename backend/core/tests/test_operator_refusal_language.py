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
    ('core/views/team_control.py', None),
    ('core/views/instructor_accounts.py', None),
    ('core/views/course.py',
     {'RosterViewSet', 'TeamManagementView', 'GameRoundScheduleView',
      'DecisionStatusView', 'SendReminderView'}),
    ('core/views/scenario_views.py',
     {'GameActivateView', 'GamePauseView', 'GameResumeView', 'GameResetView',
      'GameArchiveView', 'GameCreateView', 'GameTeamsView', 'GameDeleteView',
      'ScenarioDetailView'}),
    ('core/views/results_api.py',
     {'InstructorAdvanceRoundView', 'InstructorInjectEventView',
      'InstructorExtendDeadlineView', 'InstructorSessionReadinessView',
      'InstructorOperatorEventsView', 'InstructorTeamDecisionsView'}),
    # The 2026-09-21 remainder.
    ('core/views/decisions.py', {'DecisionUnlockView'}),
    ('core/views/instructor_sc.py', None),
    ('core/views/events.py', None),
    ('core/views/core.py', {'UserViewSet', 'DashboardViewSet'}),
    ('core/middleware.py', None),
]
LIFECYCLE_ERRORS = {'LifecycleError', 'LifecycleConflict',
                    'LifecyclePrecondition'}


# Every key whose value a person reads: a refusal (`error`, `detail`), and what
# the console shows when an action succeeded (`message`, `warning`, `reason`).
SHOWN_KEYS = ('error', 'detail', 'message', 'warning', 'reason')


def _is_literal_text(node, bound=None):
    """Whether `node` is text written in the source rather than rendered.

    `bound` maps a local name to the values assigned to it, so
    `msg = f'...'` followed by `{'message': msg}` is found too.
    """
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(re.search(r'[A-Za-z]', node.value))
    if isinstance(node, ast.BinOp):
        return (_is_literal_text(node.left, bound)
                or _is_literal_text(node.right, bound))
    if isinstance(node, ast.IfExp):
        return (_is_literal_text(node.body, bound)
                or _is_literal_text(node.orelse, bound))
    if isinstance(node, ast.Name) and bound:
        return any(_is_literal_text(value) for value in bound.get(node.id, ()))
    return False


def _bound_names(scope):
    bound = {}
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, []).append(node.value)
    return bound


def english_refusal_literals(source, classes=None, keys=SHOWN_KEYS):
    """`{'error': '<literal>'}` and `LifecycleX('<literal>')` in `source`."""
    tree = ast.parse(source)
    scopes = [tree] if classes is None else [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name in classes]
    found = []
    for scope in scopes:
        bound = _bound_names(scope)
        for node in ast.walk(scope):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if not (isinstance(key, ast.Constant) and key.value in keys):
                        continue
                    if _is_literal_text(value, bound):
                        found.append((node.lineno, f'{key.value} literal'))
                    elif (isinstance(value, ast.Call)
                          and getattr(value.func, 'id', '') == 'str'):
                        # `{'error': str(exc)}`: an exception's English text.
                        found.append((node.lineno, f'{key.value} str()'))
            elif isinstance(node, ast.Call):
                name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
                if (name in LIFECYCLE_ERRORS and node.args
                        and _is_literal_text(node.args[0], bound)):
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

    def test_the_scanner_finds_a_confirmation_however_it_is_spelled(self):
        """`message`/`warning`, a conditional, and a name bound to a literal."""
        sample = (
            "class A:\n"
            "    def post(self):\n"
            "        msg = f'{game}: advanced.' if more else 'Game complete.'\n"
            "        warning = None\n"
            "        if late:\n"
            "            warning = ('That deadline ' 'is in the past.')\n"
            "        return Response({'message': msg, 'warning': warning,\n"
            "                         'detail': 'Removed.' if x else y,\n"
            "                         'round': after, 'code': 'a_code'})\n"
            "    def ok(self):\n"
            "        text = operator_message('done_x', language=language)\n"
            "        return Response({'message': text, 'warning': None})\n")
        self.assertEqual(
            [kind for _, kind in english_refusal_literals(sample)],
            ['message literal', 'warning literal', 'detail literal'])
        self.assertEqual(
            english_refusal_literals(sample, keys=('error',)), [])
        self.assertEqual(
            [kind for _, kind in english_refusal_literals(
                "x = Response({'error': str(exc), 'code': 'c'})")],
            ['error str()'])

    def test_the_live_round_routes_carry_no_english_refusal_literal(self):
        for relative, classes in CONVERTED:
            with self.subTest(file=relative):
                source = (BACKEND / relative).read_text(encoding='utf-8')
                if classes:
                    present = {node.name for node in ast.walk(ast.parse(source))
                               if isinstance(node, ast.ClassDef)}
                    self.assertEqual(classes - present, set(),
                                     'a scanned class was renamed or removed')
                offenders, _ = split_exempt(relative, source, classes)
                self.assertEqual(
                    offenders, [],
                    f'{relative}: an operator refusal bypasses '
                    f'core.utils.operator_messages')


# Text a person is shown that is deliberately still a literal: (file, text on
# or beside the line). Empty now, and kept so that an exemption is a reviewed
# line in this file rather than a quiet hole in the scan; the guard fails on
# anything not listed, and on a listed entry that no longer matches.
WHOLE_TREE_EXEMPT = {
    # The console never shows this sentence: its code is deliberately absent
    # from the console's allowlist, and the console says its own catalogue
    # sentence (`instructor.grades_refused_model_component`) for it instead.
    ('core/views/grading.py', "'code': 'model_derived_component_in_competition'"),
}


def split_exempt(relative, source, classes=None):
    """(offenders, exemptions matched) for one file."""
    lines = source.splitlines()
    offenders, matched = [], set()
    for lineno, kind in english_refusal_literals(source, classes):
        context = ' '.join(lines[max(0, lineno - 2):lineno + 1])
        exempt = {entry for entry in WHOLE_TREE_EXEMPT
                  if entry[0] == relative and entry[1] in context}
        if exempt:
            matched |= exempt
        else:
            offenders.append(f'{relative}:{lineno} {kind}')
    return offenders, matched


def every_view_module():
    modules = sorted((BACKEND / 'core/views').glob('*.py'))
    modules += [BACKEND / 'core/rag/views.py', BACKEND / 'core/middleware.py',
                BACKEND / 'core/services/lifecycle.py',
                BACKEND / 'core/services/persona_engine.py',
                BACKEND / 'core/services/r_and_d.py']
    return modules


class WholeTreeRefusalScanTests(TestCase):
    """No view module answers a person in a sentence written in the source.

    `CONVERTED` above names the operator routes; this is the wider net asked
    for once the remainder was converted: every view module, the scope
    middleware, and the two services whose refusals a view passes straight on.
    A new English refusal anywhere in them fails here, whichever catalogue it
    should have come from.
    """

    def test_every_view_module_is_scanned(self):
        names = {path.name for path in every_view_module()}
        self.assertGreater(len(names), 40)
        for expected in ('auth.py', 'cc32a_views.py', 'cc32b_views.py',
                         'onboarding.py', 'mixins.py', 'middleware.py'):
            self.assertIn(expected, names)

    def test_no_view_module_carries_an_english_sentence_for_a_person(self):
        offenders, exempt_seen = [], set()
        for path in every_view_module():
            relative = path.relative_to(BACKEND).as_posix()
            found, matched = split_exempt(
                relative, path.read_text(encoding='utf-8'))
            offenders += found
            exempt_seen |= matched
        self.assertEqual(offenders, [])
        self.assertEqual(exempt_seen, WHOLE_TREE_EXEMPT,
                         'an exemption no longer matches anything')


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

    # -- game creation, participation, accounts ------------------------------

    def test_creating_a_game_with_no_scenario(self):
        self.both(lambda language: self.call(
            'post', '/api/games/create/', {'num_teams': 4}, language=language),
            400, 'scenario_required')

    def test_a_participation_change_that_names_no_action(self):
        from core.models import Team
        team = Team.objects.filter(game=self.game).first()
        url = (f'/api/games/{self.game.id}/instructor/teams/{team.id}'
               f'/participation/')
        self.both(lambda language: self.call('post', url, language=language),
                  400, 'participation_action_invalid')

    def test_setting_a_password_that_is_too_short(self):
        student = User.objects.create(
            username=f'pw-{id(self)}', role='student', password_hash='x')
        Enrollment.objects.create(
            user_id=student.user_id, section_id=self.section.section_id,
            is_active=True, enrolled_at=timezone.now())
        url = f'/api/instructor/student-accounts/{student.user_id}/password/'
        self.both(lambda language: self.call(
            'post', url, {'password': 'abc'}, language=language),
            400, 'password_too_short')
        self.both(lambda language: self.call(
            'post', url, {'password': '   '}, language=language),
            400, 'password_blank')
        student.refresh_from_db()
        self.assertEqual(student.password_hash, 'x')

    def test_the_two_password_checks_cannot_disagree(self):
        from core.utils.passwords import password_problem, validate_password
        for candidate in ('', '   ', 'abc', 'long-enough', None):
            with self.subTest(candidate=candidate):
                self.assertEqual(password_problem(candidate) is None,
                                 validate_password(candidate) is None)

    def test_resetting_the_password_of_a_student_you_cannot_see(self):
        self.both(lambda language: self.call(
            'post', '/api/instructor/student-accounts/99999999/password/',
            language=language), 404, 'account_not_visible')

    # -- team configuration --------------------------------------------------

    def test_saving_a_team_configuration_with_no_teams(self):
        self.game.status = 'setup'
        self.game.save(update_fields=['status'])
        url = f'/api/games/{self.game.id}/instructor/team-config/'
        self.both(lambda language: self.call('put', url, language=language),
                  400, 'team_config_no_teams')


    # -- the 2026-09-21 remainder --------------------------------------------

    def _unlock_url(self, team):
        return (f'/api/games/{self.game.id}/teams/{team.id}/decisions/round/1'
                f'/unlock/')

    def _submission(self, status):
        from core.models import DecisionSubmission, Team
        team = Team.objects.filter(game=self.game).first()
        DecisionSubmission.objects.create(team=team, round=self.round,
                                          status=status)
        return team

    def test_unlocking_a_submission_that_is_not_locked(self):
        team = self._submission('draft')
        self.both(lambda language: self.call(
            'post', self._unlock_url(team), language=language),
            409, 'submission_not_locked')
        row = OperatorAuditEvent.objects.filter(outcome='rejected').first()
        self.assertEqual(row.conflict['detail'], 'Submission is not locked.')
        en = self.call('post', self._unlock_url(team), language='en')
        self.assertEqual(en.data['guidance'],
                         'Refresh — it may already have been unlocked.')

    def test_unlocking_in_a_round_that_is_already_processed(self):
        team = self._submission('locked')
        self.round.status = 'processed'
        self.round.save(update_fields=['status'])
        self.both(lambda language: self.call(
            'post', self._unlock_url(team), language=language),
            409, 'round_already_processed')
        row = OperatorAuditEvent.objects.filter(outcome='rejected').first()
        self.assertEqual(
            row.conflict['detail'],
            'Round 1 has already been processed; unlocking now would not '
            'change its results.')

    def test_staging_a_supply_chain_event_in_a_round_that_is_not_open(self):
        from decimal import Decimal
        from core.models.scenario import EventTemplateDefinition
        template = EventTemplateDefinition.objects.create(
            scenario=self.game.scenario, name='Probe shock',
            description_template='A shock.', category='supply_chain',
            severity='moderate', probability_per_round=Decimal('0'),
            earliest_round=1, max_occurrences=1)
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])
        url = f'/api/games/{self.game.id}/instructor/inject-sc-event/'
        self.both(lambda language: self.call(
            'post', url, {'event_template_id': template.id},
            language=language), 409, 'round_not_open')
        zh = self.call('post', url, {'event_template_id': template.id})
        self.assertNotIn('closed', zh.data['error'])
        # The audit row is byte-for-byte what it was before the conversion.
        row = OperatorAuditEvent.objects.filter(outcome='rejected').first()
        self.assertEqual(
            row.conflict['detail'],
            'Round 1 is "closed"; an event staged now would not fire in it.')

    # `rounds/<id>/send-reminder/` and `rounds/<id>/decision-status/` are not
    # driven here: both look a round up by a column the model does not have and
    # answer 500 before any refusal is reached (reported as a finding). Their
    # literals are converted and held by the source scan.

    def _someone_to_record_the_game_against(self):
        from django.contrib.auth.models import User as AuthUser
        AuthUser.objects.create_superuser(f'root-{id(self)}', password='x')

    def test_a_game_that_names_a_market_the_scenario_does_not_have(self):
        self._someone_to_record_the_game_against()
        body = {'scenario_id': self.game.scenario_id, 'num_teams': 2,
                'home_markets': ['ZZ']}
        self.both(lambda language: self.call(
            'post', '/api/games/create/', body, language=language),
            400, 'game_creation_market_unknown')

    def test_a_scenario_that_cannot_produce_a_game(self):
        from core.models.scenario import FirmStarterProfile
        from core.models import Scenario
        self._someone_to_record_the_game_against()
        bare = Scenario.objects.create(
            name='Bare', industry_label='T', description='d',
            starting_cash=1, num_rounds=2)
        self.assertFalse(FirmStarterProfile.objects.filter(scenario=bare).exists())
        self.both(lambda language: self.call(
            'post', '/api/games/create/',
            {'scenario_id': bare.id, 'num_teams': 2}, language=language),
            400, 'game_creation_no_starter_profiles')

    def test_an_event_engine_failure_is_framed_in_the_instructors_language(self):
        with mock.patch('core.services.event_engine.fire_events',
                        side_effect=RuntimeError('engine said no')):
            self.both(lambda language: self.call(
                'post', '/api/fire-events/',
                {'round_number': 1, 'game_id': self.game.id},
                language=language), 400, 'fire_events_failed')

    def test_firing_events_without_saying_where(self):
        self.both(lambda language: self.call(
            'post', '/api/fire-events/', language=language),
            400, 'fire_events_incomplete')

    def test_an_account_upload_with_nothing_in_it(self):
        self.both(lambda language: self.call(
            'post', '/api/users/bulk-upload/', language=language),
            400, 'accounts_csv_empty')

    def test_an_account_row_with_no_username(self):
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                answered = self.call(
                    'post', '/api/users/bulk-upload/',
                    {'csv': 'username,role,team_id\n,Student,\n'},
                    language=language)
                row = answered.data['errors'][0]
                self.assertEqual(row['code'], 'accounts_row_missing_username')
                self.assertEqual(has_cjk(row['error']), language == 'zh-CN')

    def test_another_instructors_game_is_refused_by_the_guard_in_chinese(self):
        other = User.objects.create(
            username=f'op2-{id(self)}', role='instructor', password_hash='x')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(other)}')
        url = f'/api/games/{self.game.id}/round-control/close/'
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                refused = client.post(url, {}, format='json',
                                      HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(refused.status_code, 403)
                body = refused.json()
                self.assertEqual(body['code'],
                                 'game_belongs_to_another_instructor')
                self.assertEqual(has_cjk(body['error']), language == 'zh-CN')
                self.assertIn('request_id', body)


    # -- confirmations: what the console shows when an action SUCCEEDED ------
    # `RoundControlCard` shows `message` (and `warning`) verbatim, so an
    # instructor working in Chinese read English after every close, reopen,
    # process, advance and deadline change. English is unchanged to the byte.

    def confirmed(self, response, language, english):
        self.assertEqual(response.status_code, 200, response.data)
        text = response.data['message']
        self.assertEqual(has_cjk(text), language == 'zh-CN', text)
        self.assertIn(self.game.name, text)
        if language == 'en':
            # `\d+`: closing locks the submissions an earlier close created.
            self.assertRegex(text, '^' + re.escape(english).replace(
                'COUNT', r'\d+') + '$')

    def test_close_then_reopen(self):
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                closed = self.call(
                    'post', f'/api/games/{self.game.id}/round-control/close/',
                    language=language)
                self.confirmed(closed, language,
                               f'{self.game.name}: round 1 closed. '
                               f'COUNT submission(s) locked.')
                reopened = self.call(
                    'post', f'/api/games/{self.game.id}/round-control/reopen/',
                    {'deadline': '2099-01-01T00:00:00Z'}, language=language)
                self.confirmed(reopened, language,
                               f'{self.game.name}: round 1 reopened. '
                               f'COUNT submission(s) unlocked.')

    def test_setting_and_clearing_a_deadline(self):
        url = f'/api/games/{self.game.id}/round-control/deadline/'
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                self.confirmed(
                    self.call('post', url, {'deadline': '2099-01-01T00:00:00Z'},
                              language=language),
                    language, f'{self.game.name}: deadline updated.')
                self.confirmed(
                    self.call('post', url, {'deadline': None},
                              language=language),
                    language, f'{self.game.name}: deadline cleared.')
                late = self.call('post', url,
                                 {'deadline': '2000-01-01T00:00:00Z'},
                                 language=language)
                self.assertEqual(has_cjk(late.data['warning']),
                                 language == 'zh-CN', late.data['warning'])

    def test_a_confirmation_is_never_a_refusal_code(self):
        done = [key for key in MESSAGES if key.startswith('done_')]
        self.assertGreaterEqual(len(done), 10)
        self.assertEqual([key for key in done if key in bilingual_codes()], [])
