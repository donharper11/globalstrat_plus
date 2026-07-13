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


class RoundNumberMixin(serializers.Serializer):
    """Expose the human-readable round *number* alongside the ``round`` FK id.

    The read serializers use ``fields = '__all__'``, which renders the ``round``
    ForeignKey as its Round PK (a global id like 37), not the in-game round
    number (1..N). Students reading a round-1 decision saw ``round: 37``, which
    is confusing at best. This adds an explicit, non-breaking ``round_number``
    so payloads carry both the join key and the display value.
    """
    round_number = serializers.IntegerField(source='round.round_number', read_only=True)


def mode_is_available(lane, mode):
    """
    True if `mode` is usable on `lane`.

    Lane mode entries take two shapes in the scenario YAML (CC-8):
      - sea/air carry real parameters (baseline_cost_*, baseline_lead_time_days)
        and have no `available` key -> treated as available.
      - rail/road are declared as {'available': true|false}, and rail may also
        carry real parameters when a corridor exists.
    A mode is available when its entry exists and is not explicitly
    `available: false`.
    """
    entry = lane.modes.get(mode)
    if not entry:
        return False
    return entry.get('available', True) is not False


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

class SourcingAllocationReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = SourcingAllocation
        fields = '__all__'


class SourcingDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    allocations = SourcingAllocationReadSerializer(
        source='team.sourcing_allocations', many=True, read_only=True,
    )

    class Meta:
        model = SourcingDecision
        fields = '__all__'


class LogisticsDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = LogisticsDecision
        fields = '__all__'


class IncotermsDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = IncotermsDecision
        fields = '__all__'


class CustomsClassificationDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = CustomsClassificationDecision
        fields = '__all__'


class TradeFinanceDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = TradeFinanceDecision
        fields = '__all__'


class SinosureEnrollmentReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = SinosureEnrollment
        fields = '__all__'


class FXHedgeDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = FXHedgeDecision
        fields = '__all__'


class InventoryDecisionReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = InventoryDecision
        fields = '__all__'


class ContingencyPlanReadSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = ContingencyPlan
        fields = '__all__'


# ---------------------------------------------------------------------------
# Decision write serializers (enforce validation + progressive disclosure)
# ---------------------------------------------------------------------------

class SourcingAllocationWriteSerializer(serializers.ModelSerializer):
    # Optional / progressive-disclosure-gated fields; the model has no DB
    # default, so declare them optional here (the old view defaulted them).
    payment_terms = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=100,
    )
    volume_commitment_units = serializers.IntegerField(required=False, default=0)

    class Meta:
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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

        # Allocation percentages must sum to 100 per critical input category
        # (a category is only validated when it appears in the payload).
        allocations = data.get('allocations', [])
        totals = {}
        for alloc in allocations:
            cat = alloc.get('critical_input_category')
            totals[cat] = totals.get(cat, 0) + (alloc.get('allocation_pct') or 0)
        bad = {cat: tot for cat, tot in totals.items() if tot != 100}
        if bad:
            raise serializers.ValidationError({
                'allocations': [
                    f"Allocation percentages must sum to 100 per critical input "
                    f"category; got {bad}."
                ]
            })
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
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
            if pct > 0 and not mode_is_available(lane, mode):
                raise serializers.ValidationError(
                    f"Mode {mode} not available on lane {lane.lane_id}"
                )

        return data


class IncotermsDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
    # Progressive-disclosure-gated; model has no DB default (old view used '').
    buyer_payment_instrument = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=100,
    )

    class Meta:
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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

        # Validate the payment instrument against the scenario catalog, but
        # only when the scenario actually declares instruments (CC-9 §3.10).
        instrument = data.get('buyer_payment_instrument')
        if instrument:
            valid_ids = set(
                TradeFinanceInstrument.objects
                .filter(scenario=game.scenario)
                .values_list('instrument_id', flat=True)
            )
            if valid_ids and instrument not in valid_ids:
                raise serializers.ValidationError({
                    'buyer_payment_instrument': [
                        f"Unknown trade finance instrument '{instrument}'. "
                        f"Allowed: {sorted(valid_ids)}."
                    ]
                })
        return data


class SinosureEnrollmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
        model = FXHedgeDecision
        fields = ['team', 'round', 'currency_pair', 'hedge_ratio', 'tenor_days']

    def validate(self, data):
        game = data['team'].game
        round_number = data['round'].round_number
        _reject_locked_fields(data, game, round_number, [
            ('hedge_ratio', 'trade_finance.fx_hedging'),
            ('tenor_days', 'trade_finance.fx_hedging'),
        ])

        # Validate the currency pair against the scenario's FX instruments,
        # but only when the scenario declares available pairs (CC-9 §3.10).
        pair = data.get('currency_pair')
        if pair:
            valid_pairs = set()
            for inst in TradeFinanceInstrument.objects.filter(scenario=game.scenario):
                for p in (inst.currency_pairs_available or []):
                    valid_pairs.add(p)
            if valid_pairs and pair not in valid_pairs:
                raise serializers.ValidationError({
                    'currency_pair': [
                        f"Unknown currency pair '{pair}'. "
                        f"Allowed: {sorted(valid_pairs)}."
                    ]
                })
        return data


class InventoryDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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
        validators = []  # views handle upsert via update_or_create; DB enforces uniqueness
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

        # CC-19 §2: structured contingency rules must be executable objects, not
        # free prose. Validate shape + references so they are engine-ready.
        scenario = game.scenario
        supplier_ids = set(Supplier.objects.filter(scenario=scenario).values_list('id', flat=True))
        lane_map = {l.id: l for l in ShippingLane.objects.filter(scenario=scenario)}
        MODES = ('sea', 'air', 'rail', 'road')

        def _pct(v, label, errs):
            if v is not None and not (0 <= v <= 100):
                errs.append(f"{label} must be between 0 and 100.")

        alt_errs = []
        for i, r in enumerate(data.get('alt_supplier_activation_rules') or []):
            if not isinstance(r, dict):
                alt_errs.append(f"Rule {i + 1} must be a structured rule, not text."); continue
            if r.get('trigger') not in ('disruption', 'delay', 'capacity_drop'):
                alt_errs.append(f"Rule {i + 1}: unknown trigger '{r.get('trigger')}'.")
            if r.get('backup_supplier_id') not in supplier_ids:
                alt_errs.append(f"Rule {i + 1}: backup supplier does not exist in this scenario.")
            _pct(r.get('shift_pct'), f"Rule {i + 1} shift %", alt_errs)
        if alt_errs:
            raise serializers.ValidationError({'alt_supplier_activation_rules': alt_errs})

        mode_errs = []
        for i, r in enumerate(data.get('mode_switch_triggers') or []):
            if not isinstance(r, dict):
                mode_errs.append(f"Rule {i + 1} must be a structured rule, not text."); continue
            lane = lane_map.get(r.get('lane_id'))
            if lane is None:
                mode_errs.append(f"Rule {i + 1}: route does not exist in this scenario."); continue
            if r.get('trigger') not in ('lead_time_exceeds', 'event'):
                mode_errs.append(f"Rule {i + 1}: unknown trigger '{r.get('trigger')}'.")
            if r.get('from_mode') not in MODES or r.get('to_mode') not in MODES:
                mode_errs.append(f"Rule {i + 1}: invalid mode.")
            else:
                tm = (lane.modes or {}).get(r['to_mode'])
                if not tm or tm.get('available', True) is False:
                    mode_errs.append(f"Rule {i + 1}: '{r['to_mode']}' is not available on that route.")
            _pct(r.get('shift_pct'), f"Rule {i + 1} shift %", mode_errs)
        if mode_errs:
            raise serializers.ValidationError({'mode_switch_triggers': mode_errs})

        return data


# ---------------------------------------------------------------------------
# Engine-state serializers (read-only)
# ---------------------------------------------------------------------------

class SupplierStateSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = SupplierState
        fields = '__all__'


class LaneStateSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = LaneState
        fields = '__all__'


class SCEventInstanceSerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = SCEventInstance
        fields = '__all__'


class HedgePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HedgePosition
        fields = '__all__'


class ResilienceScoreHistorySerializer(RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = ResilienceScoreHistory
        fields = '__all__'
