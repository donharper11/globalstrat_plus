# CC-23A: GSCM Operational State Surfaces

**Project:** globalstrat+  
**Spec Type:** Retrofit / platform coherence - operational state UI  
**Depends on:** CC-12, CC-13, CC-14, CC-15, initial CC-22 findings  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted for builder execution after active frontend bundles land

---

## Non-Negotiable Builder Discipline

This bundle inherits `STANDING-DISCIPLINE.md`, but the following rules are repeated here because they are completion blockers:

1. Verify every existing field, model, table, endpoint, route, component, settings key, and payload shape before referencing it. Use the current codebase and database, not memory or nearby names.
2. Do not invent field names, model names, endpoint paths, YAML keys, payload keys, CSS classes, or React component names. If the expected name does not exist, halt with a MISMATCH report.
3. Do not silently adapt the spec to whatever name seems convenient. Report the actual state and wait for instruction if the contract and implementation diverge.
4. Before calling the bundle complete, self-verify every acceptance criterion with recorded command output, API/browser evidence, and a closeout report under `specs/reports/cc-23A/`.
5. A passing backend response alone is not proof of frontend completion. This bundle requires browser verification of the actual student and instructor-facing workflows it touches.

---

## 1. Purpose

Retrofit the GSCM frontend so it reads like a simulated operating system, not a collection of disconnected decision forms.

GlobalStrat+ is not an ERP because it is not a real enterprise system of record and does not integrate live procurement, warehouse, shipment, finance, or vendor systems. But a supply-chain simulation still needs ERP-shaped operating mirrors: students must see simulated commitments, inventory, shipment/lane status, compliance flags, financial exposure, and disruption consequences that result from decisions and stakeholder/engine responses.

CC-23A makes that operational-state layer coherent across the decision pages and dashboard after the first frontend build passes have landed.

---

## 2. Timing and Non-Interference

Do not execute CC-23A while CC-12, CC-13, or CC-14 builders are in flight.

Execute after:

1. CC-12 Logistics & Distribution page exists.
2. CC-13 Trade Finance & FX page exists.
3. CC-14 Inventory & Resilience page exists.
4. CC-15 Supply Chain Dashboard exists or has produced explicit gaps.
5. Initial CC-22 E2E findings identify what state is visible and what is missing.

If any prerequisite is absent, halt and report the missing bundle rather than retrofitting blind.

---

## 3. Scope

Inspect and, where verified data exists, improve these surfaces:

- Supply Chain Dashboard
- Sourcing & Suppliers page
- Logistics & Distribution page
- Trade Finance & FX page
- Inventory & Resilience page
- Any shared SC API client helpers
- Any backend read endpoint required to expose already-modeled state

This bundle may add small read-only aggregation endpoints if the existing API cannot reasonably support operational-state display. Any new endpoint must be backed by verified models/tables and covered by tests.

---

## 4. Operational State Categories

The retrofit should make the following categories visible where model/API state exists:

| Category | Expected student-facing meaning |
|---|---|
| Supplier commitments | Current and proposed allocation/volume commitments by input category and supplier |
| Inventory on hand | Simulated available inventory by product/market when engine/state exists |
| Inventory on order | Simulated committed or inbound inventory when engine/state exists |
| Shipment/lane status | Lane disruption, delay, mode mix, chokepoint, or simulated movement status |
| Compliance state | Holds, flags, enforcement risk, regime exposure, mitigation status |
| Trade finance exposure | Payment instrument exposure, credit insurance coverage, LC/document risk |
| FX exposure | Hedge decisions, open hedge positions, maturity/MTM/P&L only if lifecycle state exists |
| Disruption/recovery state | Open SC events, affected suppliers/lanes/markets, recovery status |
| Resilience state | Score/components if calculated; explicit not-yet-calculated state otherwise |

---

## 5. Current vs Draft vs Locked State

Every touched decision surface must clearly distinguish:

- **Current state:** last locked/submitted state or engine-generated operational state.
- **Draft/proposed state:** unsaved or editable values currently on screen.
- **Locked state:** values already locked for the round and not editable by students.
- **Unavailable state:** data category not yet implemented or not yet calculated.

