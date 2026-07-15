"""
Instructor round lifecycle control.

The round moves: open -> closed -> processed -> (next round open).

  open       students are submitting
  closed     deadline elapsed (cron) or instructor closed it; submissions locked
  processed  post-round scoring has run; results visible
             then: advance opens round N+1

Processing and advancing are deliberately separate so an instructor can
inspect a round's results before the game moves on.
"""
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Round, Team
from core.models.decisions import DecisionSubmission
from core.permissions import IsInstructor

logger = logging.getLogger(__name__)


def _round_payload(game, round_obj):
    """Everything the console needs to decide which button to enable."""
    if not round_obj:
        return None

    teams = Team.objects.filter(game=game)
    total_teams = teams.count()
    locked = DecisionSubmission.objects.filter(
        round=round_obj, team__in=teams, status='locked',
    ).count()

    now = timezone.now()
    deadline = round_obj.deadline
    seconds_remaining = None
    is_overdue = False
    if deadline:
        delta = (deadline - now).total_seconds()
        seconds_remaining = int(delta)
        is_overdue = delta <= 0

    # Which action the console should offer next.
    if round_obj.status == 'open':
        next_action = 'close' if is_overdue else 'await_deadline'
    elif round_obj.status == 'closed':
        next_action = 'process'
    elif round_obj.status == 'processed':
        next_action = 'advance'
    else:
        next_action = None

    return {
        'round_id': round_obj.id,
        'round_number': round_obj.round_number,
        'status': round_obj.status,
        'processing_status': round_obj.processing_status,
        'narrative_generated': round_obj.narrative_generated,
        'narrative_error': round_obj.narrative_error or '',
        'opened_at': round_obj.opened_at.isoformat() if round_obj.opened_at else None,
        'deadline': deadline.isoformat() if deadline else None,
        'closed_at': round_obj.closed_at.isoformat() if round_obj.closed_at else None,
        'close_reason': round_obj.close_reason or '',
        'processed_at': round_obj.processed_at.isoformat() if round_obj.processed_at else None,
        'phase_1_duration': round_obj.phase_1_duration,
        'phase_2_duration': round_obj.phase_2_duration,
        'seconds_remaining': seconds_remaining,
        'is_overdue': is_overdue,
        'teams_total': total_teams,
        'teams_locked': locked,
        'teams_pending': total_teams - locked,
        'next_action': next_action,
    }


