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

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Round, Team
from core.models.decisions import DecisionSubmission
from core.permissions import IsInstructor, instructor_can_access_game
from core.services.lifecycle import (
    LifecycleConflict, LifecyclePrecondition, lifecycle_view, operator_action)

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


def _narrative_job_payload(round_obj):
    """What an instructor needs to answer "where is my briefing?".

    The job rows already carried all of this; nothing read them but a
    management command, so an instructor could see that narratives were
    missing and nothing about why. Deliberately a projection, not the row:
    `claimed_by` is a hostname and PID that means nothing to an instructor, and
    the model *endpoint* is infrastructure detail.
    """
    from core.models.narrative_jobs import NarrativeJob

    jobs = NarrativeJob.objects.filter(round=round_obj).order_by(
        'narrative_type', 'template_version')
    rows = []
    for job in jobs:
        rows.append({
            'narrative_type': job.narrative_type,
            'label': job.get_narrative_type_display(),
            'state': job.state,
            'state_label': job.get_state_display(),
            'degraded': job.degraded,
            'attempts': job.attempts,
            'max_attempts': job.max_attempts,
            'attempts_remaining': job.attempts_remaining,
            'template_version': job.template_version,
            'model_name': job.model_name,
            # Already sanitised when stored: provider errors quote the failing
            # request, and that request carries an Authorization header.
            'last_error': job.last_error,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'claimed_at': job.claimed_at.isoformat() if job.claimed_at else None,
            'claim_expires_at': (job.claim_expires_at.isoformat()
                                 if job.claim_expires_at else None),
            'completed_at': (job.completed_at.isoformat()
                             if job.completed_at else None),
        })
    states = [row['state'] for row in rows]
    return {
        'jobs': rows,
        'summary': {
            'total': len(rows),
            'pending': states.count('pending'),
            'claimed': states.count('claimed'),
            'succeeded': states.count('succeeded'),
            'failed': states.count('failed'),
            'degraded': sum(1 for row in rows if row['degraded']),
        },
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
        if not instructor_can_access_game(request, game):
            return Response(
                {'error': 'This game belongs to another instructor.'},
                status=status.HTTP_403_FORBIDDEN)
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
            # Why the prose for this round is missing, late or template-written.
            'narratives': (_narrative_job_payload(round_obj)
                           if round_obj else None),
        })


class RoundCloseView(APIView):
    """
    POST /api/games/<game_id>/round-control/close/

    End the round now, ahead of its deadline. Locks all submissions.
    """
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'close_round') as action:
            round_obj = action.check_expected(action.require_round())
            before = action.before = _round_payload(action.game, round_obj)
            if round_obj.status in ('closed', 'processed'):
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} is already '
                    f'{round_obj.status}.',
                    guidance='Refresh the console — the deadline scheduler or '
                             'another operator closed it first.',
                    code='round_already_closed')
                raise error

            from core.engine.advance_round import close_round
            result = close_round(action.game.id, reason='manual')

            round_obj = action.require_round()
            after = _round_payload(action.game, round_obj)
            action.commit(before, after)
            return Response({
                'message': f'Round {result["round"]} closed. '
                           f'{result["submissions_locked"]} submission(s) locked.',
                'request_id': action.request_id,
                'round': after,
            })


