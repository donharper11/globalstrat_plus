# CC-04 Data Model — Acceptance Report

**Date:** 2026-04-17
**Branch:** `cc-04-data-model`
**Spec:** `specs/CC-04-data-model.md`

---

## 1. Reference Inventory (§11 criterion 1) ✅

`specs/reports/CC-04-reference-inventory.md` exists with all three sections:
- **Section A:** FK target verification — all FK targets (Team, Round, Scenario, MarketDefinition, SegmentDefinition, TeamProduct, EventTemplateDefinition) confirmed as non-ghost managed models.
- **Section B:** App layout — single `core` app, models split across `sc_models.py`, `sc_decisions.py`, `sc_state.py`.
- **Section C:** DRF conventions — read/write serializer split, existing permission classes reused.

No unresolved halts.

---

## 2. Migrations (§11 criterion 2) ✅

Two migrations created and applied:
- `0041_sc_scenario_content` — Creates all 21 new SC model tables (6 scenario-content, 10 team-decision, 5 engine-state) with indexes and unique_together constraints.
- `0042_decision_plant_sc_extensions` — Adds 5 EXTEND fields to DecisionPlant and 5 to DecisionESG.

`showmigrations` output (relevant tail):
```
 [X] 0040_cc35_promote_teamnotification
 [X] 0041_sc_scenario_content
 [X] 0042_decision_plant_sc_extensions
```

All 42 core migrations applied cleanly.

---

## 3. ORM Queryable (§11 criterion 3) ✅

All new models queryable via ORM without exceptions. Empty results as expected (no seed data in current CE scenario).

---

## 4. Endpoint Response Samples (§11 criterion 4) ✅

### §7.2 — Scenario Content (GET-only, no auth required)
| Endpoint | Status | Response |
|---|---|---|
| `GET /api/scenarios/2/suppliers/` | 200 | `[]` |
| `GET /api/scenarios/2/lanes/` | 200 | `[]` |
| `GET /api/scenarios/2/trade-finance-instruments/` | 200 | `[]` |
| `GET /api/scenarios/2/compliance-regimes/` | 200 | `[]` |

### §7.1 — Decision Endpoints (POST → 201, GET → 200)

**Sourcing POST → 201:**
```json
// POST /api/games/7/teams/4/sc/round/1/sourcing/
// Request: {"tier_2_3_visibility_investment":"basic","multi_sourcing_strategy":"dual_source","allocations":[]}
// Response:
{"id":1,"allocations":[],"tier_2_3_visibility_investment":"basic","multi_sourcing_strategy":"dual_source","team":4,"round":1}
```

**Sourcing GET → 200:**
```json
{"decision":{"id":1,"allocations":[],"tier_2_3_visibility_investment":"basic","multi_sourcing_strategy":"dual_source","team":4,"round":1},"allocations":[]}
```

**Logistics POST → 201:**
```json
// POST with empty lists: {"logistics":[],"incoterms":[],"customs":[]}
{"status":"ok"}
```

**Trade Finance POST → 201 (with FX hedge):**
```json
// POST: {"trade_finance":[],"sinosure":[],"fx_hedges":[{"currency_pair":"USDCNY","hedge_ratio":50,"tenor_days":90}]}
{"status":"ok"}
```

**Trade Finance GET → 200 (confirms persistence):**
```json
{"trade_finance":[],"sinosure":[],"fx_hedges":[{"id":1,"currency_pair":"USDCNY","hedge_ratio":50,"tenor_days":90,"team":4,"round":1}]}
```

**Inventory POST → 201 (with contingency plan):**
```json
// POST: {"inventory":[],"contingency":{"disruption_response_playbook":"Switch to alt supplier within 48h","alt_supplier_activation_rules":["rule1","rule2"],"mode_switch_triggers":["port_closure"]}}
{"status":"ok"}
```

**Inventory GET → 200 (confirms persistence):**
```json
{"inventory":[],"contingency":{"id":1,"disruption_response_playbook":"Switch to alt supplier within 48h","alt_supplier_activation_rules":["rule1","rule2"],"mode_switch_triggers":["port_closure"],"team":4,"round":1}}
```

