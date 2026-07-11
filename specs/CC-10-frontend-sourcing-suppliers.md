# CC-10: Frontend - Sourcing & Suppliers

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

Build the student-facing Sourcing & Suppliers decision page and connect it to the hardened SC API.

---

## 2. Scope

Frontend files are under `frontend/globalstrat-frontend/src/`. Before editing, verify route/component patterns in `src/App.js`, `src/components/Sidebar.js`, `src/api/decisions.js`, and existing decision pages under `src/pages/`.

---

## 3. Required UX

The page must support supplier option review, critical input categories, allocation percentages by supplier, payment terms, volume commitments, multi-sourcing strategy, tier-2/3 visibility investment, client-side validation, server error display, and successful save/reload.

Use existing GlobalStrat page style and Ant Design patterns. This is an operational decision page, not a marketing page.

---

## 4. Acceptance Criteria

1. Sourcing page is reachable from app navigation.
2. Page loads suppliers from the scenario-content endpoint.
3. Page loads existing sourcing decision state for the active team/round.
4. User can submit valid allocations and see persisted values after reload.
5. Invalid allocation totals are blocked client-side and rejected server-side.
6. Locked fields are visibly disabled or explained by round state.
7. `npm run build` succeeds.
8. Browser verification is recorded in `specs/reports/cc-10/acceptance_report.md`.

---

## 5. Non-Scope

No logistics, trade finance, inventory, dashboard, or engine logic work belongs in CC-10.
