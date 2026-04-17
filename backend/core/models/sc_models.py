"""
Supply Chain scenario-content models (CC-04).

Loaded from scenario YAML via load_scenario. Teams never write directly.
"""
from django.db import models


class Supplier(models.Model):
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='suppliers',
    )
    supplier_id = models.CharField(max_length=100)
    name = models.CharField(max_length=200)

    country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    tier = models.IntegerField()
    capacity_units_per_round = models.IntegerField()
    base_unit_price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    quality_rating = models.DecimalField(max_digits=4, decimal_places=3)  # 0.000–1.000
    reliability_rating = models.DecimalField(max_digits=4, decimal_places=3)
    lead_time_days_baseline = models.IntegerField()
    min_order_commitment = models.IntegerField(default=0)

    specialization = models.JSONField(default=list)
    volume_discount_tiers = models.JSONField(default=list)
    tier_2_3_profile = models.JSONField(default=dict)
    origin_trust_to_buyers = models.JSONField(default=dict)
    certifications = models.JSONField(default=list)
    accepts_trade_finance = models.JSONField(default=list)
    political_risk_profile = models.JSONField(default=dict)
    multi_source_substitutability = models.JSONField(default=list)

    class Meta:
        db_table = 'sc_supplier'
        unique_together = [('scenario', 'supplier_id')]
        indexes = [
            models.Index(fields=['scenario', 'country']),
            models.Index(fields=['scenario', 'tier']),
        ]

    def __str__(self):
        return f"{self.supplier_id} ({self.country})"


class ShippingLane(models.Model):
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='shipping_lanes',
    )
    lane_id = models.CharField(max_length=100)

    origin_country = models.CharField(max_length=2)
    origin_port = models.CharField(max_length=100)
    destination_country = models.CharField(max_length=2)
    destination_port = models.CharField(max_length=100)
    zone = models.CharField(max_length=50)

    modes = models.JSONField(default=dict)
    chokepoints = models.JSONField(default=dict)
    disruption_exposure = models.JSONField(default=dict)
    customs_processing_days_baseline = models.IntegerField()
    reverse_logistics_available = models.BooleanField(default=False)
    reverse_logistics_cost_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default='1.00',
    )

    class Meta:
        db_table = 'sc_shipping_lane'
        unique_together = [('scenario', 'lane_id')]
        indexes = [
            models.Index(fields=['scenario', 'origin_country', 'destination_country']),
        ]

    def __str__(self):
        return f"{self.lane_id}: {self.origin_port} → {self.destination_port}"


class TradeFinanceInstrument(models.Model):
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='trade_finance_instruments',
    )
    instrument_id = models.CharField(max_length=100)
    display_name = models.CharField(max_length=200)

    cost_bps_of_transaction = models.IntegerField(null=True, blank=True)
    cost_pct_of_insured_value = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    processing_lead_days = models.IntegerField(default=0)
    seller_protection = models.CharField(max_length=20)  # high/medium/low
    buyer_cash_requirement = models.CharField(max_length=20)

    available_in_markets = models.JSONField(default=list)
    available_to_home_countries = models.JSONField(default=list)

    rejection_probability_baseline = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
    )
    buyer_default_probability_baseline = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
    )
    coverage_ceiling_pct = models.IntegerField(null=True, blank=True)
    bri_market_premium_subsidy_pct = models.IntegerField(null=True, blank=True)
    tenor_options_days = models.JSONField(default=list)
    currency_pairs_available = models.JSONField(default=list)

    class Meta:
        db_table = 'sc_trade_finance_instrument'
        unique_together = [('scenario', 'instrument_id')]

    def __str__(self):
        return f"{self.instrument_id}: {self.display_name}"


class ComplianceRegime(models.Model):
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='compliance_regimes',
    )
    regime_id = models.CharField(max_length=100)
    name = models.CharField(max_length=200)

    enforcing_market = models.CharField(max_length=100, null=True, blank=True)
    enforcing_country = models.CharField(max_length=2, null=True, blank=True)

    applies_to_products = models.JSONField(default=list)
    trigger_condition = models.CharField(max_length=200, null=True, blank=True)
    trigger_threshold_pct = models.IntegerField(null=True, blank=True)
    baseline_enforcement_probability_per_round = models.DecimalField(
        max_digits=5, decimal_places=4, default='0.0',
    )

    detention_consequence = models.JSONField(default=dict)
    mitigation_investments = models.JSONField(default=dict)

    phase_in_schedule = models.JSONField(default=list)
    tariff_per_ton_co2_usd = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
    )
    sectors_covered = models.JSONField(default=list)
    restricted_technologies = models.JSONField(default=list)
    target_countries_baseline = models.JSONField(default=list)

    class Meta:
        db_table = 'sc_compliance_regime'
        unique_together = [('scenario', 'regime_id')]

    def __str__(self):
        return f"{self.regime_id}: {self.name}"


class ResilienceParameters(models.Model):
    scenario = models.OneToOneField(
        'core.Scenario', on_delete=models.CASCADE, related_name='resilience_parameters',
    )

    single_source_threshold_pct = models.IntegerField(default=70)
    geographic_concentration_threshold_pct = models.IntegerField(default=60)
    critical_component_buffer_days_recommended = models.IntegerField(default=45)
    bullwhip_coefficient_baseline = models.DecimalField(
        max_digits=4, decimal_places=2, default='1.40',
    )

    resilience_score_weights = models.JSONField(default=dict)
    disruption_cascade_coefficient = models.DecimalField(
        max_digits=4, decimal_places=2, default='0.30',
    )
    recovery_rate_with_alternatives_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default='0.50',
    )

    class Meta:
        db_table = 'sc_resilience_parameters'

    def __str__(self):
        return f"Resilience params for {self.scenario}"


class FreightMarket(models.Model):
    scenario = models.OneToOneField(
        'core.Scenario', on_delete=models.CASCADE, related_name='freight_market',
    )

    rate_dynamics_model = models.CharField(max_length=100, default='demand_capacity_elastic')
    baseline_capacity_abundance = models.CharField(max_length=30, default='normal')
    fuel_index_baseline_usd_per_barrel = models.DecimalField(
        max_digits=7, decimal_places=2, default='80.00',
    )
    fuel_index_volatility_sigma = models.DecimalField(
        max_digits=5, decimal_places=3, default='0.120',
    )
    container_rate_volatility_sigma = models.DecimalField(
        max_digits=5, decimal_places=3, default='0.150',
    )
    demand_elasticity_coefficient = models.DecimalField(
        max_digits=4, decimal_places=2, default='1.30',
    )
    capacity_response_lag_rounds = models.IntegerField(default=2)

    class Meta:
        db_table = 'sc_freight_market'

    def __str__(self):
        return f"Freight market for {self.scenario}"
