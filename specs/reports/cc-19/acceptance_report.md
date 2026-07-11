# CC-19 Acceptance Report — Supply-Chain Engine (Events · Contingency · Resilience)

**Spec:** `specs/CC-19-sc-engine-event-contingency-resilience.md`
**Branch:** `main` (commit `e200308`)
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — engine fires, structured contingency executes, resilience scored; verified live on the running deployment.

---

## 1. Verify-Before-Wire (STANDING-DISCIPLINE §1)

Verified against the **actual models / loader / decision serializers** (the authoritative contract), not spec prose:

- `python3 manage.py check` → *System check identified no issues (0 silenced).*
- SC state models confirmed: `SupplierState`, `LaneState`, `SCEventInstance`, `ResilienceScoreHistory` (fields, decimal precisions, FK targets — e.g. `SupplierState.active_disruption_event` is an FK to `SCEventInstance`, so disruption effects set it to `None`; `ResilienceScoreHistory.score` is `Decimal(5,3)` → engine clamps to 99.999).
- Decision models confirmed: `SourcingAllocation` (`critical_input_category`, `supplier`, `allocation_pct`), `SourcingDecision.tier_2_3_visibility_investment`, `LogisticsDecision.mode_*_pct`, `InventoryDecision.buffer_days`, `ContingencyPlan.alt_supplier_activation_rules` / `mode_switch_triggers` (structured JSON, from the earlier structured-rules conversion).
- **Ghost-field found and closed:** `EventTemplateDefinition` had **no** field to carry SC event effect parameters — the loader silently dropped `affected_suppliers`, `capacity_reduction_pct`, `recovery_rounds`, etc. Added `sc_effects` JSONField (migration `0052`) and taught `load_scenario` to capture them. Post-reseed, the effects are present, e.g. Taiwan Earthquake → `{affected_suppliers:[tsmc_taiwan,umc_taiwan,auo_taiwan], capacity_reduction_pct:40, recovery_rounds:3, teaches:single_source_risk}`.
- `ResilienceParameters.resilience_score_weights` + `ClassResilienceWeightOverride` confirmed as the weight source (class override wins).

No MISMATCH halts beyond the ghost-field, which was closed with a migration rather than an invented name.

---

## 2. What Was Built

`core/engine/sc_engine.py` — `run_sc_engine(context)`, a deterministic Phase-1 step:

1. **Determinism** — a single `random.Random` seeded by `sha256(game_id, round_number, scenario_id)`. Same inputs → same draws (test `test_seed_deterministic`).
2. **Recovery carry-forward** — prior-round `SupplierState` with `recovery_rounds_remaining > 0` is carried into the current round with the counter decremented (multi-round disruptions heal over time).
3. **Event firing** — iterates `EventTemplateDefinition(category='supply_chain')`, respects `earliest_round`, `max_occurrences` (counts existing `SCEventInstance` for the game), and draws vs `probability_per_round`. Writes `SupplierState` (capacity/quality/lead-time/cost-multiplier/recovery from `sc_effects` + severity) and `LaneState` (rate modifier) for affected entities.
4. **Structured contingency execution** — per team, reads `ContingencyPlan`:
   - *Alt-supplier rules*: when a disrupted supplier is sourced for a category and a **healthy** backup is named, shifts `shift_pct` of the impact off the disrupted supplier.
   - *Mode-switch rules*: when a disrupted lane is used for `sea`, shifts `shift_pct` of the freight-shock impact off that mode.
   Applied rules are recorded on the `SCEventInstance.resolution_data.team_impact[team]`.
5. **Disruption cost** — effective (post-contingency) impact is deducted from `team.cash_on_hand`.
6. **Resilience scoring** — six weighted components (`multi_sourcing`, `geographic_diversity`, `buffer_inventory_adequacy`, `modal_flexibility`, `tier_2_visibility`, `supplier_financial_health`) → `ResilienceScoreHistory` with the component breakdown and weights used.

`core/engine/advance_round.py` — hooked `run_sc_engine(context)` into `_run_phase_1`, **best-effort** (wrapped in try/except; a failure logs and appends to the round log but never crashes round processing).

`core/models/scenario.py` + `load_scenario.py` — `sc_effects` field + loader capture (§1).

