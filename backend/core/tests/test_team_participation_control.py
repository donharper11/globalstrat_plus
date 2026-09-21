from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.engine.advance_round import close_round
from core.models import (
    DecisionSubmission, Game, OperatorAuditEvent, Round, Scenario, Team,
    TeamMember, User,
)
from core.models.scenario import FirmStarterProfile, MarketDefinition


class TeamParticipationControlTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create(
            username='participation-instructor', role='instructor', password_hash='x',
        )
        self.student = User.objects.create(
            username='participation-student', role='student', password_hash='x',
        )
        django_student = DjangoUser.objects.create(
            id=self.student.user_id, username='participation-student-auth',
        )
        # An explicit id as well, clear of both sequences: the student's auth
        # row carries the id of their `users` row, and an owner id drawn from
        # the `auth_user` sequence can be that same number (see
        # `FixtureSequenceAlignmentTests`).
        owner = DjangoUser.objects.create(
            id=self.student.user_id + 1_000_000, username='participation-owner')
        scenario = Scenario.objects.create(
            name='Participation', industry_label='Test', description='d',
            starting_cash=1000, num_rounds=2,
        )
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HOME', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1,
        )
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Starter', description='d',
            home_market=market, starting_cash=1000, starting_debt=0,
        )
        self.game = Game.objects.create(
            scenario=scenario, name='Participation game', current_round=1,
            status='active', created_by=owner,
        )
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now(),
        )
        self.team = Team.objects.create(
            game=self.game, name='Team One', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000,
        )
        TeamMember.objects.create(team=self.team, user=django_student)
        self.url = (
            f'/api/games/{self.game.id}/instructor/teams/'
            f'{self.team.id}/participation/'
        )

    def client_for(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def test_deactivate_requires_operator_reason_and_exact_confirmation(self):
        client = self.client_for(self.instructor)
        self.assertEqual(client.post(self.url, {
            'action': 'deactivate', 'reason': 'short',
            'confirmation': f'DEACTIVATE TEAM {self.team.id}',
        }, format='json').status_code, 400)
        self.assertEqual(client.post(self.url, {
            'action': 'deactivate', 'reason': 'Voluntary competition withdrawal',
            'confirmation': 'DEACTIVATE TEAM wrong',
        }, format='json').status_code, 400)

        self.team.refresh_from_db()
        self.assertEqual(self.team.participation_status, 'active')
        # GSP-CRV2-02: a refused attempt at a destructive action is recorded,
        # because "someone tried to withdraw a team and got the confirmation
        # token wrong" is exactly what an investigator needs to see. The empty
        # `after` is what stops the row implying anything happened.
        self.assertEqual(
            OperatorAuditEvent.objects.filter(outcome='committed').count(), 0)
        rejections = OperatorAuditEvent.objects.filter(outcome='rejected')
        self.assertEqual(rejections.count(), 2)
        for event in rejections:
            self.assertEqual(event.after, {})
            self.assertTrue(event.request_id)
            self.assertIn(event.conflict['code'],
                          {'reason_required', 'confirmation_required'})

    def test_student_cannot_operate_control(self):
        response = self.client_for(self.student).post(self.url, {
            'action': 'deactivate', 'reason': 'Voluntary competition withdrawal',
            'confirmation': f'DEACTIVATE TEAM {self.team.id}',
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_withdraw_and_reactivate_are_audited_and_reversible(self):
        client = self.client_for(self.instructor)
        response = client.post(self.url, {
            'action': 'deactivate', 'reason': 'Voluntary competition withdrawal',
            'confirmation': f'DEACTIVATE TEAM {self.team.id}',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.team.refresh_from_db()
        self.assertEqual(self.team.participation_status, 'withdrawn')
        event = OperatorAuditEvent.objects.get(action='team_deactivated')
        self.assertEqual(event.reason, 'Voluntary competition withdrawal')
        self.assertEqual(event.before['participation_status'], 'active')
        self.assertEqual(event.after['participation_status'], 'withdrawn')

        response = client.post(self.url, {
            'action': 'reactivate', 'reason': 'Withdrawal reversed by adjudication',
            'confirmation': f'REACTIVATE TEAM {self.team.id}',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.team.refresh_from_db()
        self.assertEqual(self.team.participation_status, 'active')
        self.assertIsNone(self.team.withdrawn_at)
        self.assertEqual(OperatorAuditEvent.objects.count(), 2)

    def test_withdrawn_team_cannot_write_and_is_not_defaulted_at_close(self):
        client = self.client_for(self.instructor)
        client.post(self.url, {
            'action': 'deactivate', 'reason': 'Voluntary competition withdrawal',
            'confirmation': f'DEACTIVATE TEAM {self.team.id}',
        }, format='json')
        student_response = self.client_for(self.student).post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/1/',
            {}, format='json',
        )
        self.assertEqual(student_response.status_code, 403)
        from core.engine.utils import RoundContext
        self.assertEqual(RoundContext(self.game, 1).teams, [])
        close_round(self.game.id)
        self.assertFalse(DecisionSubmission.objects.filter(
            team=self.team, round=self.round,
        ).exists())


class FixtureSequenceAlignmentTests(TestCase):
    """The fixture above must not depend on where two sequences happen to be.

    It gives the student's auth row the explicit id of their `users` row, and
    used to take the owner's auth id from the `auth_user` sequence. Sequences
    are not rolled back between tests, so whenever earlier tests on the same
    worker had left the two aligned, the owner took the very id the student
    was about to be given and one test of the class died in `setUp` with
    `auth_user_pkey` -- which is how the full suite first failed after two new
    test modules moved the counts. This forces the alignment.
    """

    def test_the_fixture_survives_aligned_sequences(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence('users', 'user_id'))")
            users_at = cursor.fetchone()[0]
            # setUp takes two `users` ids (instructor, then student). Leave
            # the `auth_user` sequence so that its next value is the student's
            # id, which is what the owner used to be given.
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('auth_user', 'id'), %s)",
                [users_at + 1])

        TeamParticipationControlTests.setUp(self)

        self.assertTrue(DjangoUser.objects.filter(
            id=self.student.user_id).exists())
