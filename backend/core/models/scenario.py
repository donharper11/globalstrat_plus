"""
Group 2: Scenario Configuration Models (from 04-data-model.md)

These define WHAT game is being played. All industry-agnostic.
21 tables implementing the complete scenario configuration layer.
"""
from django.db import models
from django.conf import settings


# ---------------------------------------------------------------------------
# Tier 1 — No FK dependencies outside Django auth
# ---------------------------------------------------------------------------

class Scenario(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    industry_label = models.CharField(max_length=100)
    description = models.TextField()
    num_rounds = models.IntegerField(default=10)
    round_duration_label = models.CharField(max_length=50, default='Quarter')
    starting_cash = models.DecimalField(max_digits=15, decimal_places=2)
    currency_code = models.CharField(max_length=10, default='USD')
    max_platforms_per_team = models.IntegerField(default=3)
    max_products_per_platform = models.IntegerField(default=4)
    max_products_total = models.IntegerField(default=6)
    performance_index_base = models.DecimalField(max_digits=5, decimal_places=2, default=55.00)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='created_scenarios',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scenario'

    def __str__(self):
        return self.name


class ScenarioConfig(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='configs')
    config_key = models.CharField(max_length=100)
    config_value = models.TextField()
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'scenario_config'
        unique_together = [('scenario', 'config_key')]

    def __str__(self):
        return f"{self.scenario.name} — {self.config_key}"


# ---------------------------------------------------------------------------
# Tier 2 — Depends on Scenario only
# ---------------------------------------------------------------------------

class FeatureDefinition(models.Model):
    LAYER_CHOICES = [
        ('platform', 'Platform / R&D'),
        ('marketing', 'Marketing Mix'),
        ('strategy', 'Strategy Mix'),
    ]
    COST_CURVE_CHOICES = [
        ('linear', 'Linear'),
        ('diminishing', 'Diminishing Returns'),
        ('exponential', 'Exponential'),
        ('step', 'Step Function'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='feature_definitions')
    layer = models.CharField(max_length=20, choices=LAYER_CHOICES)
    category = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    code = models.CharField(max_length=50)
    min_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    max_value = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    default_value = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    cost_curve_type = models.CharField(max_length=20, choices=COST_CURVE_CHOICES)
    cost_base = models.DecimalField(max_digits=15, decimal_places=2)
    time_lag_rounds = models.IntegerField(default=1)
    is_licensable = models.BooleanField(default=True)
    license_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    display_order = models.IntegerField(default=0)
    icon_key = models.CharField(max_length=50, null=True, blank=True)
    is_derived = models.BooleanField(default=False)
    is_market_specific = models.BooleanField(default=False)

    class Meta:
        db_table = 'feature_definition'
        ordering = ['display_order', 'name']
        unique_together = [('scenario', 'code')]

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class PlatformGenerationDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='platform_generations')
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    generation_order = models.IntegerField()
    unlock_round = models.IntegerField(default=0)
    development_cost = models.DecimalField(max_digits=15, decimal_places=2)
    development_rounds = models.IntegerField(default=2)
    license_cost = models.DecimalField(max_digits=15, decimal_places=2)
    annual_maintenance_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_starting_platform = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_generation_definition'
        unique_together = [('scenario', 'generation_order')]

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class MarketDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='markets')
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    display_name_zh = models.CharField(max_length=200, blank=True, default='')
    code = models.CharField(max_length=20)
    description = models.TextField()
    market_description_zh = models.TextField(blank=True, default='')
    currency_code = models.CharField(max_length=10)
    exchange_rate_base = models.DecimalField(max_digits=10, decimal_places=4)
    exchange_rate_volatility = models.DecimalField(max_digits=5, decimal_places=4, default=0.05)
    base_growth_rate = models.DecimalField(max_digits=5, decimal_places=4)
    entry_cost_base = models.DecimalField(max_digits=15, decimal_places=2)
    tariff_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4)
    regulatory_difficulty = models.DecimalField(max_digits=5, decimal_places=2)
    infrastructure_quality = models.DecimalField(max_digits=5, decimal_places=2)
    base_manufacturing_cost = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    allows_manufacturing = models.BooleanField(default=False)
    plant_build_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    plant_build_rounds = models.IntegerField(default=2)
    plant_capacity_units = models.IntegerField(null=True, blank=True)
    contract_mfg_available = models.BooleanField(default=False)
    contract_mfg_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.30)
    contract_mfg_capacity_cap = models.IntegerField(null=True, blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'market_definition'
        ordering = ['display_order', 'name']
        unique_together = [('scenario', 'code')]

    @property
    def description_zh(self):
        """Alias for market_description_zh to work with get_localized_field."""
        return self.market_description_zh

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class EntryModeDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='entry_modes')
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    code = models.CharField(max_length=50)
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    capital_requirement = models.DecimalField(max_digits=15, decimal_places=2)
    setup_rounds = models.IntegerField(default=0)
    control_level = models.DecimalField(max_digits=5, decimal_places=2)
    risk_level = models.DecimalField(max_digits=5, decimal_places=2)
    local_presence_score = models.DecimalField(max_digits=5, decimal_places=2)
    logistics_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    tariff_applies = models.BooleanField(default=True)
    max_per_market = models.IntegerField(default=1)

    class Meta:
        db_table = 'entry_mode_definition'
        unique_together = [('scenario', 'code')]

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class StrategyOptionDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='strategy_options')
    category = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    code = models.CharField(max_length=50)
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    capital_cost_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    capital_cost_is_percentage = models.BooleanField(default=False)
    recurring_cost_per_round = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    time_lag_rounds = models.IntegerField(default=0)
    is_reversible = models.BooleanField(default=True)
    reversal_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=0.50)
    mutually_exclusive_with = models.CharField(max_length=200, null=True, blank=True)
    prerequisite_codes = models.CharField(max_length=200, null=True, blank=True)
    max_per_market = models.IntegerField(null=True, blank=True)
    max_per_round = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'strategy_option_definition'
        unique_together = [('scenario', 'code')]

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class AICompetitorDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='ai_competitors')
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(null=True, blank=True)
    description_zh = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'ai_competitor_definition'

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


