from rest_framework import viewsets
from core.models import (
    Score, ScoreType, LeaderboardScore, LeaderboardMetric,
    TeamPerformance,
)
from core.serializers import (
    ScoreSerializer, ScoreTypeSerializer,
    LeaderboardScoreSerializer, LeaderboardMetricSerializer,
    TeamPerformanceSerializer,
)
from core.views.mixins import InstanceScopedMixin


class ScoreTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScoreType.objects.all()
    serializer_class = ScoreTypeSerializer


class ScoreViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Score.objects.all()
    serializer_class = ScoreSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        stakeholder_id = self.request.query_params.get('stakeholder_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if stakeholder_id:
            qs = qs.filter(stakeholder_id=stakeholder_id)
        return qs


class LeaderboardViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = LeaderboardScore.objects.all()
    serializer_class = LeaderboardScoreSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        round_id = self.request.query_params.get('round_id')
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs.order_by('-score')


class LeaderboardMetricViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaderboardMetric.objects.all()
    serializer_class = LeaderboardMetricSerializer


class TeamPerformanceViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamPerformance.objects.all()
    serializer_class = TeamPerformanceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs
