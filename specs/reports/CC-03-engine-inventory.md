# CC-3 Engine Inventory Report

**Spec:** `specs/CC-03-engine-logic.md` §2.1
**Branch:** `cc-03-engine-logic`
**Project:** globalstrat+ (derived from globalstrat main codebase)
**Observes:** STANDING-DISCIPLINE.md §1.8 (model-to-table), §1.9 (DB client version)
**Status:** Complete — two halt conditions flagged (see §E).

---

## Section A — Pipeline Orchestration

### A.1 Entry point

- **File:** `backend/core/engine/advance_round.py`
- **Function:** `advance_round(game_id, dry_run=False)` — line 25
- **Signature:** `advance_round(game_id: int, dry_run: bool = False) -> dict` returning `{'phase_1_time': float, 'phase_2_status': str}`
- **Docstring summary:** "Runs Phase 1 synchronously, fires Phase 2 in background."

### A.2 Legacy entry point

- `backend/core/services/round_engine.py:255` — `advance_round(game_id=None)` — older monolithic orchestrator. Still invoked by the `check_round_deadlines` management command (`core/management/commands/check_round_deadlines.py:116`). Tests, integration runs, and the `manage.py advance_round` command all route through `core/engine/advance_round.py`. Treat `core/engine/advance_round.py` as the canonical CC-3 target; the legacy path is out of scope for the supply-chain extensions.

### A.3 Context object

- `backend/core/engine/utils.py:115` — `RoundContext(game, round_number)` carries computed per-round state through the pipeline. Fields include `teams`, `markets`, `segments`, `fit_scores`, `adjusted_fit_scores`, `best_products`, `adoption`, `readiness`, `events_fired`, `production_remaining`, `org_modifiers`, `log`. Engine functions attach additional attributes dynamically (e.g. `context.cogs`, `context.logistics`, `context.esg_savings`, `context.revenue`, `context.skip_rag`). Not persisted — discarded at round end.

### A.4 Phase 1 — Synchronous, deterministic (inside `_run_phase_1`)

