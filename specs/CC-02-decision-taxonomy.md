# CC-2: globalstrat+ Decision Taxonomy

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — decision taxonomy (every decision page, every field, every validation rule)
**Depends on:** `specs/CC-01-scenario-schema.md`
**Observes:** `specs/STANDING-DISCIPLINE.md`
**Status:** Ready for Claude Code execution

---

## 1. Purpose

This spec defines every decision page the student interacts with in globalstrat+, every field on every page, the validation rules that govern them, and the progressive disclosure schedule that stages their unlocking across rounds.

It is the contract between the scenario schema (CC-1) and the downstream data model (CC-4), engine logic (CC-3), and frontend specs (later CCs). Every subsequent spec references this document when it needs to know what students can see or set.

**Scope discipline:** CC-2 enumerates fields, types, validations, defaults, and progressive disclosure. It does NOT define Django models, serializers, API endpoints, or frontend components. Those are downstream concerns.

---

## 2. Preconditions — Verify Before Extend

Per STANDING-DISCIPLINE.md Section 1.2, before this spec can be acted on, Claude Code must produce a **field inventory report** for every GlobalStrat decision model that CC-2 proposes to EXTEND. This is the single most failure-prone transition in the build — prior projects have burned days on mismatched field names. We front-load the verification.

### 2.1 Field Inventory Report — with Ghost Model Detection

**Context from CC-1:** the CC-1 acceptance report flagged that `core/migrations/0001_initial.py` declares 50 models with `managed: False`, but only 10 were ever physically provisioned in the database. The remaining 40 are **ghost models** — present in Django's model registry but with no underlying table. Any spec that naively references a ghost model as if it were real will fail at runtime with `relation does not exist` errors. CC-2's field inventory must detect ghosts, not just enumerate fields.

Claude Code produces a report at `specs/reports/CC-02-field-inventory.md` containing two sections:

**Section A — Per-model field inventory (for every model that physically exists as a table):**

```
Model: <ModelName>
File: <path/to/models.py>
Managed: <True | False>
Physical table: <table_name> (verified present in DB)
Fields (from Django _meta.get_fields()):
  - <field_name>: <field_type> (<constraints>)
  - ...
Fields (from psql \d <table_name>):
  - <column_name>: <pg_type> (<constraints>)
  - ...
Field registry vs. DB delta: <any mismatches between the two lists>
Related models: <FK/M2M relationships>
```

Both the Django view and the psql view are reported side-by-side. Any delta between them (field present in Django but not in DB, or vice versa) is a flag for the spec author.

**Section B — Ghost model roster:**

```
Ghost models (declared in Django but no physical table):
  - <ModelName> (<file:line>)
  - ...
Total ghosts: <N>
```

**Command sequence:**

```bash
cd /home/ubuntu/projects/globalstrat+/

# Step 1: Enumerate all Django-registered models
python manage.py shell <<'PY'
from django.apps import apps
for m in apps.get_models():
    print(f"{m._meta.label}\t{m._meta.db_table}\t{m._meta.managed}")
PY
# Capture output as the Django-registered set.

# Step 2: Enumerate all physical tables in the database
python manage.py dbshell -c "\dt" > /tmp/physical_tables.txt
# Or equivalently:
python manage.py dbshell -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

# Step 3: Compute the ghost set
# Ghost = in Django-registered set AND NOT in physical tables set
# Present this as the ghost roster in Section B of the report.

# Step 4: For every non-ghost model matching the required coverage list,
# produce the Section A entry — Django _meta view AND psql \d view, side-by-side.
python manage.py shell
>>> from <app>.models import <Model>
>>> for f in <Model>._meta.get_fields():
...     print(f.name, type(f).__name__, getattr(f, 'max_length', ''), getattr(f, 'null', ''))

python manage.py dbshell
\d+ <table_name>
```

**Required coverage for Section A:** every `Decision*` model, plus `DecisionPlant`, `ESG*` models, `MarketEntryDecision`, `MarketingMix*`, `Financing*`, `Communications*`, `OrgStructure*`, `TaxStructure*`, `Alliance*`, `GovernmentRelations*`, `MandA*`/`Acquisition*`, `Product*` — **if they physically exist as tables**. Ghost instances of any of these go into Section B instead.