# ---------------------------------------------------------------------------
# Tier 3 — Depends on Tier 2 models
# ---------------------------------------------------------------------------

class PlatformFeatureCeiling(models.Model):
    id = models.BigAutoField(primary_key=True)
    platform_generation = models.ForeignKey(
        PlatformGenerationDefinition, on_delete=models.PROTECT,
        related_name='feature_ceilings',
    )
    feature = models.ForeignKey(
        FeatureDefinition, on_delete=models.PROTECT,
        related_name='platform_ceilings',
    )
    ceiling_value = models.DecimalField(max_digits=5, decimal_places=2)
    starting_value = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = 'platform_feature_ceiling'
        unique_together = [('platform_generation', 'feature')]

    def __str__(self):
        return f"{self.platform_generation.name} — {self.feature.name} (ceiling={self.ceiling_value})"


class MarketReadiness(models.Model):
    id = models.BigAutoField(primary_key=True)
    market = models.ForeignKey(MarketDefinition, on_delete=models.PROTECT, related_name='readiness_schedule')
    platform_generation = models.ForeignKey(
        PlatformGenerationDefinition, on_delete=models.PROTECT,
        related_name='market_readiness',
    )
    round_number = models.IntegerField()
    readiness_pct = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        db_table = 'market_readiness'
        unique_together = [('market', 'platform_generation', 'round_number')]

    def __str__(self):
        return f"{self.market.name} — Gen {self.platform_generation.generation_order} R{self.round_number}"


