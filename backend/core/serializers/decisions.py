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
from core.serializers.decision_limits import NonNegativeFieldsMixin, non_negative_message
from core.utils.localization import get_localized_field
from core.utils.participant_messages import (
    field_label, participant_message, serializer_language,
)

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


def validate_rd_investment_targets(investments, language='en'):
    """Require an unambiguous single operation for each platform feature."""
    targets = [
        (item['team_platform'].pk, item['feature'].pk)
        for item in investments
    ]
    if len(targets) != len(set(targets)):
        raise serializers.ValidationError(participant_message(
            'one_rd_investment_per_feature', language=language))


def _quoted(names):
    return ', '.join(f'"{name}"' for name in names)


def validate_product_names(creates, team, language='en'):
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
        raise serializers.ValidationError({'product_name': [participant_message(
            'product_name_repeated', language=language,
            names=_quoted(repeated))]})

    if team is None:
        return
    from core.models.team_state import TeamProduct
    # Every row counts, retired ones included: the manifest key spans the whole
    # table, so a name freed by retiring a product is not free.
    taken = sorted(TeamProduct.objects
                   .filter(team=team, name__in=names)
                   .values_list('name', flat=True))
    if taken:
        raise serializers.ValidationError({'product_name': [participant_message(
            'product_name_taken', language=language,
            names=_quoted(taken))]})


def enforce_authoritative_costs(rows, kind, team=None, round_number=None,
                                language='en'):
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
    from core.services.rd_costs import (NotPricedByLevel, UnauthoredCost,
                                        platform_cost_for, rd_investment_cost)

    from core.services.rd_costs import (duplicate_generation_problem,
                                        held_generation_problem,
                                        ownership_problem, unlock_problem)

    field = 'committed_cost' if kind == 'platform' else 'calculated_cost'
    price = platform_cost_for if kind == 'platform' else rd_investment_cost
    errors = []
    if kind == 'platform':
        # A cross-row rule: one generation per submission (V2-046). Raised
        # before any row is priced so a refusal writes none of the replacement
        # payload.
        duplicate = duplicate_generation_problem(rows)
        if duplicate:
            raise serializers.ValidationError({'platform_generation': [
                participant_message('platform_request_duplicate',
                                    language=language)]})
        # V2-047: and against what the team already holds, not only against the
        # other rows in this payload.
        held = held_generation_problem(rows, team)
        if held:
            raise serializers.ValidationError({'platform_generation': [
                participant_message('platform_already_held', language=language,
                                    )]})
    if kind == 'rd' and rows:
        # R10 / V2-053. The decision is retired outright, not merely gated to
        # platforms still in development. R9 removed the processor that made it
        # do anything, so every remaining row spent a team's money and earned
        # them score while changing no product. Refusing it on the write is what
        # stops them paying for that.
        #
        # An empty list still succeeds: clearing R&D is how a team removes a
        # draft row, and refusing that would strand anyone who already has one.
        raise serializers.ValidationError({'rd_investments': [participant_message(
            'rd_investment_retired', language=language)]})
    for index, row in enumerate(rows):
        if kind == 'platform':
            # V2-039: the unlock gate belongs on the write, not only on the
            # lock. A team that never locks was defaulted at close and the
            # engine built the platform anyway.
            problem = unlock_problem(row.get('platform_generation'),
                                     round_number)
            if problem:
                generation = row.get('platform_generation')
                if generation is None:
                    errors.append(participant_message(
                        'platform_not_available', language=language))
                else:
                    errors.append(participant_message(
                        'platform_unlock_required', language=language,
                        platform=get_localized_field(
                            generation, 'name', language),
                        unlock_round=getattr(generation, 'unlock_round', ''),
                        round=round_number))
                continue
        try:
            authoritative = price(row)
        except NotPricedByLevel:
            continue        # dollar-based path: the team's amount is the input
        except UnauthoredCost as problem:
            errors.append(participant_message(
                'scenario_price_unavailable', language=language,
                row=index + 1))
            continue

        submitted = row.get(field)
        if submitted is not None and Decimal(submitted) != authoritative:
            errors.append(participant_message(
                'scenario_price_mismatch', language=language,
                row=index + 1, price=f'${authoritative:,.2f}'))
            continue
        row[field] = authoritative
        if kind == 'rd':
            # `amount` is the money leg of the same decision. It follows the
            # authored figure for the same reason.
            submitted_amount = row.get('amount')
            if (submitted_amount is not None
                    and Decimal(submitted_amount) != authoritative):
                errors.append(participant_message(
                    'scenario_price_mismatch', language=language,
                    row=index + 1, price=f'${authoritative:,.2f}'))
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

    def _non_negative(self, field_name, value):
        if value < 0:
            language = serializer_language(self)
            raise serializers.ValidationError(participant_message(
                'non_negative', language=language,
                field=field_label(field_name, language),
            ))
        return value

    def validate_rd_budget(self, value):
        return self._non_negative('rd_budget', value)

    def validate_marketing_budget(self, value):
        return self._non_negative('marketing_budget', value)

    def validate_strategy_budget(self, value):
        return self._non_negative('strategy_budget', value)

    def get_warnings(self, obj):
        warnings = []
        language = serializer_language(self)
        for field in ('rd_budget', 'marketing_budget', 'strategy_budget'):
            val = getattr(obj, field, None)
            if val is not None and val == 0:
                warnings.append(participant_message(
                    'zero_budget_warning', language=language,
                    field=field_label(field, language)))
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
        validate_rd_investment_targets(attrs, serializer_language(self))
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
            language = serializer_language(self)
            raise serializers.ValidationError(non_negative_message(
                'amount', language))
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
                language = serializer_language(self)
                raise serializers.ValidationError(participant_message(
                    'feature_unavailable', language=language,
                    feature=get_localized_field(feature, 'name', language)))

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
                    raise serializers.ValidationError(participant_message(
                        'platform_feature_limit',
                        language=serializer_language(self),
                        maximum=max_features, current=active_count))

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
                raise serializers.ValidationError(participant_message(
                    'round_feature_limit', language=serializer_language(self),
                    maximum=max_slots))

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
            raise serializers.ValidationError(participant_message(
                'platform_feature_limit', language=serializer_language(self),
                maximum=max_features, current=selected))
        return value


class DecisionProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionProductCreate
        fields = [
            'id',
            'team_platform', 'product_name', 'positioning', 'target_market_ids',
        ]

    def validate_target_market_ids(self, value):
        language = serializer_language(self)
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError(participant_message(
                'target_markets_required', language=language))
        if not all(isinstance(v, int) for v in value):
            raise serializers.ValidationError(participant_message(
                'target_markets_invalid', language=language))
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
        # An ABSENT price is a representable state (Ruling 2's blank branch):
        # accepted, alerted while the round is open, and filled at the band
        # floor at the deadline. A price that is actually stated must still be
        # positive — zero is a decision to give the product away, not a blank,
        # and negatives remain refused outright.
        if value is None:
            return value
        if value <= 0:
            raise serializers.ValidationError(participant_message(
                'positive_price', language=serializer_language(self)))
        return value

    def validate_promotion_budget(self, value):
        if value < 0:
            language = serializer_language(self)
            raise serializers.ValidationError(participant_message(
                'non_negative', language=language,
                field=field_label('promotion_budget', language)))
        return value

    def validate_production_volume(self, value):
        if value < 0:
            language = serializer_language(self)
            raise serializers.ValidationError(participant_message(
                'non_negative', language=language,
                field=field_label('production_volume', language)))
        return value

    def validate_demand_estimate(self, value):
        if value < 0:
            language = serializer_language(self)
            raise serializers.ValidationError(participant_message(
                'non_negative', language=language,
                field=field_label('demand_estimate', language)))
        return value

    def validate_campaign_focus_feature_ids(self, value):
        # An EMPTY campaign focus is representable, and deliberately so. R15
        # and R24 require a marketing row to be storable purely to carry a
        # price -- including a blank one, which is then filled at the band
        # floor or marked not-for-sale at the deadline. Demanding one to three
        # focus features on every row made that row unstorable, so the pricing
        # screen's own default payload was refused outright (F7) and with it
        # every other row in the same request.
        #
        # A campaign focus is a real decision only when there is a campaign to
        # aim: the "choose one to three" rule is therefore enforced in
        # validate() below, against promotion spend, rather than here.
        if not isinstance(value, list):
            raise serializers.ValidationError(participant_message(
                'campaign_features_invalid', language=serializer_language(self)))
        if len(value) > 3:
            raise serializers.ValidationError(participant_message(
                'campaign_features_required', language=serializer_language(self)))
        if not all(isinstance(v, int) for v in value):
            raise serializers.ValidationError(participant_message(
                'campaign_features_invalid', language=serializer_language(self)))
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # Spending on promotion without saying what the campaign is about is
        # still refused; an unpromoted row simply has no campaign to describe.
        promotion = attrs.get('promotion_budget')
        if promotion is not None and promotion > 0 and not attrs.get(
                'campaign_focus_feature_ids'):
            raise serializers.ValidationError({
                'campaign_focus_feature_ids': participant_message(
                    'campaign_features_required',
                    language=serializer_language(self)),
            })
        digital = attrs.get('channel_digital_pct')
        traditional = attrs.get('channel_traditional_pct')
        trade = attrs.get('channel_trade_pct')
        if digital is not None and traditional is not None and trade is not None:
            total = digital + traditional + trade
            if abs(total - Decimal('1.0')) > Decimal('0.001'):
                raise serializers.ValidationError({
                    'channel_digital_pct': participant_message(
                        'channel_total', language=serializer_language(self),
                        total=f'{total * 100:g}'),
                })
        return attrs

    def get_warnings(self, obj):
        warnings = []
        if obj.pk is None:
            return warnings
        language = serializer_language(self)

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
                warnings.append(participant_message(
                    'production_capacity_exceeded', language=language,
                    volume=production_volume, capacity=total_capacity,
                    market=get_localized_field(
                        source_market, 'name', language)))
            else:
                cap = source_market.contract_mfg_capacity_cap or 0
                effective_cap = total_capacity + cap
                if production_volume > effective_cap:
                    warnings.append(participant_message(
                        'production_capacity_with_contract_exceeded',
                        language=language, volume=production_volume,
                        capacity=total_capacity, contract_capacity=cap,
                        market=get_localized_field(
                            source_market, 'name', language)))

        # Stage 5 price band (Ruling 2). An out-of-band price is ALERTED here
        # and accepted: the team's number is what gets stored while the round
        # is open, and the deadline is the only place it changes. Both write
        # surfaces return this serializer, so neither can alert differently
        # from the other, and the range named here comes from the same
        # calculator the deadline applies.
        from core.services import price_band as band_rules
        band = band_rules.price_band(
            obj.submission.team.game.scenario, team, obj.team_product,
            obj.market, obj.submission.round.round_number)
        # The product name is the team's own and has no translation; the
        # market name is scenario content and does.
        band_alert = band_rules.alert_for(
            obj.retail_price, band, product_name=obj.team_product.name,
            market_name=get_localized_field(obj.market, 'name', language),
            language=language)
        if band_alert:
            warnings.append(band_alert)

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
            raise serializers.ValidationError(non_negative_message(
                'new_debt', serializer_language(self)))
        return value

    def validate_debt_repayment(self, value):
        if value < 0:
            raise serializers.ValidationError(non_negative_message(
                'debt_repayment', serializer_language(self)))
        return value

    def validate_new_equity(self, value):
        if value < 0:
            raise serializers.ValidationError(non_negative_message(
                'new_equity', serializer_language(self)))
        return value

    def validate_dividend_per_share(self, value):
        if value < 0:
            raise serializers.ValidationError(non_negative_message(
                'dividend_per_share', serializer_language(self)))
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
            raise serializers.ValidationError(non_negative_message(
                'allocation_amount', serializer_language(self)))
        return value


