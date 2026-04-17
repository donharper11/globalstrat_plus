from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from core.models.gamification import (
    Achievement, GamificationBadge, PlayerProgress,
    TeamAchievement, TeamBadge,
)
from core.serializers.gamification import (
    AchievementSerializer, GamificationBadgeSerializer,
    PlayerProgressSerializer,
    TeamAchievementSerializer, TeamBadgeSerializer,
)
from core.services.gamification_engine import calculate_qicoin
from core.views.mixins import InstanceScopedMixin


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer


class GamificationBadgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GamificationBadge.objects.all()
    serializer_class = GamificationBadgeSerializer


class PlayerProgressViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PlayerProgress.objects.all()
    serializer_class = PlayerProgressSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        game_id = self.request.query_params.get('game_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if game_id:
            qs = qs.filter(game_id=game_id)
        return qs


class TeamAchievementViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamAchievement.objects.all()
    serializer_class = TeamAchievementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class TeamBadgeViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamBadge.objects.all()
    serializer_class = TeamBadgeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class QicoinView(APIView):
    """GET /api/qicoin/?team_id=1 — compute QICOIN total + breakdown."""

    def get(self, request):
        team_id = request.query_params.get('team_id')
        if not team_id:
            return Response({'error': 'team_id is required'}, status=400)
        try:
            team_id = int(team_id)
        except (ValueError, TypeError):
            return Response({'error': 'team_id must be an integer'}, status=400)

        result = calculate_qicoin(team_id)
        result['team_id'] = team_id
        return Response(result)
