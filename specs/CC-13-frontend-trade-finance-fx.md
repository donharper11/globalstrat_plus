# CC-13: Frontend - Trade Finance & FX

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

Build the Trade Finance & FX decision page connected to the SC trade-finance API.

---

## 2. Required UX

The page must support viewing trade finance instruments; selecting buyer payment instruments by segment/market; editing LC document preparation investment; setting Sinosure coverage by market; setting FX hedge ratio and tenor by currency pair; save/reload; and clear server validation error display.

Chinese-firm-going-overseas framing from CC-6 should guide labels and help text, but keep implementation lightweight.

---

## 3. Acceptance Criteria

1. Page is reachable from navigation.
2. Instruments load from the scenario-content endpoint.
3. Existing trade-finance and FX state reloads correctly.
4. Valid entries save and persist.
5. Locked fields are disabled or clearly marked unavailable.
6. `npm run build` succeeds.
7. Browser verification is recorded in `specs/reports/cc-13/acceptance_report.md`.

---

## 4. Non-Scope

No FX mark-to-market or hedge settlement logic belongs in CC-13. That is a later engine/lifecycle bundle.
