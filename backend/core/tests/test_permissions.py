"""
Tests for the 2026-07-15 permission lockdown.

Before this, DEFAULT_PERMISSION_CLASSES was AllowAny and 86 of 168 DRF view
classes declared no permission_classes, so they inherited it. A team's
briefing, results and financial reports were readable by anyone on the
internet with no credentials. Once authentication was required, any logged-in
student could still read any other team's data by editing the id in the URL —
so team scoping is enforced too.

The guards live in middleware deliberately: ~40 views take game_id/team_id
from the URL, and guarding each one individually means a new route is
unprotected until someone remembers.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Game, Round, Team, User
from core.models.course import Course, Enrollment, Section
from core.models.scenario import (
    FirmStarterProfile, MarketDefinition, Scenario,
)


class _Fixture(TestCase):
    """One game, two teams, a student in team A, and an instructor."""

    def setUp(self):
        self.client = APIClient()
        owner = DjangoUser.objects.create(username='owner')
        self.scenario = Scenario.objects.create(
            name='S', industry_label='T', description='d',
            starting_cash=1000, num_rounds=3,
        )
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1,
        )
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='P', description='d',
            home_market=self.market,
        )
        self.game = Game.objects.create(
            scenario=self.scenario, name='G', status='active',
            current_round=1, created_by=owner,
        )
        Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now(),
        )

        def team(name):
            return Team.objects.create(
                game=self.game, name=name, firm_starter_profile=profile,
                performance_index=100, cash_on_hand=1000, total_equity=1000,
                home_market=self.market,
            )

        self.my_team = team('Mine')
        self.other_team = team('Theirs')

        self.instructor = User.objects.create(
            username='prof', role='instructor', password_hash='x',
        )
        course = Course.objects.create(
            course_code='C1', course_name='C', is_active=True,
            instructor_id=self.instructor.user_id,
        )
        section = Section.objects.create(
            course=course, section_code='S1', is_active=True,
        )
        self.game.section_id = section.section_id
        self.game.save()

        self.student = User.objects.create(
            username='stu', student_id='stu', role='Student', password_hash='x',
        )
        Enrollment.objects.create(
            user_id=self.student.user_id, section=section,
            team_id=self.my_team.id, is_active=True,
        )

    def _auth(self, user):
        from core.authentication import create_access_token
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')

    def _url(self, team):
        return reverse('briefing-latest', args=[self.game.id, team.id])


class DefaultPermissionTests(_Fixture):
    """The project default must require a login."""

    def test_default_permission_is_authenticated(self):
        from django.conf import settings
        self.assertEqual(
            settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'],
            ['rest_framework.permissions.IsAuthenticated'],
        )

    def test_anonymous_cannot_read_a_briefing(self):
        """The original hole: this returned 200 to the open internet."""
        r = self.client.get(self._url(self.my_team))
        self.assertIn(r.status_code, (401, 403))

    def test_anonymous_cannot_read_round_status(self):
        r = self.client.get(reverse('round-status', args=[self.game.id]))
        self.assertIn(r.status_code, (401, 403))

    def test_login_stays_public(self):
        """Everything else requires a token; you can't have one before login."""
        r = self.client.post(reverse('auth-login'), {}, format='json')
        self.assertNotIn(r.status_code, (401, 403))


class TeamScopeTests(_Fixture):
    """A student may only reach their own team."""

    def test_student_can_read_own_team(self):
        self._auth(self.student)
        r = self.client.get(self._url(self.my_team))
        self.assertNotIn(r.status_code, (401, 403))

    def test_student_cannot_read_another_team(self):
        """The IDOR left behind once authentication alone was required."""
        self._auth(self.student)
        r = self.client.get(self._url(self.other_team))
        self.assertEqual(r.status_code, 403)

    def test_student_cannot_write_to_another_team(self):
        self._auth(self.student)
        r = self.client.post(
            reverse('briefing-read', args=[self.game.id, self.other_team.id, 1]),
            {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_instructor_can_read_any_team(self):
        self._auth(self.instructor)
        for team in (self.my_team, self.other_team):
            r = self.client.get(self._url(team))
            self.assertNotIn(r.status_code, (401, 403),
                             f'instructor blocked from team {team.id}')

    def test_unenrolled_student_is_refused(self):
        stranger = User.objects.create(
            username='stranger', role='Student', password_hash='x',
        )
        self._auth(stranger)
        r = self.client.get(self._url(self.my_team))
        self.assertEqual(r.status_code, 403)


class MiddlewareIdentityTests(_Fixture):
    """
    Middleware must resolve the caller itself.

    request.user is populated by Django's AuthenticationMiddleware from the
    session; this project authenticates with DRF JWT inside the view, so
    request.user is anonymous in middleware. Guards that trusted it were dead
    code that silently allowed everything — which is exactly what happened to
    the first version of the pause guard.
    """

    def test_auth_context_resolves_jwt_without_drf(self):
        from django.test import RequestFactory
        from core.authentication import create_access_token
        from core.utils.auth_context import (
            get_request_role, get_request_user_id,
        )

        token = create_access_token(self.student)
        request = RequestFactory().get('/api/anything/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        # No DRF involved, and request.user is not set at all.
        self.assertEqual(get_request_user_id(request), self.student.user_id)
        self.assertEqual(get_request_role(request), 'student')

    def test_auth_context_rejects_a_tampered_token(self):
        from django.test import RequestFactory
        from core.authentication import create_access_token
        from core.utils.auth_context import get_request_user_id

        token = create_access_token(self.student) + 'tampered'
        request = RequestFactory().get('/api/anything/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        self.assertIsNone(get_request_user_id(request))

    def test_pause_guard_blocks_a_route_isroundopen_does_not_cover(self):
        """
        The pause guard must cover the whole student write surface, not just
        the decision endpoints IsRoundOpen happens to protect.
        """
        self.game.status = 'paused'
        self.game.save()
        self._auth(self.student)
        r = self.client.post(
            reverse('briefing-read', args=[self.game.id, self.my_team.id, 1]),
            {}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertIn('paused', str(r.content).lower())
