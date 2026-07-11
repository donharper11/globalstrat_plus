# CC-23A Acceptance Report — GSCM Operational State Surfaces

**Spec:** `specs/CC-23A-gscm-operational-state-surfaces.md` · **Branch:** `cc-23A-gscm-operational-state-surfaces` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — coherence retrofit landed, real-browser verified (desktop + mobile).

## 1. Timing / prerequisites (§2)
CC-12, CC-13, CC-14, CC-15 all exist on `main` (verified). **Formal CC-22 E2E findings do not exist yet** — documented as an open dependency. Because CC-23A retrofits exactly the surfaces built this cycle, the §7 verification pass (below) provides the required state-visibility basis; the retrofit is not blind. See `state_inventory.md`.

## 2. Verify-Before-Wire (§7)
```
manage.py check → System check identified no issues (0 silenced).
```
Enumerated all 12 SC state models — **all registered and physically backed (no ghosts)**: `SourcingDecision/Allocation`, `LogisticsDecision`, `TradeFinanceDecision`, `FXHedgeDecision`, `HedgePosition`, `InventoryDecision`, `ContingencyPlan`, `SupplierState`, `LaneState`, `SCEventInstance`, `ResilienceScoreHistory`. Field lists recorded in `state_inventory.md`. Frontend routes/components verified before editing (App.js SC routes, Sidebar SC items, page files).

Key finding: `HedgePosition` has an existing read endpoint (`sc-hedge-positions`) unused by the UI; `LaneState`/`SupplierState` are modeled but have no read endpoint and are engine-populated (empty now).

## 3. What Was Built
- **`components/sc/scState.js` (new):** one shared operational-state vocabulary — `StateBadge` (current / draft / locked / readonly / unavailable), `StateLegend`, `pageState()`. Used identically across the dashboard and all four decision pages (§5, §11.5).
- **All four decision pages** (Sourcing, Logistics, Trade Finance, Inventory): added a **current/draft/locked/read-only** state badge in the header — "Current (saved)" when the on-screen values match the last load, "Draft — unsaved" once edited, "Locked"/"Read-only" per round/lock state. Implemented via a loaded-state snapshot compared to the live edit state (no new deps).
- **Supply Chain Dashboard:** added the `StateLegend`; surfaced **open FX positions** from the existing `HedgePosition` endpoint; added an **"Operational State (engine-generated)"** panel making the §4 engine categories visible as honest "Not available" states (shipment/lane movement → `LaneState`, supplier disruption/recovery → `SupplierState`+`SCEventInstance`, open FX positions → `HedgePosition`, inventory on-hand/on-order → not modeled), each naming its model and routed as a gap.
- **No backend endpoints added, no new models** (§8/§12): missing engine state is documented and routed to engine bundles rather than backed by endpoints over empty tables. No fake operational values (§6).

## 4. Build
`CI=false npx react-scripts build` → **Compiled**. eslint clean on all changed/new files. `manage.py check` → 0 issues. No backend changes, so no backend tests needed (§10).

## 5. Browser Verification (§10, §11.8)
Real production build in system Chromium (puppeteer-core), desktop (1300×1200) + mobile (390×844). Screenshots: `cc23a_dash.png`, `cc23a_draft.png`, `cc23a_mobile_dash.png`, `cc23a_mobile_log.png`. Results: `cc23a_results.json`.

| Requirement | Result | Evidence |
|---|---|---|
| Dashboard operational-state summary | ✅ | State legend + "Operational State (engine-generated)" panel with 5 "Not available" badges; FX open positions surfaced. |
| Logistics state panel | ✅ | Lane exposure card (modal split) + logistics page state badge; verified desktop + mobile. |
| Trade finance / FX exposure panel | ✅ | TF posture card + open FX positions (operational panel), `dash_fx_open_positions=true`. |
| Inventory / resilience state panel | ✅ | Inventory buffer card + resilience "Not calculated yet" (`dash_resilience_not_calc=true`). |
| Empty / not-yet-calculated states | ✅ | Trade finance / inventory / event empty states; resilience + engine categories "Not available". |
| Current vs draft distinction (§5) | ✅ | `page_current_badge=true` on load → edited an allocation → `page_draft_badge=true` ("Draft — unsaved"). |
| Mobile viewport (§9) | ✅ | `mobile_dash_rendered`, `mobile_logistics_rendered` true; **horizontal overflow = 0px** on both; cards stack cleanly (screenshot). |
| Runtime health | ✅ | `console_errors=[]`. |

Automated `dash_operational_section` returned false — false negative: the PanelCard title is CSS-uppercased so `innerText` reads "OPERATIONAL STATE (ENGINE-GENERATED)". The screenshot and the 5 rendered "Not available" badges confirm the section is present.

## 6. Acceptance Criteria (§11)
1. ✅ Operational-state inventory documented (`state_inventory.md`). 2. ✅ Every displayed value traces to a verified model/API (inventory table). 3. ✅ Missing categories shown honestly + listed as gaps. 4. ✅ Current/draft/locked/unavailable visually distinguishable (shared `StateBadge`). 5. ✅ Consistent labels across dashboard + decision pages (shared vocabulary). 6. ✅ No new/changed backend endpoints (so no backend tests required). 7. ✅ `npm run build` succeeds. 8. ✅ Desktop + mobile browser verification. 9. ✅ This report.

## 7. Non-Scope (§12) respected
No ERP integration, PO lifecycle, invoice matching, carrier tracking, FX MTM, resilience scoring, or new engine state generation. Missing state routed to engine/state bundles (CC-20 FX lifecycle, CC-21 resilience scoring, engine round-processing for LaneState/SupplierState).

## 8. Open dependency
Formal CC-22 E2E findings pending; this bundle's `state_inventory.md` serves as the interim state-visibility basis.
