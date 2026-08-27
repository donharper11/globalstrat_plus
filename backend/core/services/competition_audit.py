"""Competition audit helpers; failures are deliberately fail-closed."""
from core.models import DecisionAuditEvent, OperatorAuditEvent
from core.utils.auth_context import get_request_user


def record_decision_event(request, game, team, round_obj, action, payload):
    return DecisionAuditEvent.objects.create(
        game=game, team=team, round=round_obj, user=get_request_user(request),
        action=action, endpoint=request.path, payload=payload,
        request_id=request.headers.get('X-Request-ID', ''),
    )


def record_operator_event(request, game, round_obj, action, before, after):
    user = get_request_user(request)
    if user is None:
        raise ValueError('Authenticated operator identity is required.')
    reason = str(request.data.get('reason', '')).strip()
    if not reason:
        reason = f'Operator requested {action}'
    return OperatorAuditEvent.objects.create(
        game=game, round=round_obj, user=user, action=action, reason=reason,
        before=before, after=after,
        request_id=request.headers.get('X-Request-ID', ''),
    )
