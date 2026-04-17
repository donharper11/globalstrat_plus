# CC-1: globalstrat+ Scenario Schema

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — scenario schema
**Baseline:** GlobalStrat scenario schema (inherited as-is where possible)
**Observes:** `specs/STANDING-DISCIPLINE.md` (created as part of this spec — see Section 2.4a)
**Status:** Ready for Claude Code execution

---

## 1. Purpose

This spec defines the scenario YAML schema for globalstrat+. It is the foundation document every subsequent CC spec references — the contract between scenario authoring and the engine, data model, and decision surface.

globalstrat+ is forked from GlobalStrat and shares its scenario schema as the baseline. This document enumerates (a) what transfers from GlobalStrat unchanged, (b) which existing GlobalStrat sections need extending, and (c) what is net new.

Guiding principle: **minimum-necessary-change**. GlobalStrat sections that don't conflict with globalstrat+ mechanics are inherited verbatim. Sections that need globalstrat+ semantics are extended additively (existing fields remain functional). New sections exist only where globalstrat+ demands a concept GlobalStrat has no equivalent for.

---

## 2. Repository Setup (preamble steps)

Per the existing scan, `/home/ubuntu/projects/globalstrat+/` already contains the forked GlobalStrat codebase with an empty `specs/` folder and no git history. Claude Code executes these steps before any schema work:

### 2.1 Verify starting state

```bash
cd /home/ubuntu/projects/globalstrat+/
ls -la                    # Expect GlobalStrat code present
git status 2>&1 || true   # Expect "not a git repository"
ls specs/                 # Expect empty directory
```

If any of these fail, halt and report — do not attempt to re-fork.

### 2.2 Initialize git

```bash
git init
git branch -m main
```

### 2.3 Create/verify `.gitignore`

Ensure `.gitignore` at repo root covers the standard Django/Python/React ignores:

```
# Python
__pycache__/
*.pyc
*.pyo
venv/
env/
.venv/
.env
.env.local

# Django
db.sqlite3
db.sqlite3-journal
staticfiles/
media/
*.log

# Node / React
node_modules/
frontend/build/
frontend/.env
npm-debug.log*

# OS / IDE
.DS_Store
.idea/
.vscode/
*.swp
```

### 2.4 Place this spec

```bash
# This file lives at: specs/CC-01-scenario-schema.md
```

### 2.4a Create Standing Discipline reference

Place `specs/STANDING-DISCIPLINE.md` (provided alongside this spec) in the `specs/` directory. This document establishes the verify-before-wire rules Claude Code observes for every CC bundle. Every subsequent CC spec's header will declare `Observes: specs/STANDING-DISCIPLINE.md`, and Claude Code re-reads it at the start of every bundle.

### 2.5 Initial commit

```bash
git add .
git commit -m "CC-1: fork globalstrat as globalstrat+ baseline; establish repo and specs directory"
```

All subsequent CC spec work happens on feature branches (`cc-02-decision-taxonomy`, etc.) and merges to `main` on verification. No direct commits to `main` after the initial commit.

### 2.6 PostgreSQL database setup

globalstrat+ requires its own PostgreSQL database, separate from GlobalStrat's. The forked codebase currently points at GlobalStrat's database; leaving it pointed there would cause globalstrat+ migrations to corrupt the running GlobalStrat instance. This step provisions the new database and repoints the fork.

**Step 1: Verify current GlobalStrat database configuration.**

Per STANDING-DISCIPLINE.md Section 1.5, confirm the existing settings before changing anything:

```bash
cd /home/ubuntu/projects/globalstrat+/
# Locate the DATABASES block
grep -rn "DATABASES" --include="*.py" | grep -v __pycache__
# Read the actual values (may be in settings.py or split settings modules)
```

Record: current database name, host (expected 192.168.50.38), port, user. Do not proceed if the host, user, or port are unexpected — report and halt.

**Step 2: Create the new database.**

Connect to the PostgreSQL host and create the new database:

