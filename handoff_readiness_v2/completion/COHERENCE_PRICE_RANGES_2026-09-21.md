# Coherence price ranges (N3) and the determinism fixture's Team-id dependency (N4)

**Date:** 2026-09-21
**Branch:** `crv2-11-coherence-price-ranges`, from `crv2-release-integration` at `f46d173`
**Observes:** `EXECUTION_PROTOCOL.md`, `specs/STANDING-DISCIPLINE.md`, `DETERMINISM_BOUNDARY.md`
**Source of both items:** `completion/CREATION_PATHS_AND_REFERENCE_PRICES_2026-09-21.md` (N3, N4, Q6)

**No gate is claimed closed.** N3 is a **proposal pending owner confirmation of
the derivation rule** (Q6 of the source report). Nothing here was run against
production, and no register, checklist or owner-ruling file was edited.

---

## 1. State at head (`f46d173`), verified before any change

**N3 — open, as reported.** `backend/core/engine/coherence.py:29` held
`PRICE_RANGES = {'budget': (100, 300), 'mainstream': (250, 550), 'premium':
(500, 900), 'ultra_premium': (800, 1500)}` and `_score_positioning_price`
scored every retail price against it directly, with `(0, 9999)` for a
positioning it did not know. Measured against the three shipped YAMLs, each
starter product at its own authored starting price:

| Scenario | Starter products | Scoring above 0.0 at head | Component total at head |
|---|---:|---:|---:|
| Consumer Electronics | 16 | 16 | 16.0 of 16 |
| Clean Energy | 16 | **0** | **0.0** of 16 |
| Media | 16 | **0** | **0.0** of 16 |

(The source report said "most" Media products; at authored prices it is all 16.)
Also red by value through the engine: a resolved Clean Energy round and a
resolved Media round both published `positioning_price.score == 0.0` for every
team (§5).

**N4 — open, as reported, and it is a test defect, not a product defect.**
Details in §3. The manifest code is not at fault: no ordering or keying defect
was found in `resolution_manifest` / `manifest_sections`.

---

## 2. N3 — the repair

### The rule (the thing the owner is asked to confirm)

Each bound of the old ladder is read as a ratio of the Consumer Electronics
reference price for its tier; the same ratio is applied to the running
scenario's own reference price for that tier:

```
bound(scenario, tier) = old_bound(tier) * reference_price(scenario, tier)
                                        / reference_price(Consumer Electronics, tier)
```

No number is introduced. The ladder already existed (`coherence.PRICE_RANGES`,
kept unchanged as the basis) and so did the denominators (250 / 420 / 700 /
1000: V2-023, migration 0077, `consumer_electronics_2026.yaml`). The source
report observed that no *single* multiple reproduces the four ranges; that is
right, and is why the ratio is per tier and per bound — eight ratios, not one.

### Ratio table

| Tier | Old range | CE reference | Low ratio | High ratio |
|---|---|---:|---|---|
| budget | 100 – 300 | 250 | 100/250 = 2/5 = 0.400000 | 300/250 = 6/5 = 1.200000 |
| mainstream | 250 – 550 | 420 | 250/420 = 25/42 = 0.595238 | 550/420 = 55/42 = 1.309524 |
| premium | 500 – 900 | 700 | 500/700 = 5/7 = 0.714286 | 900/700 = 9/7 = 1.285714 |
| ultra_premium | 800 – 1500 | 1000 | 800/1000 = 4/5 = 0.800000 | 1500/1000 = 3/2 = 1.500000 |

Every low ratio is below 1 and every high ratio above it, so a product priced
at its tier's reference is always inside its range, in any scenario.

### Derived ranges

| Tier | Consumer Electronics (ref → range) | Clean Energy (ref → range) | Media (ref → range) |
|---|---|---|---|
| budget | 250 → 100 – 300 | 2200 → 880 – 2640 | 71 → 28.40 – 85.20 |
| mainstream | 420 → 250 – 550 | 3700 → 2202.38 – 4845.24 | 120 → 71.43 – 157.14 |
| premium | 700 → 500 – 900 | 8900 → 6357.14 – 11442.86 | 270 → 192.86 – 347.14 |
| ultra_premium | 1000 → 800 – 1500 | 13000 → 10400 – 19500 | 390 → 312 – 585 |

