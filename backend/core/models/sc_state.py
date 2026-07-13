"""
Supply Chain engine-managed state models (CC-04).

Written by the engine during round advance, not by teams.
Round-indexed for determinism per CC-4 P3.
"""
from django.db import models


class SupplierState(models.Model):
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    supplier = models.ForeignKey(
        'core.Supplier', on_delete=models.CASCADE, related_name='states',
    )

    capacity_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    quality_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    reliability_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    additional_lead_time_days = models.IntegerField(default=0)
    disruption_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    recovery_rounds_remaining = models.IntegerField(default=0)

    active_disruption_event = models.ForeignKey(
        'core.EventInstance', on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = 'sc_supplier_state'
        unique_together = [('round', 'supplier')]

    def __str__(self):
        return f"SupplierState R{self.round.round_number} {self.supplier}"


class LaneState(models.Model):
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    lane = models.ForeignKey(
        'core.ShippingLane', on_delete=models.CASCADE, related_name='states',
    )

    active_disruption = models.JSONField(null=True, blank=True)
    current_rate_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')

    class Meta:
        db_table = 'sc_lane_state'
        unique_together = [('round', 'lane')]

    def __str__(self):
        return f"LaneState R{self.round.round_number} {self.lane}"


class SCEventInstance(models.Model):
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    event_template = models.ForeignKey(
        'core.EventTemplateDefinition', on_delete=models.PROTECT,
    )

    affects_all_teams = models.BooleanField(default=True)
    affected_teams = models.ManyToManyField('core.Team', blank=True)
    fired_by_instructor = models.BooleanField(default=False)

    resolution_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'sc_event_instance'
        indexes = [
            models.Index(fields=['round']),
        ]

    def __str__(self):
        return f"SCEvent R{self.round.round_number} {self.event_template}"


class HedgePosition(models.Model):
    STATUS_CHOICES = [('open', 'Open'), ('closed', 'Closed'), ('matured', 'Matured')]
    DIRECTION_CHOICES = [('long', 'Long'), ('short', 'Short')]

    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='hedge_positions',
    )
    currency_pair = models.CharField(max_length=20)

    notional = models.DecimalField(max_digits=14, decimal_places=2)
    locked_rate = models.DecimalField(max_digits=10, decimal_places=5)
    opened_round = models.ForeignKey(
        'core.Round', on_delete=models.PROTECT, related_name='hedges_opened',
    )
    maturity_round = models.ForeignKey(
        'core.Round', on_delete=models.PROTECT, related_name='hedges_maturing',
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    mtm_current = models.DecimalField(max_digits=14, decimal_places=2, default='0.00')
    realized_pnl = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'sc_hedge_position'

    def __str__(self):
        return f"{self.team} {self.currency_pair} {self.direction} {self.status}"


class ResilienceScoreHistory(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='resilience_history',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)

    score = models.DecimalField(max_digits=5, decimal_places=3)  # 0.000–1.000
    components = models.JSONField(default=dict)
    weights_used = models.JSONField(default=dict)
    # CC-19B: per-team, per-round disruption impact — present every round a team
    # is scored (not only the round an SC event fires), so multi-round/recovery
    # disruptions surface on the dashboard. Keys: lost_revenue, disruption_cost,
    # freight_cost, mitigation_cost, capacity_factor.
    disruption_impact = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'sc_resilience_score_history'
        unique_together = [('team', 'round')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} resilience={self.score}"


class ComplianceEnforcementEvent(models.Model):
    """CC-18: a compliance regime enforcement action against a team in a market.

    Written by `compliance_engine.enforce_compliance` when a regime fires: it
    records the remediation/penalty cost booked to the P&L, the market-access
    freeze window (the market is blocked through `freeze_until_round`), the
    reputation impact, and what triggered it — closing the
    detention → freeze → cost → reputation loop.
    """
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='compliance_events',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    regime = models.ForeignKey(
        'core.ComplianceRegime', on_delete=models.PROTECT, related_name='enforcement_events',
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT, null=True, blank=True,
    )

    cost_usd = models.DecimalField(max_digits=14, decimal_places=2, default='0.00')
    freeze_until_round = models.IntegerField(default=0)  # inclusive last frozen round number
    reputation_impact = models.DecimalField(max_digits=6, decimal_places=3, default='0.000')
    triggered_by = models.CharField(max_length=200, blank=True)
    mitigated = models.BooleanField(default=False)

    class Meta:
        db_table = 'sc_compliance_enforcement_event'
        indexes = [models.Index(fields=['team', 'round'])]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} {self.regime.regime_id} ${self.cost_usd}"
