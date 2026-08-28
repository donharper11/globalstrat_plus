"""Competition audit helpers; failures are deliberately fail-closed."""
from core.models import DecisionAuditEvent, OperatorAuditEvent
from core.utils.auth_context import get_request_user


def record_decision_event(request, game, team, round_obj, action, payload):
    return DecisionAuditEvent.objects.create(
        game=game, team=team, round=round_obj, user=get_request_user(request),
        action=action, endpoint=request.path, payload=payload,
        request_id=request.headers.get('X-Request-ID', ''),
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
