# CC-19: Supply Chain Engine — Event Effects, Contingency Execution & Resilience Scoring

**Project:** globalstrat+
**Spec Type:** Build pipeline — engine (round processing)
**Depends on:** CC-3 (engine logic / Phase-1 pipeline), CC-4 (data model), CC-8 (seed data), CC-9 (decision API)
**Fulfils / refines sequence slots:** CC-19 (multi-round event handling + recovery-with-alternatives), the resilience-scoring *computation* that CC-21 surfaces, and coordinates with CC-18 (compliance enforcement) and CC-20 (FX lifecycle) as sibling Phase-1 SC steps.
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Drafted for builder execution

---

## Non-Negotiable Builder Discipline

Inherits `STANDING-DISCIPLINE.md`; the following are completion blockers:

1. Verify every existing field, model, table, endpoint, and payload shape against the running codebase/DB before referencing it. The SC decision models, state models, and `resilience_parameters` already exist (CC-4/CC-8) — read them; do not invent fields.
2. Do not invent model/field/endpoint names. If an expected name is absent, halt with a MISMATCH report.
3. This bundle **adds engine behaviour and may write to existing state models** (`SupplierState`, `LaneState`, `SCEventInstance`, `ResilienceScoreHistory`). It must not add new persistent decision models. New state fields require a migration and a MISMATCH-style note.
4. Round processing must be **deterministic** under a fixed seed (see §7). No wall-clock or unseeded randomness in Phase 1.
5. Self-verify with recorded command output + tests; closeout report under `specs/reports/cc-19/`.

---

## 1. Purpose

Today SC decisions are captured, read, and shown on the dashboard, but they do **not affect the simulation** — the dashboard honestly labels engine categories "Not yet." This bundle makes SC decisions *mechanically matter*:

- Disruption **events fire** each round and degrade the relevant suppliers/lanes.
- Each team's **contingency rules execute automatically** against those disruptions (activate a backup supplier, switch shipping mode), reducing the damage for teams that prepared.
- A **resilience score** is computed per team from their structural choices and written to `ResilienceScoreHistory`, so CC-21 can display it and CC-15/CC-23A stop showing "Not calculated yet."

This is the bundle that turns the GSCM layer from a set of forms into a simulation.

---

## 2. Structured Contingency Rules (the executable schema)

Free-text contingency plans are replaced by **structured, machine-executable rules** (frontend conversion is delivered alongside this spec on the Inventory page; the engine consumes the same JSON). The `ContingencyPlan` JSON fields carry:

### 2.1 `alt_supplier_activation_rules` — list of objects
```json
{
  "input_category": "semiconductor",     // critical input this rule protects
  "trigger": "disruption",               // "disruption" | "delay" | "capacity_drop"
  "threshold": 7,                          // delay: days; capacity_drop: %; ignored for "disruption"
  "backup_supplier_id": 30,               // supplier to shift volume to
  "shift_pct": 50                          // how much of the affected allocation to move (0–100)
}
```
Meaning: *if my primary supplier for `input_category` is disrupted / delayed beyond `threshold` days / loses more than `threshold`% capacity, move `shift_pct`% of that input's allocation to `backup_supplier_id`.*

### 2.2 `mode_switch_triggers` — list of objects
```json
{
  "lane_id": 22,                          // ShippingLane this rule protects
  "trigger": "lead_time_exceeds",         // "lead_time_exceeds" | "event"
  "threshold_days": 40,                    // for "lead_time_exceeds"
  "event_type": "red_sea",                // for "event": SC event key, or "any"
  "from_mode": "sea",                     // mode to move away from
  "to_mode": "air",                       // mode to move to (must be available on the lane)
  "shift_pct": 30                          // how much of the modal mix to move (0–100)
}
```
Meaning: *if `lane_id`'s effective sea lead time exceeds `threshold_days`, or a `event_type` disruption hits it, move `shift_pct`% of the mix from `from_mode` to `to_mode`.*

### 2.3 `disruption_response_playbook`
Retired as a free-text field (it executed nothing). The two structured rule lists above ARE the plan. The DB column may remain for backward compatibility but is no longer surfaced or required.

**Validation** (extend `ContingencyPlanWriteSerializer`): each rule validates shape, that referenced `backup_supplier_id`/`lane_id` exist in the scenario, that `to_mode` is available on the lane, `input_category` is a real specialization, and `shift_pct`/`threshold` are in range. Invalid rules → 400 with structured errors (consistent with CC-9).

---

## 3. Where It Runs (Phase-1 pipeline)

Add a bounded set of steps to the CC-3 Phase-1 sequence, after decisions are locked and before financials, in this order:

