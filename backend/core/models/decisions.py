"""
Group 5: Decision Models (from 04-data-model.md tables 5.1-5.15)

Per-round decision submissions. Each decision type gets its own table
for clean validation and querying.
"""
from django.db import models
from django.conf import settings


# ---------------------------------------------------------------------------
# Tier 1 — Master submission record
# ---------------------------------------------------------------------------

class DecisionSubmission(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('locked', 'Locked'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='decision_submissions',
    )
    round = models.ForeignKey(
        'core.Round', on_delete=models.PROTECT, related_name='decision_submissions',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='locked_submissions',
    )
    team_notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'decision_submission'
        unique_together = [('team', 'round')]

    def __str__(self):
        return f"{self.team.name} — Round {self.round.round_number} ({self.status})"


# ---------------------------------------------------------------------------
# Tier 2 — All decision detail tables (FK → DecisionSubmission)
# ---------------------------------------------------------------------------

class DecisionBudgetAllocation(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.OneToOneField(
        DecisionSubmission, on_delete=models.CASCADE, related_name='budget_allocation',
    )
    rd_budget = models.DecimalField(max_digits=15, decimal_places=2)
    marketing_budget = models.DecimalField(max_digits=15, decimal_places=2)
    strategy_budget = models.DecimalField(max_digits=15, decimal_places=2)
    research_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'decision_budget_allocation'

    def __str__(self):
        return f"Budget for {self.submission}"


class DecisionRDInvestment(models.Model):
    METHOD_CHOICES = [
        ('in_house', 'In-House'),
        ('license', 'License'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='rd_investments',
    )
    team_platform = models.ForeignKey(
        'core.TeamPlatform', on_delete=models.PROTECT, related_name='rd_investments',
    )
    feature = models.ForeignKey(
        'core.FeatureDefinition', on_delete=models.PROTECT, related_name='rd_investments',
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    target_level = models.IntegerField(null=True, blank=True)
    calculated_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'decision_rd_investment'

    def __str__(self):
        if self.target_level:
            return f"R&D: {self.feature.name} on {self.team_platform} → Level {self.target_level} (${self.calculated_cost})"
        return f"R&D: {self.feature.name} on {self.team_platform} — ${self.amount}"


class DecisionPlatformDevelopment(models.Model):
    METHOD_CHOICES = [
        ('in_house', 'In-House'),
        ('license', 'License'),
        ('partnership', 'Partnership'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='platform_developments',
    )
    platform_generation = models.ForeignKey(
        'core.PlatformGenerationDefinition', on_delete=models.PROTECT,
        related_name='development_decisions',
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    committed_cost = models.DecimalField(max_digits=15, decimal_places=2)
    platform_name = models.CharField(max_length=100, blank=True, default='')
    feature_levels = models.JSONField(
        default=dict, blank=True,
        help_text='Dict mapping feature_id → target_level for the new platform',
    )

    class Meta:
        db_table = 'decision_platform_development'

    def __str__(self):
        name = self.platform_name or self.platform_generation.name
        return f"Platform Dev: {name} ({self.method})"


class DecisionProductCreate(models.Model):
    POSITIONING_CHOICES = [
        ('budget', 'Budget'),
        ('mainstream', 'Mainstream'),
        ('premium', 'Premium'),
        ('ultra_premium', 'Ultra-Premium'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='product_creates',
    )
    team_platform = models.ForeignKey(
        'core.TeamPlatform', on_delete=models.PROTECT, related_name='product_create_decisions',
    )
    product_name = models.CharField(max_length=200)
    positioning = models.CharField(max_length=20, choices=POSITIONING_CHOICES)
    target_market_ids = models.JSONField()

    class Meta:
        db_table = 'decision_product_create'

    def __str__(self):
        return f"New Product: {self.product_name} ({self.positioning})"


class DecisionProductRetire(models.Model):
    TIMING_CHOICES = [
        ('immediate', 'Immediate'),
        ('end_of_round', 'End of Round'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='product_retires',
    )
    team_product = models.ForeignKey(
        'core.TeamProduct', on_delete=models.PROTECT, related_name='retire_decisions',
    )
    timing = models.CharField(max_length=20, choices=TIMING_CHOICES)

    class Meta:
        db_table = 'decision_product_retire'

    def __str__(self):
        return f"Retire: {self.team_product.name} ({self.timing})"


class DecisionMarketing(models.Model):
    DISTRIBUTION_CHOICES = [
        ('mass_retail', 'Mass Retail'),
        ('selective_retail', 'Selective Retail'),
        ('exclusive_retail', 'Exclusive Retail'),
        ('direct_online', 'Direct Online'),
        ('hybrid', 'Hybrid'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='marketing_decisions',
    )
    team_product = models.ForeignKey(
        'core.TeamProduct', on_delete=models.PROTECT, related_name='marketing_decisions',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='marketing_decisions',
    )
    retail_price = models.DecimalField(max_digits=15, decimal_places=2)
    promotion_budget = models.DecimalField(max_digits=15, decimal_places=2)
    campaign_focus_feature_ids = models.JSONField()
    channel_digital_pct = models.DecimalField(max_digits=5, decimal_places=4)
    channel_traditional_pct = models.DecimalField(max_digits=5, decimal_places=4)
    channel_trade_pct = models.DecimalField(max_digits=5, decimal_places=4)
    distribution_strategy = models.CharField(max_length=30, choices=DISTRIBUTION_CHOICES)
    distribution_investment = models.DecimalField(max_digits=15, decimal_places=2)
    sales_team_count = models.IntegerField(default=0)
    distribution_channel_detail = models.JSONField(
        default=dict, blank=True,
        help_text='Per-channel sales rep assignments, e.g. {"mass_retail": 3, "direct_online": 2}',
    )
    production_volume = models.IntegerField()
    production_source_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='production_source_decisions',
    )
    demand_estimate = models.IntegerField()

    class Meta:
        db_table = 'decision_marketing'
        unique_together = [('submission', 'team_product', 'market')]

    def __str__(self):
        return f"Marketing: {self.team_product.name} in {self.market.name}"


class DecisionMarketEntry(models.Model):
    ACTION_CHOICES = [
        ('enter', 'Enter'),
        ('change_mode', 'Change Mode'),
        ('exit', 'Exit'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='market_entries',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='entry_decisions',
    )
    entry_mode = models.ForeignKey(
        'core.EntryModeDefinition', on_delete=models.PROTECT, related_name='entry_decisions',
    )
    initial_investment = models.DecimalField(max_digits=15, decimal_places=2)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    integration_strategy = models.CharField(
        max_length=20,
        choices=[
            ('FULL', 'Full Integration'),
            ('BRAND_PRESERVE', 'Brand Preservation'),
            ('DUAL_BRAND', 'Dual Brand'),
        ],
        default='FULL',
        null=True, blank=True,
        help_text="Only applicable for acquisitions. Determines trust impact and operating cost.",
    )

    class Meta:
        db_table = 'decision_market_entry'

    def __str__(self):
        return f"Market Entry: {self.market.name} ({self.action})"


class DecisionFinancing(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.OneToOneField(
        DecisionSubmission, on_delete=models.CASCADE, related_name='financing',
    )
    new_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    debt_repayment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    new_equity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dividend_per_share = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    class Meta:
        db_table = 'decision_financing'

    def __str__(self):
        return f"Financing for {self.submission}"


class DecisionPlant(models.Model):
    ACTION_CHOICES = [
        ('build', 'Build'),
        ('expand', 'Expand'),
        ('contract_mfg', 'Contract Manufacturing'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='plant_decisions',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='plant_decisions',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    capacity_units = models.IntegerField(null=True, blank=True)
    contract_mfg_volume = models.IntegerField(null=True, blank=True)

    # SC extensions (CC-4 §4.4.1)
    SOURCING_NODE_ROLE_CHOICES = [
        ('owned_manufacturing', 'Owned Manufacturing'),
        ('contract_manufacturing', 'Contract Manufacturing'),
        ('pure_assembly', 'Pure Assembly'),
    ]
    sourcing_node_role = models.CharField(
        max_length=30, choices=SOURCING_NODE_ROLE_CHOICES,
        default='owned_manufacturing',
    )
    upstream_suppliers_required = models.JSONField(default=list)
    scope_1_co2_per_unit_kg = models.DecimalField(max_digits=7, decimal_places=3, default='0.000')
    scope_2_co2_per_unit_kg = models.DecimalField(max_digits=7, decimal_places=3, default='0.000')
    reverse_logistics_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'decision_plant'

    def __str__(self):
        return f"Plant: {self.action} in {self.market.name}"


class DecisionPartnership(models.Model):
    ACTION_CHOICES = [
        ('establish', 'Establish'),
        ('modify', 'Modify'),
        ('terminate', 'Terminate'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='partnerships',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='partnership_decisions',
    )
    strategy_option = models.ForeignKey(
        'core.StrategyOptionDefinition', on_delete=models.PROTECT,
        related_name='partnership_decisions',
    )
    annual_investment = models.DecimalField(max_digits=15, decimal_places=2)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    class Meta:
        db_table = 'decision_partnership'

    def __str__(self):
        return f"Partnership: {self.strategy_option.name} in {self.market.name} ({self.action})"


class DecisionAcquisition(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='acquisitions',
    )
    acquisition_target = models.ForeignKey(
        'core.AcquisitionTarget', on_delete=models.PROTECT, related_name='acquisition_decisions',
    )

    class Meta:
        db_table = 'decision_acquisition'

    def __str__(self):
        return f"Acquisition: {self.acquisition_target.target_name}"


class DecisionESG(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.OneToOneField(
        DecisionSubmission, on_delete=models.CASCADE, related_name='esg',
    )
    environmental_investment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    social_investment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    governance_commitments = models.JSONField(null=True, blank=True)

    # SC extensions (CC-4 §4.4.2)
    AUDIT_PROGRAM_CHOICES = [
        ('none', 'None'), ('basic', 'Basic'), ('comprehensive', 'Comprehensive'),
    ]
    UFLPA_TIER_MAPPING_CHOICES = [
        ('none', 'None'), ('partial', 'Partial'), ('full', 'Full'),
    ]
    supplier_audit_program = models.CharField(
        max_length=20, choices=AUDIT_PROGRAM_CHOICES, default='none',
    )
    scope_3_emissions_tracking = models.BooleanField(default=False)
    scope_3_investment_usd = models.IntegerField(default=0)
    cbam_reporting_readiness = models.BooleanField(default=False)
    uflpa_tier_mapping_investment = models.CharField(
        max_length=20, choices=UFLPA_TIER_MAPPING_CHOICES, default='none',
    )

    class Meta:
        db_table = 'decision_esg'

    def __str__(self):
        return f"ESG for {self.submission}"


class DecisionEventResponse(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='event_responses',
    )
    event_instance = models.ForeignKey(
        'core.EventInstance', on_delete=models.PROTECT,
        null=True, blank=True, related_name='decision_responses',
    )
    response = models.ForeignKey(
        'core.EventResponseDefinition', on_delete=models.PROTECT,
        related_name='decision_responses',
    )

    class Meta:
        db_table = 'decision_event_response'

    def __str__(self):
        return f"Event Response: event {self.event_instance} → {self.response.name}"


class DecisionResearchAllocation(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        DecisionSubmission, on_delete=models.CASCADE, related_name='research_allocations',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='research_allocations',
    )
    allocation_amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'decision_research_allocation'

    def __str__(self):
        return f"Research: ${self.allocation_amount} for {self.market.name}"
