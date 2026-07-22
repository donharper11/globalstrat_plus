# GSP-R1-11 — Performance Index Composite Reweighting

Date: 2026-07-23

## Summary

Changed the Round 1 Performance Index from a mostly segment-satisfaction delta to a five-part strategic-management composite:

- Market performance: 30%
- Strategic capability: 25%
- Financial discipline: 15%
- Stakeholder confidence: 15%
- Execution resilience: 15%

The persisted `RoundResultPerformanceIndex.satisfaction_score` field now stores the final composite score because the current model does not yet have component-level columns.

## Implementation Notes

- `backend/core/engine/performance.py` now calculates component scores with explicit helpers.
- Market performance combines customer fit and relative revenue.
- Strategic capability uses submitted R&D effort plus product/platform and strategic action signals.
- Financial discipline uses relative revenue, net income strength, and debt-to-equity discipline.
- Stakeholder confidence uses non-customer segment fit and active-market compliance freeze penalties.
- Execution resilience uses supply-chain capacity/disruption signals and active-market freeze penalties.
- Compliance freezes outside a team's active markets are ignored for PI freeze penalties. This avoids letting the already identified inactive-market compliance noise flatten every team's stakeholder/resilience score.
- Engine logs now include the five component scores per team.

## Verification

Passed:

- `python3 manage.py check`
- `python3 manage.py test core.tests.test_cc18_compliance.CC18ComplianceTest --verbosity=2`

Regression added:

- `test_performance_index_composite_rewards_financials_and_penalizes_freeze`

This proves the new composite rewards stronger revenue/profit under otherwise similar conditions, and that an active-market compliance freeze lowers the affected team's PI.

## Read-Only Replay: Game 18, Round 1

Using the already processed controlled Round 1 data:

| Team | Replay PI | Old PI | Revenue | Net Income | Active Freezes | Market | Capability | Financial | Stakeholder | Resilience |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lumen Devices | 57.54 | 51.60 | $17,864,400 | $9,471,384 | 0 | 0.449 | 0.750 | 0.995 | 0.036 | 1.000 |
| Nova Circuit | 57.52 | 51.63 | $13,184,400 | $5,316,300 | 0 | 0.345 | 0.990 | 0.798 | 0.036 | 1.000 |
| Solaris Consumer | 56.36 | 51.63 | $13,184,400 | $5,837,700 | 0 | 0.345 | 0.750 | 0.811 | 0.037 | 1.000 |
| Meridian Tech | 52.44 | 49.81 | $0 | -$4,095,000 | 1 | 0.000 | 0.810 | 0.309 | 0.000 | 0.820 |

## Interpretation

The new mix creates a wider and more defensible spread: Meridian is clearly last after the compliance freeze and zero sales, while Lumen's revenue/profit advantage moves it to the top. Nova remains very close to Lumen because its strategic capability signal is stronger in this run.

This is directionally better for a strategic management course: revenue/profit matter, but they do not fully dominate capability and stakeholder/resilience logic.

## Carry-Forward

- A future model migration should store component scores explicitly instead of overloading `satisfaction_score`.
- The compliance engine still needs a separate cleanup so customs enforcement does not generate noisy inactive-market events.
- The replay has sparse persisted stakeholder data, so the next live processed game should be reviewed through the real engine log component lines.
