"""
Onboarding API — data for the student first-login walkthrough.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.db.models import Sum

from core.models.core import Game, Team, Round
from core.models.course import Enrollment
from core.models.team_state import TeamProduct, TeamPlatform
from core.models.talent import TeamTalentState
from core.utils.localization import get_localized_field, get_user_language


class OnboardingDataView(APIView):
    """GET /api/onboarding/?game_id=&team_id= — dynamic data for onboarding screens."""

    def get(self, request):
        game_id = request.query_params.get('game_id')
        team_id = request.query_params.get('team_id')
        if not game_id or not team_id:
            return Response({'error': 'game_id and team_id required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            game = Game.objects.select_related('scenario').get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            team = Team.objects.select_related('home_market').get(pk=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

        # Products
        products = list(
            TeamProduct.objects.filter(team=team, status='active')
            .values('name', 'positioning')
        )

        # Current open round + deadline
        open_round = Round.objects.filter(game=game, status='open').first()
        if not open_round:
            open_round = Round.objects.filter(game=game).order_by('round_number').first()

        # Scenario info
        scenario = game.scenario
        language = get_user_language(request)

        # Platform name (active Gen 1 platform)
        platform = TeamPlatform.objects.filter(
            team=team, status='active',
        ).select_related('platform_generation').first()
        platform_name = (platform.name or platform.platform_generation.name) if platform else None

        # Total talent headcount
        talent_count = (
            TeamTalentState.objects.filter(team=team)
            .aggregate(total=Sum('headcount'))['total']
        ) or 0

        return Response({
            'team_name': team.name,
            'home_market_name': get_localized_field(team.home_market, 'name', language) if team.home_market else None,
            'home_market_code': team.home_market.code if team.home_market else None,
            'industry': scenario.industry_label if scenario else None,
            'scenario_name': scenario.name if scenario else None,
            'cash_on_hand': str(team.cash_on_hand),
            'performance_index': str(team.performance_index),
            'total_equity': str(team.total_equity),
            'products': products,
            'product_count': len(products),
            'platform_name': platform_name,
            'talent_count': talent_count,
            'current_round': open_round.round_number if open_round else 1,
            'deadline': open_round.deadline.isoformat() if open_round and open_round.deadline else None,
            'total_rounds': game.scenario.num_rounds if scenario else 10,
            'num_teams': game.teams.count(),
        })


class OnboardingCompleteView(APIView):
    """POST /api/onboarding/complete/ — mark onboarding as done."""

    def post(self, request):
        user_id = request.data.get('user_id')
        section_id = request.data.get('section_id')
        if not user_id:
            return Response({'error': 'user_id required'},
                            status=status.HTTP_400_BAD_REQUEST)

        filters = {'user_id': user_id, 'is_active': True}
        if section_id:
            filters['section_id'] = section_id

        updated = Enrollment.objects.filter(**filters).update(onboarding_completed=True)
        if updated == 0:
            return Response({'error': 'No active enrollment found'},
                            status=status.HTTP_404_NOT_FOUND)

        return Response({'onboarding_completed': True})