| # | Step | Module | Notes |
|---|---|---|---|
| 1 | Determine current open `Round`; auto-lock any un-submitted team | `advance_round.py` | Creates `DecisionSubmission(status='locked')` for teams with no submission |
| 2 | Build `RoundContext(game, current_round)`, set `skip_rag=True` | `engine/utils.py` | Phase 2 will re-invoke RAG calls |
| 3 | `fire_events(context)` | `engine/events.py` | §C — probabilistic event firing |
| 4 | `update_market_conditions(context)` | `engine/events.py` | Applies round-scheduled market condition deltas |
| 5 | `process_event_responses(context)` | `engine/events.py` | CC-7 — team response submissions evaluated |
| 6 | `process_rd(context)` | `engine/rd_processing.py` | R&D spend + platform readiness advancement |
| 7 | `apply_strategy_effects(context)` | `engine/strategy_effects.py` | Strategy-option feature gains applied |
| 8 | `process_talent(context)` | `engine/talent.py` | CC-16 |
| 9 | `apply_org_structure_modifiers(context)` | `engine/org_structure.py` | CC-32B (try/except) |
| 10 | `process_acquisitions(context)` | `engine/acquisitions.py` | CC-20 |
| 11 | `process_alliances(context)` | `engine/alliance_engine.py` | CC-32D (try/except) |
| 12 | `calculate_fit_scores(context)` | `engine/preference_engine.py` | — |
| 13 | `apply_campaign_multipliers(context)` | `engine/campaign_engine.py` | — |
| 14 | `apply_readiness_gating(context)` | `engine/readiness_engine.py` | — |
| 15 | `run_bass_adoption(context)` | `engine/bass_engine.py` | — |
| 16 | `calculate_revenue(context)` | `engine/revenue.py` | Step 10 in legacy numbering |
| 17 | `calculate_cogs(context)` | `engine/costs.py` | §B.1 |
| 18 | `calculate_logistics_tariffs(context)` | `engine/costs.py` | §B.2 |
| 19 | `calculate_entry_mode_overhead(context)` | `engine/costs.py` | §B.4 (CC-31A B7, runs **before** opex) |
| 20 | `calculate_org_structure_costs(context)` | `engine/org_structure.py` | CC-32B (try/except) |
| 21 | `calculate_operating_expenses(context)` | `engine/costs.py` | §B.5 |
| 22 | `calculate_interest(context)` | `engine/costs.py` | — |
| 23 | `calculate_tax(context)` | `engine/costs.py` | — |
| 24 | `calculate_repatriation_costs(context)` | `engine/costs.py` | CC-31A B6 |
| 25 | `process_tax_structure_costs(context)` | `engine/costs.py` | CC-32C (try/except) |
| 26 | `calculate_inventory_costs(context)` | `engine/costs.py` | §B.3 |
| 27 | `calculate_retirement_costs(context)` | `engine/costs.py` | — |
| 28 | `generate_financial_statements(context)` | `engine/financials.py` | Writes `RoundResultFinancials` |
| 29 | `record_esg_impacts / record_talent_impacts / record_partnership_impacts` | `engine/strategic_economics.py` | CC-24 (try/except) |
| 30 | `calculate_derived_features(context)` | `engine/derived_features.py` | CC-25 (try/except) |
| 31 | `process_capital_markets(context)` | `engine/capital_markets.py` | CC-26 (try/except) |
| 32 | `calculate_performance_index(context)` | `engine/performance.py` | — |
| 33 | `calculate_coherence(context, skip_rag=True)` | `engine/coherence.py` | Deterministic formula only; RAG path deferred to Phase 2 |
| 34 | `run_agent_cycle(game, current_round_obj, context)` | `engine/agents/orchestrator.py` | CC-32E (try/except) |
| 35 | `update_leaderboard(context)` | `engine/leaderboard.py` | — |
| 36 | `generate_post_round_alerts(game, current_round)` | `engine/instructor_alerts.py` | Deterministic templates only (try/except) |
| 37 | Finalize round: `Round.status='processed'`, `processing_status='RESULTS_AVAILABLE'`, `phase_1_duration=…`; create or re-open next `Round`; on final round, mark game `completed` | `advance_round.py` | — |

Note: steps flagged *try/except* swallow exceptions into `context.log` so a downstream bug in one subsystem does not crash the full pipeline. This is already the project-wide idiom for newer CC-32* additions.

### A.5 Phase 2 — Background thread, LLM-driven (inside `_run_phase_2`)

Dispatch: `threading.Thread(target=_run_phase_2, args=(game.id, round_obj.id), daemon=True).start()` immediately after Phase 1 returns. Skipped entirely when `dry_run=True`.

| # | Step | Module | Notes |
|---|---|---|---|
| 1 | `connection.ensure_connection()` (Django DB) | — | Required because Phase 2 runs in a separate thread |
| 2 | `generate_round_narratives(game, round_obj)` | `engine/narratives.py` | Orchestrates: briefing prompts, coherence RAG, coaching prompts, market outlook. Store helpers: `_store_briefing_results`, `_store_coherence_results`, `_store_coaching_results`, `_store_outlook_results` |
| 3 | Finalize: `Round.processing_status='FULLY_COMPLETE'`, `narrative_generated=True`, `phase_2_duration`, clear `narrative_error`. On exception, persist error string only; numbers stay valid | `advance_round.py` | — |

Phase 2 outputs **do not** feed back into Phase 1 scoring — consistent with spec §5 "Phase 2 outputs never feed back into Phase 1 scoring."

### A.6 Phase invocation mechanism

- Phase 1: synchronous call in request thread.
- Phase 2: Python `threading.Thread` (daemon). Not a task queue — no Celery, no RQ, no Redis broker. This simplifies ops but means Phase 2 work is lost on process restart before `FULLY_COMPLETE` is persisted; recovery relies on `narrative_error` being non-empty or `processing_status` stuck at `RESULTS_AVAILABLE`.

---

## Section B — Cost Function Roster

