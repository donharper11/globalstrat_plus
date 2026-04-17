"""
CC-21: Instructor Alerts API views.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from core.models.core import Game
from core.models.cc21_models import InstructorAlert


class InstructorAlertsView(APIView):
    """GET /api/games/{game_id}/instructor/alerts/
    Returns alerts with optional filtering."""

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        alerts = InstructorAlert.objects.filter(game=game)

        # Filters
        severity = request.query_params.get('severity')
        if severity:
            alerts = alerts.filter(severity=severity)

        team_id = request.query_params.get('team_id')
        if team_id:
            alerts = alerts.filter(team_id=team_id)

        round_number = request.query_params.get('round_number')
        if round_number:
            alerts = alerts.filter(round_number=round_number)

        acknowledged = request.query_params.get('acknowledged')
        if acknowledged is not None:
            alerts = alerts.filter(acknowledged=acknowledged.lower() == 'true')

        alerts = alerts.select_related('team')[:100]

        return Response({
            'alerts': [
                {
                    'id': a.id,
                    'team_id': a.team_id,
                    'team_name': a.team.name,
                    'round_number': a.round_number,
                    'alert_type': a.alert_type,
                    'severity': a.severity,
                    'title': a.title,
                    'detail': a.detail,
                    'teaching_note': a.teaching_note,
                    'acknowledged': a.acknowledged,
                    'created_at': a.created_at.isoformat(),
                }
                for a in alerts
            ],
        })


class InstructorAlertAcknowledgeView(APIView):
    """POST /api/games/{game_id}/instructor/alerts/{alert_id}/acknowledge/"""

    def post(self, request, game_id, alert_id):
        alert = get_object_or_404(InstructorAlert, id=alert_id, game_id=game_id)
        alert.acknowledged = True
        alert.save(update_fields=['acknowledged'])
        return Response({'status': 'acknowledged'})


class InstructorAlertSummaryView(APIView):
    """GET /api/games/{game_id}/instructor/alerts/summary/
    Returns counts by severity."""

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)

        round_number = request.query_params.get('round_number')
        qs = InstructorAlert.objects.filter(game=game)
        if round_number:
            qs = qs.filter(round_number=round_number)

        from django.db.models import Count
        counts = qs.values('severity').annotate(count=Count('id'))
        summary = {item['severity']: item['count'] for item in counts}

        total = sum(summary.values())
        unacknowledged = qs.filter(acknowledged=False).count()

        return Response({
            'total': total,
            'unacknowledged': unacknowledged,
            'by_severity': summary,
        })


class TeamChangesView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/changes/
    Returns recent decision changes for team notification."""

    def get(self, request, game_id, team_id):
        from core.models.cc21_models import DecisionChangeLog
        from core.models.core import Team
        team = get_object_or_404(Team, id=team_id, game_id=game_id)

        changes = DecisionChangeLog.objects.filter(team=team)

        # Filter to exclude current user's changes
        exclude_user = request.query_params.get('exclude_user')
        if exclude_user:
            changes = changes.exclude(user_id=exclude_user)

        # Filter by time
        since = request.query_params.get('since')
        if since:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(since)
            if dt:
                changes = changes.filter(created_at__gte=dt)

        round_number = request.query_params.get('round_number')
        if round_number:
            changes = changes.filter(round_number=round_number)

        changes = changes.select_related('user')[:50]

        return Response({
            'changes': [
                {
                    'id': c.id,
                    'user_id': c.user_id,
                    'user_name': c.user.display_name if hasattr(c.user, 'display_name') else f'User {c.user_id}',
                    'round_number': c.round_number,
                    'page': c.page,
                    'change_description': c.change_description,
                    'change_data': c.change_data,
                    'created_at': c.created_at.isoformat(),
                }
                for c in changes
            ],
        })