```bash
# From a machine with psql access to 192.168.50.38
psql -h 192.168.50.38 -U <postgres_admin_user> -c "CREATE DATABASE globalstrat_plus;"
psql -h 192.168.50.38 -U <postgres_admin_user> -c "GRANT ALL PRIVILEGES ON DATABASE globalstrat_plus TO <existing_django_user>;"
```

The Django user is the same user GlobalStrat uses (reusing the user avoids credential sprawl; the databases themselves are isolated).

**Step 3: Repoint the fork's settings.**

Update the `DATABASES['default']['NAME']` value from the GlobalStrat DB name to `globalstrat_plus`. Verify the change with:

```bash
python manage.py dbshell -c "SELECT current_database();"
# Must return: globalstrat_plus
```

If it returns the GlobalStrat database name, **halt** — the settings repoint did not take effect, and running migrations now would damage GlobalStrat's schema.

**Step 4: Run baseline migrations.**

With the fork pointed at the empty `globalstrat_plus` database:

```bash
python manage.py migrate
python manage.py check
```

This produces a fresh `globalstrat_plus` with GlobalStrat's baseline schema. Subsequent CC specs add globalstrat+-specific migrations on top.

**Step 5: Commit the settings change.**

```bash
git add .
git commit -m "CC-1: repoint fork at globalstrat_plus database"
```

### 2.7 Qdrant collection setup

GlobalStrat's RAG content lives in Qdrant at 192.168.50.186. globalstrat+ needs its own collection so supply-chain-specific RAG content (shipping regulations, trade finance references, compliance guidance) doesn't mingle with GlobalStrat's strategy literature.

**Step 1: Verify GlobalStrat's current collection configuration.**

```python
from qdrant_client import QdrantClient
client = QdrantClient(host="192.168.50.186", port=6333)
collections = client.get_collections()
# Identify GlobalStrat's collection name
# Record: collection name, vector size, distance metric
```

**Step 2: Create the globalstrat+ collection.**

Collection name: `globalstrat_plus_articles`. Vector size and distance metric match GlobalStrat's existing configuration (so the same BGE-M3 or equivalent embedding model can be reused).

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="192.168.50.186", port=6333)
client.create_collection(
    collection_name="globalstrat_plus_articles",
    vectors_config=VectorParams(
        size=<match_globalstrat_size>,
        distance=Distance.COSINE,  # or match existing
    ),
)
```

**Step 3: Update the fork's Qdrant client configuration.**

Locate where GlobalStrat's Qdrant collection name is referenced (typically a settings constant or environment variable) and update it to `globalstrat_plus_articles`. Verify:

```bash
grep -rn "QDRANT_COLLECTION" --include="*.py" | grep -v __pycache__
grep -rn "globalstrat_articles" --include="*.py" | grep -v __pycache__
```

Commit the Qdrant config change:

```bash
git add .
git commit -m "CC-1: repoint fork at globalstrat_plus_articles Qdrant collection"
```

No RAG content is ingested during CC-1. Content ingestion is a later build-pipeline spec.

---

## 3. Schema Classification Framework

Every top-level section of the globalstrat+ scenario YAML is classified as:

- **INHERIT** — identical to GlobalStrat; no schema changes
- **EXTEND** — GlobalStrat schema plus globalstrat+ fields (additive only)
- **NEW** — no GlobalStrat equivalent; defined below in full

---

## 4. INHERIT Sections (verbatim from GlobalStrat)

The following sections transfer from GlobalStrat without modification. Claude Code does NOT touch these during CC-1:

| Section | Notes |
|---|---|
| `metadata` | Scenario id, name, industry, version, language support (EN/ZH) |
| `features` | Platform features with Gen 1→2→3 progression; no SC-specific fields |
| `segments` | Customer segments per market; preferences, size, growth, price sensitivity |
| `ai_competitors` | Reactive AI competitor profiles |
| `tax_structures` | Corporate tax, transfer pricing, withholding |
| `alliances` / `alliance_partner_profiles` | Alliance templates and partner behavior |
| `governments` | Government actor profiles; SC-aware prompt extensions deferred to CC-39 |
| `cultural_distance` | Pairwise cultural distance matrix |
| `origin_trust` | Origin-country → buyer-market trust coefficients (used as-is for finished-product origin) |

Note on `origin_trust`: the matrix is inherited unchanged. Supplier-origin trust effects are a *symmetric application* of the same values via the `suppliers.*.origin_trust_to_buyers` field (Section 6.1), not a modification of the matrix itself.

---

## 5. EXTEND Sections

These existing GlobalStrat sections receive additive fields. Existing fields remain functional.

### 5.1 `markets` — compliance regime bindings

Each market gains a reference to applicable compliance regimes (defined in Section 6.4):

```yaml
markets:
  - id: us_market
    # ... all existing GlobalStrat fields (currency, tax, tariffs, etc.) ...
    # NEW:
    compliance_regimes: [uflpa, us_bis_entity_list, cfius_review]
    customs_enforcement_intensity: 0.75       # 0–1
    processing_trade_recognition: false       # Whether this market uses China-style processing trade category
