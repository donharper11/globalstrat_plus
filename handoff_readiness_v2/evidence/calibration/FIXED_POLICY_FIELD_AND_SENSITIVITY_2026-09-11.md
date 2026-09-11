# CRV2-11 fixed-policy field-size and sensitivity measurement

## Scope and rule held fixed

This measurement implements the competition owner's 2026-09-11 decision:
**Fix A only**. AI take remains in the competitive-attractiveness denominator
and is recorded, but only human adoption is cumulative Bass `N`.

No scenario, profile, market, AI, or scoring parameter was retuned. Every
replay uses Consumer Electronics 2026, all teams assigned to NA, and the
existing competent policy with its deterministic 10% historical sales
production buffer. The sensitivity runs change exactly one price, promotion,
production, or staffing decision for team index 0; every other team remains on
that same policy.

The evidence was produced at `a521f7a259cb022d5d77ff8592f38b869c71bec9` by:

```bash
backend/scripts/run-calibration-postgres \
  --output handoff_readiness_v2/evidence/calibration/fixed_policy_measurements.json
```

That wrapper creates a local Docker PostgreSQL 16 container with a generated
credential, and the replay creates then force-drops a separate database for
each run. It neither reads nor needs the production systemd secret.

## Field-size / saturation result

All five ten-round replays reconcile, to cents, for every segment-market:
`human + AI + unserved = Bass pool`. The table is the whole-economy round-10
result; HHI is human team-unit-sales concentration (lower is less concentrated).

| teams | human adopters | AI adopters | unserved | human share | sales HHI |
|---:|---:|---:|---:|---:|---:|
| 4 | 290,996.00 | 2,836,850.09 | 449,241.64 | 9.17% | 0.271573 |
| 6 | 406,733.00 | 2,809,352.98 | 438,567.08 | 12.82% | 0.181545 |
| 8 | 499,873.00 | 2,790,378.61 | 359,971.97 | 15.75% | 0.129876 |
| 10 | 555,496.00 | 2,778,833.43 | 331,381.92 | 17.51% | 0.103373 |
| 12 | 666,358.60 | 2,770,194.65 | 234,713.92 | 20.99% | 0.085803 |

The intended 4–12-team heat range therefore runs without a conservation,
capacity-accounting, or mechanical concentration failure. This is an outcome
characterisation, not a new parity threshold or a retuning instruction.

## Fixed-policy decision sensitivity (8-team field, round 10)

The reference team's baseline was 70,665.00 units, $4,747,076.02 net income,
and PI 81.77. Each row is the changed team's result relative to that baseline.

| single decision variation | unit-sales delta | net-income delta | PI delta |
|---|---:|---:|---:|
| retail price +10% | -9,275.00 | -$186,469.38 | -1.76 |
| promotion budget +50% | +300.00 | -$149,856.39 | +0.13 |
| production +25% | +40,636.06 | +$4,560,901.38 | +12.40 |
| sales-team count +50% | 0.00 | -$790,000.00 | -0.78 |

These are directional measurements, not recommended moves. In particular,
the fixed baseline is production constrained, so an additional 25% supply is
valuable; extra sales staff have a cost but no incremental sales in that
condition. The result makes those trade-offs explicit without altering the
competition rules or implementing Fix B.

The complete per-round results, commands, input hashes and integrity checks
are in `fixed_policy_measurements.json`.
