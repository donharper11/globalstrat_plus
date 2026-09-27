# Starter-profile recoverability: pre-change attribution

This evidence was recorded on the isolated branch
`fix/profile-recoverability-20260927` before changing any scenario profile.
The exact candidate is `49b547fd30c954c44049b1f34e79e5e3a0d5dd3e`.

## Reproduction and provenance

Each run used the repository's disposable-PostgreSQL calibration runner, eight
teams, ten rounds, adaptive production, the documented competent baseline,
one North American home market for every team, and name seed `20260927`:

```text
backend/scripts/run-calibration-postgres \
  --scenario <scenario> --field-sizes 8 --rounds 10 --baseline-only \
  --home-markets <NA-or-na> --name-seed 20260927 --output <report>
```

Scenario SHA-256 values:

| scenario | SHA-256 |
|---|---|
| Consumer Electronics | `0fae38ca4167db1083e7f78b18896ed5a0555bfc8a879fb270108f5b47d25623` |
| Clean Energy | `7de9ad0bcb1d59409aaea69cb7ed70f6cfae0df847b7eba4dce0ffee0a4c63e0` |
| Media | `f4bec76ad33dfda200a95d2259051677c0ca1b08c9a107bfc41f97908af12665` |

The fixed baseline SHA-256 is
`b7cb6eead9b81467c197dbc0d74099faf82fdc06883c241404da63ef93d2212f`;
the scoring implementation SHA-256 is
`f1a79f8a98c193e346ebb147b393f09a550b6464c90e9b4818581781fef454c8`.
The three complete reports had SHA-256 values `2eb57833...09c09dc`,
`2dd5c554...8771e6`, and `7e2c9f41...5e5f6f` respectively. Every run exercised
all 80 profile-round cells and passed adoption-pool reconciliation.

## Observed deterministic spread

| scenario | round-by-round PI spread (rounds 1-10) | final range |
|---|---|---|
| Consumer Electronics | 2.74, 5.54, 8.22, 10.77, 13.12, 21.99, 24.49, 27.34, 30.17, 32.93 | 65.89-98.82 |
| Clean Energy | 1.70, 3.41, 5.15, 6.93, 8.76, 10.63, 12.57, 14.65, 17.18, 19.80 | 68.71-88.51 |
| Media | 1.06, 2.14, 3.24, 4.32, 5.43, 6.59, 7.82, 9.15, 10.66, 12.49 | 73.36-85.85 |

The gap widens in every round in every scenario, so this is a repeated-flow
advantage, not merely a round-zero endowment.

### Final profile outcomes

| scenario / profile | tier mix | revenue | net income | PI | rank |
|---|---|---:|---:|---:|---:|
| CE / Heritage Manufacturer | ultra-premium + premium | 30,945,760 | 15,026,883 | 98.82 | 1 |
| CE / Brand Builder | premium + mainstream | 26,405,120 | 10,944,425 | 90.39 | 2 |
| CE / Ecosystem Player | premium + mainstream | 19,680,640 | 6,236,212 | 76.80 | 3 |
| CE / Volume Champion | mainstream + budget | 17,123,888 | 3,642,189 | 76.10 | 4 |
| CE / Innovator | mainstream + budget | 16,146,624 | 3,120,589 | 73.94 | 5 |
| CE / Workhorse | mainstream + budget | 15,600,592 | 2,861,237 | 67.61 | 6 |
| CE / Turnaround | mainstream + budget | 14,181,936 | 1,543,652 | 66.25 | 7 |
| CE / Green Pioneer | mainstream + budget | 12,892,200 | 1,204,036 | 65.89 | 8 |
| Clean / Endurance Specialist | premium + mainstream | 8,407,200 | -345,646 | 88.51 | 1 |
| Clean / Industrial Integrator | premium + mainstream | 8,033,040 | -755,937 | 85.94 | 2 |
| Clean / Density Leader | premium + mainstream | 8,033,040 | -815,937 | 85.49 | 3 |
| Clean / Safety Champion | premium + mainstream | 7,870,560 | -1,088,174 | 83.90 | 4 |
| Clean / Fast-Charge Specialist | premium + mainstream | 7,586,560 | -1,293,608 | 82.35 | 5 |
| Clean / Green Pioneer | mainstream + premium | 6,826,400 | -1,764,983 | 79.01 | 6 |
| Clean / Residential Brand | mainstream + mainstream | 4,777,440 | -3,575,428 | 69.16 | 7 |
| Clean / Cost Leader | mainstream + mainstream | 4,807,040 | -3,608,448 | 68.71 | 8 |
| Media / Content King | premium + mainstream | 10,154,928 | 369,841 | 85.85 | 1 |
| Media / Compliance Broadcaster | premium + mainstream | 9,983,856 | 356,988 | 85.68 | 2 |
| Media / Arthouse Curator | premium + mainstream | 9,903,312 | 401,103 | 85.62 | 3 |
| Media / Algorithm | premium + mainstream | 9,918,576 | 173,709 | 84.12 | 4 |
| Media / Rights Holder | premium + mainstream | 10,076,112 | 178,044 | 83.98 | 5 |
| Media / Disruptor | premium + mainstream | 9,683,280 | -27,544 | 82.26 | 6 |
| Media / Localizer | premium + mainstream | 9,456,528 | -28,166 | 81.95 | 7 |
| Media / Value Bundler | mainstream + mainstream | 7,521,984 | -1,938,270 | 73.36 | 8 |

