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
from core.utils.operator_messages import (
    game_status, lifecycle_refusal, operator_refusal)
from core.services.lifecycle import (
    LifecycleConflict, LifecyclePrecondition, lifecycle_view, operator_action)
import json
import random

from core.models.scenario import (
    Scenario, ScenarioConfig, FeatureDefinition, PlatformGenerationDefinition,
    FirmStarterProfile, FirmStarterPlatformConfig, FirmStarterProduct,
    EntryModeDefinition, MarketDefinition, SegmentDefinition,
)
from core.models.core import Game, Team, Round

# The team-building loop, the company names and the starter-state rules live
# in ONE place (V2-112). The old names stay importable from here.
from core.services.game_creation import (  # noqa: E402,F401
    DEFAULT_COMPANY_NAMES, GameCreationError, create_game,
    get_company_names as _get_company_names, resolve_home_markets,
)
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
                operator_refusal(request, 'scenario_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            scenario = Scenario.objects.get(pk=scenario_id)
        except Scenario.DoesNotExist:
            return Response(
                operator_refusal(request, 'scenario_not_found'),
                status=status.HTTP_404_NOT_FOUND,
            )

        num_teams = request.data.get('num_teams')
        if num_teams is None:
            return Response(
                operator_refusal(request, 'team_count_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            num_teams = int(num_teams)
        except (ValueError, TypeError):
            return Response(
                operator_refusal(request, 'team_count_not_a_number'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        game_name = request.data.get('name') or f"{scenario.name} Game"
        home_markets_arg = request.data.get('home_markets')  # list of market codes
        section_id = request.data.get('section_id')

        # One cap, not two. This used to refuse num_teams outside 2..16 -- a
        # bound unrelated to the section's authored max_teams of 8, and two
        # caps that disagree is one cap that does not exist (A6 / V2-042). The
        # section's authored cap is now the only bound on the size of the
        # competitive field.
        from core.services.cohort_caps import (
            game_team_count_error, section_for_id)
        from core.utils.cohort_messages import language_for_request
        cap_error = game_team_count_error(
            section_for_id(section_id), num_teams,
            language=language_for_request(request))
        if cap_error:
            return Response(
                {'error': cap_error, 'code': 'team_count_refused'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Resolve created_by ───────────────────────────────────────
        # `Game.created_by` is a foreign key to Django's auth user, and the
        # only authentication class hands this view a `JWTUser` wrapping the
        # platform's own `core.User`. Assigning that raised ValueError, so this
        # route answered 500 to every instructor it exists for and the
        # superuser fallback below was unreachable. Only a real auth user is
        # assigned; otherwise the game is recorded against the first superuser,
        # exactly as `initialize_game` records it.
        created_by = request.user if isinstance(request.user, AuthUser) else None
        if created_by is None:
            created_by = AuthUser.objects.filter(
                is_superuser=True).order_by('id').first()
            if not created_by:
                return Response(
                    operator_refusal(request, 'game_creator_missing'),
                    status=status.HTTP_403_FORBIDDEN,
                )

        # ── Build the game: the one builder every path calls (V2-112) ──
        try:
            home_market_overrides = resolve_home_markets(
                scenario, home_markets_arg)
            game, created_teams = create_game(
                scenario, num_teams, name=game_name, created_by=created_by,
                home_market_overrides=home_market_overrides,
                section_id=section_id)
        except GameCreationError as exc:
            return Response(
                {'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Game stays in 'setup' — instructor activates explicitly
        # after assigning students and setting round schedule
        teams_response = [{
            'team_id': row['team'].id,
            'team_name': row['team'].name,
            'profile_name': get_localized_field(
                row['profile'], 'profile_name', language),
            'home_market': (get_localized_field(
                row['home_market'], 'name', language)
                if row['home_market'] else None),
        } for row in created_teams]

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
            return Response(operator_refusal(request, 'game_not_found'),
                            status=status.HTTP_404_NOT_FOUND)

        teams = Team.objects.filter(game=game).select_related(
            'home_market', 'firm_starter_profile',
        ).order_by('id')

        result = []
        for t in teams:
            result.append({
                'team_id': t.id,
                'team_name': t.name,
                'participation_status': t.participation_status,
                'withdrawn_at': t.withdrawn_at,
                'withdrawal_reason': t.withdrawal_reason,
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


def _game_state(game):
    """The lifecycle state an operator audit row needs to be readable."""
    return {'game_id': game.id, 'name': game.name, 'status': game.status,
            'current_round': game.current_round}


class GameActivateView(APIView):
    """POST /api/games/<game_id>/activate/ — move game from setup to active."""

    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'activate_game') as action:
            game = action.game
            before = action.before = _game_state(game)
            if game.status != 'setup':
                raise lifecycle_refusal(
                    LifecycleConflict, 'game_not_in_setup',
                    status=game_status(game.status))

            round_1 = Round.objects.select_for_update().filter(
                game=game, round_number=1).first()
            if not round_1:
                raise lifecycle_refusal(
                    LifecyclePrecondition, 'round_one_missing')

            round_1.status = 'open'
            round_1.opened_at = timezone.now()
            round_1.save(update_fields=['status', 'opened_at'])

            game.current_round = 1
            game.status = 'active'
            # update_fields, always: a bare save() on a Game rewrites every
            # column from this copy, and would undo a concurrent advance's
            # current_round.
            game.save(update_fields=['current_round', 'status'])

            after = _game_state(game)
            action.commit(before, after)
            return Response({
                'game_id': game.id,
                'game_name': game.name,
                'status': game.status,
                'current_round': game.current_round,
                'request_id': action.request_id,
            })


class GamePauseView(APIView):
    """POST /api/games/<game_id>/pause/ — pause an active game."""

    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        # Pausing stops the deadline scheduler from closing this game's rounds,
        # so it is a lifecycle change even though it only writes one column.
        with operator_action(request, game_id, 'pause_game') as action:
            game = action.game
            before = action.before = _game_state(game)
            if game.status != 'active':
                raise lifecycle_refusal(
                    LifecycleConflict, 'game_not_active',
                    status=game_status(game.status))

            game.status = 'paused'
            game.save(update_fields=['status'])
            action.commit(before, _game_state(game))
            return Response({
                'game_id': game.id,
                'status': game.status,
                'current_round': game.current_round,
                'request_id': action.request_id,
            })


class GameResetView(APIView):
    """POST /api/games/<game_id>/reset/ — reset game back to setup status."""

    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        # The most destructive of the five: it reopens rounds and sends the
        # game back to round 0. Racing a resolution it would strand results for
        # a round the game no longer believes it is on.
        with operator_action(request, game_id, 'reset_game') as action:
            game = action.game
            before = action.before = _game_state(game)
            reason = action.require_reason()

            reopened = Round.objects.filter(game=game, status='open').update(
                status='pending', opened_at=None, deadline=None,
                decisions_locked=False, lock_reason='')
            game.current_round = 0
            game.status = 'setup'
            game.save(update_fields=['current_round', 'status'])

            after = _game_state(game)
            after['rounds_reset'] = reopened
            action.commit(before, after, reason=reason)
            return Response({
                'game_id': game.id,
                'status': game.status,
                'current_round': game.current_round,
                'rounds_reset': reopened,
                'request_id': action.request_id,
            })


class GameResumeView(APIView):
    """POST /api/games/<game_id>/resume/ — resume a paused game."""

    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'resume_game') as action:
            game = action.game
            before = action.before = _game_state(game)
            if game.status != 'paused':
                raise lifecycle_refusal(
                    LifecycleConflict, 'game_not_paused',
                    status=game_status(game.status))

            game.status = 'active'
            game.save(update_fields=['status'])
            action.commit(before, _game_state(game))
            return Response({
                'game_id': game.id,
                'status': game.status,
                'current_round': game.current_round,
                'request_id': action.request_id,
            })


class GameArchiveView(APIView):
    """POST /api/games/<game_id>/archive/ — archive a game (keeps data, disables play)."""

    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'archive_game') as action:
            game = action.game
            before = action.before = _game_state(game)
            if game.status == 'archived':
                raise lifecycle_refusal(
                    LifecycleConflict, 'game_already_archived')
            reason = action.require_reason()

            game.status = 'archived'
            game.save(update_fields=['status'])

            # Clear SimulationInstance link so section can host a new game
            from core.models.course import SimulationInstance
            SimulationInstance.objects.filter(game_id=game.id).delete()

            action.commit(before, _game_state(game), reason=reason)
            return Response({
                'game_id': game.id,
                'status': game.status,
                'message': 'Game archived. Section is now free for a new game.',
                'request_id': action.request_id,
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
    from core.models.results import (
        EventInstance, ActiveModifier, RoundResultAdoption,
        RoundResultAIAdoption, RoundResultDemandReconciliation,
    )
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

    # Layer 2: Results FIRST — they hold protected FKs into team state.
    # This used to run after Layer 3 below, so deleting TeamProduct raised
    #   ProtectedError: ... referenced through protected foreign keys:
    #   'RoundResultAdoption.best_product', 'RoundResultProductMarket.team_product'
    # and, because the view is atomic, the whole delete rolled back. Deleting
    # any game whose rounds had ever been processed was therefore impossible —
    # only a game that had never run could be deleted, which is why this went
    # unnoticed.
    EventInstance.objects.filter(game=game).delete()
    ActiveModifier.objects.filter(game=game).delete()
    RoundResultAIAdoption.objects.filter(game=game).delete()
    RoundResultDemandReconciliation.objects.filter(game=game).delete()
    RoundResultAdoption.objects.filter(game=game).delete()
    RRPM.objects.filter(game=game).delete()
    RoundResultFinancials.objects.filter(game=game).delete()
    RoundResultMarketRevenue.objects.filter(game=game).delete()
    RoundResultPerformanceIndex.objects.filter(game=game).delete()
    RoundResultCoherence.objects.filter(game=game).delete()
    LeaderboardEntry.objects.filter(game=game).delete()

    # Layer 3: Team state (leaf tables first, then parents)
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
            return Response(operator_refusal(request, 'game_not_found'),
                            status=status.HTTP_404_NOT_FOUND)

        game_name = game.name
        _delete_game_cascade(game)

        return Response({
            'message': f'Game "{game_name}" and all related data permanently deleted.',
        })