class RoundControlView(APIView):
    """
    GET /api/games/<game_id>/round-control/

    The state of the current round, plus which lifecycle action is next.
    Safe to poll.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()

        return Response({
            'game_id': game.id,
            'game_name': game.name,
            'game_status': game.status,
            'current_round': game.current_round,
            'total_rounds': game.scenario.num_rounds if game.scenario else None,
            'server_time': timezone.now().isoformat(),
            'round': _round_payload(game, round_obj),
        })


class RoundCloseView(APIView):
    """
    POST /api/games/<game_id>/round-control/close/

    End the round now, ahead of its deadline. Locks all submissions.
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        from core.engine.advance_round import close_round

        try:
            result = close_round(game.id, reason='manual')
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not result['changed']:
            return Response(
                {'error': f'Round {result["round"]} is already {result["status"]}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        game.refresh_from_db()
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()
        return Response({
            'message': f'Round {result["round"]} closed. '
                       f'{result["submissions_locked"]} submission(s) locked.',
            'round': _round_payload(game, round_obj),
        })


class RoundReopenView(APIView):
    """
    POST /api/games/<game_id>/round-control/reopen/

    Undo a close: let students back in. Body may set a new deadline.
    Refused once the round has been processed, since results already exist.
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()
        if not round_obj:
            return Response({'error': 'No current round.'},
                            status=status.HTTP_404_NOT_FOUND)

        if round_obj.status == 'processed':
            return Response(
                {'error': f'Round {round_obj.round_number} has already been '
                          f'processed and cannot be reopened.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if round_obj.status == 'open':
            return Response({'error': 'Round is already open.'},
                            status=status.HTTP_400_BAD_REQUEST)

        new_deadline = request.data.get('deadline')
        if new_deadline:
            parsed = parse_datetime(new_deadline)
            if not parsed:
                return Response({'error': 'Could not parse deadline.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            round_obj.deadline = parsed
        elif round_obj.deadline and round_obj.deadline <= timezone.now():
            # Reopening without moving a past deadline would just let cron
            # close it again within the minute.
            return Response(
                {'error': 'The deadline has already passed. Supply a new '
                          'deadline when reopening, or it will close again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        round_obj.status = 'open'
        round_obj.closed_at = None
        round_obj.close_reason = ''
        round_obj.save(update_fields=['status', 'closed_at', 'close_reason', 'deadline'])

        # Unlock submissions so teams can edit again.
        unlocked = DecisionSubmission.objects.filter(
            round=round_obj, team__in=Team.objects.filter(game=game),
            status='locked',
        ).update(status='draft', locked_at=None)

        return Response({
            'message': f'Round {round_obj.round_number} reopened. '
                       f'{unlocked} submission(s) unlocked.',
            'round': _round_payload(game, round_obj),
        })


class RoundProcessView(APIView):
    """
    POST /api/games/<game_id>/round-control/process/

    Run post-round processing: events, R&D, adoption, revenue, costs,
    financial statements, performance index, coherence, leaderboard and
    instructor alerts. Narratives generate in the background afterwards.

    Does not advance the game. Body: {"force": true} to process a round that
    is still open (closes it first).
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()
        if not round_obj:
            return Response({'error': 'No current round.'},
                            status=status.HTTP_404_NOT_FOUND)

        force = request.data.get('force', False)

        if round_obj.status == 'open':
            if not force:
                return Response(
                    {'error': f'Round {round_obj.round_number} is still open. '
                              f'Close it first, or pass force=true to close '
                              f'and process in one step.',
                     'teams_pending': _round_payload(game, round_obj)['teams_pending']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from core.engine.advance_round import close_round
            close_round(game.id, reason='manual')

        elif round_obj.status == 'processed':
            return Response(
                {'error': f'Round {round_obj.round_number} has already been '
                          f'processed. Advance to the next round.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.engine.advance_round import process_round
        try:
            result = process_round(game.id)
        except Exception as e:
            logger.exception('Processing failed for game %s', game_id)
            return Response(
                {'error': f'Post-round processing failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        game.refresh_from_db()
        round_obj.refresh_from_db()
        return Response({
            'message': f'Round {result["processed_round"]} processed in '
                       f'{result["phase_1_time"]:.1f}s. Results are available; '
                       f'narratives are generating in the background.',
            'phase_1_time': result['phase_1_time'],
            'phase_2_status': result['phase_2_status'],
            'round': _round_payload(game, round_obj),
        })


class RoundAdvanceView(APIView):
    """
    POST /api/games/<game_id>/round-control/advance/

    Open the next round. Requires the current round to be processed
    (force=true overrides).
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        force = request.data.get('force', False)

        from core.engine.advance_round import advance_to_next_round
        try:
            result = advance_to_next_round(game.id, force=force)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Advance failed for game %s', game_id)
            return Response({'error': f'Advance failed: {e}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        game.refresh_from_db()
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()

        if result['next_round'] is None:
            msg = f'Round {result["completed_round"]} was the last round. Game complete.'
        else:
            msg = f'Advanced to round {result["next_round"]}.'

        return Response({
            'message': msg,
            'completed_round': result['completed_round'],
            'next_round': result['next_round'],
            'game_status': game.status,
            'round': _round_payload(game, round_obj),
        })


class RoundDeadlineView(APIView):
    """
    POST /api/games/<game_id>/round-control/deadline/

    Set or clear the current round's deadline.
    Body: {"deadline": "2026-07-20T17:00:00Z"} or {"deadline": null}
          {"minutes_from_now": 90}
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, pk=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()
        if not round_obj:
            return Response({'error': 'No current round.'},
                            status=status.HTTP_404_NOT_FOUND)

        if 'minutes_from_now' in request.data:
            try:
                minutes = int(request.data['minutes_from_now'])
            except (TypeError, ValueError):
                return Response({'error': 'minutes_from_now must be a number.'},
                                status=status.HTTP_400_BAD_REQUEST)
            round_obj.deadline = timezone.now() + timezone.timedelta(minutes=minutes)
        elif 'deadline' in request.data:
            raw = request.data['deadline']
            if raw in (None, ''):
                round_obj.deadline = None
            else:
                parsed = parse_datetime(raw)
                if not parsed:
                    return Response({'error': 'Could not parse deadline.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                round_obj.deadline = parsed
        else:
            return Response({'error': 'Provide deadline or minutes_from_now.'},
                            status=status.HTTP_400_BAD_REQUEST)

        round_obj.save(update_fields=['deadline'])

        warning = None
        if round_obj.deadline and round_obj.deadline <= timezone.now() \
                and round_obj.status == 'open':
            warning = ('That deadline is in the past — the round will close '
                       'within a minute.')

        return Response({
            'message': 'Deadline updated.'
                       if round_obj.deadline else 'Deadline cleared.',
            'warning': warning,
            'round': _round_payload(game, round_obj),
        })
