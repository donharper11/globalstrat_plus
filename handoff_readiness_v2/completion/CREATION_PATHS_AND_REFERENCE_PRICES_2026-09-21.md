# Creation paths (V2-112) and per-scenario reference prices (V2-114) — 2026-09-21

**Branch:** `crv2-11-creation-paths-and-reference-prices`, cut from
`crv2-release-integration` at `79db2bf`.
**Commits:** `ffd34a9` (V2-112), `326d759` (V2-114), plus the commit carrying
this report.
**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoffs/EXECUTION_PROTOCOL.md`.
**Claims no gate closed.** The register and the launch checklist are not
edited; proposed register text is at the end.

**Read this first.** Neither finding came out the way its register cell
predicts.

- **V2-112.** The register says the view "honours" the authored `beta` block and
  the command discards it, and reads that as the command being wrong. Both halves
  are true and the conclusion is backwards: **the game the view builds cannot be
  scored** — the engine refuses any game in which a team holds two platforms of
  one generation — **and the view could not build a game at all**, because it
  answered 500 to every instructor. The single builder therefore keeps the
  command's shape, and the command's output is byte-identical before and after.
- **V2-114.** Repaired for Media and for Clean Energy's premium tier. **Not
  repairable by reference prices alone in Clean Energy's mainstream tier**, whose
  authored prices span 9.4× where one reference can hold 3× live. Six products
  remain on a clamp under *any* reference. That is put to the owner, not settled
  here.

---

## 1. State found at head (`79db2bf`) — inventory before implementation

### V2-112 — open, and worse than registered

Creation paths, from `core/urls.py` and `core/management/commands/`, by
searching for every `Game.objects.create` / `Team.objects.create` in runtime
code rather than for the helper a correct path would call:

| # | Entry point | Builds its own game? | Disposition |
|---|---|---|---|
| 1 | `POST /api/games/create/` → `GameCreateView.post` (`scenario_views.py`) | **Yes** — own copy of the loop | **Changed**: calls `create_game` |
| 2 | `manage.py initialize_game` | **Yes** — own copy of the loop | **Changed**: calls `create_game` |
| 3 | `setup_test_game`, `load_demo`, `run_deadline_rehearsal`, `run_integration_test`, `run_cc31i_test`, `run_cc32f_test` | No — each `call_command('initialize_game')` | Covered through 2 |
| 4 | Evidence harnesses under `handoff_readiness_v2/evidence/**` (`seed_field.py`, `seed_classA.py`, `seed_crv213.py`, `seed_r35.py`, `r11_round_zero_replay.py`, `stage1_runtime_replay.py`, `fixture_bodies.py`, …) | No — `initialize_game` | Covered through 2 |
| 5 | `GameResetView` | No — returns a game to `setup`; creates no team state | Exempt: not a creation path |
| 6 | `rd_processing.py:209` `TeamPlatform.objects.create` | No — in-play platform development | Exempt: not creation |
| 7 | `core/admin.py` | Read-only under R13 (`CompetitionReadOnlyAdmin`) | Exempt |

There are exactly two implementations. Their differences at head:

| | Command | View |
|---|---|---|
| Platforms per team | 1, `"<team> Base Platform"`, from `alpha` | 2, `"<team> Platform A/B"`, one per authored label |
| Products | both on the one platform | each on its `platform_label` |
| Feature-level rows | authored features only | authored + **every other platform feature at level 0** |
| Transaction | none (a failed create left an orphan `Game`) | `atomic` |
| Profile order | unordered queryset (V2-111) | unordered queryset (V2-111) |
| Section / `SimulationInstance` | none | yes |
| Lifecycle afterwards | opens round 1, `active` | stays `setup` |

Round-0 adoption is apportioned on the best level across a team's platforms
(`bootstrap._round_zero_fit`), so the paths **publish different round-0 rows**
from the same scenario. Measured (Consumer Electronics, The Brand Builder,
Premium Consumers segment): fit `0.4200`, adopters `23808.52` by the command
against `0.4700`, `23849.26` by the view's logic.

### Two new defects found in the inventory — recorded before repair

**N1 — `POST /api/games/create/` answers 500 to every authenticated
instructor.** `Game.created_by` is a foreign key to `auth.User`
(`AUTH_USER_MODEL` is not overridden); the only authentication class is
`JWTAuthentication`, so `request.user` is always a `JWTUser`, and the view
assigned it: `ValueError: Cannot assign "<JWTUser>": "Game.created_by" must be a
"User" instance.` The superuser fallback was unreachable for exactly the caller
the route exists for. **An instructor cannot create a game through the
product.** Reproduced at head by this work's first red run (three 500s). It was
first observed earlier in this programme by the CRV2-10 Stage 1 probe
(`evidence/decision-rules/STAGE1_PROBE_RECORD_PARALLEL_PASS_675b347.md` §N2,
"Proposed P1, arguably P0 for Stage 6") and **was never given a register ID** —
`games/create` does not appear in `V2_FINDINGS_REGISTER.md`. `test_cohort_caps`
posts to the route but only asserts refusals, which return before the create.
*In scope:* convergence cannot be built or proved on a path that cannot run.
**Repaired** (see §2).

**N2 — a game built the view's way can never resolve round 1.** `_run_phase_1`
raises `InvalidPersistedDecisionError` while
`rd_costs.duplicate_platform_state(game)` is non-empty — "a team develops one
platform per generation" (V2-046 / V2-047, CRV2-10). The view created an `alpha`
**and** a `beta` platform on the same starting generation for every team.
Observed directly: with the builder temporarily carrying the view's logic,
`ManifestSnapshotIntegrationTests` failed three times with *"3 team/generation
pair(s) hold more than one non-retired platform"*. So N1 was masking N2: had the
route not crashed, every heat an instructor created would have been unscoreable.
*In scope:* it decides which implementation can be authoritative. **Repaired**
by that choice (see §2).

**N3 — coherence scores price against a hard-coded Consumer Electronics ladder.**
`core/engine/coherence.py:29` — `PRICE_RANGES = {'budget': (100, 300),
'mainstream': (250, 550), 'premium': (500, 900), 'ultra_premium': (800, 1500)}`
— is an engine constant, not scenario data. `_score_positioning_price` awards
1.0 inside the range, 0.5 within 20% outside, 0.0 beyond. **Every Clean Energy
starter price ($850+) and every Media mainstream price below $200 scores 0.0**
on this component whatever the team does. It is V2-114's defect in a second
place, and it is **not repaired here**: deriving ranges from the scenario's
references is a scoring-rule change that touches all three scenarios' code path
(the four CE ranges are not a uniform multiple of the four CE references, so no
single formula reproduces them), and that is a rules decision. **Proposed P1**,
same reasoning as V2-114. See Q6.

**N4 — `ManifestSnapshotIntegrationTests.test_product_demand_ledger_row_is_signed_in_the_round_manifest`
depends on `Team` primary keys.** The fixture markets are the first three by
code (AFR/APAC/EU), and whether any `product_demand` row exists after round 1
depends on draws keyed to surrogate ids (DETERMINISM_BOUNDARY residual
conditions 1 and 3). **Proved pre-existing, on head's own creation code:** with
the game sequence set so the fixture game is id 28 and the team sequence set so
its teams are 135–137, the test fails with `demand 0`; at teams 132–134 it
passes with 24 rows; at other ids, 16. Any new test that creates teams earlier
in the same process can flip it. **Mine do** when
`test_game_creation_paths` runs before `test_manifest_determinism` in one
invocation; run on its own, `test_manifest_determinism` is green (57 tests).
**Not repaired** — it is a determinism-fixture defect, not a creation or pricing
one. **Proposed P2** (verification apparatus; sibling of V2-116), with the
caveat that *it can turn the full suite red after this merge for a reason
unrelated to this change*. I was instructed not to run the full suite, so **I do
not know whether it does.**

### V2-114 — open, exactly as registered

All three YAMLs authored `250 / 420 / 700 / 1000`. Measured through the engine's
own `_derive_price_competitiveness` on scenarios loaded by the real
`load_scenario`: **16 of 16 Clean Energy starter products on the floor clamp
(ratio 2.02–19.05), 16 of 16 Media starter products on the ceiling clamp (ratio
0.13–0.49), 0 of 16 Consumer Electronics.** `price_band` additionally bands a
never-sold product ±30% around the tier reference, so a new Clean Energy
mainstream product was legal only between **$294 and $546**.

No owner ruling covers the numbers. `OWNER_DECISIONS_PENDING_2026-09-16.md` §D11
says: *"The numbers themselves are calibration; only the owner sets them."*
**That sentence is in tension with this handoff**, which instructs the
data-derived option to be implemented and the judgement surfaced. I have done
the latter; the values below are a proposal the owner can replace by editing
eight YAML lines, and are not a ruling.

---

## 2. Changes

### V2-112 (`ffd34a9`)

- **New `core/services/game_creation.py` — `create_game()`**, the only code that
  builds a game. `GameCreateView` and `initialize_game` both call it; neither
  keeps a loop. Lifecycle stays with the callers (the view leaves `setup`, the
  command opens round 1), applied *after* the builder returns.
- **Shape: the command's**, for the reason in N2 — it is the only shape the
  engine scores — and because it is the shape every replay, balance and
  playthrough record in the programme was measured on.
- **The command's output is byte-identical before and after.** A canonical dump
  of everything creation writes (teams, platforms, feature levels, products,
  presence, compliance, strategy levels, org structure, and all round-0 result
  rows), 3 scenarios × 8 firms, built by head's command and by the new one:
  both `sha256 4de6202518fe9982dfff277d87b007ff498ca5210cc2d04c61a24b81cb2c37e4`.
- **V2-111 folded in** (same two call sites, now one): profiles, platform
  configs and starter products are read `order_by('id')`.
- **N1 repaired:** the view assigns `created_by` only when `request.user` is a
  real `auth.User`, and otherwise records the first superuser — exactly what the
  command records. See Q5.
- **The whole create is now atomic on both paths.**
- **`route_inventory.py`:** the detector reads a view's *source*. Moving the
  creates into a service would have re-recorded `api/games/create/` as **not
  lifecycle-mutating** — the writes moved out of sight, they did not stop.
  `create_game(` is now a write marker; the checked-in inventory is unchanged
  and `RouteCoverageTests` is green. This is the V2-095 class (a guard whose
  reach does not follow the code) and it was caught by that guard's own test.

**What is NOT fixed:** the authored `beta` block is still unused — now on every
path rather than on one. See Q4.

### V2-114 (`326d759`)

Eight config values in two YAML files; no engine code.

| | budget | mainstream | premium | ultra-premium |
|---|---:|---:|---:|---:|
| Consumer Electronics | 250 | 420 | 700 | 1000 — **unchanged** |
| Clean Energy | **2200** | **3700** | **8900** | **13000** |
| Media & Entertainment | **71** | **120** | **270** | **390** |

`consumer_electronics_2026.yaml` sha256 before and after:
`0fae38ca4167db1083e7f78b18896ed5a0555bfc8a879fb270108f5b47d25623`.

A database that already has either scenario loaded keeps its old rows until
`load_scenario` is re-run; D11 records that neither is loaded in the live
database. No migration is written, deliberately: a migration would silently
change competitive numbers in any database it met.

---

## 3. Derivation of the prices

**What the YAMLs carry that bears on price:** starter product prices by tier,
`base_unit_cost` (120 / 15), supplier unit prices (CE only), and nothing else —
no willingness-to-pay, no segment income, no price preference. So the derivation
rests on starter prices. Prior art agrees: BECSR anchors round 1 to the authored
starting price (`BECSR/backend/csr_sim/services/pricing.py`, "THE ROUND-1
ANCHOR"), and `reprice_calibration.md` rules that a reference price and the
product prices must move together or price fit floors. CE's own ladder is, per
migration `0077`, "the starting prices the demo already used".

**Rule 1 — a tier with authored starter products takes their mean, to 2 s.f.**
The mean, not the median, because the score is linear in price
(`f = 1.5 − price/reference`): at `reference = mean`, the field's average price
competitiveness at the authored starting prices is exactly the neutral 0.5.

| Scenario / tier | Authored starter prices | Mean | Reference |
|---|---|---:|---:|
| Clean Energy mainstream | 850, 900, 1200, 1400, 2800, 4200, 4500, 5500, 7500, 8000 | 3685.00 | **3700** |
| Clean Energy premium | 6500, 7000, 8000, 9000, 11000, 12000 | 8916.67 | **8900** |
| Media mainstream | 55, 90, 95, 100, 120, 130, 150, 160, 170 | 118.89 | **120** |
| Media premium | 180, 220, 250, 280, 300, 320, 340 | 270.00 | **270** |

**Rule 2 — a tier with no authored starter product extends the scenario's own
ladder by the CE step.** Neither scenario authors a budget or ultra-premium
starter product. budget = mainstream × 250/420; ultra-premium = premium ×
1000/700; 2 s.f.

| | mainstream × 250/420 | → | premium × 1000/700 | → |
|---|---:|---:|---:|---:|
| Clean Energy | 2202.4 | **2200** | 12714.3 | **13000** |
| Media | 71.4 | **71** | 385.7 | **390** |

Both rules are pinned by
`test_references_are_derived_from_the_scenarios_own_starter_prices`, which
recomputes them from the loaded rows — no price is embedded in the test.

**Before and after, per starter product** (ratio = price / tier reference;
score on a 0–1 feature range, live only for 0.5 < ratio < 1.5; demand × is
`high_price_demand_multiplier` at elasticity 1.5):

Clean Energy

| Product | Tier | Price | ratio before | score before | demand × before | ratio after | score after | demand × after |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| VoltPack Pro | premium | 6,500 | 9.286 | 0.000 | 0.035 | 0.730 | 0.770 | 1.000 |
| VoltPack Standard | mainstream | 4,200 | 10.000 | 0.000 | 0.032 | 1.135 | 0.365 | 0.827 |
| GridCell Max | premium | 12,000 | 17.143 | 0.000 | 0.014 | 1.348 | 0.152 | 0.639 |
| **GridCell Standard** | mainstream | 8,000 | 19.048 | 0.000 | 0.012 | 2.162 | **0.000** | 0.315 |
| SafeCell Premium | premium | 8,000 | 11.429 | 0.000 | 0.026 | 0.899 | 0.601 | 1.000 |
| SafeCell EV | mainstream | 5,500 | 13.095 | 0.000 | 0.021 | 1.486 | 0.014 | 0.552 |
| **EcoCell Home** | mainstream | 1,200 | 2.857 | 0.000 | 0.207 | 0.324 | **1.000** | 1.000 |
| EcoCell Grid | premium | 9,000 | 12.857 | 0.000 | 0.022 | 1.011 | 0.489 | 0.983 |
| SurgeCell Pro | premium | 7,000 | 10.000 | 0.000 | 0.032 | 0.787 | 0.713 | 1.000 |
| SurgeCell | mainstream | 4,500 | 10.714 | 0.000 | 0.029 | 1.216 | 0.284 | 0.746 |
| BaseCell | mainstream | 2,800 | 6.667 | 0.000 | 0.058 | 0.757 | 0.743 | 1.000 |
| **BaseCell Lite** | mainstream | 900 | 2.143 | 0.000 | 0.319 | 0.243 | **1.000** | 1.000 |
| AxisStore Prime | premium | 11,000 | 15.714 | 0.000 | 0.016 | 1.236 | 0.264 | 0.728 |
| **AxisStore** | mainstream | 7,500 | 17.857 | 0.000 | 0.013 | 2.027 | **0.000** | 0.347 |
| **HomeVolt** | mainstream | 1,400 | 3.333 | 0.000 | 0.164 | 0.378 | **1.000** | 1.000 |
| **HomeVolt Compact** | mainstream | 850 | 2.024 | 0.000 | 0.347 | 0.230 | **1.000** | 1.000 |

Media & Entertainment

| Product | Tier | Price | ratio before | score before | demand × before | ratio after | score after | demand × after |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Premium Originals | premium | 280 | 0.400 | 1.000 | 1.000 | 1.037 | 0.463 | 0.947 |
| Mainstream Library | mainstream | 130 | 0.310 | 1.000 | 1.000 | 1.083 | 0.417 | 0.887 |
| SmartStream Pro | premium | 220 | 0.314 | 1.000 | 1.000 | 0.815 | 0.685 | 1.000 |
| SmartStream Basic | mainstream | 100 | 0.238 | 1.000 | 1.000 | 0.833 | 0.667 | 1.000 |
| WorldView Premium | premium | 250 | 0.357 | 1.000 | 1.000 | 0.926 | 0.574 | 1.000 |
| WorldView Standard | mainstream | 120 | 0.286 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 |
| ViralStream | mainstream | 90 | 0.214 | 1.000 | 1.000 | 0.750 | 0.750 | 1.000 |
| ViralStream+ | premium | 180 | 0.257 | 1.000 | 1.000 | 0.667 | 0.833 | 1.000 |
| Civic Premium | premium | 300 | 0.429 | 1.000 | 1.000 | 1.111 | 0.389 | 0.854 |
| Civic Standard | mainstream | 150 | 0.357 | 1.000 | 1.000 | 1.250 | 0.250 | 0.716 |
| Arena Live | premium | 320 | 0.457 | 1.000 | 1.000 | 1.185 | 0.315 | 0.775 |
| Arena Replay | mainstream | 160 | 0.381 | 1.000 | 1.000 | 1.333 | 0.167 | 0.650 |
| Salon Select | premium | 340 | 0.486 | 1.000 | 1.000 | 1.259 | 0.241 | 0.708 |
| Salon | mainstream | 170 | 0.405 | 1.000 | 1.000 | 1.417 | 0.083 | 0.593 |
| OmniPass | mainstream | 95 | 0.226 | 1.000 | 1.000 | 0.792 | 0.708 | 1.000 |
| **OmniPass Lite** | mainstream | 55 | 0.131 | 1.000 | 1.000 | 0.458 | **1.000** | 1.000 |

| Clamped at authored price | Before | After |
|---|---:|---:|
| Consumer Electronics | 0 / 16 | 0 / 16 |
| Clean Energy | **16 / 16** | **6 / 16** (premium 0 / 6, mainstream 6 / 10) |
| Media & Entertainment | **16 / 16** | **1 / 16** |

New-product band (`price_band`, ±30% of the tier reference): Clean Energy
mainstream $294–546 → **$2,590–4,810**, premium $490–910 → **$6,230–11,570**;
Media mainstream $294–546 → **$84–156**, premium $490–910 → **$189–351**.

### The residual, and why no reference removes it

The score is live for `0.5 < price/reference < 1.5`, a 3× window. **A tier whose
authored prices span more than 3× cannot be held live by any single
reference.** Clean Energy mainstream spans **9.41×** — $850 home packs and
$8,000 grid modules under one label. Alternatives, all measured:

| Clean Energy mainstream reference | Live | Clamped |
|---|---:|---|
| 420 (head) | 0 / 10 | all, on the floor |
| median 3500 | 3 / 10 | 4 ceiling, 3 floor |
| **mean 3700 (implemented)** | **4 / 10** | 4 ceiling (home products), 2 floor (GridCell Standard, AxisStore) |
| midrange 4425 | 4 / 10 | 4 ceiling, 2 floor |
| best possible, ≈5340 | 6 / 10 | 4 ceiling |

The four home products (EcoCell Home, BaseCell Lite, HomeVolt, HomeVolt Compact)
are on the ceiling under **every** reference that serves the other six. What
that means in play: they hold maximum price competitiveness and can raise price
30% a round for several rounds at no cost in score — the mirror image of the
two grid modules, which open with zero price competitiveness and 31–35% of
their demand, and need two to three rounds of maximum cuts to come back in.
**Round 0 is unaffected and R22 parity holds** (bootstrap reads no reference
price; `EightFirmDistinctStarterTests` green) — this is a rounds-1+ balance
effect, the kind R28 says must be measured.

Media mainstream spans 3.09×, so exactly one product (OmniPass Lite, $55, the
Value Bundler's deliberately cheap line) sits marginally on the ceiling
(ratio 0.458) under every reference.

These seven are listed in `KNOWN_RESIDUAL_CLAMPS` in the test — not as
acceptable, but so the set cannot grow unnoticed; the test also fails if a
listed product stops being clamped, so the list cannot outlive the defect.

---

## 4. Commands, results, durations

Every test ran as
`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`
— disposable `postgres:16-alpine` container, random password, never the
production database, never `/etc/globalstrat-plus.env`. No full suite. No
release-scale evidence run. No evidence directory written.

| # | Labels | Code state | Result | Wall |
|---|---|---|---|---:|
| 1 | `test_game_creation_paths` | head | **RED** — 3 errors (route 500, N1), 1 failure (1 platform ≠ 2, under my first, wrong hypothesis) | 19s |
| 2 | same | view's `created_by` repaired, head's command | **RED** — 3 failures: starting state differs by path in all 3 scenarios | 23s |
| 3 | 12 affected modules | single builder carrying the **view's** shape | **RED** — 3 errors in `test_manifest_determinism`: "hold more than one non-retired platform" (N2) | 78s |
| 4 | `test_game_creation_paths` incl. new scoreability test | same as 3 | **RED** — `duplicate_platform_state` non-empty on both paths | 35s |
| 5 | starting-state dump, head's command vs new command | — | **identical**, sha `4de62025…` | 2 × ~25s |
| 6 | `test_scenario_reference_prices` | YAMLs at head | **RED** — 8 failures: 16/16 + 16/16 clamped; 420 ≠ 3700; 420 ≠ 120; new-product band excludes every authored price | 27s |
| 7 | 16 affected modules (331 tests) | final code | 329 pass; `RouteCoverageTests` red (inventory drift → fixed, see §2); ledger test red (N4) | 208s |
| 8 | same 16 modules | + inventory marker | 330 pass; ledger test red (N4) | 190s test / 418s wall (lock wait) |
| 9 | N4 isolation: 7 short runs, incl. three on **head's** creation code with game/team sequences set | — | failure reproduced on head's code at teams 135–137; passes at 132–134 | ~45s each |
| 10 | **Final, candidate code:** `test_scenario_reference_prices test_game_creation_paths test_round_zero_adoption test_cohort_caps test_calibration test_price_band test_reference_price test_platform_lifecycle test_legacy_control_removal test_console_defects test_rng_cohort_and_streams test_rd_ordering test_operator_concurrency.RouteCoverageTests` | final | **GREEN — 225 tests** | 55s |
| 11 | **Final:** `test_manifest_determinism` (own process, as at head) | final | **GREEN — 57 tests** | 29s |

Run 1's fourth result deserves a note: my first test asserted that the command
should build **two** platforms, because I had taken the register's framing at
its word. Run 3 is what showed that framing to be wrong. The assertion was
replaced by the scoreability test before any commit.

## 5. Red, then green

| Test | Red (without the change) | Green |
|---|---|---|
| `test_both_paths_build_the_same_starting_state` ×3 scenarios | run 2: `'<team> Base Platform'…` ≠ `'<team> Platform A'…`; round-0 adoption 23808.52 vs 23849.26 | run 10 |
| `test_every_path_builds_a_game_the_engine_will_score` ×2 paths | run 4 (view-shaped builder); and at head the `view` sub-test errors on the 500 | run 10 |
| `test_authored_starting_prices_are_not_on_a_clamp` | run 6: 16 of 16, twice | run 10 |
| `test_the_premium_tier_is_live_for_every_authored_product` | run 6: VoltPack Pro 0.0; Premium Originals 1.0 | run 10 |
| `test_references_are_derived_from_the_scenarios_own_starter_prices` | run 6: 420.0 ≠ 3700; 420.0 ≠ 120 | run 10 |
| `test_a_new_product_is_banded_around_its_own_scenarios_prices` | run 6: `above_band`; `below_band` | run 10 |
| `test_consumer_electronics_is_unchanged` | green before and after, by design | run 10 |

## 6. Earlier evidence this invalidates

**V2-112 — none that was built through the command**, which is all of it: the
command's starting state is byte-identical (§2). The CRV2-01 determinism
records, the R11/R25 calibration replays, the R28 starter-profile balance
replay, the load/failure and playthrough seeds all went through
`initialize_game`. **What becomes stale is description, not measurement:**
`evidence/calibration/starter-profiles/PROFILE_ASSIGNMENT_INVENTORY.md` and the
V2-109/V2-111/V2-112 register cells cite `initialize_game.py:112` and
`scenario_views.py:325`, which no longer exist, and describe the view as the
path that honours authored data. No record of a game created through the view
exists to invalidate, because none could be created.

**V2-114 — Consumer Electronics: nothing.** File byte-identical; its config
digest is unchanged.
**Clean Energy and Media: every rounds-1+ number ever produced on them**, and
their `config_digests` / `input_sha256`. I found no multi-round replay of
either scenario in `handoff_readiness_v2/evidence` — the calibration and
balance replays are Consumer Electronics — but I searched by filename and
scenario name and **did not read every harness**, so treat that as "none
found", not "none exists". Round-0 evidence on both scenarios stands (R11/R22/R28
tests green): bootstrap reads no reference price.
**Owed and not done:** R28 requires balance to be *measured*. It has never been
measured on Clean Energy or Media, and could not meaningfully have been while
the price lever was dead. It is now measurable for Media; for Clean Energy it
should wait for Q1.

## 7. Questions for the owner

**Q1 — Clean Energy's mainstream tier cannot be priced by one reference. Which
way?** (a) Accept 3700 and the six clamped products as authored asymmetry. (b)
**Re-tier the four home products to `budget`** — then budget = mean(850, 900,
1200, 1400) = 1087.5 → **1100**, mainstream = mean of the remaining six =
5416.7 → **5400**, and **all 16 products are live** (extremes: 2800/5400 =
0.519, 8000/5400 = 1.481, 850/1100 = 0.773, 1400/1100 = 1.273). It also changes
those products' distribution-alignment coherence and the label students see,
and it edits three profiles authored under R28. (c) Re-price the outliers. (d)
Move the reference off the tier (per product or per market) — an engine rule
change that V2-023's "independent of team decisions" argument constrains. I
implemented none of (b)–(d): each rewrites authored competitive positions.

**Q2 — Is "mean of the tier's authored starting prices, 2 s.f." the rule you
want?** The median gives 3500 / 8500 / 120 / 280 and one fewer live product.
Consumer Electronics itself follows neither (its means are 240 / 409 / 750 /
1150 against an authored 250 / 420 / 700 / 1000, because four profiles were
added under R28 after the ladder was set); I left it alone as instructed, so
the three scenarios are now on two different derivations. D11 says only the
owner sets these numbers — these are a proposal.

**Q3 — The empty tiers.** Neither scenario has a budget or ultra-premium
starter product. I extended each ladder by the CE step (×250/420, ×1000/700).
The alternatives are to leave the tier unauthored (scoring then *refuses* a
product positioned there — `scenario_reference_prices` fails closed) or to
author the numbers by hand.

**Q4 — The authored `beta` platform block is unused on every path.** 24 profiles
author one, and `FirmStarterProduct.platform_label` points products at it.
Honouring it needs either a second starting generation or an exemption from
one-platform-per-generation for round-0 platforms; both change every team's
starting capability and invalidate all existing evidence. Or the blocks are
deleted as decorative (the R25 precedent). Until ruled, the second product of
every firm is scored on the first product's platform.

**Q5 — `created_by`.** A game created through the product is now recorded
against the first superuser, as the command has always done, because the
platform's `core.User` has no `auth.User` counterpart. Instructor ownership is
carried by section → course, not by this field. Is superuser attribution
acceptable, or should `Game` gain a `core.User` creator column (a migration)?

**Q6 — N3, the hard-coded coherence price ranges.** Should positioning-price
coherence be derived from the scenario's reference prices, and with what
bounds? Until it is, that component is 0.0 for every Clean Energy product and
most Media products regardless of play.

## 8. EXECUTION_PROTOCOL preflight

- *Inventory from registries, not from the new helper?* Yes — `urls.py`, the
  management-command directory, and a search for the model creates themselves.
- *Active legacy or alternate entry point?* Two found, both converged; wrappers
  listed. `GameResetView` checked and exempt.
- *Does a refusal survive rollback / negative tests prove no mutation?* The
  create is now atomic on both paths; `GameCreationError` is raised before any
  write. Not separately tested — existing `GameCreationCapTests` cover refusals.
- *Do claimed values describe the executing process?* Every figure in §3 was
  produced by the engine's own functions on scenarios loaded by `load_scenario`.
- *Do P0/P1/P2 labels match their definitions?* Proposed only; see §9.
- *Runtime code changed after evidence began?* No evidence run was made.
  Final runs 10–11 are on the committed bytes.
- *Command budget:* full suite 0; determinism matrix 0; release harness 0.

## 9. Proposed register text (not applied)

> **V2-112 — status update 2026-09-21, `ffd34a9`. Repaired, pending closure; the
> premise of this entry is corrected.** One builder,
> `core/services/game_creation.create_game`, and both registered paths call it;
> `CreationPathsConvergeTests` builds an 8-firm heat by each path from all three
> scenarios and asserts identical starting state including every round-0 result
> row. **The builder keeps the command's single-platform shape, not the view's**,
> because the view's shape is one the engine refuses to score
> (`duplicate_platform_state`, V2-046/047) — so this entry's reading that the
> CLI game "is not the game the scenario author wrote" was right about the data
> and wrong about the remedy. The command's starting state is byte-identical
> before and after (sha `4de62025…`); no command-built evidence is invalidated.
> V2-111 is repaired by the same change (`order_by('id')`). **Residual, for the
> owner:** the authored `beta` block is unused on every path.
>
> **V2-1xx (new) — P1, arguably P0 for a competition. `POST /api/games/create/`
> returned 500 to every authenticated instructor** (`JWTUser` assigned to an
> `auth.User` foreign key), first seen by the CRV2-10 Stage 1 probe (§N2) and
> never registered; **and a game it built could not have resolved round 1**
> (two platforms per generation). Repaired at `ffd34a9`.
>
> **V2-114 — status update 2026-09-21, `326d759`. Partially repaired; stays
> open.** Clean Energy 2200/3700/8900/13000 and Media 71/120/270/390, derived as
> the mean authored starter price per tier (2 s.f.), empty tiers extended by the
> CE step; CE byte-unchanged. Clamped starter products 16/16 → 6/16 (Clean
> Energy) and 16/16 → 1/16 (Media). **Open because** Clean Energy's mainstream
> tier spans 9.4× and no single reference holds more than six of its ten
> products live; the choice (re-tier, re-price, or accept) is the owner's. The
> values are a builder's data-derived proposal, **not a ruling** (D11).
>
> **V2-1xx (new) — P1. `coherence.PRICE_RANGES` is a hard-coded Consumer
> Electronics ladder**, so positioning-price coherence is 0.0 for every Clean
> Energy product and most Media products. Open; needs a rules decision.
>
> **V2-1xx (new) — P2. `test_product_demand_ledger_row_is_signed_in_the_round_manifest`
> depends on `Team` primary keys** (fails at 135–137, on head's code as well), so
> any new test creating teams earlier in the process can turn it red. Open;
> owner CRV2-01 / GSP-CRV2-09, with V2-116.
