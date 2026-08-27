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
        owner = DjangoUser.objects.create(username='participation-owner')
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
        self.instructor = User.objects.create(
            username='participation-instructor', role='instructor', password_hash='x',
        )
        self.student = User.objects.create(
            username='participation-student', role='student', password_hash='x',
        )
        django_student = DjangoUser.objects.create(
            id=self.student.user_id, username='participation-student-auth',
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
        self.assertEqual(OperatorAuditEvent.objects.count(), 0)

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
