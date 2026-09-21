"""
Initialize a new game from a scenario with starter profiles.

Usage: python manage.py initialize_game --scenario <id> --teams <count> [--name "Game Name"]
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User as AuthUser

from core.models.core import Round
from core.models.scenario import PlatformGenerationDefinition, Scenario
from core.models.team_state import (
    TeamMarketPresence, TeamPlatformFeatureLevel, TeamProduct,
    TeamProductMarket,
)
from core.services.game_creation import (
    GameCreationError, create_game, resolve_home_markets,
)


class Command(BaseCommand):
    help = 'Create a new game from a scenario and initialize teams with starter profiles'

    def add_arguments(self, parser):
        parser.add_argument('--scenario', type=int, required=True, help='Scenario ID')
        parser.add_argument('--teams', type=int, required=True, help='Number of teams to create')
        parser.add_argument('--name', type=str, default=None, help='Game name')
        parser.add_argument(
            '--home_markets', type=str, default=None,
            help='Comma-separated market codes for teams (e.g., na,ea,eu,sa,wa). '
                 'Teams are assigned in order. If not provided, uses profile home_market.',
        )

    def handle(self, *args, **options):
        scenario_id = options['scenario']
        num_teams = options['teams']
        game_name = options['name']
        home_markets_arg = options.get('home_markets')

        # 1. Load scenario
        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            raise CommandError(
                f"Error: Scenario with ID {scenario_id} not found. "
                "Create a scenario first or run CC-8 seed data."
            )

        if not game_name:
            game_name = f"{scenario.name} Game"

        # Get admin user for created_by
        admin_user = AuthUser.objects.filter(is_superuser=True).first()
        if not admin_user:
            raise CommandError("No superuser found. Create one first: manage.py createsuperuser")

        # 2-5b. Build the game. There is ONE builder and the instructor's
        # `POST /api/games/create/` calls the same one (V2-112): this command
        # and the view used to carry a copy of the loop each, and the copies had
        # drifted into building different games from the same scenario.
        try:
            home_market_overrides = resolve_home_markets(
                scenario,
                [c for c in (home_markets_arg or '').split(',') if c.strip()])
            game, created = create_game(
                scenario, num_teams, name=game_name, created_by=admin_user,
                home_market_overrides=home_market_overrides)
        except GameCreationError as exc:
            raise CommandError(str(exc))

        starting_gen = PlatformGenerationDefinition.objects.filter(
            scenario=scenario, is_starting_platform=True).order_by('id').first()
        default_entry_mode = None
        teams_created = []
        for row in created:
            team, home_market = row['team'], row['home_market']
            presence = TeamMarketPresence.objects.filter(
                team=team).select_related('entry_mode').first()
            if presence is not None:
                default_entry_mode = presence.entry_mode
            features_initialized = TeamPlatformFeatureLevel.objects.filter(
                team_platform__team=team).count()
            products_info = []
            for product in TeamProduct.objects.filter(team=team).order_by('id'):
                offered = TeamProductMarket.objects.filter(
                    team_product=product).select_related('market').first()
                products_info.append(
                    f"{product.name} ({product.positioning}, "
                    f"{offered.market.name if offered else 'no market'})")
            teams_created.append({
                'team': team,
                'profile': row['profile'],
                'features_initialized': features_initialized,
                'products': products_info,
                'home_market': home_market.name,
                'cash': team.cash_on_hand,
                'debt': team.total_debt,
            })

        # 5c. Open Round 1 for play
        from django.utils import timezone
        round_1 = Round.objects.get(game=game, round_number=1)
        round_1.status = 'open'
        round_1.opened_at = timezone.now()
        round_1.save()
        game.current_round = 1
        game.status = 'active'
        game.save()

        # 6. Print summary
        self.stdout.write(f'\nGame "{game.name}" created (ID: {game.id})')
        self.stdout.write(f'Scenario: {scenario.name}')
        self.stdout.write('Teams:')
        for info in teams_created:
            t = info['team']
            p = info['profile']
            self.stdout.write(f'  {t.name} — Profile: {p.profile_name}')
            self.stdout.write(
                f'    Platform: {starting_gen.name} (active), '
                f'{info["features_initialized"]} features initialized'
            )
            for prod in info['products']:
                self.stdout.write(f'    Products: {prod}')
            entry_label = default_entry_mode.name if default_entry_mode else 'N/A'
            self.stdout.write(f'    Home market: {info["home_market"]} ({entry_label})')
            self.stdout.write(
                f'    Cash: ${float(info["cash"]):,.0f} | '
                f'Debt: ${float(info["debt"]):,.0f} | '
                f'Index: {t.performance_index}'
            )
            self.stdout.write('')

        self.stdout.write(
            f'Rounds: 0 (processed) | 1 (open) | 2-{scenario.num_rounds} (pending)'
        )
        self.stdout.write(self.style.SUCCESS(
            'Round 0 results generated. Round 1 is open. Ready for play.'
        ))
