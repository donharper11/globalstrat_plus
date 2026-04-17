"""
Initialize a new game from a scenario with starter profiles.

Usage: python manage.py initialize_game --scenario <id> --teams <count> [--name "Game Name"]
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User as AuthUser

from core.models.scenario import (
    Scenario, ScenarioConfig, FeatureDefinition, PlatformGenerationDefinition,
    FirmStarterProfile, FirmStarterPlatformConfig, FirmStarterProduct,
    EntryModeDefinition, MarketDefinition,
)
from core.views.scenario_views import _get_company_names
from core.models.core import Game, Team, Round
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel,
    TeamProduct, TeamProductMarket,
    TeamMarketPresence, TeamStrategyFeatureLevel,
)
from core.models.cc31_models import TeamMarketCompliance
from core.models.cc32b_models import OrganizationalStructureType, TeamOrganizationalStructure


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

        # 2. Create Game
        game = Game.objects.create(
            scenario=scenario,
            name=game_name,
            current_round=0,
            status='setup',
            created_by=admin_user,
        )

        # 3. Get starter profiles (cycle through if fewer profiles than teams)
        profiles = list(FirmStarterProfile.objects.filter(scenario=scenario))
        if not profiles:
            raise CommandError(
                f"No FirmStarterProfiles found for scenario '{scenario.name}'. "
                "Create starter profiles first or run CC-8 seed data."
            )

        # Get starting platform generation
        starting_gen = PlatformGenerationDefinition.objects.filter(
            scenario=scenario, is_starting_platform=True,
        ).first()
        if not starting_gen:
            raise CommandError(
                f"No starting platform generation found for scenario '{scenario.name}'. "
                "Mark one PlatformGenerationDefinition as is_starting_platform=True."
            )

        # Get lowest-capital entry mode as default
        default_entry_mode = EntryModeDefinition.objects.filter(
            scenario=scenario,
        ).order_by('capital_requirement').first()

        # Get all strategy-layer features for initialization
        strategy_features = FeatureDefinition.objects.filter(
            scenario=scenario, layer='strategy',
        )

        # CC-31A: Resolve --home_markets if provided
        home_market_overrides = []
        if home_markets_arg:
            codes = [c.strip().upper() for c in home_markets_arg.split(',')]
            for code in codes:
                mkt = MarketDefinition.objects.filter(scenario=scenario, code__iexact=code).first()
                if not mkt:
                    raise CommandError(f"Market code '{code}' not found in scenario '{scenario.name}'")
                home_market_overrides.append(mkt)

        # 4. Create teams
        company_names = _get_company_names(scenario)
        teams_created = []
        for i in range(num_teams):
            profile = profiles[i % len(profiles)]
            starting_cash = profile.starting_cash if profile.starting_cash else scenario.starting_cash
            starting_debt = profile.starting_debt
            total_equity = starting_cash - starting_debt

            # CC-31A: Determine home market
            if home_market_overrides:
                assigned_home_market = home_market_overrides[i % len(home_market_overrides)]
            else:
                assigned_home_market = profile.home_market

            team_name = company_names[i] if i < len(company_names) else f"Team {i + 1}"
            team = Team.objects.create(
                game=game,
                name=team_name,
                firm_starter_profile=profile,
                home_market=assigned_home_market,
                performance_index=scenario.performance_index_base,
                cash_on_hand=starting_cash,
                total_debt=starting_debt,
                total_equity=total_equity,
            )

            # 4e. Create TeamPlatform for starting generation
            team_platform = TeamPlatform.objects.create(
                team=team,
                platform_generation=starting_gen,
                name=f"{team.name} Base Platform",
                status='active',
                activated_round=0,
            )

            # 4f. Create TeamPlatformFeatureLevel from starter config
            # Only use the primary (alpha) platform config — beta is for
            # the second starter product's platform if the profile has one.
            # Each team starts with one platform; max 5 features enforced.
            starter_configs = FirmStarterPlatformConfig.objects.filter(
                firm_starter_profile=profile,
                platform_label='alpha',
            )
            features_initialized = 0
            for config in starter_configs:
                _, created = TeamPlatformFeatureLevel.objects.get_or_create(
                    team_platform=team_platform,
                    feature=config.feature,
                    defaults={'current_level': config.starting_level},
                )
                if created:
                    features_initialized += 1

            # Only starter config features are created.
            # Max 5 features per platform — additional features must be
            # acquired through R&D investment during gameplay.

            # 4g/4h. Create TeamProduct + TeamProductMarket from starter products
            starter_products = FirmStarterProduct.objects.filter(
                firm_starter_profile=profile,
            )
            products_info = []
            for sp in starter_products:
                tp = TeamProduct.objects.create(
                    team=team,
                    team_platform=team_platform,
                    name=sp.product_name,
                    positioning=sp.positioning_label.lower().replace('-', '_').replace(' ', '_'),
                    created_round=0,
                )
                # Place product in team's home market (not the seed-data default)
                product_market = assigned_home_market if assigned_home_market else sp.market
                TeamProductMarket.objects.create(
                    team_product=tp,
                    market=product_market,
                    first_offered_round=0,
                )
                products_info.append(
                    f"{sp.product_name} ({sp.positioning_label}, {product_market.name})"
                )

            # 4i. Create TeamMarketPresence for home market
            home_market = assigned_home_market
            if default_entry_mode:
                TeamMarketPresence.objects.create(
                    team=team,
                    market=home_market,
                    entry_mode=default_entry_mode,
                    established_round=0,
                    initial_investment=0,
                    status='active',
                )

            # 4i-b. Initialize TeamMarketCompliance for home market (trust=1.0)
            TeamMarketCompliance.objects.create(
                game=game,
                team=team,
                market=home_market,
                cumulative_investment=0,
                compliance_level=0,
                current_trust_multiplier=1.0,
                effective_rd_multiplier=1.0,
                effective_commercial_multiplier=1.0,
                effective_operations_multiplier=1.0,
                rounds_present=1,
            )

            # 4j. Initialize strategy-layer features at defaults
            for feat in strategy_features:
                TeamStrategyFeatureLevel.objects.create(
                    team=team,
                    feature=feat,
                    market=None,
                    current_level=feat.default_value,
                    round_number=0,
                )

            # 4k. CC-32B: Initialize org structure (default: Centralized)
            default_org = OrganizationalStructureType.objects.filter(
                scenario=scenario, code='centralized',
            ).first()
            if default_org:
                TeamOrganizationalStructure.objects.create(
                    game=game, team=team,
                    current_structure=default_org,
                    adopted_round=0,
                )

            teams_created.append({
                'team': team,
                'profile': profile,
                'features_initialized': features_initialized,
                'products': products_info,
                'home_market': home_market.name,
                'cash': starting_cash,
                'debt': starting_debt,
            })

        # 5. Create rounds
        Round.objects.create(game=game, round_number=0, status='processed')
        for r in range(1, scenario.num_rounds + 1):
            Round.objects.create(game=game, round_number=r, status='pending')

        # 5b. Bootstrap Round 0 results
        from core.engine.bootstrap import bootstrap_round_zero
        bootstrap_round_zero(game)

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
