"""Cohort routes are owned, roster faults are not echoed, and delete is guarded.

Three claims came out of a read-only source sweep (CONSOLE_AND_ANALYST_LEFTOVERS
D3a) and nobody had driven them. Every test here drives the registered route
with a real signed JWT, and every one of them was run against the unrepaired
code first; the completion report records what each returned then.

* **Ownership.** `roster/`, `team-management/`, `courses/` and `sections/`
  carry no game id, so `GameScopeGuardMiddleware` never sees them, and the views
  declared `IsInstructor`, which answers "is this an instructor" and nothing
  else. The ownership rule applied is the adopted one and is not restated:
  admin always; an unowned course is the shared pilot cohort; otherwise the
  course's `instructor_id`.
* **Exception text.** Two roster paths returned `str(e)` to the client.
* **Delete.** `GameDeleteView` deleted a game outside the lifecycle boundary.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import AuthorizationRefusalEvent, OperatorAuditEvent, Round, User
from core.models.core import Game, Team
from core.models.course import Course, Enrollment, Section, SimulationInstance
from core.tests.test_operator_concurrency import build_minimal_game

REFUSAL_CODE = 'cohort_belongs_to_another_instructor'


def say(response):
    """What the server actually answered, for the failure message."""
    body = getattr(response, 'data', None)
    if body is None:
        body = response.content[:300]
    return f'{response.status_code} {body!r}'


class OwnershipBase(TestCase):

    def _user(self, name, role='instructor'):
        return User.objects.create(
            username=f'{name}-{id(self)}', role=role, password_hash='x')

    def _client(self, user, language=None):
        client = APIClient()
        credentials = {
            'HTTP_AUTHORIZATION': f'Bearer {create_access_token(user)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        return client

    def _cohort(self, tag, instructor_id):
        course = Course.objects.create(
            course_code=f'{tag}{id(self) % 100000}', course_name=f'Course {tag}',
            instructor_id=instructor_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code=f'S-{tag}',
            section_name=f'Section {tag}', max_teams=8, team_size_min=1,
            team_size_max=5, is_active=True)
        return course, section

    def _student(self, name, section):
        user = User.objects.create(
            username=f'{name}-{id(self)}', display_name=name, role='Student',
            email=f'{name}@example.edu', password_hash='')
        enrollment = Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            is_active=True)
        return user, enrollment

    def setUp(self):
        self.owner = self._user('owner')
        self.rival = self._user('rival')
        self.admin = self._user('admin', role='admin')
        self.course, self.section = self._cohort('OWN', self.owner.user_id)
        self.student, self.enrollment = self._student('ada', self.section)

    def assertRefused(self, response, language_fragment='another instructor'):
        self.assertEqual(response.status_code, 403, say(response))
        self.assertEqual(response.data.get('code'), REFUSAL_CODE, say(response))
        self.assertIn(language_fragment, response.data.get('error', ''))
        self.assertTrue(response.data.get('request_id'), say(response))


# ---------------------------------------------------------------------------
# Claim 1 — roster
# ---------------------------------------------------------------------------

class RosterOwnershipTests(OwnershipBase):

    def _rename(self, client, name='Renamed By Request'):
        return client.put('/api/roster/', {
            'action': 'update', 'enrollment_id': self.enrollment.enrollment_id,
            'display_name': name, 'email': 'changed@example.edu'},
            format='json')

    def test_a_rival_instructor_cannot_rename_another_cohorts_student(self):
        response = self._rename(self._client(self.rival))

        self.assertRefused(response)
        self.student.refresh_from_db()
        # The negative half: the write did not happen.
        self.assertEqual(self.student.display_name, 'ada')
        self.assertEqual(self.student.email, 'ada@example.edu')

    def test_the_refused_write_leaves_an_authorization_record(self):
        response = self._rename(self._client(self.rival))

        event = AuthorizationRefusalEvent.objects.filter(
            actor_user_id=self.rival.user_id, method='PUT').last()
        self.assertIsNotNone(event, say(response))
        self.assertEqual(event.route, 'api/roster/')
        self.assertEqual(event.request_id, response.data.get('request_id'))

    def test_the_refusal_is_in_chinese_for_a_zh_instructor(self):
        response = self._rename(self._client(self.rival, language='zh-CN'))

        self.assertRefused(response, language_fragment='其他教师')
        self.assertNotIn('another instructor', response.data['error'])

    def test_the_owner_still_renames(self):
        response = self._rename(self._client(self.owner))

        self.assertEqual(response.status_code, 200, say(response))
        self.student.refresh_from_db()
        self.assertEqual(self.student.display_name, 'Renamed By Request')

    def test_an_admin_still_renames(self):
        response = self._rename(self._client(self.admin))

        self.assertEqual(response.status_code, 200, say(response))

    def test_an_unowned_course_is_still_the_shared_pilot_cohort(self):
        """The adopted rule, preserved: the live pilot's course has no owner."""
        _course, section = self._cohort('PILOT', None)
        _student, enrollment = self._student('pilot-student', section)

        response = self._client(self.rival).put('/api/roster/', {
            'action': 'update', 'enrollment_id': enrollment.enrollment_id,
            'display_name': 'Pilot Renamed'}, format='json')

        self.assertEqual(response.status_code, 200, say(response))

    def test_a_rival_cannot_remove_an_enrolment(self):
        response = self._client(self.rival).delete(
            f'/api/roster/?enrollment_id={self.enrollment.enrollment_id}')

        self.assertRefused(response)
        self.assertTrue(Enrollment.objects.filter(
            pk=self.enrollment.enrollment_id).exists())

    def test_the_owner_still_removes_an_enrolment(self):
        response = self._client(self.owner).delete(
            f'/api/roster/?enrollment_id={self.enrollment.enrollment_id}')

        self.assertEqual(response.status_code, 204, say(response))

    def test_a_rival_cannot_add_a_student(self):
        response = self._client(self.rival).post('/api/roster/', {
            'action': 'add', 'section_id': self.section.section_id,
            'student_id': 'planted', 'display_name': 'Planted',
            'email': 'planted@example.edu'}, format='json')

        self.assertRefused(response)
        self.assertEqual(Enrollment.objects.filter(
            section_id=self.section.section_id).count(), 1)
        self.assertFalse(User.objects.filter(student_id='planted').exists())

    def test_a_rival_cannot_upload_a_roster(self):
        response = self._client(self.rival).post('/api/roster/', {
            'action': 'upload', 'section_id': self.section.section_id,
            'csv': 'student_id,display_name,email\np1,P One,p1@example.edu\n'},
            format='json')

        self.assertRefused(response)
        self.assertEqual(Enrollment.objects.filter(
            section_id=self.section.section_id).count(), 1)

    def test_the_owner_still_adds_and_uploads(self):
        client = self._client(self.owner)
        added = client.post('/api/roster/', {
            'action': 'add', 'section_id': self.section.section_id,
            'student_id': 'own1', 'display_name': 'Own One',
            'email': 'own1@example.edu'}, format='json')
        uploaded = client.post('/api/roster/', {
            'action': 'upload', 'section_id': self.section.section_id,
            'csv': 'student_id,display_name,email\nown2,Own Two,own2@example.edu\n'},
            format='json')

        self.assertEqual(added.status_code, 201, say(added))
        self.assertEqual(uploaded.status_code, 201, say(uploaded))
        self.assertEqual(uploaded.data['created'], 1)

    def test_a_rival_cannot_read_another_cohorts_roster(self):
        response = self._client(self.rival).get(
            f'/api/roster/?section_id={self.section.section_id}')

        self.assertRefused(response)

    def test_a_refused_read_is_not_written_as_a_refused_mutation(self):
        self._client(self.rival).get(
            f'/api/roster/?section_id={self.section.section_id}')

        self.assertFalse(AuthorizationRefusalEvent.objects.filter(
            actor_user_id=self.rival.user_id).exists())

    def test_the_owner_still_reads_the_roster(self):
        response = self._client(self.owner).get(
            f'/api/roster/?section_id={self.section.section_id}')

        self.assertEqual(response.status_code, 200, say(response))
        self.assertEqual(len(response.data), 1)