class SegmentDefinition(models.Model):
    SEGMENT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('investor', 'Investor'),
        ('regulator', 'Regulator'),
        ('channel_partner', 'Channel Partner'),
        ('community', 'Community'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='segments')
    market = models.ForeignKey(
        MarketDefinition, on_delete=models.PROTECT,
        null=True, blank=True, related_name='segments',
    )
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    population_size = models.IntegerField()
    population_growth_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000)
    bass_p = models.DecimalField(max_digits=8, decimal_places=6)
    bass_q = models.DecimalField(max_digits=8, decimal_places=6)
    performance_index_weight = models.DecimalField(max_digits=5, decimal_places=4)
    revenue_per_unit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_generation_required = models.IntegerField(null=True, blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'segment_definition'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class StrategyOptionEffect(models.Model):
    EFFECT_TYPE_CHOICES = [
        ('set', 'Set'),
        ('add', 'Add'),
        ('multiply', 'Multiply'),
    ]

    id = models.BigAutoField(primary_key=True)
    strategy_option = models.ForeignKey(
        StrategyOptionDefinition, on_delete=models.PROTECT,
        related_name='effects',
    )
    feature = models.ForeignKey(
        FeatureDefinition, on_delete=models.PROTECT,
        related_name='strategy_effects',
    )
    effect_type = models.CharField(max_length=10, choices=EFFECT_TYPE_CHOICES)
    effect_value = models.DecimalField(max_digits=8, decimal_places=4)
    market_specific = models.BooleanField(default=True)

    class Meta:
        db_table = 'strategy_option_effect'

    def __str__(self):
        return f"{self.strategy_option.name} → {self.feature.name} ({self.effect_type} {self.effect_value})"


class EventTemplateDefinition(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='event_templates')
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description_template = models.TextField()
    description_template_zh = models.TextField(blank=True, default='')
    category = models.CharField(max_length=100)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    probability_per_round = models.DecimalField(max_digits=5, decimal_places=4)
    earliest_round = models.IntegerField(default=1)
    latest_round = models.IntegerField(null=True, blank=True)
    max_occurrences = models.IntegerField(default=1)
    affects_all_markets = models.BooleanField(default=False)
    target_market = models.ForeignKey(
        MarketDefinition, on_delete=models.PROTECT,
        null=True, blank=True, related_name='targeted_events',
    )
    response_required = models.BooleanField(default=False)
    response_deadline_rounds = models.IntegerField(default=0)
    rag_source_tags = models.CharField(max_length=500, null=True, blank=True)

    # CC-31E: Team-specific targeting
    TARGET_TYPE_CHOICES = [
        ('MARKET_WIDE', 'Affects all teams in the market'),
        ('TEAM_SPECIFIC', 'Targets specific teams based on conditions'),
    ]
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default='MARKET_WIDE',
        help_text="MARKET_WIDE fires once for the market. TEAM_SPECIFIC evaluates per-team.",
    )
    trigger_condition = models.JSONField(
        null=True, blank=True, default=None,
        help_text="JSON condition(s) evaluated per-team for TEAM_SPECIFIC events. "
                  "Single dict or list of dicts (AND logic). "
                  "Format: {attribute, operator, value}.",
    )
    affected_markets = models.JSONField(
        null=True, blank=True, default=None,
        help_text="List of market codes where this event can fire. Null = use target_market/affects_all_markets logic.",
    )
    # CC-19: supply-chain event effect parameters (affected_suppliers/lanes,
    # capacity_reduction_pct, recovery_rounds, additional_lead_time_days,
    # mode_rate_multiplier, etc.). Populated by the loader for category=supply_chain.
    sc_effects = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'event_template_definition'

    def __str__(self):
        return f"{self.scenario.name} — {self.name}"


class FirmStarterProfile(models.Model):
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name='starter_profiles')
    profile_name = models.CharField(max_length=200)
    profile_name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    home_market = models.ForeignKey(MarketDefinition, on_delete=models.PROTECT, related_name='starter_profiles')
    starting_cash = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    starting_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    starting_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'firm_starter_profile'

    def __str__(self):
        return f"{self.scenario.name} — {self.profile_name}"


class MarketConditionByRound(models.Model):
    id = models.BigAutoField(primary_key=True)
    market = models.ForeignKey(MarketDefinition, on_delete=models.PROTECT, related_name='conditions_by_round')
    round_number = models.IntegerField()
    growth_rate_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000)
    exchange_rate_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000)
    tariff_rate_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000)
    demand_multiplier = models.DecimalField(max_digits=5, decimal_places=4, default=1.0000)
    market_outlook_narrative = models.TextField(null=True, blank=True)
    rag_source_tags = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'market_condition_by_round'
        unique_together = [('market', 'round_number')]

    def __str__(self):
        return f"{self.market.name} — Round {self.round_number}"


