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
