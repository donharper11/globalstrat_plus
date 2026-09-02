"""
Serializers for decision models (Group 5).

Each of the 15 decision tables gets a ModelSerializer. The master
DecisionSubmissionSerializer nests all 14 detail serializers and handles
writable nested create/update inside a transaction.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from collections import Counter

from rest_framework import serializers
from core.serializers.decision_limits import NonNegativeFieldsMixin

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


def validate_rd_investment_targets(investments):
    """Require an unambiguous single operation for each platform feature."""
    targets = [
        (item['team_platform'].pk, item['feature'].pk)
        for item in investments
    ]
    if len(targets) != len(set(targets)):
        raise serializers.ValidationError(
            'Only one R&D investment per platform feature is allowed in a round.')


def _quoted(names):
    return ', '.join(f'"{name}"' for name in names)


def validate_product_names(creates, team):
    """A product name identifies a product, so it must be unique for the team.

    The resolution manifest keys `decision_product_create` on
    (submission_id, product_name) and `team_product` on (team_id, name).
    Without this check a duplicate is accepted with a 200 and only refused
    later, inside the resolution transaction -- which stalls the round for the
    whole cohort and tells nobody which student wrote it. Refusing it on the
    write puts the error in front of the person who can fix it.

    Names are compared exactly, after the serializer's own string handling.
    "vanguard" and "Vanguard" are different products here, as they are
    everywhere else in the game.
    """
    names = [item.get('product_name') for item in creates
             if item.get('product_name') is not None]
    if not names:
        return

    counts = Counter(names)
    repeated = sorted(name for name, count in counts.items() if count > 1)
    if repeated:
        raise serializers.ValidationError({'product_name': [
            f'Each new product needs its own name. {_quoted(repeated)} '
            f'appears more than once in this submission.']})

    if team is None:
        return
    from core.models.team_state import TeamProduct
    # Every row counts, retired ones included: the manifest key spans the whole
    # table, so a name freed by retiring a product is not free.
    taken = sorted(TeamProduct.objects
                   .filter(team=team, name__in=names)
                   .values_list('name', flat=True))
    if taken:
        raise serializers.ValidationError({'product_name': [
            f'Your team already has a product named {_quoted(taken)}. '
            f'Choose a different name.']})


def enforce_authoritative_costs(rows, kind, team=None, round_number=None):
    """Replace client-supplied R&D prices with the authored ones.

    Two behaviours, and the difference between them is the whole rule:

    * a row that names **no** cost, or names the authored figure, is filled in
      with the authored figure and accepted;
    * a row that names a **different** figure is refused, and the refusal says
      what the authored figure is.

    Never silently corrected. A submitted decision quietly replaced with a
    different one looks ordinary afterwards, which is precisely what made
    V2-037 invisible: the browser computed the price, the server stored what it
    was given, and the engine charged that.

    `kind` is 'platform' or 'rd'. Rows are validated dicts from either write
    surface, so both enforce the identical rule.
    """
    from core.services.rd_costs import (UnauthoredCost, platform_cost_for,
                                        rd_investment_cost)

    from core.services.rd_costs import ownership_problem, unlock_problem

    field = 'committed_cost' if kind == 'platform' else 'calculated_cost'
    price = platform_cost_for if kind == 'platform' else rd_investment_cost
    errors = []
    for index, row in enumerate(rows):
        if kind == 'rd' and team is not None:
            # V2-044: the platform named must belong to the submitting team.
            problem = ownership_problem(row.get('team_platform'), team)
            if problem:
                errors.append(f'row {index + 1}: {problem}')
                continue
        if kind == 'platform':
            # V2-039: the unlock gate belongs on the write, not only on the
            # lock. A team that never locks was defaulted at close and the
            # engine built the platform anyway.
            problem = unlock_problem(row.get('platform_generation'),
                                     round_number)
            if problem:
                errors.append(f'row {index + 1}: {problem}')
                continue
        try:
            authoritative = price(row)
        except UnauthoredCost as problem:
            errors.append(f'row {index + 1}: {problem}')
            continue

        submitted = row.get(field)
        if submitted is not None and Decimal(submitted) != authoritative:
            errors.append(
                f'row {index + 1}: {field} was submitted as '
                f'{Decimal(submitted):,.2f}, but this scenario prices it at '
                f'{authoritative:,.2f}. The server sets the price; correct the '
                f'submission or leave the field out.')
            continue
        row[field] = authoritative
        if kind == 'rd':
            # `amount` is the money leg of the same decision. It follows the
            # authored figure for the same reason.
            submitted_amount = row.get('amount')
            if (submitted_amount is not None
                    and Decimal(submitted_amount) != authoritative):
                errors.append(
                    f'row {index + 1}: amount was submitted as '
                    f'{Decimal(submitted_amount):,.2f}, but this scenario '
                    f'prices it at {authoritative:,.2f}.')
                continue
            row['amount'] = authoritative

    if errors:
        raise serializers.ValidationError({field: errors})
    return rows


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


class DecisionRDInvestmentListSerializer(serializers.ListSerializer):
    """The cross-row R&D rule, wherever the rows arrive together.

    It used to live only in `DecisionSubmissionSerializer.validate()`, so the
    whole-submission endpoint refused a duplicate platform+feature pair and the
    per-type PATCH endpoint — which validated each row on its own — accepted it.
    A `ListSerializer` runs for `many=True` on both paths, so there is one rule
    and one place to change it.
    """

    def validate(self, attrs):
        attrs = super().validate(attrs)
        validate_rd_investment_targets(attrs)
        return attrs


class DecisionRDInvestmentSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
    # Both money fields are advisory for the same reason as committed_cost.
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False)
    calculated_cost = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False)

    class Meta:
        model = DecisionRDInvestment
        fields = [
            'id',
            'team_platform', 'feature', 'method', 'amount',
            'target_level', 'calculated_cost',
        ]
        list_serializer_class = DecisionRDInvestmentListSerializer

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
                # Scoped to this platform's scenario, and stated once in
                # rd_costs.feature_cap. Read unscoped, this raised
                # MultipleObjectsReturned as soon as a second scenario
                # authored the key.
                from core.services.rd_costs import feature_cap
                max_features = feature_cap(
                    getattr(team_platform.platform_generation, 'scenario', None))
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


class DecisionPlatformDevelopmentSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
    # committed_cost is advisory: the server sets it from the scenario
    # (`enforce_authoritative_costs`). Leaving it required would refuse a
    # submission that declines to name a price at all, which is the shape a
    # client should be free to send once the price is not its business.
    committed_cost = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False)

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
        # Same single statement of the cap. Read unscoped, this took whichever
        # scenario's row came back first.
        from core.services.rd_costs import feature_cap
        generation = self.initial_data.get('platform_generation') if isinstance(
            getattr(self, 'initial_data', None), dict) else None
        scenario = None
        if generation is not None:
            from core.models.scenario import PlatformGenerationDefinition
            row = PlatformGenerationDefinition.objects.filter(
                pk=generation).select_related('scenario').first()
            scenario = getattr(row, 'scenario', None)
        max_features = feature_cap(scenario)
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


class DecisionMarketingSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
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


class DecisionMarketEntrySerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
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


class DecisionPlantSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = DecisionPlant
        fields = [
            'id',
            'market', 'action', 'capacity_units', 'contract_mfg_volume',
        ]


class DecisionPartnershipSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
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


class DecisionESGSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = DecisionESG
        fields = [
            'id',
            'environmental_investment', 'social_investment', 'governance_commitments',
        ]
        extra_kwargs = {
            'governance_commitments': {'required': False, 'allow_null': True},
        }


class DecisionTalentSerializer(NonNegativeFieldsMixin, serializers.ModelSerializer):
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

    def validate(self, attrs):
        """Reject payloads the resolution manifest would later refuse."""
        investments = attrs.get('rd_investments')
        if investments is not None:
            try:
                validate_rd_investment_targets(investments)
            except serializers.ValidationError as error:
                raise serializers.ValidationError({'rd_investments': error.detail})
        # The same enforcement the per-type surface applies, so a price
        # cannot be authoritative on one endpoint and client-supplied on the
        # other.
        investments_for_cost = attrs.get('rd_investments')
        if investments_for_cost is not None:
            submitting_team = attrs.get('team') or getattr(
                self.instance, 'team', None)
            enforce_authoritative_costs(
                investments_for_cost, 'rd', team=submitting_team)
        developments = attrs.get('platform_developments')
        if developments is not None:
            round_obj = attrs.get('round') or getattr(self.instance, 'round', None)
            enforce_authoritative_costs(
                developments, 'platform',
                round_number=getattr(round_obj, 'round_number', None))

        creates = attrs.get('product_creates')
        if creates is not None:
            # A partial update need not carry the team, so fall back to the
            # submission being edited.
            team = attrs.get('team') or getattr(self.instance, 'team', None)
            try:
                validate_product_names(creates, team)
            except serializers.ValidationError as error:
                raise serializers.ValidationError({'product_creates': error.detail})
        return attrs

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