### 2.2 Mismatch and Ghost Handling

Claude Code halts with a MISMATCH report per STANDING-DISCIPLINE.md Section 3 under any of the following conditions:

1. **Field name mismatch:** a field named in this spec's EXTEND sections (Section 5) does not match what exists in the codebase for that model.
2. **Field collision:** a field this spec proposes to add in EXTEND would collide with an existing field on the target model.
3. **Ghost EXTEND target:** a model that CC-2 proposes to EXTEND (specifically `DecisionPlant` in §5.1 and the ESG model(s) in §5.2) turns out to be a ghost — registered in Django but with no physical table. This is an explicit halt condition because the entire EXTEND premise collapses if the base model has no database reality.
4. **Field registry vs. DB delta:** a model has fields visible in Django's `_meta.get_fields()` that do not exist in the database (or vice versa). This indicates schema drift that needs human resolution before CC-2 proceeds.

In every halt case, Claude Code does NOT attempt to resolve the issue — not by creating a new model, not by running unreviewed migrations, not by assuming the intent. The spec author resolves the name, promotes the ghost to a managed model via a dedicated migration, or re-scopes the EXTEND target.

### 2.3 Commit the Inventory

The field inventory report is committed to the repo:

```bash
git checkout -b cc-02-decision-taxonomy
git add specs/reports/CC-02-field-inventory.md
git commit -m "CC-2: field inventory report for GlobalStrat decision models"
```

Only after the inventory is complete and clean does CC-2 proceed.

---

## 3. Classification Framework

Every decision page is classified as:

- **INHERIT** — identical to GlobalStrat; no changes to fields, validation, or display logic
- **EXTEND** — GlobalStrat page plus additive globalstrat+ fields (existing fields and behaviors retained)
- **NEW** — no GlobalStrat equivalent

Per the minimum-necessary-change principle established in the design conversation, most GlobalStrat pages INHERIT. globalstrat+'s character comes from what we add, not what we rip out.

---

## 4. INHERIT Pages

The following GlobalStrat decision pages transfer unchanged. Claude Code does NOT modify them in CC-2 or subsequent CCs unless a specific spec authorizes it:

| Page | Notes |
|---|---|
| R&D / Platform Investment | Feature investment, Gen 1→2→3 progression, research prioritization |
| Products | Product configuration (platform + feature bundle per product) |
| Marketing Mix | Per product × market: price, promotion, placement, production volume |
| Market Entry | Entry mode, timing, localization investment per market |
| Financing | Debt/equity mix, dividend policy, working capital facilities |
| Communications | Corporate communications, investor relations, media strategy |
| Organization Structure | Org design, headcount allocation, reporting hierarchy |
| Tax Structure | Transfer pricing, jurisdictional allocation, holding structure |
| Alliances | Strategic alliance selection and partner engagement |
| Government Relations | Government affairs, lobbying, subsidy applications |
| M&A / Acquisitions | Acquisition target selection and deal structuring |

These pages retain their existing fields, validation, and progressive disclosure from GlobalStrat. A Chinese executive team navigating globalstrat+ sees the same options here as a master's student navigating GlobalStrat — the distinctiveness of globalstrat+ lives in the EXTEND and NEW pages below.

---

## 5. EXTEND Pages

Each EXTEND page adds fields to an existing GlobalStrat page. Existing fields and behaviors are preserved.

### 5.1 Plants / Production Capacity (EXTEND)

**Existing role:** GlobalStrat treats plants as owned manufacturing capacity with location, unit cost, quality profile, and capacity constraints.

**globalstrat+ role:** plants become one type of sourcing node within a broader supply chain architecture. Plants don't go away; they're now integrated with the upstream supplier layer.

**Verification before extending** (STANDING-DISCIPLINE §1.2): confirm the current field list on `DecisionPlant` matches what the field inventory report shows. Proceed only if no name collisions with the new fields below.

**New fields:**

