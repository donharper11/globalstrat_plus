# GSP-R1-14 — Zero-Floor Ranking Invariant Closure

Date: 2026-08-23  
Audit source: `handoffs_v3/reports/GSP-R1-13-independent-audit-rework.md`

## Finding and decision

The independent audit correctly identified that a nonnegative PI cannot be made strictly lower than a positive-revenue peer already at `0.00`. Persisting a negative PI would change the established PI domain and was rejected.

The invariant is therefore defined as an ordering rule:

> A zero-revenue team cannot outrank a positive-revenue team.

Above the zero floor, the existing performance guard persists the zero-revenue PI at least `0.01` below the lowest positive-revenue PI. At the `0.00` floor, both persisted PI values may equal `0.00`; leaderboard ordering breaks that tie in favor of positive revenue.

## Implementation

`core.engine.leaderboard.update_leaderboard` now uses this deterministic descending sort key:

1. persisted Performance Index;
2. whether total revenue is positive;
3. total revenue;
4. net income;
5. stable team ID.

Thus persisted PI and leaderboard behavior agree: PI remains within its nonnegative domain, and an equal-PI zero-floor tie is explicitly resolved by actual market performance. Additional revenue/net-income/team-ID keys make otherwise equal results deterministic and intelligible.

The performance guard docstring and GSP-R1-13 closure report were corrected to describe ordering rather than impossible strict numeric separation at zero.

## Boundary regression and mutation proof

Added:

`CC18ComplianceTest.test_zero_floor_uses_revenue_aware_leaderboard_tie_break`

The fixture starts both teams at PI zero. It gives the zero-revenue team dominant fit signals and places that team first in context order. The positive-revenue team receives weak fit and only `$1` revenue, making its calculated PI reach the zero floor.

Persisted semantics asserted:

- zero-revenue team PI: `0.00`;
- positive-revenue team PI: `0.00`.

Actual leaderboard semantics asserted:

- positive-revenue team: rank 1;
- zero-revenue team: rank 2.

With the new test installed but the old PI-only stable sort retained, the test failed:

```text
FAIL
AssertionError: 2 != 1
```

The positive-revenue team incorrectly received rank 2, proving the regression detects the boundary defect. With the revenue-aware tie-break installed, the identical test passed.

## Verification

Targeted boundary plus historical anomaly regressions:

```text
Ran 2 tests in 2.716s
OK
```

Fresh-database complete compliance suite:

```text
python3 manage.py test core.tests.test_cc18_compliance --noinput
Ran 11 tests in 3.070s
OK
```

`python3 manage.py check` reported no issues.

Games #19 and #20 remain intact. `gap_closing/` remains untracked and unmodified.

## Verdict

- RW-1: closed.
- RW-2 historical anomaly: closed.
- RW-2 zero-floor/full-domain ordering: closed.

Round 1 technical readiness satisfies the independent audit's bounded rework checklist.
