"""
CC-21: Instructor Alerts API views.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsInstructor
from django.shortcuts import get_object_or_404

from core.models.core import Game
from core.models.cc21_models import InstructorAlert
from core.utils.operator_messages import language_for_request


class InstructorAlertsView(APIView):
    """GET /api/games/{game_id}/instructor/alerts/
    Returns alerts with optional filtering."""
    # V2-035: these declared no permission classes and inherited the
    # project default of IsAuthenticated, so any signed-in student could
    # read instructor alerts about teams. Role and ownership are separate
    # checks: this is the role half, the guard middleware is the other.
    permission_classes = [IsInstructor]


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

        # W-CE3-08 / W-CE2-08's residue. An alert is written in the language
        # stored at processing time, so every alert written before an
        # instructor set their language stayed English for ever and the panel
        # was permanently mixed -- rounds 1 and 2 of the third walkthrough
        # were 0 of 56 Chinese and could never become Chinese.
        #
        # The `coherence_feedback` precedent applies, with one difference: a
        # coherence breakdown stores the numbers its sentence was derived
        # from, and an alert stores only the finished sentence. So the alert
        # carries its rendering inputs (`render_context`, excluded from both
        # manifest sections) and the panel says the sentence again in the
        # reader's language. The stored row is never written; an alert with
        # no context, or one a model wrote, is served exactly as stored.
        from core.engine.instructor_alerts import reader_text
        language = language_for_request(request)

        rows = []
        for a in alerts:
            title, detail, teaching_note = reader_text(a, language)
            rows.append({
                'id': a.id,
                'team_id': a.team_id,
                'team_name': a.team.name,
                'round_number': a.round_number,
                'alert_type': a.alert_type,
                'severity': a.severity,
                'title': title,
                'detail': detail,
                'teaching_note': teaching_note,
                'acknowledged': a.acknowledged,
                'created_at': a.created_at.isoformat(),
            })
        return Response({'alerts': rows})


class InstructorAlertAcknowledgeView(APIView):
    """POST /api/games/{game_id}/instructor/alerts/{alert_id}/acknowledge/"""
    # V2-035: these declared no permission classes and inherited the
    # project default of IsAuthenticated, so any signed-in student could
    # read instructor alerts about teams. Role and ownership are separate
    # checks: this is the role half, the guard middleware is the other.
    permission_classes = [IsInstructor]


    def post(self, request, game_id, alert_id):
        alert = get_object_or_404(InstructorAlert, id=alert_id, game_id=game_id)
        alert.acknowledged = True
        alert.save(update_fields=['acknowledged'])
        return Response({'status': 'acknowledged'})


class InstructorAlertSummaryView(APIView):
    """GET /api/games/{game_id}/instructor/alerts/summary/
    Returns counts by severity."""
    # V2-035: these declared no permission classes and inherited the
    # project default of IsAuthenticated, so any signed-in student could
    # read instructor alerts about teams. Role and ownership are separate
    # checks: this is the role half, the guard middleware is the other.
    permission_classes = [IsInstructor]


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
    # V2-035: these declared no permission classes and inherited the
    # project default of IsAuthenticated, so any signed-in student could
    # read instructor alerts about teams. Role and ownership are separate
    # checks: this is the role half, the guard middleware is the other.
    permission_classes = [IsInstructor]


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
