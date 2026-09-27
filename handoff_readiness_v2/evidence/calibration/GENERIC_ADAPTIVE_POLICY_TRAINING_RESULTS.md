# Generic adaptive recoverability proof — training results

## Outcome

Generic adaptive recoverability was **not established**.  None of the four
precommitted policies reached rank 1 for either Consumer Electronics / Green
Pioneer or Clean Energy / Cost Leader, so none was eligible to be frozen.
Under the predeclared stop rule, no second parameter generation was created and
the Media / Value Bundler holdout was never opened.  Media therefore remains a
final-certification calibration blocker; these results do not justify a Media
data change by themselves.

## Frozen-before-run design

The candidate grid and lexicographic selection rule were committed at
`5e02dfe9b31a0e9f4cb9e90c97d2f716c3eec09b` before the first replay.  A CE
run then exposed an unavailable prior product-market observation.  It produced
no output file.  The scenario-neutral fallback—retain the competent baseline
decision when the prior observation is unavailable—was committed at
`d8a506e0bb53d5627cf1a0bf01e437a778f34f53` before all eight successful runs.
Six pure policy tests passed.  Earlier Clean outputs made before that harness
fix were not inspected for selection and were overwritten by the final runs.

All successful runs used:

- exact product revision `d8a506e0bb53d5627cf1a0bf01e437a778f34f53` based on candidate2 `20ec2b7d`;
- eight teams, ten rounds, seed `20261011`, and 10% adaptive production for
  the seven baseline teams;
- Green Pioneer at team index 3 for CE and Cost Leader at team index 5 for
  Clean Energy;
- a fresh disposable PostgreSQL database per run;
- only prior sell-through, lost demand, inventory, cash, and leverage as
  feedback—no scenario/profile names or Media constants.

Implementation SHA-256 values:

- `generic_adaptive_policy.py`: `1f57de70a217cc41350883a285141b740d34ab7239992398ad49042cc8772b09`
- `stage1_runtime_replay.py`: `79599d9a2eba9785d91c70ef434abc15148d4f9bb7ee8cfd8b70b9a72a73511f`
- candidate JSON: `ebca44025582cc21e111b51c646fa54f61fda1a56d173258f3fd3fb97e3451fa`
- CE scenario: `02dd5e1750d740beeffc035da367320ed05f7d36f27c346568a5b118fab17675`
- Clean scenario: `7de9ad0bcb1d59409aaea69cb7ed70f6cfae0df847b7eba4dce0ffee0a4c63e0`

## Exact training results

PI margin is the subject's final PI minus the best competing team's final PI
in that same replay.  Cumulative income and units cover all ten rounds.

| candidate | scenario | final PI/rank | PI margin | cumulative net income | cumulative units | max reconciliation error | raw SHA-256 |
|---|---|---:|---:|---:|---:|---:|---|
| C1 conservative | CE | 77.47 / 7 | -13.46 | 3,776,518.20 | 339,224.74 | 2.91e-11 | `595a824882738a68586c8832216dbefc92202d2d678cddb4140a522a3d0ce98c` |
| C1 conservative | Clean | 54.49 / 8 | -39.19 | -67,145,209.36 | 59,855.90 | 1.82e-12 | `a507c3d7866941b27fb1239f9867a62beed9ec29bd687ca3ca87d2dd9a06be9f` |
| C2 balanced | CE | 80.00 / 6 | -7.87 | 19,850,300.19 | 414,084.74 | 5.82e-11 | `246377b346ae91bc7dd665f322e0910d249930c22f5678be2479122f9d4d8b99` |
| C2 balanced | Clean | 58.31 / 8 | -35.61 | -58,476,980.98 | 89,085.00 | 3.87e-12 | `30b2dc28e6c96294304930e8491b2f4739a5a98b547ad49bd4ddf1b5f1cbb222` |
| C3 growth | CE | 81.05 / 6 | -5.58 | 27,585,767.82 | 453,026.38 | 5.82e-11 | `5bf55a599f2282b3b63074ff86784841c9ba22be3ce2b7483a35f34cfb073f27` |
| C3 growth | Clean | 59.59 / 8 | -34.37 | -56,107,700.12 | 98,283.32 | 3.18e-12 | `c02bc0fd19a44e233ba7fffbe6a5a330426c5e2feac883953c79f3ab6d93674a` |
| C4 production-only | CE | 79.97 / 6 | -8.06 | 18,763,754.79 | 414,084.74 | 2.91e-11 | `80457934e31e770add2d245384541c6419636f37350b3774865161a24d167bd4` |
| C4 production-only | Clean | 58.33 / 8 | -35.58 | -58,275,619.17 | 89,931.26 | 2.44e-12 | `fbe72cc219566fa6a04aef307429df65253b6866ee8cbe1d38465056cee32f49` |

Every run contains 80 team-round rows, 80 decision rows, 20 subject
product-round feedback records, all ten rounds, and 250 market/segment
reconciliation rows.  All reconciliation residuals are below `6e-11`.

## Failure attribution

Clean Energy exposed the limiting behavior most clearly.  Its subject produced
25,000 units per product in round 1 and sold 1,753.95 (7.02% sell-through).
Every candidate correctly cut round-2 inventory, but the predeclared subsequent
stockout buffers (1.15–1.30) rebuilt volume too slowly to cover the fixed cost
base within ten rounds.  C3 was best, yet still finished rank 8 with a 34.37 PI
deficit and negative cumulative income.  C4's production-only results closely
match C2, showing that the two-percent price/two-representative response was not
the primary cause.

CE also rejected all candidates: C3 again performed best but finished rank 6,
5.58 PI behind the best competitor.  Because neither training scenario met the
rank-1 requirement, the selection procedure had no eligible policy.  A new
growth schedule could be fit to these revealed trajectories, but doing so under
the time constraint would increase overfitting risk; it was explicitly not
attempted.

## Reproduction

For each candidate key and scenario, the runner invocation inside a disposable
PostgreSQL environment was equivalent to:

```text
python3 handoff_readiness_v2/evidence/calibration/stage1_runtime_replay.py \
  --output /tmp/generic-train-<candidate>-<scenario>.json \
  --scenario <consumer_electronics_2026|clean_energy_tech_2026> \
  --rounds 10 --teams 8 --adaptive-production --name-seed 20261011 \
  --subject-team-index <3|5> \
  --adaptive-policy-json <candidate JSON from generic_adaptive_training_candidates.json>
```

The Media scenario SHA was recorded for provenance
(`f4bec76ad33dfda200a95d2259051677c0ca1b08c9a107bfc41f97908af12665`),
but no adaptive-policy Media database or output was created.
