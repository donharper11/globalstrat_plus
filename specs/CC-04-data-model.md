# CC-4: globalstrat+ Data Model

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — Django models, migrations, serializers, DRF API endpoints
**Depends on:** `specs/CC-01-scenario-schema.md`, `specs/CC-02-decision-taxonomy.md`, `specs/CC-03-engine-logic.md`
**Observes:** `specs/STANDING-DISCIPLINE.md` (including §1.8 model-to-table verification and §1.9 client version alignment)
**Status:** Ready for Claude Code execution

---

## 1. Purpose

This spec translates the contracts established in CC-1 (scenario schema), CC-2 (decision taxonomy), and CC-3 (engine logic) into concrete Django artifacts:

- Model definitions for all NEW scenario-content entities (Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime, etc.)
- Model definitions for all NEW team-decision entities (SourcingAllocation, LogisticsDecision, TradeFinanceDecision, etc.)
- Model definitions for all NEW engine-managed state entities (SupplierState, LaneState, HedgePosition, SCEventInstance, ResilienceScoreHistory)
- Additive field extensions to two confirmed non-ghost models: DecisionPlant and DecisionESG
- Migrations, reversible, grouped by logical concern
- DRF serializers for every new model
- DRF endpoints for decision submission and round-state retrieval
- Extension of the existing `manage.py load_scenario` command to consume the new YAML sections

CC-4 is the first foundation spec that commits code. CC-1 and Amendment A1 committed infrastructure (DB, Qdrant, bootstrap schema, specs). CC-2 and CC-3 committed inventory reports only. CC-4 writes models, migrations, and endpoints.

**Scope boundary:** CC-4 does NOT implement the engine pipeline steps from CC-3. Model definitions and API surface only. Engine logic implementation is a build-pipeline bundle (post-CC-6). CC-4 also does NOT populate real scenario content; only a skeleton suitable for load-testing the new loader paths. Real seed data is CC-8.

---

## 2. Preconditions — Model Reference Inventory

Per STANDING-DISCIPLINE §1.8, Claude Code verifies every existing model referenced by CC-4 (as a FK target or as an EXTEND target) is non-ghost before proceeding.

### 2.1 Reference Inventory Report

Claude Code produces a report at `specs/reports/CC-04-reference-inventory.md` covering:

**Section A — FK target confirmation.** For every model referenced by CC-4's FK fields (enumerated in §4 of this spec), confirm:

- Model is registered in Django
- Physical table exists in `globalstrat_plus` database
- db_table name matches what this spec assumes
- Primary key type matches what CC-4's FK declarations will use

Specifically: `Team`, `Round`, `Scenario`, `Market`, `Product`, `DecisionSubmission` (or whatever the per-round submission wrapper is), `Segment`, `Company`, and the extend targets `DecisionPlant` and `DecisionESG`. Any additional models surfaced by the CC-3 engine inventory as orchestration dependencies.

**Section B — App layout and model file conventions.** Confirm:

- Which Django app owns decision models (`core/`, or split apps)
- Whether models are in a single `models.py` or split into `models/` package files
- Migration directory location and current migration numbering
- Naming conventions for db_table values

This determines where CC-4's new models physically live in the codebase.

**Section C — DRF routing conventions.** Confirm:

- Existing API URL prefix (`/api/v1/`, `/api/`, or other)
- Authentication middleware (JWT confirmed in CC-13-era work per project context; verify current state)
- Serializer base class conventions (ModelSerializer vs. custom base)
- Existing decision submission endpoint patterns so new endpoints match

### 2.2 Halt Conditions

Per STANDING-DISCIPLINE §3, Claude Code halts with a MISMATCH report if:

1. Any FK target model is a ghost, has a different name, or uses a different primary key type than expected.
2. The app layout differs materially from what this spec's §4 model files assume (e.g., models are split across apps that don't align with CC-4's proposed structure).
3. Existing migration chain is not clean (`showmigrations` reports unapplied migrations, branches, or drift).
4. Authentication or serializer conventions differ such that CC-4's endpoint design would be inconsistent with existing endpoints.

Resolution belongs to the spec author, not to Claude Code.

### 2.3 Commit the Inventory

```bash
git checkout -b cc-04-data-model
git add specs/reports/CC-04-reference-inventory.md
git commit -m "CC-4: reference inventory report for data model dependencies"
```

CC-4's code work begins only after the inventory is clean.

---

## 3. Design Principles

Principles that govern every model decision in §4:

**P1 — Managed models only.** Every new model has `Meta.managed = True`. No new `managed: False` declarations. This is a direct response to the ghost model problem documented in CC-1 Amendment A1 D2.

