# Competition sensitivity and starter-profile evidence — 2026-09-27

## Verdict

The candidate mechanics were measured at
`49b547fd30c954c44049b1f34e79e5e3a0d5dd3e`. The evidence harness is the
separate child commit `c32f50b1c9e8393f2c7aa8256fc9327cc9dad75b`; it changes
no engine, scenario or calibration file.

This evidence does **not** support competition-candidate release yet:

1. Eight firms making the same competent decisions finish with deterministic
   round-10 Performance Index spreads of **32.93 to 41.38 points**, depending
   only on starter profile. The gap grows in every round.
2. A measured, multi-lever policy applied to the weakest profile improved it by
   **12.64 to 28.65 PI points**, but did not beat the strongest starting profile
   in the same field in any shipped scenario.
3. Sales staffing contains a dominant cap path. Reducing each marketing row
   from 10 representatives to 5 leaves cumulative units and revenue exactly
   unchanged in all three scenarios, saves **$8.15M to $9.52M** of ten-round net
   income, and improves final PI by **0.61 to 0.92**. Zero representatives is
   the highest-PI staffing probe in every scenario.

Production, price and financing are not flat. Production is overwhelmingly
the strongest decision lever; its compounding magnitude, Media's supply-capped
promotion/ESG response, and the stakeholder tradeoff need an explicit owner
ruling before final certification.

## Run design and provenance

- 3 shipped scenarios: Consumer Electronics, Clean Energy, Media.
- 8 distinct starter profiles per field; 10 rounds per replay.
- 84 isolated replays: baseline plus identical seeded repeat, 25 one-factor
  probes, and one skilled-policy/weakest-profile adversarial field per scenario.
- One-factor ranges:
  - price: 0.70, 0.85, 1.00, 1.15, 1.30 times baseline;
  - promotion: 0, 0.50, 1.00, 1.50, 2.00 times baseline;
  - production: 0.50, 0.75, 1.00, 1.25, 1.50 times adaptive baseline;
  - sales staff: 0, 0.50, 1.00, 1.50, 2.00 times baseline;
  - financing: $2M/$1M repayment, baseline, $1M/$2M new debt per round;
  - ESG: $0, $0.5M, $1M, $2M, $4M, $6M total per round, split evenly
    between environmental and social investment.
- Every replay used a newly migrated database inside one disposable PostgreSQL
  container. No service or production database was in scope.
- All three seeded baseline repeats were numerically identical.
- Full matrix wall time: 3,002.526 seconds.
- Machine-readable evidence:
  `competition_sensitivity_measurements.json` (round trajectories, decision
  snapshots, cap flags, hashes and all 84 exact commands).

## Starter-profile advantage

Every team used the same competent baseline policy. Therefore these baseline
differences are attributable to authored starting position and its interaction
with the mechanics, not to a decision difference.

| Scenario | Weakest profile / PI | Strongest profile / PI | R10 spread | Tested skilled result on weakest | Same-field strongest | Overcame? |
|---|---:|---:|---:|---:|---:|---:|
| Consumer Electronics | Green Pioneer / 65.89 | Heritage Manufacturer / 98.82 | **32.93** | 80.89, rank 3 (+15.00) | 96.86, rank 1 | No |
| Clean Energy | Cost Leader / 54.14 | Density Leader / 93.75 | **39.61** | 66.78, rank 7 (+12.64) | 94.11, rank 1 | No |
| Media | Disruptor / 46.47 | Arthouse Curator / 87.85 | **41.38** | 75.12, rank 7 (+28.65) | 87.83, rank 1 | No |

The spreads compound rather than appearing only at the finish:

| Scenario | R1 | R5 | R10 |
|---|---:|---:|---:|
| Consumer Electronics | 2.74 | 13.12 | 32.93 |
| Clean Energy | 3.15 | 17.78 | 39.61 |
| Media | 3.64 | 19.52 | 41.38 |

The adversarial policy was selected transparently: within each one-factor
family, take a level only if it improves team 0's final PI by more than 0.01,
then compose the selected levels and apply them to the baseline-weakest
profile. This is a strong measured policy, but not an exhaustive proof that no
policy can win. It demonstrates that recoverability has not been established.

## Decision sensitivity

The values below are final-PI deltas from the subject profile's identical
baseline. Each range reports the worst and best observed nonbaseline point.

| Family | Consumer Electronics | Clean Energy | Media |
|---|---:|---:|---:|
| Price | -4.18 to -1.08 | -18.11 to -0.96 | -12.98 to +3.28 |
| Promotion | -0.44 to +0.25 | -2.34 to -0.32 | -1.04 to 0.00 |
| Production | **-38.87 to +15.75** | **-49.93 to +2.23** | **-52.06 to +8.59** |
| Sales staff | -1.46 to **+3.19** | -1.51 to **+2.03** | -3.66 to **+2.49** |
| Net debt direction | -1.24 to +0.54 | -0.91 to +0.61 | -2.61 to +0.99 |
| ESG total | -4.30 to +0.58 | -4.78 to +0.38 | **-7.39 to -0.20** |