# ---------------------------------------------------------------------------
# Tier 4 — Depends on Tier 3 models
# ---------------------------------------------------------------------------

class SegmentPreference(models.Model):
    id = models.BigAutoField(primary_key=True)
    segment = models.ForeignKey(SegmentDefinition, on_delete=models.PROTECT, related_name='preferences')
    feature = models.ForeignKey(FeatureDefinition, on_delete=models.PROTECT, related_name='segment_preferences')
    ideal_value = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=4)
    tolerance = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = 'segment_preference'
        unique_together = [('segment', 'feature')]

    def __str__(self):
        return f"{self.segment.name} — {self.feature.name} (ideal={self.ideal_value})"


class EventImpactDefinition(models.Model):
    IMPACT_TYPE_CHOICES = [
        ('preference_shift', 'Preference Shift'),
        ('market_condition', 'Market Condition'),
        ('cost_change', 'Cost Change'),
        ('demand_shock', 'Demand Shock'),
        ('exchange_rate', 'Exchange Rate'),
    ]

    id = models.BigAutoField(primary_key=True)
    event_template = models.ForeignKey(
        EventTemplateDefinition, on_delete=models.PROTECT,
        related_name='impacts',
    )
    impact_type = models.CharField(max_length=20, choices=IMPACT_TYPE_CHOICES)
    target_segment = models.ForeignKey(
        SegmentDefinition, on_delete=models.PROTECT,
        null=True, blank=True, related_name='event_impacts',
    )
    target_feature = models.ForeignKey(
        FeatureDefinition, on_delete=models.PROTECT,
        null=True, blank=True, related_name='event_impacts',
    )
    target_market = models.ForeignKey(
        MarketDefinition, on_delete=models.PROTECT,
        null=True, blank=True, related_name='event_impacts',
    )
    target_field = models.CharField(max_length=100, null=True, blank=True)
    impact_value = models.DecimalField(max_digits=10, decimal_places=4)
    duration_rounds = models.IntegerField(default=0)
    is_cumulative = models.BooleanField(default=False)

    class Meta:
        db_table = 'event_impact_definition'

    def __str__(self):
        return f"{self.event_template.name} — {self.impact_type}"


class EventResponseDefinition(models.Model):
    id = models.BigAutoField(primary_key=True)
    event_template = models.ForeignKey(
        EventTemplateDefinition, on_delete=models.PROTECT,
        related_name='responses',
    )
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    effects = models.JSONField(default=list)
    rag_alignment_tags = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'event_response_definition'

    def __str__(self):
        return f"{self.event_template.name} — {self.name}"


class FirmStarterPlatformConfig(models.Model):
    id = models.BigAutoField(primary_key=True)
    firm_starter_profile = models.ForeignKey(
        FirmStarterProfile, on_delete=models.PROTECT,
        related_name='platform_configs',
    )
    platform_generation = models.ForeignKey(
        PlatformGenerationDefinition, on_delete=models.PROTECT,
        related_name='starter_configs',
    )
    platform_label = models.CharField(max_length=20, default='alpha')
    feature = models.ForeignKey(
        FeatureDefinition, on_delete=models.PROTECT,
        related_name='starter_configs',
    )
    starting_level = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = 'firm_starter_platform_config'
        unique_together = [('firm_starter_profile', 'platform_label', 'feature')]

    def __str__(self):
        return f"{self.firm_starter_profile.profile_name} — {self.platform_label}/{self.feature.name} = {self.starting_level}"


class FirmStarterProduct(models.Model):
    id = models.BigAutoField(primary_key=True)
    firm_starter_profile = models.ForeignKey(
        FirmStarterProfile, on_delete=models.PROTECT,
        related_name='starter_products',
    )
    product_name = models.CharField(max_length=200)
    positioning_label = models.CharField(max_length=50)
    base_price = models.DecimalField(max_digits=15, decimal_places=2)
    market = models.ForeignKey(MarketDefinition, on_delete=models.PROTECT, related_name='starter_products')
    unit_volume = models.IntegerField()
    market_share_pct = models.DecimalField(max_digits=5, decimal_places=4)
    platform_label = models.CharField(max_length=20, default='alpha')

    class Meta:
        db_table = 'firm_starter_product'

    def __str__(self):
        return f"{self.firm_starter_profile.profile_name} — {self.product_name} ({self.platform_label})"