| Field | Type | Values / Constraint | Purpose |
|---|---|---|---|
| `sourcing_node_role` | choice | `owned_manufacturing` \| `contract_manufacturing` \| `pure_assembly` | Declares how this plant functions in the SC architecture |
| `upstream_suppliers_required` | computed (read-only) | list of specialization strings | Derived from product BOM; shown to student, not editable |
| `scope_1_co2_per_unit_kg` | computed (read-only) | float ≥ 0 | From scenario YAML plant data; displayed for CBAM context |
| `scope_2_co2_per_unit_kg` | computed (read-only) | float ≥ 0 | From scenario YAML plant data |
| `reverse_logistics_enabled` | boolean | default: false | Whether this plant accepts returned products |

**Validation:**
- `sourcing_node_role` must be one of the three declared values.
- `upstream_suppliers_required` is computed by the engine, not student-input.

**Progressive disclosure:**
- Round 1+: `sourcing_node_role` visible and editable.
- `upstream_suppliers_required` display unlocks at Round 2 (when students begin actively managing sourcing).
- Scope emissions visibility unlocks at Round 5 (when CBAM begins phasing in per scenario).
- `reverse_logistics_enabled` unlocks at Round 5.

### 5.2 ESG (EXTEND)

**Existing role:** GlobalStrat's ESG page captures environmental, social, and governance commitments that feed stakeholder perception and regulatory standing.

**globalstrat+ role:** ESG becomes the entry point for supplier-side ESG (audits, Scope 3, CBAM readiness, UFLPA compliance investment) in addition to corporate ESG.

**Verification before extending:** confirm ESG model field inventory before adding the new fields.

**New fields:**

| Field | Type | Values / Constraint | Purpose |
|---|---|---|---|
| `supplier_audit_program` | choice | `none` \| `basic` \| `comprehensive` | Tier of supplier auditing; unlocks tier-2 visibility |
| `scope_3_emissions_tracking` | boolean | default: false | Whether team invests in Scope 3 reporting infrastructure |
| `scope_3_investment_usd` | integer | ≥ 0, required if `scope_3_emissions_tracking = true` | Investment level in Scope 3 tracking |
| `cbam_reporting_readiness` | boolean | default: false | Whether team has invested in CBAM reporting capability |
| `uflpa_tier_mapping_investment` | choice | `none` \| `partial` \| `full` | Tier-2 supplier mapping for UFLPA compliance |

**Validation:**
- `supplier_audit_program` options and their unlocked capabilities come from the scenario YAML `esg.supplier_audit_program.investment_tiers` (CC-1 §5.3).
- `scope_3_investment_usd` must meet the minimum declared in the scenario YAML if tracking is enabled.
- `uflpa_tier_mapping_investment = full` is required before Round 5 for teams selling to US markets with Xinjiang-adjacent tier-2 exposure; otherwise the team accumulates UFLPA enforcement risk.

**Progressive disclosure:**
- Rounds 1–3: existing GlobalStrat ESG fields only.
- Round 4: `supplier_audit_program` and `scope_3_emissions_tracking` unlock.
- Round 5: `cbam_reporting_readiness` and `uflpa_tier_mapping_investment` unlock (aligning with CBAM 50% phase-in and UFLPA enforcement threshold).

---

## 6. NEW Pages

Four new decision pages. Each has a Purpose, a Fields table, a Validation section, and a Progressive Disclosure schedule.

### 6.1 Sourcing & Suppliers (NEW)

**Purpose:** Students select suppliers for each critical input category, allocate volume across them, and invest in supplier visibility and auditing.

**Page structure:**

The page is organized by **critical input category** (e.g., semiconductors, displays, batteries, casings — derived from the scenario YAML `features` and product BOM). For each category, students see a supplier allocation table.

**Fields — per critical input category:**

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `supplier_id` | FK to Supplier | must have matching `specialization` | Which supplier is sourced from |
| `allocation_pct` | integer | 0–100, sum across category = 100 | Volume percentage from this supplier |
| `volume_commitment_units` | integer | ≥ 0 | For triggering volume discount tiers |
| `payment_terms` | choice | from supplier's `accepts_trade_finance` | Procurement payment instrument |

Students can add or remove supplier rows (up to a scenario-configured max, default 5 per category).

**Fields — page-level:**

