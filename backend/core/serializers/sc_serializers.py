"""
Supply Chain DRF serializers (CC-04 §6).

Read serializers return all fields. Write serializers enforce progressive
disclosure and validation rules. Progressive-disclosure enforcement consults
`core.utils.disclosure.get_effective_unlock_round`, which honours per-class
overrides (CC-04 Amendment A1).
"""
from rest_framework import serializers
from core.models.sc_models import (
    Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime,
    ResilienceParameters, FreightMarket,
)
from core.models.sc_decisions import (
    SourcingAllocation, SourcingDecision, LogisticsDecision,
    IncotermsDecision, CustomsClassificationDecision,
    TradeFinanceDecision, SinosureEnrollment, FXHedgeDecision,
    InventoryDecision, ContingencyPlan,
)
from core.models.sc_state import (
    SupplierState, LaneState, SCEventInstance,
    HedgePosition, ResilienceScoreHistory,
)
from core.utils.disclosure import get_effective_unlock_round


def _reject_locked_fields(data, game, round_number, field_specs):
    """
    Raise ValidationError if any field in `field_specs` is locked for this
    (game, round_number).

    `field_specs` is an iterable of (data_key, field_path) pairs: data_key is
    the serializer input key; field_path is the CC-2 dot-notation path. A
    field is "submitted" when its data_key is present with a truthy value.
    """
    for data_key, field_path in field_specs:
        if not data.get(data_key):
            continue
        unlock = get_effective_unlock_round(game, field_path)
        if round_number < unlock:
            raise serializers.ValidationError(
                f"{field_path} not yet unlocked at round {round_number} "
                f"for this class (unlocks at round {unlock})."
            )


# ---------------------------------------------------------------------------
# Scenario-content serializers (read-only for teams)
# ---------------------------------------------------------------------------

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class ShippingLaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingLane
        fields = '__all__'


class TradeFinanceInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeFinanceInstrument
        fields = '__all__'


class ComplianceRegimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRegime
        fields = '__all__'


class ResilienceParametersSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResilienceParameters
        fields = '__all__'


class FreightMarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreightMarket
        fields = '__all__'


# ---------------------------------------------------------------------------
# Decision read serializers (return all stored fields)
# ---------------------------------------------------------------------------

class SourcingAllocationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourcingAllocation
        fields = '__all__'


class SourcingDecisionReadSerializer(serializers.ModelSerializer):
    allocations = SourcingAllocationReadSerializer(
        source='team.sourcing_allocations', many=True, read_only=True,
    )

    class Meta:
        model = SourcingDecision
        fields = '__all__'


class LogisticsDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsDecision
        fields = '__all__'


class IncotermsDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncotermsDecision
        fields = '__all__'


class CustomsClassificationDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomsClassificationDecision
        fields = '__all__'


class TradeFinanceDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeFinanceDecision
        fields = '__all__'


class SinosureEnrollmentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SinosureEnrollment
        fields = '__all__'


class FXHedgeDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FXHedgeDecision
        fields = '__all__'


class InventoryDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryDecision
        fields = '__all__'


class ContingencyPlanReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContingencyPlan
        fields = '__all__'


# ---------------------------------------------------------------------------
# Decision write serializers (enforce validation + progressive disclosure)
# ---------------------------------------------------------------------------

class SourcingAllocationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourcingAllocation
        fields = [
            'team', 'round', 'critical_input_category', 'supplier',
            'allocation_pct', 'volume_commitment_units', 'payment_terms',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('payment_terms', 'sourcing.payment_terms'),
            ('volume_commitment_units', 'sourcing.volume_commitments'),
        ])
        return data


class SourcingDecisionWriteSerializer(serializers.ModelSerializer):
    allocations = SourcingAllocationWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = SourcingDecision
        fields = [
            'team', 'round', 'tier_2_3_visibility_investment',
            'multi_sourcing_strategy', 'allocations',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('tier_2_3_visibility_investment', 'sourcing.tier_2_3_visibility_investment'),
            ('multi_sourcing_strategy', 'sourcing.multi_sourcing_strategy'),
        ])
        return data

    def create(self, validated_data):
        allocations_data = validated_data.pop('allocations', [])
        decision = SourcingDecision.objects.create(**validated_data)
        for alloc_data in allocations_data:
            alloc_data['team'] = validated_data['team']
            alloc_data['round'] = validated_data['round']
            SourcingAllocation.objects.create(**alloc_data)
        return decision


class LogisticsDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsDecision
        fields = [
            'team', 'round', 'lane',
            'mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct',
            'volume_commitment_teu',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number

        # Progressive disclosure — modal mix (round 3) and volume commitment (round 5)
        modal_unlock = get_effective_unlock_round(game, 'logistics.modal_mix')
        if round_number < modal_unlock and any(
            data.get(f) for f in ['mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct']
        ):
            raise serializers.ValidationError(
                f"logistics.modal_mix not yet unlocked at round {round_number} "
                f"for this class (unlocks at round {modal_unlock})."
            )
        _reject_locked_fields(data, game, round_number, [
            ('volume_commitment_teu', 'logistics.volume_commitment_teu'),
        ])

        total = sum([
            data.get('mode_sea_pct', 0),
            data.get('mode_air_pct', 0),
            data.get('mode_rail_pct', 0),
            data.get('mode_road_pct', 0),
        ])
        if total != 100:
            raise serializers.ValidationError(f"Modal mix must sum to 100; got {total}")

        lane = data['lane']
        for mode in ['sea', 'air', 'rail', 'road']:
            pct = data.get(f'mode_{mode}_pct', 0)
            if pct > 0 and not lane.modes.get(mode, {}).get('available', False):
                raise serializers.ValidationError(
                    f"Mode {mode} not available on lane {lane.lane_id}"
                )

        return data


class IncotermsDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncotermsDecision
        fields = ['team', 'round', 'destination_market', 'incoterms', 'insurance_coverage_pct']

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('incoterms', 'logistics.incoterms'),
            ('insurance_coverage_pct', 'logistics.insurance_coverage_pct'),
        ])
        return data


class CustomsClassificationDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomsClassificationDecision
        fields = [
            'team', 'round', 'destination_market', 'classification',
            'reverse_logistics_capacity_pct', 'reverse_logistics_hub_market',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('classification', 'logistics.customs_classification'),
            ('reverse_logistics_capacity_pct', 'logistics.reverse_logistics'),
            ('reverse_logistics_hub_market', 'logistics.reverse_logistics'),
        ])
        return data


class TradeFinanceDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeFinanceDecision
        fields = [
            'team', 'round', 'segment', 'market',
            'buyer_payment_instrument', 'lc_doc_prep_investment',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('buyer_payment_instrument', 'trade_finance.buyer_payment_instrument'),
            ('lc_doc_prep_investment', 'trade_finance.lc_doc_prep_investment'),
        ])
        return data


class SinosureEnrollmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SinosureEnrollment
        fields = ['team', 'round', 'market', 'coverage_pct']

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('coverage_pct', 'trade_finance.sinosure_coverage'),
        ])
        return data


class FXHedgeDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FXHedgeDecision
        fields = ['team', 'round', 'currency_pair', 'hedge_ratio', 'tenor_days']

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('hedge_ratio', 'trade_finance.fx_hedging'),
            ('tenor_days', 'trade_finance.fx_hedging'),
        ])
        return data


class InventoryDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryDecision
        fields = ['team', 'round', 'product', 'market', 'buffer_days', 'safety_stock_trigger_pct']

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('buffer_days', 'inventory.buffer_days'),
            ('safety_stock_trigger_pct', 'inventory.safety_stock_trigger_pct'),
        ])
        return data


class ContingencyPlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContingencyPlan
        fields = [
            'team', 'round', 'disruption_response_playbook',
            'alt_supplier_activation_rules', 'mode_switch_triggers',
        ]

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('disruption_response_playbook', 'inventory.contingency_plans'),
            ('alt_supplier_activation_rules', 'inventory.contingency_plans'),
            ('mode_switch_triggers', 'inventory.contingency_plans'),
        ])
        return data


# ---------------------------------------------------------------------------
# Engine-state serializers (read-only)
# ---------------------------------------------------------------------------

class SupplierStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierState
        fields = '__all__'


class LaneStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaneState
        fields = '__all__'


class SCEventInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCEventInstance
        fields = '__all__'


class HedgePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HedgePosition
        fields = '__all__'


class ResilienceScoreHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResilienceScoreHistory
        fields = '__all__'
