"""
Group 6 (partial): Engine Result Models — created in CC-05.
"""
from django.db import models


class EventInstance(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='event_instances')
    event_template = models.ForeignKey('core.EventTemplateDefinition', on_delete=models.PROTECT, related_name='instances')
    round_number = models.IntegerField()
    target_market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, null=True, blank=True, related_name='event_instances')
    narrative = models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'event_instance'

    def __str__(self):
        return f"{self.event_template.name} — Round {self.round_number}"


class ActiveModifier(models.Model):
    MODIFIER_TYPE_CHOICES = [
        ('preference', 'Preference'),
        ('market_condition', 'Market Condition'),
        ('demand_shock', 'Demand Shock'),
        ('cost', 'Cost'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='active_modifiers')
    modifier_type = models.CharField(max_length=30, choices=MODIFIER_TYPE_CHOICES)
    source_event = models.ForeignKey(EventInstance, on_delete=models.PROTECT, null=True, blank=True, related_name='modifiers')
    target_segment = models.ForeignKey('core.SegmentDefinition', on_delete=models.PROTECT, null=True, blank=True, related_name='active_modifiers')
    target_feature = models.ForeignKey('core.FeatureDefinition', on_delete=models.PROTECT, null=True, blank=True, related_name='active_modifiers')
    target_market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, null=True, blank=True, related_name='active_modifiers')
    target_field = models.CharField(max_length=100, null=True, blank=True)
    modifier_value = models.DecimalField(max_digits=10, decimal_places=4)
    started_round = models.IntegerField()
    expires_round = models.IntegerField(null=True, blank=True)
    is_cumulative = models.BooleanField(default=False)

    class Meta:
        db_table = 'active_modifier'

    def __str__(self):
        return f"{self.modifier_type} modifier ({self.modifier_value})"


class RoundResultAdoption(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='adoption_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='adoption_results')
    segment = models.ForeignKey('core.SegmentDefinition', on_delete=models.PROTECT, related_name='adoption_results')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, related_name='adoption_results', null=True, blank=True)
    best_product = models.ForeignKey('core.TeamProduct', on_delete=models.PROTECT, null=True, blank=True, related_name='adoption_results')
    fit_score = models.DecimalField(max_digits=5, decimal_places=4)
    adjusted_fit_score = models.DecimalField(max_digits=5, decimal_places=4)
    market_readiness_pct = models.DecimalField(max_digits=5, decimal_places=4)
    adoption_pool = models.DecimalField(max_digits=15, decimal_places=2)
    team_attractiveness = models.DecimalField(max_digits=10, decimal_places=4)
    team_share_pct = models.DecimalField(max_digits=5, decimal_places=4)
    new_adopters = models.DecimalField(max_digits=15, decimal_places=2)
    cumulative_adopters = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'round_result_adoption'
        unique_together = [('game', 'round_number', 'team', 'segment', 'market')]

    def __str__(self):
        market_name = self.market.name if self.market else 'Global'
        return f"Adoption: {self.team.name} × {self.segment.name} × {market_name} R{self.round_number}"


class RoundResultAIAdoption(models.Model):
    """The demand an AI competitor takes from a segment's Bass pool.

    AI competitors have always participated in the attractiveness denominator.
    Keeping their allocation beside the human result rows makes that otherwise
    invisible share auditable without changing the diffusion dynamics.
    """
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT,
                             related_name='ai_adoption_results')
    round_number = models.IntegerField()
    ai_competitor = models.ForeignKey(
        'core.AICompetitorDefinition', on_delete=models.PROTECT,
        related_name='adoption_results',
    )
    segment = models.ForeignKey('core.SegmentDefinition', on_delete=models.PROTECT,
                                related_name='ai_adoption_results')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT,
                               related_name='ai_adoption_results')
    fit_score = models.DecimalField(max_digits=5, decimal_places=4)
    attractiveness = models.DecimalField(max_digits=10, decimal_places=4)
    share_pct = models.DecimalField(max_digits=7, decimal_places=6)
    new_adopters = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'round_result_ai_adoption'
        unique_together = [
            ('game', 'round_number', 'ai_competitor', 'segment', 'market'),
        ]

    def __str__(self):
        return (f"AI adoption: {self.ai_competitor.name} × {self.segment.name} "
                f"× {self.market.name} R{self.round_number}")


class RoundResultDemandReconciliation(models.Model):
    """Per-pool accounting identity for a resolved demand allocation.

    ``human + AI + unserved == adoption_pool`` is stored to cents, so a share
    query is answerable from published game state instead of from a code audit.
    ``unserved`` includes capacity and price-constrained human demand.
    """
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT,
                             related_name='demand_reconciliations')
    round_number = models.IntegerField()
    segment = models.ForeignKey('core.SegmentDefinition', on_delete=models.PROTECT,
                                related_name='demand_reconciliations')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT,
                               related_name='demand_reconciliations')
    adoption_pool = models.DecimalField(max_digits=15, decimal_places=2)
    human_adopters = models.DecimalField(max_digits=15, decimal_places=2)
    ai_adopters = models.DecimalField(max_digits=15, decimal_places=2)
    unserved_adopters = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'round_result_demand_reconciliation'
        unique_together = [('game', 'round_number', 'segment', 'market')]

    def __str__(self):
        return (f"Demand reconciliation: {self.segment.name} × {self.market.name} "
                f"R{self.round_number}")
