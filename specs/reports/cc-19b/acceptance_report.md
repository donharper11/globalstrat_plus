# CC-19B Acceptance Report — Two-Channel Disruption Economics

**Spec:** `specs/CC-19B-two-channel-disruption-economics.md`
**Depends on:** CC-19. **Branch:** `main`. **Observes:** `STANDING-DISCIPLINE.md`.
**Status:** Complete — both channels flow through net income; verified live on the deployment.

---

## 1. Why

CC-19 collapsed all disruption impact into one scalar and deducted it straight
from `team.cash_on_hand`, calling it "cost." That conflated a **revenue** effect
(lost sales — foregone contribution margin) with an **expenditure** effect (freight
/ mitigation), and bypassed the P&L. CC-19B separates them and routes both through
net income.

## 2. Verify-Before-Wire (STANDING-DISCIPLINE §1)

Verified against the actual pipeline before editing:
- `calculate_revenue` books `units_sold` = Bass adopters (demand) and `units_produced`
  = the `production_volume` decision; **no supply-constraint on sales exists today** —
  so lost-sales-from-disruption is a *new* mechanic.
- **No product↔input BOM and no product↔lane BOM exist** (grep: `critical_input_category`
  appears only inside the SC layer). This forces the two modelling choices below.
- COGS (`calculate_cogs`) and logistics (`calculate_logistics_tariffs`) both read
  `rev['units_produced']` / `rev['units_sold']`, so throttling units in
  `calculate_revenue` cascades to them automatically.
- `generate_financial_statements` builds `operating_income` by subtracting a series
  of `getattr(context,'X',{}).get(team.id,0)` cost lines (retirement, tax-structure) —
  Channel 2 slots in as one more, idiomatically.

## 3. Modelling decisions (confirmed with product owner)

- **Liebig weakest-link:** production capacity factor `cf = min` availability across
  the team's critical inputs (`availability = Σ share×supplier_capacity / Σ share`).
- **Disruption-only (surgical):** `cf == 1` when nothing sourced is disrupted, so
  **no-disruption rounds are byte-identical** to pre-CC-19B (regression-safe).
- **Contingency feeds `cf`:** an alt-supplier rule rerouting a disrupted category to a
  *healthy* backup restores that share's availability (raising `cf`, cutting lost
  sales) at the price of a Channel-2 mitigation premium.

## 4. What was built

`core/engine/sc_engine.py` split into three pipeline steps:
- `run_sc_state(context)` — fires SC events, carries recovery forward, computes
  `context.sc_capacity_factor[team]`. Runs **before** `calculate_revenue`.
- `calculate_sc_disruption_costs(context)` — Channel 2: freight surcharge on disrupted
  lanes + backup/expedite mitigation premiums → `context.sc_disruption_costs[team]`.
- `score_sc_resilience(context)` — resilience score (unchanged formula) + per-team
  impact record. Runs **after** financials.

Integration edits:
- `revenue.py` — Channel 1: `cf<1` throttles `units_sold` and `units_produced` by the
  lost fraction; accumulates `context.sc_lost_revenue`.
- `financials.py` — subtracts `sc_disruption_costs` in `operating_income`.
- `advance_round.py` — reordered: `run_sc_state` after event/market steps;
  `calculate_sc_disruption_costs` before financials; `score_sc_resilience` at the end.
  All three best-effort (try/except) — an SC failure never crashes round processing.
- **Removed** the CC-19 direct `cash_on_hand` poke and the single "disruption cost" scalar.

## 5. Tests (`core/tests/test_cc19_sc_engine.py`, 7 tests)

- `test_state_generation_fires_and_populates` — forced event → SupplierState + `cf` map.
- `test_capacity_factor_liebig` — `cf` = min (0.4 with a healthy second category present,
  **not** the 0.7 average); no disruption → 1.0.
- `test_capacity_factor_contingency_restores` — 50% reroute to a healthy backup → `cf = 0.7`.
- `test_channel1_lost_sales_throttles_revenue` — `cf=0.6` → units 1000→600, produced
  1000→600, `sc_lost_revenue>0`; **no disruption → units unchanged** (surgical guarantee).
- `test_channel2_disruption_costs_booked` — freight + mitigation both >0 and sum correctly;
  no disruption → 0.
- `test_resilience_scored_and_recorded`, `test_seed_deterministic`.

**Full suite: 132 tests, OK** (was 129). The suite includes CC-22 `test_07`, a real
`advance_round` through the entire modified pipeline — crash-free. No-disruption
regression safety confirmed by the unchanged financial/engine tests.

## 6. Live verification (deployed :8012, real CE data)

Restarted the globalstrat+ gunicorn to load the new code, then on the demo game:

**Full pipeline, real `advance_round`:** ran crash-free — SC events fired, 5 suppliers
disrupted, resilience scored for all teams, `RoundResultFinancials` written, and
**cash moved only via net income (no direct poke).**

**Channel 1 (real round-2 adoptions), Team A sourcing a supplier disrupted to 40%:**
```
capacity_factor = 0.4
baseline  (cf=1)   revenue = 32,000,000   units_sold = 50,000   units_produced = 50,000
disrupted (cf=0.4) revenue = 12,800,000   units_sold = 20,000   units_produced = 20,000
Channel-1 lost sales = 19,200,000   (sc_lost_revenue accumulator = 19,200,000)
```
Units sold **and** produced both fall to 40% → COGS falls with revenue → the net-income
hit is the lost *contribution margin*, not gross revenue.

**Channel 2 (Team A on a disrupted sea lane, rate ×2.0):**
```
disruption cost = 200,000   (freight = 200,000, mitigation = 0)  → booked in operating_income
```

## 7. Known bounds (documented, not silent)

- **Per-team impact reporting for multi-round disruptions:** the per-team
  `{lost_revenue, disruption_cost, capacity_factor}` record is attached to the
  `SCEventInstance` that fired that round. A disruption that persists via recovery
  carry-forward (no new event) still causes lost sales / costs through the P&L every
  round, but those later rounds have no instance to attach the record to, so the
  dashboard's SC-event view shows the impact only for the firing round. Economics are
  unaffected; this is a reporting follow-up (surface ongoing per-team impact alongside
  the resilience score).
- **Channel-2 anchors:** `FREIGHT_SURCHARGE_BASE` / `MITIGATION_PREMIUM_BASE` are
  documented tunable constants (no product↔lane BOM exists to price per-shipment).

## 8. Acceptance criteria (spec §9)

| Criterion | Status |
|---|---|
| Lost sales via revenue (revenue **and** COGS fall) | ✅ live 32M→12.8M, units 50k→20k |
| Real costs booked in the P&L, not cash | ✅ freight 200k in operating_income; no cash poke |
| Liebig weakest-link `cf` | ✅ test + live (0.4) |
| Disruption-only (no-disruption rounds identical) | ✅ full suite green; surgical test |
| Contingency restores `cf` | ✅ `cf=0.7` on 50% reroute |
| Never crashes round processing | ✅ best-effort hooks; real advance crash-free |
| Full suite green | ✅ 132 tests OK |
