# Starter-profile recoverability repair

## Decision

This lane tested the exact competition candidate
`49b547fd30c954c44049b1f34e79e5e3a0d5dd3e` in an isolated worktree.  The
pre-change attribution is in `PRE_CHANGE_ATTRIBUTION_2026-09-27.md` and was
committed before scenario data changed.

The initial hypothesis was too broad.  Under the pre-existing
`production_plus_25` policy, the last-place Clean Energy Cost Leader and Media
Value Bundler already finish first.  Consumer Electronics was the actual
recoverability failure: its Green Pioneer moved only from eighth to third.
Clean Energy and Media were therefore left byte-unchanged and served as the
scenario holdout.

The accepted repair removes only CE's empirically score-bearing tier extremes:

- four of the five budget second products become mainstream; Volume Champion's
  already-$250, volume-led `VoltEdge Go` remains budget;
- Brand Builder's premium product becomes mainstream;
- Heritage Manufacturer's ultra-premium and premium products become
  mainstream;
- Ecosystem Player keeps its premium product because it was not the leading
  advantage;
- six changed products whose old price fell outside the mainstream band are
  moved to the nearest established $250-$550 band edge.

No feature vector, debt, cash, starting revenue, unit volume, market share,
scoring formula, demand formula, cost formula, or sales-staff mechanic changed.
The eight profiles remain distinct in alpha feature vectors, finance pairs,
and authored product price/volume/share schedules.  The repair changes seven
of 16 CE positioning labels and six prices.  It also preserves three distinct
starter positioning mixes: mainstream/mainstream, mainstream/premium, and
budget/mainstream.  Two short English/Chinese descriptions were updated so
the participant briefing matches the data.

## Why this is the minimum accepted candidate

| candidate | CE labels changed | final baseline spread | Green +25% rank | decision |
|---|---:|---:|---:|---|
| original | 0 | 32.93 | 3 | fails recoverability |
| tier extremes retained for Brand + Ecosystem | 7 | 22.91 | 3 | rejects: skilled policy still cannot win |
| all CE tier labels normalized | 9 | 15.80 | 1 | passes, but erases an unnecessary premium distinction |
| Ecosystem premium retained | 8 | 14.77 | 1 | passed the recoverability gate |
| accepted follow-up; Ecosystem premium and Volume budget retained | 7 | 13.19 | 1 | passes recoverability and restores the three-mix contract |

The first 7-change candidate retained Brand's premium product and Ecosystem's
premium product; it failed the declared gate.  The accepted 7-change candidate
is a different subset: Brand is normalized, while the already inexpensive
Volume product retains its budget label.  It both passes and avoids restoring
structural advantage to a leading profile.  The ninth change was unnecessary
and was reverted.
The price edits do not change the fixed-policy decisions (which price at the
scenario reference); they keep the round-zero briefing coherent with the
new positioning labels.

## Before and after — CE baseline

Every row is round 10 of an 8-team, 10-round run.  All teams use the same
documented competent policy and 10% adaptive production.

| profile | before PI/rank | after PI/rank | after revenue | after net income |
|---|---:|---:|---:|---:|
| Heritage Manufacturer | 98.82 / 1 | 90.99 / 2 | 20,452,992 | 6,547,477 |
| Brand Builder | 90.39 / 2 | 91.26 / 1 | 21,071,904 | 6,788,673 |
| Ecosystem Player | 76.80 / 3 | 85.80 / 4 | 19,680,640 | 6,236,212 |
| Volume Champion | 76.10 / 4 | 82.78 / 5 | 17,122,344 | 3,641,252 |
| Innovator | 73.94 / 5 | 89.65 / 3 | 20,282,304 | 6,204,741 |
| Workhorse | 67.61 / 6 | 79.78 / 6 | 17,889,984 | 4,864,975 |
| Turnaround | 66.25 / 7 | 79.04 / 7 | 16,263,072 | 3,357,955 |
| Green Pioneer | 65.89 / 8 | 78.07 / 8 | 14,784,000 | 2,846,117 |

The final spread is 13.19 instead of 32.93, a 59.9% reduction.  Its full
round-by-round trajectory changed from
`2.74, 5.54, 8.22, 10.77, 13.12, 21.99, 24.49, 27.34, 30.17, 32.93` to
`1.80, 4.05, 6.26, 8.26, 4.44, 9.35, 9.82, 10.32, 11.78, 13.19`.
The profiles do not collapse to a tie: the accepted baseline still spans
13.19 points and all eight have a distinct result.

## Policy sensitivity and holdout

Subjects and policies were declared in the pre-change evidence.  They were
not chosen after seeing the repaired outcomes.

| scenario / subject | baseline PI/rank | production +25% PI/rank | PI delta | result |
|---|---:|---:|---:|---|
| CE / Green Pioneer | 78.07 / 8 | 86.45 / 1 | +8.38 | repaired training failure now recoverable |
| Clean / Cost Leader | 68.71 / 8 | 86.70 / 1 | +17.99 | unchanged scenario control |
| Media / Value Bundler | 73.36 / 8 | 83.79 / 1 | +10.43 | untouched scenario holdout |

