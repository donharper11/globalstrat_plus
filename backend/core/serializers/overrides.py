"""
Serializers for the instructor override tables (CC-04 Amendment A1 §3.5).

Write serializers carry the class-level validation rules:
  - disclosure: field_path must live in the CC-2 §8 registry;
    override_unlock_round must land in [1, 10].
  - resilience weights: each value in (0, 0.6]; the combined weight set
    (overrides + scenario defaults for non-overridden weights) must sum to
    1.0 (±0.01) — see §3.3.
"""
from decimal import Decimal

from rest_framework import serializers

from core.models.overrides import (
    ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride,
)
from core.utils.disclosure import DEFAULT_UNLOCK_ROUNDS, is_known_field_path


SEMESTER_MIN_ROUND = 1
SEMESTER_MAX_ROUND = 10

WEIGHT_VALUE_MIN = Decimal('0')
WEIGHT_VALUE_MAX = Decimal('0.6')
WEIGHT_SUM_TARGET = Decimal('1.0')
WEIGHT_SUM_TOLERANCE = Decimal('0.01')


class ClassProgressiveDisclosureOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassProgressiveDisclosureOverride
        fields = [
            'id', 'game', 'field_path', 'override_unlock_round',
            'created_by', 'created_at', 'reason',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_field_path(self, value):
        if not is_known_field_path(value):
            raise serializers.ValidationError(
                f"Unknown field_path '{value}'. Must be one of: "
                f"{sorted(DEFAULT_UNLOCK_ROUNDS.keys())}"
            )
        return value

    def validate_override_unlock_round(self, value):
        if value < SEMESTER_MIN_ROUND or value > SEMESTER_MAX_ROUND:
            raise serializers.ValidationError(
                f"override_unlock_round must be within "
                f"[{SEMESTER_MIN_ROUND}, {SEMESTER_MAX_ROUND}]"
            )
        return value


class ClassResilienceWeightOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassResilienceWeightOverride
        fields = [
            'id', 'game', 'weight_name', 'override_value',
            'created_by', 'created_at', 'reason',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_override_value(self, value):
        if value <= WEIGHT_VALUE_MIN:
            raise serializers.ValidationError(
                "override_value must be greater than 0"
            )
        if value > WEIGHT_VALUE_MAX:
            raise serializers.ValidationError(
                f"override_value must not exceed {WEIGHT_VALUE_MAX}"
            )
        return value

    def validate(self, data):
        game = data.get('game') or (self.instance.game if self.instance else None)
        weight_name = data.get('weight_name') or (
            self.instance.weight_name if self.instance else None
        )
        override_value = data.get('override_value')

        _validate_combined_weight_sum(
            game, proposed={weight_name: override_value},
            exclude_override_id=self.instance.pk if self.instance else None,
        )
        return data


def _validate_combined_weight_sum(game, proposed=None, exclude_override_id=None):
    """
    Confirm the combined weight set (existing overrides + `proposed` new
    overrides + scenario defaults for non-overridden weights) sums to 1.0 ± 0.01.

    `proposed` is a dict of {weight_name: override_value} entries to fold in
    before checking.
    """
    proposed = proposed or {}

    existing_qs = ClassResilienceWeightOverride.objects.filter(game=game)
    if exclude_override_id is not None:
        existing_qs = existing_qs.exclude(pk=exclude_override_id)
    override_map = {o.weight_name: Decimal(o.override_value) for o in existing_qs}
    for name, value in proposed.items():
        if name is not None and value is not None:
            override_map[name] = Decimal(value)

    scenario_weights = _scenario_weight_defaults(game)

    combined = {}
    for weight_name, _label in ClassResilienceWeightOverride.WEIGHT_CHOICES:
        if weight_name in override_map:
            combined[weight_name] = override_map[weight_name]
        else:
            combined[weight_name] = Decimal(str(scenario_weights.get(weight_name, 0)))

    total = sum(combined.values(), Decimal('0'))
    if abs(total - WEIGHT_SUM_TARGET) > WEIGHT_SUM_TOLERANCE:
        raise serializers.ValidationError(
            f"Combined resilience weights sum to {total}, must be "
            f"{WEIGHT_SUM_TARGET} (±{WEIGHT_SUM_TOLERANCE})"
        )


def _scenario_weight_defaults(game):
    """
    Return the scenario's resilience-weight defaults keyed by weight_name.
    Falls back to an empty dict if ResilienceParameters is absent — the
    caller's sum check will then fail, which is the intended behaviour.
    """
    if game is None:
        return {}
    try:
        params = game.scenario.resilience_parameters
    except Exception:
        return {}
    weights = getattr(params, 'resilience_score_weights', None)
    return weights if isinstance(weights, dict) else {}
