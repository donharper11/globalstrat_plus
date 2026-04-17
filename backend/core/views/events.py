from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsInstructor
from core.views.mixins import InstanceScopedMixin
from core.models.events import (
    TriggeredEvent,
)
from core.serializers.events import (
    TriggeredEventSerializer,
)


class TriggeredEventViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TriggeredEvent.objects.all()
    serializer_class = TriggeredEventSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        event_id = self.request.query_params.get('event_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs


class FireEventsViewSet(viewsets.ViewSet):
    """Trigger event engine for a given round and game."""
    permission_classes = [IsInstructor]

    def create(self, request):
        round_number = request.data.get('round_number')
        game_id = request.data.get('game_id')

        if not round_number or not game_id:
            return Response(
                {'error': 'round_number and game_id are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            round_number = int(round_number)
            game_id = int(game_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'round_number and game_id must be integers'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.services.event_engine import fire_events
        try:
            result = fire_events(round_number, game_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