Non-whole bounds are shown to the cent; the comparison uses the unrounded
value. The 1.0 / 0.5 / 0.0 rule and its 20% shoulder are unchanged.

### Effect, starter products at authored prices

| Scenario | Above 0.0 before | Above 0.0 after | Component total before → after |
|---|---:|---:|---|
| Consumer Electronics | 16 | 16 | 16.0 → 16.0 (identical) |
| Clean Energy | 0 | 10 | 0.0 → 9.0 |
| Media | 0 | 15 | 0.0 → 13.5 |

The seven that still score 0.0 — Clean Energy `GridCell Standard`, `AxisStore`,
`EcoCell Home`, `BaseCell Lite`, `HomeVolt`, `HomeVolt Compact`; Media
`OmniPass Lite` — are **exactly** `KNOWN_RESIDUAL_CLAMPS` from V2-114's own
test. Same cause (Clean Energy's mainstream tier spans 9.4x; one range cannot
hold it), same open owner question, not a new one. A test pins the set to that
list so it cannot grow silently.

### Code changes

`backend/core/engine/coherence.py`

- `PRICE_RANGES` kept, byte for byte, now documented as the basis ladder.
- `PRICE_RANGE_BASIS_REFERENCES` added (250 / 420 / 700 / 1000). A test pins it
  to the references the shipped Consumer Electronics scenario actually loads,
  so the two cannot drift.
- `scenario_price_ranges(scenario)` added. Exact arithmetic (`Fraction`,
  multiply before divide, from the authored string rather than its float), so
  Consumer Electronics derives the **integers** `100`, `300`, … and not
  `100.0`: the range is formatted into `RoundResultCoherence.breakdown`, which
  is inside the hashed `coherence` section, and `"100.0-300.0"` would have
  moved the competitive hash of every Consumer Electronics round.
- **Refusal.** It calls `scenario_reference_prices()` first — the V2-023
  function — so a missing, zero, negative, NaN or infinite reference raises
  `InvalidScenarioConfiguration` naming the key. There is no fallback to the
  Consumer Electronics dollars. In a real round this is the second line, not
  the first: `_run_phase_1` already calls `scenario_reference_prices()` before
  the first competitive write (`advance_round.py`, V2-023) and turns a failure
  into `InvalidScenarioConfigurationError`, so a missing reference stops the
  round before any mutation. The check inside coherence covers a caller that
  reaches the scorer some other way; nothing between `calculate_coherence` and
  its caller catches it.
- `_score_positioning_price(team, submission, scenario)` takes the scenario
  (`context.scenario` at its one call site). An unknown positioning now raises
  instead of scoring against `(0, 9999)` — full marks for any price under
  $9,999 was a silent fallback of the same kind. `TeamProduct.positioning` is
  limited to the four tiers by its choices, and `bass_engine` already refuses
  the same condition earlier in the round for any such product that is on sale
  with a positive fit, so no legal round changes.

`MANIFEST_SCHEMA_VERSION` stays **6**. Values change; no section, field or key
is added, removed or re-typed (`breakdown.positioning_price` keeps `score` and
`details[product, market, price, range, aligned]`). `SchemaProvenanceTests`
green.

---

## 3. N4 — cause and repair

### Cause: a test-fixture defect

`ManifestSnapshotIntegrationTests._decision_rows` sourced each team 50/50 from
the first two suppliers by `supplier_id`, one of which is flagged
`xinjiang_adjacent`. 50% exposure is over the UFLPA regime's 5% threshold, so
the fixture armed a UFLPA enforcement draw for every team, at probability 0.15,
in NA — the only market the fixture's products are sold in during round 1.

That draw is `get_rng(cohort, round, 'compliance_enforcement:uflpa:<team.id>:NA')`
— seeded on `Team.id` **deliberately** (V2-011, commented at the call site: a
rename must not resegment a team's stream; DETERMINISM_BOUNDARY residual
condition 1). `setUp` pins `section_id = 4242` so the fixture's draws do not
move with the game id, but the team id is inside the operation id, so the pin
does not reach it.