class RoundReopenView(APIView):
    """
    POST /api/games/<game_id>/round-control/reopen/

    Undo a close: let students back in. Body may set a new deadline.
    Refused once the round has been processed, since results already exist.
    """
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'reopen_round') as action:
            game = action.game
            round_obj = action.check_expected(action.require_round())
            before = action.before = _round_payload(game, round_obj)

            if round_obj.status == 'processed':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} has already been processed '
                    f'and cannot be reopened.',
                    guidance='Results exist for this round. Recovery is the only '
                             'route back; see RECOVERY_RUNBOOK.md.',
                    code='round_already_processed')
                raise error
            if round_obj.status == 'open':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} is already open.',
                    guidance='Refresh the console — another operator reopened it.',
                    code='round_already_open')
                raise error

            new_deadline = request.data.get('deadline')
            if new_deadline:
                parsed = parse_datetime(new_deadline)
                if not parsed:
                    raise LifecyclePrecondition('Could not parse deadline.')
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(
                        parsed, timezone.get_current_timezone())
                round_obj.deadline = parsed
            elif round_obj.deadline and round_obj.deadline <= timezone.now():
                # Reopening without moving a past deadline would just let cron
                # close it again within the minute.
                raise LifecyclePrecondition(
                    'The deadline has already passed.',
                    guidance='Supply a new deadline when reopening, or the '
                             'scheduler will close the round again within a minute.',
                    code='deadline_in_past')

            round_obj.status = 'open'
            round_obj.closed_at = None
            round_obj.close_reason = ''
            # Clear the projection with the status it projects (see close_round).
            round_obj.decisions_locked = False
            round_obj.lock_reason = ''
            round_obj.save(update_fields=[
                'status', 'closed_at', 'close_reason', 'deadline',
                'decisions_locked', 'lock_reason'])

            # Unlock submissions so teams can edit again.
            unlocked = DecisionSubmission.objects.filter(
                round=round_obj, team__in=Team.objects.filter(game=game),
                status='locked',
            ).update(status='draft', locked_at=None)

            after = _round_payload(game, action.require_round())
            action.commit(before, after)
            return Response({
                'message': f'Round {round_obj.round_number} reopened. '
                           f'{unlocked} submission(s) unlocked.',
                'request_id': action.request_id,
                'round': after,
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

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'process_round') as action:
            game = action.game
            round_obj = action.check_expected(action.require_round())
            before = action.before = _round_payload(game, round_obj)
            force = bool(request.data.get('force', False))
            reason = ''

            # Exactly-once resolution: this is checked while holding the
            # boundary, so a second operator arriving during Phase 1 waits here
            # and then sees the finished state rather than resolving again.
            if round_obj.status == 'processed':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} has already been processed.',
                    guidance='Refresh the console. If results look wrong, use '
                             'recovery rather than processing again.',
                    code='round_already_processed')
                raise error

            if round_obj.status == 'open':
                if not force:
                    error = LifecyclePrecondition(
                        f'Round {round_obj.round_number} is still open.',
                        guidance='Close it first, or resend with force=true and '
                                 'a written reason to close and process in one step.',
                        code='round_still_open')
                    raise error
                # force closes an open round early: an integrity bypass, so it
                # is not available without a reason on the audit record.
                reason = action.require_reason()
                from core.engine.advance_round import close_round
                close_round(game.id, reason='manual')
                round_obj = action.require_round()

            from core.engine.advance_round import process_round, RoundNotReadyError
            try:
                result = process_round(game.id)
            except RoundNotReadyError as e:
                # Operator-fixable precondition (e.g. a team is unlocked), not a
                # server fault — report it as an actionable 400.
                logger.warning('Round not ready to process for game %s: %s',
                               game_id, e)
                error = LifecyclePrecondition(
                    str(e), guidance='Re-lock the team, or close the round, '
                                     'then process again.',
                    code='round_not_ready')
                raise error
            except Exception as e:
                logger.exception('Processing failed for game %s', game_id)
                # The engine marks the round FAILED outside its own rolled-back
                # savepoint; returning a response rather than re-raising is what
                # lets that record — and this audit row — commit.
                action.record_fault(f'Post-round processing failed: {e}')
                return Response(
                    {'error': f'Post-round processing failed: {e}',
                     'request_id': action.request_id},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            game.refresh_from_db()
            after = _round_payload(game, action.require_round())
            action.commit(before, after, reason=reason)
            return Response({
                'message': f'Round {result["processed_round"]} processed in '
                           f'{result["phase_1_time"]:.1f}s. Results are available; '
                           f'narratives are generating in the background.',
                'phase_1_time': result['phase_1_time'],
                'phase_2_status': result['phase_2_status'],
                'request_id': action.request_id,
                'round': after,
            })


class RoundAdvanceView(APIView):
    """
    POST /api/games/<game_id>/round-control/advance/

    Open the next round. Requires the current round to be processed
    (force=true overrides).
    """
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'advance_round') as action:
            game = action.game
            old_round = action.check_expected(action.require_round())
            before = action.before = _round_payload(game, old_round)
            force = bool(request.data.get('force', False))
            reason = ''

            if old_round.status != 'processed':
                if not force:
                    error = LifecyclePrecondition(
                        f'Round {old_round.round_number} is "{old_round.status}", '
                        f'not "processed".',
                        guidance='Run post-round processing first, or resend with '
                                 'force=true and a written reason to advance '
                                 'without results.',
                        code='round_not_processed')
                    raise error
                # Advancing past an unprocessed round leaves that round with no
                # results at all, so the bypass is audited with a reason.
                reason = action.require_reason()

            from core.engine.advance_round import advance_to_next_round
            try:
                result = advance_to_next_round(game.id, force=True if force else False)
            except ValueError as e:
                error = LifecycleConflict(str(e), code='advance_refused',
                                          guidance='Refresh the console.')
                raise error
            except Exception as e:
                logger.exception('Advance failed for game %s', game_id)
                action.record_fault(f'Advance failed: {e}', code='advance_failed')
                return Response({'error': f'Advance failed: {e}',
                                 'request_id': action.request_id},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            game.refresh_from_db()
            after = _round_payload(game, action.require_round())
            action.commit(before, after, reason=reason)

            if result['next_round'] is None:
                msg = (f'Round {result["completed_round"]} was the last round. '
                       f'Game complete.')
            else:
                msg = f'Advanced to round {result["next_round"]}.'

            return Response({
                'message': msg,
                'completed_round': result['completed_round'],
                'next_round': result['next_round'],
                'game_status': game.status,
                'request_id': action.request_id,
                'round': after,
            })


class RoundDeadlineView(APIView):
    """
    POST /api/games/<game_id>/round-control/deadline/

    Set or clear the current round's deadline.
    Body: {"deadline": "2026-07-20T17:00:00Z"} or {"deadline": null}
          {"minutes_from_now": 90}
    """
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'set_deadline') as action:
            game = action.game
            round_obj = action.check_expected(action.require_round())
            before = action.before = _round_payload(game, round_obj)

            # Checked under the boundary: a close committing a microsecond
            # earlier must win, and this request must not extend a round that
            # is already closed or resolved.
            if round_obj.status != 'open':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} is "{round_obj.status}"; '
                    f'deadline changes are refused unless the round is open.',
                    guidance='Reopen the round with a new deadline if students '
                             'still need time.',
                    code='round_not_open')
                raise error

            if 'minutes_from_now' in request.data:
                try:
                    minutes = int(request.data['minutes_from_now'])
                except (TypeError, ValueError):
                    raise LifecyclePrecondition('minutes_from_now must be a number.')
                round_obj.deadline = timezone.now() + timezone.timedelta(
                    minutes=minutes)
            elif 'deadline' in request.data:
                raw = request.data['deadline']
                if raw in (None, ''):
                    round_obj.deadline = None
                else:
                    parsed = parse_datetime(raw)
                    if not parsed:
                        raise LifecyclePrecondition('Could not parse deadline.')
                    if timezone.is_naive(parsed):
                        parsed = timezone.make_aware(
                            parsed, timezone.get_current_timezone())
                    round_obj.deadline = parsed
            else:
                raise LifecyclePrecondition(
                    'Provide deadline or minutes_from_now.')

            round_obj.save(update_fields=['deadline'])
            after = _round_payload(game, action.require_round())
            action.commit(before, after)

            warning = None
            if round_obj.deadline and round_obj.deadline <= timezone.now():
                warning = ('That deadline is in the past — the round will close '
                           'within a minute.')

            return Response({
                'message': 'Deadline updated.'
                           if round_obj.deadline else 'Deadline cleared.',
                'warning': warning,
                'request_id': action.request_id,
                'round': after,
            })