**P2 — JSON fields for variable-structure scenario content.** Scenario content (from YAML) with nested or list-valued structure stored as `JSONField`. Top-level scalar fields queried in engine calculations are denormalized to columns. This balances ORM ergonomics against query performance for the actual hot paths.

**P3 — Round-indexed state for determinism.** Engine-managed state entities (SupplierState, LaneState) carry a `round` FK. Historical state is preserved, enabling replay per CC-3 §9. Storage cost is acceptable given scenario volumes (tens of suppliers, tens of lanes, ~10 rounds).

**P4 — Unique-together discipline.** Every decision and state model declares `Meta.unique_together` for the natural key (e.g., `(team, round, lane)` for LogisticsDecision). Prevents duplicate submissions and surfaces race conditions at the DB layer.

**P5 — Soft progressive disclosure enforcement.** The API returns only fields unlocked for the current round (per CC-2 §8), but the DB stores all fields. Locked fields default per CC-2 §10. This keeps the backend simple (no per-round schemas) and pushes display logic to serializers.

**P6 — Explicit on_delete behavior.** Every FK declares `on_delete` explicitly. Scenario content uses `PROTECT` (don't let teams exist referencing deleted suppliers). Team decisions use `CASCADE` (if a team is deleted, their decisions go). State entities use `CASCADE` on round (round deletion is rare and total).

**P7 — Decimal for financial values.** Currency amounts use `DecimalField(max_digits=14, decimal_places=2)`. Percentages use `IntegerField` (0–100 range) unless fractional precision matters, then `DecimalField(max_digits=5, decimal_places=2)`. No `FloatField` for anything that affects team score.

**P8 — Naming.** New tables follow the existing GlobalStrat db_table convention (surfaced in Section A of the reference inventory report). New models follow existing naming patterns in the same app.

---

## 4. Model Definitions

### 4.1 Scenario-content models (loaded from YAML, refreshed per scenario load)

These represent declarative scenario content. One row per scenario per entity. They are written only by the `load_scenario` management command; teams never directly write to them.

#### 4.1.1 `Supplier`

Represents a supplier declared in the scenario YAML (CC-1 §6.1).

```python
class Supplier(models.Model):
    # Identity
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='suppliers')
    supplier_id = models.CharField(max_length=100)  # from YAML
    name = models.CharField(max_length=200)

    # Core scalars (denormalized for query)
    country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    tier = models.IntegerField()
    capacity_units_per_round = models.IntegerField()
    base_unit_price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    quality_rating = models.DecimalField(max_digits=4, decimal_places=3)  # 0.000–1.000
    reliability_rating = models.DecimalField(max_digits=4, decimal_places=3)
    lead_time_days_baseline = models.IntegerField()
    min_order_commitment = models.IntegerField(default=0)

    # Variable structure content
    specialization = models.JSONField()  # list of strings
    volume_discount_tiers = models.JSONField(default=list)
    tier_2_3_profile = models.JSONField(default=dict)
    origin_trust_to_buyers = models.JSONField(default=dict)
    certifications = models.JSONField(default=list)
    accepts_trade_finance = models.JSONField(default=list)
    political_risk_profile = models.JSONField(default=dict)
    multi_source_substitutability = models.JSONField(default=list)

    class Meta:
        unique_together = [('scenario', 'supplier_id')]
        indexes = [
            models.Index(fields=['scenario', 'country']),
            models.Index(fields=['scenario', 'tier']),
        ]

    def __str__(self):
        return f"{self.supplier_id} ({self.country})"
```

#### 4.1.2 `ShippingLane`

```python
class ShippingLane(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='shipping_lanes')
    lane_id = models.CharField(max_length=100)

    origin_country = models.CharField(max_length=2)
    origin_port = models.CharField(max_length=100)
    destination_country = models.CharField(max_length=2)
    destination_port = models.CharField(max_length=100)
    zone = models.CharField(max_length=50)

    modes = models.JSONField()  # per-mode config from YAML
    chokepoints = models.JSONField(default=dict)
    disruption_exposure = models.JSONField(default=dict)
    customs_processing_days_baseline = models.IntegerField()
    reverse_logistics_available = models.BooleanField(default=False)
    reverse_logistics_cost_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default='1.00')

    class Meta:
        unique_together = [('scenario', 'lane_id')]
        indexes = [
            models.Index(fields=['scenario', 'origin_country', 'destination_country']),
        ]
```

#### 4.1.3 `TradeFinanceInstrument`

```python
class TradeFinanceInstrument(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='trade_finance_instruments')
    instrument_id = models.CharField(max_length=100)  # letter_of_credit, sinosure_coverage, etc.
    display_name = models.CharField(max_length=200)

    cost_bps_of_transaction = models.IntegerField(null=True, blank=True)
    cost_pct_of_insured_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    processing_lead_days = models.IntegerField(default=0)
    seller_protection = models.CharField(max_length=20)  # high/medium/low
    buyer_cash_requirement = models.CharField(max_length=20)

    available_in_markets = models.JSONField(default=list)  # list of market ids, or ["all"]
    available_to_home_countries = models.JSONField(default=list)  # restrict by home country

    # Instrument-specific extras
    rejection_probability_baseline = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    buyer_default_probability_baseline = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    coverage_ceiling_pct = models.IntegerField(null=True, blank=True)
    bri_market_premium_subsidy_pct = models.IntegerField(null=True, blank=True)
    tenor_options_days = models.JSONField(default=list)
    currency_pairs_available = models.JSONField(default=list)

    class Meta:
        unique_together = [('scenario', 'instrument_id')]
```

#### 4.1.4 `ComplianceRegime`

```python
class ComplianceRegime(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='compliance_regimes')
    regime_id = models.CharField(max_length=100)
    name = models.CharField(max_length=200)

    enforcing_market = models.CharField(max_length=100, null=True, blank=True)
    enforcing_country = models.CharField(max_length=2, null=True, blank=True)

    applies_to_products = models.JSONField(default=list)
    trigger_condition = models.CharField(max_length=200, null=True, blank=True)
    trigger_threshold_pct = models.IntegerField(null=True, blank=True)
    baseline_enforcement_probability_per_round = models.DecimalField(max_digits=5, decimal_places=4, default='0.0')

    detention_consequence = models.JSONField(default=dict)
    mitigation_investments = models.JSONField(default=dict)

    # Regime-specific extras
    phase_in_schedule = models.JSONField(default=list)
    tariff_per_ton_co2_usd = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sectors_covered = models.JSONField(default=list)
    restricted_technologies = models.JSONField(default=list)
    target_countries_baseline = models.JSONField(default=list)

    class Meta:
        unique_together = [('scenario', 'regime_id')]
```

#### 4.1.5 `ResilienceParameters` (scenario singleton)

```python
class ResilienceParameters(models.Model):
    scenario = models.OneToOneField(Scenario, on_delete=models.CASCADE, related_name='resilience_parameters')

    single_source_threshold_pct = models.IntegerField(default=70)
    geographic_concentration_threshold_pct = models.IntegerField(default=60)
    critical_component_buffer_days_recommended = models.IntegerField(default=45)
    bullwhip_coefficient_baseline = models.DecimalField(max_digits=4, decimal_places=2, default='1.40')

    resilience_score_weights = models.JSONField()  # must sum to 1.0, enforced in loader
    disruption_cascade_coefficient = models.DecimalField(max_digits=4, decimal_places=2, default='0.30')
    recovery_rate_with_alternatives_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default='0.50')
```

#### 4.1.6 `FreightMarket` (scenario singleton)

```python
class FreightMarket(models.Model):
    scenario = models.OneToOneField(Scenario, on_delete=models.CASCADE, related_name='freight_market')

    rate_dynamics_model = models.CharField(max_length=100, default='demand_capacity_elastic')
    baseline_capacity_abundance = models.CharField(max_length=30, default='normal')
    fuel_index_baseline_usd_per_barrel = models.DecimalField(max_digits=7, decimal_places=2, default='80.00')
    fuel_index_volatility_sigma = models.DecimalField(max_digits=5, decimal_places=3, default='0.120')
    container_rate_volatility_sigma = models.DecimalField(max_digits=5, decimal_places=3, default='0.150')
    demand_elasticity_coefficient = models.DecimalField(max_digits=4, decimal_places=2, default='1.30')
    capacity_response_lag_rounds = models.IntegerField(default=2)
```

#### 4.1.7 `SCEventTemplate`

Per the CC-3 engine inventory report (§2 Section C), SC events may either extend the existing Event model via a `category` field or warrant a new model. The final choice is determined by what the inventory reveals. This spec assumes **extension of the existing Event model via a `category` field** — if the inventory contradicts this, CC-4 halts and the spec is revised.

If extension is the path, no new model is created here; instead, a migration adds a `category` CharField to the existing Event model, and new SC-specific fields (`affected_suppliers`, `affected_lanes`, `mode_rate_multiplier`, etc.) are added as JSONField columns or via a one-to-one SCEventExtension model, depending on which pattern the inventory report recommends.

If the inventory instead reveals that event templates are stored only in scenario YAML and materialized per-round as different model instances, this spec's SCEventTemplate work is restructured accordingly. Claude Code produces a mini-decision note in the reference inventory report before proceeding.

### 4.2 Team decision models (team-submitted, per-round)

#### 4.2.1 `SourcingAllocation`

Represents one supplier's allocation within a critical input category for a team in a round. Multiple rows per (team, round, category).

```python
class SourcingAllocation(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='sourcing_allocations')
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    critical_input_category = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)

    allocation_pct = models.IntegerField()  # 0–100
    volume_commitment_units = models.IntegerField(default=0)
    payment_terms = models.CharField(max_length=100)  # instrument_id

    class Meta:
        unique_together = [('team', 'round', 'critical_input_category', 'supplier')]
        indexes = [
            models.Index(fields=['team', 'round']),
        ]
```

#### 4.2.2 `SourcingDecision` (page-level)

Captures page-level sourcing decisions not tied to a specific supplier row.

```python
class SourcingDecision(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)

    tier_2_3_visibility_investment = models.CharField(max_length=20, default='none')  # none/basic/comprehensive
    multi_sourcing_strategy = models.CharField(max_length=30, default='single_source')

    class Meta:
        unique_together = [('team', 'round')]
```

#### 4.2.3 `LogisticsDecision`

Per lane. Modal mix.

```python
class LogisticsDecision(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    lane = models.ForeignKey(ShippingLane, on_delete=models.PROTECT)

    mode_sea_pct = models.IntegerField(default=0)
    mode_air_pct = models.IntegerField(default=0)
    mode_rail_pct = models.IntegerField(default=0)
    mode_road_pct = models.IntegerField(default=0)
    volume_commitment_teu = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [('team', 'round', 'lane')]

    def clean(self):
        total = sum([self.mode_sea_pct, self.mode_air_pct, self.mode_rail_pct, self.mode_road_pct])
        if total != 100:
            raise ValidationError(f"Modal mix must sum to 100; got {total}")
```

#### 4.2.4 `IncotermsDecision`

Per market.

```python
class IncotermsDecision(models.Model):
    INCOTERMS_CHOICES = [
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'), ('CFR', 'CFR'), ('CIF', 'CIF'),
        ('CPT', 'CPT'), ('CIP', 'CIP'), ('DAP', 'DAP'), ('DPU', 'DPU'), ('DDP', 'DDP'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    destination_market = models.ForeignKey(Market, on_delete=models.PROTECT)

    incoterms = models.CharField(max_length=3, choices=INCOTERMS_CHOICES, default='CIF')
    insurance_coverage_pct = models.IntegerField(default=110)

    class Meta:
        unique_together = [('team', 'round', 'destination_market')]
```

#### 4.2.5 `CustomsClassificationDecision`

Chinese-home teams only. Nullable on enforcement side — teams without home CN simply never create rows here.

```python
class CustomsClassificationDecision(models.Model):
    CLASSIFICATION_CHOICES = [
        ('processing_trade', 'Processing Trade'),
        ('general_trade', 'General Trade'),
        ('bonded_logistics', 'Bonded Logistics'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    destination_market = models.ForeignKey(Market, on_delete=models.PROTECT)

    classification = models.CharField(max_length=30, choices=CLASSIFICATION_CHOICES, default='general_trade')
    reverse_logistics_capacity_pct = models.IntegerField(default=0)
    reverse_logistics_hub_market = models.ForeignKey(Market, on_delete=models.PROTECT, null=True, blank=True, related_name='reverse_logistics_hub_for')

    class Meta:
        unique_together = [('team', 'round', 'destination_market')]
```

#### 4.2.6 `TradeFinanceDecision`

Per segment × market. Buyer payment terms.

```python
class TradeFinanceDecision(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    segment = models.ForeignKey(Segment, on_delete=models.PROTECT)
    market = models.ForeignKey(Market, on_delete=models.PROTECT)

    buyer_payment_instrument = models.CharField(max_length=100)  # instrument_id
    lc_doc_prep_investment = models.CharField(max_length=20, default='standard')  # minimal/standard/diligent

    class Meta:
        unique_together = [('team', 'round', 'segment', 'market')]
```

#### 4.2.7 `SinosureEnrollment`

CN home teams only.

```python
class SinosureEnrollment(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    market = models.ForeignKey(Market, on_delete=models.PROTECT)

    coverage_pct = models.IntegerField()  # 0–(instrument.coverage_ceiling_pct)

    class Meta:
        unique_together = [('team', 'round', 'market')]
```

#### 4.2.8 `FXHedgeDecision`

Per currency pair exposure.

```python
class FXHedgeDecision(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    currency_pair = models.CharField(max_length=20)  # e.g., "USD_CNY"

    hedge_ratio = models.IntegerField(default=0)
    tenor_days = models.IntegerField(default=90)

    class Meta:
        unique_together = [('team', 'round', 'currency_pair')]
```

#### 4.2.9 `InventoryDecision`

Per SKU × market.

```python
class InventoryDecision(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    market = models.ForeignKey(Market, on_delete=models.PROTECT)

    buffer_days = models.IntegerField(default=30)
    safety_stock_trigger_pct = models.IntegerField(default=20)

    class Meta:
        unique_together = [('team', 'round', 'product', 'market')]
```

#### 4.2.10 `ContingencyPlan`

Per team, per round. Structured lists in JSON.

```python
class ContingencyPlan(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    round = models.ForeignKey(Round, on_delete=models.CASCADE)

    disruption_response_playbook = models.TextField(max_length=500, blank=True)
    alt_supplier_activation_rules = models.JSONField(default=list)
    mode_switch_triggers = models.JSONField(default=list)

    class Meta:
        unique_together = [('team', 'round')]
```

### 4.3 Engine-managed state models

These are written by the engine, not by teams. Round-indexed for determinism per P3.

#### 4.3.1 `SupplierState`

Per round, per supplier. Shared across teams.

```python
class SupplierState(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)

    capacity_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    quality_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    reliability_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    additional_lead_time_days = models.IntegerField(default=0)
    disruption_cost_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')
    recovery_rounds_remaining = models.IntegerField(default=0)

    active_disruption_event = models.ForeignKey('Event', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [('round', 'supplier')]
```

#### 4.3.2 `LaneState`

Per round, per lane. Shared across teams.

```python
class LaneState(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    lane = models.ForeignKey(ShippingLane, on_delete=models.CASCADE)

    active_disruption = models.JSONField(null=True, blank=True)  # {mode_rate_multiplier, additional_lead_time_days, rounds_remaining}
    current_rate_modifier = models.DecimalField(max_digits=5, decimal_places=3, default='1.000')

    class Meta:
        unique_together = [('round', 'lane')]
```

#### 4.3.3 `SCEventInstance`

A fired instance of an event in a given round. Distinct from SCEventTemplate (the scenario declaration).

```python
class SCEventInstance(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    event_template = models.ForeignKey('Event', on_delete=models.PROTECT)

    affects_all_teams = models.BooleanField(default=True)
    affected_teams = models.ManyToManyField(Team, blank=True)
    fired_by_instructor = models.BooleanField(default=False)

    resolution_data = models.JSONField(default=dict)  # snapshot of applied effects for audit/replay

    class Meta:
        indexes = [
            models.Index(fields=['round']),
        ]
```

#### 4.3.4 `HedgePosition`

Multi-round lifecycle.

```python
class HedgePosition(models.Model):
    STATUS_CHOICES = [('open', 'Open'), ('closed', 'Closed'), ('matured', 'Matured')]
    DIRECTION_CHOICES = [('long', 'Long'), ('short', 'Short')]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='hedge_positions')
    currency_pair = models.CharField(max_length=20)

    notional = models.DecimalField(max_digits=14, decimal_places=2)
    locked_rate = models.DecimalField(max_digits=10, decimal_places=5)
    opened_round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name='hedges_opened')
    maturity_round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name='hedges_maturing')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    mtm_current = models.DecimalField(max_digits=14, decimal_places=2, default='0.00')
    realized_pnl = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
```

#### 4.3.5 `ResilienceScoreHistory`

Per team, per round. Component breakdown retained per P3 and CC-3 §6.5.

```python
class ResilienceScoreHistory(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='resilience_history')
    round = models.ForeignKey(Round, on_delete=models.CASCADE)

    score = models.DecimalField(max_digits=5, decimal_places=3)  # 0.000–1.000
    components = models.JSONField()  # {multi_sourcing: 0.x, geographic_diversity: 0.x, ...}
    weights_used = models.JSONField()  # snapshot of weights at time of calculation

    class Meta:
        unique_together = [('team', 'round')]
```

### 4.4 EXTEND models

Additive fields only. Existing fields unchanged.

#### 4.4.1 `DecisionPlant` extension

Per CC-2 §5.1. Confirmed non-ghost in CC-2 Section C. Per CC-2 inventory, existing fields are `{action, capacity_units, contract_mfg_volume, id, market, submission}` — no collisions with proposed additions.

Fields added via migration:

```python
# Added to DecisionPlant via migration
sourcing_node_role = models.CharField(
    max_length=30,
    choices=[
        ('owned_manufacturing', 'Owned Manufacturing'),
        ('contract_manufacturing', 'Contract Manufacturing'),
        ('pure_assembly', 'Pure Assembly'),
    ],
    default='owned_manufacturing',
)
upstream_suppliers_required = models.JSONField(default=list)  # list of specialization strings, engine-computed
scope_1_co2_per_unit_kg = models.DecimalField(max_digits=7, decimal_places=3, default='0.000')
scope_2_co2_per_unit_kg = models.DecimalField(max_digits=7, decimal_places=3, default='0.000')
reverse_logistics_enabled = models.BooleanField(default=False)
```

#### 4.4.2 `DecisionESG` extension

Per CC-2 §5.2. Target confirmed as `DecisionESG` (not `ESGEconomicImpact`) per the design dialogue on CC-2's acceptance. Existing fields `{environmental_investment, governance_commitments, id, social_investment, submission}` — no collisions.

Fields added via migration:

```python
# Added to DecisionESG via migration
supplier_audit_program = models.CharField(
    max_length=20,
    choices=[('none', 'None'), ('basic', 'Basic'), ('comprehensive', 'Comprehensive')],
    default='none',
)
scope_3_emissions_tracking = models.BooleanField(default=False)
scope_3_investment_usd = models.IntegerField(default=0)
cbam_reporting_readiness = models.BooleanField(default=False)
uflpa_tier_mapping_investment = models.CharField(
    max_length=20,
    choices=[('none', 'None'), ('partial', 'Partial'), ('full', 'Full')],
    default='none',
)
```

---

## 5. Migration Strategy

Migrations are grouped by logical concern, not per-model. This produces a reviewable migration set where each file represents a coherent schema unit.

### 5.1 Migration groups

| Order | Migration | Contains |
|---|---|---|
| 0040 | `scenario_supply_chain_content.py` | Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime, ResilienceParameters, FreightMarket |
| 0041 | `event_category_extension.py` | Adds `category` field to existing Event model (or creates SCEventExtension per inventory findings) |
| 0042 | `sourcing_decisions.py` | SourcingAllocation, SourcingDecision |
| 0043 | `logistics_decisions.py` | LogisticsDecision, IncotermsDecision, CustomsClassificationDecision |
| 0044 | `trade_finance_decisions.py` | TradeFinanceDecision, SinosureEnrollment, FXHedgeDecision |
| 0045 | `inventory_decisions.py` | InventoryDecision, ContingencyPlan |
| 0046 | `engine_state_models.py` | SupplierState, LaneState, SCEventInstance, HedgePosition, ResilienceScoreHistory |
| 0047 | `decision_plant_sc_extensions.py` | Adds fields to DecisionPlant |
| 0048 | `decision_esg_sc_extensions.py` | Adds fields to DecisionESG |

Actual starting number (0040 here) adjusts to match whatever the current migration chain ends at (verify via `showmigrations` in precondition inventory).

### 5.2 Reversibility

Every migration is reversible. `ALTER TABLE ADD COLUMN` operations reverse via `ALTER TABLE DROP COLUMN`. `CreateModel` operations reverse via `DeleteModel`. No irreversible data transformations in CC-4 migrations — data transformation is content work, not schema work.

### 5.3 Verification after each migration group

Per STANDING-DISCIPLINE §4:

```bash
python manage.py makemigrations --dry-run   # confirm no pending model changes
python manage.py migrate <app> <migration_name>
python manage.py check
python manage.py showmigrations <app>
```

If any step fails or reports unexpected output, halt and report per §3.

---

## 6. Serializer Design

One serializer per decision model. DRF `ModelSerializer` base unless a specific reason to diverge.

### 6.1 Write vs. read separation

Write serializers (used for POST/PATCH) enforce CC-2 progressive disclosure: locked fields at the current round are rejected with validation error. Read serializers (used for GET) return all stored fields regardless of lock state — the frontend decides what to display.

Rationale: prevents students from bypassing the UI to submit locked-field values, while keeping read-side behavior simple for instructor panel needs.

Example pattern for `LogisticsDecision`:

```python
class LogisticsDecisionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsDecision
        fields = '__all__'


class LogisticsDecisionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsDecision
        fields = ['team', 'round', 'lane', 'mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct', 'volume_commitment_teu']

    def validate(self, data):
        # Progressive disclosure check
        round_number = data['round'].number
        if round_number < 3:
            # Modal mix locked — reject any non-default values
            if any([data.get(f) for f in ['mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct']]):
                raise serializers.ValidationError("Modal mix not yet unlocked at this round")
        if round_number < 5 and data.get('volume_commitment_teu'):
            raise serializers.ValidationError("Volume commitments not yet unlocked at this round")

        # Modal mix sum check (from model.clean())
        total = sum([data.get(f, 0) for f in ['mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct']])
        if total != 100:
            raise serializers.ValidationError(f"Modal mix must sum to 100; got {total}")

        # Available-mode check
        lane = data['lane']
        for mode in ['sea', 'air', 'rail', 'road']:
            if data.get(f'mode_{mode}_pct', 0) > 0 and not lane.modes.get(mode, {}).get('available', False):
                raise serializers.ValidationError(f"Mode {mode} not available on lane {lane.lane_id}")

        return data
```

### 6.2 Nested serialization

`SourcingDecision` (page-level) and `SourcingAllocation` (row-level) are nested — a single POST includes the page-level fields and a list of allocation rows. Use DRF writable nested serializers or accept flat POST then materialize in the view. CC-4 uses the flat-POST-then-materialize pattern for simplicity; nested writable is brittle.

### 6.3 Scenario-content serializers

Read-only for teams (they consume scenario content but don't modify it). Used in endpoints that feed the decision pages with supplier options, lane options, etc.

---

## 7. API Endpoint Design

Endpoint paths follow the existing convention surfaced in the reference inventory report Section C. Assumed base `/api/v1/` pending confirmation.

### 7.1 Decision submission endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/teams/{team_id}/rounds/{round_id}/sourcing/` | Submit sourcing decisions (page-level + allocation rows) |
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/sourcing/` | Retrieve current sourcing decisions |
| POST | `/api/v1/teams/{team_id}/rounds/{round_id}/logistics/` | Submit logistics decisions (modal mix, Incoterms, customs) |
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/logistics/` | Retrieve current logistics decisions |
| POST | `/api/v1/teams/{team_id}/rounds/{round_id}/trade-finance/` | Submit trade finance decisions |
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/trade-finance/` | Retrieve |
| POST | `/api/v1/teams/{team_id}/rounds/{round_id}/inventory/` | Submit inventory & contingency decisions |
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/inventory/` | Retrieve |

### 7.2 Scenario-content retrieval endpoints

Scenario content is read-only from the team's perspective. These feed the decision pages with options.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/scenarios/{scenario_id}/suppliers/` | List suppliers in this scenario, optionally filtered by specialization |
| GET | `/api/v1/scenarios/{scenario_id}/lanes/` | List shipping lanes |
| GET | `/api/v1/scenarios/{scenario_id}/trade-finance-instruments/` | List available instruments |
| GET | `/api/v1/scenarios/{scenario_id}/compliance-regimes/` | List regimes |

### 7.3 State retrieval endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/resilience-score/` | Current resilience score with component breakdown |
| GET | `/api/v1/teams/{team_id}/hedge-positions/` | List open and recently-closed hedge positions |
| GET | `/api/v1/teams/{team_id}/rounds/{round_id}/sc-events/` | SC events fired this round affecting the team |

### 7.4 Authentication and permissions

Per the existing JWT pattern (confirmed in reference inventory Section C). Every endpoint requires authentication. Students access only their own team's data; instructors access all teams in their classes.

---

## 8. Scenario YAML Loader Extension

The existing `manage.py load_scenario` command is extended to consume the new YAML sections. Per CC-1 §8, validation rules are enforced at load time.

### 8.1 Loader changes

```python
# Pseudocode for load_scenario extensions
def load_scenario(yaml_path):
    data = yaml.safe_load(open(yaml_path))
    scenario = get_or_create_scenario(data['metadata'])

    # Existing GlobalStrat sections (unchanged)
    load_features(scenario, data.get('features', []))
    load_markets(scenario, data.get('markets', []))
    # ... etc.

    # NEW sections
    load_suppliers(scenario, data.get('suppliers', []))
    load_shipping_lanes(scenario, data.get('shipping_lanes', []))
    load_trade_finance_instruments(scenario, data.get('trade_finance_instruments', {}))
    load_compliance_regimes(scenario, data.get('compliance_regimes', []))
    load_resilience_parameters(scenario, data.get('resilience_parameters', {}))
    load_freight_market(scenario, data.get('freight_market', {}))
    load_sc_event_templates(scenario, data.get('events', []))  # SC events merged into existing events

    # Validation per CC-1 §8
    run_scenario_validations(scenario)
```

### 8.2 Validation on load

The nine validation rules from CC-1 §8 execute after all content is loaded. Any validation failure rolls back the entire scenario load (atomic transaction).

### 8.3 Loader test

Load the skeleton YAML from CC-1 (`scenarios/consumer_electronics_plus_skeleton.yaml`) and confirm:
- All new-section content materializes as DB rows.
- Validation passes.
- Re-loading is idempotent (no duplicate rows).

---

## 9. Verification Checkpoints

Per STANDING-DISCIPLINE §5, CC-4 has verification checkpoints at each phase:

### 9.1 After migration group 0040 (scenario content)

```bash
python manage.py migrate core 0040
python manage.py check
python manage.py shell <<'PY'
from core.models import Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime, ResilienceParameters, FreightMarket
print(f"Suppliers: {Supplier.objects.count()}")  # expect 0
print(f"Lanes: {ShippingLane.objects.count()}")  # expect 0
# Etc. Tables exist, queryable, empty.
PY
```

### 9.2 After migration group 0041 (event extension)

Verify existing Event records still have their original field values (no data loss from adding the `category` column).

### 9.3 After each decision-model migration (0042–0045)

Verify the migration is reversible by running `migrate core <previous>` then back `migrate core <current>`. Reversed DB state matches starting point.

### 9.4 After engine-state migration (0046)

Confirm FK relationships resolve correctly — create a Round, a Supplier, and a SupplierState row via ORM; query via reverse accessor.

### 9.5 After EXTEND migrations (0047, 0048)

Re-run CC-2's field inventory spot-check against DecisionPlant and DecisionESG. Confirm new fields visible in `_meta.get_fields()` AND in psql `\d`. No drift.

### 9.6 After serializers and endpoints

Hit each endpoint with Django test client:

- GET scenario-content endpoints return empty lists (no data loaded yet).
- POST decision endpoints with valid payload succeed and materialize DB rows.
- POST with invalid payload (bad modal mix sum, locked-field submission) returns 400 with clear error.

### 9.7 Final: load skeleton YAML end-to-end

```bash
python manage.py load_scenario scenarios/consumer_electronics_plus_skeleton.yaml
python manage.py shell <<'PY'
from core.models import Supplier
# Confirm skeleton entries loaded
print([s.supplier_id for s in Supplier.objects.all()])
PY
```

---

## 10. What This Spec Does NOT Cover

| Concern | Spec |
|---|---|
| Engine pipeline implementation (Phase 1 step logic) | Build pipeline CC (post-CC-6) |
| Real scenario seed data | **CC-8** |
| Frontend components | **CC-10 through CC-15** |
| Ghost model triage for the 40 ghosts | **CC-5** |
| Instructor panel SC extensions | **CC-16** |
| Phase 2 LLM narrative implementation | **CC-17** |

---

## 11. Acceptance Criteria

CC-4 is complete when:

1. `specs/reports/CC-04-reference-inventory.md` exists with all three sections (FK targets, app layout, DRF conventions) and no unresolved halts.
2. All migration groups 0040–0048 (adjusted numbering per actual starting state) apply cleanly. `python manage.py check` reports zero issues. `python manage.py showmigrations` shows all new migrations applied.
3. Every new model is queryable via ORM (empty results, but no exceptions).
4. Every DRF endpoint returns expected status codes: GET returns 200 with empty or valid payload; POST with valid data returns 201 and materializes DB rows; POST with invalid data returns 400 with structured error.
5. `load_scenario` loads the CC-1 skeleton YAML successfully. All NEW-section rows materialize. Re-loading is idempotent (no duplicates, no errors).
6. DecisionPlant and DecisionESG have their new fields visible in both Django introspection and psql `\d`. CC-2's field inventory baseline is preserved for existing fields.
7. Branch `cc-04-data-model` contains all CC-4 commits and is merged to `main` after verification.
8. **No engine logic code is written.** Engine state models exist but the logic that populates them (CC-3 pseudocode) is not implemented in CC-4.
9. **No frontend code is written.** Endpoints exist and respond, but no React components are created.

**Report back to the user with:** the reference inventory report contents, `showmigrations` output, endpoint response samples (one successful POST per decision type, one failure case per), `load_scenario` output against the skeleton YAML, and explicit confirmation that no engine logic or frontend code was written.

---

## 12. Open Questions for CC-6

- **Nested POST structure.** §6.2 chose flat-POST-then-materialize over writable nested serializers for the SourcingDecision + SourcingAllocation pair. The pattern is solid but worth reconfirming with frontend needs (CC-10) — if the frontend naturally produces nested payloads, revisit.
- **Multi-scenario simultaneous load.** Can the loader handle two scenarios in the DB at once (e.g., Consumer Electronics and Clean Energy Tech both loaded)? The schema supports it (every scenario-content model has a `scenario` FK). The loader currently assumes single active scenario per class; whether this should change for multi-scenario classes is a CC-6 pedagogical question.
- **Round 0 seeding for state models.** When a class is created, do state models (SupplierState, LaneState) need Round 0 rows seeded to baseline, or do they lazy-init on first round advance? CC-3 assumes states exist at advance time. CC-6 can lock this, or CC-4 can default to lazy-init and adjust later.

---

## 13. Interactions with Prior Findings

- **Ghost models (CC-1 D2, CC-2 Section B).** CC-4 creates only NEW models and EXTENDS confirmed non-ghost models. Zero ghost model interaction. If the reference inventory Section A surfaces any ghost in the FK target list (Team, Round, Market, etc.), CC-4 halts — those are structural anchors that can't be ghost.
- **pg_dump version alignment (CC-1 D3).** Not directly relevant to CC-4 (no dumps). Included for completeness.
- **Event category extension (§4.1.7, §5 migration 0041).** The precise form depends on CC-3 engine inventory findings. Spec explicitly halts and defers to design conversation if the inventory reveals an unexpected event-model architecture.
