# GSP-R1-13 — Round 1 Readiness Rework Closure

Date: 2026-08-23  
Rework source: `gap_closing/rework/RW-01-round1-readiness-rework.md`  
Verification game: #20, Round 1

## Summary

RW-1 and RW-2 are resolved. Game #20 used four materially divergent, predeclared strategies and produced a 5.46-point PI spread with a defensible ordering. A new direct recurrence test recreates the Game #17 symptom shape: a zero-revenue team receives dominant fit/non-financial signals while a peer produces positive revenue. The test was demonstrated failing before the guard was installed and passing afterward.

## RW-2 — Direct invariant and mutation proof

`core.engine.performance.calculate_performance_index` now calculates all team candidates before persistence and enforces this round-level rule, supplemented by the GSP-R1-14 zero-floor tie-break:

> When at least one team has positive revenue, a team with zero or negative revenue cannot outrank the lowest positive-revenue team.

If the raw composite would violate the rule, the zero-revenue PI is capped at 0.01 below the lowest positive-revenue PI. At the nonnegative `0.00` PI floor, strict numeric separation is impossible; GSP-R1-14 permits equal persisted PI values and uses an explicit revenue-aware leaderboard tie-break so the selling team ranks first. The raw composite remains in `satisfaction_score`; `index_change` and `index_value` record the guarded result, and the engine log explicitly records `zero-revenue ranking guard applied`.

New regression:

`CC18ComplianceTest.test_zero_revenue_high_fit_team_cannot_outrank_positive_revenue_team`

The fixture gives the zero-revenue team fit/adjusted-fit values of 1.0 and the selling team values of 0.0, recreating the original anomaly's non-financial dominance rather than depending on a compliance freeze.

Mutation proof, with the test installed and guard absent:

```text
FAIL
AssertionError: Decimal('101.11') not less than Decimal('99.97')
```

Identical test after the guard was installed:

```text
Ran 1 test in 2.795s
OK
```

Fresh-database full-suite proof:

```text
python3 manage.py test core.tests.test_cc18_compliance --noinput
Ran 10 tests in 3.306s
OK
```

`python3 manage.py check` reported no issues.

## RW-1 — Divergent decision design

Created game #20 with `python3 manage.py setup_test_game` without `--flush`. Game #19 was left intact. All teams received North America customs documentation. Every submission passed `DecisionLockView._full_validate`, all four locked, and Round 1 processed in 5.4 seconds without errors.

All values below are per product; each team marketed two products in North America.

| Team | Strategy | Prices | Promotion | Distribution | Sales team | Production |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Nova Circuit | Aggressive balanced growth | $949 / $649 | $600k each | $300k each | 12 each | 16,000 / 15,000 |
| Helix Digital | Premium margin | $1,499 / $1,199 | $450k each | $250k each | 8 each | 9,000 / 9,000 |
| Lumen Devices | Value volume | $799 / $499 | $250k each | $100k each | 5 each | 12,000 / 14,000 |
| Apex Devices | No-production control | $1,099 / $799 | $0 | $0 | 0 | 0 / 0 |

The expected broad ordering was growth or premium first, value-volume in the middle, and no-production last. The precise first/second ordering was intentionally left to the composite because the growth strategy should lead market/capability signals while premium should lead profit quality.

## Results

| Rank | Team | Strategy | Product-market rows | Revenue | Net income | Net margin | PI |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Nova Circuit | Aggressive balanced growth | 2 | $19,935,200.00 | $8,929,294.16 | 44.79% | 60.69 |
| 2 | Helix Digital | Premium margin | 2 | $19,425,600.00 | $10,675,358.48 | 54.96% | 59.45 |
| 3 | Lumen Devices | Value volume | 2 | $13,259,200.00 | $6,238,933.36 | 47.05% | 58.60 |
| 4 | Apex Devices | No-production control | 2 | $0.00 | -$1,665,000.00 | N/M | 55.23 |

PI spread: `60.69 - 55.23 = 5.46` points.

All four teams have persisted financial, PI, leaderboard, and product-market rows. No compliance events fired. The no-production rows correctly contain zero units and zero revenue and rank last below every positive-revenue team.

## Rank narrative

1. **Nova Circuit — aggressive balanced growth.** It funded the largest promotion, distribution footprint, sales force, and production plan. It sold all 31,000 units, generated the most revenue ($19.94M), and achieved broad adoption across premium, value, and enterprise segments. The strategy's scale and breadth justify first place even though its heavy spending reduced margin relative to Helix.
2. **Helix Digital — premium margin.** It charged materially higher prices and limited production to 18,000 units. It generated nearly Nova's revenue on 42% fewer units, the highest net income ($10.68M), and the highest net margin (54.96%). Second place is defensible because superior financial discipline is balanced against Nova's stronger market scale/capability signals.
3. **Lumen Devices — value volume.** Lower prices and moderate commercial investment produced 26,000 sales and strong Value Seeker fit, but revenue and profit trailed both leaders. Its middle rank follows directly from successful volume with weaker monetization and a smaller go-to-market commitment.
4. **Apex Devices — no-production control.** It committed no promotion, distribution, sales staff, or production. It recorded no adoption, no revenue, and a $1.665M loss. Last place is mandatory and observed; it did not outrank any positive-revenue team.

## Acceptance result

### RW-1

- Fresh four-team game locked and processed: PASS.
- Materially different decision inputs documented: PASS.
- Discriminating PI spread: PASS, 5.46 points.
- Written decision/result narrative for each rank: PASS.
- No zero/negative-revenue team above a positive-revenue team: PASS.
- Exact results captured: PASS.

### RW-2

- New GSP-R1 regression test committed with implementation: PASS.
- Zero-revenue/high-fit anomaly shape constructed: PASS.
- Direct persisted-PI ordering invariant asserted: PASS.
- Test shown failing without guard and passing with guard: PASS.
- Full suite passes on a fresh test database: PASS, 10/10.

Verdict: the two findings in RW-01 are closed. Round 1 technical readiness is an unconditional PASS, subject only to the already separate platform-owner approval of the live-rehearsal protocol.
