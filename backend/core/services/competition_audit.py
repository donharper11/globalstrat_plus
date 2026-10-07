"""Competition audit helpers; failures are deliberately fail-closed."""
from core.models import (DecisionAuditEvent, GameDeletionAuditEvent,
                         OperatorAuditEvent)
from core.utils.auth_context import get_request_user


def record_decision_event(request, game, team, round_obj, action, payload):
    """One immutable row per accepted decision write.

    ``request_id`` used to be ``request.headers.get('X-Request-ID', '')`` — the
    caller's header or nothing. The product's own client never sends that
    header, so **every row a real user created carried an empty id**, and the
    instructor's evidence panel printed ``—`` in the column the dispute
    procedure asks for. The one caller in the tree that does send it is
    ``run_deadline_rehearsal``, which is why the synthetic rehearsal produced
    correlation ids no browser would.

    It is minted here exactly as ``record_operator_event`` mints it, through
    ``request_id_for``, which caches the value on the request so the id on this
    row is the id in the response and in anything else written for the same
    request. Nothing hashed moves: ``resolution_manifest`` never reads
    ``request_id`` — it carries ``decision_event_count``, a count — so no
    manifest digest, envelope version or replay changes.
    """
    from core.services.lifecycle import request_id_for
    return DecisionAuditEvent.objects.create(
        game=game, team=team, round=round_obj, user=get_request_user(request),
        action=action, endpoint=request.path, payload=payload,
        request_id=request_id_for(request),
    )


def record_operator_event(request, game, round_obj, action, before, after,
                          outcome='committed', request_id=None, reason=None,
                          conflict=None):
    """One immutable row per operator attempt.

    ``outcome='rejected'`` records an attempt that changed nothing — a race it
    lost, or a precondition it failed — so the attempt is observable without
    the row implying a state change. ``request_id`` correlates the row with the
    response the operator saw; it is minted when the caller sends none.
    """
    user = get_request_user(request)
    if user is None:
        raise ValueError('Authenticated operator identity is required.')
    if reason is None:
        reason = str(request.data.get('reason', '')).strip()
    if not reason:
        reason = f'Operator requested {action}'
    if request_id is None:
        from core.services.lifecycle import request_id_for
        request_id = request_id_for(request)
    return OperatorAuditEvent.objects.create(
        game=game, round=round_obj, user=user, action=action, reason=reason,
        before=before, after=after, outcome=outcome,
        conflict=conflict or {}, request_id=request_id,
    )


def record_game_deletion(request, before, scenario, reason, request_id):
    """The durable record of one committed game deletion (R45).

    Called by `GameDeleteView` inside the transaction that deletes the game,
    after the cascade has succeeded: if this write fails the deletion is rolled
    back with it, and if anything fails after it the row goes with the
    deletion. Fail-closed like the rest of this module -- there is no `except`
    here on purpose.

    Takes `before` (the `_game_state` snapshot) rather than the game, because
    by now the game object describes a row that no longer exists. Plain values
    only; see `GameDeletionAuditEvent` for why it holds no keys.
    """
    user = get_request_user(request)
    if user is None:
        raise ValueError('Authenticated operator identity is required.')
    return GameDeletionAuditEvent.objects.create(
        game_id_deleted=before['game_id'], game_name=before['name'],
        scenario_id_value=getattr(scenario, 'pk', None),
        scenario_name=getattr(scenario, 'name', '') or '',
        actor_user_id=user.user_id, username=user.username or '',
        action='delete_game', reason=reason, before=before,
        request_id=request_id,
    )
