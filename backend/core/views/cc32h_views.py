from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from core.models.core import Game, Round


class RoundStatusView(APIView):
    """GET — polling endpoint for round processing status."""

    def get(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        # Get the current active round (not the highest pre-created round)
        round_obj = Round.objects.filter(
            game=game,
            round_number=game.current_round,
        ).first()

        if not round_obj:
            return Response({'error': 'No rounds found'}, status=404)

        return Response({
            'round': round_obj.round_number,
            'status': round_obj.status,
            'processing_status': round_obj.processing_status,
            'narrative_generated': round_obj.narrative_generated,
            'phase_1_duration': round_obj.phase_1_duration,
            'phase_2_duration': round_obj.phase_2_duration,
        })
