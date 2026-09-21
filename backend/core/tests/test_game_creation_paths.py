"""V2-112 — every supported creation path builds the same game.

Two competition heats must be comparable, so a game built from one scenario has
to be the same game whichever registered entry point built it.  There are
exactly two entry points that create ``Game``/``Team`` rows in runtime code:

* ``POST /api/games/create/`` (``GameCreateView``) — what an instructor uses;
* ``manage.py initialize_game`` — what ``setup_test_game``, ``load_demo``,
  ``run_deadline_rehearsal``, the ``run_*_test`` commands and nearly every
  evidence harness in ``handoff_readiness_v2/evidence`` call.

Before this repair each carried its own copy of the builder.  The command read
only the ``alpha`` platform block and put both starter products on one
platform; the view built one platform per authored label (``alpha`` and
``beta``), zero-filled every unauthored feature, and so opened the same
scenario on different round-0 rows — and on a state the engine refuses to
score, because a team may hold one platform per generation.  Both now call
``core.services.game_creation.create_game``.  This test builds an 8-firm heat
by each path from each shipped scenario and asserts the two starting states are
identical — built, like ``EightFirmDistinctStarterTests``, from observable
state rather than from primary keys.

Team display names are drawn by an unseeded shuffle on both paths, so teams are
matched by starter profile (eight teams, eight distinct profiles — R28) and the
display name is replaced by a placeholder wherever it is embedded in a name.
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import Round, User
from core.models.cc31_models import TeamMarketCompliance
from core.models.cc32b_models import TeamOrganizationalStructure
from core.models.core import Game, Team
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    LeaderboardEntry, RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultProductMarket,
)
from core.models.scenario import Scenario
from core.models.team_state import (
    TeamMarketPresence, TeamPlatform, TeamPlatformFeatureLevel, TeamProduct,
    TeamProductMarket, TeamStrategyFeatureLevel,
)

SCENARIO_DIR = Path(__file__).resolve().parents[2] / 'scenarios'

SCENARIOS = (
    'consumer_electronics_2026.yaml',
    'clean_energy_tech_2026.yaml',
    'media_entertainment_2026.yaml',
)
HEAT_SIZE = 8


def _platform_state(platform, team_name):
    levels = tuple(sorted(
        (row.feature.code, str(row.current_level))
        for row in TeamPlatformFeatureLevel.objects.filter(
            team_platform=platform).select_related('feature')))
    return (platform.name.replace(team_name, '<team>'),
            platform.platform_generation.name, platform.status,
            platform.activated_round, levels)


def starting_state(game):
    """Everything creation writes, keyed by starter profile, free of ids."""
    state = {
        'game': (game.status, game.current_round, game.scenario.name),
        'rounds': tuple(Round.objects.filter(game=game).order_by(
            'round_number').values_list('round_number', 'status')),
        'teams': {},
    }
    for team in Team.objects.filter(game=game).select_related(
            'firm_starter_profile', 'home_market'):
        platforms = {
            p.id: _platform_state(p, team.name)
            for p in TeamPlatform.objects.filter(team=team).select_related(
                'platform_generation')}
        products = tuple(sorted(
            (product.name, product.positioning, product.status,
             product.created_round, platforms[product.team_platform_id],
             tuple(sorted(TeamProductMarket.objects.filter(
                 team_product=product).values_list(
                     'market__code', 'first_offered_round'))))
            for product in TeamProduct.objects.filter(team=team)))
        team.refresh_from_db()
        state['teams'][team.firm_starter_profile.profile_name] = {
            'team': (team.home_market.code, str(team.cash_on_hand),
                     str(team.total_debt), str(team.total_equity),
                     str(team.performance_index)),
            'platforms': tuple(sorted(platforms.values())),
            'products': products,
            'presence': tuple(sorted(TeamMarketPresence.objects.filter(
                team=team).values_list('market__code', 'entry_mode__code',
                                       'status', 'established_round'))),
            'compliance': tuple(sorted(
                (code, str(trust)) for code, trust in
                TeamMarketCompliance.objects.filter(team=team).values_list(
                    'market__code', 'current_trust_multiplier'))),
            'strategy': tuple(sorted(
                (code, str(level)) for code, level in
                TeamStrategyFeatureLevel.objects.filter(team=team).values_list(
                    'feature__code', 'current_level'))),
            'org': tuple(TeamOrganizationalStructure.objects.filter(
                team=team).values_list('current_structure__code', flat=True)),
            'r0_product_market': tuple(sorted(
                (name, code, str(sold), str(price), str(revenue), str(cogs))
                for name, code, sold, price, revenue, cogs in
                RoundResultProductMarket.objects.filter(
                    team=team, round_number=0).values_list(
                        'team_product__name', 'market__code', 'units_sold',
                        'retail_price', 'local_revenue', 'total_cogs'))),
            'r0_adoption': tuple(sorted(
                (segment, code, str(fit), str(adopters), str(share))
                for segment, code, fit, adopters, share in
                RoundResultAdoption.objects.filter(
                    team=team, round_number=0).values_list(
                        'segment__name', 'market__code', 'fit_score',
                        'new_adopters', 'team_share_pct'))),
            'r0_financials': tuple(
                tuple(str(v) for v in row) for row in
                RoundResultFinancials.objects.filter(
                    team=team, round_number=0).values_list(
                        'total_revenue', 'total_cogs', 'net_income',
                        'cash_closing', 'total_equity', 'share_price')),
            'r0_index': tuple(
                str(v) for v in RoundResultPerformanceIndex.objects.filter(
                    team=team, round_number=0).values_list(
                        'index_value', flat=True)),
            'r0_rank': tuple(LeaderboardEntry.objects.filter(
                team=team, round_number=0).values_list('rank', flat=True)),
        }
    return state


class CreationPathsConvergeTests(TestCase):
    """The command and the view build the same heat from the same scenario."""

    maxDiff = None

    def setUp(self):
        get_user_model().objects.create_superuser(
            'v2-112', 'v2-112@example.com', 'x')
        instructor = User.objects.create(
            username='v2-112-instructor', role='instructor', password_hash='x')
        self.client_ = APIClient()
        self.client_.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(instructor)}')

    def _by_command(self, scenario):
        call_command('initialize_game', scenario=scenario.id, teams=HEAT_SIZE,
                     name=f'V2-112 command {scenario.id}', verbosity=0)
        return Game.objects.order_by('-id').first()

    def _by_view(self, scenario):
        response = self.client_.post('/api/games/create/', {
            'scenario_id': scenario.id, 'num_teams': HEAT_SIZE,
            'name': f'V2-112 view {scenario.id}'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        game = Game.objects.get(pk=response.json()['game_id'])
        # The view leaves the game in `setup` for the instructor to activate;
        # the command activates. Activate through the registered route so the
        # comparison covers the lifecycle state as well as the field.
        activated = self.client_.post(f'/api/games/{game.id}/activate/')
        self.assertEqual(activated.status_code, 200, activated.content)
        game.refresh_from_db()
        return game

    def test_both_paths_build_the_same_starting_state(self):
        for filename in SCENARIOS:
            with self.subTest(scenario=filename):
                call_command('load_scenario',
                             file=str(SCENARIO_DIR / filename), verbosity=0)
                scenario = Scenario.objects.order_by('-id').first()

                by_command = starting_state(self._by_command(scenario))
                by_view = starting_state(self._by_view(scenario))

                self.assertEqual(len(by_command['teams']), HEAT_SIZE)
                self.assertEqual(len(by_view['teams']), HEAT_SIZE)
                for profile_name in sorted(by_view['teams']):
                    self.assertEqual(
                        by_command['teams'][profile_name],
                        by_view['teams'][profile_name],
                        f'{filename}: {profile_name!r} starts differently '
                        f'depending on which path created the game')
                self.assertEqual(by_command, by_view)

    def test_every_path_builds_a_game_the_engine_will_score(self):
        """One non-retired platform per team and generation, on both paths.

        ``_run_phase_1`` refuses a round while ``duplicate_platform_state`` is
        non-empty ("a team develops one platform per generation", V2-046 /
        V2-047). The view's own copy of the builder created an ``alpha`` and a
        ``beta`` platform on the same starting generation for every team, so a
        heat created through the instructor route could never have resolved
        round 1. Whatever the single builder does, it must not do that.
        """
        from core.services.rd_costs import duplicate_platform_state

        call_command('load_scenario',
                     file=str(SCENARIO_DIR / SCENARIOS[0]), verbosity=0)
        scenario = Scenario.objects.order_by('-id').first()
        for label, build in (('command', self._by_command),
                             ('view', self._by_view)):
            with self.subTest(path=label):
                game = build(scenario)
                self.assertEqual(
                    duplicate_platform_state(game), [],
                    f'{label}: the engine refuses to score this game')
                for team in Team.objects.filter(game=game):
                    self.assertEqual(
                        TeamPlatform.objects.filter(team=team).count(), 1)
