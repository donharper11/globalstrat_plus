"""
Serializers for decision models (Group 5).

Each of the 15 decision tables gets a ModelSerializer. The master
DecisionSubmissionSerializer nests all 14 detail serializers and handles
writable nested create/update inside a transaction.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from core.models.decisions import (
    DecisionAcquisition,
    DecisionBudgetAllocation,
    DecisionESG,
    DecisionEventResponse,
    DecisionFinancing,
    DecisionMarketEntry,
    DecisionMarketing,
    DecisionPartnership,
    DecisionPlant,
    DecisionPlatformDevelopment,
    DecisionProductCreate,
    DecisionProductRetire,
    DecisionRDInvestment,
    DecisionResearchAllocation,
    DecisionSubmission,
)
from core.models.scenario import PlatformFeatureCeiling, ScenarioConfig
from core.models.team_state import TeamPlant


# ---------------------------------------------------------------------------
# Tier 2 — Detail serializers
# ---------------------------------------------------------------------------

class DecisionBudgetAllocationSerializer(serializers.ModelSerializer):
    warnings = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DecisionBudgetAllocation
        fields = [
            'id',
            'rd_budget', 'marketing_budget', 'strategy_budget',
            'warnings',
        ]

    # -- validation ----------------------------------------------------------

    def validate_rd_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("rd_budget must be >= 0.")
        return value

    def validate_marketing_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("marketing_budget must be >= 0.")
        return value

    def validate_strategy_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("strategy_budget must be >= 0.")
        return value

    def get_warnings(self, obj):
        warnings = []
        for field in ('rd_budget', 'marketing_budget', 'strategy_budget'):
            val = getattr(obj, field, None)
            if val is not None and val == 0:
                warnings.append(f"{field} is 0.")
        return warnings


class DecisionRDInvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionRDInvestment
        fields = [
            'id',
            'team_platform', 'feature', 'method', 'amount',
            'target_level', 'calculated_cost',
        ]

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("amount must be >= 0.")
        return value

    def validate(self, attrs):
        feature = attrs.get('feature')
        team_platform = attrs.get('team_platform')

        # Validate: feature must have ceiling > 0 on team's platform
        if feature and team_platform:
            ceiling = PlatformFeatureCeiling.objects.filter(
                platform_generation=team_platform.platform_generation,
                feature=feature,
            ).first()
            if not ceiling or ceiling.ceiling_value == 0:
                raise serializers.ValidationError(
                    f"'{feature.name}' is not available on your current platform. "
                    f"Upgrade to a newer generation to unlock this capability."
                )

        # Validate: max selected features on a platform (non-zero level)
        if feature and team_platform:
            from core.models.team_state import TeamPlatformFeatureLevel
            current_level_obj = TeamPlatformFeatureLevel.objects.filter(
                team_platform=team_platform, feature=feature,
            ).first()
            current_level = float(current_level_obj.current_level) if current_level_obj else 0
            if current_level == 0:
                # Selecting a new feature — check limit
                active_count = TeamPlatformFeatureLevel.objects.filter(
                    team_platform=team_platform, current_level__gt=0,
                ).count()
                try:
                    max_features = int(ScenarioConfig.objects.get(
                        config_key='max_platform_features',
                    ).config_value)
                except ScenarioConfig.DoesNotExist:
                    max_features = 5
                if active_count >= max_features:
                    raise serializers.ValidationError(
                        f"Maximum {max_features} features can be selected per platform. "
                        f"You already have {active_count} active features."
                    )

        # Validate: slot limit (max features per round)
        submission = attrs.get('submission') or getattr(self, '_submission', None)
        if submission:
            existing = DecisionRDInvestment.objects.filter(
                submission=submission,
            ).exclude(pk=self.instance.pk if self.instance else None)
            invested_features = set(inv.feature_id for inv in existing)
            if feature:
                invested_features.add(feature.id)
            try:
                max_slots = int(ScenarioConfig.objects.get(
                    scenario=submission.round.game.scenario,
                    config_key='max_rd_investments_per_round',
                ).config_value)
            except ScenarioConfig.DoesNotExist:
                max_slots = 5
            if len(invested_features) > max_slots:
                raise serializers.ValidationError(
                    f"Maximum {max_slots} features can be invested in per round. "
                    f"Remove an investment before adding a new one."
                )

        return attrs


class DecisionPlatformDevelopmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionPlatformDevelopment
        fields = [
            'id',
            'platform_generation', 'method', 'committed_cost',
            'platform_name', 'feature_levels',
        ]

    def validate_feature_levels(self, value):
        if not isinstance(value, dict):
            return value
        # Count features with non-zero levels
        selected = sum(1 for v in value.values() if v and float(v) > 0)
        try:
            cfg = ScenarioConfig.objects.filter(
                config_key='max_platform_features',
            ).first()
            max_features = int(cfg.config_value) if cfg else 5
        except (ScenarioConfig.DoesNotExist, ValueError):
            max_features = 5
        if selected > max_features:
            raise serializers.ValidationError(
                f"Maximum {max_features} features can be selected per platform. "
                f"You have selected {selected}."
            )
        return value


class DecisionProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionProductCreate
        fields = [
            'id',
            'team_platform', 'product_name', 'positioning', 'target_market_ids',
        ]

    def validate_target_market_ids(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("target_market_ids must be a non-empty list.")
        if not all(isinstance(v, int) for v in value):
            raise serializers.ValidationError("target_market_ids must contain only integers.")
        return value


class DecisionProductRetireSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionProductRetire
        fields = [
            'id',
            'team_product', 'timing',
        ]


class DecisionMarketingSerializer(serializers.ModelSerializer):
    warnings = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DecisionMarketing
        fields = [
            'id',
            'team_product', 'market',
            'retail_price', 'promotion_budget',
            'campaign_focus_feature_ids',
            'channel_digital_pct', 'channel_traditional_pct', 'channel_trade_pct',
            'distribution_strategy', 'distribution_investment', 'sales_team_count',
            'distribution_channel_detail',
            'production_volume', 'production_source_market', 'demand_estimate',
            'warnings',
        ]

    def validate_retail_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("retail_price must be > 0.")
        return value

    def validate_promotion_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("promotion_budget must be >= 0.")
        return value

    def validate_production_volume(self, value):
        if value < 0:
            raise serializers.ValidationError("production_volume must be >= 0.")
        return value

    def validate_demand_estimate(self, value):
        if value < 0:
            raise serializers.ValidationError("demand_estimate must be >= 0.")
        return value

    def validate_campaign_focus_feature_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("campaign_focus_feature_ids must be a list.")
        if len(value) < 1 or len(value) > 3:
            raise serializers.ValidationError(
                "campaign_focus_feature_ids must contain 1-3 integers."
            )
        if not all(isinstance(v, int) for v in value):
            raise serializers.ValidationError(
                "campaign_focus_feature_ids must contain only integers."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        digital = attrs.get('channel_digital_pct')
        traditional = attrs.get('channel_traditional_pct')
        trade = attrs.get('channel_trade_pct')
        if digital is not None and traditional is not None and trade is not None:
            total = digital + traditional + trade
            if abs(total - Decimal('1.0')) > Decimal('0.001'):
                raise serializers.ValidationError({
                    'channel_digital_pct': (
                        "channel_digital_pct + channel_traditional_pct + "
                        f"channel_trade_pct must sum to 1.0 (got {total})."
                    ),
                })
        return attrs

    def get_warnings(self, obj):
        warnings = []
        if obj.pk is None:
            return warnings

        production_volume = obj.production_volume
        source_market = obj.production_source_market
        team = obj.submission.team

        # Sum capacity across all operational plants for this team + source market
        total_capacity = (
            TeamPlant.objects.filter(
                team=team,
                market=source_market,
                status='operational',
            ).aggregate(total=Sum('capacity_units'))['total']
        ) or 0

        if production_volume > total_capacity:
            if not source_market.contract_mfg_available:
                warnings.append(
                    f"production_volume ({production_volume}) exceeds total "
                    f"plant capacity ({total_capacity}) in "
                    f"{source_market.name} and contract manufacturing is not "
                    f"available there."
                )
            else:
                cap = source_market.contract_mfg_capacity_cap or 0
                effective_cap = total_capacity + cap
                if production_volume > effective_cap:
                    warnings.append(
                        f"production_volume ({production_volume}) exceeds "
                        f"plant capacity ({total_capacity}) plus contract "
                        f"manufacturing cap ({cap}) in {source_market.name}."
                    )

        return warnings


class DecisionMarketEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionMarketEntry
        fields = [
            'id',
            'market', 'entry_mode', 'initial_investment', 'action',
            'integration_strategy',
        ]

    def validate_integration_strategy(self, value):
        # Only required when entry mode is ACQUISITION — nullable for others
        return value


class DecisionFinancingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionFinancing
        fields = [
            'id',
            'new_debt', 'debt_repayment', 'new_equity', 'dividend_per_share',
        ]

    def validate_new_debt(self, value):
        if value < 0:
            raise serializers.ValidationError("new_debt must be >= 0.")
        return value

    def validate_debt_repayment(self, value):
        if value < 0:
            raise serializers.ValidationError("debt_repayment must be >= 0.")
        return value

    def validate_new_equity(self, value):
        if value < 0:
            raise serializers.ValidationError("new_equity must be >= 0.")
        return value

    def validate_dividend_per_share(self, value):
        if value < 0:
            raise serializers.ValidationError("dividend_per_share must be >= 0.")
        return value


class DecisionPlantSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionPlant
        fields = [
            'id',
            'market', 'action', 'capacity_units', 'contract_mfg_volume',
        ]


class DecisionPartnershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionPartnership
        fields = [
            'id',
            'market', 'strategy_option', 'annual_investment', 'action',
        ]


class DecisionAcquisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionAcquisition
        fields = [
            'id',
            'acquisition_target',
        ]


class DecisionESGSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionESG
        fields = [
            'id',
            'environmental_investment', 'social_investment', 'governance_commitments',
        ]
        extra_kwargs = {
            'governance_commitments': {'required': False, 'allow_null': True},
        }


class DecisionTalentSerializer(serializers.ModelSerializer):
    class Meta:
        from core.models.talent import DecisionTalent
        model = DecisionTalent
        fields = [
            'id',
            'rd_headcount', 'rd_salary_level', 'rd_training_budget',
            'commercial_headcount', 'commercial_salary_level', 'commercial_training_budget',
            'operations_headcount', 'operations_salary_level', 'operations_training_budget',
        ]


class DecisionEventResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionEventResponse
        fields = [
            'id',
            'event_instance', 'response',
        ]
        extra_kwargs = {
            'event_instance': {'required': False, 'allow_null': True},
        }


class DecisionResearchAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionResearchAllocation
        fields = [
            'id',
            'market', 'allocation_amount',
        ]

    def validate_allocation_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("allocation_amount must be >= 0.")
        return value


# ---------------------------------------------------------------------------
# CC-31A: Talent Allocation & Compliance Investment serializers
# ---------------------------------------------------------------------------

class TalentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        from core.models.cc31_models import TalentAllocation
        model = TalentAllocation
        fields = ['id', 'talent_pool', 'hq_count', 'market_allocation']

    def validate(self, data):
        submission = self.context.get('submission')
        if not submission:
            return data

        from core.models.talent import DecisionTalent
        try:
            talent_decision = submission.talent
        except DecisionTalent.DoesNotExist:
            raise serializers.ValidationError("No talent decision found for this submission")

        pool = data.get('talent_pool', '')
        prefix_map = {'rd': 'rd', 'commercial': 'commercial', 'operations': 'operations'}
        prefix = prefix_map.get(pool, pool)
        total_headcount = getattr(talent_decision, f'{prefix}_headcount', 0)

        # Sum must equal total headcount
        allocated = data.get('hq_count', 0) + sum(data.get('market_allocation', {}).values())
        if allocated != total_headcount:
            raise serializers.ValidationError(
                f"Allocation ({allocated}) must equal total headcount ({total_headcount})"
            )

        # Cannot allocate to markets the team hasn't entered
        from core.models.team_state import TeamMarketPresence
        active_codes = set(
            TeamMarketPresence.objects.filter(
                team=submission.team, status='active',
            ).values_list('market__code', flat=True)
        )
        for code, count in data.get('market_allocation', {}).items():
            if code not in active_codes and count > 0:
                raise serializers.ValidationError(
                    f"Cannot allocate staff to {code} — not an active market"
                )

        # HQ minimum: at least 20% of headcount
        min_hq = max(1, int(total_headcount * 0.2))
        if data.get('hq_count', 0) < min_hq:
            raise serializers.ValidationError(
                f"Minimum {min_hq} staff must remain at HQ (20% of headcount)"
            )

        return data


class ComplianceInvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        from core.models.cc31_models import ComplianceInvestment
        model = ComplianceInvestment
        fields = ['id', 'market', 'investment_amount']

    def validate_investment_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Investment cannot be negative")
        if value > 10000000:
            raise serializers.ValidationError("Maximum $10M compliance investment per market per round")
        return value


# ---------------------------------------------------------------------------
# Tier 1 — Master serializer with nested writable relations
# ---------------------------------------------------------------------------

# Mapping from payload key -> (related_name, serializer class, is_one_to_one)
_NESTED_CONFIG = [
    ('budget_allocation',      DecisionBudgetAllocationSerializer,      True),
    ('financing',              DecisionFinancingSerializer,              True),
    ('esg',                    DecisionESGSerializer,                    True),
    ('rd_investments',         DecisionRDInvestmentSerializer,           False),
    ('platform_developments',  DecisionPlatformDevelopmentSerializer,    False),
    ('product_creates',        DecisionProductCreateSerializer,          False),
    ('product_retires',        DecisionProductRetireSerializer,          False),
    ('marketing_decisions',    DecisionMarketingSerializer,              False),
    ('market_entries',         DecisionMarketEntrySerializer,            False),
    ('plant_decisions',        DecisionPlantSerializer,                  False),
    ('partnerships',           DecisionPartnershipSerializer,            False),
    ('acquisitions',           DecisionAcquisitionSerializer,            False),
    ('event_responses',        DecisionEventResponseSerializer,          False),
    ('research_allocations',   DecisionResearchAllocationSerializer,     False),
    ('talent_allocations',     TalentAllocationSerializer,               False),
    ('compliance_investments', ComplianceInvestmentSerializer,            False),
]


class DecisionSubmissionSerializer(serializers.ModelSerializer):
    # OneToOne nested fields (allow null for GET when not yet created)
    budget_allocation = DecisionBudgetAllocationSerializer(required=False, allow_null=True)
    financing = DecisionFinancingSerializer(required=False, allow_null=True)
    esg = DecisionESGSerializer(required=False, allow_null=True)

    # Many nested fields
    rd_investments = DecisionRDInvestmentSerializer(many=True, required=False)
    platform_developments = DecisionPlatformDevelopmentSerializer(many=True, required=False)
    product_creates = DecisionProductCreateSerializer(many=True, required=False)
    product_retires = DecisionProductRetireSerializer(many=True, required=False)
    marketing_decisions = DecisionMarketingSerializer(many=True, required=False)
    market_entries = DecisionMarketEntrySerializer(many=True, required=False)
    plant_decisions = DecisionPlantSerializer(many=True, required=False)
    partnerships = DecisionPartnershipSerializer(many=True, required=False)
    acquisitions = DecisionAcquisitionSerializer(many=True, required=False)
    event_responses = DecisionEventResponseSerializer(many=True, required=False)
    research_allocations = DecisionResearchAllocationSerializer(many=True, required=False)
    talent_allocations = TalentAllocationSerializer(many=True, required=False)
    compliance_investments = ComplianceInvestmentSerializer(many=True, required=False)

    class Meta:
        model = DecisionSubmission
        fields = [
            'id', 'team', 'round', 'status', 'locked_at', 'locked_by', 'team_notes',
            # nested
            'budget_allocation', 'financing', 'esg',
            'rd_investments', 'platform_developments',
            'product_creates', 'product_retires',
            'marketing_decisions', 'market_entries',
            'plant_decisions', 'partnerships', 'acquisitions',
            'event_responses', 'research_allocations',
            'talent_allocations', 'compliance_investments',
        ]
        read_only_fields = ['id', 'status', 'locked_at', 'locked_by']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pop_nested(validated_data):
        """Extract all nested payloads from validated_data, returning a dict."""
        nested = {}
        for key, _serializer_cls, _is_o2o in _NESTED_CONFIG:
            if key in validated_data:
                nested[key] = validated_data.pop(key)
        return nested

    @staticmethod
    def _create_nested(submission, nested_data):
        """Create nested objects for a given submission."""
        for key, serializer_cls, is_o2o in _NESTED_CONFIG:
            data = nested_data.get(key)
            if data is None:
                continue
            if is_o2o:
                # data is a dict
                serializer_cls.Meta.model.objects.create(
                    submission=submission, **data,
                )
            else:
                # data is a list of dicts
                model_cls = serializer_cls.Meta.model
                objs = [model_cls(submission=submission, **item) for item in data]
                model_cls.objects.bulk_create(objs)

    @staticmethod
    def _update_nested(submission, nested_data):
        """
        Replace-style update: delete existing children and recreate.

        Only touches relations whose key is present in nested_data, so a
        partial update (PATCH) that omits a relation will leave it intact.
        """
        for key, serializer_cls, is_o2o in _NESTED_CONFIG:
            if key not in nested_data:
                continue
            data = nested_data[key]
            model_cls = serializer_cls.Meta.model

            if is_o2o:
                # Delete the old one if it exists, then create
                model_cls.objects.filter(submission=submission).delete()
                if data is not None:
                    model_cls.objects.create(submission=submission, **data)
            else:
                # Delete all existing, bulk-create replacements
                model_cls.objects.filter(submission=submission).delete()
                if data:
                    objs = [model_cls(submission=submission, **item) for item in data]
                    model_cls.objects.bulk_create(objs)

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        nested_data = self._pop_nested(validated_data)
        submission = DecisionSubmission.objects.create(**validated_data)
        self._create_nested(submission, nested_data)
        return submission

    @transaction.atomic
    def update(self, instance, validated_data):
        nested_data = self._pop_nested(validated_data)

        # Update scalar fields on the submission itself
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update nested relations (replace strategy)
        self._update_nested(instance, nested_data)

        # Refresh from DB so nested relations reflect the new state
        instance.refresh_from_db()
        return instance