class CompetitionRosterTests(OwnershipBase):
    """V2-033 reaches the roster: a heat with no instructor of record."""

    def test_the_roster_of_an_unowned_competition_section_cannot_be_changed(self):
        _course, section = self._cohort('HEAT', None)
        SimulationInstance.objects.create(
            section_id=section.section_id, current_round=0, total_rounds=5,
            status='setup', settings={'is_competition': True})

        response = self._client(self.rival).post('/api/roster/', {
            'action': 'add', 'section_id': section.section_id,
            'student_id': 'heat1', 'display_name': 'Heat One',
            'email': 'heat1@example.edu'}, format='json')

        self.assertEqual(response.status_code, 400, say(response))
        self.assertEqual(response.data.get('code'),
                         'competition_course_unowned', say(response))
        self.assertFalse(Enrollment.objects.filter(
            section_id=section.section_id).exists())


# ---------------------------------------------------------------------------
# Claim 1 — the sibling routes
# ---------------------------------------------------------------------------

class TeamManagementOwnershipTests(OwnershipBase):

    def setUp(self):
        super().setUp()
        self.game, self.teams = build_minimal_game(f'own-{id(self)}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)
        self.team = self.teams[0]
        # The rival's own cohort, with a student of their own.
        self.rival_course, self.rival_section = self._cohort(
            'RIV', self.rival.user_id)
        self.rival_student, _ = self._student('rival-student',
                                              self.rival_section)

    def test_a_rival_cannot_rename_another_cohorts_team(self):
        response = self._client(self.rival).put('/api/team-management/', {
            'action': 'rename', 'team_id': self.team.pk,
            'team_name': 'Defaced'}, format='json')

        self.assertRefused(response)
        self.team.refresh_from_db()
        self.assertNotEqual(self.team.name, 'Defaced')

    def test_a_rival_cannot_move_another_cohorts_student(self):
        response = self._client(self.rival).put('/api/team-management/', {
            'action': 'assign', 'assignments': [
                {'user_id': self.student.user_id, 'team_id': self.team.pk}]},
            format='json')

        self.assertRefused(response)
        self.enrollment.refresh_from_db()
        self.assertIsNone(self.enrollment.team_id)

    def test_a_rival_cannot_plant_their_own_student_on_another_cohorts_team(self):
        response = self._client(self.rival).put('/api/team-management/', {
            'action': 'assign', 'assignments': [
                {'user_id': self.rival_student.user_id,
                 'team_id': self.team.pk}]}, format='json')

        self.assertRefused(response)
        self.assertFalse(Enrollment.objects.filter(
            user_id=self.rival_student.user_id, team_id=self.team.pk).exists())

    def test_one_foreign_item_refuses_the_whole_assignment(self):
        """All or nothing: the rival's legitimate item is not applied either."""
        rival_game, rival_teams = build_minimal_game(f'riv-{id(self)}')
        Game.objects.filter(pk=rival_game.pk).update(
            section_id=self.rival_section.section_id)

        response = self._client(self.rival).put('/api/team-management/', {
            'action': 'assign', 'assignments': [
                {'user_id': self.rival_student.user_id,
                 'team_id': rival_teams[0].pk},
                {'user_id': self.student.user_id, 'team_id': self.team.pk}]},
            format='json')

        self.assertRefused(response)
        self.assertFalse(Enrollment.objects.filter(
            team_id__isnull=False).exists())

    def test_a_rival_cannot_read_another_cohorts_teams(self):
        response = self._client(self.rival).get(
            f'/api/team-management/?section_id={self.section.section_id}')

        self.assertRefused(response)

    def test_the_owner_and_an_admin_still_manage_teams(self):
        for user in (self.owner, self.admin):
            client = self._client(user)
            assigned = client.put('/api/team-management/', {
                'action': 'assign', 'assignments': [
                    {'user_id': self.student.user_id,
                     'team_id': self.team.pk}]}, format='json')
            renamed = client.put('/api/team-management/', {
                'action': 'rename', 'team_id': self.team.pk,
                'team_name': f'Named by {user.role}'}, format='json')
            listed = client.get(
                f'/api/team-management/?section_id={self.section.section_id}')

            self.assertEqual(assigned.status_code, 200, say(assigned))
            self.assertEqual(assigned.data['updated'], 1, say(assigned))
            self.assertEqual(renamed.status_code, 200, say(renamed))
            self.assertEqual(listed.status_code, 200, say(listed))


class CourseAndSectionOwnershipTests(OwnershipBase):

    def test_a_rival_cannot_delete_another_instructors_course(self):
        response = self._client(self.rival).delete(
            f'/api/courses/{self.course.course_id}/')

        self.assertRefused(response)
        self.assertTrue(Course.objects.filter(pk=self.course.course_id).exists())

    def test_a_rival_cannot_take_over_another_instructors_course(self):
        response = self._client(self.rival).patch(
            f'/api/courses/{self.course.course_id}/',
            {'instructor_id': self.rival.user_id}, format='json')

        self.assertRefused(response)
        self.assertEqual(Course.objects.get(
            pk=self.course.course_id).instructor_id, self.owner.user_id)

    def test_a_rival_cannot_change_or_delete_another_cohorts_section(self):
        client = self._client(self.rival)
        changed = client.patch(
            f'/api/sections/{self.section.section_id}/',
            {'max_teams': 1}, format='json')
        deleted = client.delete(f'/api/sections/{self.section.section_id}/')

        self.assertRefused(changed)
        self.assertRefused(deleted)
        self.assertEqual(Section.objects.get(
            pk=self.section.section_id).max_teams, 8)

    def test_a_rival_cannot_open_a_section_under_another_instructors_course(self):
        response = self._client(self.rival).post('/api/sections/', {
            'course': self.course.course_id, 'section_code': 'PLANTED',
            'section_name': 'Planted', 'is_active': True}, format='json')

        self.assertRefused(response)
        self.assertFalse(Section.objects.filter(
            section_code='PLANTED').exists())

    def test_every_refused_course_or_section_write_leaves_a_record(self):
        """The viewsets refuse by raising, so the record must not be written
        inside a block that the raise itself unwinds."""
        client = self._client(self.rival)
        client.post('/api/sections/', {
            'course': self.course.course_id, 'section_code': 'PLANTED',
            'section_name': 'Planted', 'is_active': True}, format='json')
        client.patch(f'/api/sections/{self.section.section_id}/',
                     {'max_teams': 1}, format='json')
        client.delete(f'/api/courses/{self.course.course_id}/')

        recorded = list(AuthorizationRefusalEvent.objects.filter(
            actor_user_id=self.rival.user_id).values_list('method', flat=True))
        self.assertEqual(sorted(recorded), ['DELETE', 'PATCH', 'POST'])

    def test_the_lists_show_a_rival_only_what_they_may_open(self):
        _pilot_course, pilot_section = self._cohort('PILOT', None)
        client = self._client(self.rival)

        courses = {row['course_id'] for row in client.get('/api/courses/').data}
        sections = {row['section_id']
                    for row in client.get('/api/sections/').data}

        self.assertNotIn(self.course.course_id, courses)
        self.assertNotIn(self.section.section_id, sections)
        # The shared pilot cohort stays visible to every instructor.
        self.assertIn(pilot_section.section_id, sections)

    def test_the_owner_and_an_admin_still_manage_the_course(self):
        for user in (self.owner, self.admin):
            client = self._client(user)
            listed = client.get('/api/courses/')
            changed = client.patch(
                f'/api/sections/{self.section.section_id}/',
                {'max_teams': 6}, format='json')
            created = client.post('/api/sections/', {
                'course': self.course.course_id,
                'section_code': f'NEW-{user.role}', 'section_name': 'New',
                'is_active': True}, format='json')

            self.assertIn(self.course.course_id,
                          {row['course_id'] for row in listed.data})
            self.assertEqual(changed.status_code, 200, say(changed))
            self.assertEqual(created.status_code, 201, say(created))

    def test_the_owner_still_deletes_their_course(self):
        response = self._client(self.owner).delete(
            f'/api/courses/{self.course.course_id}/')

        self.assertEqual(response.status_code, 204, say(response))


# ---------------------------------------------------------------------------
# Claim 2 — exception text
# ---------------------------------------------------------------------------

SECRET = 'relation "users" violates constraint users_email_key DETAIL: secret'


class RosterFaultTests(OwnershipBase):

    def _explode(self):
        from core.views.course import RosterViewSet
        return mock.patch.object(
            RosterViewSet, '_find_or_create_user',
            side_effect=RuntimeError(SECRET))

    def _add(self, language=None):
        return self._client(self.owner, language=language).post('/api/roster/', {
            'action': 'add', 'section_id': self.section.section_id,
            'student_id': 'boom', 'display_name': 'Boom',
            'email': 'boom@example.edu'}, format='json')

    def _upload(self, language=None):
        return self._client(self.owner, language=language).post('/api/roster/', {
            'action': 'upload', 'section_id': self.section.section_id,
            'csv': 'student_id,display_name,email\nb1,B One,b1@example.edu\n'},
            format='json')

    def test_a_failed_add_does_not_return_the_exception_text(self):
        with self._explode():
            response = self._add()

        self.assertNotIn('users_email_key', str(response.data), say(response))
        self.assertNotIn('relation', str(response.data))
        self.assertEqual(response.status_code, 400, say(response))
        self.assertEqual(response.data.get('code'), 'roster_add_failed')
        self.assertIn('could not be added', response.data['error'])

    def test_a_failed_add_is_logged_with_its_traceback(self):
        """The detail an operator needs stays on the server."""
        with self._explode(), self.assertLogs('core.views.course', 'ERROR') as logs:
            self._add()

        self.assertIn('users_email_key', '\n'.join(logs.output))
        self.assertIn('Traceback', '\n'.join(logs.output))

    def test_a_failed_add_is_explained_in_chinese(self):
        with self._explode():
            response = self._add(language='zh-CN')

        self.assertIn('未能添加', response.data['error'], say(response))
        self.assertNotIn('users_email_key', str(response.data))

    def test_a_failed_csv_row_does_not_return_the_exception_text(self):
        with self._explode():
            response = self._upload()

        self.assertNotIn('users_email_key', str(response.data), say(response))
        self.assertEqual(response.status_code, 201, say(response))
        self.assertEqual(len(response.data['errors']), 1, say(response))
        row = response.data['errors'][0]
        self.assertEqual(row['row'], 2)
        self.assertEqual(row.get('code'), 'roster_row_failed')
        self.assertIn('could not be added', row['error'])

    def test_a_failed_csv_row_is_logged_with_its_row_number(self):
        with self._explode(), self.assertLogs('core.views.course', 'ERROR') as logs:
            self._upload()

        self.assertIn('users_email_key', '\n'.join(logs.output))
        self.assertIn('row 2', '\n'.join(logs.output))

    def test_a_failed_csv_row_is_explained_in_chinese(self):
        with self._explode():
            response = self._upload(language='zh-CN')

        self.assertIn('未能添加', response.data['errors'][0]['error'],
                      say(response))


# ---------------------------------------------------------------------------
# Claim 3 — delete
# ---------------------------------------------------------------------------

REASON = 'created by mistake during setup'


class GameDeleteBoundaryTests(OwnershipBase):

    def setUp(self):
        super().setUp()
        self.game, self.teams = build_minimal_game(f'del-{id(self)}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id, status='setup', current_round=0)
        self.game.refresh_from_db()
        Round.objects.create(game=self.game, round_number=0, status='pending')

    def _delete(self, user, body=None, language=None):
        client = self._client(user, language=language)
        # A 500 is a finding here, not a test error.
        client.raise_request_exception = False
        return client.delete(f'/api/games/{self.game.pk}/delete/',
                             body if body is not None else {'reason': REASON},
                             format='json')

    def _mark_competition(self):
        SimulationInstance.objects.create(
            section_id=self.section.section_id, game_id=self.game.pk,
            current_round=0, total_rounds=5, status='setup',
            settings={'is_competition': True})

    def test_a_rival_is_refused_by_the_game_scope_guard(self):
        """Already true before this work: the route names a game."""
        response = self._delete(self.rival)

        self.assertEqual(response.status_code, 403, say(response))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())

    def test_delete_without_a_reason_is_refused_and_audited(self):
        response = self._delete(self.owner, body={})

        self.assertEqual(response.status_code, 400, say(response))
        self.assertEqual(response.data.get('code'), 'reason_required')
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        event = OperatorAuditEvent.objects.get(
            game=self.game, action='delete_game')
        self.assertEqual(event.outcome, 'rejected')
        self.assertEqual(event.request_id, response.data['request_id'])

    def test_a_competition_heat_cannot_be_deleted(self):
        self._mark_competition()

        response = self._delete(self.owner)

        self.assertEqual(response.status_code, 409, say(response))
        self.assertEqual(response.data.get('code'),
                         'competition_game_not_deletable')
        self.assertIn('rchive', response.data.get('guidance', ''))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)
        event = OperatorAuditEvent.objects.get(
            game=self.game, action='delete_game')
        self.assertEqual(event.outcome, 'rejected')
        self.assertEqual(event.user_id, self.owner.user_id)

    def test_an_admin_cannot_delete_a_competition_heat_either(self):
        self._mark_competition()

        response = self._delete(self.admin)

        self.assertEqual(response.status_code, 409, say(response))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())

    def test_the_competition_refusal_is_in_chinese_for_a_zh_operator(self):
        self._mark_competition()

        response = self._delete(self.owner, language='zh-CN')

        self.assertIn('竞赛场次', response.data['error'])
        self.assertNotIn('competition', response.data['error'])

    def test_an_unowned_competition_heat_is_refused_like_every_other_action(self):
        Course.objects.filter(pk=self.course.course_id).update(
            instructor_id=None)
        self._mark_competition()

        response = self._delete(self.rival)

        self.assertEqual(response.status_code, 400, say(response))
        self.assertEqual(response.data.get('code'),
                         'competition_course_unowned')
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())

    def test_a_game_with_an_audit_record_is_refused_not_a_500(self):
        """The audit tables PROTECT the game, and they are append-only, so a
        game that has ever been operated cannot be deleted at all. That used to
        surface as an unexplained 500.

        The activation here is itself refused (the fixture has no round 1) and
        that is deliberate: a *rejected* attempt writes an audit row too, so
        even a game nobody ever managed to start is already undeletable."""
        activated = self._client(self.owner).post(
            f'/api/games/{self.game.pk}/activate/', {}, format='json')
        self.assertTrue(OperatorAuditEvent.objects.filter(
            game=self.game).exists(), say(activated))

        response = self._delete(self.owner)

        self.assertEqual(response.status_code, 409, say(response))
        self.assertEqual(response.data.get('code'), 'game_has_record')
        self.assertIn('rchive', response.data.get('guidance', ''))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)

    def test_a_protected_row_the_precheck_missed_undoes_the_whole_cascade(self):
        """The pre-check names three tables. If a fourth ever PROTECTs a game,
        the cascade must not stop halfway with the teams already gone."""
        self._client(self.owner).post(
            f'/api/games/{self.game.pk}/activate/', {}, format='json')
        with mock.patch('core.views.scenario_views._has_permanent_record',
                        return_value=False), \
                self.assertLogs('core.lifecycle', 'ERROR'):
            response = self._delete(self.owner)

        self.assertEqual(response.status_code, 409, say(response))
        self.assertEqual(response.data.get('code'), 'game_has_record')
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)
        self.assertEqual(Round.objects.filter(game=self.game).count(), 1)

    def test_a_never_operated_game_is_deleted_and_the_deletion_is_recorded(self):
        game_id = self.game.pk
        with self.assertLogs('core.lifecycle', 'WARNING') as logs:
            response = self._delete(self.owner)

        self.assertEqual(response.status_code, 200, say(response))
        self.assertFalse(Game.objects.filter(pk=game_id).exists())
        self.assertFalse(Team.objects.filter(game_id=game_id).exists())
        self.assertTrue(response.data.get('request_id'))
        self.assertIn('permanently deleted', response.data['message'])
        line = '\n'.join(logs.output)
        self.assertIn(f'game {game_id}', line)
        self.assertIn(self.owner.username, line)
        self.assertIn(REASON, line)
        self.assertIn(response.data['request_id'], line)

    def test_the_route_inventory_counts_delete_as_lifecycle_and_guarded(self):
        from core.services.route_inventory import mutating_routes
        entry = mutating_routes()['api/games/<int:game_id>/delete/|delete']

        self.assertTrue(entry['lifecycle_mutating'],
                        'Deleting a game removes its rounds, teams and events; '
                        'the detector must not read that as harmless.')
        self.assertTrue(entry['uses_boundary'])
        self.assertFalse(entry['exempt'])


