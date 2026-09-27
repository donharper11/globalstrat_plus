# Sales staffing reach repair — 2026-09-27

## Disposition

The candidate mechanic at `49b547fd` is defective: five and ten sales
representatives have identical demand effect, staffing cost continues to rise,
and zero staff dominates the tested baseline policy in all three shipped
scenarios.

The evidence supports the utilization-scaled experiment at `f2650fb0` for
integration review. It removes free distribution reach, restores a responsive
commercial curve, and creates a real reach-versus-cost trade-off. It does not
change scenario constants or starter profiles.

## Root cause and intended contract

The decision was wired, but two effects made it behave as if it were not:

1. Customer demand reads `sales_team_count` through
   `distribution_coverage`; costs charge every representative at the authored
   per-round rate. The candidate calculated `base_reach + min(investment /
   cap, 0.1)`. With the shipped `$100,000` representative cost and `$5,000,000`
   effective-investment cap, demand benefit stopped after five people while
   cost remained linear.
2. The selected channel's 30–90% reach was granted even with zero staff.
   `distribution_coverage` is then scored with Gaussian ideal matching on a
   0–20 scale. Hybrid's free 70% reach is 14/20, exactly matching many authored
   segment ideals; adding staff could move above the ideal and reduce demand.
   Supply caps hid or flattened some of those demand changes.

There is a separate stakeholder/strategy path: `distribution_commitment` sums
distribution investment and representatives, but gives at most five points
from representatives. That cap was not changed. It is not the customer-demand
path and the repaired demand curve remains live beyond five representatives;
changing the stakeholder scoring contract would require separate evidence.

The source contract points to a different interpretation:

- all three scenarios describe `distribution_investment_cap = 5000000` as
  “Max effective distribution investment” and
  `sales_rep_cost_per_round = 100000` as the per-round cost;
- the feature description says reach is derived from distribution strategy
  **and investment**;
- the research report calls the channel constant its
  `theoretical_reach`;
- the participant UI assigns representatives to selected channels and charges
  the same authored representative cost.

The repair therefore treats the channel constant as its fully staffed
potential:

```text
utilization = min(representatives × representative_cost / effective_investment_cap, 1)
realized_reach = channel_theoretical_reach × utilization
```

Zero representatives now produce zero reach, the curve is proportional up to
the authored cap, and additional staff beyond the cap have no demand effect.
The engine and participant research preview call the same calculator.

## Experiment design

Each point is a fresh PostgreSQL-backed replay: ten rounds, eight teams,
deterministic name seed `20260927`, and adaptive production at 110% of the
prior round's unit sales. Only team 0's disclosed policy is varied; competitors
retain the baseline. The matrix contains 54 replays:

- baseline plus seeded repeat;
- standalone staffing multipliers 0, .25, .5, .75, 1, 1.25, 1.5, and 2;
- staffing 0, .5, 1, and 1.5 with production ×1.25;
- staffing 0, .5, 1, and 1.5 with promotion ×1.5;
- the fixed production ×1.25, promotion ×1.5, staffing ×1 policy on holdout
  team 6.

The baseline has two marketing rows and 20 total first-round representatives,
so the standalone sweep covers 0–40 total first-round representatives.
Seeded baseline repeats were identical in all scenarios.

## Standalone utilization curve

| Scenario | Staffing multiplier | First-round staff | Revenue ($m) | Units | Net income ($m) | Final PI |
|---|---:|---:|---:|---:|---:|---:|
| Consumer Electronics | 0 | 0 | 105.411 | 392,539 | 12.051 | 73.11 |
|  | .25 | 6 | 106.127 | 395,207 | 7.360 | **73.14** |
|  | .5 | 10 | 106.697 | 397,332 | 4.230 | 72.98 |
|  | 1 | 20 | 108.482 | 403,975 | -3.493 | 72.70 |
|  | 2 | 40 | 113.317 | 421,982 | -18.633 | 72.71 |
| Clean Energy | 0 | 0 | 124.460 | 24,863 | 36.316 | **94.57** |
|  | .25 | 6 | 124.608 | 24,899 | 31.560 | 94.26 |
|  | .5 | 10 | 124.774 | 24,928 | 28.442 | 94.04 |
|  | 1 | 20 | 125.798 | 25,130 | 21.056 | 93.57 |
|  | 2 | 40 | 133.312 | 26,616 | 10.015 | 93.20 |
| Media | 0 | 0 | 72.051 | 510,079 | -2.438 | **85.12** |
|  | .25 | 6 | 72.051 | 510,079 | -7.923 | 84.64 |
|  | .5 | 10 | 72.051 | 510,079 | -11.671 | 84.34 |
|  | 1 | 20 | 72.051 | 510,079 | -21.192 | 83.43 |
|  | 2 | 40 | 72.051 | 510,079 | -41.005 | 80.01 |

