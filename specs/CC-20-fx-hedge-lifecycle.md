# CC-20 — FX Hedge Lifecycle

**Bundle:** CC-20 · **Depends on:** CC-9 (FX decision API), CC-13 (FX UI), CC-19B (P&L plumbing)
**Observes:** `STANDING-DISCIPLINE.md`, rework `REWORK_SPEC_2026-07-13.md` §4 W8
**Status:** Built (this rework).

## 1. Purpose
Before this, an `FXHedgeDecision` persisted but was **inert** in the engine — no
`HedgePosition` was ever created, no mark-to-market, no P&L. The FX decision was
pedagogically hollow. This closes the lifecycle: **open → mark-to-market per round
→ settle at maturity → book realized P&L.**

## 2. Model
An exporter with foreign-currency receivables is naturally LONG the foreign
currency, so a hedge **shorts** it forward, locking the rate. The hedge gains when
the foreign currency weakens (current rate < locked rate), offsetting the lower
spot revenue `calculate_revenue` books. Rates are the round's effective exchange
rates (`context.markets[*].effective_exchange_rate`, home-per-unit-foreign, which
already move per round via `MarketConditionByRound.exchange_rate_modifier` +
events).

- **Notional** = `hedge_ratio%` × the team's foreign-currency receivables in that
  currency this round (`market_revenue[*].local_revenue`).
- **Tenor** → `max(1, round(tenor_days / fx_days_per_round))` rounds (default 90
  days/round), capped at the last round.
- **MTM** = `notional × (locked_rate − current_rate)`.
- **Settle** at maturity → `realized_pnl`, booked into `pre_tax_income` (a
  non-operating financial item) via `context.sc_fx_hedge_pnl`.
- Currency pairs with no in-scenario market (e.g. JPY, GBP in the CE scenario)
  have no rate basis → no position (logged, not faked).

## 3. Implementation
- `core/engine/fx_engine.py::process_fx_hedges` — open/mark/settle. Runs after
  `calculate_revenue` (needs exposure), before `generate_financial_statements`
  (which reads the P&L). Wired in `advance_round` with the same fail-open + strict
  handling as the SC steps.
- `core/engine/financials.py` — `pre_tax_income = operating_income − interest +
  fx_hedge_pnl`.
- Frontend: `TradeFinancePage` gains an **Open FX hedge positions** panel showing
  notional, locked rate, mark-to-market, realized P&L, and status.

## 4. Acceptance
- `test_cc20_fx_engine` — open (locked rate + notional), MTM, settle with correct
  sign (gain when foreign weakens, loss when it strengthens), no-basis-currency
  skipped, zero-exposure opens nothing.
- Full suite green; `manage.py check` clean; frontend build clean.

## 5. Out of scope
FX P&L is booked pre-tax but the separate tax engine does not re-tax it (a
deliberate simplification — tax is computed upstream from operating figures).
Multi-leg / options hedging and speculative (long) hedges are not modelled; all
hedges are receivables (short) hedges.
