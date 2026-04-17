"""
CC-32B: Organizational Design — Structure Choice & Operational Modifiers

Models:
- OrganizationalStructureType (A1): Scenario-configured structure options
- TeamOrganizationalStructure (A2): Team's current structure choice and transition state
"""
from django.db import models


class OrganizationalStructureType(models.Model):
    """
    Scenario-configured organizational structure options.
    Each has different cost/benefit profiles that interact
    with the number of active markets.
    """
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='org_structures',
    )

    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')

    # Base overhead cost per round (independent of market count)
    base_overhead_per_round = models.DecimalField(max_digits=10, decimal_places=2)

    # Per-market coordination cost (scales with number of active markets)
    per_market_coordination_cost = models.DecimalField(max_digits=10, decimal_places=2)

    # Modifiers (multipliers applied to various engine calculations)
    # All default to 1.0 = no change
    hq_talent_effectiveness_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Multiplier on HQ talent contribution to global capability",
    )
    local_talent_effectiveness_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Multiplier on local market talent effectiveness",
    )
    innovation_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Multiplier on R&D output (feature level gains per investment)",
    )
    coordination_efficiency = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Multiplier on cross-market campaign effectiveness and supply chain optimization",
    )
    decision_speed_modifier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        help_text="Affects market entry speed and plant construction time. >1.0 = faster.",
    )

    # Market count thresholds — at what point does this structure strain?
    optimal_market_range_min = models.IntegerField(default=1)
    optimal_market_range_max = models.IntegerField(default=5)

    # Penalty applied per market beyond optimal_market_range_max
    overextension_cost_per_market = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    overextension_effectiveness_penalty = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Percentage reduction in all effectiveness modifiers per market beyond optimal range",
    )

    # Transition cost — one-time cost to switch TO this structure from another
    transition_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transition_disruption_rounds = models.IntegerField(
        default=0,
        help_text="Rounds of reduced effectiveness during transition. 0 = immediate.",
    )

    display_order = models.IntegerField(default=0)

    class Meta:
        unique_together = ('scenario', 'code')
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} ({self.scenario})"


class TeamOrganizationalStructure(models.Model):
    """Tracks the team's current and historical organizational structure."""
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE)
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE)

    current_structure = models.ForeignKey(
        OrganizationalStructureType, on_delete=models.SET_NULL, null=True,
        related_name='current_teams',
    )
    adopted_round = models.IntegerField(default=0)

    # Transition tracking
    transitioning_from = models.ForeignKey(
        OrganizationalStructureType, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transitioning_from',
    )
    transition_rounds_remaining = models.IntegerField(default=0)

    class Meta:
        unique_together = ('game', 'team')

    def __str__(self):
        structure_name = self.current_structure.name if self.current_structure else 'None'
        return f"{self.team} — {structure_name}"