File: `backend/core/engine/costs.py` (1,038 lines).

All four spec-named cost functions exist with matching names. **Signatures are uniformly `(context: RoundContext) -> None`** — results attach as attributes on `context` rather than return values. This is the project-wide idiom; the pseudocode `(team, round_state)` in CC-3 §6 is algorithmic, not a literal signature. Engine wrappers must follow the `(context)` convention for consistency with the existing pipeline. Not a MISMATCH.

### B.1 `calculate_cogs` — costs.py:30

- **Signature:** `def calculate_cogs(context)`
- **Called from:** `core/engine/advance_round.py` (step 17 above)
- **Consumes decisions:** `DecisionMarketing` (`production_source_market_id`), `DecisionSubmission` (lookup key)
- **Consumes scenario:** `ScenarioConfig` (`base_unit_cost`, `learning_curve_factor`); `MarketDefinition.base_manufacturing_cost`, `contract_mfg_available`, `contract_mfg_cost_multiplier`; `PlatformGenerationDefinition.generation_order`
- **Consumes team state:** `TeamProduct`, `TeamPlant.cumulative_production`
- **Consumes prior-step context:** `context.revenue`
- **Also reads:** CC-16 talent (`get_talent_level(team, 'operations', …)`), CC-24 ESG (`calculate_esg_cogs_modifier`)
- **Produces:** `context.cogs[(team_id, product_id, market_id)] = {unit_cost, total_cogs, units_produced}`; side-effects `context.esg_savings`, `context.talent_savings`; mutates `TeamPlant.cumulative_production`

### B.2 `calculate_logistics_tariffs` — costs.py:196

- **Signature:** `def calculate_logistics_tariffs(context)`
- **Called from:** `advance_round.py` step 18
- **Consumes decisions:** `DecisionMarketing` (`production_source_market_id`)
- **Consumes scenario:** `ScenarioConfig.logistics_base_cost_per_unit`; `MarketDefinition`; entry-mode relation via `TeamMarketPresence.entry_mode` (→ `EntryModeDefinition.logistics_cost_multiplier`, `tariff_applies`)
- **Consumes modifiers:** `ActiveModifier(modifier_type='cost', target_field='logistics_cost', …)`
- **Consumes CC-24:** `calculate_esg_tariff_reduction`, `get_partnership_effects`
- **Consumes prior-step context:** `context.revenue`, `context.markets` (for `effective_tariff_rate`)
- **Produces:** `context.logistics[(team_id, product_id, market_id)] = {logistics_cost, tariff_cost}`; side-effects `context.esg_savings`, `context.partnership_savings`

### B.3 `calculate_inventory_costs` — costs.py:704

- **Signature:** `def calculate_inventory_costs(context)`
- **Called from:** `advance_round.py` step 26
- **Consumes scenario:** `ScenarioConfig.inventory_holding_cost_pct`
- **Consumes prior-step context:** `context.revenue` (for `units_unsold`), `context.cogs` (for `unit_cost`)
- **Produces:** `context.inventory_costs[(team_id, product_id, market_id)] = {units_unsold, inventory_cost, inventory_value}`

### B.4 `calculate_entry_mode_overhead` — costs.py:868

- **Signature:** `def calculate_entry_mode_overhead(context)`
- **Called from:** `advance_round.py` step 19 (before opex per CC-31A B7)
- **Consumes decisions:** `DecisionMarketEntry.integration_strategy` (most-recent round)
- **Consumes team state:** `TeamMarketPresence` (active presences), `TeamMarketPresence.brand_preserved`
- **Produces:** `context.entry_mode_overhead[(team_id, market_id)] = Decimal` multiplier (1.00 / 1.15 / 1.25)

### B.5 Additional cost functions (discovered in costs.py)

