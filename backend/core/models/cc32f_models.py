"""
CC-32F: AI Government Agent Models

GovernmentProfile — scenario-configured industrial policy per market.
GovernmentSatisfaction — per-team per-market government satisfaction tracking.
GovernmentAction — historical log of every government action.
"""
from django.db import models


class GovernmentProfile(models.Model):
    """
    Defines the AI government's industrial policy priorities,
    action thresholds, and behavioral parameters for each market.
    """
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='government_profiles',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='government_profile',
    )

    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')

    # Industrial policy priorities — JSON list of weighted objectives
    policy_priorities = models.JSONField(
        help_text=(
            'List of {objective, weight, description} dicts. '
            'Objectives: local_employment, technology_transfer, tax_revenue, '
            'esg_compliance, local_manufacturing, export_contribution.'
        ),
    )

    # Satisfaction thresholds
    incentive_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.70,
        help_text='Above this → eligible for incentives',
    )
    warning_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.40,
        help_text='Below this → government issues warning',
    )
    restriction_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.25,
        help_text='Below this for patience_rounds → market access restrictions',
    )

    # Action parameters
    max_incentive_value_per_round = models.DecimalField(
        max_digits=12, decimal_places=2, default=2000000,
        help_text='Maximum incentive value per round across all firms',
    )
    procurement_budget_per_round = models.DecimalField(
        max_digits=12, decimal_places=2, default=3000000,
        help_text='Procurement contract value available each round',
    )
    procurement_frequency = models.IntegerField(
        default=2,
        help_text='Procurement contract available every N rounds',
    )

    # Bilateral policy volatility
    policy_volatility = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.10,
        help_text='Probability per round of a bilateral policy shift',
    )

    # Patience
    patience_rounds = models.IntegerField(default=2)

    class Meta:
        db_table = 'government_profile'
        unique_together = ('scenario', 'market')

    def __str__(self):
        return f'{self.name} ({self.market})'


class GovernmentSatisfaction(models.Model):
    """
    Tracks each government's satisfaction with each foreign firm
    operating in their market.
    """
    STATUS_CHOICES = [
        ('WELCOMED', 'Government actively supports this firm'),
        ('NEUTRAL', 'Standard operating conditions'),
        ('MONITORED', 'Government watching closely'),
        ('WARNING', 'Official warning issued'),
        ('RESTRICTED', 'Operating restrictions applied'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE)
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.CASCADE)

    satisfaction = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.50,
    )

    # Per-objective scores
    objective_scores = models.JSONField(default=dict)

    # Warning/restriction tracking
    rounds_below_warning = models.IntegerField(default=0)
    rounds_below_restriction = models.IntegerField(default=0)

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='NEUTRAL',
    )

    # Active incentives/restrictions
    active_incentive = models.JSONField(null=True, blank=True)
    active_restriction = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'government_satisfaction'
        unique_together = ('game', 'team', 'market')

    def __str__(self):
        return f'{self.team} in {self.market}: {self.status} ({self.satisfaction})'


class GovernmentAction(models.Model):
    """Records every government action for the audit trail."""
    ACTION_CHOICES = [
        ('INCENTIVE_GRANT', 'Tax holiday, land grant, or permit expedition'),
        ('PROCUREMENT_AWARD', 'Government contract awarded'),
        ('TARIFF_ADJUSTMENT', 'Tariff rate change for specific origin'),
        ('REGULATORY_TIGHTENING', 'New compliance requirements'),
        ('REGULATORY_RELAXATION', 'Reduced requirements to attract investment'),
        ('BILATERAL_SHIFT', 'Trade policy change between two markets'),
        ('WARNING_ISSUED', 'Official warning to a firm'),
        ('ACCESS_RESTRICTION', 'Operating restrictions applied'),
        ('ACCESS_RESTORED', 'Restrictions lifted after improvement'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
    )

    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)

    target_team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    target_origin = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='targeted_by_policy',
    )

    parameters = models.JSONField(default=dict)
    narrative = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'government_action'

    def __str__(self):
        return f'{self.action_type} in {self.market} (R{self.round})'