Consumer Electronics and Clean Energy now gain revenue and units as staffing
rises, while net income and cash fall. Consumer Electronics has a small
interior PI optimum at ×.25; Clean Energy makes the commercial-versus-financial
trade-off explicit. Media remains production-capped in the standalone policy,
so its commercial line is flat and zero staff wins on cost there.

## Interaction and no-free-win evidence

Raising production separates a temporary supply cap from a flat mechanic:

| Scenario | Production ×1.25 staffing change | Revenue delta | Unit delta | Net-income delta | PI delta |
|---|---|---:|---:|---:|---:|
| Consumer Electronics | 0 → .5 | +$2.804m | +10,440 | -$6.568m | +0.03 |
| Clean Energy | 0 → .5 | +$0.696m | +138 | -$7.593m | -0.19 |
| Media | 0 → .5 | +$0.058m | +378 | -$8.198m | -0.40 |
| Consumer Electronics | 0 → 1.5 | +$11.489m | +42,782 | -$18.421m | +0.08 |
| Clean Energy | 0 → 1.5 | +$8.570m | +1,700 | -$17.975m | -0.24 |
| Media | 0 → 1.5 | +$1.011m | +6,584 | -$24.201m | -1.12 |

Positive staffing therefore produces commercial value in all three scenarios,
including Media when supply permits it. Zero staffing retains a financial-cost
advantage. Neither zero nor the high tested staffing policy dominates across
revenue, units, income, cash, and PI.

Promotion ×1.5 preserves the responsive Consumer Electronics and Clean Energy
curves. Media remains supply-capped at 510,079 units on that path, which is
consistent with the production interaction rather than evidence of an unwired
lever.

The disclosed combined policy on holdout team 6 dominates its own baseline in
all three scenarios. This is a policy-transfer check, not a claim that staffing
alone caused the holdout gain.

## Comparison with the two rejected mechanics

| Variant | Consumer Electronics | Clean Energy | Media |
|---|---|---|---|
| Candidate `49b547fd`: additive bonus capped at .1 | 5 and 10 reps have the same demand effect; zero beats baseline by $5.783m revenue, 21,541 units, and 3.19 PI | zero beats baseline by $7.134m revenue, 1,412 units, and 2.03 PI | units/revenue flat; zero +2.49 PI |
| Rejected `0d978e90`: additive bonus capped at 1.0 | increasing staff reduces revenue and units; zero beats baseline by $14.518m and 54,068 units | zero beats baseline by $9.912m and 1,970 units | units/revenue flat; zero +3.28 PI |
| Utilization `f2650fb0` | 0→baseline adds $3.071m and 11,436 units; small interior PI optimum | 0→baseline adds $1.338m and 267 units; explicit cost trade-off | standalone supply cap; production interaction is responsive |

The additive experiment proved that the original five-representative ceiling
was real, but it amplified the free-reach/Gaussian-ideal problem and must not be
integrated.

## Provenance, tests, and limitations

- Candidate mechanics: `49b547fd30c954c44049b1f34e79e5e3a0d5dd3e`
- Rejected additive experiment: `0d978e9001a69020372733dc74ea53ecc39e5c57`
- Utilization experiment: `f2650fb0bd132e42ce29af26b6e9a01217f0a034`
- Evidence harness: `01b8cb1c7733f39da0060bb5957a5ccd7290e678`
- Preview/engine consistency test: `33901f4487c4387adf48452255449cb86163ecc5`
- Original candidate evidence SHA-256:
  `f209660dc4521e06f0797a2f80d68f870ebac65c1e0eeaa5bde7ebd3e118cc4f`
- Rejected additive evidence SHA-256:
  `2c0b00749e6649f2b0a7beaaf6e316ecc964685dfb52151ff1e27f9132c209cc`
- Utilization evidence SHA-256:
  `fbf6406a6a60cbfa6acee60bcd13435a797c34b366cfa24905541c8ab23623c8`
- Utilization matrix wall time: 1,988.656 seconds.
- Focused engine/calibration/research suite: 53/53 passed in 4.801 seconds.
- Evidence harness unit suite: 11/11 passed.
- Complete backend suite: 1,865/1,865 passed in 487.721 seconds on disposable
  PostgreSQL.

The engine is deterministic, so repeatability is exact but there are no
stochastic confidence intervals. The matrix covers three disclosed policy
paths and one holdout, not the full combinatorial policy space. It tests up to
40 total first-round representatives; the authored per-row investment cap is
covered by boundary tests, not by a full-horizon cap sweep. Decisions are
written through the established locked-decision replay harness, so this is a
mechanics result rather than an API-usability result.

The remaining certification risk is calibration breadth, not wiring: run a
participant-feasible cap-adjacent sweep and additional team/profile holdouts
before declaring the final economy calibrated. The measured lane no longer
blocks a candidate on the original “free zero staff / dead staffing lever”
defect. It passes the complete backend gate and is ready for integration
review. The separate five-point
`distribution_commitment` stakeholder cap should also be explicitly
dispositioned during final calibration, even though it no longer flattens the
commercial mechanic.