---

## 3. Tests

`core/tests/test_cc19_sc_engine.py` (4 tests, runs against the real CE scenario):

- `test_resilience_scored` — both teams get a `ResilienceScoreHistory` row with a numeric score and the expected component + weight keys.
- `test_contingency_reduces_impact` — two teams single-source the same disrupted supplier; the team with a backup-supplier rule loses **less** cash than the unprotected team (`A.cash > B.cash`, both `< start`). Deterministic (event probabilities zeroed; disruption injected via carry-forward).
- `test_events_fire_and_populate_state` — forcing the Taiwan-earthquake probability to 1 fires an `SCEventInstance` and creates a `SupplierState` for `tsmc_taiwan` with reduced capacity and a positive recovery counter.
- `test_seed_deterministic` — `_seed` is stable across calls and varies with round.

**Full suite: 129 tests, OK** (was 125 pre-CC-19; +4). `manage.py check` clean.

---

## 4. Live Verification (on the running deployment)

Restarted the globalstrat+ gunicorn master on `:8012` (cwd `…/globalstrat+/backend`, distinct from the original stack on `:8000`/`:8002`) to load the new engine. Re-created the demo game (the earlier game 9 was cascade-deleted when the CE scenario was reseeded for `sc_effects`):

- `setup_test_game --flush --scenario 7` → **game 10**, 4 teams, round 0 processed, round 1 open.
- `seed_sc_posture --game 10` → starting single-source posture for all 4 teams.
- Ran `run_sc_engine` on game 10 / round 1 (the exact call the Phase-1 hook makes): **fired 1 SC event, wrote 3 `SupplierState` rows, scored all 4 teams.**

Live API (instructor header auth, through `:8012`):

```
GET /api/games/10/teams/10/sc/round/1/resilience-score/
→ {"score":"20.538",
   "components":{"multi_sourcing":0.0,"modal_flexibility":0.0,"tier_2_visibility":0.0,
                "geographic_diversity":0.125,"buffer_inventory_adequacy":0.667,
                "supplier_financial_health":0.804},
   "weights_used":{...}}

GET /api/games/10/teams/10/sc/round/1/sc-events/
→ [{"event_template":188,"resolution_data":{"team_impact":{...}}, ...}]
```

The dashboard **Supply Chain** tab now renders a real score (20.538) and the SC event, replacing the prior "Not scored yet" empty state. The score correctly reflects the seeded single-source posture (multi_sourcing 0, modal_flex 0, tier-2 0; buffer and supplier-health carry it). In this draw the fired event's affected suppliers did not overlap any team's sourced supplier, so per-team impact is `0` — correct behavior (no false losses); the impact/contingency path is proven deterministically by `test_contingency_reduces_impact`.

---

## 5. Known Bounds (documented, not silent)

- **Cost coupling:** the disruption cost is applied directly to `team.cash_on_hand` at end of Phase 1; it does not yet flow through COGS/net-income. A bounded follow-up, called out in the engine module docstring.
- **Idempotency:** resilience scoring and event firing are idempotent (`update_or_create`; firing respects `max_occurrences`). The **cash deduction is not** — it assumes `run_sc_engine` runs once per round, which is the case inside `advance_round` (each round is processed once). Re-invoking the engine on an already-processed round would re-deduct.

---

## 6. Acceptance Criteria (spec §9)

| Criterion | Status |
|---|---|
| Structured SC events fire deterministically from scenario data | ✅ `sc_effects` loaded; seeded firing; live fire on game 10 |
| Event effects populate SupplierState/LaneState with duration & recovery | ✅ 3 SupplierState rows; recovery carry-forward tested |
| Structured contingency rules reduce disruption impact | ✅ `test_contingency_reduces_impact` (A < B) |
| Resilience scored per team per round with component breakdown | ✅ live 20.538 + 6 components; written to `ResilienceScoreHistory` |
| Deterministic (seeded) | ✅ `test_seed_deterministic` |
| Never crashes round processing | ✅ best-effort try/except in `_run_phase_1` |
| Surfaced on the dashboard | ✅ live resilience-score + sc-events endpoints return data |
| Full suite green | ✅ 129 tests OK |