| Function | Line | Called from (advance_round step) | Purpose |
|---|---|---|---|
| `calculate_operating_expenses` | 371 | 21 | R&D opex, marketing opex, campaign, org comms, etc. |
| `calculate_interest` | 541 | 22 | Interest/financing on loans & working capital |
| `calculate_tax` | 558 | 23 | Corporate tax by market |
| `calculate_retirement_costs` | 735 | 27 | Product-retirement inventory write-off |
| `calculate_repatriation_costs` | 808 | 24 | CC-31A B6 — foreign-profit repatriation |
| `process_tax_structure_costs` | 906 | 25 | CC-32C — tax structure maintenance + audit rolls |
| `_apply_regulator_modifiers` | 998 | (helper) | Private — applied inside tax path |

---

## Section C — Event System

### C.1 Declaration

| Entity | Model | File:Line | Physical table |
|---|---|---|---|
| Event template | `EventTemplateDefinition` | `core/models/scenario.py:346` | `event_template_definition` |
| Event impact | `EventImpactDefinition` | `core/models/scenario.py:460` | `event_impact_definition` |
| Event response option | `EventResponseDefinition` | `core/models/scenario.py:499` | `event_response_definition` |
| Fired event instance | `EventInstance` | `core/models/results.py:7` | `event_instance` |
| Active modifier | `ActiveModifier` | `core/models/results.py` | `active_modifier` |
| Team response choice | `DecisionEventResponse` | `core/models/decisions.py:361` | `decision_event_response` |

Templates are loaded from scenario YAML at scenario-load time into `EventTemplateDefinition` + `EventImpactDefinition` rows.

Note: `TriggeredEvent` (`core/models/events.py:4`) exists but is **not** imported by `core/engine/events.py`. The live engine path uses `EventInstance` from `core/models/results.py`. Flag for CC-4 cleanup candidate.

### C.2 Trigger probability evaluation

Per round, for each `EventTemplateDefinition`:

```python
roll = random.random()
if roll > base_prob:
    continue
```

(`core/engine/events.py:67`). Also checks `earliest_round`, `latest_round`, and `max_occurrences`. For templates with `category ∈ {REGULATORY, GEOPOLITICAL, SANCTIONS}`, CC-31A B8 branches into `_fire_compliance_adjusted_event` for per-team probability adjustment.

### C.3 Seeded RNG — **ABSENT**

`core/engine/events.py:6` imports Python stdlib `random` at module scope. No `random.seed(…)` or `random.Random(seed)` appears anywhere in `core/engine/`, `core/services/`, or model definitions. Other `random`-using engine modules (`alliance_engine.py`, `costs.py`, `agents/governments.py`, `services/competitor_ai.py`) share the same unseeded global state.

**Consequence:** Two advance-round runs with the same decisions and scenario will **not** produce identical event sequences, violating spec §9 ("Determinism and Reproducibility"). See §E halt #3.

### C.4 Effect application

`_apply_event_impact(game, event_instance, impact, market, current_round)` (events.py:128) branches on `EventImpactDefinition.impact_type` and writes `ActiveModifier` rows with `started_round=current_round`, `expires_round=current_round + impact.duration_rounds`. Downstream consumers (cost steps, revenue, bass adoption) query `ActiveModifier` filtered on `started_round__lte=current_round` excluding `expires_round__lte=current_round`.

At the top of each `fire_events` call, `ActiveModifier.objects.filter(game=game, expires_round=current_round).delete()` retires modifiers that hit their expiration this round.

### C.5 Multi-round support

Supported via `EventImpactDefinition.duration_rounds` (`scenario.py:489`) + `ActiveModifier.started_round` / `expires_round` (`results.py:40-41`). **No explicit `recovery_rounds` field.** CC-3 §7.3's `recovery_rounds_remaining` / linear recovery interpolation is not yet implemented — the current system expresses durations as hard cutoffs, not gradual recovery. CC-4 will need to add recovery-rate fields to the event/impact schema.

---

## Section D — Model-to-Table Ghost Check

Per STANDING-DISCIPLINE §1.8. Scanned all 86 models imported under `core.models.*` anywhere inside `backend/core/engine/`. Ran `connection.introspection.table_names()` against the live `globalstrat_plus` DB and cross-referenced each model's `_meta.db_table` and `_meta.managed`.

