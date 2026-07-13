# CC-20 Acceptance Report — FX Hedge Lifecycle

**Spec:** `specs/CC-20-fx-hedge-lifecycle.md` · **Rework:** W8 · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — the FX decision is no longer inert; full open→mark→settle→P&L lifecycle, tested.

## What changed
Previously `grep mark_to_market` returned nothing and no `HedgePosition` was ever
created — the FX decision persisted but did nothing. Now:
- `core/engine/fx_engine.py::process_fx_hedges` opens a `HedgePosition` from each
  FX hedge decision (locks the round's rate on `hedge_ratio%` of foreign
  receivables), marks every open position to market each round, and settles at
  maturity — booking realized P&L into `context.sc_fx_hedge_pnl`.
- `financials.py` adds that P&L to `pre_tax_income` (non-operating).
- `TradeFinancePage` gains an **Open FX hedge positions** panel (notional, locked
  rate, mark-to-market, realized P&L, status).

## Tests — `test_cc20_fx_engine` (5)
```
$ python3 manage.py test core.tests.test_cc20_fx_engine --noinput
Ran 5 tests ... OK
```
- `test_open_marktomarket_settle_gain` — open at rate 1.0 (notional = 100% of
  1,000,000 USD receivables, locked 1.0, MTM 0); on advance USD weakens to 0.9 →
  position matures with realized P&L **+100,000** (1,000,000 × (1.0 − 0.9)).
- `test_settle_loss_when_foreign_strengthens` — USD 1.0→1.1 → realized **−50,000**
  on a 50% hedge (correct opposite sign).
- `test_realized_pnl_flows_into_net_income` — with all other lines zero, the
  settled P&L (+100,000) becomes `net_income` = **100,000** (integration through
  the real `generate_financial_statements`).
- `test_no_basis_currency_is_skipped` — JPY_CNY (no JPY market) opens nothing.
- `test_zero_exposure_opens_nothing` — no foreign receivables → no position.

Full suite: **`Ran 143 tests … OK`**. `manage.py check` clean; frontend build clean.

## Honest scope
FX P&L is booked pre-tax but not re-taxed (tax is computed upstream from operating
figures — a deliberate simplification). Only receivables (short) hedges are
modelled. Currency pairs with no in-scenario market have no basis and are skipped
(logged, not faked).
