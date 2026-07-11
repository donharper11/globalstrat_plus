# Supply-Chain Layer — Gap Audit & Closure

**Date:** 2026-07-11 · **Scope:** CC-8 → CC-15, CC-22, CC-23A (the landed SC layer) · **Observes:** `STANDING-DISCIPLINE.md`

After all SC specs landed, I audited the layer for gaps (loader validation, loose ends, TODOs, untested paths, working-tree state). Findings and disposition below.

## Closed in this pass

### G1 — CC-1 §8 scenario-loader validation was not enforced *(closed)*
CC-1 §8 mandates the loader halt on 9 SC cross-reference rules, but `validate_scenario_yaml` only checked cultural-distance / origin-trust market codes. A malformed future SC scenario (bad supplier country, weights not summing to 1.0, dangling substitutability, unknown instrument/lane, single-source category) would have loaded silently.
- **Fix:** added `_validate_supply_chain(data, market_codes)` implementing all 9 §8 rules, wired into `validate_scenario_yaml` (runs only when a `suppliers` section exists, so non-SC scenarios are unaffected). Failures now halt the load with structured errors.
- **Verified:** the real Consumer Electronics scenario passes with **0** errors (no regression; still loads via `load_scenario --flush`); deliberately-broken scenarios are rejected with precise messages.
- **Tests:** `core/tests/test_cc_gaps.py::CC01SupplyChainValidationTests` (8 tests).

### G2 — Scenario-content list endpoints (CC-12/13) had no tests *(closed)*
`ScenarioMarketsView` / `ScenarioSegmentsView` (added as CC-12/13 enablement) were untested.
- **Fix:** `core/tests/test_cc_gaps.py::ScenarioContentEndpointTests` (3 tests) — response shape, `segment_type` filter, empty-scenario state.

**Result:** `manage.py check` clean; focused module 11/11; **full suite 124 tests, all OK** (no regressions).

## Identified — deferred by design or needing input (not closed)

| # | Gap | Why not closed here |
|---|---|---|
| G3 | **No SC engine bundle** — SC decisions persist and are read, but the engine does not yet derive SC outputs (resilience score, event effects, `LaneState`/`SupplierState` population). | Deliberately deferred by the specs themselves (CC-23A §12, CC-22 §2.11 is conditional "when engine bundles are present"). This is a large new feature routed to CC-3/CC-21 engine bundles — not a defect in the landed specs. Surfaced honestly in the CC-15/CC-23A dashboards as "Not calculated yet" / "Not available". |
| G4 | **CC-11 RAG corpus absent** — `globalstrat_plus_articles` empty; no curated SC corpus. | Gated handoff; deferred by user. Un-gates when a ≥40-item corpus is provided (see `specs/reports/cc-11/gate_check.md`). |
| G5 | **Other scenarios (clean_energy, media) have no SC data.** | Expected per CC-1 §7 (SC coverage for other industries is a later bundle; media is intentionally light). Dashboards handle the empty case honestly. Now that G1 is enforced, when those scenarios gain SC data they'll be validated too. |
| G6 | **Live `:8002` gunicorn runs pre-change code** — won't serve the new endpoints or `/auth/me` `scenario_id` until restarted. | Operational action on a shared service, not a code gap. Flagged for deploy; not restarted unprompted. |
| G7 | **Uncommitted working-tree edits** — `backend/core/engine/advance_round.py` + externally-added "Non-Negotiable Builder Discipline" sections in CC-08/09/10/12/13/14 specs + `CC-SEQUENCE-PLAN.md`. | Not authored by me. The spec edits were confirmed "ok as is". `advance_round.py` is an external fix (it makes `test_advance_round_unlocked_team` pass) that is **modified but never committed** — recommend the author commits it so the green suite is reproducible from a clean checkout. |
| G8 | **Benign frontend 404** — the app polls `…/decisions/round/N/` (main-decision draft) which 404s when no draft exists. | Part of the pre-existing main-decision flow, not the SC layer; cosmetic. |

## Bottom line
The SC layer's own closeable defects are closed (loader validation + endpoint tests). The remaining items are either forward engine work the specs intentionally deferred, gated content (CC-11), an ops restart, or external uncommitted edits — each documented rather than silently left.