```

### 5.2 `plants` (DecisionPlant) — sourcing node integration

Per the last design conversation, we extend `DecisionPlant` rather than replace it. Plants become one type of sourcing node within a broader supplier architecture. Existing fields retained; new fields added:

```yaml
plants:
  - id: own_shenzhen_plant
    # ... all existing fields (location, capacity, cost_per_unit, quality_profile, etc.) ...
    # NEW:
    sourcing_node_role: owned_manufacturing     # owned_manufacturing | contract_manufacturing | pure_assembly
    upstream_suppliers_required: [semiconductors, displays, batteries]
    output_feeds_lanes: [cn_shanghai_to_all_markets]
    scope_1_co2_per_unit_kg: 2.4                # For CBAM calculation
    scope_2_co2_per_unit_kg: 1.8
    accepts_reverse_logistics: true
```

This preserves the existing plant cost math while the new supplier layer attaches upstream.

### 5.3 `esg` — supplier and Scope 3 extensions

```yaml
esg:
  # ... existing fields retained ...
  # NEW:
  supplier_audit_program:
    investment_tiers:
      - level: basic
        annual_cost_usd: 200000
        tier_1_visibility: full
        tier_2_visibility: partial
      - level: comprehensive
        annual_cost_usd: 800000
        tier_1_visibility: full
        tier_2_visibility: full
        tier_3_visibility: partial
  scope_3_emissions_tracking:
    enabled: true
    supplier_reporting_investment_usd: 150000
  cbam_reporting_readiness:
    investment_usd: 300000
    reduces_cbam_processing_friction: true
```

### 5.4 `events` — catalog expansion

The existing `events` container schema is unchanged. globalstrat+ adds event templates with `category: supply_chain`. Field additions specific to SC events are defined in Section 6.5.

---

## 6. NEW Sections

### 6.1 `suppliers`

The supplier roster. Each entry declares a tier-1 supplier available for teams to source from.

```yaml
suppliers:
  - id: tsmc_taiwan
    name: "Taiwan Semiconductor Manufacturing Company"
    country: TW
    tier: 1
    specialization: [semiconductors, advanced_chips]
    capacity_units_per_round: 500000
    base_unit_price_usd: 45.00
    quality_rating: 0.95          # 0–1, multiplier on finished product quality
    reliability_rating: 0.92      # 0–1, on-time delivery probability under normal conditions
    lead_time_days_baseline: 45
    min_order_commitment: 10000
    volume_discount_tiers:
      - threshold_units: 50000
        discount_pct: 3
      - threshold_units: 200000
        discount_pct: 7
    tier_2_3_profile:
      transparency_default: 0.6   # 0–1; tier-2 visibility without investment
      geographic_concentration:
        TW: 0.40
        CN: 0.30
        JP: 0.20
        KR: 0.10
      risk_flags:
        xinjiang_adjacent: false
        conflict_minerals: low
        forced_labor_exposure: low
    origin_trust_to_buyers:
      # When this supplier is in your bill of materials, how do buyer markets perceive it?
      NA: -0.15
      EU: -0.05
      APAC: 0.10
      LATAM: 0.00
    certifications: [ISO_9001, ISO_14001, IATF_16949]
    accepts_trade_finance: [letter_of_credit, documentary_collection, open_account]
    political_risk_profile:
      geopolitical_exposure: [cross_strait_tension, us_export_controls]
      expropriation_risk: low
      sanctions_exposure: low
    multi_source_substitutability:
      # Which other suppliers can partially or fully substitute in a disruption?
      - supplier_id: samsung_foundry_korea
        substitution_fraction: 0.7
      - supplier_id: smic_china
        substitution_fraction: 0.4     # Lower because of US export restrictions
