"""The /api/users/ endpoint answers instead of raising.

`User.team_id` is a plain IntegerField -- the table is unmanaged and the column
was never declared as a relation -- but `UserSerializer` declared a `team`
field and sourced `team_name` from `team.team_name`, and the viewset called
`select_related('team')`. DRF raised ImproperlyConfigured before rendering
anything, so every read through the routed endpoint failed.

Found while writing the V2-026 disclosure contract, which walks every
serializer and could not instantiate this one.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import Client, TestCase
from django.utils import timezone

from core.authentication import create_access_token
from core.models import Game, Scenario, Team, User
from core.models.scenario import FirmStarterProfile, MarketDefinition
from core.serializers.core import UserSerializer


class UserEndpoint(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username=f'own-ue-{id(self)}')
        scenario = Scenario.objects.create(
            name=f'Users {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='S', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=scenario, name='Users game', current_round=1,
            status='active', created_by=owner)
        self.team = Team.objects.create(
            game=self.game, name='Alpha Team', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)
        self.instructor = User.objects.create(
            username=f'inst-{id(self)}', role='instructor', email='i@e.com')
        self.student = User.objects.create(
            username=f'stud-{id(self)}', role='student', email='s@e.com',
            team_id=self.team.id)
        token = create_access_token(self.instructor)
        self.client = Client(HTTP_AUTHORIZATION=f'Bearer {token}',
                             SERVER_NAME='localhost')

    def test_the_serializer_can_be_instantiated(self):
        """It raised ImproperlyConfigured before it could render a row."""
        self.assertIn('team_id', UserSerializer().fields)

    def test_the_list_endpoint_answers(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)

    def test_a_user_row_carries_its_team_id_and_name(self):
        rendered = UserSerializer(self.student).data
        self.assertEqual(rendered['team_id'], self.team.id)
        self.assertEqual(rendered['team_name'], 'Alpha Team')

    def test_a_user_with_no_team_renders_null_rather_than_failing(self):
        rendered = UserSerializer(self.instructor).data
        self.assertIsNone(rendered['team_id'])
        self.assertIsNone(rendered['team_name'])

    def test_a_dangling_team_id_renders_null_rather_than_failing(self):
        """The column is not a foreign key, so nothing enforces the target."""
        self.instructor.team_id = 10 ** 7
        self.instructor.save(update_fields=['team_id'])
        self.assertIsNone(UserSerializer(self.instructor).data['team_name'])
