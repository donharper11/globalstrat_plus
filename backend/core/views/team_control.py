"""Guarded instructor controls for reversible competition withdrawal."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Game, Team
from core.services.lifecycle import (
    LifecycleConflict, LifecyclePrecondition, lifecycle_view, operator_action)
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

    @lifecycle_view
    def post(self, request, game_id, team_id):
        from core.services.competition_locks import lock_team_for_decision_write

        # Changing who is in the competition changes what a round resolves
        # from, so it runs on the same boundary as close and process. Existing
        # team writes finish first; queued writes then re-check participation
        # and receive 403.
        with operator_action(request, game_id, 'team_participation') as guard:
            game = guard.game
            lock_team_for_decision_write(team_id)
            operator = get_request_user(request)
            action = str(request.data.get('action', '')).strip().lower()
            if action not in ('deactivate', 'reactivate'):
                raise LifecyclePrecondition(
                    'action must be either "deactivate" or "reactivate".')
            reason = guard.require_reason()
            expected_confirmation = f'{action.upper()} TEAM {team_id}'
            if request.data.get('confirmation') != expected_confirmation:
                raise LifecyclePrecondition(
                    f'confirmation must exactly equal "{expected_confirmation}".',
                    code='confirmation_required')

            guard.action = f'team_{action}d'
            team = get_object_or_404(
                Team.objects.select_for_update(), pk=team_id, game=game,
            )
            before = guard.before = _snapshot(team)
            target_status = 'withdrawn' if action == 'deactivate' else 'active'
            if team.participation_status == target_status:
                error = LifecycleConflict(
                    f'Team is already {target_status}.',
                    guidance='Refresh — another operator may have changed it.',
                    code='participation_unchanged')
                raise error

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
            guard.commit(before, after, reason=reason)
            return Response({**after, 'request_id': guard.request_id})
