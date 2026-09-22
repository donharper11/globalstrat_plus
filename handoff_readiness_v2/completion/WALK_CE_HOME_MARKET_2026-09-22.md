# W-CE-21 — a home market set in Team Configuration is not where the team starts

**Branch:** `walk-ce-home-market` from `crv2-release-integration` at `4756ffc`
(contains `4b152f8` and `completion/WALKTHROUGH_CE_2026-09-22.md`; verified).
**Finding:** W-CE-21 (P1), `WALKTHROUGH_CE_2026-09-22.md` line 177.
**Rulings observed:** R48 (bugs first; no new rules), R22 (round-0 parity is
the only starter gate), R28 (distinct starting positions; the shared
`home_market: NA` question is measurement, not a builder's call), R19 (a
ruling exists dated or not at all). No rule is invented below.

---

## 1. Reproduction (red)

Through the real routes, in `backend/core/tests/test_team_home_market_config.py`
(commit `57edf8a`), against `consumer_electronics_2026.yaml` loaded by
`load_scenario`, an 8-firm heat:

1. `POST /api/games/create/` as an instructor, no `home_markets` (the
   walkthrough's Create Game form in its default *profile* mode) → 201; every
   team starts in **NA**, the market every CE profile authors.
2. `GET /api/games/<id>/instructor/team-config/` → the console's rows;
   `PUT` the same rows back with team 1's `home_market_code` set to **AFR**
   (what *Save Configuration* sends) → 200, `home_market_code: "AFR"` in the
   response — the console shows the save as successful.
3. As a member of team 1, `GET …/teams/<id>/context/strategy/` (the Market
   Strategy page) and `GET …/context/talent-allocation/` (the Localization
   Overview with cultural distance).

Red, recorded in `scratchpad/red-run.txt` before any repair (`Ran 6 tests …
FAILED (failures=5)`):

```
AssertionError: 'not_entered' != 'active' : AFR is the home market but the
student sees it as 'not_entered'
```

and the state dump behind it — `presence (('NA','export','active',0),)`,
`compliance (('NA','1.00'),)`, both starter products offered in `NA`, round-0
adopters in `NA` — for a team whose `Team.home_market` said `AFR`. The sixth
test (the refusal once a round-1 submission exists) failed only on my expected
status: that route refuses with a `LifecyclePrecondition`, which is 400, and
was 400 before this repair; the expectation was corrected, the behaviour was
not changed.

## 2. The exact cause

**The console accepted a setting and applied it to one field the starting
state does not read.**

- `backend/core/views/team_config.py:157-158` (base revision):
  `team.home_market = market; save_fields.append('home_market')` — the PUT
  wrote `Team.home_market` and nothing else.
- `backend/core/services/game_creation.py:186-189, 235, 240, 245, 274` (base):
  `create_game` chooses the home market **once, at creation** — the override
  if given, else `profile.home_market` — and builds against it the round-0
  `TeamMarketPresence` (line 240), every starter product's `TeamProductMarket`
  (235), the `TeamMarketCompliance` row (245), and then `bootstrap_round_zero`
  (274).
- `backend/core/engine/bootstrap.py:199-202`: round 0 takes the home market
  from the **presence row** (`home_presence.market`), not from
  `Team.home_market`. So the round-0 revenue, adoption, product-market and
  leaderboard rows are all in the market the team was created with.

Order of operations in the console flow: *create game* (starting state built
against the authored market) → *configure teams* (only `Team.home_market`
moves) → *activate* (does not rebuild anything: `GameActivateView` opens
round 1 and flips status). Nothing ever moved the starting state.

Every student screen then reported the disagreement faithfully:
`StrategyContextView` (`decisions.py:2214-2247`) marks `is_home_market` from
`Team.home_market` and `entry_status` from the presence rows, hence *Africa —
Not Entered* beside *North America — Active, Export from Home Market*; and
`TalentAllocationContextView` (`cc31_views.py:52-73`) looks up the
`CulturalDistanceMatrix` **from `Team.home_market` to each presence**, hence NA
at VERY_HIGH. From round 1 the engine would have kept both readings: costs,
talent, tariffs and agents read `Team.home_market` (`costs.py:818,1061`,
`talent.py:210`, `agents/state.py:194`) while revenue and presence-driven
logic read the presence rows.

## 3. Which reading the code supports, and why

**The console override is meant to be honoured; the profile's market is a
default.** This is not a judgement call — the code says so in three places:

1. `create_game(…, home_market_overrides=…)` exists and is used by the console
   itself: the Create Game form's *instructor* market mode sends
   `home_markets` (`InstructorDashboard.js:247-256`) →
   `GameCreateView` → `create_game(home_market_overrides=…)`; the CLI has the
   same `--home_markets`. On that path the override reaches presence,
   products, compliance and round 0 consistently.
2. Every scenario authors `home_market_options` ("Available home markets for
   team selection", e.g. `clean_energy_tech_2026.yaml:294`).
3. The Team Configuration panel's own text (`instructor.home_market_info`):
   "Teams start with products and market presence in their home market."

R28 ("all profiles sharing `home_market: NA` is to be reported with
measurement, not decided by a builder") concerns *what the authored default
should be* — calibration, deferred under R48. It does not say the console
may not override, and the override path already existed before R28. So there
is no contradiction between profiles and console to resolve by removing the
control; the defect is that **one of the two console routes to the same
choice did not reach the starting state**. Removing the control instead would
have taken away a working, authored feature (the Create Game form's market
mode does the same thing correctly) to hide a bug in its sibling.

## 4. The repair (commit `0b3c1da`)

`backend/core/services/game_creation.py:296` — `rehome_team(team, market)`,
beside `create_game` because it must mirror exactly what `create_game` keys on
the home market. Inside one transaction (the route already holds the game's
lifecycle lock): set `Team.home_market`; move the round-0 presence
(`established_round=0`), the starter products' market rows
(`first_offered_round=0`) and the compliance row to the new market; delete
the team's market-keyed round-0 result rows (`RoundResultProductMarket`,
`RoundResultAdoption`, `RoundResultMarketRevenue` — the three whose keys carry
a market, so an in-place rebuild would leave the old market's rows beside the
new); then `bootstrap_round_zero(game)`, the one way round 0 is ever built.
Everything else bootstrap writes is keyed without a market and is rewritten
in place with the same values.

`backend/core/views/team_config.py:162` — the PUT calls `rehome_team` where it
used to set the field. Nothing else in the route changed: same refusal once a
round-1 submission exists, same audit before/after, same response shape.
**No frontend change**: the panel's text was already the promise; it is now
kept. No new setting, no new refusal, no migration.

Alternatives considered and not taken: (a) making `bootstrap_round_zero` read
`Team.home_market` — that would change a function inside the determinism
boundary and still leave presence/products/compliance in the old market;
(b) refusing home-market changes after creation — removes a working control
to fix its bug, and contradicts the panel's own text.

## 5. Green

`scripts/test-postgres core.tests.test_team_home_market_config
core.tests.test_game_creation_paths core.tests.test_round_zero_adoption
core.tests.test_console_defects core.tests.test_cohort_caps
core.tests.test_manifest_determinism core.tests.test_operator_refusal_language
core.tests.test_refusal_audit core.tests.test_who_attempted` (under the
flock): **Ran 183 tests … OK** (`scratchpad/green-run.txt`).

What the six new tests prove, all through the registered routes:

| test | proves |
|---|---|
| `test_the_walkthrough_sequence_starts_the_team_in_its_home_market` | the walkthrough's exact sequence; after the save, AFR is `active` and `is_home_market`, every other market `not_entered`, the Localization Overview lists only AFR at distance `HOME`; presence, product markets, compliance, round-0 product/market-revenue/adoption rows all in AFR; R22 parity holds (index = base, rank = {1}, 8 rows) |
| `test_a_re_homed_team_starts_exactly_as_one_created_there` | **the invariant**: V2-112's `starting_state` dump of a heat re-homed through Team Configuration equals, whole-game, the dump of a heat created with `home_markets=['AFR', 'NA' × 7]` — the console's two routes to one choice build the same game |
| `test_teams_whose_home_market_did_not_change_are_untouched` | a save that changes nothing leaves the dump byte-identical; re-homing one team leaves the other seven teams' dumps byte-identical |
| `test_a_change_after_activation_but_before_any_submission` | the route's existing window (until the first round-1 submission) works after activation too; round 1 stays open, round 0 processed, `current_round` 1 |
| `test_changing_back_and_forth_leaves_no_trace` | AFR then back to NA returns the dump to its original bytes |
| `test_refused_once_a_round_one_submission_exists` | the pre-existing refusal (`round_1_started`, 400) still refuses and leaves the dump untouched |

## 6. Round-0 state for untouched games — unchanged

- `create_game` and `bootstrap_round_zero` are byte-for-byte as they were:
  `git diff crv2-release-integration -- backend/core/engine/bootstrap.py` is
  empty, and the only change to `game_creation.py` is two imports and a new
  function appended after `create_game`, which nothing calls except the
  team-config PUT on a changed market.
- `test_game_creation_paths` (V2-112's command-vs-view dump across all three
  scenarios × 8 firms) and `test_round_zero_adoption`
  (`EightFirmDistinctStarterTests`, R22 parity, R11 reconciliation) pass
  unchanged, and `test_teams_whose_home_market_did_not_change_are_untouched`
  shows a no-op save through the route leaves the dump identical.
- Determinism: round 0 is a briefing state, not a resolved round; no
  `ResolutionManifest` exists for it and no replay evidence is invalidated.
  Re-homing is refused once any round-1 submission exists, so it can never
  run against a round the engine has hashed.

## 7. Full run (once, from the freeze candidate `0b3c1da`)

`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock
scripts/test-postgres core --parallel 8` — result recorded in §7a below when
the run completed; no runtime code changed after it started.

### 7a. Result

Run once, from `walk-ce-home-market` at `0b3c1da`, PID 3840243, disposable
Postgres, started 2026-09-22T18:34:35Z, ended 18:37:05Z:

```
Ran 1525 tests in 123.572s
OK
exit=0
```

No runtime code changed after the run started; the only commit after it is
this report.

## 8. Proposed register status text (for the integrator; this file does not edit the register)

> **W-CE-21 — Repaired, pending closure** at `0b3c1da`. The team-config PUT
> wrote `Team.home_market` only; the starting state (`TeamMarketPresence`,
> starter `TeamProductMarket`, `TeamMarketCompliance`, round-0 results) had
> been built by `create_game` against the profile's authored market and
> `bootstrap_round_zero` reads the home market from the presence row
> (`bootstrap.py:199-202`). The console override is the designed behaviour —
> `create_game(home_market_overrides)` is the Create Game form's own path —
> so the sibling route now applies it the same way: `rehome_team` moves the
> rows `create_game` keys on the home market and rebuilds round 0.
> Proven through the routes: a team re-homed in Team Configuration starts
> byte-identical (V2-112 dump) to one created with that market; untouched
> teams and untouched games byte-identical; R22 parity holds. No frontend
> change; the panel's text ("Teams start with products and market presence
> in their home market") was the promise and is now kept.

## 9. For the owner, in plain language

No decision is needed to close W-CE-21: the console already had two ways to
choose a team's home market and one of them did not take effect; now both
do the same thing. Two things are recorded, not decided:

1. **Whether Consumer Electronics should author every profile at home in
   North America** stays with R28's measurement task and R48's calibration
   pass. The console can move any team; the default is the scenario's.
2. **Clearing a home market** (`home_market_code: null`) is accepted by the
   API as before and still writes only the field; the console cannot send it
   (its rows always carry a code, and every created team has one), so no
   player can reach it. If the owner wants it refused outright, that is a
   one-line change and a new refusal sentence in both languages — not made
   here because no one can hit it and R48 says bugs first.

## 10. Unresolved, observed on the way (not fixed here; out of scope)

- **A renamed team keeps its creation-time platform name.** The walkthrough
  renamed team 1 to *Aurora Devices*; its platform is still
  "`<old name>` Base Platform" (`create_game` names it once). Cosmetic, seen
  by the student on the R&D page. Separate finding for the register.
- **Randomising all eight teams runs `bootstrap_round_zero` once per changed
  team** (eight times for one save). Correct and idempotent, a few seconds at
  most on an 8-team game at setup time; batching would be an optimisation
  inside the game builder and was not worth the extra surface today.
- `sc_posture.py:48` derives a supply-chain default market as the literal
  `NA`, independent of any home market; not touched, noted for the
  supply-chain owner.

## 11. Commands

```
git checkout -b walk-ce-home-market crv2-release-integration
git merge-base --is-ancestor 4b152f8 HEAD                          # ok
cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock \
  scripts/test-postgres core.tests.test_team_home_market_config     # RED: 6 run, 5 fail
cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock \
  scripts/test-postgres core.tests.test_team_home_market_config \
  core.tests.test_game_creation_paths core.tests.test_round_zero_adoption \
  core.tests.test_console_defects core.tests.test_cohort_caps \
  core.tests.test_manifest_determinism core.tests.test_operator_refusal_language \
  core.tests.test_refusal_audit core.tests.test_who_attempted         # GREEN: 183 OK
cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock \
  scripts/test-postgres core --parallel 8                            # once; §7a
```

Never the production database; never `/etc/globalstrat-plus.env`. Disposable
Postgres per run via `scripts/test-postgres`.
