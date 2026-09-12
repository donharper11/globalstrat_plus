# GSP-CRV2-11 — R11 (round-zero adoption) and Stage 5 (authored preferences)

**Builder scope:** Stage 1 item 5 / R11 implementation, and Stage 5 items 1–4.
**Branch:** `crv2-11-round-zero-and-preferences`, cut from
`crv2-release-integration` at `e1b744c`, in an isolated worktree.
**Observes:** `handoffs/EXECUTION_PROTOCOL.md`, `specs/STANDING-DISCIPLINE.md`.
**Rule in force:** `OWNER_RULINGS_2026-09-11.md` R11.

**No gate is claimed closed.** Everything below is development-grade
measurement under the protocol's Phase 2/3 budget, offered for audit.

---

## Part A — R11: round-zero adopters derived from the authored starter sales

### The rule, in plain terms

Round 0 is a briefing state. No team has decided anything, so there is no
demand to allocate. What the scenario *does* author is how much each firm was
already selling when the students inherited it, and which customers existed to
have bought it. So round-0 adopters are **not generated** — the authored
starting unit sales are **apportioned**:

```
adopters(team, segment)
    = the team's authored round-0 unit sales in its home market
      x  share(segment)

share(segment)  ∝  bass_p(segment) x population(segment, home market)
                   x  fit(team's authored starting feature levels, segment)
```

In the terms a scenario author would recognise: *a firm's authored starting
sales are divided between its home market's customer segments in proportion to
how many of that segment are ready to buy this period — the segment's own
first-period Bass pool, `bass_p x population` — weighted by how well the firm's
authored starting feature levels match that segment's authored ideal
preferences.*

### Where every term is authored

| Term | Authored in | Model field |
|---|---|---|
| the team's starting unit sales | `starter_profiles[].products[]` element 5 | `FirmStarterProduct.unit_volume` |
| which market those sales are in | `starter_profiles[].home_market` (overridable per game by `initialize_game --home_markets`) | `FirmStarterProfile.home_market` / `Team.home_market` |
| who is ready to buy | `customer_segments[].bass_p` and `.populations[market]` | `SegmentDefinition.bass_p`, `.population_size` |
| how well the firm matches them | `segment_preferences[segment][market]` and `starter_profiles[].platforms[]` | `SegmentPreference.{ideal_value,weight,tolerance}`, `FirmStarterPlatformConfig.starting_level` |
| who cannot be served yet | `customer_segments[].min_generation_required` | `SegmentDefinition.min_generation_required` |

**No unauthored constant participates.** The retired line was
`new_adopters = bass_p * pop * avg_share * 10  # Scale for meaningful numbers`
(`bootstrap.py:175`). It is deleted and **not** replaced by another factor —
not 10, not 1, and not a new scale key. The rule is stated in the
`core/engine/bootstrap.py` module docstring in the scenario-authoring terms
above, as required.

### Determinism

The apportionment is ordered and exact (this is inside the CRV2-01 determinism
boundary). Each segment first takes `units x weight / Σweight` rounded **down**
to the cent; the cents that rounding leaves over are handed out one at a time,
largest discarded fraction first, ties broken by the caller's segment order
(primary key, the order `bootstrap_round_zero` already used). Two runs of the
same scenario therefore produce identical rows, and the allocations sum to the
authored units **exactly** rather than nearly.

### Segments that take nothing

A segment carrying `min_generation_required` above the generation the team
actually starts on is excluded from the apportionment, exactly as
`preference_engine.py:70-76` excludes it from round 1 onward. It keeps its
baseline row at zero. This affects Tech Enthusiasts (consumer electronics),
Aerospace & Defense (clean energy) and Gen Z Digital Natives (media), all of
which require Gen 2 while every team starts on Gen 1.

### Failing loudly rather than defaulting

If a scenario authors starting sales but no customer segment in that market
that the team could have sold to (none reachable, or all with zero
population × `bass_p` × fit), `bootstrap_round_zero` raises a `ValueError`
naming the team, the profile, the market and the unit count, and saying that
round-0 adopters are never defaulted to a constant. There is no fallback.

**Nothing in the three shipped scenarios triggers it** — this is a guard for
the next scenario author, and it is proved by a test that constructs the
condition deliberately.

### The reconciliation, and what it replaced

The reconciliation is the point of the ruling: a team's round-0 segment
adopters must sum to its round-0 units sold in that market, to the cent.

`ShippedScenarioRoundZeroTests` loads each shipped YAML through the real
`load_scenario`, initialises a real 4-team game through `initialize_game`, and
asserts per team that round-0 adopters equal round-0 units sold, and that
round-0 units sold equal the authored `unit_volume` sum. **How far apart those
two numbers were before the change**, measured by running the same tests
against the pre-change engine:

| scenario | team | round-0 adopters (retired rule) | round-0 units sold | error |
|---|---|---:|---:|---:|
| consumer_electronics_2026 | Apex Devices | 208,650.00 | 65,000.00 | **3.21x** |
| clean_energy_tech_2026 | Nova Power Systems | 2,725.00 | 8,000.00 | **0.34x** |
| media_entertainment_2026 | Meridian Productions | 201,000.00 | 9,000.00 | **22.3x** |

The retired rule did not merely mis-scale the figure — it mis-scaled it in
**different directions in different scenarios**, over-stating consumer
electronics by 3x, understating clean energy by 3x, and over-stating media by
22x. That is the concrete form of "the two numbers a student can see side by
side do not reconcile at any factor": no single constant could have fixed all
three, which is why a derived figure was the only available answer.

