"""
Supply Chain team-decision models (CC-04).

Per-round decisions submitted by teams. Each has unique_together on
the natural key per P4.
"""
from django.core.exceptions import ValidationError
from django.db import models


class SourcingAllocation(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='sourcing_allocations',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    critical_input_category = models.CharField(max_length=100)
    supplier = models.ForeignKey(
        'core.Supplier', on_delete=models.PROTECT,
    )

    allocation_pct = models.IntegerField()  # 0–100
    volume_commitment_units = models.IntegerField(default=0)
    payment_terms = models.CharField(max_length=100)  # instrument_id

    class Meta:
        db_table = 'sc_sourcing_allocation'
        unique_together = [('team', 'round', 'critical_input_category', 'supplier')]
        indexes = [
            models.Index(fields=['team', 'round']),
        ]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} {self.critical_input_category} → {self.supplier}"


class SourcingDecision(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='sourcing_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)

    tier_2_3_visibility_investment = models.CharField(
        max_length=20, default='none',
    )  # none/basic/comprehensive
    multi_sourcing_strategy = models.CharField(
        max_length=30, default='single_source',
    )

    class Meta:
        db_table = 'sc_sourcing_decision'
        unique_together = [('team', 'round')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} sourcing"


class LogisticsDecision(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='logistics_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    lane = models.ForeignKey(
        'core.ShippingLane', on_delete=models.PROTECT,
    )

    mode_sea_pct = models.IntegerField(default=0)
    mode_air_pct = models.IntegerField(default=0)
    mode_rail_pct = models.IntegerField(default=0)
    mode_road_pct = models.IntegerField(default=0)
    volume_commitment_teu = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'sc_logistics_decision'
        unique_together = [('team', 'round', 'lane')]

    def clean(self):
        total = sum([self.mode_sea_pct, self.mode_air_pct, self.mode_rail_pct, self.mode_road_pct])
        if total != 100:
            raise ValidationError(f"Modal mix must sum to 100; got {total}")

    def __str__(self):
        return f"{self.team} R{self.round.round_number} lane={self.lane.lane_id}"


class IncotermsDecision(models.Model):
    INCOTERMS_CHOICES = [
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'), ('CFR', 'CFR'), ('CIF', 'CIF'),
        ('CPT', 'CPT'), ('CIP', 'CIP'), ('DAP', 'DAP'), ('DPU', 'DPU'), ('DDP', 'DDP'),
    ]

    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='incoterms_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    destination_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
    )

    incoterms = models.CharField(max_length=3, choices=INCOTERMS_CHOICES, default='CIF')
    insurance_coverage_pct = models.IntegerField(default=110)

    class Meta:
        db_table = 'sc_incoterms_decision'
        unique_together = [('team', 'round', 'destination_market')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} {self.destination_market} {self.incoterms}"


class CustomsClassificationDecision(models.Model):
    CLASSIFICATION_CHOICES = [
        ('processing_trade', 'Processing Trade'),
        ('general_trade', 'General Trade'),
        ('bonded_logistics', 'Bonded Logistics'),
    ]

    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='customs_classification_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    destination_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
    )

    classification = models.CharField(
        max_length=30, choices=CLASSIFICATION_CHOICES, default='general_trade',
    )
    reverse_logistics_capacity_pct = models.IntegerField(default=0)
    reverse_logistics_hub_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        null=True, blank=True, related_name='reverse_logistics_hub_for',
    )

    class Meta:
        db_table = 'sc_customs_classification_decision'
        unique_together = [('team', 'round', 'destination_market')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} customs {self.classification}"


class TradeFinanceDecision(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='trade_finance_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    segment = models.ForeignKey(
        'core.SegmentDefinition', on_delete=models.PROTECT,
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
    )

    buyer_payment_instrument = models.CharField(max_length=100)  # instrument_id
    lc_doc_prep_investment = models.CharField(
        max_length=20, default='standard',
    )  # minimal/standard/diligent

    class Meta:
        db_table = 'sc_trade_finance_decision'
        unique_together = [('team', 'round', 'segment', 'market')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} trade_finance {self.market}"


class SinosureEnrollment(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='sinosure_enrollments',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
    )

    coverage_pct = models.IntegerField()

    class Meta:
        db_table = 'sc_sinosure_enrollment'
        unique_together = [('team', 'round', 'market')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} sinosure {self.market} {self.coverage_pct}%"


class FXHedgeDecision(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='fx_hedge_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    currency_pair = models.CharField(max_length=20)  # e.g., "USD_CNY"

    hedge_ratio = models.IntegerField(default=0)
    tenor_days = models.IntegerField(default=90)

    class Meta:
        db_table = 'sc_fx_hedge_decision'
        unique_together = [('team', 'round', 'currency_pair')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} hedge {self.currency_pair}"


class InventoryDecision(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='inventory_decisions',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)
    product = models.ForeignKey(
        'core.TeamProduct', on_delete=models.PROTECT,
    )
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
    )

    buffer_days = models.IntegerField(default=30)
    safety_stock_trigger_pct = models.IntegerField(default=20)

    class Meta:
        db_table = 'sc_inventory_decision'
        unique_together = [('team', 'round', 'product', 'market')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} inventory {self.product} {self.market}"


class ContingencyPlan(models.Model):
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='contingency_plans',
    )
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE)

    disruption_response_playbook = models.TextField(max_length=500, blank=True)
    alt_supplier_activation_rules = models.JSONField(default=list)
    mode_switch_triggers = models.JSONField(default=list)

    class Meta:
        db_table = 'sc_contingency_plan'
        unique_together = [('team', 'round')]

    def __str__(self):
        return f"{self.team} R{self.round.round_number} contingency"
