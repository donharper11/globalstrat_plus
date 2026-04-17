"""
CC-24: Strategic Investment Economic Impact Models.

Track the quantified economic impact of ESG, talent, and partnership
investments per round so students can calculate ROI on every strategic decision.
"""
from django.db import models


class ESGEconomicImpact(models.Model):
    """Per-round, per-market ESG economic benefit record."""
    BENEFIT_TYPES = [
        ('tariff_reduction', 'Tariff Reduction'),
        ('tax_incentive', 'Tax Incentive'),
        ('cogs_reduction', 'COGS Reduction'),
        ('event_protection', 'Event Protection'),
    ]

    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='esg_impacts',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='esg_impacts',
    )
    round_number = models.IntegerField()
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        related_name='esg_impacts', null=True, blank=True,
    )
    benefit_type = models.CharField(max_length=50, choices=BENEFIT_TYPES)
    base_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='What the cost would have been without ESG benefit',
    )
    effective_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='What the cost actually was after ESG benefit',
    )
    savings = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    esg_level = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='The esg_track_record level that triggered this benefit',
    )
    description = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'esg_economic_impact'

    def __str__(self):
        return f"ESG {self.benefit_type}: {self.team.name} R{self.round_number} ${self.savings}"


class TalentEconomicImpact(models.Model):
    """Per-round talent economic impact record per team."""
    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='talent_impacts',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='talent_impacts',
    )
    round_number = models.IntegerField()

    # R&D talent impact
    rd_talent_level = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    rd_cost_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    rd_cost_savings = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Commercial talent impact
    commercial_talent_level = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    campaign_effectiveness_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    campaign_revenue_uplift = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Operations talent impact
    operations_talent_level = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    cogs_modifier = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    cogs_savings = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Totals
    total_talent_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_talent_benefit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_talent_roi = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'talent_economic_impact'
        unique_together = [('game', 'team', 'round_number')]

    def __str__(self):
        return f"Talent: {self.team.name} R{self.round_number} net={self.net_talent_roi}"


class PartnershipEconomicImpact(models.Model):
    """Per-round partnership economic benefit record."""
    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='partnership_impacts',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='partnership_impacts',
    )
    round_number = models.IntegerField()
    partnership = models.ForeignKey(
        'core.TeamPartnership', on_delete=models.CASCADE,
        related_name='economic_impacts',
    )
    benefit_type = models.CharField(max_length=50)
    benefit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    description = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'partnership_economic_impact'

    def __str__(self):
        return f"Partnership {self.benefit_type}: {self.team.name} R{self.round_number} ${self.benefit_amount}"