### Production

Production is responsive from round 1 and dominates the other commercial
levers. A 25% increase over adaptive production produced these ten-round
effects for the subject profile:

| Scenario | Revenue delta | Net-income delta | PI delta |
|---|---:|---:|---:|
| Consumer Electronics | +$89.16M | +$44.12M | +15.75 |
| Clean Energy | +$143.31M | +$103.22M | +2.23 |
| Media (`x1.50`, its best point) | +$130.37M | +$85.29M | +8.59 |

The high production points become demand-capped in 7–10 rounds. The low points
remain supply-capped and suffer compounding lost sales. This is a real, highly
amplified mechanic rather than a flat field.

### Sales staffing

The baseline writes 10 representatives per marketing row. The distribution
benefit caps at five representatives under the current scenario values, while
cost continues to rise. At `x0.50`, all scenarios delivered exactly the same
cumulative revenue and units as baseline:

| Scenario | Net-income delta | Cash delta | PI delta |
|---|---:|---:|---:|
| Consumer Electronics | +$8.86M | +$8.86M | +0.86 |
| Clean Energy | +$8.15M | +$8.15M | +0.61 |
| Media | +$9.52M | +$9.52M | +0.92 |

This is a cap, not a flat mechanic: dropping all the way to zero changes
coverage in Consumer Electronics and Clean Energy. Nevertheless zero staff was
the highest-PI staffing point in all three subject runs, and in Media even zero
staff left revenue and units unchanged because the field was supply-capped.

### Price and promotion

- Consumer Electronics and Clean Energy price responses are nonmonotonic; the
  competent reference price is the best PI point among the tested levels.
- Media is supply-capped in all ten rounds: units are flat across the price
  range, while higher price monotonically increases revenue and PI through
  `x1.30`.
- Promotion has a small CE response, a nonmonotonic Clean Energy response, and
  no Media revenue or unit response at any level because Media remains
  supply-capped. In Media, half promotion matches baseline PI while saving
  $3.35M, so baseline promotion is financially dominated.

### Financing / debt-equity

Financing behaves directionally and is not flat:

- revenue and units remain unchanged, as expected;
- more net debt monotonically lowers PI and increases leverage/cash;
- repayment improves PI and lowers leverage, but consumes cash;
- the family presents a visible tradeoff rather than a free winning point.

The run intentionally did not force new equity when no legal funding shortfall
existed. Equity subscription needs a separate distress/funding-need design for
final certification.

### Stakeholder-relevant ESG investment

- Consumer Electronics peaks at $1M total per round: +0.58 PI and +$3.64M
  revenue, but -$6.59M net income.
- Clean Energy peaks at $0.5M total: +0.38 PI and +$3.45M revenue, but -$1.51M
  net income.
- Media is commercially supply-capped and every tested positive ESG level is
  PI-negative. The range runs from -0.20 PI at $0.5M to -7.39 at $6M, with no
  revenue or unit response.

ESG is not mechanically flat, because it changes cost, balance-sheet and PI
outcomes. Its gameplay value is weak and scenario-dependent; Media offers no
positive tested point.

## Gate disposition

### Blocks the competition candidate

1. **Starter-profile recoverability is not demonstrated.** Identical competent
   play produces 32.93–41.38 PI spreads, and the tested skilled policy cannot
   overcome the best start in any same-field comparison.
2. **Sales staffing has a dominant cap path.** Five representatives give the
   same commercial result as ten while saving $8.15M–$9.52M. Zero staff is the
   highest-PI tested point in all three scenarios.

### Blocks final certification unless explicitly accepted or remediated

1. Production is disproportionately dominant and compounds through adaptive
   supply; the owner must accept or recalibrate its effect size.
2. Media promotion and ESG are supply-cap masked across the entire horizon;
   stakeholder investment has no positive tested PI point.
3. A profile-specific or holdout-trained skilled policy, API-valid lock-path
   replay, and legal equity/distress experiment remain necessary before making
   a universal claim that no skilled policy can overcome profile advantage.

## Run-design limits

- The engine is deterministic. Seeded repeats prove repeatability but do not
  produce stochastic confidence intervals.
- One-factor sweeps do not cover every interaction in the full combinatorial
  decision space.
- Sensitivity uses team 0 in each scenario; the composed policy is selected
  in-sample on that team and transferred to the weakest profile.
- Like the pre-existing calibration harness, the replay writes locked rows
  directly. It measures resolver mechanics, not API discoverability or lock
  usability.
- The same competent baseline and adaptive-production rule are used across all
  profiles. A different policy could alter absolute values, but cannot explain
  the measured identical-policy starting-position spread.
