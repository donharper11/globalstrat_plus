"""
API views for scenario listing and game creation.
"""
from django.contrib.auth.models import User as AuthUser
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsInstructor, IsInstructorOrReadOnly
import json
import random

from core.models.scenario import (
    Scenario, ScenarioConfig, FeatureDefinition, PlatformGenerationDefinition,
    FirmStarterProfile, FirmStarterPlatformConfig, FirmStarterProduct,
    EntryModeDefinition, MarketDefinition, SegmentDefinition,
)
from core.models.core import Game, Team, Round

# Default company names used when no scenario-specific names are configured.
DEFAULT_COMPANY_NAMES = [
    'Nexus Dynamics', 'Aether Industries', 'Solaris Corp',
    'Zenith Innovations', 'Orion Collective', 'Helios Ventures',
    'Vantage Systems', 'Prism Technologies', 'Astra Enterprises',
    'Vertex Global', 'Nova Synthetica', 'Quantum Forge',
    'Eclipse Digital', 'Cipher Networks', 'Parallax Labs',
    'Meridian Works', 'Stratos Group', 'Axiom Devices',
    'Pulse Robotics', 'Titan Microtech', 'Lumen Industries',
    'Catalyst Corp', 'Helix Foundry', 'Aegis Solutions',
    'Photon Systems', 'Nebula Dynamics', 'Tesseract Inc',
    'Arc Innovations', 'Cobalt Ventures', 'Apex Synergies',
]


def _get_company_names(scenario):
    """Return a shuffled list of company names for team creation."""
    cfg = ScenarioConfig.objects.filter(
        scenario=scenario, config_key='company_names',
    ).first()
    if cfg:
        try:
            names = json.loads(cfg.config_value)
            if isinstance(names, list) and names:
                random.shuffle(names)
                return names
        except (json.JSONDecodeError, TypeError):
            pass
    names = list(DEFAULT_COMPANY_NAMES)
    random.shuffle(names)
    return names
from core.utils.localization import get_localized_field, get_user_language
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel,
    TeamProduct, TeamProductMarket,
    TeamMarketPresence, TeamStrategyFeatureLevel,
)
from core.models.cc31_models import TeamMarketCompliance
from core.models.cc32b_models import OrganizationalStructureType, TeamOrganizationalStructure


class ScenarioListView(APIView):
    """GET /api/scenarios/ — list all active scenarios with annotated counts."""

    permission_classes = [IsInstructorOrReadOnly]

    def get(self, request):
        language = get_user_language(request)
        scenarios = Scenario.objects.filter(is_active=True).annotate(
            market_count=Count('markets', distinct=True),
            feature_count=Count(
                'feature_definitions',
                filter=Q(feature_definitions__layer='platform'),
                distinct=True,
            ),
            starter_profile_count=Count('starter_profiles', distinct=True),
        ).order_by('-created_at')

        result = []
        for s in scenarios:
            # Count unique customer segment names (segments are per-market)
            segment_count = (
                SegmentDefinition.objects.filter(scenario=s, segment_type='customer')
                .values('name').distinct().count()
            )
            result.append({
                'id': s.id,
                'name': s.name,
                'industry_label': s.industry_label,
                'description': s.description,
                'starting_cash': float(s.starting_cash),
                'num_rounds': s.num_rounds,
                'is_active': s.is_active,
                'created_at': s.created_at.isoformat(),
                'market_count': s.market_count,
                'feature_count': s.feature_count,
                'segment_count': segment_count,
                'starter_profile_count': s.starter_profile_count,
            })

        return Response({'scenarios': result})


