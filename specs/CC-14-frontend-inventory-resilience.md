# CC-14: Frontend - Inventory & Resilience

**Project:** globalstrat+  
**Spec Type:** Build pipeline - frontend decision page  
**Depends on:** CC-8, CC-9  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted for builder execution

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

Build the Inventory & Resilience decision page connected to the SC inventory API.

---

## 2. Required UX

The page must support selecting buffer days by product/market; setting safety-stock trigger percentage; editing disruption response playbook; editing alternative supplier activation rules; editing mode-switch triggers; save/reload; and server validation error display.

---

## 3. Acceptance Criteria

1. Page is reachable from navigation.
2. Existing inventory and contingency state reloads correctly.
3. Valid entries save and persist.
4. Locked fields are disabled or clearly marked unavailable.
5. `npm run build` succeeds.
6. Browser verification is recorded in `specs/reports/cc-14/acceptance_report.md`.

---

## 4. Non-Scope

No resilience score calculation belongs in CC-14. This page captures decisions; dashboard/scoring display comes later.