A detained team is frozen out of the market, and `bass_engine` writes no
`product_demand` row for a frozen team-market. Reproduced arithmetically from
`core/engine/rng.py`, cohort 4242, round 1:

| Team id | 132 | 133 | 134 | 135 | 136 | 137 |
|---|---|---|---|---|---|---|
| draw | 0.2190 | 0.8973 | 0.6833 | **0.0478** | **0.1370** | **0.0070** |
| < 0.15 → detained | no | no | no | yes | yes | yes |

So at 132–134 nobody is detained (24 rows), at 135–137 everybody is (0 rows),
and wherever one of three is, 16 — the three figures in the source report.
Confirmed on the database: at 135–137 the round wrote three
`ComplianceEnforcementEvent` rows, `uflpa`, NA, `freeze_until_round=2`,
`xinjiang exposure 50% > 5%`; at 132–134, none. In ids 1–399 there are four
such windows of three (135, 286, 359, 375).

**Not a product defect.** Manifest construction, row tokens and section order
were not involved. The id-keyed seed is a recorded design decision with a
recorded boundary condition, and replay against a restored database (ids
preserved) is unaffected.

### Reproduction at head

Running `core.tests.test_game_creation_paths core.tests.test_manifest_determinism`
in one process at head was **green** (59 tests): at `f46d173` the creation-path
module does not leave the team sequence at 135 when the fixture runs. The
dependency is real regardless and was reproduced directly on head's code by
setting the `team` sequence to 135 before the fixture builds its game:
`AssertionError: [] is not true` from the named test, `DEMAND 0`. At 132:
passes, `DEMAND 24`.

### Repair

`backend/core/tests/test_manifest_determinism.py`

- The fixture sources from the first two suppliers that are **not**
  `xinjiang_adjacent`, so exposure is 0% and no enforcement draw is armed. UFLPA
  is the only evaluable trigger in round 1 (customs documentation is locked
  until round 5; the other three regimes' triggers return "not evaluable").
- `setUp` body moved to `_build_fixture_game()` so a test can rebuild the
  fixture at chosen ids.
- `test_fixture_arms_no_enforcement_draw_keyed_on_a_team_id` — patches the
  compliance engine's `get_rng` so every draw fires, resolves the round, and
  requires that the draw was never taken, no enforcement event exists, and
  ledger rows do. Independent of whatever ids the run happens to hand out.
- `test_ledger_rows_exist_at_the_team_ids_that_used_to_freeze_them` — sets the
  team sequence to 135, rebuilds the fixture, asserts the ids are 135–137 and
  that ledger rows exist: the reported symptom, literally.

No pinned hash depends on the fixture's supplier choice (none is pinned in the
module), and no evidence harness imports the fixture.

---

## 4. Commits

| Commit | Content |
|---|---|
| `455f0cf` | N3: engine change + `core/tests/test_coherence_price_ranges.py` |
| `aede440` | N4: fixture repair + two tests |
| `62cb69c` | Player-language string inventory regenerated (own commit) |
| (this report) | following commit |

The inventory was stale only because of `455f0cf` (line numbers in
`coherence.py` and the text of one f-string); 2275 rows before and after.
`generate_inventory.py --check` is clean at `62cb69c`.

---

## 5. Red, then green

**N3, by value, through `_run_phase_1`** — `coherence.py` restored to `f46d173`,
new tests in place:

```
scripts/test-postgres core.tests.test_coherence_price_ranges.ResolvedRoundTests
FAIL: test_clean_energy_round_publishes_a_positioning_price_score
  AssertionError: 0.0 not greater than 0.0
FAIL: test_media_round_publishes_a_positioning_price_score
  AssertionError: False is not true
Ran 2 tests — FAILED (failures=2)                                   17s wall
```

The whole new module against the old engine: `Ran 12 tests — FAILED (errors=19)`
(27s) — the rest fail on the names and the signature that did not exist, which
is red but not informative; the two above are the ones that fail on the score.
With the change: `Ran 16 tests — OK`.