**Result: 84 PHYSICAL, 2 GHOSTS.**

| Module.Model | db_table | managed | Status | Engine call site |
|---|---|---|---|---|
| `financials.FinancialExpense` | `financial_expenses` | `False` | **GHOST** | Imported at `core/engine/preference_engine.py:22`; **no usage** below the import line (dormant) |
| `messaging.TeamNotification` | `team_notifications` | `False` | **GHOST** | **Live call:** `TeamNotification.objects.create(...)` at `core/engine/acquisitions.py:117` inside `_notify_rejected_bid` — wrapped in try/except, so failure is logged and swallowed but the notification silently does not land |

All other 84 engine-referenced models are backed by physical tables. Full listing produced by `/tmp/ghost_check.py` (see git log; not committed to the repo to avoid one-off script sprawl).

CC-2 Section B already identified `core.Decision` as a ghost. It is **not** referenced by any `core/engine/` import in globalstrat+ — the engine uses the `Decision*` leaf models (`DecisionSubmission`, `DecisionMarketing`, etc.) directly. No engine path calls `Decision.objects.*`.

CC-3 EXTEND targets `DecisionPlant` and `DecisionESG` are both **PHYSICAL** (`decision_plant`, `decision_esg`) — safe to extend.

---

## Section E — Halt Condition Evaluation

Per CC-3 §2.2:

| # | Condition | Result | Detail |
|---|---|---|---|
| 1 | `advance_round` exists with expected signature | ✅ PASS | `core/engine/advance_round.py:25`, `advance_round(game_id, dry_run=False)` |
| 2 | Four named cost functions exist with expected names | ✅ PASS | `calculate_cogs`, `calculate_logistics_tariffs`, `calculate_inventory_costs`, `calculate_entry_mode_overhead` all present in `core/engine/costs.py`; all use `(context)` signature per engine idiom |
| 3 | Event system uses seeded RNG | ❌ **HALT** | Unseeded `random.random()` — see §C.3. Spec §9 determinism contract cannot be delivered without adding seeding |
| 4 | No engine-referenced ghost models | ❌ **HALT** | 2 ghosts — see §D. One dormant (`FinancialExpense`), one live (`TeamNotification` in acquisitions.py) |
| 5 | Phase 1 / Phase 2 split exists | ✅ PASS | Synchronous `_run_phase_1` + `threading.Thread` daemon `_run_phase_2` (§A.5–A.6) |

### E.1 Recommended resolutions (for spec author review — not auto-applied)

**Halt #3 (seeded RNG):**
- **Option A (minimal):** Add `rng = random.Random(seed_for(game_id, round_number, 'events'))` in `fire_events` and thread `rng` through other probabilistic engine calls. Backward-compatible with existing scenarios.
- **Option B (broad):** Attach `context.rng` at `_run_phase_1` entry with seed derived from `(game.id, round_number)`; require every engine module to consume `context.rng.random()` instead of module-level `random`. Cleaner long-term, but touches ~6 engine modules.

**Halt #4 (ghosts):**
- **`financials.FinancialExpense`:** Remove the unused import in `preference_engine.py:22`. Zero runtime impact, but keeps the codebase honest with §1.8. Alternatively, keep the model and add a migration to create `financial_expenses` — but only if a caller is actually planned.
- **`messaging.TeamNotification`:** The `acquisitions.py:117` call is active and silently failing. Either (a) add a migration creating `team_notifications` so notifications actually land, or (b) remove `_notify_rejected_bid`'s write path and route the message through `context.log` only. CC-4 decision.

Both halts are structural, not blocking for CC-3's spec scope (inventory + algorithmic contract). CC-3 acceptance §11 permits the inventory commit to land; resolutions flow through CC-4 design and/or amendment.

---

## Section F — CC-3.5 Resolution

*Added 2026-04-17 — records how the two halts from §E were cleared.*

### F.1 Halt #3 (seeded RNG) — resolved