| Field | Type | Values | Purpose |
|---|---|---|---|
| `tier_2_3_visibility_investment` | choice | `none` \| `basic` \| `comprehensive` | Separate from supplier audit program — focuses on visibility without full audit |
| `multi_sourcing_strategy` | choice | `single_source` \| `primary_backup` \| `balanced_split` \| `geographic_diversity` | Declarative positioning that affects resilience scoring |

**Validation:**
- Allocation percentages sum to exactly 100 per category (rounded to whole percents).
- At least one supplier allocated per critical input category (no unserved category).
- Selected supplier's `specialization` must include the category.
- Selected supplier's `payment_terms` must be in the supplier's `accepts_trade_finance` list.
- `multi_sourcing_strategy = single_source` fires a validation warning (not error) when concentration > `single_source_threshold_pct` in the scenario's `resilience_parameters`.
- Geographic concentration warning surfaced when any country > `geographic_concentration_threshold_pct`.

**Progressive disclosure:**

- **Round 1–2:** one supplier per category, pre-assigned by scenario default. Allocation field hidden (implicit 100%). Students see who their suppliers are but cannot change them yet. Payment terms hidden (default to LC).
- **Round 3:** multi-supplier allocation unlocks. Students can add suppliers, set allocation percentages, and declare `multi_sourcing_strategy`. `payment_terms` still hidden.
- **Round 4:** `payment_terms` unlocks (coordinates with Trade Finance & FX page unlock).
- **Round 5:** `tier_2_3_visibility_investment` unlocks. Volume commitment fields unlock.

### 6.2 Logistics & Distribution (NEW)

**Purpose:** Students set modal mix per shipping lane, choose Incoterms per destination market, select customs classification (where applicable), and allocate reverse logistics capacity.

**Page structure:**

Three sections: **Modal Mix** (by lane), **Incoterms** (by destination market), and **Customs & Reverse Logistics**.

**Fields — Modal Mix (per active lane):**

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `mode_sea_pct` | integer | 0–100, only if lane.modes.sea.available | Volume routed by sea on this lane |
| `mode_air_pct` | integer | 0–100, only if lane.modes.air.available | Volume routed by air on this lane |
| `mode_rail_pct` | integer | 0–100, only if lane.modes.rail.available | Volume routed by rail on this lane |
| `mode_road_pct` | integer | 0–100, only if lane.modes.road.available | Volume routed by road on this lane |
| `volume_commitment_teu` | integer | optional, ≥ 0 | For rate locking with carriers |

Active lanes are derived from the team's supplier origins × destination markets.

**Fields — Incoterms (per destination market):**

| Field | Type | Values | Purpose |
|---|---|---|---|
| `incoterms` | choice | `EXW` \| `FCA` \| `FOB` \| `CFR` \| `CIF` \| `CPT` \| `CIP` \| `DAP` \| `DPU` \| `DDP` | Incoterms 2020 term governing the transaction |
| `insurance_coverage_pct` | integer | 0–110 | Insurance coverage level; default 110% under CIF/CIP per industry norm |

**Fields — Customs & Reverse Logistics (home-country-gated):**

| Field | Type | Values | Visibility |
|---|---|---|---|
| `customs_classification` | choice | `processing_trade` \| `general_trade` \| `bonded_logistics` | Visible only for teams with Chinese home country |
| `reverse_logistics_capacity_pct` | integer | 0–30 | Per destination market |
| `reverse_logistics_hub_market` | FK to Market | optional | Which market serves as the reverse logistics consolidation hub |

**Validation:**
- Per lane: sum of `mode_*_pct` across available modes = 100.
- Only available modes (`lane.modes.*.available = true`) can carry non-zero volume.
- Incoterms: exactly one per destination market.
- `customs_classification` visible and validated only for Chinese home teams; other teams do not see the field.
- `reverse_logistics_capacity_pct` cannot exceed 30% per market (business-reasonable ceiling).

**Progressive disclosure:**

- **Round 1–2:** sensible default per lane (sea-dominant for long-haul, road for short-haul, air only for declared-premium products), hidden from student. Incoterms default to CIF (standard Chinese exporter baseline). Customs classification defaults to `general_trade`.
- **Round 3:** Modal Mix section fully unlocks. Students can redistribute modes per lane.
- **Round 4:** Incoterms section unlocks. Students can set terms per market.
- **Round 5:** Customs classification unlocks (Chinese home teams). Reverse logistics capacity unlocks.

