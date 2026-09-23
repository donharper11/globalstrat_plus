"""CC-27: Strategic Briefing API endpoints."""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from core.utils.participant_messages import participant_refusal
from rest_framework.views import APIView

from core.models.core import Game, Team, User
from core.models.cc27_models import StrategicBriefing, BriefingReadStatus
from core.utils.localization import get_user_language


class LatestBriefingView(APIView):
    """GET — Get the latest (most recent) briefing for a team.
    Accepts ?user_id=N to include per-user read status.
    """

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)

        briefing = StrategicBriefing.objects.filter(
            game=game, team=team,
        ).order_by('-round_number').first()

        if not briefing:
            return Response({'briefing': None, 'is_read': True})

        user_id = request.query_params.get('user_id')
        is_read = False
        if user_id:
            is_read = BriefingReadStatus.objects.filter(
                briefing=briefing, user_id=user_id,
            ).exists()

        return Response({
            'briefing': _serialize(briefing, get_user_language(request)),
            'is_read': is_read,
        })


class RoundBriefingView(APIView):
    """GET — Get a specific round's briefing."""

    def get(self, request, game_id, team_id, round_number):
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)

        briefing = StrategicBriefing.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        if not briefing:
            return Response({'briefing': None, 'is_read': True})

        user_id = request.query_params.get('user_id')
        is_read = False
        if user_id:
            is_read = BriefingReadStatus.objects.filter(
                briefing=briefing, user_id=user_id,
            ).exists()

        return Response({
            'briefing': _serialize(briefing, get_user_language(request)),
            'is_read': is_read,
        })


class BriefingReadView(APIView):
    """POST — Mark a briefing as read for a specific user."""

    def post(self, request, game_id, team_id, briefing_id):
        briefing = get_object_or_404(StrategicBriefing, pk=briefing_id)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                participant_refusal(request, 'request_incomplete'), status=400)

        user = get_object_or_404(User, pk=user_id)
        BriefingReadStatus.objects.get_or_create(
            briefing=briefing, user=user,
        )
        return Response({'status': 'ok'})


def _serialize(briefing, language='en'):
    """The stored briefing, with its prose in this reader's language.

    W-CE3-11: a briefing is Phase-2 prose written in the language
    `get_team_language` returned at processing time, so a student who chose
    中文 after a round was resolved could never read that round's briefing.
    `narratives.briefing_for_reader` re-derives the template sentences from
    the figures they came from and returns the stored text untouched for
    anything it cannot place -- a summary a model wrote, above all. The
    stored row is never written.
    """
    from core.engine.narratives import briefing_for_reader

    fields = briefing_for_reader(briefing, language)
    return {
        'id': briefing.id,
        'round_number': briefing.round_number,
        'executive_summary': fields['executive_summary'],
        'performance_analysis': fields['performance_analysis'],
        'investment_returns': fields['investment_returns'],
        'investor_sentiment': fields['investor_sentiment'],
        'competitive_landscape': fields['competitive_landscape'],
        'strategic_recommendations': fields['strategic_recommendations'],
        'risk_alerts': fields['risk_alerts'],
        'generated_at': briefing.generated_at.isoformat() if briefing.generated_at else None,
    }