Consumer Electronics identity is proved three ways, all green:
`test_consumer_electronics_ranges_are_the_old_constants_exactly` (equality,
`repr` equality and `type is int`);
`test_component_is_identical_to_the_function_it_replaced` and
`test_every_tier_is_identical_…` (the pre-change function kept verbatim as an
oracle; 36 prices on every boundary and a cent either side, plus an unpriced
product, all four tiers, compared as tuples and as serialised JSON);
`test_consumer_electronics_round_publishes_what_it_always_did` (a resolved
round's stored `breakdown.positioning_price` equals the oracle's, serialised).

**N4** — new tests in place, fixture unrepaired:

```
FAIL: test_fixture_arms_no_enforcement_draw_keyed_on_a_team_id
  AssertionError: 3 != 0 : the fixture armed a compliance enforcement draw, which is seeded on Team.id
FAIL: test_ledger_rows_exist_at_the_team_ids_that_used_to_freeze_them
  AssertionError: False is not true
Ran 2 tests — FAILED (failures=2)                                   16s wall
```

Repaired: `Ran 2 tests — OK` (17s).

---

## 6. Commands, results, durations

All as `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock
scripts/test-postgres <labels>` — disposable Postgres container per run, no
`--parallel` except the last. Wall time includes container start.

| # | Labels | Code | Result | Wall |
|---|---|---|---|---:|
| 1 | `test_game_creation_paths test_manifest_determinism` | head | 59 OK (N4 not hit by module order at head) | 39s |
| 2 | N4 probe, team sequence 135 (scratch module, not committed) | head | named test FAILS, 0 ledger rows, 3 UFLPA events | 15s |
| 3 | N4 probe, team sequence 132 | head | passes, 24 rows, 0 events | 15s |
| 4 | 2 new N4 tests | fixture unrepaired | 2 FAIL (red) | 16s |
| 5 | 2 new N4 tests | repaired | 2 OK | 17s |
| 6 | `test_coherence_price_ranges` | old engine | 12 run, errors=19 (red) | 27s |
| 7 | `…ResolvedRoundTests` | old engine | 2 FAIL by value (red) | 17s |
| 8 | `test_coherence_price_ranges` | new engine | 16 OK | 37s |
| 9 | `test_coherence_price_ranges test_game_creation_paths test_manifest_determinism test_scoring_dispositions test_r31_llm_not_in_grades test_scenario_reference_prices test_reference_price test_calibration test_engine test_rd_scoring_retired` | final | **220 OK** | 89s |
| 10 | `test_game_creation_paths test_manifest_determinism`, one process, serial | final | **61 OK** | 44s |
| 11 | `core --parallel 8` (the one permitted full run) | `62cb69c` | **1231 OK** | 135s |

Run 8 was preceded by one run (37s) in which a test of mine counted round-0
coherence rows as well as round-1; the test was wrong, not the engine, and was
corrected before run 9. Two extra probe runs (15s each) located the cause of N4.

---

## 7. Stored evidence this invalidates

N3 changes `RoundResultCoherence` (`formula_score`, `blended_score`,
`breakdown.positioning_price`) for **Clean Energy and Media games only**, and
through it anything downstream of coherence for those games: the `coherence`
manifest section and so `output_sha256`; grading's `coherence_score` dimension
(`core/services/grading.py`); and Phase-2 prose that quotes the score. The
performance index does not read coherence. Consumer Electronics is
byte-identical, so nothing recorded for it moves.

Checked under `handoff_readiness_v2/evidence/`:

- Every stored manifest and replay comparison that contains a `coherence`
  section or quotes a coherence score (`evidence/determinism/**`,
  `evidence/durable-narratives/**`, `evidence/durable-narratives-rework/**`,
  `evidence/post-close-disputes/replay/**`,
  `evidence/calibration/preference_reauthor_replay_comparison.json`,
  `evidence/calibration/r11_round_zero_replay_comparison.json`) is a
  **Consumer Electronics** game. **Not invalidated.**
