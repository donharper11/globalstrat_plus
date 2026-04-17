"""CC-32C: Tax Structure & Transfer Pricing Models."""
from decimal import Decimal
from django.db import models


class TaxStructureType(models.Model):
    """Available tax structure options configured per scenario."""
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='tax_structures',
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    setup_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_maintenance_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Per-round cost for legal, accounting, and compliance",
    )
    effective_tax_reduction_pct = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Percentage point reduction in effective tax rate across foreign markets",
    )
    repatriation_cost_reduction_pct = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Fraction reduction in repatriation costs (0.0 to 1.0)",
    )
    audit_probability_per_round = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Probability of a tax audit event per round",
    )
    audit_penalty_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('1.0'),
        help_text="Multiplier on back-taxes + penalty if audited",
    )
    value_investor_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Granite Investments satisfaction modifier",
    )
    esg_investor_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="GreenHorizon satisfaction modifier",
    )
    regulator_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Applied to regulator satisfaction in all markets",
    )
    anti_corruption_conflict = models.BooleanField(
        default=False,
        help_text="If True, creates visible hypocrisy when combined with Anti-Corruption commitment",
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'tax_structure_type'
        unique_together = [('scenario', 'code')]
        ordering = ['display_order']

    def __str__(self):
        return self.name


class TeamTaxStructure(models.Model):
    """Tracks which tax structure a team has adopted."""
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE)
    current_structure = models.ForeignKey(
        TaxStructureType, on_delete=models.SET_NULL, null=True, blank=True,
    )
    adopted_round = models.IntegerField(default=0)
    setup_cost_paid = models.BooleanField(default=False)
    times_audited = models.IntegerField(default=0)
    cumulative_audit_penalties = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
    )
    cumulative_tax_savings = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
    )
    last_audit_round = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'team_tax_structure'
        unique_together = [('game', 'team')]

    def __str__(self):
        structure_name = self.current_structure.name if self.current_structure else 'None'
        return f"{self.team.name}: {structure_name}"