### 6.3 Trade Finance & FX (NEW)

**Purpose:** Students select payment terms for buyer relationships, enroll in Sinosure coverage (where applicable), and hedge FX exposure.

**Page structure:**

Three sections: **Buyer Payment Terms**, **Sinosure Coverage**, **FX Hedging**.

**Fields — Buyer Payment Terms (per segment × market):**

| Field | Type | Values | Purpose |
|---|---|---|---|
| `buyer_payment_instrument` | choice | `letter_of_credit` \| `documentary_collection` \| `open_account` | Revenue-side payment mechanism |
| `lc_doc_prep_investment` | choice | `minimal` \| `standard` \| `diligent` | Only shown when instrument = LC; affects rejection probability |

Segments × markets are derived from the scenario's customer segment taxonomy.

**Fields — Sinosure Coverage (home-country-gated to CN):**

| Field | Type | Constraint | Visibility |
|---|---|---|---|
| `sinosure_enrolled_markets` | multi-select | subset of destination markets | Visible only for Chinese home teams |
| `sinosure_coverage_pct_per_market` | integer (per enrolled market) | 0 to instrument's `coverage_ceiling_pct` | Percentage of receivables insured |

**Fields — FX Hedging (per foreign currency exposure stream):**

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `hedge_ratio` | integer | 0–100 | Percentage of exposure hedged |
| `tenor_days` | choice | from instrument's `tenor_options_days` | Forward contract tenor |

Foreign currency exposure streams are derived from the team's cross-border receivables (each destination market with a non-home-currency transaction generates one exposure stream).

**Validation:**
- `buyer_payment_instrument` must be in the target market's `trade_finance_instruments` availability list.
- `lc_doc_prep_investment` shown only when instrument = LC.
- `sinosure_enrolled_markets` visible only for Chinese home teams.
- `sinosure_coverage_pct_per_market` ≤ Sinosure instrument's `coverage_ceiling_pct` (typically 90%).
- `hedge_ratio` in [0, 100]. `tenor_days` must be a valid option for the currency pair.

**Progressive disclosure:**

- **Round 1–3:** all fields hidden. Defaults: LC for all buyers (with `lc_doc_prep_investment = standard`), no Sinosure, no FX hedging.
- **Round 4:** Buyer Payment Terms section unlocks fully. Sinosure Coverage unlocks for Chinese home teams.
- **Round 5:** FX Hedging unlocks.

### 6.4 Inventory & Resilience (NEW)

**Purpose:** Students set buffer inventory policy per critical SKU-market combination, declare resilience strategy, and set contingency plan triggers.

**Page structure:**

Two sections: **Buffer Inventory Policy** (per critical SKU × market) and **Contingency Plans**.

**Fields — Buffer Inventory (per critical SKU × market):**

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `buffer_days` | integer | 0–90 | Safety stock in days of expected demand |
| `safety_stock_trigger_pct` | integer | 0–50 | Reorder trigger as percentage of expected demand |

Critical SKU-market combinations are the cross-product of team's active products and served markets.

**Fields — Contingency Plans:**

| Field | Type | Purpose |
|---|---|---|
| `disruption_response_playbook` | narrative (max 500 chars) | Team's stated resilience strategy; evaluated qualitatively |
| `alt_supplier_activation_rules` | structured list | Rules of form "if supplier X capacity < Y%, activate supplier Z" |
| `mode_switch_triggers` | structured list | Rules of form "if sea lane L disrupted, shift up to N% to air" |

**Validation:**
- `buffer_days` 0–90 per SKU-market.
- `safety_stock_trigger_pct` ≤ 50.
- Contingency rules reference existing suppliers and lanes in the scenario.
- `alt_supplier_activation_rules` target suppliers must have overlapping `specialization` with primary supplier.

**Progressive disclosure:**

- **Rounds 1–2:** buffer default of 30 days per SKU-market, hidden from student. Contingency plans hidden.
- **Round 3:** Buffer Inventory section unlocks.
- **Round 5:** Contingency Plans section unlocks (timed to when disruption events start firing in the event catalog).

---

## 7. Supply Chain Dashboard (non-decision page)

