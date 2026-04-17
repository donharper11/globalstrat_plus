"""
Group 4: Team State Models (from 04-data-model.md tables 4.1-4.9)

Runtime models tracking what each team currently owns and operates.
"""
from django.db import models


# ---------------------------------------------------------------------------
# Tier 1 — Depends on Group 2 (scenario) + Group 3 (game) only
# ---------------------------------------------------------------------------

class TeamPlatform(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in_development', 'In Development'),
        ('retired', 'Retired'),
    ]
    DEVELOPMENT_METHOD_CHOICES = [
        ('in_house', 'In-House'),
        ('licensed', 'Licensed'),
        ('partnership', 'Partnership'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='platforms',
    )
    platform_generation = models.ForeignKey(
        'core.PlatformGenerationDefinition', on_delete=models.PROTECT,
        related_name='team_platforms',
    )
    name = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Team-assigned platform name (falls back to generation name)',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    development_method = models.CharField(
        max_length=20, choices=DEVELOPMENT_METHOD_CHOICES,
        null=True, blank=True,
    )
    development_started_round = models.IntegerField(null=True, blank=True)
    development_rounds_remaining = models.IntegerField(null=True, blank=True)
    activated_round = models.IntegerField(null=True, blank=True)
    licensed_dependency_pct = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Proportion of platform features developed via licensing (0.0-1.0). Higher = more vulnerable to technology sanctions.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'team_platform'

    def __str__(self):
        return f"{self.team.name} — {self.platform_generation.name} ({self.status})"


class TeamMarketPresence(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('setup', 'Setup'),
        ('exited', 'Exited'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='market_presences',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='team_presences',
    )
    entry_mode = models.ForeignKey(
        'core.EntryModeDefinition', on_delete=models.PROTECT,
        related_name='team_presences',
    )
    established_round = models.IntegerField()
    initial_investment = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    setup_rounds_remaining = models.IntegerField(default=0)
    ip_exposure_cumulative = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Cumulative IP exposure from JV/licensing. 0.0 = none, increases per round.",
    )
    brand_preserved = models.BooleanField(
        default=False,
        help_text="True if acquired via Brand Preservation or Dual Brand strategy",
    )

    class Meta:
        db_table = 'team_market_presence'

    def __str__(self):
        return f"{self.team.name} — {self.market.name} ({self.status})"

    def clean(self):
        """Only one non-exited presence per team-market pair."""
        from django.core.exceptions import ValidationError
        if self.status != 'exited':
            existing = TeamMarketPresence.objects.filter(
                team=self.team, market=self.market,
            ).exclude(status='exited').exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    'Only one active/setup presence allowed per team-market pair.'
                )


