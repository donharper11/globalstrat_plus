# CC-19B — Two-Channel Disruption Economics

**Depends on:** CC-19 (SC engine — event firing, contingency, resilience).
**Observes:** `STANDING-DISCIPLINE.md`.
**Problem:** CC-19 collapsed all disruption impact into one scalar and deducted it
straight from `team.cash_on_hand`, labelling it "cost." That conflated two
economically distinct effects and bypassed the P&L. This spec models them
properly and routes both through net income.

## 1. The two channels

A supply-chain disruption produces two different economic effects:

1. **Lost sales (a revenue effect).** A supplier's capacity is knocked out, so
   the team cannot obtain the input, cannot build the units, and does not sell
   them. This is foregone **contribution margin**, hitting the top line — *not* a
   cash expenditure. Modelled by capping units, so revenue **and** COGS both fall
   and net income drops by exactly the lost contribution margin.

2. **Real costs (an expenditure effect).** Freight rates spike on disrupted
   lanes; the team pays expedite / backup-supplier premiums to reroute. These are
   genuine cash outflows and belong in operating costs → COGS/opex.

## 2. Modelling decisions (confirmed with product owner)

- **Input→output mapping = Liebig weakest-link.** There is no product↔input
  bill-of-materials in the model. A team's *production capacity factor* `cf` is
  the **minimum** availability across the critical inputs it sources. One badly
  hit input throttles the whole output. (`availability(category) = Σ (allocation
  share × supplier capacity), normalised by total share`; `cf = min over
  categories`.)
- **Scope = disruption-only (surgical).** `cf` is 1.0 whenever nothing the team
  sources is disrupted, so **normal rounds are byte-identical to today** — this
  introduces no general stockout mechanic. Lost sales apply only to the shortfall
  `(1 − cf)`.
- **Contingency feeds `cf`.** An alt-supplier rule that reroutes a disrupted
  category's allocation to a *healthy* backup restores that share's availability,
  lifting `cf` and reducing lost sales — at the price of a Channel-2 mitigation
  premium. This is the real trade-off the mechanic teaches.

## 3. Pipeline placement (`advance_round._run_phase_1`)

CC-19 ran the whole engine *last*. It is split so state exists before revenue:

| Step | Function | When |
|---|---|---|
| Generate disruption state + `cf` | `run_sc_state(context)` | **before** `calculate_revenue` (after event/market steps) |
| Channel 1 — throttle units | inside `calculate_revenue` | reads `context.sc_capacity_factor` |
| Channel 2 — freight + mitigation costs | `calculate_sc_disruption_costs(context)` | during cost phase, **before** `generate_financial_statements` |
| Book Channel-2 cost line | `generate_financial_statements` | subtracts `context.sc_disruption_costs[team]` in `operating_income` |
| Resilience score (read-only) | `score_sc_resilience(context)` | **after** financials |

## 4. Channel 1 — lost sales (in `calculate_revenue`)

For each product/market of a team with `cf < 1`:
```
lost_units      = round(units_sold × (1 − cf))
units_sold     -= lost_units                       # revenue falls
units_produced -= lost_units   (floor 0)           # COGS falls (didn't build them)
```
`units_sold` also drives logistics cost and `units_unsold` (inventory), so those
fall consistently. Net-income impact = `lost_units × (price·margin·fx − unit_cost
− unit_logistics)` = lost contribution margin. Lost revenue is accumulated in
`context.sc_lost_revenue[team]` for reporting.

## 5. Channel 2 — real costs (`calculate_sc_disruption_costs`)

Team-level (no product↔lane BOM exists, so per-shipment attribution is not
possible; team-level is the honest granularity):
```
freight    = Σ_lanes  sea_share × (lane_rate_modifier − 1) × FREIGHT_SURCHARGE_BASE
mitigation = Σ applied alt-supplier reroutes:  shifted_share × alloc_share × MITIGATION_PREMIUM_BASE
           + Σ applied mode-switches:          shifted_share × sea_share   × MITIGATION_PREMIUM_BASE
context.sc_disruption_costs[team] = freight + mitigation
```
Booked as an operating expense line in `operating_income` → `net_income` → cash.
`FREIGHT_SURCHARGE_BASE` / `MITIGATION_PREMIUM_BASE` are documented tunable
anchors (kept modest vs ~$50M starting cash), not derived from real volumes.

## 6. What is removed

- The direct `team.cash_on_hand -= disruption_cost` poke (CC-19).
- The single "disruption cost" scalar. `SCEventInstance.resolution_data.team_impact`
  now records `{lost_revenue, disruption_cost, capacity_factor, applied}` split by
  channel.

## 7. Determinism & safety

- Event firing / draws remain seeded by `(game, round, scenario)`.
- Every hook is guarded: `cf == 1` and `sc_disruption_costs.get(team, 0)` default
  to no-ops, so a game with no SC disruption is unchanged (regression-safe).
- `run_sc_state` and cost/score steps are best-effort in `_run_phase_1`
  (try/except); an engine failure never crashes round processing.

## 8. Tests (`test_cc19_sc_engine.py`)

1. State generation: forced event fires → `SupplierState`/`LaneState` populated.
2. `cf` = Liebig minimum; a single disrupted single-source input → `cf < 1`;
   undisrupted → `cf == 1`.
3. Lost sales: disrupted team's revenue **and** COGS fall; net income drops by
   the lost contribution margin; **no disruption → revenue identical** (surgical).
4. Contingency restores `cf`: team with a healthy-backup rule has higher `cf`
   (fewer lost sales) than an unprotected team, and carries a mitigation cost.
5. Channel 2: `sc_disruption_costs` booked; net income reflects it.
6. Resilience still scored; `_seed` deterministic.
7. Full suite green (existing engine/financial tests unchanged).

## 9. Acceptance

- Both channels flow through net income; no direct cash poke remains.
- No-disruption rounds identical to pre-CC-19B (proven by full suite).
- Liebig + disruption-only + contingency-restores-cf behave as specified.
- Verified live on the running deployment.