class ConsoleReasonContractTests(OwnershipBase):
    """What the instructor console has to send, pinned from the server side.

    Found while bringing delete under the boundary: the console called
    `resetGame(gameId)` and `archiveGame(gameId)` with no body at all, and both
    routes have required a written reason since they joined the boundary -- so
    both buttons answered 400 on every click. The frontend half of the repair
    is pinned by `src/pages/reasonedActions.test.js`.
    """

    def setUp(self):
        super().setUp()
        self.game, _teams = build_minimal_game(f'con-{id(self)}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)

    def test_the_empty_body_the_console_used_to_send_is_refused(self):
        client = self._client(self.owner)
        for path in ('reset', 'archive'):
            response = client.post(
                f'/api/games/{self.game.pk}/{path}/', {}, format='json')
            self.assertEqual(response.status_code, 400, say(response))
            self.assertEqual(response.data.get('code'), 'reason_required',
                             say(response))

    def test_the_body_the_console_now_sends_is_accepted(self):
        client = self._client(self.owner)
        body = {'reason': 'the course has finished'}

        reset = client.post(f'/api/games/{self.game.pk}/reset/', body,
                            format='json')
        archived = client.post(f'/api/games/{self.game.pk}/archive/', body,
                               format='json')

        self.assertEqual(reset.status_code, 200, say(reset))
        self.assertEqual(archived.status_code, 200, say(archived))

    def test_deleting_a_game_that_does_not_exist_is_a_refusal_not_a_500(self):
        response = self._client(self.admin).delete(
            '/api/games/987654/delete/', {'reason': REASON}, format='json')

        self.assertEqual(response.status_code, 400, say(response))


# ---------------------------------------------------------------------------
# Auditor preflight: "is there an active legacy or alternate entry point?"
# ---------------------------------------------------------------------------

class AlternateEntryPointTests(OwnershipBase):
    """The same writes, reached through the generic `teams/` and `users/`
    viewsets, which also name no game and also declared only a role.

    Closing `roster/` while `PATCH /api/users/<id>/` still rewrites any account
    -- including its role and its password -- would have closed nothing.
    """

    def setUp(self):
        super().setUp()
        self.game, self.teams = build_minimal_game(f'alt-{id(self)}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)
        self.team = self.teams[0]
        self.rival_course, self.rival_section = self._cohort(
            'RIV', self.rival.user_id)
        self.rival_student, _ = self._student('rival-student',
                                              self.rival_section)

    # ---- teams/ -----------------------------------------------------------

    def test_no_one_rewrites_a_team_through_the_generic_team_route(self):
        """`TeamSerializer` is `fields = '__all__'`: cash, equity, the
        performance index and participation status, with no lock and no audit
        row. The console never calls it; every sanctioned team write has its
        own guarded route."""
        for user in (self.rival, self.owner, self.admin):
            response = self._client(user).patch(
                f'/api/teams/{self.team.pk}/',
                {'cash_on_hand': '1.00', 'name': 'Defaced'}, format='json')
            self.assertEqual(response.status_code, 405, say(response))
        deleted = self._client(self.rival).delete(f'/api/teams/{self.team.pk}/')
        self.assertEqual(deleted.status_code, 405, say(deleted))
        self.team.refresh_from_db()
        self.assertEqual(str(self.team.cash_on_hand), '1000000.00')
        self.assertNotEqual(self.team.name, 'Defaced')

    def test_the_team_route_still_reads(self):
        response = self._client(self.owner).get(f'/api/teams/{self.team.pk}/')

        self.assertEqual(response.status_code, 200, say(response))

    # ---- users/ -----------------------------------------------------------

    def test_an_instructor_cannot_make_themselves_an_admin(self):
        response = self._client(self.rival).patch(
            f'/api/users/{self.rival.user_id}/', {'role': 'admin'},
            format='json')

        self.assertIn(response.status_code, (403, 404), say(response))
        self.rival.refresh_from_db()
        self.assertEqual(self.rival.role, 'instructor')

    def test_an_instructor_cannot_promote_a_student_of_their_own(self):
        response = self._client(self.rival).patch(
            f'/api/users/{self.rival_student.user_id}/', {'role': 'admin'},
            format='json')

        self.assertEqual(response.status_code, 403, say(response))
        self.assertEqual(response.data.get('code'), 'staff_account_admin_only')
        self.rival_student.refresh_from_db()
        self.assertEqual(self.rival_student.role, 'Student')
        event = AuthorizationRefusalEvent.objects.get(
            actor_user_id=self.rival.user_id)
        self.assertIn('staff account', event.reason)
        self.assertEqual(event.request_id, response.data['request_id'])

    def test_an_instructor_cannot_set_another_instructors_password(self):
        response = self._client(self.rival).patch(
            f'/api/users/{self.owner.user_id}/',
            {'password': 'taken-over-123'}, format='json')

        self.assertIn(response.status_code, (403, 404), say(response))
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.password_hash, 'x')

    def test_an_instructor_cannot_rewrite_another_cohorts_student(self):
        client = self._client(self.rival)
        patched = client.patch(
            f'/api/users/{self.student.user_id}/',
            {'password': 'taken-over-123', 'username': 'defaced'},
            format='json')
        deleted = client.delete(f'/api/users/{self.student.user_id}/')

        self.assertEqual(patched.status_code, 404, say(patched))
        self.assertEqual(deleted.status_code, 404, say(deleted))
        self.student.refresh_from_db()
        self.assertEqual(self.student.password_hash, '')
        self.assertNotEqual(self.student.username, 'defaced')

    def test_an_instructor_cannot_create_a_staff_account(self):
        client = self._client(self.rival)
        created = client.post('/api/users/', {
            'username': 'backdoor', 'role': 'admin',
            'password': 'known-to-me-123'}, format='json')
        uploaded = client.post('/api/users/bulk-upload/', {
            'csv': 'username,role,team_id,password\n'
                   'backdoor2,Admin,,known-to-me-123\n'}, format='json')

        self.assertEqual(created.status_code, 403, say(created))
        self.assertEqual(created.data.get('code'), 'staff_account_admin_only')
        self.assertEqual(uploaded.data.get('created'), 0, say(uploaded))
        self.assertEqual(uploaded.data['errors'][0].get('code'),
                         'staff_account_admin_only', say(uploaded))
        self.assertFalse(User.objects.filter(
            username__startswith='backdoor').exists())

    def test_an_instructor_cannot_move_another_cohorts_student_by_the_user_route(self):
        response = self._client(self.rival).post(
            f'/api/users/{self.student.user_id}/assign-team/',
            {'team_id': self.team.pk}, format='json')

        self.assertEqual(response.status_code, 404, say(response))
        self.student.refresh_from_db()
        self.assertIsNone(self.student.team_id)

    def test_an_instructor_cannot_plant_a_student_on_another_cohorts_team(self):
        client = self._client(self.rival)
        assigned = client.post(
            f'/api/users/{self.rival_student.user_id}/assign-team/',
            {'team_id': self.team.pk}, format='json')
        uploaded = client.post('/api/users/bulk-upload/', {
            'csv': 'username,role,team_id,password\n'
                   f'planted,Student,{self.team.pk},pw-123456\n'},
            format='json')

        self.assertRefused(assigned)
        self.assertRefused(uploaded)
        self.rival_student.refresh_from_db()
        self.assertIsNone(self.rival_student.team_id)
        self.assertFalse(User.objects.filter(username='planted').exists())

    def test_the_owner_still_administers_their_own_student(self):
        client = self._client(self.owner)
        patched = client.patch(
            f'/api/users/{self.student.user_id}/',
            {'password': 'a-new-password-1'}, format='json')
        assigned = client.post(
            f'/api/users/{self.student.user_id}/assign-team/',
            {'team_id': self.team.pk}, format='json')
        created = client.post('/api/users/', {
            'username': f'fresh-{id(self)}', 'role': 'Student'}, format='json')

        self.assertEqual(patched.status_code, 200, say(patched))
        self.assertEqual(assigned.status_code, 200, say(assigned))
        self.assertEqual(created.status_code, 201, say(created))

    def test_an_admin_still_changes_a_role(self):
        response = self._client(self.admin).patch(
            f'/api/users/{self.rival.user_id}/', {'role': 'admin'},
            format='json')

        self.assertEqual(response.status_code, 200, say(response))

    def test_a_failed_bulk_row_does_not_return_the_exception_text(self):
        with mock.patch('core.views.core.User.objects.create',
                        side_effect=RuntimeError(SECRET)), \
                self.assertLogs('core.views.core', 'ERROR') as logs:
            response = self._client(self.owner).post('/api/users/bulk-upload/', {
                'csv': 'username,role,team_id,password\nrow1,Student,,\n'},
                format='json')

        self.assertNotIn('users_email_key', str(response.data), say(response))
        self.assertEqual(response.data['errors'][0].get('code'),
                         'account_row_failed')
        self.assertIn('users_email_key', '\n'.join(logs.output))


class InventoryBlindSpotTests(TestCase):
    """The detector reads source; a bare model viewset has none to read."""

    def test_a_bare_model_viewset_over_a_lifecycle_model_is_flagged(self):
        from rest_framework import viewsets
        from core.services.route_inventory import generic_lifecycle_writer

        class WritableTeams(viewsets.ModelViewSet):
            queryset = Team.objects.all()

        class ReadableTeams(viewsets.ReadOnlyModelViewSet):
            queryset = Team.objects.all()

        class WritableCourses(viewsets.ModelViewSet):
            queryset = Course.objects.all()

        self.assertTrue(generic_lifecycle_writer(WritableTeams))
        self.assertFalse(generic_lifecycle_writer(ReadableTeams))
        self.assertFalse(generic_lifecycle_writer(WritableCourses))

    def test_no_registered_writable_viewset_sits_on_a_lifecycle_model(self):
        from core.services.route_inventory import (
            generic_lifecycle_writer, mutating_routes)
        from django.utils.module_loading import import_string
        offenders = sorted({
            entry['view'] for entry in mutating_routes().values()
            if generic_lifecycle_writer(import_string(entry['view']))
            and not entry['uses_boundary'] and not entry['exempt']})
        self.assertEqual(offenders, [])