Do not blur these states. A user must be able to tell whether they are looking at simulated reality, a draft decision, or a missing calculation.

---

## 6. No Fake Operational Values

Do not synthesize fake operational values just to make the UI look complete.

Allowed:

- showing verified decision values
- showing verified engine/state values
- showing `Not calculated yet`, `No shipment state available`, or equivalent explicit unavailable states
- adding read-only aggregation over existing verified models

Not allowed:

- random inventory values
- made-up shipment statuses
- fake hedge P&L
- fabricated compliance holds
- UI-only resilience scores that do not trace to `ResilienceScoreHistory` or a verified calculation

---

## 7. Verification Before Editing

Run and record:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py check
python3 manage.py showmigrations core | tail -20
python3 manage.py shell <<'CHECK'
from django.apps import apps
for label in [
    'core.SourcingDecision', 'core.SourcingAllocation', 'core.LogisticsDecision',
    'core.TradeFinanceDecision', 'core.FXHedgeDecision', 'core.HedgePosition',
    'core.InventoryDecision', 'core.ContingencyPlan', 'core.SupplierState',
    'core.LaneState', 'core.SCEventInstance', 'core.ResilienceScoreHistory',
]:
    model = apps.get_model(label)
    print(label, model._meta.db_table, [f.name for f in model._meta.get_fields()])
CHECK
```

For frontend routes/components, verify actual names before editing:

```bash
cd /home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend
grep -rn "path=\|Route\|Sidebar\|Supply" src/App.js src/components src/pages src/api --include='*.js' --include='*.jsx'
```

If any expected field, model, route, or component does not exist, halt with a MISMATCH report.

---

## 8. Backend Rules

Prefer existing endpoints first. Add backend read endpoints only when:

1. The required state already exists in verified models/tables.
2. The frontend would otherwise need excessive multi-call stitching.
3. The endpoint has a focused read-only purpose.
4. Tests cover response shape and empty-state behavior.

Do not add new persistent state models in CC-23A unless explicitly authorized after a MISMATCH report. Missing operational state belongs in an engine/state-generation bundle, not a UI retrofit.

---

## 9. Frontend UX Rules

Use the existing GlobalStrat design patterns and Ant Design components. Keep the pages operational and scan-friendly:

- compact status panels
- tables for commitments/exposures
- badges for state/severity
- clear empty/unavailable states
- links back to relevant decision forms
- no marketing hero sections
- no decorative dashboards with fake completeness

Mobile compatibility must be checked for every touched page.

---

## 10. Tests and Verification

Minimum verification:

Backend, if any endpoint is added or changed:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py check
python3 manage.py test <focused_test_module> --verbosity=2
python3 manage.py test --verbosity=1
```

Frontend:

```bash
cd /home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend
npm run build
```

Browser verification must cover:

- dashboard operational state summary
- at least one logistics state panel
- at least one trade finance / FX exposure panel
- at least one inventory/resilience state panel
- empty/not-yet-calculated states
- mobile viewport for each touched page

---

## 11. Acceptance Criteria

CC-23A is complete when:

1. Operational-state inventory is documented in `specs/reports/cc-23A/state_inventory.md`.
2. Every displayed operational value traces to a verified model/API source.
3. Missing state categories are shown honestly and listed as follow-up gaps.
4. Current/draft/locked/unavailable states are visually distinguishable.
5. Dashboard and decision pages use consistent labels for the same state concepts.
6. Backend tests pass for any new or changed read endpoints.
7. `npm run build` succeeds.
8. Browser verification confirms desktop and mobile workflows.
9. `specs/reports/cc-23A/acceptance_report.md` records commands, outputs, screenshots or browser notes, and remaining gaps.

---

## 12. Non-Scope

CC-23A does not implement:

- ERP integrations
- real purchase order lifecycle
- invoice matching
- warehouse-bin logic
- real carrier tracking
- FX hedge mark-to-market unless CC-20 has already implemented lifecycle state
- resilience scoring unless CC-21 has already implemented score generation
- new simulation engine state generation

If the UI needs a state value that the engine does not generate, document the gap and route it to the appropriate engine/state bundle.