On final CE bytes, the adverse/control probes are price +10%: -1.40 PI,
promotion +50%: +0.03 PI with -$237,000 net income, and sales staff +50%:
-1.21 PI with -$790,000 net income.  The repair does not make arbitrary spend
a winning substitute for production execution.

Seed `20260927` was used for selection and `20261011` for the final run.  In
this harness a seed only shuffles company display names; starter profiles are
assigned by index and the engine is deterministic.  Profile-keyed results are
identical across seed changes.  The scenario holdout is therefore the stronger
overfit check: Media was not edited or used to select the CE data rule, and its
predeclared policy still wins.

## Exact final verification

The disposable-PostgreSQL commands were:

```text
backend/scripts/run-calibration-postgres --scenario consumer_electronics_2026 \
  --field-sizes 8 --rounds 10 --subject-team-index 3 --home-markets NA \
  --name-seed 20261011 \
  --output /tmp/lane-b-thirdmix-ce.json

backend/scripts/run-calibration-postgres --scenario clean_energy_tech_2026 \
  --field-sizes 8 --rounds 10 --subject-team-index 5 --home-markets na \
  --name-seed 20261011 --policies production_plus_25 \
  --output /tmp/lane-b-exact-final-clean.json

backend/scripts/run-calibration-postgres --scenario media_entertainment_2026 \
  --field-sizes 8 --rounds 10 --subject-team-index 7 --home-markets na \
  --name-seed 20261011 --policies production_plus_25 \
  --output /tmp/lane-b-exact-final-media.json
```

Each report contains eight distinct profiles, all 80 team-round cells, all
requested policy runs, and `all_field_sizes_reconciled: true`.  Report SHA-256
values are:

- CE: `bb2c8a297084d822c9074b9dbfad5d33a790e140f6c8fcc6378aa2dcda49f4cc`
- Clean: `af06b17879d32fbeaff4d1f1b1b5189ec6760505e718d7a01c0624ec551d3378`
- Media: `e44ab0385af9e8c377c598453b3bf42c15a6674289ff1a60aa1828711f1b45b4`

The final CE scenario SHA-256 in the report is
`a9c1444b6b1f1f7e66a73c0f8c002f983bd73886b5342fcfd1e7bc7179e14cdc`.
Clean and Media retain their candidate SHA-256 values
`7de9ad0b...4c63e0` and `f4bec76a...12665`.

The final-byte CE report includes baseline plus all four declared controls.
Its repeat used the same exact scenario bytes and seed; deterministic
`checks`, `method`, `field_size_saturation`, `per_profile_final`, and
`fixed_policy_sensitivity` payloads all matched.  The repeat report SHA-256 is
`4be937ee1894d9d8ce8f61d5197f970fff6256fa67678065d9e065ae15298d2a`;
the full-file hashes differ because the reports include generated timestamps
and per-run temporary database names.

The focused disposable-PostgreSQL suite was:

```text
backend/scripts/test-postgres \
  core.tests.test_calibration.ScenarioPreferenceValidationTests \
  core.tests.test_scenario_reference_prices \
  core.tests.test_coherence_price_ranges \
  core.tests.test_game_creation_paths \
  core.tests.test_manifest_determinism
```

It passed 89/89 in 90.557 seconds on the eight-label version.  The first run
exposed one test-fixture assumption: a three-team prefix was expected to
contain multiple tiers.  The test now creates the full eight-team competition
field, still requires more
than one tier, and compares the old and new coherence implementations for all
eight teams.  After the final one-label restoration, the exact distinct-mix
test plus the profile data contract passed 2/2; neither assertion was weakened.
`py_compile`, YAML load/distinctness assertions, and `git diff --check` also
passed.

An exact final replay repeated seed `20261011`; all eight final profile rows,
all 80 baseline profile-round PI cells, and every final result for the four
policy probes were identical.

## Tradeoffs and non-claims

- CE's competition start now treats most inherited products as mainstream,
  while retaining one budget product and one premium product;
  feature fit, scale, price within band, debt, and balance sheet carry the
  starter archetype.  This is a deliberate reduction in tier variety, not a
  claim that the profiles are symmetric.
- The low profile still finishes last under identical play.  Fairness here is
  recoverability, not guaranteed parity: a predeclared competent lever can now
  overcome the inherited deficit.
- Clean and Media retain 19.80 and 12.49 deterministic baseline spreads.  They
  were not tuned because their last-place profiles already reach rank 1 under
  the holdout policy.  Equal-play spread alone is not treated as a defect.
- No empirical result here certifies subjective classroom fun, explanation
  quality, or strategy diversity.  Those remain manual competition-walkthrough
  questions.
