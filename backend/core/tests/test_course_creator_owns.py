"""Whoever creates a course owns it (R46, V2-133's open question).

The console creates a course with a code, a name and nothing else, so every
course it made had no instructor of record and -- under the adopted rule --
stayed shared with every instructor until an admin assigned one. The ownership
checks V2-133 added therefore protected nothing the console had just created.

Every test drives the registered route with a signed JWT. `POST /api/courses/`
is the only course-creation path an instructor can reach; the three management
commands that create a course already name its instructor.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import AuthorizationRefusalEvent, User
from core.models.core import Game
from core.models.course import Course, Enrollment, Section
from core.tests.test_operator_concurrency import build_minimal_game

REFUSAL_CODE = 'cohort_belongs_to_another_instructor'


def say(response):
    body = getattr(response, 'data', None)
    if body is None:
        body = response.content[:300]
    return f'{response.status_code} {body!r}'


class CourseCreatorBase(TestCase):

    def _user(self, name, role='instructor'):
        return User.objects.create(
            username=f'{name}-{id(self)}', role=role, password_hash='x')

    def _client(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def setUp(self):
        self.alice = self._user('alice')
        self.bob = self._user('bob')
        self.admin = self._user('root', role='admin')

    def _create(self, user, code, **extra):
        """Exactly what `InstructorDashboard.js` sends, plus any extras."""
        body = {'course_code': code, 'course_name': f'Course {code}',
                'is_active': True}
        body.update(extra)
        return self._client(user).post('/api/courses/', body, format='json')

    def assertRefused(self, response):
        self.assertEqual(response.status_code, 403, say(response))
        self.assertEqual(response.data.get('code'), REFUSAL_CODE, say(response))
        self.assertTrue(response.data.get('request_id'), say(response))


class InstructorCreatedCourseTests(CourseCreatorBase):

    def test_the_creator_is_the_instructor_of_record_from_creation(self):
        response = self._create(self.alice, 'R46A')

        self.assertEqual(response.status_code, 201, say(response))
        self.assertEqual(response.data['instructor_id'], self.alice.user_id)
        self.assertEqual(
            Course.objects.get(course_code='R46A').instructor_id,
            self.alice.user_id)

    def test_an_instructor_cannot_create_a_course_for_someone_else(self):
        """The serializer accepts `instructor_id`; the actor decides it."""
        response = self._create(self.alice, 'R46B',
                                instructor_id=self.bob.user_id)

        self.assertEqual(response.status_code, 201, say(response))
        self.assertEqual(
            Course.objects.get(course_code='R46B').instructor_id,
            self.alice.user_id)

    def test_an_instructor_cannot_create_an_unowned_course(self):
        response = self._create(self.alice, 'R46C', instructor_id=None)

        self.assertEqual(response.status_code, 201, say(response))
        self.assertEqual(
            Course.objects.get(course_code='R46C').instructor_id,
            self.alice.user_id)

    def test_another_instructor_is_refused_on_the_new_course(self):
        course_id = self._create(self.alice, 'R46D').data['course_id']
        bob = self._client(self.bob)

        read = bob.get(f'/api/courses/{course_id}/')
        renamed = bob.patch(f'/api/courses/{course_id}/',
                            {'course_name': 'Taken'}, format='json')
        taken = bob.patch(f'/api/courses/{course_id}/',
                          {'instructor_id': self.bob.user_id}, format='json')
        section = bob.post('/api/sections/', {
            'course': course_id, 'section_code': 'PLANTED',
            'section_name': 'Planted', 'is_active': True}, format='json')
        deleted = bob.delete(f'/api/courses/{course_id}/')
        listed = bob.get('/api/courses/')

        for response in (read, renamed, taken, section, deleted):
            self.assertRefused(response)
        self.assertNotIn(course_id, {row['course_id'] for row in listed.data})
        course = Course.objects.get(pk=course_id)
        self.assertEqual(course.instructor_id, self.alice.user_id)
        self.assertEqual(course.course_name, 'Course R46D')
        self.assertFalse(Section.objects.filter(section_code='PLANTED').exists())
        # Four refused writes, each recorded; the refused read is not.
        self.assertEqual(AuthorizationRefusalEvent.objects.filter(
            actor_user_id=self.bob.user_id).count(), 4)

    def test_the_creator_and_an_admin_succeed_on_the_new_course(self):
        course_id = self._create(self.alice, 'R46E').data['course_id']

        for user in (self.alice, self.admin):
            client = self._client(user)
            read = client.get(f'/api/courses/{course_id}/')
            listed = client.get('/api/courses/')
            renamed = client.patch(
                f'/api/courses/{course_id}/',
                {'course_name': f'Renamed by {user.role}'}, format='json')

            self.assertEqual(read.status_code, 200, say(read))
            self.assertIn(course_id, {row['course_id'] for row in listed.data})
            self.assertEqual(renamed.status_code, 200, say(renamed))


class ConsoleFlowAfterCreationTests(CourseCreatorBase):
    """The console's next steps: a section, a roster, teams.

    Each of these routes carries a V2-133 ownership check. The creator must
    pass every one of them immediately, with no admin step in between, and the
    other instructor must be refused at every one.
    """

    def setUp(self):
        super().setUp()
        self.course_id = self._create(self.alice, 'R46F').data['course_id']
        created = self._client(self.alice).post('/api/sections/', {
            'course': self.course_id, 'section_code': 'S1',
            'section_name': 'Section one', 'is_active': True}, format='json')
        self.assertEqual(created.status_code, 201, say(created))
        self.section_id = created.data['section_id']
        game, teams = build_minimal_game(f'r46-{id(self)}')
        Game.objects.filter(pk=game.pk).update(section_id=self.section_id)
        self.team = teams[0]

    def _rename_team(self, client, name):
        return client.put('/api/team-management/', {
            'action': 'rename', 'team_id': self.team.pk, 'team_name': name},
            format='json')

    def _add_student(self, client, username):
        return client.post('/api/roster/', {
            'action': 'add', 'section_id': self.section_id,
            'student_id': username, 'display_name': username.title(),
            'email': f'{username}@example.edu'}, format='json')

    def test_the_creator_runs_the_whole_console_flow(self):
        alice = self._client(self.alice)

        section = alice.patch(f'/api/sections/{self.section_id}/',
                              {'max_teams': 6}, format='json')
        added = self._add_student(alice, f'ada-{id(self)}')
        roster = alice.get(f'/api/roster/?section_id={self.section_id}')
        teams = alice.get(
            f'/api/team-management/?section_id={self.section_id}')

        self.assertEqual(section.status_code, 200, say(section))
        self.assertEqual(added.status_code, 201, say(added))
        self.assertEqual(roster.status_code, 200, say(roster))
        renamed = self._rename_team(alice, 'Named by the creator')

        self.assertEqual(teams.status_code, 200, say(teams))
        self.assertEqual(renamed.status_code, 200, say(renamed))
        self.assertTrue(Enrollment.objects.filter(
            section_id=self.section_id, is_active=True).exists())

    def test_an_admin_runs_it_too(self):
        admin = self._client(self.admin)

        added = self._add_student(admin, f'grace-{id(self)}')
        roster = admin.get(f'/api/roster/?section_id={self.section_id}')
        teams = admin.get(
            f'/api/team-management/?section_id={self.section_id}')

        self.assertEqual(added.status_code, 201, say(added))
        self.assertEqual(roster.status_code, 200, say(roster))
        self.assertEqual(teams.status_code, 200, say(teams))

    def test_the_other_instructor_is_refused_at_every_step(self):
        bob = self._client(self.bob)

        section = bob.patch(f'/api/sections/{self.section_id}/',
                            {'max_teams': 1}, format='json')
        added = self._add_student(bob, f'mallory-{id(self)}')
        roster = bob.get(f'/api/roster/?section_id={self.section_id}')
        teams = bob.get(
            f'/api/team-management/?section_id={self.section_id}')

        renamed = self._rename_team(bob, 'Defaced')

        for response in (section, added, roster, teams, renamed):
            self.assertRefused(response)
        self.team.refresh_from_db()
        self.assertNotEqual(self.team.name, 'Defaced')
        self.assertFalse(Enrollment.objects.filter(
            section_id=self.section_id).exists())


class AdminCreatedCourseTests(CourseCreatorBase):

    def test_an_admin_course_with_no_named_instructor_stays_shared(self):
        response = self._create(self.admin, 'R46G')

        self.assertEqual(response.status_code, 201, say(response))
        course_id = response.data['course_id']
        self.assertIsNone(Course.objects.get(pk=course_id).instructor_id)
        # Shared means every instructor may open it, as before.
        for user in (self.alice, self.bob):
            read = self._client(user).get(f'/api/courses/{course_id}/')
            self.assertEqual(read.status_code, 200, say(read))

    def test_an_admin_may_name_the_instructor(self):
        response = self._create(self.admin, 'R46H',
                                instructor_id=self.bob.user_id)

        self.assertEqual(response.status_code, 201, say(response))
        course_id = response.data['course_id']
        self.assertEqual(Course.objects.get(pk=course_id).instructor_id,
                         self.bob.user_id)
        self.assertEqual(self._client(self.bob).get(
            f'/api/courses/{course_id}/').status_code, 200)
        self.assertRefused(
            self._client(self.alice).get(f'/api/courses/{course_id}/'))

    def test_existing_unowned_courses_are_not_reassigned(self):
        """R46: guessing an owner for a stored course would invent a fact."""
        stored = Course.objects.create(
            course_code=f'OLD{id(self) % 100000}', course_name='Stored',
            instructor_id=None, is_active=True)

        self._create(self.alice, 'R46I')
        touched = self._client(self.alice).patch(
            f'/api/courses/{stored.course_id}/',
            {'course_name': 'Stored, renamed'}, format='json')
        self._client(self.alice).post('/api/sections/', {
            'course': stored.course_id, 'section_code': 'OLD-S',
            'section_name': 'Old section', 'is_active': True}, format='json')

        self.assertEqual(touched.status_code, 200, say(touched))
        stored.refresh_from_db()
        self.assertIsNone(stored.instructor_id)
        self.assertEqual(self._client(self.bob).get(
            f'/api/courses/{stored.course_id}/').status_code, 200)