```

**Required fields:** `id`, `name`, `country`, `tier`, `specialization`, `capacity_units_per_round`, `base_unit_price_usd`, `quality_rating`, `reliability_rating`, `lead_time_days_baseline`.

**Scenario authoring expectations:**
- 15–25 suppliers in the Consumer Electronics reference scenario, covering semiconductors, displays, batteries, casings, assembly.
- Every critical input category has at least 3 suppliers across at least 2 countries (multi-sourcing must be a real choice).
- At least 2 suppliers have `xinjiang_adjacent: true` or tier-2 Xinjiang concentration so UFLPA pedagogy lands.

### 6.2 `shipping_lanes`

Origin-destination pairs with modal options. A lane describes what's *possible*; the team's modal mix decision (defined in CC-2) selects what's *used*.

```yaml
shipping_lanes:
  - id: cn_shanghai_to_us_long_beach
    origin_country: CN
    origin_port: shanghai
    destination_country: US
    destination_port: long_beach
    zone: transpacific
    modes:
      sea:
        baseline_cost_per_teu_usd: 2500
        baseline_lead_time_days: 28
        capacity_abundance: normal          # normal | constrained | glut
        fuel_pass_through_pct: 60
      air:
        baseline_cost_per_kg_usd: 8.50
        baseline_lead_time_days: 3
        capacity_abundance: constrained
        fuel_pass_through_pct: 85
      rail:
        available: false
      road:
        available: false
    chokepoints:
      panama_canal: false
      suez_canal: false
      malacca_strait: true
    disruption_exposure:
      typhoon_season_months: [7, 8, 9, 10]
      port_congestion_baseline_prob: 0.15
      geopolitical_incidents: [taiwan_strait_tension]
    customs_processing_days_baseline: 4
    reverse_logistics_available: true
    reverse_logistics_cost_multiplier: 1.8
```

**Scenario authoring expectations:**
- Every origin country in the supplier roster has at least one lane to every buyer market.
- Key geopolitical lanes declared distinctly so events can target them: Asia→Europe via Suez, Asia→Europe via Cape, Asia→US transpacific, intra-Asia, and (where scenario demands) China→BRI lanes (Piraeus, Colombo, Djibouti, Gwadar).
- Rail lanes explicitly declared for the China–Europe Belt and Road rail corridor where relevant.

### 6.3 `trade_finance_instruments`

The catalog of trade finance instruments. Per-market availability is controlled by each instrument's `available_in_markets` field.

```yaml
trade_finance_instruments:
  letter_of_credit:
    display_name: "Letter of Credit"
    cost_bps_of_transaction: 150
    processing_lead_days: 7
    seller_protection: high
    buyer_cash_requirement: high
    available_in_markets: [all]
    rejection_probability_baseline: 0.02
    documentation_discipline_sensitivity: high

  documentary_collection:
    display_name: "Documentary Collection (D/P, D/A)"
    cost_bps_of_transaction: 40
    processing_lead_days: 3
    seller_protection: medium
    buyer_cash_requirement: low
    available_in_markets: [all]

  open_account:
    display_name: "Open Account"
    cost_bps_of_transaction: 0
    processing_lead_days: 0
    seller_protection: low
    buyer_cash_requirement: none
    available_in_markets: [EU, NA]          # Typical for trusted long-term relationships
    buyer_default_probability_baseline: 0.015

  sinosure_coverage:
    display_name: "Sinosure Export Credit Insurance"
    cost_pct_of_insured_value: 0.8
    coverage_ceiling_pct: 90
    available_to_home_countries: [CN]
    bri_market_premium_subsidy_pct: 40
    political_risk_covered: true
    commercial_risk_covered: true
    claim_processing_rounds: 2

  fx_forward:
    display_name: "FX Forward Contract"
    cost_bps: 25
    tenor_options_days: [30, 60, 90, 180]
    currency_pairs_available: [USD_CNY, EUR_CNY, JPY_CNY, GBP_CNY]
