# CC-22 E2E Report — Supply Chain Simulation

**Spec:** `specs/CC-22-e2e-supply-chain-simulation-test.md` · **Branch:** `cc-22-e2e-supply-chain-simulation-test` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — E2E proven end to end (backend integration + real-stack browser).

## 1. Backend integration test (§2.1–2.10, §4.3, §4.4, §4.5)

New module `core/tests/test_cc22_e2e.py`. Loads the **real Consumer Electronics scenario** into the test DB (`load_scenario`), builds a game/team/user/open-round + product chain, and drives the real views.

```
$ python3 manage.py test core.tests.test_cc22_e2e --verbosity=1
Ran 8 tests in 4.191s
OK
```

Coverage:
- `test_01` scenario seed present (25 suppliers, 20 lanes).
- `test_02` **submit sourcing** → 201, 2 allocations persisted.
- `test_03` **submit logistics** (round 5, modal mix unlocked) → 201, `LogisticsDecision` persisted.
- `test_04` **submit trade finance + inventory** → 201 each, `TradeFinanceDecision` + `InventoryDecision` persisted.
- `test_05` **dashboard read** of submitted sourcing (GET returns the 100% allocation).
- `test_06` advance requires lock → `advance_round` raises `ValueError` when the team hasn't locked.
- `test_07` **lock + advance, no crash with SC data** → create `DecisionSubmission(status='locked')`, then `advance_round(game.id, dry_run=True)` runs Phase 1 on the full CE scenario + SC decisions and returns without exception.
- `test_08` **seed determinism** → fingerprint `{suppliers:25, lanes:20, tf:6, tsmc_price:'45.00'}` reproduces exactly from the same YAML.

Full suite regression:
```
$ python3 manage.py test --verbosity=1
Ran 113 tests in 11.9s
OK
```
(All green — the previously-noted `test_engine.test_advance_round_unlocked_team` now passes as well.)

## 2. Round-advancement note (§4.4)
`advance_round(dry_run=True)` runs Phase 1 (the synchronous deterministic engine) and returns before Phase 2 (an async background thread that generates narrative). The dry-run path is what the test exercises — it proves the engine does not crash with SC decisions and the full CE scenario present. Phase 2 (background narrative) is out of scope for a synchronous test.

## 3. Browser E2E (§3, §4.2) — real stack, real persistence

Because §3 requires more than API-only testing, a **real-stack** browser path was run: the production build served by a small node harness that **proxies `/api` to a live backend** (`manage.py runserver` on the real `globalstrat_plus` DB); only `/api/auth/me` was mocked for session bootstrap. Puppeteer (system Chromium) drove the UI; the decision was written through the real API to the real DB.

Seeded (then deleted after): game "CC22-BROWSER-E2E" (id 8) on scenario 5, team 5, open round 5, instructor user 7.

```
[cc22b] dashboard_rendered_real  => true    (dashboard read real backend; "Uyghur…" regime rendered)
[cc22b] suppliers_loaded_real    => true    (Sourcing page loaded 25 real suppliers)
[cc22b] supplier_selected        => "Contemporary Amperex Technology (CN)"
[cc22b] save_success             => true    ("Sourcing decision saved")
[cc22b] persisted_after_reload   => true    (allocation re-rendered after full reload)
```

**Direct DB confirmation** (the UI write reached the real DB):
```
SourcingAllocation(team 5) → [{'critical_input_category':'battery','supplier_id':37,'allocation_pct':100}]
SourcingDecision(team 5)   → exists
```
(supplier 37 = Contemporary Amperex / CATL battery — matches the supplier the browser selected.)

Screenshots: `cc22b_dash.png` (dashboard on real backend), `cc22b_saved.png` (post-submit). Session/auth note: the legacy `X-User-Id` header path is used (an `access_token` in localStorage would send a fake `Bearer` token that JWT auth rejects with 403; omitting it lets the instructor-role header auth through).

## 4. Determinism (§4.5)
Seeded-data determinism verified in `test_08` (identical fingerprint from the same YAML). Full engine-output determinism across seeded runs is **not applicable yet** — the SC engine bundle that would derive SC-specific outputs (resilience score, event effects) from decisions does not exist (see gaps).

## 5. Remaining known gaps (§4.6)
- **No SC engine bundle** — SC decisions are persisted and read, but not yet consumed by the engine to produce SC-derived outputs. `§2.11` ("at least one SC-derived state/output exists when engine bundles are present") is **conditional and not met**: `ResilienceScoreHistory`, `SupplierState`, `LaneState` remain engine-populated/empty. Routed to CC-3/CC-21 engine bundles (consistent with CC-23A's operational-state inventory).
- **Phase 2 (async narrative)** not exercised by the synchronous test.
- **Deploy note:** the standing `:8002` gunicorn still runs pre-change code; the browser E2E used a fresh `runserver` on the current code. Production deploy requires restarting the backend to serve the new endpoints + `scenario_id`.
- **Benign frontend 404s:** the app polls `…/decisions/round/5/` (main-decision draft), which 404s when no submission draft exists — unrelated to the SC flow.

## 6. Acceptance Criteria (§4)
1. ✅ E2E test script exists + documented (`test_cc22_e2e.py` + this report). 2. ✅ Browser test passes for the dashboard + a decision page (real stack). 3. ✅ Backend integration test passes for all four SC decision families. 4. ✅ Round advancement does not crash with SC data present. 5. ✅ Determinism recorded for seeded runs. 6. ✅ This report records commands, outputs, and gaps.
