"""
Mixin to scope game-data ViewSets by instance_id.

Every game-data endpoint filters by the X-Instance-ID header or
instance_id query parameter. This ensures section isolation.
"""

from rest_framework.response import Response


def _get_instance_id_from_request(request):
    """Extract instance_id from header or query param."""
    instance_id = request.META.get('HTTP_X_INSTANCE_ID') or \
        request.query_params.get('instance_id')
    if instance_id:
        try:
            return int(instance_id)
        except (ValueError, TypeError):
            pass
    return None


class DecisionLockedMixin:
    """Mixin that rejects write operations when the current round is locked."""

    def _check_decisions_locked(self, request):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        from core.models import SimulationState, Round
        instance_id = _get_instance_id_from_request(request)
        if not instance_id:
            return None
        state = SimulationState.objects.filter(
            instance_id=instance_id, status='active',
        ).first()
        if not state or not state.current_round_id:
            return None
        current_round = Round.objects.filter(
            round_id=state.current_round_id,
        ).first()
        if current_round and current_round.decisions_locked:
            return Response(
                {
                    'error': 'Decisions are locked for this round.',
                    'reason': current_round.lock_reason,
                    'deadline': current_round.deadline.isoformat() if current_round.deadline else None,
                },
                status=423,
            )
        return None

    def create(self, request, *args, **kwargs):
        locked = self._check_decisions_locked(request)
        if locked:
            return locked
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        locked = self._check_decisions_locked(request)
        if locked:
            return locked
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        locked = self._check_decisions_locked(request)
        if locked:
            return locked
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        locked = self._check_decisions_locked(request)
        if locked:
            return locked
        return super().destroy(request, *args, **kwargs)


class InstanceScopedMixin:
    """Add instance_id filtering to any ViewSet whose model has instance_id."""

    instance_id_field = 'instance_id'  # override if column differs

    def _get_instance_id(self):
        """Extract instance_id from header or query param."""
        request = self.request
        instance_id = request.META.get('HTTP_X_INSTANCE_ID') or \
            request.query_params.get('instance_id')
        if instance_id:
            try:
                return int(instance_id)
            except (ValueError, TypeError):
                pass
        return None

    def get_queryset(self):
        qs = super().get_queryset()
        instance_id = self._get_instance_id()
        if instance_id is not None:
            qs = qs.filter(**{self.instance_id_field: instance_id})
        return qs

    def perform_create(self, serializer):
        """Auto-set instance_id on create if not provided."""
        instance_id = self._get_instance_id()
        if instance_id is not None:
            serializer.save(**{self.instance_id_field: instance_id})
        else:
            serializer.save()
