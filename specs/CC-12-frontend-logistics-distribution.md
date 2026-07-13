# CC-12: Frontend - Logistics & Distribution

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

Build the Logistics & Distribution decision page connected to the SC logistics API.

---

## 2. Required UX

The page must support viewing shipping lanes and lane mode availability; editing modal mix per lane; editing volume commitments when unlocked; setting Incoterms per destination market; setting insurance coverage; setting customs classification; setting reverse logistics capacity/hub; validation that modal mix sums to 100; and save/reload.

Use existing decision-page visual patterns. Avoid adding a new design system.

---

## 3. Acceptance Criteria

1. Page is reachable from navigation.
2. Lanes load from the scenario-content endpoint.
3. Existing logistics decision state reloads correctly.
4. Valid modal mix saves and persists.
5. Invalid modal mix is blocked client-side and rejected server-side.
6. Locked fields are disabled or clearly marked unavailable.
7. `npm run build` succeeds.
8. Browser verification is recorded in `specs/reports/cc-12/acceptance_report.md`.

---

## 4. Non-Scope

No sourcing, trade finance, inventory, dashboard, or engine work belongs in CC-12.