class FeatureLevelCost(models.Model):
    """Defines the cost to develop each feature to each level on each platform generation."""
    id = models.BigAutoField(primary_key=True)
    feature = models.ForeignKey(
        FeatureDefinition, on_delete=models.CASCADE,
        related_name='level_costs',
    )
    platform_generation = models.ForeignKey(
        PlatformGenerationDefinition, on_delete=models.CASCADE,
        related_name='feature_level_costs',
    )
    level = models.IntegerField()
    cumulative_cost = models.DecimalField(max_digits=15, decimal_places=2)
    incremental_cost = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'feature_level_cost'
        unique_together = [('feature', 'platform_generation', 'level')]
        ordering = ['feature', 'platform_generation', 'level']

    def __str__(self):
        return f"{self.feature.name} Gen{self.platform_generation.generation_order} L{self.level} — ${self.incremental_cost}"


class AICompetitorFitByRound(models.Model):
    id = models.BigAutoField(primary_key=True)
    ai_competitor = models.ForeignKey(
        AICompetitorDefinition, on_delete=models.PROTECT,
        related_name='fit_by_round',
    )
    segment = models.ForeignKey(
        SegmentDefinition, on_delete=models.PROTECT,
        related_name='ai_competitor_fits',
    )
    market = models.ForeignKey(
        MarketDefinition, on_delete=models.PROTECT,
        related_name='ai_competitor_fits',
    )
    round_number = models.IntegerField()
    fit_score = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        db_table = 'ai_competitor_fit_by_round'
        unique_together = [('ai_competitor', 'segment', 'market', 'round_number')]

    def __str__(self):
        return f"{self.ai_competitor.name} — {self.segment.name} R{self.round_number}"


class AcquisitionTarget(models.Model):
    """Pre-defined acquisition targets available in each market."""
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='acquisition_targets')
    market = models.ForeignKey(MarketDefinition, on_delete=models.PROTECT, related_name='acquisition_targets')
    target_name = models.CharField(max_length=200)
    target_name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    base_acquisition_cost = models.DecimalField(max_digits=15, decimal_places=2)
    market_share_gained = models.DecimalField(max_digits=5, decimal_places=4)
    includes_plant = models.BooleanField(default=False)
    plant_capacity = models.IntegerField(default=0)
    includes_distribution = models.BooleanField(default=False)
    distribution_reach_bonus = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    talent_bonus = models.JSONField(default=dict)
    min_round_available = models.IntegerField(default=2)
    requires_market_presence = models.BooleanField(default=True)
    integration_rounds = models.IntegerField(default=2)
    integration_cost_per_round = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'acquisition_target'
        unique_together = [('scenario', 'market')]

    def __str__(self):
        return f"{self.target_name} ({self.market.name})"


class AICompetitorBehavior(models.Model):
    """Behavioral rules for dynamic AI competitor scoring."""
    STRATEGY_CHOICES = [
        ('aggressive', 'Aggressive — pursues market share'),
        ('defensive', 'Defensive — protects existing position'),
        ('niche', 'Niche — focuses on specific segments'),
        ('adaptive', 'Adaptive — responds to market leader'),
    ]
    ai_competitor = models.OneToOneField(
        AICompetitorDefinition, on_delete=models.CASCADE, related_name='behavior',
    )
    strategy_type = models.CharField(max_length=30, choices=STRATEGY_CHOICES)
    price_sensitivity = models.DecimalField(max_digits=3, decimal_places=2, default=0.5)
    innovation_rate = models.DecimalField(max_digits=3, decimal_places=2, default=0.3)
    market_entry_threshold = models.DecimalField(max_digits=5, decimal_places=4, default=0.05)
    primary_segments = models.JSONField(default=list)

    class Meta:
        db_table = 'ai_competitor_behavior'

    def __str__(self):
        return f"{self.ai_competitor.name} — {self.strategy_type}"