1. **Freight/market update** — roll `freight_market` fuel + container volatility (seeded) into per-lane base rates for the round.
2. **Event firing** — for each `category: supply_chain` event template, draw against `probability_per_round` (seeded); respect `earliest_round`, `max_occurrences`, `condition`. Create an `SCEventInstance`.
3. **Apply event effects to state:**
   - `SupplierState` for affected suppliers: `capacity_multiplier`, `quality_modifier`, `reliability_modifier`, `additional_lead_time_days`, `disruption_cost_multiplier`, `recovery_rounds_remaining`, `active_disruption_event` (per the event template's `capacity_reduction_pct`, `recovery_rounds`, `additional_lead_time_days`, `mode_rate_multiplier`).
   - `LaneState` for affected lanes: `active_disruption`, `current_rate_modifier`.
4. **Contingency execution (per team):** for each team with SC decisions this round, evaluate §2 rules against the round's `SupplierState`/`LaneState`. When a rule's trigger is met, apply its action to that team's *effective* sourcing/logistics for the round (shift allocation to backup supplier; shift modal mix). Record what fired (for narrative + audit) in the `SCEventInstance.resolution_data` or a per-team applied-actions structure.
5. **Multi-round recovery:** decrement `recovery_rounds_remaining`; teams with a triggered alternative recover faster per `resilience_parameters.recovery_rate_with_alternatives_multiplier`. Clear state when recovered.
6. **Resilience scoring** (§4) → `ResilienceScoreHistory`.
7. **Cost/impact feed:** the effective (post-contingency) sourcing/logistics + disruption cost multipliers feed the existing COGS/logistics cost steps so disruptions and good planning show up in financials.

Determinism: a single per-(game, round) seed drives all draws (§7).

---

## 4. Resilience Scoring

Compute a per-team score each round from `resilience_parameters.resilience_score_weights` (weights already sum to 1.0, CC-1 §8) over these components, each normalised 0–1:

| Component (weight key) | Signal |
|---|---|
| `multi_sourcing` | fraction of critical inputs with ≥2 suppliers / not exceeding `single_source_threshold_pct` |
| `geographic_diversity` | 1 − max single-country share vs `geographic_concentration_threshold_pct` |
| `buffer_inventory_adequacy` | buffer days vs `critical_component_buffer_days_recommended` |
| `modal_flexibility` | share of used lanes with >1 available mode configured |
| `tier_2_visibility` | `tier_2_3_visibility_investment` level (none/basic/comprehensive → 0/0.5/1) |
| `supplier_financial_health` | avg reliability/health of sourced suppliers, less active disruptions |

`score = Σ weight_k · component_k` (0–100 scale). Persist `score`, per-component `components`, and `weights_used` (effective, honouring CC-04-A1 per-class weight overrides) to `ResilienceScoreHistory(team, round)`. CC-15/CC-23A already read this endpoint and will flip from "Not calculated yet" to the real score.

---

## 5. Scope Boundaries

- **In:** SC event firing + effects, `SupplierState`/`LaneState` population, structured contingency execution + multi-round recovery, resilience scoring, feeding effective SC state into existing cost steps, `ContingencyPlanWriteSerializer` structured validation.
- **Adjacent (separate bundles, same Phase-1 SC step):** CC-18 compliance enforcement (detention/freeze), CC-20 FX hedge lifecycle (`HedgePosition` open→MTM→settle), CC-17 Phase-2 narratives for fired events.
- **Out:** new decision models; frontend resilience *display* (CC-21); instructor event-injection UI (CC-16).

---

## 6. Verification Before Editing

```bash
cd backend
python3 manage.py check
python3 manage.py shell <<'PY'
from django.apps import apps
for m in ['SupplierState','LaneState','SCEventInstance','ResilienceScoreHistory','ContingencyPlan']:
    M=apps.get_model('core',m); print(m, M._meta.db_table, [f.name for f in M._meta.get_fields()])
PY
grep -rn "def advance_round\|Phase 1\|_run_phase_1" core/engine/advance_round.py
```
Confirm the state models' fields match §3/§4 before writing. If a needed field is absent, halt with a MISMATCH report (a migration is a spec-authorised change, but the field list must be confirmed first).

---

## 7. Determinism

- One deterministic seed per (game, round) — e.g. `hash((game_id, round_number, scenario_id))` — seeds a local `random.Random`; all event draws and stochastic effects use it. No global `random`, no `Math.random`, no wall-clock in Phase 1.
- Re-running the same locked inputs for the same round must produce identical `SCEventInstance`, state, contingency outcomes, and resilience scores. A determinism test asserts this (two runs → identical fingerprint).

---

## 8. Tests

- Contingency execution: a team with a matching `alt_supplier_activation_rule` shifts allocation to its backup when the primary is disrupted; a team without the rule takes full impact. Same for `mode_switch_triggers`.
- Event effects: firing a Taiwan-earthquake event reduces affected `SupplierState.capacity_multiplier` and sets `recovery_rounds_remaining`; recovery decrements and clears; teams with alternatives recover faster.
- Resilience scoring: single-source everything → low `multi_sourcing`/`geographic_diversity` components; diversified → higher; weights honour a per-class override.
- Structured contingency validation: bad `backup_supplier_id`/`to_mode`/`shift_pct` → 400.
- Determinism: two seeded runs of a round produce identical outputs.
- `manage.py check` clean; focused module + full suite reported.

---

## 9. Acceptance Criteria

1. SC disruption events fire (seeded) and populate `SupplierState`/`LaneState`; effects respect duration/recovery.
2. Structured contingency rules execute per team and demonstrably reduce disruption impact vs. an unprotected team.
3. `ContingencyPlanWriteSerializer` validates the structured schema; free-text playbook no longer required.
4. `ResilienceScoreHistory` is written each round; the Dashboard/Supply Chain tab shows a real score (no longer "Not calculated yet").
5. Round advancement remains crash-free with SC data present (CC-22 path still passes).
6. Determinism check recorded for seeded runs.
7. `specs/reports/cc-19/acceptance_report.md` records pipeline placement, sample outcomes, and test output.

---

## 10. Non-Scope

No compliance detention (CC-18), no FX MTM (CC-20), no resilience-display/instructor-calibration UI (CC-21), no Phase-2 narrative generation (CC-17), no new scenarios. If the engine needs a state value not modelled, document the gap rather than faking it (per CC-23A §6).