### §7.3 — State Retrieval (GET-only)
| Endpoint | Status | Response |
|---|---|---|
| `GET .../sc/round/1/resilience-score/` | 200 | `{"score":null,"components":{},"weights_used":{}}` |
| `GET .../sc/hedge-positions/` | 200 | `[]` |
| `GET .../sc/round/1/sc-events/` | 200 | `[]` |

### Failure case (round not open):
POST to any decision endpoint with round `status != 'open'` returns **403** with:
```json
{"detail":"Authentication credentials were not provided."}
```
(DRF default message when permission denied and no authenticated user — `IsRoundOpen` rejects unsafe methods on non-open rounds.)

---

## 5. load_scenario (§11 criterion 5) ✅

`load_scenario --flush` runs successfully with SC extension active:
```
  ShippingLane: 0
  Supplier: 0
  TradeFinanceInstrument: 0
  TOTAL RECORDS: 2066
  Scenario ID: 3
```

SC sections are handled gracefully when absent from YAML (zero rows, no errors). The `_flush()` method includes SC table names for cleanup. Re-loading is idempotent.

**Note:** The CC-1 skeleton YAML (`consumer_electronics_plus_skeleton.yaml`) has format mismatches with the loader (uses `metadata:` instead of `scenario:` and lacks `features:`). Tested with the real CE scenario (`consumer_electronics_2026.yaml`) instead, which is the production scenario file. SC seed data will be added in CC-8.

---

## 6. EXTEND Fields (§11 criterion 6) ✅

Verified via `psql \d`:

**decision_plant** — 5 new fields:
- `sourcing_node_role` (varchar(30))
- `upstream_suppliers_required` (jsonb)
- `scope_1_co2_per_unit_kg` (numeric(7,3))
- `scope_2_co2_per_unit_kg` (numeric(7,3))
- `reverse_logistics_enabled` (boolean)

**decision_esg** — 5 new fields:
- `supplier_audit_program` (varchar(20))
- `scope_3_emissions_tracking` (boolean)
- `scope_3_investment_usd` (integer)
- `cbam_reporting_readiness` (boolean)
- `uflpa_tier_mapping_investment` (varchar(20))

All existing fields preserved (CC-2 field inventory baseline intact).

---

## 7. Branch Status (§11 criterion 7)

Branch `cc-04-data-model` contains 6 commits:
1. Reference inventory report
2. 21 SC models + migration 0041
3. EXTEND DecisionPlant/DecisionESG + migration 0042
4. DRF serializers
5. API endpoints + URL routing
6. load_scenario extension

**Pending:** Merge to `main` with `--no-ff`.

---

## 8. No Engine Logic (§11 criterion 8) ✅

Confirmed. Engine state models (`SupplierState`, `LaneState`, `SCEventInstance`, `HedgePosition`, `ResilienceScoreHistory`) exist as empty shells. No simulation logic, no round-advance processing, no score calculation code was written. That work belongs to CC-3/CC-6.

---

## 9. No Frontend Code (§11 criterion 9) ✅

Confirmed. No React components, no TypeScript files, no frontend changes of any kind were made. Endpoints exist and respond via DRF; frontend integration is CC-10 through CC-15.

---

## Deviations from Spec

1. **Migration numbering:** Spec planned 0040–0048 (9 migrations). Actual: 0041–0042 (2 migrations). Django auto-grouped all 21 new model creates into one migration (0041), and all EXTEND fields into another (0042). The event category extension (spec's 0041) was eliminated — `EventTemplateDefinition` already has a `category` CharField.

2. **API prefix:** Spec assumed `/api/v1/`. Actual codebase uses `/api/`. All endpoints adapted accordingly.

3. **URL structure:** Decision endpoints use `sc/round/<round_number>/` (matching existing codebase convention for `decisions/round/<round_number>/`), not `rounds/<round_number>/sc/`.

4. **Skeleton YAML not testable:** The CC-1 skeleton YAML has structural mismatches with the loader. Tested with the production CE scenario instead.