# ---------------------------------------------------------------------------
# CC-31A: Talent Allocation & Compliance Investment serializers
# ---------------------------------------------------------------------------

TALENT_POOLS = ('rd', 'commercial', 'operations')


def talent_headcounts(talent):
    """{pool: headcount} from a stored staffing decision or a validated one.

    A validated payload may omit a headcount; the per-type route then stores
    the model's default for it, so that default is the headcount to total
    against.
    """
    from core.models.talent import DecisionTalent
    counts = {}
    for pool in TALENT_POOLS:
        name = f'{pool}_headcount'
        if isinstance(talent, dict):
            counts[pool] = talent.get(
                name, DecisionTalent._meta.get_field(name).default)
        else:
            counts[pool] = getattr(talent, name)
    return counts


def validate_talent_allocations(rows, submission, language='en',
                                headcounts=None):
    """The staff-allocation rules, for every route that stores an allocation.

    These rules were written inside `TalentAllocationSerializer.validate`,
    which read the submission from the serializer context -- and no route ever
    put one there, so they ran nowhere: the whole-submission route stored any
    allocation at all, and the per-type route had no such section. They are one
    function now so both routes apply the same rule to the same rows.

    `rows` are validated allocation dicts (or stored rows reduced to the same
    keys). `headcounts` overrides the stored staffing decision, for a request
    that changes staffing and allocation together.
    """
    rows = list(rows or [])
    if not rows:
        return

    pools = [row.get('talent_pool') for row in rows]
    if len(set(pools)) != len(pools):
        # Not reachable from the page. Refused here because the table is
        # unique on (submission, pool): the alternative is a 500.
        raise serializers.ValidationError({'talent_allocations': [
            participant_message('request_incomplete', language=language)]})

    if headcounts is None:
        from core.models.talent import DecisionTalent
        try:
            if submission is None:
                raise DecisionTalent.DoesNotExist
            headcounts = talent_headcounts(submission.talent)
        except DecisionTalent.DoesNotExist:
            raise serializers.ValidationError({'talent_allocations': [
                participant_message('talent_decision_required',
                                    language=language)]})

    from core.models.team_state import TeamMarketPresence
    active_codes = set()
    if submission is not None:
        active_codes = set(
            TeamMarketPresence.objects.filter(
                team=submission.team, status='active',
            ).values_list('market__code', flat=True))

    for row in rows:
        total_headcount = headcounts.get(row.get('talent_pool'), 0)
        market_allocation = row.get('market_allocation') or {}
        hq_count = row.get('hq_count', 0)

        # Sum must equal total headcount
        allocated = hq_count + sum(market_allocation.values())
        if allocated != total_headcount:
            raise serializers.ValidationError({'talent_allocations': [
                participant_message(
                    'talent_allocation_total', language=language,
                    allocated=allocated, headcount=total_headcount)]})

        # Cannot allocate to markets the team hasn't entered
        for code, count in market_allocation.items():
            if code not in active_codes and count > 0:
                raise serializers.ValidationError({'talent_allocations': [
                    participant_message('talent_market_inactive',
                                        language=language)]})

        # HQ minimum: at least 20% of headcount
        min_hq = max(1, int(total_headcount * 0.2))
        if total_headcount > 0 and hq_count < min_hq:
            raise serializers.ValidationError({'talent_allocations': [
                participant_message('talent_hq_minimum', language=language,
                                    minimum=min_hq)]})


