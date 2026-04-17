"""
CC-31A: Origin-Trust Framework, Talent Allocation & Globalization Engine
CC-31J: Governance Commitment Overhaul

New models:
- CulturalDistanceMatrix (A2)
- OriginTrustModifier (A3)
- TalentAllocation (A4)
- ComplianceInvestment (A5)
- TeamMarketCompliance (A6)
- GovernanceCommitmentType (J-A1)
- TeamGovernanceCommitment (J-A2)
"""
from django.db import models


class CulturalDistanceMatrix(models.Model):
    """
    Scenario-configured pairwise cultural/institutional distance
    between markets. Determines talent localization effectiveness
    discount and stakeholder sensitivity.
    """
    DISTANCE_CHOICES = [
        ('HOME', 'Home Market'),
        ('LOW', 'Low Distance'),
        ('MEDIUM', 'Medium Distance'),
        ('HIGH', 'High Distance'),
        ('VERY_HIGH', 'Very High Distance'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='cultural_distances',
    )
    from_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='distance_from',
    )
    to_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='distance_to',
    )
    distance_level = models.CharField(
        max_length=20, choices=DISTANCE_CHOICES,
        help_text="Cultural/institutional distance classification",
    )
    base_effectiveness = models.DecimalField(
        max_digits=4, decimal_places=2,
        help_text="Base talent effectiveness multiplier before localization investment. 1.00 = home market.",
    )
    repatriation_cost_pct = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Percentage of profits lost during cross-border consolidation. 0 for home market.",
    )

    class Meta:
        db_table = 'cultural_distance_matrix'
        unique_together = ('scenario', 'from_market', 'to_market')

    def __str__(self):
        return f"{self.from_market.code} → {self.to_market.code}: {self.distance_level}"


class OriginTrustModifier(models.Model):
    """
    Per-origin, per-host-market trust modifier applied to preference matching.
    Represents liability of origin — the systematic trust discount
    foreign firms face in host markets based on their home country.
    """
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='origin_trust_modifiers',
    )
    origin_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='trust_as_origin',
    )
    host_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
        related_name='trust_as_host',
    )
    customer_trust_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Multiplier on customer fit scores. 1.0 = no penalty. Lower = more distrust.",
    )
    regulator_origin_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.00,
        help_text="Added to regulator satisfaction. Negative = scrutiny, positive = favorable.",
    )
    trust_erosion_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.02,
        help_text="Per-round improvement in trust multiplier from sustained presence and compliance.",
    )

    class Meta:
        db_table = 'origin_trust_modifier'
        unique_together = ('scenario', 'origin_market', 'host_market')

    def __str__(self):
        return f"{self.origin_market.code} in {self.host_market.code}: {self.customer_trust_multiplier}"


class TalentAllocation(models.Model):
    """
    Per-round allocation of each talent pool's headcount
    across HQ and active markets. Must sum to total headcount
    set in the talent decision.
    """
    POOL_CHOICES = [
        ('rd', 'R&D Team'),
        ('commercial', 'Sales & Marketing Team'),
        ('operations', 'Operations & Supply Chain Team'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        'core.DecisionSubmission', on_delete=models.CASCADE,
        related_name='talent_allocations',
    )
    talent_pool = models.CharField(max_length=30, choices=POOL_CHOICES)
    hq_count = models.IntegerField(
        default=0,
        help_text="Headcount stationed at headquarters",
    )
    market_allocation = models.JSONField(
        default=dict,
        help_text='Headcount per market code. Keys = market codes, values = integer headcount.',
    )

    class Meta:
        db_table = 'talent_allocation'
        unique_together = ('submission', 'talent_pool')

    def total_allocated(self):
        return self.hq_count + sum(self.market_allocation.values())

    def is_balanced(self):
        """Must be validated against the corresponding talent decision headcount."""
        return True  # Actual validation in serializer

    def __str__(self):
        return f"{self.submission} — {self.talent_pool} (HQ={self.hq_count})"


class ComplianceInvestment(models.Model):
    """
    Per-market, per-round investment in institutional adaptation:
    data localization, regulatory compliance, standards certification,
    government relations, local process adaptation.
    """
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        'core.DecisionSubmission', on_delete=models.CASCADE,
        related_name='compliance_investments',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.CASCADE,
    )
    investment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Dollar investment this round in compliance and localization for this market",
    )

    class Meta:
        db_table = 'compliance_investment'
        unique_together = ('submission', 'market')

    def __str__(self):
        return f"Compliance: {self.market} — ${self.investment_amount}"


class TeamMarketCompliance(models.Model):
    """
    Tracks cumulative compliance/localization investment effect per team per market.
    Updated by engine each round. Used by event probability system and
    stakeholder preference matching.
    """
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE)
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.CASCADE)

    cumulative_investment = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Total compliance investment in this market across all rounds",
    )
    compliance_level = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="0.0 = no compliance adaptation, 1.0 = fully localized",
    )
    current_trust_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Current trust multiplier after accounting for sustained presence and compliance",
    )
    effective_rd_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
    )
    effective_commercial_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
    )
    effective_operations_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
    )
    rounds_present = models.IntegerField(
        default=0,
        help_text="Consecutive rounds with active market presence",
    )

    class Meta:
        db_table = 'team_market_compliance'
        unique_together = ('game', 'team', 'market')

    def __str__(self):
        return f"{self.team.name} — {self.market.name}: compliance={self.compliance_level}"


# ---------------------------------------------------------------------------
# CC-31J: Governance Commitment Overhaul
# ---------------------------------------------------------------------------

class GovernanceCommitmentType(models.Model):
    """
    Scenario-configured governance commitment with specific
    costs, benefits, risks, and interaction requirements.
    """
    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='governance_commitments',
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')

    ongoing_cost_per_round = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Cash cost per round while commitment is active",
    )

    benefits = models.JSONField(
        default=list,
        help_text="List of stakeholder feature boosts when commitment is active",
    )
    interactions = models.JSONField(
        default=list,
        help_text="Conditional effects based on other team decisions",
    )
    revocation_penalty = models.JSONField(
        default=dict,
        help_text="Penalties applied after revoking: duration_rounds, investor_confidence_drop, etc.",
    )
    prerequisite = models.JSONField(
        null=True, blank=True,
        help_text="Condition that must be met to activate this commitment",
    )
    amplifier = models.JSONField(
        null=True, blank=True,
        help_text="If set, this commitment multiplies the effectiveness of another ESG investment",
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'governance_commitment_type'
        unique_together = ('scenario', 'code')
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} (${self.ongoing_cost_per_round}/round)"


class TeamGovernanceCommitment(models.Model):
    """
    Tracks which commitments a team has active, when they were adopted,
    and revocation history.
    """
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE, related_name='governance_commitments')
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE, related_name='governance_commitments')
    commitment_type = models.ForeignKey(
        GovernanceCommitmentType, on_delete=models.CASCADE,
        related_name='team_commitments',
    )

    is_active = models.BooleanField(default=False)
    activated_round = models.IntegerField(null=True, blank=True)
    revoked_round = models.IntegerField(null=True, blank=True)
    penalty_rounds_remaining = models.IntegerField(
        default=0,
        help_text="Rounds of revocation penalty still active. Decrements each round.",
    )

    class Meta:
        db_table = 'team_governance_commitment'
        unique_together = ('game', 'team', 'commitment_type')