class TeamPlant(models.Model):
    STATUS_CHOICES = [
        ('under_construction', 'Under Construction'),
        ('operational', 'Operational'),
        ('decommissioned', 'Decommissioned'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='plants',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='plants',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    capacity_units = models.IntegerField()
    construction_started_round = models.IntegerField()
    completion_round = models.IntegerField()
    cumulative_production = models.IntegerField(default=0)

    class Meta:
        db_table = 'team_plant'

    def __str__(self):
        return f"{self.team.name} plant in {self.market.name} ({self.status})"


class TeamPartnership(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('terminated', 'Terminated'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='partnerships',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='partnerships',
    )
    strategy_option = models.ForeignKey(
        'core.StrategyOptionDefinition', on_delete=models.PROTECT,
        related_name='team_partnerships',
    )
    annual_investment = models.DecimalField(max_digits=15, decimal_places=2)
    established_round = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    terminated_round = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'team_partnership'

    def __str__(self):
        return f"{self.team.name} — {self.strategy_option.name} in {self.market.name}"


# ---------------------------------------------------------------------------
# Tier 2 — Depends on Tier 1
# ---------------------------------------------------------------------------

class TeamPlatformFeatureLevel(models.Model):
    id = models.BigAutoField(primary_key=True)
    team_platform = models.ForeignKey(
        TeamPlatform, on_delete=models.PROTECT, related_name='feature_levels',
    )
    feature = models.ForeignKey(
        'core.FeatureDefinition', on_delete=models.PROTECT,
        related_name='team_platform_levels',
    )
    current_level = models.DecimalField(max_digits=5, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'team_platform_feature_level'
        unique_together = [('team_platform', 'feature')]

    def __str__(self):
        return f"{self.team_platform} — {self.feature.name} = {self.current_level}"


class PendingFeatureGain(models.Model):
    id = models.BigAutoField(primary_key=True)
    team_platform = models.ForeignKey(
        TeamPlatform, on_delete=models.PROTECT, related_name='pending_gains',
    )
    feature = models.ForeignKey(
        'core.FeatureDefinition', on_delete=models.PROTECT,
        related_name='pending_gains',
    )
    gain_amount = models.DecimalField(max_digits=5, decimal_places=2)
    applies_round = models.IntegerField()
    applied = models.BooleanField(default=False)

    class Meta:
        db_table = 'pending_feature_gain'

    def __str__(self):
        return f"{self.team_platform} — {self.feature.name} +{self.gain_amount} @ R{self.applies_round}"


class TeamProduct(models.Model):
    POSITIONING_CHOICES = [
        ('budget', 'Budget'),
        ('mainstream', 'Mainstream'),
        ('premium', 'Premium'),
        ('ultra_premium', 'Ultra-Premium'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retired', 'Retired'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='products',
    )
    team_platform = models.ForeignKey(
        TeamPlatform, on_delete=models.PROTECT, related_name='products',
    )
    name = models.CharField(max_length=200)
    positioning = models.CharField(max_length=20, choices=POSITIONING_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_round = models.IntegerField()
    retired_round = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'team_product'

    def __str__(self):
        return f"{self.team.name} — {self.name} ({self.positioning})"


class TeamStrategyFeatureLevel(models.Model):
    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT, related_name='strategy_levels',
    )
    feature = models.ForeignKey(
        'core.FeatureDefinition', on_delete=models.PROTECT,
        related_name='team_strategy_levels',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        null=True, blank=True, related_name='team_strategy_levels',
    )
    current_level = models.DecimalField(max_digits=5, decimal_places=2)
    round_number = models.IntegerField()

    class Meta:
        db_table = 'team_strategy_feature_level'
        unique_together = [('team', 'feature', 'market', 'round_number')]

    def __str__(self):
        market_label = self.market.name if self.market else 'Global'
        return f"{self.team.name} — {self.feature.name} ({market_label}) = {self.current_level}"


# ---------------------------------------------------------------------------
# Tier 3 — Depends on Tier 2
# ---------------------------------------------------------------------------

class TeamProductMarket(models.Model):
    id = models.BigAutoField(primary_key=True)
    team_product = models.ForeignKey(
        TeamProduct, on_delete=models.PROTECT, related_name='markets',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='product_offerings',
    )
    is_active = models.BooleanField(default=True)
    first_offered_round = models.IntegerField()

    class Meta:
        db_table = 'team_product_market'
        unique_together = [('team_product', 'market')]

    def __str__(self):
        return f"{self.team_product.name} in {self.market.name}"


class TeamAcquisition(models.Model):
    """Tracks a completed or in-progress acquisition."""
    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='acquisitions',
    )
    acquisition_target = models.ForeignKey(
        'core.AcquisitionTarget', on_delete=models.PROTECT, related_name='team_acquisitions',
    )
    acquired_round = models.IntegerField()
    integration_complete = models.BooleanField(default=False)
    integration_rounds_remaining = models.IntegerField()
    total_cost_paid = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'team_acquisition'
        unique_together = [('team', 'acquisition_target')]

    def __str__(self):
        return f"{self.team.name} — {self.acquisition_target.target_name}"


class TeamMarketModifier(models.Model):
    """Permanent or temporary modifiers applied to team's market performance."""
    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='market_modifiers',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, related_name='team_modifiers',
    )
    modifier_type = models.CharField(max_length=50)  # e.g., 'distribution_reach'
    value = models.FloatField()
    source = models.CharField(max_length=200)
    expires_round = models.IntegerField(null=True, blank=True)  # null = permanent

    class Meta:
        db_table = 'team_market_modifier'

    def __str__(self):
        return f"{self.team.name} — {self.modifier_type} in {self.market.name}"