def validate_compliance_investments(rows, team, language='en'):
    """Compliance is invested in a market the team operates in, once each.

    `strategy_effects._process_compliance` reads a row only for an active
    market presence, so a row for any other market is a decision the engine
    would silently not act on. It is refused on the write instead.
    """
    rows = list(rows or [])
    if not rows:
        return
    market_ids = [getattr(row.get('market'), 'id', row.get('market'))
                  for row in rows]
    if len(set(market_ids)) != len(market_ids):
        # Unique on (submission, market); see the pool check above.
        raise serializers.ValidationError({'compliance_investments': [
            participant_message('request_incomplete', language=language)]})
    if team is None:
        return
    from core.models.team_state import TeamMarketPresence
    active_ids = set(TeamMarketPresence.objects.filter(
        team=team, status='active').values_list('market_id', flat=True))
    if any(market_id not in active_ids for market_id in market_ids):
        raise serializers.ValidationError({'compliance_investments': [
            participant_message('compliance_market_inactive',
                                language=language)]})


class TalentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        from core.models.cc31_models import TalentAllocation
        model = TalentAllocation
        fields = ['id', 'talent_pool', 'hq_count', 'market_allocation']

    def validate_hq_count(self, value):
        if value < 0:
            raise serializers.ValidationError(non_negative_message(
                'hq_count', serializer_language(self)))
        return value

    def validate_market_allocation(self, value):
        """{market code: whole, non-negative headcount}.

        The column is JSON, so nothing else checks its contents, and the
        engine reads each value as a number. A negative count would also let a
        total balance that is not an allocation (60 at HQ, -10 in a market).
        """
        language = serializer_language(self)
        if not isinstance(value, dict):
            raise serializers.ValidationError(participant_message(
                'request_incomplete', language=language))
        for code, count in value.items():
            if isinstance(count, bool) or not isinstance(count, int):
                raise serializers.ValidationError(participant_message(
                    'whole_number_required', language=language,
                    field=field_label('market_allocation', language)))
            if count < 0:
                raise serializers.ValidationError(non_negative_message(
                    'market_allocation', language))
        return value

    def validate(self, data):
        # Kept for a caller that validates one row with the submission in its
        # context. The routes call `validate_talent_allocations` themselves,
        # because the rules span rows and need the staffing decision.
        submission = self.context.get('submission')
        if not submission:
            return data
        validate_talent_allocations(
            [data], submission, serializer_language(self))
        return data


class ComplianceInvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        from core.models.cc31_models import ComplianceInvestment
        model = ComplianceInvestment
        fields = ['id', 'market', 'investment_amount']

    def validate_investment_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(non_negative_message(
                'investment_amount', serializer_language(self)))
        if value > 10000000:
            raise serializers.ValidationError(participant_message(
                'compliance_maximum', language=serializer_language(self)))
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
                validate_rd_investment_targets(
                    investments, serializer_language(self))
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
                investments_for_cost, 'rd', team=submitting_team,
                language=serializer_language(self))
        developments = attrs.get('platform_developments')
        if developments is not None:
            round_obj = attrs.get('round') or getattr(self.instance, 'round', None)
            submitting_team = attrs.get('team') or getattr(
                self.instance, 'team', None)
            enforce_authoritative_costs(
                developments, 'platform', team=submitting_team,
                round_number=getattr(round_obj, 'round_number', None),
                language=serializer_language(self))

        creates = attrs.get('product_creates')
        if creates is not None:
            # A partial update need not carry the team, so fall back to the
            # submission being edited.
            team = attrs.get('team') or getattr(self.instance, 'team', None)
            try:
                validate_product_names(creates, team, serializer_language(self))
            except serializers.ValidationError as error:
                raise serializers.ValidationError({'product_creates': error.detail})

        # The same two checks the per-type route makes. On this route the
        # allocation rules had never run at all (see
        # `validate_talent_allocations`). A staffing decision cannot be written
        # here, so a submission that does not exist yet cannot have one.
        staff_rows = attrs.get('talent_allocations')
        if staff_rows:
            validate_talent_allocations(
                staff_rows, self.instance, serializer_language(self))
        compliance_rows = attrs.get('compliance_investments')
        if compliance_rows:
            validate_compliance_investments(
                compliance_rows,
                attrs.get('team') or getattr(self.instance, 'team', None),
                serializer_language(self))
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