A read-only landing page that summarizes the team's supply chain posture. Not itself a decision page, but referenced here so CC-4 and downstream frontend specs know it exists.

**Content:**
- Resilience score (computed per CC-3 engine logic) with component breakdown
- Single-source exposure flags per critical input category
- Geographic concentration heatmap
- Supplier health summary (from supplier `reliability_rating` and event state)
- Current round's SC event log
- Links to each SC decision page (Sourcing, Logistics, Trade Finance, Inventory)

No student input fields. Purely informational.

**Unlock:** visible from Round 2 onward (once students start engaging with sourcing decisions).

---

## 8. Progressive Disclosure Schedule — Consolidated

| Round | Unlocks |
|---|---|
| 1 | Default SC configuration applied (invisible to student). All standard GlobalStrat decisions available. `sourcing_node_role` on Plants page visible. |
| 2 | Supply Chain Dashboard visible (read-only posture view). `upstream_suppliers_required` display on Plants page. |
| 3 | Sourcing & Suppliers page: multi-supplier allocation, `multi_sourcing_strategy`. Logistics & Distribution: Modal Mix section. Inventory & Resilience: Buffer Inventory section. |
| 4 | Sourcing: `payment_terms` field. Logistics: Incoterms section. Trade Finance & FX: Buyer Payment Terms section, Sinosure Coverage (CN home teams). ESG EXTEND: supplier audit program, Scope 3. |
| 5 | Sourcing: `tier_2_3_visibility_investment`, volume commitments. Logistics: Customs classification (CN teams), Reverse logistics. Trade Finance & FX: FX Hedging. Inventory: Contingency Plans. ESG EXTEND: CBAM readiness, UFLPA tier mapping. Plants EXTEND: Scope emissions visibility, reverse logistics toggle. |
| 6+ | No new unlocks; teams operate the full decision surface. |

The rationale for the schedule: students earn complexity by surviving the early rounds. Compliance and trade-finance depth unlock at Round 4–5 when the corresponding events start firing (UFLPA enforcement, CBAM phase-in, LC rejection events), so the mechanic arrives *with* the reason to care about it.

---

## 9. Cross-Page Validation Rules

Validation rules that span multiple decision pages. These run after a round's decisions are submitted, before advancement.

