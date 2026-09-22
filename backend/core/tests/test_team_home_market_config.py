"""W-CE-21 — a home market set in Team Configuration is where the team starts.

The walkthrough of 2026-09-22 set team 1's home market to Africa in the
console's Team Configuration panel; the save answered 200, the sidebar said
*AURORA DEVICES · AFRICA*, and the student's Market Strategy page then showed
Africa as **Not Entered**, North America as the only active market ("Export
from Home Market"), and North America at cultural distance VERY_HIGH.

Cause: ``PUT /api/games/<id>/instructor/team-config/`` wrote ``Team.home_market``
and nothing else.  The starting state — the round-0 ``TeamMarketPresence``,
the starter products' ``TeamProductMarket`` rows, ``TeamMarketCompliance`` and
every round-0 result row — had already been built by ``create_game`` against
the profile's authored market, and ``bootstrap_round_zero`` reads the home
market from the presence row, not from the team.  Two fields that must agree
were left disagreeing, and every screen that compares them (cultural distance
from ``Team.home_market`` to each presence; "is home market" against the
presence list) reported the contradiction faithfully.

These tests drive the real routes: create through ``POST /api/games/create/``,
configure through the team-config route, then read what the student reads.
The invariant asserted is the strongest one available: a team re-homed through
the console starts **exactly** as a team created with that home market in the
first place (``create_game(home_market_overrides=...)``, the path the console's
own Create Game form uses when the instructor picks markets there).
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import DecisionSubmission, Round, TeamMember, User
from core.models.cc31_models import TeamMarketCompliance
from core.models.core import Game, Team
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    LeaderboardEntry, RoundResultMarketRevenue, RoundResultPerformanceIndex,
    RoundResultProductMarket,
)
from core.models.scenario import Scenario
from core.models.team_state import TeamMarketPresence, TeamProductMarket
from core.tests.test_game_creation_paths import starting_state

SCENARIO = (Path(__file__).resolve().parents[2] / 'scenarios'
            / 'consumer_electronics_2026.yaml')
HEAT_SIZE = 8
AUTHORED_HOME = 'NA'   # every Consumer Electronics profile authors NA
CHOSEN_HOME = 'AFR'    # what the walkthrough instructor picked


class _HomeMarketFixture(TestCase):

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_superuser(
            'w-ce-21', 'w-ce-21@example.com', 'x')
        call_command('load_scenario', file=str(SCENARIO), verbosity=0)
        cls.scenario = Scenario.objects.order_by('-id').first()
        cls.instructor = User.objects.create(
            username='w-ce-21-instructor', role='instructor',
            password_hash='x')
        cls.student = User.objects.create(
            username='w-ce-21-student', role='student', password_hash='x')
        DjangoUser.objects.create(
            id=cls.student.user_id, username='w-ce-21-student-auth')

    def setUp(self):
        self.as_instructor = APIClient()
        self.as_instructor.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.instructor)}')
        self.as_student = APIClient()
        self.as_student.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')

    # -- the real routes ------------------------------------------------------

    def create_game(self, name, home_markets=None):
        payload = {'scenario_id': self.scenario.id, 'num_teams': HEAT_SIZE,
                   'name': name}
        if home_markets is not None:
            payload['home_markets'] = home_markets
        response = self.as_instructor.post(
            '/api/games/create/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return Game.objects.get(pk=response.json()['game_id'])

    def team_config(self, game):
        response = self.as_instructor.get(
            f'/api/games/{game.id}/instructor/team-config/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def save_team_config(self, game, teams):
        return self.as_instructor.put(
            f'/api/games/{game.id}/instructor/team-config/',
            {'teams': teams}, format='json')

    def set_home_market(self, game, team, code):
        """What the console's Save Configuration button sends."""
        config = self.team_config(game)
        payload = [{'team_id': row['team_id'],
                    'home_market_code': (code if row['team_id'] == team.id
                                         else row['home_market_code'])}
                   for row in config['teams']]
        response = self.save_team_config(game, payload)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def first_team(self, game):
        team = Team.objects.filter(game=game).order_by('id').first()
        TeamMember.objects.get_or_create(
            team=team, user_id=self.student.user_id)
        return team

    def strategy_context(self, game, team):
        response = self.as_student.get(
            f'/api/games/{game.id}/teams/{team.id}/context/strategy/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def talent_allocation_context(self, game, team):
        response = self.as_student.get(
            f'/api/games/{game.id}/teams/{team.id}/context/talent-allocation/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    # -- what the student would see ------------------------------------------

    def assert_starts_at_home(self, game, team, code):
        """The home market and the starting presence are the same market."""
        team.refresh_from_db()
        self.assertEqual(team.home_market.code, code)

        markets = {m['code']: m for m in
                   self.strategy_context(game, team)['markets']}
        self.assertTrue(markets[code]['is_home_market'])
        self.assertEqual(markets[code]['entry_status'], 'active',
                         f'{code} is the home market but the student sees it '
                         f'as {markets[code]["entry_status"]!r}')
        for other, row in markets.items():
            if other != code:
                self.assertFalse(row['is_home_market'], other)
                self.assertEqual(row['entry_status'], 'not_entered', other)

        active = self.talent_allocation_context(game, team)['markets']
        self.assertEqual([m['code'] for m in active], [code])
        self.assertEqual(active[0]['distance_level'], 'HOME')
        self.assertTrue(active[0]['is_home_market'])

        # And the rows behind the screens agree with each other.
        self.assertEqual(
            list(TeamMarketPresence.objects.filter(team=team).values_list(
                'market__code', 'status', 'established_round')),
            [(code, 'active', 0)])
        self.assertEqual(
            set(TeamProductMarket.objects.filter(
                team_product__team=team).values_list('market__code', flat=True)),
            {code})
        self.assertEqual(
            list(TeamMarketCompliance.objects.filter(team=team).values_list(
                'market__code', flat=True)),
            [code])
        self.assertEqual(
            set(RoundResultProductMarket.objects.filter(
                team=team, round_number=0).values_list(
                    'market__code', flat=True)),
            {code})
        revenue = {row.market.code: row for row in
                   RoundResultMarketRevenue.objects.filter(
                       team=team, round_number=0).select_related('market')}
        self.assertGreater(revenue[code].local_revenue, 0)
        for other, row in revenue.items():
            if other != code:
                self.assertEqual(row.local_revenue, 0, other)
        adopted = set(RoundResultAdoption.objects.filter(
            team=team, round_number=0, new_adopters__gt=0,
        ).values_list('market__code', flat=True))
        self.assertEqual(adopted, {code})

    def assert_round_zero_parity(self, game):
        """R22: every team opens on the scenario base index, joint first."""
        self.assertEqual(
            set(RoundResultPerformanceIndex.objects.filter(
                game=game, round_number=0).values_list(
                    'index_value', flat=True)),
            {self.scenario.performance_index_base})
        self.assertEqual(
            set(LeaderboardEntry.objects.filter(
                game=game, round_number=0).values_list('rank', flat=True)),
            {1})
        self.assertEqual(
            LeaderboardEntry.objects.filter(game=game, round_number=0).count(),
            HEAT_SIZE)


class TeamConfigHomeMarketTests(_HomeMarketFixture):

    def test_the_walkthrough_sequence_starts_the_team_in_its_home_market(self):
        """Create → Team Configuration: Africa → Save → student's screens."""
        game = self.create_game('W-CE-21 heat')
        team = self.first_team(game)
        self.assert_starts_at_home(game, team, AUTHORED_HOME)

        saved = self.set_home_market(game, team, CHOSEN_HOME)
        self.assertEqual(
            next(row for row in saved['teams']
                 if row['team_id'] == team.id)['home_market_code'],
            CHOSEN_HOME)

        self.assert_starts_at_home(game, team, CHOSEN_HOME)
        self.assert_round_zero_parity(game)

    def test_a_re_homed_team_starts_exactly_as_one_created_there(self):
        """The console's two ways of choosing a home market agree.

        The Create Game form can pass the market at creation
        (``home_markets`` → ``create_game(home_market_overrides=...)``); Team
        Configuration sets it afterwards.  A team must start identically
        either way — the same presence, products, compliance row and round-0
        results — or the two routes build two different games from one
        choice.
        """
        configured = self.create_game('W-CE-21 configured afterwards')
        team = self.first_team(configured)
        profile = team.firm_starter_profile.profile_name
        self.set_home_market(configured, team, CHOSEN_HOME)

        at_creation = self.create_game(
            'W-CE-21 chosen at creation',
            home_markets=[CHOSEN_HOME] + [AUTHORED_HOME] * (HEAT_SIZE - 1))

        self.assertEqual(
            starting_state(configured)['teams'][profile],
            starting_state(at_creation)['teams'][profile],
            'a team re-homed through Team Configuration starts differently '
            'from a team created with that home market')
        self.assertEqual(starting_state(configured), starting_state(at_creation))

    def test_teams_whose_home_market_did_not_change_are_untouched(self):
        """Re-homing one team must not move any other team's starting state.

        A save that changes nothing (the console re-sends every row) leaves
        the starting state byte-identical.
        """
        game = self.create_game('W-CE-21 untouched')
        team = self.first_team(game)
        others = Team.objects.filter(game=game).exclude(pk=team.pk)
        before = starting_state(game)

        config = self.team_config(game)
        unchanged = self.save_team_config(game, [
            {'team_id': row['team_id'],
             'home_market_code': row['home_market_code']}
            for row in config['teams']])
        self.assertEqual(unchanged.status_code, 200, unchanged.content)
        self.assertEqual(starting_state(game), before)

        self.set_home_market(game, team, CHOSEN_HOME)
        after = starting_state(game)
        for other in others:
            name = other.firm_starter_profile.profile_name
            self.assertEqual(after['teams'][name], before['teams'][name], name)
        self.assertNotEqual(
            after['teams'][team.firm_starter_profile.profile_name],
            before['teams'][team.firm_starter_profile.profile_name])

    def test_a_change_after_activation_but_before_any_submission(self):
        """The route allows changes until the first round-1 submission.

        The walkthrough saved before activating; an instructor who activates
        first and configures second must get the same result, with round 1
        left open.
        """
        game = self.create_game('W-CE-21 activated first')
        team = self.first_team(game)
        activated = self.as_instructor.post(f'/api/games/{game.id}/activate/')
        self.assertEqual(activated.status_code, 200, activated.content)

        self.set_home_market(game, team, CHOSEN_HOME)
        self.assert_starts_at_home(game, team, CHOSEN_HOME)
        self.assert_round_zero_parity(game)

        game.refresh_from_db()
        self.assertEqual((game.status, game.current_round), ('active', 1))
        self.assertEqual(
            Round.objects.get(game=game, round_number=1).status, 'open')
        self.assertEqual(
            Round.objects.get(game=game, round_number=0).status, 'processed')

    def test_changing_back_and_forth_leaves_no_trace(self):
        game = self.create_game('W-CE-21 round trip')
        team = self.first_team(game)
        before = starting_state(game)
        self.set_home_market(game, team, CHOSEN_HOME)
        self.set_home_market(game, team, AUTHORED_HOME)
        self.assertEqual(starting_state(game), before)
        self.assert_starts_at_home(game, team, AUTHORED_HOME)

    def test_refused_once_a_round_one_submission_exists(self):
        game = self.create_game('W-CE-21 locked')
        team = self.first_team(game)
        self.assertEqual(
            self.as_instructor.post(f'/api/games/{game.id}/activate/')
            .status_code, 200)
        DecisionSubmission.objects.create(
            team=team, round=Round.objects.get(game=game, round_number=1),
            status='draft')
        before = starting_state(game)

        config = self.team_config(game)
        self.assertTrue(config['locked'])
        response = self.save_team_config(game, [
            {'team_id': row['team_id'],
             'home_market_code': (CHOSEN_HOME if row['team_id'] == team.id
                                  else row['home_market_code'])}
            for row in config['teams']])
        # A LifecyclePrecondition, as before this repair: 400 with the code.
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['code'], 'round_1_started')
        self.assertEqual(starting_state(game), before)
        self.assert_starts_at_home(game, team, AUTHORED_HOME)