```

### 6.4 `compliance_regimes`

The regulatory apparatus. Regimes are referenced by markets (Section 5.1) and can trigger events (Section 6.5).

```yaml
compliance_regimes:
  - id: uflpa
    name: "Uyghur Forced Labor Prevention Act"
    enforcing_market: US
    applies_to_products: [electronics, textiles, solar_panels, automotive_components]
    trigger_condition: tier_2_3_xinjiang_exposure_above_threshold
    trigger_threshold_pct: 5
    baseline_enforcement_probability_per_round: 0.15
    detention_consequence:
      shipment_value_loss_pct: 100
      remediation_cost_usd: 500000
      market_access_freeze_rounds: 2
    mitigation_investments:
      tier_2_mapping:
        cost_usd: 800000
        reduces_enforcement_probability_pct: 70

  - id: cbam
    name: "Carbon Border Adjustment Mechanism"
    enforcing_market: EU
    phase_in_schedule:
      - round: 1
        coverage_pct: 25
      - round: 3
        coverage_pct: 50
      - round: 5
        coverage_pct: 100
    tariff_per_ton_co2_usd: 85
    sectors_covered: [steel, aluminum, cement, hydrogen, electricity, fertilizer]
    reporting_burden_hours_per_shipment: 12

  - id: us_bis_entity_list
    name: "BIS Entity List Export Controls"
    enforcing_country: US
    restricted_technologies: [advanced_semiconductors, ai_chips, euv_lithography]
    target_countries_baseline: [CN, RU, IR, KP]
    event_driven_expansion: true
    violation_penalty_usd: 10000000
    violation_market_access_impact: indefinite_freeze

  - id: chinese_export_controls_rare_earths
    name: "China Rare Earth Export Controls"
    enforcing_country: CN
    restricted_materials: [gallium, germanium, graphite, heavy_rare_earths]
    target_countries_baseline: []             # Licensing regime, not blanket ban
    licensing_friction_days: 45

  - id: processing_trade_regime
    name: "China Processing Trade Classification"
    enforcing_country: CN
    classification_options: [processing_trade, general_trade, bonded_logistics]
    duty_exemption_processing_trade: true
    administrative_burden_processing_trade: medium
    applicable_to_ftz_operations: true
