# CC-15: Supply Chain Dashboard

**Project:** globalstrat+  
**Spec Type:** Build pipeline - read-only frontend surface  
**Depends on:** CC-8, CC-9, CC-10, CC-12, CC-13, CC-14  
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


## Operational State Mirror Requirement

The dashboard is the primary ERP-shaped simulation mirror. It must summarize simulated operational state, not just configuration data:

- supplier commitments and concentration
- inventory on hand / on order when available
- shipment or lane status when available
- compliance holds/flags when available
- trade-finance and FX exposure
- open disruptions and recovery status
- resilience score or explicit `Not calculated yet` state

When a state category is not yet backed by engine/API data, show an honest unavailable/not-yet-calculated state and document the missing source. Do not synthesize fake operational values in the UI.

---

## 1. Purpose

Build a read-only Supply Chain Dashboard that summarizes the team's supply-chain posture and routes users to decision pages for edits.

This dashboard should prove the E2E read path before full engine scoring is implemented.

---

## 2. Required Dashboard Cards

Minimum cards:

- supplier concentration by critical input category
- geographic concentration by supplier country
- lane exposure summary
- compliance regime exposure summary
- trade finance / FX posture summary
- inventory buffer summary
- latest SC event log, if any
- resilience score panel using API state if present, with a clear `Not calculated yet` state if absent

---

## 3. Data Rules

Use existing scenario-content and decision endpoints. Do not invent a new backend aggregation endpoint unless the builder verifies the existing endpoints make the dashboard unreasonably inefficient.

If an aggregation endpoint is added, it must be covered by backend tests and documented in the acceptance report.

---

## 4. Acceptance Criteria

1. Dashboard is reachable from navigation.
2. Dashboard reads real supplier/lane/compliance/decision data.
3. Empty state is professional and explicit when no decisions exist.
4. Cards route to relevant edit pages.
5. Dashboard does not claim a calculated resilience score unless `ResilienceScoreHistory` exists.
6. `npm run build` succeeds.
7. Browser verification is recorded in `specs/reports/cc-15/acceptance_report.md`.

---

## 5. Non-Scope

No engine scoring, event firing, or narrative generation belongs in CC-15.
