# CC-22: E2E Supply Chain Simulation Test

**Project:** globalstrat+  
**Spec Type:** Validation - end-to-end proof  
**Depends on:** CC-8 through CC-15, plus any engine bundles needed for scoring/events  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted for builder execution after implementation bundles land

---

## Non-Negotiable Builder Discipline

This bundle inherits `STANDING-DISCIPLINE.md`, but the following rules are repeated here because they are completion blockers:

1. Verify every existing field, model, table, endpoint, route, component, settings key, and payload shape before referencing it. Use the current codebase and database, not memory or nearby names.
2. Do not invent field names, model names, endpoint paths, YAML keys, payload keys, CSS classes, or React component names. If the expected name does not exist, halt with a MISMATCH report.
3. Do not silently adapt the spec to whatever name seems convenient. Report the actual state and wait for instruction if the contract and implementation diverge.
4. Before calling the bundle complete, self-verify every acceptance criterion with recorded command output, API/browser evidence, and a closeout report under the bundle's `specs/reports/cc-XX/` directory.
5. A passing backend response alone is not proof of frontend completion. Frontend bundles require browser verification of the actual user workflow.

---

## 1. Purpose

Prove the supply-chain process works end to end: seeded scenario data, student UI decisions, backend persistence, dashboard reads, round advancement, and repeatable results.

This is the finish-line gate for the supply-chain layer.

---

## 2. Minimum E2E Path

The test harness must cover:

1. Load Consumer Electronics scenario with SC seed data.
2. Create a game, teams, users, and current round.
3. Submit sourcing decisions.
4. Submit logistics decisions.
5. Submit trade finance / FX decisions.
6. Submit inventory / contingency decisions.
7. Verify dashboard reads submitted decisions.
8. Lock decisions.
9. Advance the round.
10. Verify no runtime exception.
11. Verify at least one SC-derived state/output exists when engine bundles are present.
12. Re-run with the same seed and confirm deterministic output where applicable.

---

## 3. Browser Requirement

At least one Playwright or equivalent browser path must exercise the student UI through the supply-chain dashboard and one decision page. API-only testing is insufficient.

---

## 4. Acceptance Criteria

1. E2E test script exists and is documented.
2. Browser test passes for the dashboard plus at least one SC decision page.
3. Backend integration test passes for all four SC decision families.
4. Round advancement does not crash with SC data present.
5. Determinism check is recorded for seeded runs.
6. `specs/reports/cc-22/e2e_report.md` includes commands, outputs, and remaining known gaps.

---

## 5. Calibration Note

Exact supplier prices, probabilities, and resilience weights do not block CC-22 unless they prevent the E2E path from functioning. Calibration can be tuned after the process is demonstrably working.
