# CC-15 Acceptance Report — Supply Chain Dashboard

**Spec:** `specs/CC-15-supply-chain-dashboard.md` · **Branch:** `cc-15-supply-chain-dashboard` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met, real-browser verified.

## 1. Verify-Before-Wire
Verified all read endpoints against the running code/DB: scenario-content (`/scenarios/<id>/suppliers|lanes|compliance-regimes/`), decision GETs (sourcing/logistics/trade-finance/inventory), and SC engine state — `ResilienceScoreView` returns `{score:null, components:{}, weights_used:{}}` when no `ResilienceScoreHistory` exists; `SCEventsView` returns a list of `SCEventInstance` (`event_template` is an id). **No new backend aggregation endpoint was added** — the dashboard aggregates client-side from existing endpoints (§3), which is efficient (≤9 parallel GETs).

## 2. What Was Built
- `pages/SupplyChainDashboard.js` (new, read-only): cards for resilience score, supplier concentration by critical input, geographic concentration by supplier country, lane exposure, compliance regime exposure (with computed forced-labor/UFLPA flag from sourced suppliers' `risk_flags`), trade finance/FX posture, inventory buffer, and SC event log. Each editable card links to its decision page. Loads via `Promise.all` with per-endpoint error tolerance; honest empty/`Not calculated yet` states everywhere.
- `api/sc.js`: `getComplianceRegimes`, `getResilienceScore`, `getSCEvents`.
- `App.js` route (`/games/:gameId/teams/:teamId/sc-dashboard`) + `Sidebar.js` nav item (top of Decisions group, `faChartPie`).

**Operational State Mirror (spec requirement):** synthesizes no fake operational values. Categories not yet backed by engine data render explicit unavailable states — resilience ("Not calculated yet — engine computes after round processing"), and inventory-on-hand / shipment-status / open-disruptions are represented only by the decision-level data that exists (buffer settings, lane modal mix, SC event log), which is documented as decision-state rather than live engine state.

## 3. Build
`CI=false npx react-scripts build` → **Compiled** (`+2.64 kB`). eslint clean on changed files. `manage.py check` → 0 issues.

## 4. Browser Verification (§4.7, STANDING-DISCIPLINE §5.5)
Real production build in system Chromium (puppeteer-core). Mixed fixture: sourcing (TSMC 60% + Xinjiang-flagged SMIC 40%) and logistics populated; trade-finance/inventory empty; resilience `score:null`; no events. Screenshot: `cc15_01.png`. Results: `cc15_results.json`.

| Criterion | Result | Evidence |
|---|---|---|
| §4.1 Reachable from nav | ✅ | `nav_reachable=true`; sidebar item (screenshot). |
| §4.2 Reads real supplier/lane/compliance/decision data | ✅ | Supplier concentration (Semiconductor, 2 suppliers, top share 60%), geographic (TW 60% / CN 40%), lane exposure (`cn_shanghai_to_us_long_beach` sea 80%·air 20%), all 5 compliance regimes, and **computed UFLPA exposure** naming the flagged supplier — all from real endpoint data. |
| §4.3 Professional/explicit empty state | ✅ | `trade_finance_empty_state`, `inventory_empty_state`, `sc_events_empty_state` all true (screenshot). |
| §4.4 Cards route to edit pages | ✅ | `card_route_clicked=true`, `routed_to_sourcing=true` (clicked "Manage sourcing" → `/decisions/sourcing`). |
| §4.5 No calculated resilience unless history exists | ✅ | `resilience_not_calculated=true`; card shows "Not calculated yet" (screenshot). |
| Runtime health | ✅ | `console_errors=[]`. |

Automated `geographic_concentration` / `single_source_or_share` returned false — false negatives: PanelCard titles and Table headers are CSS-uppercased, so `innerText` reads "GEOGRAPHIC CONCENTRATION" / "TOP SUPPLIER SHARE". The screenshot confirms both cards render correctly.

## 5. Acceptance Criteria
1. ✅ Reachable from nav. 2. ✅ Reads real data. 3. ✅ Explicit empty states. 4. ✅ Cards route to edit pages. 5. ✅ No calculated score without `ResilienceScoreHistory`. 6. ✅ `npm run build` succeeds. 7. ✅ Browser verification recorded. No engine scoring / event firing / narrative (§5 respected).