1. **Supplier-payment consistency:** `buyer_payment_instrument` selected on Trade Finance page must be available in the destination market's `trade_finance_instruments`. `payment_terms` on Sourcing page must be in supplier's `accepts_trade_finance`.
2. **Lane-supplier consistency:** every active lane on Logistics page must have at least one supplier shipping on it (lane origin must match at least one selected supplier's country).
3. **UFLPA gating:** if team has `xinjiang_adjacent` tier-2 exposure > threshold AND sells to US markets AND does not have `uflpa_tier_mapping_investment = full` by Round 5, a UFLPA risk warning is surfaced (not a hard block — it becomes an event trigger).
4. **Sinosure coverage ceiling:** `sinosure_coverage_pct_per_market` ≤ the Sinosure instrument's `coverage_ceiling_pct`.
5. **FX hedge consistency:** hedge tenors selected must match available tenors on the currency pair.
6. **Budget totals:** total investments across ESG EXTEND (supplier audit + Scope 3 + CBAM readiness + UFLPA mapping), Sourcing (tier-2/3 visibility), and Logistics (reverse logistics capacity) must not exceed the team's working capital allocation for SC investments (capped at a scenario-configured percentage of revenue).

Cross-page validation runs server-side during round submission and returns structured error payloads that the frontend can surface against the correct page.

---

## 10. Default Values for Unlocked-Later Fields

When a field is not yet unlocked, it receives a default. Defaults are chosen to be sensible-but-suboptimal — the student isn't penalized for locked fields, but they're not optimized either.

| Field | Default while locked |
|---|---|
| Sourcing `allocation_pct` | 100% to the pre-assigned default supplier |
| Sourcing `payment_terms` | `letter_of_credit` |
| Sourcing `multi_sourcing_strategy` | `single_source` |
| Logistics `mode_*_pct` | 100% to default mode (sea for long-haul, road for short-haul, air for declared-premium products) |
| Logistics `incoterms` | `CIF` (standard Chinese exporter baseline) |
| Logistics `customs_classification` (CN) | `general_trade` |
| Logistics `reverse_logistics_capacity_pct` | 0 |
| Trade Finance `buyer_payment_instrument` | `letter_of_credit` |
| Trade Finance `lc_doc_prep_investment` | `standard` |
| Trade Finance `sinosure_enrolled_markets` | empty list |
| Trade Finance `hedge_ratio` | 0 |
| Inventory `buffer_days` | 30 |
| Inventory `safety_stock_trigger_pct` | 20 |
| ESG EXTEND `supplier_audit_program` | `none` |
| ESG EXTEND `uflpa_tier_mapping_investment` | `none` |
| Plants EXTEND `sourcing_node_role` | `owned_manufacturing` (matches pre-globalstrat+ behavior) |
| Plants EXTEND `reverse_logistics_enabled` | `false` |

Defaults are specified here so CC-3 (engine) and CC-4 (data model) know what values to seed and compute against.

---

## 11. Language Support

globalstrat+ inherits GlobalStrat's EN/ZH i18n. All new field labels, help text, validation messages, and progressive disclosure tooltips must be declared in both languages. Language keys follow the GlobalStrat convention (verify the exact key pattern via STANDING-DISCIPLINE §1.5 before adding new keys).

CC-2's acceptance does not require the translations to be written — that's a later content task. CC-2 requires the translation key placeholders to be defined so CC-4 and frontend specs know what keys to expect.

---

## 12. What This Spec Does NOT Cover

| Concern | Spec |
|---|---|
| Django model definitions for new decision pages | **CC-4** (data model) |
| API endpoints serving each decision page | **CC-4** |
| Engine logic consuming decision values | **CC-3** |
| Frontend component rendering | Later frontend CC |
| Translation content (EN/ZH actual strings) | Later content CC |
| Instructor panel extensions for SC decision viewing/injection | **CC-5** (fork audit) and later instructor panel CC |
| Seed data for Consumer Electronics scenario | Later build-pipeline CC |

---

## 13. Acceptance Criteria

CC-2 is complete when:

1. Claude Code has produced the field inventory report at `specs/reports/CC-02-field-inventory.md` with both Section A (per-model field inventory for physically-existing tables) and Section B (ghost model roster). Section A covers every Decision* model, DecisionPlant, ESG models, and the other existing GlobalStrat decision models enumerated in Section 2.1 — to the extent they physically exist. Section B lists every model registered in Django but absent from the database.
2. The EXTEND targets in Section 5 (`DecisionPlant` and the ESG model(s)) are explicitly confirmed as non-ghosts. If either appears in Section B, CC-2 halts with a MISMATCH report.
3. No MISMATCH halts remain unresolved. If the inventory turned up field collisions or schema-drift deltas, the spec author has either renamed the colliding CC-2 fields, authorized the collision explicitly, or resolved the drift — documented in `specs/reports/CC-02-collisions-resolved.md`.
4. `specs/CC-02-decision-taxonomy.md` exists (this file).
5. Branch `cc-02-decision-taxonomy` contains the field inventory report commit and is merged to `main` after verification.
6. No code-level implementation of the new or extended decision pages is required at this stage — taxonomy definition and field inventory only.

**Report back to the user with:** the field inventory report contents (both sections), explicit confirmation that EXTEND targets are non-ghosts, any detected name collisions or schema-drift deltas, `git log --oneline` for the branch, and explicit confirmation that no Django models, migrations, or frontend code was written during CC-2.

---

## 14. Open Questions for CC-6 (design note)

Flagged here so they don't get lost; resolved in CC-6:

- **Home market commitment:** Is globalstrat+ China-home-only, or multi-home with Chinese-specific instruments conditionally displayed? (Affects UI complexity and scenario seed coverage.)
- **Cognitive load sanity check:** does the progressive disclosure schedule land at the right pace for a 10-round semester delivered to Chinese executives with work experience? Early field testing in CC-6 may adjust specific unlock rounds.
- **Instructor override:** should instructors be able to alter the progressive disclosure schedule per class (e.g., unlock Trade Finance at Round 3 for a finance-heavy cohort)? This is a CC-5 / instructor panel concern but the schema needs to accommodate either outcome.