```

### 6.5 Supply chain event templates

Event templates added to the existing `events` section with `category: supply_chain`.

```yaml
events:
  # ... existing GlobalStrat events retained ...

  - id: taiwan_earthquake_semiconductor
    category: supply_chain
    trigger_probability_per_round: 0.03
    affected_suppliers: [tsmc_taiwan, umc_taiwan]
    capacity_reduction_pct: 40
    recovery_rounds: 3
    teaches: single_source_risk
    teams_affected: all_with_exposure

  - id: red_sea_shipping_disruption
    category: supply_chain
    trigger_probability_per_round: 0.08
    affected_lanes: [asia_to_europe_via_suez]
    mode_rate_multiplier:
      sea: 2.8
      air: 1.4
    additional_lead_time_days: 14
    duration_rounds: 2
    teaches: [modal_alternatives, buffer_inventory]

  - id: uflpa_detention_incident
    category: supply_chain
    trigger_probability_per_round: 0.10
    condition: team_has_xinjiang_tier2_exposure_above_threshold
    shipment_value_loss_pct: 100
    reputation_impact: high
    teaches: tier_2_visibility

  - id: bis_entity_list_expansion
    category: supply_chain
    trigger_probability_per_round: 0.05
    added_restricted_firms: scenario_specified
    teams_affected: exposed
    teaches: export_control_risk

  - id: container_freight_rate_shock
    category: supply_chain
    trigger_probability_per_round: 0.10
    global_rate_multiplier:
      sea: 2.2
    duration_rounds: 3
    teaches: hedge_freight_exposure

  - id: supplier_financial_distress
    category: supply_chain
    trigger_probability_per_round: 0.04
    affected_supplier: scenario_specified
    capacity_reduction_pct: 60
    quality_rating_degradation: 0.15
    teaches: supplier_health_monitoring

  - id: lc_rejection
    category: supply_chain
    trigger_probability_per_round: 0.03
    condition: team_uses_lc_with_discrepancies
    revenue_delay_rounds: 1
    teaches: trade_documentation_discipline

  - id: cny_appreciation_shock
    category: supply_chain
    trigger_probability_per_round: 0.05
    fx_move_pct: 8
    teaches: fx_hedging

  - id: cbam_enforcement_tightening
    category: supply_chain
    trigger_probability_per_round: 0.04
    cbam_rate_multiplier: 1.5
    teaches: carbon_intensity_management

  - id: bri_port_capacity_expansion
    category: supply_chain
    type: opportunity                         # Not all events are negative
    trigger_probability_per_round: 0.03
    affected_lanes: [cn_to_piraeus, cn_to_colombo]
    cost_reduction_pct: 15
    teaches: institutional_logistics_advantage

  - id: panama_canal_drought
    category: supply_chain
    trigger_probability_per_round: 0.04
    affected_lanes: [asia_to_us_east_coast_via_panama]
    mode_rate_multiplier:
      sea: 1.8
    additional_lead_time_days: 10
    teaches: chokepoint_exposure

  - id: sinosure_coverage_tightening
    category: supply_chain
    trigger_probability_per_round: 0.03
    condition: team_over_indexed_on_sinosure_bri_markets
    coverage_ceiling_reduction_pct: 20
    teaches: institutional_risk_tool_limits
```

**Minimum scenario coverage:** 15 supply chain event templates.

### 6.6 `resilience_parameters`

Parameters governing how the engine scores supply chain resilience and triggers disruption consequences.

```yaml
resilience_parameters:
  single_source_threshold_pct: 70
  geographic_concentration_threshold_pct: 60
  critical_component_buffer_days_recommended: 45
  bullwhip_coefficient_baseline: 1.4
  resilience_score_weights:
    multi_sourcing: 0.25
    geographic_diversity: 0.20
    buffer_inventory_adequacy: 0.15
    modal_flexibility: 0.15
    tier_2_visibility: 0.15
    supplier_financial_health: 0.10
  disruption_cascade_coefficient: 0.3          # How strongly a tier-1 disruption propagates
  recovery_rate_with_alternatives_multiplier: 0.5   # Multi-source halves recovery time
```

### 6.7 `freight_market`

Global freight market parameters that modulate lane costs round-over-round.

```yaml
freight_market:
  rate_dynamics_model: demand_capacity_elastic
  baseline_capacity_abundance: normal
  fuel_index_baseline_usd_per_barrel: 80
  fuel_index_volatility_sigma: 0.12
  container_rate_volatility_sigma: 0.15
  demand_elasticity_coefficient: 1.3
  capacity_response_lag_rounds: 2              # Shipping capacity doesn't adjust instantly
