# GSP-R1-13 Independent Audit — Rework Required

Date: 2026-08-23  
Audited commit: `f24e9f4bfad3cd675822a0315c95437008748754`  
Audited deployment: `.5` VM, `~/projects/globalstrat+`  
Original contract: `gap_closing/rework/RW-01-round1-readiness-rework.md`

## Verdict

RW-1 is closed. RW-2 is substantially implemented, but its claimed strict ranking invariant has
an uncovered zero-floor failure. Round 1 readiness should remain **changes required** until the
bounded RW-2 correction and regression below land.

`gap_closing/` was read for the controlling contract and was not modified.

## Accepted evidence — do not redo

- Local `HEAD` and `origin/main` both equal `f24e9f4`.
- Game #19 still exists with its four original locked teams and persisted Round 1 results.
- Game #20 exists with four locked teams and two product-market rows per team.
- Game #20 persisted financial and PI results exactly match the closure report:
  - Nova Circuit: `$19,935,200.00`, `$8,929,294.16`, PI `60.69`.
  - Helix Digital: `$19,425,600.00`, `$10,675,358.48`, PI `59.45`.
  - Lumen Devices: `$13,259,200.00`, `$6,238,933.36`, PI `58.60`.
  - Apex Devices: `$0.00`, `-$1,665,000.00`, PI `55.23`.
- The 5.46-point spread and written ranking narrative satisfy RW-1.
- Fresh `core.tests.test_cc18_compliance`: 10/10 passed; the test database was created and
  destroyed during the independent run.
- `python3 manage.py check`: no issues.
- Gunicorn and the GlobalStrat FRP client are active.
- `https://globalstrat.camdani.com/` returns HTTP 200.

## Finding

### Medium — The zero-revenue invariant fails when the lowest selling-team PI is zero

`_enforce_zero_revenue_invariant` computes:

```python
ceiling = max(D('0'), min(positive_indexes) - D('0.01'))
```

If a positive-revenue team has `new_index == 0`, the ceiling is also zero. A zero-revenue team
whose raw PI is at or above zero is then persisted at zero as well. It is not strictly below the
positive-revenue team, contradicting all three of these stated contracts:

- the helper docstring: “Keep a zero-revenue firm below every firm that generated revenue”;
- the closure report: zero/negative revenue cannot be “at or above” the lowest positive-revenue
  PI;
- the regression assertion, which uses `assertLess`, not `assertLessEqual`.

The existing regression starts both teams at PI 100 and proves the historical high-fit anomaly,
but it does not exercise the lower bound. PI is clamped nonnegative, so subtracting 0.01 cannot
enforce a strict numeric ordering at that boundary.

Relevant locations:

- `backend/core/engine/performance.py:156-174`
- `backend/core/engine/performance.py:226-243`
- `backend/core/tests/test_cc18_compliance.py:267-322`
- `backend/core/models/results_financials.py:125` (`index_value` has two decimal places)

## Required correction

1. Decide and document how leaderboard ordering represents this impossible-at-zero numeric case.
   Viable approaches include an explicit revenue-aware ranking/tie-break rule or reserving a
   positive PI floor for revenue-generating teams. Do not persist a negative PI merely to satisfy
   the assertion unless the PI domain is intentionally changed everywhere.
2. Make the persisted result and leaderboard behavior agree.
3. Add a regression with:
   - at least one positive-revenue candidate whose calculated PI reaches zero;
   - a zero-revenue/high-fit candidate whose calculated PI would be zero or higher;
   - an assertion on the actual leaderboard order as well as persisted PI semantics.
4. Retain the existing Game-17-shaped regression; the boundary test supplements it.
5. Run the complete fresh-database compliance suite without `--keepdb`.

## Re-audit checklist

- [ ] Existing mutation-proven zero-revenue/high-fit regression still passes.
- [ ] New zero-floor regression passes and would fail without the correction.
- [ ] Zero-revenue teams cannot appear above positive-revenue teams when PI values reach zero.
- [ ] Persisted PI values and leaderboard ordering remain consistent and deterministic.
- [ ] Fresh `core.tests.test_cc18_compliance` suite passes without `--keepdb`.
- [ ] `python3 manage.py check` passes.
- [ ] Game #19 and Game #20 remain intact.
- [ ] `gap_closing/` remains untracked and unmodified.
- [ ] Corrective commit is pushed and deployed commit parity is verified.
- [ ] Public site and backend health checks pass.

## Final disposition

- RW-1: **PASS / closed**.
- RW-2 historical recurrence case: **PASS**.
- RW-2 invariant over its full stated domain: **REWORK REQUIRED** for the zero-floor boundary.

