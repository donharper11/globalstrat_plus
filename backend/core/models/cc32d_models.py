"""
CC-32D: AI Alliance Partners — Dynamic Partnership Agents

Models:
- AlliancePartnerProfile (A1): Scenario-configured AI personality for each partner
- TeamAllianceState (A2): Per-game tracking of alliance satisfaction and status
"""
from django.db import models


class AlliancePartnerProfile(models.Model):
    """
    Defines the AI personality and preferences of each alliance partner.
    Attached to partnership type definitions in each market.
    """
    PARTNER_TYPE_CHOICES = [
        ('DISTRIBUTION', 'Distribution Partner'),
        ('TECHNOLOGY', 'Technology Partner'),
        ('GOVERNMENT', 'Government / Regulatory Advisor'),
        ('BRAND', 'Brand Ambassador'),
        ('LOCAL_STRATEGIC', 'Local Strategic Partner'),
    ]

    BENEFIT_CURVE_CHOICES = [
        ('LINEAR', 'Benefits scale linearly with satisfaction'),
        ('THRESHOLD', 'Full benefits above 0.7, degraded below'),
        ('BINARY', 'Full benefits above floor, zero below'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='alliance_profiles',
    )

    partnership_code = models.CharField(max_length=50)
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='alliance_profiles',
    )

    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    partner_type = models.CharField(max_length=30, choices=PARTNER_TYPE_CHOICES)

    description = models.TextField(
        help_text="Who this partner is and what they care about",
    )
    description_zh = models.TextField(blank=True, default='')

    preferences = models.JSONField(
        help_text="List of {feature, weight, description} dicts evaluated each round",
    )

    satisfaction_floor = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.30,
        help_text="Below this level, partner initiates dissolution",
    )
    renegotiation_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.50,
        help_text="Below this level, partner demands renegotiation",
    )

    patience_rounds = models.IntegerField(
        default=2,
        help_text="Rounds of sustained dissatisfaction before partner acts",
    )

    benefit_curve = models.CharField(
        max_length=20, choices=BENEFIT_CURVE_CHOICES, default='LINEAR',
    )

    class Meta:
        db_table = 'alliance_partner_profile'
        unique_together = ('scenario', 'partnership_code', 'market')

    def __str__(self):
        return f"{self.name} ({self.partner_type}) in {self.market.code}"


class TeamAllianceState(models.Model):
    """
    Tracks the dynamic state of each active partnership/alliance.
    Updated by the engine each round.
    """
    STATUS_CHOICES = [
        ('HEALTHY', 'Operating normally'),
        ('STRAINED', 'Below renegotiation threshold — benefits degrading'),
        ('RENEGOTIATING', 'Partner demanding new terms'),
        ('DISSOLVING', 'Partnership ending — wind-down period'),
        ('DISSOLVED', 'Partnership terminated'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE)
    partner_profile = models.ForeignKey(
        AlliancePartnerProfile, on_delete=models.CASCADE,
        related_name='alliance_states',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='alliance_states',
    )

    satisfaction = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.70,
    )
    feature_satisfaction = models.JSONField(default=dict)

    rounds_below_renegotiation = models.IntegerField(default=0)
    rounds_below_dissolution = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='HEALTHY',
    )

    benefit_delivery_pct = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="0.0 to 1.0 — percentage of partnership benefits delivered",
    )

    renegotiation_demands = models.JSONField(null=True, blank=True)

    established_round = models.IntegerField(default=0)
    dissolved_round = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'team_alliance_state'
        unique_together = ('game', 'team', 'partner_profile')

    def __str__(self):
        return f"{self.team.name} ↔ {self.partner_profile.name}: {self.status} ({self.satisfaction})"