```

---

## 7. Reference Scenario: Consumer Electronics (pilot)

globalstrat+ v1 ships with Consumer Electronics as the pilot SC-enabled scenario. CC-2 through CC-39 test against this scenario.

Consumer Electronics makes SC mechanics land because it has:
- Real single-source semiconductor dependencies (Taiwan).
- Real UFLPA exposure (rare earth refining, component assembly).
- Real CBAM adjacency (battery production).
- Real LC/Sinosure relevance (Chinese firms selling to BRI markets and developed markets).
- Real modal choice tension (air for premium launches vs. sea for volume).

Full scenario seed data is produced in a later CC bundle. For CC-1 acceptance, only a skeleton YAML demonstrating schema structure is required (see Section 9).

Other scenarios (Clean Energy Tech, Media/Entertainment, Industrial Manufacturing) receive SC schema coverage in later bundles. Media/Entertainment will receive a deliberately lighter treatment (fewer suppliers, fewer compliance regimes, SC layer effectively optional) because the SC surface for that industry is thin.

---

## 8. Validation Rules

The scenario loader (`manage.py load_scenario`) must enforce:

1. Every supplier's country exists as a declared origin in at least one `shipping_lane`.
2. Every market referenced in `suppliers.*.origin_trust_to_buyers` exists in `markets`.
3. Every `compliance_regime` referenced in `markets.*.compliance_regimes` exists in `compliance_regimes`.
4. Every specialization in `plants.*.upstream_suppliers_required` is resolvable (at least one supplier has that specialization).
5. Every trade finance instrument referenced in `suppliers.*.accepts_trade_finance` exists in `trade_finance_instruments`.
6. Every lane referenced in events exists in `shipping_lanes`.
7. Every critical input category has at least 2 suppliers (prevents single-point pedagogical failure).
8. `resilience_score_weights` sum to 1.0 (±0.01 tolerance).
9. Every `multi_source_substitutability.*.supplier_id` reference resolves to a declared supplier.

Validation failures halt scenario load with structured error messages identifying the failing field and section.

---

## 9. What This Spec Does NOT Cover

Out of scope for CC-1 (handled in subsequent specs):

| Concern | Spec |
|---|---|
| Decision page definitions and student-facing fields | **CC-2** (decision taxonomy) |
| Engine pipeline changes to consume the new schema | **CC-3** (engine logic) |
| Django model definitions (Supplier, ShippingLane, TradeInstrument, etc.) | **CC-4** (data model) |
| GlobalStrat fork audit (KEEP / ADAPT / NEW against every existing module) | **CC-5** (fork audit) |
| Pedagogical design note (progressive disclosure, home-market commitment, audience calibration) | **CC-6** (design note) |
| Consumer Electronics seed data with real values | Later build-pipeline CC |

---

## 10. Acceptance Criteria

CC-1 is complete when:

1. `/home/ubuntu/projects/globalstrat+/` exists with the forked GlobalStrat codebase, `.gitignore` in place, and a clean git repo initialized on `main`.
2. `specs/CC-01-scenario-schema.md` exists (this file).
3. `specs/STANDING-DISCIPLINE.md` exists and is referenced from this spec's header.
4. A new PostgreSQL database `globalstrat_plus` exists at 192.168.50.38 and the fork's settings point at it. `python manage.py dbshell -c "SELECT current_database();"` returns `globalstrat_plus`. Baseline GlobalStrat migrations have been applied cleanly. `python manage.py check` passes with zero issues.
5. A new Qdrant collection `globalstrat_plus_articles` exists at 192.168.50.186 with vector configuration matching GlobalStrat's existing collection. The fork's Qdrant client configuration points at the new collection.
6. A skeleton scenario YAML file at `scenarios/consumer_electronics_plus_skeleton.yaml` validates the schema structure. No production seed data required — each new section (`suppliers`, `shipping_lanes`, `trade_finance_instruments`, `compliance_regimes`, `resilience_parameters`, `freight_market`) has at least one example entry. Each EXTEND section shows at least one example of the new fields.
7. `git log` shows a clean, linear history for the CC-1 work (initial commit + DB repoint + Qdrant repoint + skeleton YAML commit, at minimum).
8. No code-level implementation of the new schema is required at this stage — schema definition, repo bootstrap, and infrastructure provisioning only.

**Report back to the user with:** `git log --oneline` output, directory tree (one level deep), `python manage.py showmigrations` output, `SELECT current_database();` confirmation, Qdrant `get_collections()` output, and the skeleton YAML file contents.