class ScenarioDetailView(APIView):
    """GET /api/scenarios/<id>/ — scenario detail with markets and starter profiles."""

    permission_classes = [IsInstructorOrReadOnly]

    def get(self, request, scenario_id):
        language = get_user_language(request)
        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            return Response(
                {'error': f'Scenario {scenario_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        markets = MarketDefinition.objects.filter(
            scenario=scenario,
        ).order_by('display_order', 'name')

        profiles = FirmStarterProfile.objects.filter(
            scenario=scenario,
        ).select_related('home_market')

        return Response({
            'id': scenario.id,
            'name': scenario.name,
            'industry_label': scenario.industry_label,
            'description': scenario.description,
            'starting_cash': float(scenario.starting_cash),
            'num_rounds': scenario.num_rounds,
            'markets': [
                {
                    'id': m.id,
                    'code': m.code,
                    'name': get_localized_field(m, 'name', language),
                    'description': get_localized_field(m, 'description', language),
                    'base_growth_rate': float(m.base_growth_rate),
                    'tax_rate': float(m.tax_rate),
                    'tariff_rate': float(m.tariff_rate),
                    'regulatory_difficulty': float(m.regulatory_difficulty),
                    'infrastructure_quality': float(m.infrastructure_quality),
                    'entry_cost_base': float(m.entry_cost_base),
                    'currency_code': m.currency_code,
                }
                for m in markets
            ],
            'starter_profiles': [
                {
                    'id': p.id,
                    'profile_name': get_localized_field(p, 'profile_name', language),
                    'description': get_localized_field(p, 'description', language),
                    'home_market_code': p.home_market.code if p.home_market else None,
                    'home_market_name': get_localized_field(p.home_market, 'name', language) if p.home_market else None,
                }
                for p in profiles
            ],
        })


class GameListView(APIView):
    """GET /api/games/ — list games, optionally filtered by section_id or created_by."""

    permission_classes = [IsInstructor]

    def get(self, request):
        qs = Game.objects.all().select_related('scenario').order_by('-created_at')

        section_id = request.query_params.get('section_id')
        if section_id:
            qs = qs.filter(section_id=section_id)

        result = []
        for g in qs:
            team_count = Team.objects.filter(game=g).count()
            result.append({
                'game_id': g.id,
                'game_name': g.name,
                'scenario_name': g.scenario.name if g.scenario else None,
                'scenario_id': g.scenario_id,
                'section_id': g.section_id,
                'status': g.status,
                'current_round': g.current_round,
                'num_rounds': g.scenario.num_rounds if g.scenario else None,
                'team_count': team_count,
                'created_at': g.created_at.isoformat(),
            })

        return Response({'games': result})


class GameCreateView(APIView):
    """POST /api/games/create/ — create a new game from a scenario."""

    permission_classes = [IsInstructor]

    def post(self, request):
        language = get_user_language(request)
        # ── Validate inputs ──────────────────────────────────────────
        scenario_id = request.data.get('scenario_id')
        if not scenario_id:
            return Response(
                {'error': 'scenario_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            return Response(
                {'error': f'Scenario with ID {scenario_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        num_teams = request.data.get('num_teams')
        if num_teams is None:
            return Response(
                {'error': 'num_teams is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            num_teams = int(num_teams)
        except (ValueError, TypeError):
            return Response(
                {'error': 'num_teams must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (2 <= num_teams <= 16):
            return Response(
                {'error': 'num_teams must be between 2 and 16.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        game_name = request.data.get('name') or f"{scenario.name} Game"
        home_markets_arg = request.data.get('home_markets')  # list of market codes
        section_id = request.data.get('section_id')

        # ── Resolve created_by ───────────────────────────────────────
        if (
            hasattr(request, 'user')
            and request.user.is_authenticated
            and hasattr(request.user, 'pk')
        ):
            created_by = request.user
        else:
            created_by = AuthUser.objects.filter(is_superuser=True).first()
            if not created_by:
                return Response(
                    {'error': 'No authenticated user and no superuser found.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # ── Pre-flight checks ────────────────────────────────────────
        profiles = list(FirmStarterProfile.objects.filter(scenario=scenario))
        if not profiles:
            return Response(
                {'error': f"No starter profiles found for scenario '{scenario.name}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        starting_gen = PlatformGenerationDefinition.objects.filter(
            scenario=scenario, is_starting_platform=True,
        ).first()
        if not starting_gen:
            return Response(
                {'error': f"No starting platform generation found for scenario '{scenario.name}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        default_entry_mode = EntryModeDefinition.objects.filter(
            scenario=scenario,
        ).order_by('capital_requirement').first()

        strategy_features = FeatureDefinition.objects.filter(
            scenario=scenario, layer='strategy',
        )

        # Resolve home market overrides
        home_market_overrides = []
        if home_markets_arg:
            for code in home_markets_arg:
                mkt = MarketDefinition.objects.filter(
                    scenario=scenario, code__iexact=code.strip(),
                ).first()
                if not mkt:
                    return Response(
                        {'error': f"Market code '{code}' not found in scenario '{scenario.name}'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                home_market_overrides.append(mkt)

        # ── Create game inside a transaction ─────────────────────────
        with transaction.atomic():
            game = Game.objects.create(
                scenario=scenario,
                name=game_name,
                current_round=0,
                status='setup',
                created_by=created_by,
                section_id=section_id,
            )

            teams_response = []
            company_names = _get_company_names(scenario)

            for i in range(num_teams):
                profile = profiles[i % len(profiles)]
                starting_cash = profile.starting_cash if profile.starting_cash else scenario.starting_cash
                starting_debt = profile.starting_debt
                total_equity = starting_cash - starting_debt

                # Determine home market
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

                # Create TeamPlatforms — one per platform_label in starter config
                starter_configs = FirmStarterPlatformConfig.objects.filter(
                    firm_starter_profile=profile,
                )
                platform_labels = sorted(
                    starter_configs.values_list('platform_label', flat=True).distinct()
                )
                if not platform_labels:
                    platform_labels = ['alpha']

                all_platform_features = FeatureDefinition.objects.filter(
                    scenario=scenario, layer='platform',
                )
                label_names = {'alpha': 'A', 'beta': 'B', 'gamma': 'C'}
                platform_map = {}  # label -> TeamPlatform

                for label in platform_labels:
                    team_platform = TeamPlatform.objects.create(
                        team=team,
                        platform_generation=starting_gen,
                        name=f"{team.name} Platform {label_names.get(label, label.title())}",
                        status='active',
                        activated_round=0,
                    )
                    platform_map[label] = team_platform

                    # Create feature levels from starter config for this label
                    label_configs = starter_configs.filter(platform_label=label)
                    initialized_ids = set()
                    for config in label_configs:
                        TeamPlatformFeatureLevel.objects.create(
                            team_platform=team_platform,
                            feature=config.feature,
                            current_level=config.starting_level,
                        )
                        initialized_ids.add(config.feature_id)

                    # Initialize remaining platform features at level 0
                    for feat in all_platform_features:
                        if feat.id not in initialized_ids:
                            TeamPlatformFeatureLevel.objects.create(
                                team_platform=team_platform,
                                feature=feat,
                                current_level=0,
                            )

                # Create TeamProduct + TeamProductMarket from starter products
                starter_products = FirmStarterProduct.objects.filter(
                    firm_starter_profile=profile,
                )
                for sp in starter_products:
                    target_platform = platform_map.get(
                        sp.platform_label, list(platform_map.values())[0]
                    )
                    tp = TeamProduct.objects.create(
                        team=team,
                        team_platform=target_platform,
                        name=sp.product_name,
                        positioning=sp.positioning_label.lower().replace('-', '_').replace(' ', '_'),
                        created_round=0,
                    )
                    product_market = assigned_home_market if assigned_home_market else sp.market
                    TeamProductMarket.objects.create(
                        team_product=tp,
                        market=product_market,
                        first_offered_round=0,
                    )

                # Create TeamMarketPresence for home market
                if default_entry_mode:
                    TeamMarketPresence.objects.create(
                        team=team,
                        market=assigned_home_market,
                        entry_mode=default_entry_mode,
                        established_round=0,
                        initial_investment=0,
                        status='active',
                    )

                # Initialize TeamMarketCompliance for home market
                TeamMarketCompliance.objects.create(
                    game=game,
                    team=team,
                    market=assigned_home_market,
                    cumulative_investment=0,
                    compliance_level=0,
                    current_trust_multiplier=1.0,
                    effective_rd_multiplier=1.0,
                    effective_commercial_multiplier=1.0,
                    effective_operations_multiplier=1.0,
                    rounds_present=1,
                )

                # Initialize strategy-layer features at defaults
                for feat in strategy_features:
                    TeamStrategyFeatureLevel.objects.create(
                        team=team,
                        feature=feat,
                        market=None,
                        current_level=feat.default_value,
                        round_number=0,
                    )

                # CC-32B: Initialize org structure (default: Centralized)
                default_org = OrganizationalStructureType.objects.filter(
                    scenario=scenario, code='centralized',
                ).first()
                if default_org:
                    TeamOrganizationalStructure.objects.create(
                        game=game, team=team,
                        current_structure=default_org,
                        adopted_round=0,
                    )

                teams_response.append({
                    'team_id': team.id,
                    'team_name': team.name,
                    'profile_name': get_localized_field(profile, 'profile_name', language),
                    'home_market': get_localized_field(assigned_home_market, 'name', language) if assigned_home_market else None,
                })

            # Create rounds
            Round.objects.create(game=game, round_number=0, status='processed')
            for r in range(1, scenario.num_rounds + 1):
                Round.objects.create(game=game, round_number=r, status='pending')

            # Bootstrap Round 0 results
            from core.engine.bootstrap import bootstrap_round_zero
            bootstrap_round_zero(game)

            # Create SimulationInstance to bridge Section → Game for student auth
            if section_id:
                from core.models.course import SimulationInstance
                SimulationInstance.objects.update_or_create(
                    section_id=section_id,
                    defaults={
                        'game_id': game.id,
                        'current_round': 0,
                        'total_rounds': scenario.num_rounds,
                        'status': 'setup',
                    },
                )

            # Game stays in 'setup' — instructor activates explicitly
            # after assigning students and setting round schedule

        return Response({
            'game_id': game.id,
            'game_name': game.name,
            'scenario_name': scenario.name,
            'num_teams': num_teams,
            'status': game.status,
            'teams': teams_response,
        }, status=status.HTTP_201_CREATED)


class GameTeamsView(APIView):
    """GET /api/games/<game_id>/teams/ — list teams in a game."""

    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        language = get_user_language(request)
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        teams = Team.objects.filter(game=game).select_related(
            'home_market', 'firm_starter_profile',
        ).order_by('id')

        result = []
        for t in teams:
            result.append({
                'team_id': t.id,
                'team_name': t.name,
                'home_market': get_localized_field(t.home_market, 'name', language) if t.home_market else None,
                'home_market_code': t.home_market.code if t.home_market else None,
                'profile_name': get_localized_field(t.firm_starter_profile, 'profile_name', language) if t.firm_starter_profile else None,
            })

        return Response({
            'game_id': game.id,
            'game_name': game.name,
            'status': game.status,
            'teams': result,
        })


class GameActivateView(APIView):
    """POST /api/games/<game_id>/activate/ — move game from setup to active."""

    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response(
                {'error': f'Game {game_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if game.status != 'setup':
            return Response(
                {'error': f"Game is already '{game.status}'. Only 'setup' games can be activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Open Round 1 for play
        round_1 = Round.objects.filter(game=game, round_number=1).first()
        if not round_1:
            return Response(
                {'error': 'Round 1 not found for this game.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        round_1.status = 'open'
        round_1.opened_at = timezone.now()
        round_1.save()

        game.current_round = 1
        game.status = 'active'
        game.save()

        return Response({
            'game_id': game.id,
            'game_name': game.name,
            'status': game.status,
            'current_round': game.current_round,
        })


class GamePauseView(APIView):
    """POST /api/games/<game_id>/pause/ — pause an active game."""

    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        if game.status != 'active':
            return Response(
                {'error': f"Game is '{game.status}', not 'active'. Cannot pause."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        game.status = 'paused'
        game.save()

        return Response({
            'game_id': game.id,
            'status': game.status,
            'current_round': game.current_round,
        })


class GameResetView(APIView):
    """POST /api/games/<game_id>/reset/ — reset game back to setup status."""

    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Close any open round, reset Round 1 to pending
        Round.objects.filter(game=game, status='open').update(
            status='pending', opened_at=None,
        )

        game.current_round = 0
        game.status = 'setup'
        game.save()

        return Response({
            'game_id': game.id,
            'status': game.status,
            'current_round': game.current_round,
        })


class GameResumeView(APIView):
    """POST /api/games/<game_id>/resume/ — resume a paused game."""

    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        if game.status != 'paused':
            return Response(
                {'error': f"Game is '{game.status}', not 'paused'. Cannot resume."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        game.status = 'active'
        game.save()

        return Response({
            'game_id': game.id,
            'status': game.status,
            'current_round': game.current_round,
        })


class GameArchiveView(APIView):
    """POST /api/games/<game_id>/archive/ — archive a game (keeps data, disables play)."""

    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        if game.status == 'archived':
            return Response(
                {'error': 'Game is already archived.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        game.status = 'archived'
        game.save()

        # Clear SimulationInstance link so section can host a new game
        from core.models.course import SimulationInstance
        SimulationInstance.objects.filter(game_id=game.id).delete()

        return Response({
            'game_id': game.id,
            'status': game.status,
            'message': 'Game archived. Section is now free for a new game.',
        })


def _delete_game_cascade(game):
    """
    Delete a game and ALL related data in the correct order
    to respect PROTECT foreign-key constraints.
    """
    from core.models.decisions import DecisionSubmission
    from core.models.team_state import (
        TeamPlatform, TeamPlatformFeatureLevel,
        TeamProduct, TeamProductMarket,
        TeamMarketPresence, TeamStrategyFeatureLevel,
        TeamPlant, TeamPartnership, TeamAcquisition, TeamMarketModifier,
    )
    from core.models.results import EventInstance, ActiveModifier, RoundResultAdoption
    from core.models.results_financials import (
        RoundResultProductMarket as RRPM,
        RoundResultFinancials, RoundResultMarketRevenue,
        RoundResultPerformanceIndex, RoundResultCoherence,
        LeaderboardEntry,
    )
    from core.models.course import SimulationInstance

    team_ids = list(game.teams.values_list('id', flat=True))
    round_ids = list(game.rounds.values_list('id', flat=True))

    # Layer 1: Decision submissions (detail tables CASCADE from submission)
    DecisionSubmission.objects.filter(team_id__in=team_ids).delete()

    # Layer 2: Team state (leaf tables first, then parents)
    TeamProductMarket.objects.filter(team_product__team_id__in=team_ids).delete()
    TeamProduct.objects.filter(team_id__in=team_ids).delete()
    TeamPlatformFeatureLevel.objects.filter(team_platform__team_id__in=team_ids).delete()
    TeamPlatform.objects.filter(team_id__in=team_ids).delete()
    TeamStrategyFeatureLevel.objects.filter(team_id__in=team_ids).delete()
    TeamMarketPresence.objects.filter(team_id__in=team_ids).delete()
    TeamPlant.objects.filter(team_id__in=team_ids).delete()
    TeamPartnership.objects.filter(team_id__in=team_ids).delete()
    TeamAcquisition.objects.filter(team_id__in=team_ids).delete()
    TeamMarketModifier.objects.filter(team_id__in=team_ids).delete()

    # Layer 3: Results (PROTECT on game/team)
    EventInstance.objects.filter(game=game).delete()
    ActiveModifier.objects.filter(game=game).delete()
    RoundResultAdoption.objects.filter(game=game).delete()
    RRPM.objects.filter(game=game).delete()
    RoundResultFinancials.objects.filter(game=game).delete()
    RoundResultMarketRevenue.objects.filter(game=game).delete()
    RoundResultPerformanceIndex.objects.filter(game=game).delete()
    RoundResultCoherence.objects.filter(game=game).delete()
    LeaderboardEntry.objects.filter(game=game).delete()

    # Layer 4: TeamMember, then Team, then Round
    from core.models.core import TeamMember
    TeamMember.objects.filter(team_id__in=team_ids).delete()
    Team.objects.filter(id__in=team_ids).delete()
    Round.objects.filter(id__in=round_ids).delete()

    # Layer 5: SimulationInstance bridge
    SimulationInstance.objects.filter(game_id=game.id).delete()

    # Layer 6: Game itself
    game.delete()


class GameDeleteView(APIView):
    """DELETE /api/games/<game_id>/delete/ — permanently delete a game and all data."""

    permission_classes = [IsInstructor]

    @transaction.atomic
    def delete(self, request, game_id):
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        game_name = game.name
        _delete_game_cascade(game)

        return Response({
            'message': f'Game "{game_name}" and all related data permanently deleted.',
        })
