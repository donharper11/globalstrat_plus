# CC-23A Operational State Inventory

**Spec:** `specs/CC-23A-gscm-operational-state-surfaces.md` · **Observes:** `STANDING-DISCIPLINE.md`

Authoritative map of each GSCM operational-state category (spec §4) to its verified model/table, read endpoint, UI surface, and current availability. Every value shown in the UI traces to a row below; nothing is synthesized (§6).

Verified via `manage.py shell` (§7): all 12 SC models are registered **and physically backed** (no ghost models).

| # | State category (§4) | Source model → table | Read endpoint | UI surface | Status | Gap → owner |
|---|---|---|---|---|---|---|
| 1 | Supplier commitments | `SourcingAllocation`/`SourcingDecision` → `sc_sourcing_allocation`/`sc_sourcing_decision` | `GET …/sc/round/<r>/sourcing/` | Dashboard "Supplier concentration" + "Geographic concentration"; Sourcing page | **Visible** (decision state) | — |
| 2 | Inventory on hand | *(no model)* | — | Dashboard "Operational State" → "Not available" | **Unavailable (not modeled)** | engine/state bundle |
| 3 | Inventory on order | *(no model)* | — | Dashboard "Operational State" → "Not available" | **Unavailable (not modeled)** | engine/state bundle |
| 4 | Shipment / lane status | `LaneState` → `sc_lane_state` (`active_disruption`, `current_rate_modifier`) | *(none yet)* | Dashboard "Operational State" → "Not available"; Lane exposure shows decision modal mix | **Modeled, engine-populated, empty** | engine/round-processing bundle |
| 5 | Compliance state | `ComplianceRegime` → `sc_compliance_regime` + supplier `tier_2_3_profile.risk_flags` | `GET …/compliance-regimes/` + sourcing | Dashboard "Compliance regime exposure" (computes forced-labor/UFLPA flag from sourced suppliers) | **Visible** (scenario + decision-derived) | enforcement *holds* (event-driven) → engine bundle |
| 6 | Trade finance exposure | `TradeFinanceDecision` → `sc_trade_finance_decision` | `GET …/sc/round/<r>/trade-finance/` | Dashboard "Trade finance & FX posture"; Trade Finance page | **Visible** (decision state) | — |
| 7 | FX exposure — hedge decisions | `FXHedgeDecision` → `sc_fx_hedge_decision` | `GET …/trade-finance/` | Dashboard TF card "FX hedge decisions"; Trade Finance page | **Visible** (decision state) | — |
| 7b | FX exposure — open positions / MTM / P&L | `HedgePosition` → `sc_hedge_position` (`notional`, `locked_rate`, `mtm_current`, `realized_pnl`, `status`) | `GET …/sc/hedge-positions/` (existing) | Dashboard "Operational State" → "Open FX positions" (Current if any, else Not available) | **Modeled, engine lifecycle, empty** | FX lifecycle/MTM → CC-20 engine bundle (per §12) |
| 8 | Disruption / recovery | `SCEventInstance` → `event_… `/`sc_event_instance`; `SupplierState` → `sc_supplier_state` (`recovery_rounds_remaining`, `active_disruption_event`) | `GET …/sc/round/<r>/sc-events/` (+ no supplier-state ep) | Dashboard "SC event log" + "Operational State" → "Supplier disruption/recovery" | **Partially visible** (events exposed; supplier-state not) | engine bundle populates; supplier-state read ep deferred |
| 9 | Resilience state | `ResilienceScoreHistory` → `sc_resilience_score_history` (`score`, `components`, `weights_used`) | `GET …/sc/round/<r>/resilience-score/` | Dashboard "Resilience score" ("Not calculated yet" when null) | **Visible / honestly-absent** | score generation → CC-21 engine bundle (per §12) |

## Notes

- **No new backend endpoints were added.** Per §8, the retrofit reused existing endpoints; the two empty engine-state categories with models but no read endpoint (`LaneState`, `SupplierState`) are shown as honest "Not available" gaps rather than backed by endpoints over empty tables (§8 criterion 2 not met — no excessive stitching, and §12 routes missing engine state to an engine bundle). `HedgePosition` uses its existing `sc-hedge-positions` endpoint.
- **Current / Draft / Locked / Unavailable** vocabulary is centralized in `components/sc/scState.js` (`StateBadge`, `StateLegend`, `pageState`) and used identically on the dashboard and all four decision pages (§5, §11.5).
- **Follow-up gaps (route to engine/state bundles):** inventory on-hand/on-order (no model), lane movement/disruption population (`LaneState`), supplier disruption population + read endpoint (`SupplierState`), FX hedge lifecycle/MTM (`HedgePosition` fields exist; CC-20), resilience score generation (`ResilienceScoreHistory`; CC-21).
- **CC-22 dependency:** formal CC-22 E2E findings have not been produced yet. This inventory (from the §7 verification pass over the exact surfaces built in CC-10/12/13/14/15) provides the equivalent state-visibility basis, so the retrofit is not "blind." Recorded as an open dependency.
