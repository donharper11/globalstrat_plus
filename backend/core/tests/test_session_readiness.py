"""CRV2-07 — session readiness is not roster membership.

The addendum claimed "all 96 sessions visible in instructor readiness" from a
dashboard response listing 24 teams and 293 enrolled members, while the primary
artifact recorded that same readiness request returning 403 with zero visible
members. An enrollment count answers "who is in this class"; opening a round
needs "who is signed in and working". These tests pin the difference.

Active is `UserSession.active_qs`: no `logout_at`, `last_seen_at` within
`IDLE_TIMEOUT_MINUTES`. That definition is the model's and is not restated here.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.models import Game, Scenario, Team, User
from core.models.auth_models import UserSession
from core.models.course import Course, Enrollment, Section
from core.models.scenario import FirmStarterProfile, MarketDefinition
from core.services.session_readiness import readiness


class ReadinessFixture(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username=f'own-sr-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Readiness {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Readiness game', current_round=1,
            status='active', created_by=owner)
        self.other_game = Game.objects.create(
            scenario=self.scenario, name='Other cohort', current_round=1,
            status='active', created_by=owner)
        self.team = Team.objects.create(
            game=self.game, name='Alpha', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        course = Course.objects.create(course_code=f'C{id(self) % 9999}',
                                       course_name='C', is_active=True)
        self.section = Section.objects.create(
            course=course, section_code=f'S{id(self) % 9999}',
            section_name='S', is_active=True, created_at=timezone.now())
        # The game must name its section, or `instructor_can_access_game`
        # reads it as having no cohort recorded and treats it as unowned --
        # which made an ownership test pass a stranger with 200.
        self.game.section_id = self.section.section_id
        self.game.save(update_fields=['section_id'])

        # Three expected students, as the acceptance walkthrough requires.
        self.students = []
        for n in range(3):
            user = User.objects.create(
                username=f'sr-student-{n}-{id(self)}', role='student',
                email=f'sr{n}-{id(self)}@example.invalid', team_id=self.team.id)
            Enrollment.objects.create(
                user_id=user.user_id, section=self.section,
                team_id=self.team.id, is_active=True,
                enrolled_at=timezone.now())
            self.students.append(user)

    def sign_in(self, user, game=None, minutes_ago=0, logged_out=False):
        now = timezone.now()
        return UserSession.objects.create(
            user_id=user.user_id, username=user.username, role='student',
            game_id=(game or self.game).id, team_id=self.team.id,
            login_at=now - timezone.timedelta(minutes=minutes_ago + 1),
            last_seen_at=now - timezone.timedelta(minutes=minutes_ago),
            logout_at=now if logged_out else None)


class TheContract(ReadinessFixture):
    def test_roster_and_sessions_are_named_separately(self):
        state = readiness(self.game)
        self.assertEqual(state['roster']['expected_participants'], 3)
        self.assertEqual(state['sessions']['authenticated'], 0)
        self.assertIn('roster', state)
        self.assertIn('sessions', state)

    def test_two_of_three_authenticated_is_not_ready(self):
        self.sign_in(self.students[0])
        self.sign_in(self.students[1])
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 2)
        self.assertEqual(state['sessions']['missing'], 1)
        self.assertFalse(state['ready'])
        self.assertEqual(
            [p['user_id'] for p in state['missing_participants']],
            [self.students[2].user_id])

    def test_the_third_login_makes_the_cohort_ready(self):
        for student in self.students:
            self.sign_in(student)
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 3)
        self.assertEqual(state['sessions']['missing'], 0)
        self.assertTrue(state['ready'])
        self.assertEqual(state['blocking_reasons'], [])

    def test_an_idle_session_is_not_counted_active(self):
        self.sign_in(self.students[0])
        self.sign_in(self.students[1])
        self.sign_in(self.students[2],
                     minutes_ago=UserSession.IDLE_TIMEOUT_MINUTES + 5)
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 2)
        self.assertEqual(state['sessions']['missing'], 1)
        self.assertEqual(state['sessions']['stale'], 1)
        self.assertIn('idle', state['stale_participants'][0]['reason'])
        self.assertFalse(state['ready'])

    def test_a_logged_out_session_is_not_counted_active(self):
        self.sign_in(self.students[0])
        self.sign_in(self.students[1])
        self.sign_in(self.students[2], logged_out=True)
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 2)
        self.assertEqual(state['sessions']['stale'], 1)
        self.assertEqual(state['stale_participants'][0]['reason'], 'logged out')
        self.assertFalse(state['ready'])

    def test_another_cohorts_session_cannot_satisfy_this_one(self):
        for student in self.students:
            self.sign_in(student, game=self.other_game)
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 0)
        self.assertEqual(state['sessions']['missing'], 3)
        self.assertFalse(state['ready'])

    def test_duplicate_sessions_are_surfaced_not_double_counted(self):
        for student in self.students:
            self.sign_in(student)
        self.sign_in(self.students[0])          # a second browser
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 3,
                         'two sessions for one person is still one person')
        self.assertEqual(state['sessions']['duplicate_sessions'], 1)
        self.assertEqual(state['duplicate_participants'][0]['session_count'], 2)
        self.assertFalse(state['ready'],
                         'duplicates block ready rather than being absorbed')

    def test_a_session_for_someone_not_enrolled_is_reported_apart(self):
        stranger = User.objects.create(
            username=f'sr-stranger-{id(self)}', role='student',
            email=f'x{id(self)}@example.invalid')
        for student in self.students:
            self.sign_in(student)
        self.sign_in(stranger)
        state = readiness(self.game)
        self.assertEqual(state['sessions']['authenticated'], 3)
        self.assertEqual(state['sessions']['unexpected_active_sessions'], 1)
        self.assertTrue(state['ready'])


class TheEndpoint(ReadinessFixture):
    """Authorization, not merely the role.

    The first version of this class asserted that an instructor with no
    relationship to the game received 200, which pinned a bypass as intended
    behaviour: readiness carries participant names, team membership and who is
    signed in, missing, stale or duplicated, so any instructor could enumerate
    another cohort by changing the game id.

    Ownership is `instructor_can_access_game`, the rule already used by round
    control: the instructor who owns the course behind the game's section, with
    an unowned course visible to any instructor because `Course.instructor_id`
    is genuinely NULL for the live pilot. That helper is used, not reimplemented.
    """

    def client_for(self, user):
        from django.test import Client
        from core.authentication import create_access_token
        return Client(HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}',
                      SERVER_NAME='localhost')

    def instructor(self, label):
        return User.objects.create(
            username=f'sr-{label}-{id(self)}', role='instructor',
            email=f'{label}{id(self)}@example.invalid')

    def own_the_course(self, instructor_user):
        """Give this game's course an owner, making it no longer a pilot."""
        from core.models.course import Course
        course = Course.objects.get(course_id=self.section.course_id)
        course.instructor_id = instructor_user.user_id
        course.save(update_fields=['instructor_id'])

    def url(self, game=None):
        return (f'/api/games/{(game or self.game).id}'
                f'/instructor/session-readiness/')

    def test_a_student_is_refused(self):
        response = self.client_for(self.students[0]).get(self.url())
        self.assertEqual(response.status_code, 403)

    def test_the_owning_instructor_receives_the_contract(self):
        owner = self.instructor('owner')
        self.own_the_course(owner)
        self.sign_in(self.students[0])
        response = self.client_for(owner).get(self.url())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['roster']['expected_participants'], 3)
        self.assertEqual(body['sessions']['authenticated'], 1)
        self.assertEqual(body['sessions']['missing'], 2)
        self.assertFalse(body['ready'])

    def test_an_instructor_of_another_course_is_refused(self):
        owner = self.instructor('owner')
        self.own_the_course(owner)
        stranger = self.instructor('stranger')
        response = self.client_for(stranger).get(self.url())
        self.assertEqual(response.status_code, 403)

    def test_a_refused_request_discloses_no_readiness_body(self):
        """403 must not leak the thing it refused."""
        owner = self.instructor('owner')
        self.own_the_course(owner)
        for student in self.students:
            self.sign_in(student)
        stranger = self.instructor('stranger')
        response = self.client_for(stranger).get(self.url())
        self.assertEqual(response.status_code, 403)
        text = response.content.decode('utf-8', 'replace')
        for leaked in ('roster', 'sessions', 'authenticated', 'missing',
                       'ready', 'expected_participants'):
            self.assertNotIn(leaked, text)
        for student in self.students:
            self.assertNotIn(student.username, text)

    def test_an_unowned_pilot_course_stays_visible_to_any_instructor(self):
        """Pinned deliberately: Course.instructor_id is NULL for the pilot.

        Scoping strictly to owned courses would hide the live cohort from every
        instructor, so the shared helper permits it. That is the established
        behaviour and this test exists so a future change to it is a decision
        rather than an accident.
        """
        from core.models.course import Course
        course = Course.objects.get(course_id=self.section.course_id)
        self.assertIsNone(course.instructor_id)
        any_instructor = self.instructor('unrelated')
        response = self.client_for(any_instructor).get(self.url())
        self.assertEqual(response.status_code, 200)

    def test_ownership_of_one_game_does_not_grant_another(self):
        owner = self.instructor('owner')
        self.own_the_course(owner)
        # A second course and game the same instructor does not own.
        from core.models.course import Course, Section
        other_course = Course.objects.create(
            course_code=f'X{id(self) % 9999}', course_name='X',
            is_active=True, instructor_id=self.instructor('other').user_id)
        other_section = Section.objects.create(
            course=other_course, section_code=f'XS{id(self) % 9999}',
            section_name='XS', is_active=True, created_at=timezone.now())
        self.other_game.section_id = other_section.section_id
        self.other_game.save(update_fields=['section_id'])
        response = self.client_for(owner).get(self.url(self.other_game))
        self.assertEqual(response.status_code, 403)