- The only stored evidence resolved on another scenario is
  `evidence/adversarial-balance/negative-sweep*.{json,txt}` and
  `phase1-seed.txt` / `phase1-probe-log.txt` (Clean Energy, because
  `setup_test_game` takes the first scenario). None of them records a coherence
  value or a competitive hash. **Not invalidated as recorded**; a re-run would
  now produce different coherence rows than the run that was stored.

So: **no checked-in evidence file is invalidated.** What *is* invalidated is
any `ResolutionManifest.output_sha256` already stored in a live database for a
resolved Clean Energy or Media round — a replay under this code will not match
it. See §9.

N4 changes a test fixture only. It invalidates nothing.

---

## 8. EXECUTION_PROTOCOL preflight (applicable questions)

- *Alternate entry point?* `_score_positioning_price` has one caller
  (`calculate_coherence`); `PRICE_RANGES` has no reader outside `coherence.py`
  and two assertions in `test_engine.py`, which still hold. The `range` string
  is not rendered by the frontend (`ResultsPage.js` shows the component score
  only), and no player-facing copy or scenario YAML quotes the old dollars.
- *Does each negative test prove the engine did not proceed?* The refusal tests
  assert the exception from `scenario_price_ranges` and from
  `_score_positioning_price` itself — no score tuple is returned.
- *Do P-labels match their definitions?* Proposed labels are carried over from
  the source report unchanged; I have not re-argued them.
- Full backend suite: 1, on the final code commit. No evidence directory was
  written; no other handoff's harness was run.

---

## 9. What a reviewer should distrust

Only what could not be resolved from here.

1. **The derivation rule is a proposal.** It is the rule the task specified and
   it introduces no number, but whether positioning-price coherence *should*
   scale with the reference prices, and with these eight ratios, is Q6 and is
   the owner's to confirm. If the owner picks different bounds, the Consumer
   Electronics identity tests are what will say whether that ladder moved too.
2. **Clean Energy's mainstream tier.** Six of its ten mainstream starter
   products still score 0.0 at their authored prices, because one range cannot
   span 9.4x. This is V2-114's existing residual, already before the owner; it
   needs a scenario-authoring decision (split the tier or re-tier the
   products), not an engine change.
3. **Live games.** Whether the production database holds resolved Clean Energy
   or Media rounds — whose stored competitive hashes would no longer replay,
   and whose published coherence would differ if re-resolved — was not checked,
   because the production host is out of bounds for this work. It needs someone
   with access to look before this merges to a release that serves such a game.

---

## 10. Proposed register text (not applied)

> **V2-1xx (was N3) — positioning-price coherence scored every scenario against
> Consumer Electronics dollars.** P1 proposed. `coherence.PRICE_RANGES` was an
> engine constant; the component was 0.0 for all 16 Clean Energy and all 16
> Media starter products at their authored prices. **Repaired on
> `crv2-11-coherence-price-ranges` (`455f0cf`), pending owner confirmation of
> the rule:** each bound is the same ratio of the tier's reference price that
> it is in Consumer Electronics (2/5–6/5, 25/42–55/42, 5/7–9/7, 4/5–3/2),
> applied to the scenario's own `reference_price_*`. Consumer Electronics
> byte-identical (proved). Missing reference refuses. After: 10 of 16 Clean
> Energy and 15 of 16 Media starters score; the remaining seven are V2-114's
> `KNOWN_RESIDUAL_CLAMPS`. Changes coherence for Clean Energy and Media only;
> schema version unchanged at 6. Status: repaired, awaiting ruling on Q6.

> **V2-1xx (was N4) — determinism fixture depended on `Team` primary keys.**
> P2 proposed (verification apparatus; sibling of V2-116). Test defect, not a
> product defect: the fixture sourced 50% from a Xinjiang-adjacent supplier,
> arming the UFLPA enforcement draw, which is seeded on `Team.id` by design
> (V2-011). At ids 135–137 all three teams were detained and the
> `product_demand` section was empty. **Repaired (`aede440`):** fixture sources
> from unflagged suppliers; two tests hold it (forced-fire, and the fixture
> rebuilt at 135–137). Both modules green in one process; full suite 1231 OK.
