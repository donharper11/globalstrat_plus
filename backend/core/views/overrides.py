"""
Instructor override API views (CC-04 Amendment A1 §3.6).

Endpoints are scoped by `game_id` (the class-instance scope) and restricted
to instructor/admin callers via core.permissions.IsInstructor.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game
from core.models.overrides import (
    ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride,
)
from core.permissions import IsInstructor
from core.serializers.overrides import (
    ClassProgressiveDisclosureOverrideSerializer,
    ClassResilienceWeightOverrideSerializer,
    _validate_combined_weight_sum,
)


class DisclosureOverrideListCreateView(APIView):
    """GET list overrides for a game; POST create one."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        get_object_or_404(Game, pk=game_id)
        qs = ClassProgressiveDisclosureOverride.objects.filter(game_id=game_id)
        return Response(
            ClassProgressiveDisclosureOverrideSerializer(qs, many=True).data
        )

    def post(self, request, game_id):
        get_object_or_404(Game, pk=game_id)
        payload = dict(request.data)
        payload['game'] = game_id
        serializer = ClassProgressiveDisclosureOverrideSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DisclosureOverrideDeleteView(APIView):
    """DELETE a specific disclosure override — reverts to the CC-2 §8 default."""
    permission_classes = [IsInstructor]

    def delete(self, request, game_id, override_id):
        override = get_object_or_404(
            ClassProgressiveDisclosureOverride,
            pk=override_id, game_id=game_id,
        )
        override.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResilienceWeightOverrideListCreateView(APIView):
    """GET list weight overrides for a game; POST create or update one."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        get_object_or_404(Game, pk=game_id)
        qs = ClassResilienceWeightOverride.objects.filter(game_id=game_id)
        return Response(
            ClassResilienceWeightOverrideSerializer(qs, many=True).data
        )

    def post(self, request, game_id):
        get_object_or_404(Game, pk=game_id)
        payload = dict(request.data)
        payload['game'] = game_id
        serializer = ClassResilienceWeightOverrideSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ResilienceWeightOverrideDeleteView(APIView):
    """DELETE a weight override. Re-validates that the resulting combined set still sums to 1.0."""
    permission_classes = [IsInstructor]

    def delete(self, request, game_id, override_id):
        override = get_object_or_404(
            ClassResilienceWeightOverride,
            pk=override_id, game_id=game_id,
        )
        # After deletion the weight reverts to the scenario default; re-check
        # that the combined set still sums to 1.0.
        _validate_combined_weight_sum(
            override.game, proposed=None, exclude_override_id=override.pk,
        )
        override.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
