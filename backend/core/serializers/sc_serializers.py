"""
Supply Chain DRF serializers (CC-04 §6).

Read serializers return all fields. Write serializers enforce progressive
disclosure and validation rules.
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


class SourcingDecisionWriteSerializer(serializers.ModelSerializer):
    allocations = SourcingAllocationWriteSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = SourcingDecision
        fields = [
            'team', 'round', 'tier_2_3_visibility_investment',
            'multi_sourcing_strategy', 'allocations',
        ]

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


class CustomsClassificationDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomsClassificationDecision
        fields = [
            'team', 'round', 'destination_market', 'classification',
            'reverse_logistics_capacity_pct', 'reverse_logistics_hub_market',
        ]


class TradeFinanceDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeFinanceDecision
        fields = [
            'team', 'round', 'segment', 'market',
            'buyer_payment_instrument', 'lc_doc_prep_investment',
        ]


class SinosureEnrollmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SinosureEnrollment
        fields = ['team', 'round', 'market', 'coverage_pct']


class FXHedgeDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FXHedgeDecision
        fields = ['team', 'round', 'currency_pair', 'hedge_ratio', 'tenor_days']


class InventoryDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryDecision
        fields = ['team', 'round', 'product', 'market', 'buffer_days', 'safety_stock_trigger_pct']


class ContingencyPlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContingencyPlan
        fields = [
            'team', 'round', 'disruption_response_playbook',
            'alt_supplier_activation_rules', 'mode_switch_triggers',
        ]


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
