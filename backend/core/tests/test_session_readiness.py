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
    def test_the_endpoint_requires_an_instructor(self):
        from django.test import Client
        from core.authentication import create_access_token
        student_token = create_access_token(self.students[0])
        client = Client(HTTP_AUTHORIZATION=f'Bearer {student_token}',
                        SERVER_NAME='localhost')
        response = client.get(
            f'/api/games/{self.game.id}/instructor/session-readiness/')
        self.assertEqual(response.status_code, 403)

    def test_the_endpoint_returns_the_same_contract(self):
        from django.test import Client
        from core.authentication import create_access_token
        instructor = User.objects.create(
            username=f'sr-inst-{id(self)}', role='instructor',
            email=f'i{id(self)}@example.invalid')
        self.sign_in(self.students[0])
        client = Client(HTTP_AUTHORIZATION=f'Bearer {create_access_token(instructor)}',
                        SERVER_NAME='localhost')
        response = client.get(
            f'/api/games/{self.game.id}/instructor/session-readiness/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['roster']['expected_participants'], 3)
        self.assertEqual(body['sessions']['authenticated'], 1)
        self.assertEqual(body['sessions']['missing'], 2)
        self.assertFalse(body['ready'])