## Attribution

The fixed policy prices each product at its scenario/tier reference and gives
budget, mainstream, premium, and ultra-premium products initial production of
25,000, 20,000, 12,000, and 8,000 units respectively. Later production is
110% of prior sales. Consequently, the authored tier pair determines a stable
price/volume offer and then propagates it through every subsequent round.

Across the eight profiles, the final-PI correlations were:

| scenario | tier-policy offer value | alpha feature sum | starting debt | final revenue | final net income |
|---|---:|---:|---:|---:|---:|
| CE | 0.761 | -0.060 | -0.584 | 0.987 | 0.982 |
| Clean | 0.931 | 0.325 | 0.723 (confounded) | 0.996 | 0.999 |
| Media | 0.931 | 0.511 | 0.228 | 0.977 | 0.988 |

These are descriptive correlations, not independent causal estimates. The
mechanism is nevertheless directly traceable: market score is 30% of PI and
contains 40% cohort-relative revenue; financial score is 15% and contains 40%
cohort-relative revenue plus 40% cohort-relative profit. The resulting index
change is carried into the next round. The game builder uses only each
profile's `alpha` feature block for both initial products; `beta` changes would
not alter these runs. Authored `starting_revenue` is stored but is not consumed
by the round resolver. Debt has a real but much smaller path through the 20%
debt term within the 15% financial component.

Therefore:

- Intentional asymmetry is present in product identity, feature strengths,
  debt, and the low-volume/premium versus high-volume/value archetype story.
- The measured scoring advantage is specifically the tier mix's repeated
  revenue/profit effect under competent identical play. A low-tier profile is
  not merely different; in all three scenarios it occupies the bottom cohort
  and the deficit grows monotonically.
- Changing scoring weights/formulas or the sales-staff mechanic is unnecessary
  and outside this repair.

## Predeclared training and holdout plan

Before any profile edit, the disadvantaged subjects and policies are fixed:

| role | scenario | subject profile | subject index | policy |
|---|---|---|---:|---|
| training | Consumer Electronics | Green Pioneer | 3 | production +25% |
| training | Clean Energy | Cost Leader | 5 | production +25% |
| holdout | Media | Value Bundler | 7 | production +25% |

`production_plus_25` is a pre-existing harness policy, not a newly tuned
strategy. Price +10% is the adverse sensitivity control. Seed `20260927` is
the training name seed and `20261011` is predeclared as the replay seed. Seeds
shuffle display labels only; they do not introduce engine randomness or
reassign starter profiles, so scenario holdout is the meaningful overfit
control. The Media post-change holdout result will not be inspected while
choosing the cross-scenario data rule.

The candidate data rule to test is structural and scenario-independent:
remove tier-mix advantage from the competition start by giving every starter
one premium and one mainstream product, while leaving names, feature vectors,
cash, debt, starting revenue, authored prices/volumes/shares, and all mechanics
distinct. This changes ten positioning labels across 48 product rows (20.8%)
and no scoring or sales-staff code. It is the smallest coherent rule that
removes the identified categorical advantage in all three fields; one-off
cash, debt, or feature compensation would instead tune unrelated inputs to
mask a revenue mechanism.
