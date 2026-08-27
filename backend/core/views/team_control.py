"""Guarded instructor controls for reversible competition withdrawal."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Game, Team
from core.services.competition_audit import record_operator_event
from core.utils.auth_context import get_request_user
from core.views.decisions import IsInstructor


def _snapshot(team):
    return {
        'team_id': team.id,
        'name': team.name,
        'participation_status': team.participation_status,
        'withdrawn_at': team.withdrawn_at.isoformat() if team.withdrawn_at else None,
        'withdrawn_by_id': team.withdrawn_by_id,
        'withdrawal_reason': team.withdrawal_reason,
    }


class InstructorTeamParticipationView(APIView):
    """Withdraw or reactivate a team without deleting competition history."""
    permission_classes = [IsInstructor]

    @transaction.atomic
    def post(self, request, game_id, team_id):
        from core.services.competition_locks import (
            lock_game_for_round_close, lock_team_for_decision_write)
        # Use the same lock order as deadline close. Existing team writes finish
        # first; queued writes then re-check participation and receive 403.
        lock_game_for_round_close(game_id)
        game = get_object_or_404(Game.objects.select_for_update(), pk=game_id)
        lock_team_for_decision_write(team_id)
        operator = get_request_user(request)
        action = str(request.data.get('action', '')).strip().lower()
        if action not in ('deactivate', 'reactivate'):
            return Response(
                {'detail': 'action must be either "deactivate" or "reactivate".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = str(request.data.get('reason', '')).strip()
        if len(reason) < 10:
            return Response(
                {'detail': 'A substantive reason of at least 10 characters is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        expected_confirmation = f'{action.upper()} TEAM {team_id}'
        if request.data.get('confirmation') != expected_confirmation:
            return Response(
                {'detail': f'confirmation must exactly equal "{expected_confirmation}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team = get_object_or_404(
            Team.objects.select_for_update(), pk=team_id, game=game,
        )
        target_status = 'withdrawn' if action == 'deactivate' else 'active'
        if team.participation_status == target_status:
            return Response(
                {'detail': f'Team is already {target_status}.'},
                status=status.HTTP_409_CONFLICT,
            )

        before = _snapshot(team)
        if action == 'deactivate':
            team.participation_status = 'withdrawn'
            team.withdrawn_at = timezone.now()
            team.withdrawn_by = operator
            team.withdrawal_reason = reason
        else:
            team.participation_status = 'active'
            team.withdrawn_at = None
            team.withdrawn_by = None
            team.withdrawal_reason = ''
        team.save(update_fields=[
            'participation_status', 'withdrawn_at', 'withdrawn_by',
            'withdrawal_reason',
        ])
        after = _snapshot(team)
        record_operator_event(
            request, game, None, f'team_{action}d', before, after,
        )
        return Response(after)