After the change all three reconcile exactly, and the small hand-built
fixtures reconcile to the cent including a deliberately awkward volume
(25,000 units across pools in a 1:2 ratio → 8,333.33 + 16,666.67 = 25,000.00).

### One consequential change, flagged for the owner

`team_share_pct` on the round-0 adoption row previously carried
`avg_share` — the authored **firm-level market share** from
`FirmStarterProduct.market_share_pct`. From round 1 onward that same column
carries a different quantity: the team's share of **that segment's adoption
pool**. Round 0 now carries the round-1 quantity (`adopters / pool`, at the
column's full 4 decimal places), so the column means one thing across all
eleven rounds.

**This changes a student-visible number and was not explicitly ordered by R11.**
It is reported here rather than buried: if the owner prefers the round-0 column
to keep showing authored market share, that is a one-line revert, but then the
column means two different things in the same table.

### Item 5 — the display oddity, reported and not fixed

Round-0 `cumulative_adopters` does not carry into round 1:
`bass_engine._get_total_cumulative` and `_get_team_cumulative` return `0.0`
when `prev_round < 1`, so round 1's cumulative equals round 1's new adopters. A
student therefore sees **Cumulative fall between round 0 and round 1**,
whatever the round-0 figure is.

**My derivation does not change this**, and I have not repaired it — it is a
wording/presentation matter for CRV2-12 as instructed. It is now *smaller* in
magnitude for consumer electronics and media (because round-0 adopters fell to
the authored unit volumes) and *larger* for clean energy (because they rose),
but the direction of the anomaly is identical. The current behaviour is pinned
by `test_round_zero_cumulative_equals_new_adopters` so that any future change
to it is deliberate rather than accidental.

### Replay comparison — rounds 1–10 unchanged

Two 8-team, 10-round fixed-policy replays of Consumer Electronics 2026 —
identical scenario, identical `initialize_game --home_markets NA`, identical
competent baseline policy from the adversarial-balance harness, identical 10%
adaptive production — one against the **pre-change** engine (`bootstrap.py`
reverted to `e1b744c`) and one against **R11**. Development-grade, as
permitted: one seed, one opponent set, one scenario.

| run | round-zero rule the probe recorded at runtime | rounds | wall |
|---|---|---:|---:|
| `baseline_pre_r11` | `new_adopters = bass_p * pop * avg_share * 10  # Scale for meaningful numbers` | 10 | 87.4s |
| `variant_r11` | `adopters_by_segment = _apportion_starter_units(` | 10 | 87.7s |

The probe records the rule it actually ran rather than asserting one, so the
same script drives both arms; the recorded lines above are the proof that each
arm ran the engine it was supposed to.

**Rows differing, per result table:**

| table | rounds 1–10 | round 0 |
|---|---:|---:|
| adoption | **0** | 40 |
| product_demand | **0** | 0 |
| ai_adoption | **0** | 0 |
| reconciliation | **0** | 0 |
| financials | **0** | 0 |
| performance_index | **0** | 0 |
| leaderboard | **0** | 0 |
| product_market | **0** | 0 |
| market_revenue | **0** | 0 |
| coherence | **0** | 0 |

`per_round_team_summary_identical_rounds_ge1 = True` — units sold, revenue, net
income, closing cash, performance index and rank are identical per team per
round for all ten rounds. **Rounds 1–10 are unchanged.** This is the expected
result and it has a mechanical reason, already established under V2-060:
`bass_engine._get_total_cumulative` and `_get_team_cumulative` return `0.0`
when `prev_round < 1`, so round-0 adopters never enter Bass `N`.

**The 40 round-0 rows that do differ** are 8 teams × 5 NA customer segments,
which is the entire round-0 NA adoption table. Fields:

* `new_adopters` / `cumulative_adopters` / `team_share_pct` on all 40 — the
  derivation and the column-meaning change. Example row, TEAM00 × Enterprise &
  Institutional Buyers × NA: **11,700.00 → 5,161.48** adopters, share
  **0.0700 → 0.2867**.
* `fit_score`, `adjusted_fit_score`, `adoption_pool`, `team_attractiveness` and
  `best_product__name` additionally on the 8 **Tech Enthusiasts** rows. That
  segment carries `min_generation_required: 2`, so it is now excluded from the
  apportionment and falls to the zero baseline row — the same treatment
  `preference_engine` gives it from round 1 onward. Previously it was shown a
  computed fit, a populated pool and a best product for a segment no Gen-1 team
  can sell to.

**A caveat on the hash comparison, stated rather than glossed.**
`output_sha256` differs in every round 0–10, and so does the recomputed hash
with round-0 rows excluded. That second figure is **not** evidence of a
round-1+ change: I did not pin `--name-seed`, so the two runs drew different
random company names, and the raw manifest bodies therefore cannot hash equal
whatever the engine does. The valid comparison is the name-normalised one, and
it reads
`manifest_name_normalised_rows_ge1_or_unrounded_differing_by_round = 0` for
**every** round 0–10, with `adoption` the only differing section in any round —
consistent with V2-060's standing note that the adoption manifest section spans
all rounds and so carries round 0 inside every round's hash. The D6 evidence
already demonstrated the pinned-name form of this check; I did not spend two
further replays to reproduce it, because the per-table row comparison above
answers the question directly.

Artifacts: `evidence/calibration/r11_round_zero_replay_comparison.json`, with
the probe and comparator committed alongside it as
`r11_round_zero_replay.py` and `r11_round_zero_compare.py`. Both replays ran
against disposable PostgreSQL 16 containers that were dropped on exit; the
probe refuses to start unless `DB_HOST` is `127.0.0.1`.

---

## Part B — Stage 5: authored preference validation

### First, a correction to the handoff's premise

Stage 5 items 1 and 3 describe the authored preferences as "validated by
nothing". **That is no longer true on this branch.** A calibration-contract
block already exists in `validate_scenario_yaml`
(`core/management/commands/load_scenario.py:146-243`), landed in **`b9510dc`
"CRV2-11: compound market growth and reconcile AI demand"**, together with
`scenario_validation_warnings` and six tests in
`core/tests/test_calibration.py::ScenarioPreferenceValidationTests`.

I verified it rather than rebuilding it. What it already refuses at load:

* an `ideal_value` outside its own feature's `min_value`..`max_value`;
* a `tolerance` of zero or less;
* a negative `weight`;
* a preference on a platform feature whose ceiling is 0 in **every**
  generation (globally unreachable);
* a preference referencing an unknown feature, or a malformed row.

And what it reports without refusing: zero-weight preferences, and positive
weight on a feature unreachable on **Gen 1** specifically.

**The refuse-vs-report split already in place is the right one**, and it
matches the BECSR precedent I was asked to read first. BECSR's `32ed072`
clamped out-of-range ideals because it was repairing **live data in a running
database** with no loader to refuse at; `bfd45c7` excluded dead weight from
scoring because those features had been **pruned from the platform mapping
entirely** and could never come back. Here neither applies: a globally
unreachable feature is an authoring error with no legitimate reading, so it is
refused; a Gen-1-only unreachable feature has a legitimate reading (upgrade
pressure), so it is reported and left loadable. I did not change that split.

**What I added** is the measurement the handoff actually asks for in items 2
and 4, which had not been done: the audit script
`handoff_readiness_v2/evidence/calibration/preference_audit.py` and its output
`preference_audit.json`. It imports no engine code and reads the shipped YAML
directly, so it is evidence about the authored data rather than about the
engine that consumes it.

### Item 1 — ideals in range, across all three scenarios

| scenario | preferences audited | segment × markets | ideals out of range |
|---|---:|---:|---:|
| consumer_electronics_2026 | 658 | 37 | **0** |
| clean_energy_tech_2026 | 670 | 38 | **0** |
| media_entertainment_2026 | 671 | 38 | **0** |

**1,999 authored preferences, no out-of-range ideal in any of them.** BECSR's
finding-3 defect does not exist in this data. The loader guard that would catch
a new one is in place and is proved by a test that injects `ideal = 999`.

### Item 1 — weight degeneracy

Non-degenerate in all three scenarios, by two measures:

| scenario | weight sums | effective terms (1/Herfindahl) | degenerate segment-markets | zero-weight prefs |
|---|---|---|---:|---:|
| consumer_electronics_2026 | 1.00 everywhere | 6.88 – 14.43 | 0 | 5 |
| clean_energy_tech_2026 | 1.00 everywhere | 6.88 – 15.23 | 0 | 0 |
| media_entertainment_2026 | 0.99 – 1.00 | 7.32 – 16.03 | 0 | 0 |

No segment-market puts ≥90% of its weight on one feature, and none sums to
zero. The weakest case still spreads its score across the equivalent of ~7
equally weighted terms. The five zero-weight preferences in consumer
electronics are legal and already reported by the loader as "deliberately
dormant or dead weight"; they are documentation, not scoring.

One presentational note: media's weight sums are 0.99 in some segment-markets
rather than 1.00. Nothing depends on it — `preference_engine` normalises by the
observed total — but it is an authoring inconsistency worth tidying.

### Item 4 — the Gaussian tolerance distribution

Measured as the **half-fit distance** (`tolerance x sqrt(2 ln 2)`, the distance
at which a team's score on that term falls to 0.5) expressed as a fraction of
the feature's own authored range. Above ~1.0 the term cannot discriminate
between teams (decorative); below ~0.05 only a near-exact match scores (cliff).

| scenario | min | median | max | decorative | cliffed |
|---|---:|---:|---:|---:|---:|
| consumer_electronics_2026 | 0.147 | 0.294 | 0.706 | 0 | 0 |
| clean_energy_tech_2026 | 0.118 | 0.236 | 0.654 | 0 | 0 |
| media_entertainment_2026 | 0.118 | 0.294 | 0.706 | 0 | 0 |

**All 1,999 preferences land in the discriminating band.** The tightest
(0.118 of range) still gives a team roughly a fifth of the scale to work with
before its score halves; the widest (0.706) still separates a well-matched team
from a poorly-matched one. **No retuning is proposed and none was done.**

### Items 2 and 3 — the known Gen-1 case, measured

The handoff names `ai_features`, `connectivity` and `iot_integration`:
ceiling 0 on Gen 1, while NA segments carry authored weight on all three. The
same pattern exists in the other two scenarios (`solid_state` / `smart_bms` /
`sodium_ion`; `ai_personalization` / `immersive_media` / `creator_economy`) —
75 preference rows per scenario, 225 in total.

**The framing "dead weight" is not accurate, and this is the substantive
finding.** `gaussian_fit(actual, ideal, tolerance)` is
`exp(-(actual-ideal)² / 2·tolerance²)`. A team pinned at level 0 on a
zero-ceiling feature does **not** score zero on that term — it scores
`exp(-ideal² / 2·tolerance²)`, which for a low ideal and a wide tolerance is
close to 1. So whether a row is a real upgrade incentive or a decorative term
that pays out anyway depends entirely on its authored ideal and tolerance, and
it varies enormously **within** the same scenario:

Consumer Electronics 2026, NA (weight on unreachable features, and what those
terms actually pay a Gen-1 team):

| segment | unreachable weight | pays | drag on the whole fit score |
|---|---:|---:|---:|
| Tech Enthusiasts | 0.260 (26.0%) | 1.4% of its max | **0.2564** |
| Enterprise & Institutional Buyers | 0.088 (8.8%) | 46.1% | 0.0472 |
| Premium Consumers | 0.081 (8.1%) | 44.2% | 0.0451 |
| Sustainability-Conscious Buyers | 0.060 (6.0%) | 80.1% | 0.0120 |
| **Value Seekers** | **0.050 (5.0%)** | **80.1%** | **0.0100** |

Value Seekers — the segment the handoff names — carries `ai_features` ideal
4.0/tolerance 6.0, `connectivity` 4.0/6.0 and `iot_integration` 4.0/6.0. A
Gen-1 team scores **0.8007** on each of those terms without being able to build
them at all. The three together cost it **1.00 percentage point** of fit.

Tech Enthusiasts is the opposite: `ai_features` ideal 16.0/tolerance 4.0 scores
**0.0003** at level 0. A quarter of that segment's entire score is unreachable
until Gen 2, a **25.6-point** drag. (Tech Enthusiasts also carries
`min_generation_required: 2`, so no Gen-1 team competes for it at all — the
weight is unreachable *and* the segment is closed.)

Worst drag per scenario: consumer electronics **0.2564** (Tech
Enthusiasts/APAC), media **0.1630** (Gen Z Digital Natives/EA), clean energy
**0.0103** (Aerospace & Defense/EA). Clean energy authored all 75 of its rows
at ideal 3–4 against tolerance 4, so its entire "dead weight" question is worth
one point of fit and is effectively decorative.

**Both readings, as asked:**

* *Deliberate pull toward upgrading.* Holds for Tech Enthusiasts and Gen Z
  Digital Natives, where the unreachable terms are genuinely unpayable at
  level 0 and a team feels a real 16–26 point penalty until it takes Gen 2.
  For those segments the mechanic works as the handoff hypothesised.
* *Dead weight.* Holds for Value Seekers, Sustainability-Conscious Buyers and
  all five clean-energy segments, where the unreachable terms pay 66–88% of
  their value to **every** team regardless of what anyone builds. These do not
  create upgrade pressure; they slightly compress the score range and lower the
  achievable ceiling for everyone equally — exactly BECSR's `bfd45c7`
  observation that it "never distorted competition … but it made the number
  unreadable".

Note the asymmetry this produces: the segments with the *strongest* upgrade
pull are also the ones a Gen-1 team is *already* locked out of by
`min_generation_required`, while the segments a Gen-1 team can actually sell to
carry the *decorative* version. On this data the mechanic pushes hardest
exactly where it cannot be felt.

**This is put to the rules owner as a decision, not decided here.** See the
questions section.

---

---

## Part C — re-authoring the decorative rows (owner ruling, 2026-09-12)

**The ruling:** *re-author the decorative rows.* Do not exclude unreachable
weight from scoring, and do not leave it as authored. Scenario data only; the
`validate_scenario_yaml` contract stays as found; gated segments' own pull is
not to be touched beyond what the re-authoring requires.

### The fact that shaped the design: "unreachable" has two durations

The Part B measurement treated these features as one class. They are not. In
**all three** scenarios, two of the three appear on **Gen 2** (unlock round 2)
and one only on **Gen 3** (unlock round 5, plus 2 development rounds):

| scenario | reachable from round 2 | reachable only from round 5 |
|---|---|---|
| consumer_electronics | `ai_features`, `iot_integration` | `connectivity` |
| clean_energy_tech | `solid_state`, `smart_bms` | `sodium_ion` |
| media_entertainment | `ai_personalization`, `immersive_media` | `creator_economy` |

So one class is out of reach for a single round and the other for **four rounds
at best**. That distinction drives the two rules; a single uniform edit would
have been wrong.

### Rule A — move: the Gen-3-only rows (60 rows)

A demand no team can act on for the first four rounds is a flat tax, not
pressure. The row is **removed** from segments a Gen-1 team plays in, and its
weight **moved** to that segment-market's highest-weighted Gen-1-reachable
platform feature, so the segment's total weight is unchanged and the weight now
sits on something a team can move.

| scenario | segment | feature removed | weight moved to | fit at level 0 was |
|---|---|---|---|---:|
| consumer_electronics | Value Seekers | `connectivity` | `durability` | 0.8007 |
| consumer_electronics | Enterprise & Institutional Buyers | `connectivity` | `durability` | 0.2780 |
| consumer_electronics | Premium Consumers | `connectivity` | `product_design` | 0.6065 |
| consumer_electronics | Sustainability-Conscious Buyers | `connectivity` | `sustainable_materials` | 0.8007 |
| clean_energy_tech | EV Manufacturers | `sodium_ion` | `charging_speed` | 0.7548 |
| clean_energy_tech | Grid-Scale Energy Storage | `sodium_ion` | `cycle_life` | 0.7548 |
| clean_energy_tech | Consumer Electronics OEMs | `sodium_ion` | `energy_density` | 0.7548 |
| clean_energy_tech | Off-Grid Solar & Residential Storage | `sodium_ion` | `cycle_life` | 0.7548 |
| media_entertainment | Mass Entertainment Viewers | `creator_economy` | `content_quality` | 0.8825 |
| media_entertainment | Premium Content Subscribers | `creator_economy` | `content_quality` | 0.8825 |
| media_entertainment | Cultural Enthusiasts | `creator_economy` | `localization_quality` | 0.8825 |
| media_entertainment | Enterprise & Institutional | `creator_economy` | `content_safety` | 0.8825 |

Each row above is × 5 markets. The move target is deterministic: highest
authored weight among Gen-1-reachable platform features, ties broken by feature
code.

### Rule B — sharpen: the Gen-2 rows (120 rows)

These are the upgrade incentive the scenario intended, authored decoratively: a
low ideal against a wide tolerance paid 0.61–0.88 of its value to a team
sitting at level 0, so nobody felt it. The **weight is kept** and the demand is
made real — the ideal is remapped into the band a Gen-2 platform can actually
reach and the tolerance tightened. Each segment's authored ordering is
preserved: the segment that asked for least still asks for least.

| scenario | ideal remap | tolerance | Gen-2 ceiling | fit at level 0 |
|---|---|---|---|---|
| consumer_electronics | 4→8, 6→10, 8→12 | 5.0/6.0 → 4.0 | 16 | 0.61–0.80 → **0.011–0.135** |
| clean_energy_tech | 4→6 | 4.0 → 2.5 | 7 / 8 | 0.6065 → **0.0561** |
| media_entertainment | 3→5, 4→6, 5→7 | 5.0/6.0 → 2.5 | 8 / 7 | 0.61–0.88 → **0.020–0.135** |

Every remapped ideal is at or below its feature's Gen-2 ceiling — verified as an
assertion, so the target is genuinely attainable once a team upgrades rather
than merely harder.

The full per-row record, all 180 rows with before/after values, is committed as
`evidence/calibration/preference_reauthor_plan.json`; the transformation itself
is `evidence/calibration/reauthor_unreachable_preferences.py` (`--dry-run` /
`--apply`), so the edit is reproducible rather than hand-made.

### Rule C — the 0.99 weight sums (2 rows), and what I found first

**Item 5 asked me to confirm nothing divides by an assumed 1.00 before
tidying. Nothing does — but something worse is true.** Every scorer divides by
the *observed* sum: `preference_engine.py:177` and `:245-248`,
`bootstrap.py:98-99`, `capital_markets.py:173-185`,
`investor_relations.py:57-59`, `alliance_engine.py:49-55`. A 0.99 vector is
therefore harmless to all of them.

`campaign_engine.py:99` is the exception: it accumulates
`weight × feature_strength × multiplier` and **never normalises**, so it treats
the weight vector as already summing to 1.00. A segment authored at 0.99
yields ~1% less campaign bonus than an identical one at 1.00. Tidying makes
that path *more* correct, not less — which is why I tidied rather than left it.

Two blocks were genuinely short: `Cultural Enthusiasts/eu` and
`Gen Z Digital Natives/eu`, both media, both 0.99. Consumer electronics' 13
"off" sums are float representation artefacts (1.000001, 0.999999) on authored
6-decimal weights and were **left alone**. The 0.01 was added to a
Gen-1-**reachable** feature in each case (`localization_quality`,
`audience_engagement`) so that tidying Gen Z — a gated segment — did not alter
its upgrade pull, which item 4 puts out of scope.

### What was deliberately not touched (item 4)

The three gated segments — Tech Enthusiasts, Aerospace & Defense, Gen Z Digital
Natives — keep every preference row exactly as authored. Verified numerically:
their drag is **identical to four decimal places** before and after (0.2564,
0.0103, 0.1489). The only gated row that changed at all is Gen Z's tidied
`audience_engagement` weight, on a reachable feature.

**Options for the separate design question, reported and not decided.** One
input the owner should have: a gated segment's Gen-2 demand is arguably already
self-consistent. `preference_engine.py:70-76` zeroes a team's fit for a segment
it cannot enter, and entering Tech Enthusiasts *requires* Gen 2 — which is the
same platform that unlocks `ai_features`. A team that can compete for the
segment can also build what it asks for, so that 25.6-point drag is never
actually borne by a scoring team. The residual that is **not** self-consistent
is the Gen-3-only row: a Gen-2 team entering at round 2 still cannot build
`connectivity` until round 5–7.

- **(a) Leave it.** Defensible on the above: the Gen-2 half is coherent, and
  only the Gen-3-only row is genuinely stranded.
- **(b) Apply Rule A to gated segments too** — move only their Gen-3-only
  weight to a reachable feature, leaving the Gen-2 pull intact. Smallest change
  that removes the remaining stranded weight.
- **(c) Drop `min_generation_required`** and let the sharpened preference do
  the gating, so the segment is enterable but unwinnable without the upgrade.
  Largest change; would alter who competes for those segments at all.

### The consequence, measured (item 3) — **this is the finding**

Two 8-team, 10-round fixed-policy replays, **`--name-seed 20260912` pinned** so
the rosters are provably identical (`teams_equal: True`), differing only in the
scenario data. Both at `4d2169c`.

**Outcomes did shift in rounds 1–10.**
`per_round_team_summary_identical_rounds_ge1 = False`, with rows differing in
every table (product_demand 576, adoption 328, product_market 87, leaderboard
79, performance_index 79, market_revenue 72, financials 70, coherence 69,
ai_adoption 80, reconciliation 40). `output_sha256` differs in every round —
this time meaningfully, since names are pinned.

**Magnitude is small and uniform in direction:**

| round | industry units before | after | delta | PI spread before | after |
|---:|---:|---:|---:|---:|---:|
| 1 | 205,216 | 203,806 | −0.69% | 8.79 | 8.69 |
| 5 | 306,340 | 304,612 | −0.56% | 29.96 | 29.73 |
| 10 | 499,873 | 497,849 | −0.40% | 40.96 | 40.78 |

Per team at round 10: revenue **−1.48% … +0.34%**, performance index down
**0.74–1.64 points**, competitive dispersion essentially unchanged (spread
40.96 → 40.78). Divergence **shrinks** across the game rather than compounding,
because the sharpened demands bite hardest while every team is still on Gen 1.

**The round-10 finishing order is unchanged.** Rank differs in 20 of 80
team-rounds, but **none of those flips crossed a performance-index gap wider
than 0.5 points** — the largest gap crossed was 0.22, and most were 0.00–0.11.
Every flip is between The Innovator and The Green Pioneer (and their
duplicates), two archetypes that score within a rounding error of each other; a
change of ~0.5–1.0 PI reshuffles them. That is near-tie churn, not competitive
movement. **It is still worth the owner's attention**, because a cohort with
duplicate archetypes will contain such near-ties and their displayed rank is
not robust to a change of this size.

**One team gained, and it is the right one.** The Brand Builder
(`product_design` 11) is the only profile whose revenue rose (+0.34%), because
Premium Consumers' `connectivity` weight moved onto `product_design` — the
feature it has authored strength in. Weight that previously paid out to
everyone regardless now rewards the team that actually built the thing. That is
the ruling working as intended.

**One number to read carefully:** net income swings further than revenue —
up to −17.90% for The Innovator at round 5 on a −1.48% revenue change. That is
leverage on a small base (net income is a difference of large numbers
mid-game), not a 17% economic effect. Revenue, units and PI are the honest
magnitude measures here.

**Verdict, for the owner rather than absorbed:** the change is *material enough
to be real* (every result table moves) and *immaterial enough not to alter the
competition outcome* (finishing order unchanged, dispersion preserved, all rank
flips inside 0.22 PI). It shifts the early game, which is where the ruling
intended it to bite.

### Before and after, on the authored data

| scenario | preferences | dead-weight rows | unreachable weight total |
|---|---|---|---|
| consumer_electronics | 658 → **638** | 75 → **55** | 2.678 → **2.184** |
| clean_energy_tech | 670 → **650** | 75 → **55** | 0.750 → **0.550** |
| media_entertainment | 671 → **651** | 75 → **55** | 1.590 → **1.370** |

Still 0 out-of-range ideals, 0 degenerate segment-markets, and every tolerance
in the discriminating band in all three scenarios. The 55 remaining rows are
the 15 gated rows left alone plus the 40 playable Gen-2 rows, which now carry
real pressure rather than decoration.

Drag per segment, home market shown (gated segments in bold are unchanged):

| scenario | segment | drag before | drag after |
|---|---|---:|---:|
| consumer_electronics | Value Seekers | 0.0100 | **0.0259** |
| consumer_electronics | Sustainability-Conscious Buyers | 0.0120 | **0.0346** |
| consumer_electronics | Premium Consumers | 0.0451 | **0.0593** |
| consumer_electronics | Enterprise & Institutional Buyers | 0.0472 | 0.0465 |
| consumer_electronics | *Tech Enthusiasts (gated)* | 0.2564 | *0.2564* |
| clean_energy_tech | all four playable segments | 0.0103 | **0.0189** |
| clean_energy_tech | *Aerospace & Defense (gated)* | 0.0103 | *0.0103* |
| media_entertainment | Mass Entertainment Viewers | 0.0035 | **0.0173** |
| media_entertainment | Cultural Enthusiasts | 0.0035 | **0.0173** |
| media_entertainment | Enterprise & Institutional | 0.0043 | **0.0181** |
| media_entertainment | Premium Content Subscribers | 0.0110 | **0.0290** |
| media_entertainment | *Gen Z Digital Natives (gated)* | 0.1489 | *0.1489* |

The loader contract passes on all three (`validate_scenario_yaml` → no errors).
Its warnings show the change precisely: the Gen-3-only features drop from 25
preferences to **5** — the gated segment's five markets, all that remain —
while the Gen-2 features correctly stay at 25, because their weight is retained
and is now real.

### Part C commands

| command | result | duration |
|---|---|---|
| `reauthor_unreachable_preferences.py --dry-run` | 182 row actions planned | <1s |
| invariant check on throwaway copies | **ALL INVARIANTS HOLD** | <1s |
| `reauthor_unreachable_preferences.py --apply` | 182 applied | <1s |
| `test-postgres` × 3 focused modules | **Ran 22 — OK** | 7.43s |
| 2 × pinned replay (8 teams, 10 rounds) | complete | 89.2s / 86.9s |
| loader contract on all three scenarios | 0 errors | <1s |

Before applying, the transformation was run against **copies** and asserted to
preserve every weight sum, keep every ideal in range and at or below its Gen-2
ceiling, remove exactly one row per playable segment-market, and leave gated
segments byte-identical. Only then was it applied for real.

## Commands, counts and durations

All test runs used `backend/scripts/test-postgres`, which starts its own
disposable PostgreSQL 16 container with a generated credential and drops it on
exit. Every run was serialised under `flock -w 1800
/tmp/globalstrat-backend-test.lock`. The production database at 192.168.50.38
was never contacted and no systemd environment file was read.

| command | result | duration |
|---|---|---|
| `test-postgres core.tests.test_round_zero_adoption.RoundZeroReconciliationTests …FitWeightingTests …AuthoringErrorTests` | **Ran 8 tests — OK** | 0.162s (2m17s wall incl. container) |
| `test-postgres core.tests.test_round_zero_adoption core.tests.test_leaderboard_tiebreak core.tests.test_calibration` | **Ran 22 tests — OK** | 7.681s (21s wall) |
| `test-postgres core.tests.test_round_zero_adoption` **against the reverted pre-change engine** | **Ran 9 tests — FAILED (failures=11)** | 4.599s |
| `preference_audit.py` (no database) | 1,999 preferences across 3 scenarios | <1s |

**The tests fail without the change**, which is the requirement. Reverting only
`core/engine/bootstrap.py` to `e1b744c` and rerunning produced 11 failures
across 8 of the 9 test methods, including all three shipped scenarios. The one
method that still passed is the pinned display-oddity assertion, which is
deliberately a statement about unchanged behaviour.

No full suite, no load run, no concurrency matrix and no determinism matrix was
run — those belong to GSP-CRV2-09. The seven pre-existing full-suite failures
(V2-071 / V2-074) were not touched and are not in any module I ran.

**Commit policy — the hook does fail, but not for the stated reason.** The
handoff said the pre-commit hook fails because `checks/.aide-checks-rev` is
absent, and that its header sanctions `--no-verify`. In this worktree that file
is **present**. The hook fails on something else: a **revision mismatch** —
`run-checks` is built from `e1b744c` while the repo vendors `e710f26`, and it
exits 2 rather than let a stale runner report a pass for checks it does not
carry ("a stale runner reports PASS for checks it does not carry. That is a
false pass, not a pass"). The hook's own header still sanctions the bypass
("Bypassable with --no-verify; the deploy gate is the layer that is not"), so
this work was committed with `--no-verify` and the **actual** reason is
recorded here rather than the assumed one. Re-vendoring the runner is an owner
action, not a builder's.

## Files changed

| file | change |
|---|---|
| `backend/core/engine/bootstrap.py` | R11 derivation, the rule in the module docstring, ordered cent-exact apportionment, fail-loud guard |
| `backend/core/tests/test_round_zero_adoption.py` | new — 9 test methods pinning the authored source |
| `handoff_readiness_v2/evidence/calibration/preference_audit.py` | new — Stage 5 items 1–4 audit |
| `handoff_readiness_v2/evidence/calibration/preference_audit.json` | new — its machine-readable output |
| `handoff_readiness_v2/evidence/calibration/r11_round_zero_replay.py` | new — the round-zero replay probe |
| `handoff_readiness_v2/evidence/calibration/r11_round_zero_compare.py` | new — its comparator |
| `handoff_readiness_v2/evidence/calibration/r11_round_zero_replay_comparison.json` | new — the rounds 1–10 comparison |

Part C (the 2026-09-12 ruling) adds, in a second commit:

| file | change |
|---|---|
| `backend/scenarios/consumer_electronics_2026.yaml` | **data** — 20 rows moved/sharpened per Rules A/B |
| `backend/scenarios/clean_energy_tech_2026.yaml` | **data** — 20 rows moved/sharpened per Rules A/B |
| `backend/scenarios/media_entertainment_2026.yaml` | **data** — 20 rows moved/sharpened, 2 weight sums tidied to 1.00 |
| `handoff_readiness_v2/evidence/calibration/reauthor_unreachable_preferences.py` | new — the transformation, `--dry-run` / `--apply` |
| `handoff_readiness_v2/evidence/calibration/preference_reauthor_plan.json` | new — the per-row record, all 180 rows |
| `handoff_readiness_v2/evidence/calibration/preference_reauthor_replay_comparison.json` | new — the pinned before/after replay |
| `handoff_readiness_v2/evidence/calibration/preference_audit.json` | regenerated against the re-authored data |

**No scoring or engine code changed in Part C** — it is scenario data plus
evidence, exactly as the ruling scoped it. The `validate_scenario_yaml`
contract is untouched.

I did not touch `core/views/decisions.py`, the serializers,
`core/views/course.py`, `core/views/core.py`,
`core/services/route_inventory.py`, or any existing test module — all named as
other builders' territory. `V2_FINDINGS_REGISTER.md` is not edited; proposed
entries are handed over below.

## EXECUTION_PROTOCOL preflight answers

* **Did inventory start from registered models, not code using the new
  abstraction?** Yes. The authored-data inventory came from the scenario YAML
  sections and the Django model registry (`FirmStarterProduct`,
  `SegmentDefinition`, `SegmentPreference`, `PlatformFeatureCeiling`), not from
  grepping for the new helper.
* **Is there an active legacy or alternate entry point?** Yes, and it is
  covered: `bootstrap_round_zero` has two callers —
  `management/commands/initialize_game.py:253` and
  `views/scenario_views.py:461`. Both reach the same function, so both get the
  derived figure; there is no second round-0 adoption writer.
* **Does a failure/refusal audit survive rollback?** The fail-loud guard raises
  before any `RoundResultAdoption` row is written for that team, inside the
  caller's transaction, so a refused bootstrap leaves no partial round-0 table.
* **Is each correlation ID generated once?** Not applicable — no request,
  audit or log identifier is created on this path.
* **Is background/external work delayed until commit?** Not applicable — the
  change performs no background or external work.
* **Do claimed environment values describe the executing process?** Yes. Every
  figure above came from a disposable container created by the named script in
  this worktree; the replay probe refuses to run unless `DB_HOST` is
  `127.0.0.1`.
* **Does provenance identify runtime bytes?** Yes — branch
  `crv2-11-round-zero-and-preferences` off `e1b744c`, with the changed-file
  list above. The audit script and its JSON are committed together.
* **Do README commands run exactly as written?** The commands in this report
  are the ones that were run, verbatim.
* **Do P0/P1/P2 labels match their definitions?** The proposed entries below
  are P2: they change a briefing-screen figure and a scenario contract, not a
  competitive outcome.
* **Does each negative test prove no mutation occurred?**
  `test_starter_units_with_no_reachable_customer_segment_raises` asserts the
  `ValueError` and its message; the bootstrap aborts before writing that team's
  adoption rows.

## Proposed register entries — for the owner to land, not edited by me

**V2-060 (D6) — update the disposition.** The rules question was answered by
R11 and the implementation is now built on
`crv2-11-round-zero-and-preferences`. Suggested replacement for the
disposition: *Implemented. `bootstrap.py` derives round-0 adopters by
apportioning the authored `FirmStarterProduct.unit_volume` across the home
market's customer segments in proportion to `bass_p x population x preference
fit`, settled to the cent, with `min_generation_required` segments excluded and
a loud failure where the authored data cannot support the derivation. The
reconciliation is asserted for all three shipped scenarios. The retired `* 10`
is deleted and no constant replaces it. Measured error under the retired rule:
consumer electronics 3.21x, clean energy 0.34x, media 22.3x against round-0
units sold — no single constant could have reconciled all three.*

**New entry — round-0 `team_share_pct` column meaning.** P2. The round-0
adoption row previously carried the authored firm-level market share in the
column that carries segment pool share from round 1 onward; it now carries pool
share in both. Student-visible, reversible in one line, flagged for the owner.

**New entry — Gen-1 unreachable preference weight is two different mechanics.**
P2. 225 authored preference rows across the three scenarios put weight on
platform features with a Gen-1 ceiling of 0. Measured, they split into genuine
upgrade pressure (up to 25.6 points of fit) and effectively decorative terms
that pay 66–88% to every team regardless. Awaiting a rules-owner ruling; no
data was retuned.

**Not a new finding, recorded for accuracy:** `CRV2-13_D2_D6_FOLLOWUP.md`
still states that the multiplier "changes the round-one Bass cumulative state
and therefore later competitive demand". The register already records that this
is wrong; my replay reconfirms it.

## Questions for the rules owner

1. **RULED 2026-09-12 — re-author the decorative rows; implemented in Part C.
   This question is closed.** The original framing is kept for the record:
   The data contains both
   a real upgrade incentive and a decorative term, under one authoring pattern.
   Three coherent answers: (a) leave it, and accept that the mechanic is a
   strong pull in two segments and a rounding artefact in eight; (b) treat
   unreachable weight as genuinely dead and exclude it from the fit
   denominator, as BECSR did in `bfd45c7` — this *raises* every team's fit
   equally and makes the number readable, and costs the upgrade pressure in
   Tech Enthusiasts and Gen Z; (c) keep the weight but re-author the decorative
   rows so the ideal is out of reach at level 0, making the incentive real
   everywhere. **I have not chosen.** (b) is the BECSR precedent but BECSR's
   features were permanently unmappable, whereas these unlock at round 2 — the
   cases are not the same, which is why this is a rules question rather than a
   port of a prior fix.
2. **Does the pull belong where it can be felt?** The two segments with the
   strongest upgrade pull both also carry `min_generation_required: 2`, so a
   Gen-1 team is already excluded from them entirely. If the intent is to make
   teams *want* Gen 2, the incentive currently sits in segments they cannot
   enter, while the segments they can sell to carry the decorative version.
   That may be deliberate layering; it has never been stated.
3. **Round-0 `team_share_pct`** — should it carry segment pool share
   consistently with rounds 1–10 (what it now does), or revert to the authored
   firm-level market share?
4. **DONE — Media's 0.99 weight sums** tidied to 1.00 (Part C, Rule C), after
   confirming no scorer divides by an assumed 1.00 and finding that
   `campaign_engine.py:99` does not normalise at all.
5. **NEW, open — should a segment teams cannot enter carry upgrade pressure?**
   Options (a)/(b)/(c) are set out in Part C with the measurement behind them,
   including the point that a gated segment's Gen-2 demand may already be
   self-consistent. Not decided here.
6. **NEW, for awareness — near-tie rank churn.** The re-authoring reshuffled
   rank in 20 of 80 team-rounds without any flip crossing a 0.5-point index
   gap. Duplicate archetypes score within ~0.02 of each other, so displayed
   mid-table rank is not robust to a change of this size. A tie-break rule, or
   accepting it, is a rules decision.