**Approach chosen:** Option B (broad) from §E.1 — a seeded RNG helper is consumed at every probabilistic call site, keyed off `(class_id, round_number, operation_id)`.

- New utility: `core/engine/rng.py` exposes `get_rng(class_id, round_number, operation_id) -> random.Random`. Seed is `int(sha256(f"{class_id}:{round_number}:{operation_id}").hexdigest()[:16], 16)`.
- `class_id` convention: no `Game.class_id` field exists, so call sites pass `game.section_id or game.id` (section_id is nullable on Game). Documented in `rng.py`'s module docstring.
- **12 call sites migrated:**
  - `events.py` × 4 — event_trigger, event_target_market, compliance_event_target_market, compliance_event_roll
  - `costs.py` × 1 — tax_audit
  - `alliance_engine.py` × 1 — alliance_partner_defection
  - `agents/governments.py` × 5 — govt_regulatory_relaxation, govt_regulatory_tightening, govt_bilateral_volatility, govt_bilateral_facilitation, govt_bilateral_screening
  - `agents/state.py` × 1 — StateSnapshot now carries `class_id` alongside `round_number`, removing redundant Game lookups in agent evaluators.
- **Module-level `import random` removed** from every migrated file. `grep -rn "random\." core/engine/` returns zero matches.
- **Regression tests:**
  - `core/engine/tests/test_rng.py` — 7 unit tests for the utility itself
  - `core/engine/tests/test_determinism.py` — 6 contract tests covering every engine call site (same keys → same draws; distinct keys → distinct streams; class/round divergence)
  - Both modules run DB-free (`SimpleTestCase`); 13 tests total, all passing.

### F.2 Halt #4 (ghost models) — partially resolved

**`messaging.TeamNotification` (live ghost):** promoted to managed.
- Migration `core/migrations/0040_cc35_promote_teamnotification.py` uses `SeparateDatabaseAndState` to (a) update Django's model state and (b) emit `CREATE TABLE team_notifications` with indexes on `team_id` and `round_id`.
- The defensive `try/except Exception` wrapper at `acquisitions.py:117` — which had been silently swallowing every create — was removed. Notification creation is now a real failure path.
- Verified: `\d team_notifications` reports the table; a `TeamNotification.objects.create(...)` + delete round-trip succeeds in a Django shell.

**`financials.FinancialExpense` (dormant ghost):** **deferred to CC-5.** Not touched in CC-3.5 — the import remains in `preference_engine.py:22`. Rationale: CC-5 will decide whether to promote (create `financial_expenses`) or delete based on the financial-reporting spec's needs, and that decision is outside CC-3.5's scope.

### F.3 Halt evaluation update

| # | Condition | CC-3 | CC-3.5 |
|---|---|---|---|
| 3 | Event system uses seeded RNG | ❌ HALT | ✅ PASS |
| 4 | No engine-referenced ghost models | ❌ HALT | ⚠️ PARTIAL — live ghost resolved; `FinancialExpense` dormant ghost deferred to CC-5 |

### F.4 Commit trail

Branch `cc-03.5-determinism-and-notification` (merged via `--no-ff`):
1. `CC-3.5: add seeded RNG utility for deterministic engine operations`
2. `CC-3.5: replace unseeded random.random() in event triggers with seeded RNG`
3. `CC-3.5: replace remaining unseeded random.* calls in engine`
4. `CC-3.5: add regression test — identical inputs produce identical round outcomes`
5. `CC-3.5: promote messaging.TeamNotification from ghost — create team_notifications table`
6. `CC-3.5: remove defensive try/except — TeamNotification is no longer a ghost`
7. `CC-3.5: update inventory report with Section F resolution record`

---


## Section G — CC-3 Artifact Summary

- **Report file:** `specs/reports/CC-03-engine-inventory.md` (this file)
- **Scripts:** `/tmp/ghost_check.py` (transient — invoked via `PYTHONPATH=backend python3 /tmp/ghost_check.py`)
- **Code modifications:** **none.** CC-3 is specification-only.
- **Halts flagged for spec author:** 2 (see §E).
