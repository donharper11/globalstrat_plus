# Determinism fixture (V2-116), 0085 downgrade guard (V2-041), reset_simulation withheld (V2-076)

**Branch:** `crv2-01-fixture-downgrade-reset`, cut from `crv2-release-integration`
at `79db2bf`. Not pushed, not merged.

> **Development-grade. No gate is closed by this report.** I did not edit
> `V2_FINDINGS_REGISTER.md` or `LAUNCH_CHECKLIST_V2.md`; proposed wording is in
> §9. The replay in §3 is one environment, one game, one replayed round. It is
> **not** the four-environment release evidence, which GSP-CRV2-09 owns and
> which was not run.

---

## 1. Isolation (EXECUTION_PROTOCOL Phase 0)

| | |
|---|---|
| Suite runs | `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>` — a fresh `postgres:16-alpine` container per run, removed on exit |
| Fixture / migration runs | a second disposable container, `gsp-fdr-pg`, database `globalstrat_fdr`, built the way `scripts/test-postgres` and the V6 replay report build theirs: credential from `openssl rand -hex 32` held only in a mode-600 scratchpad file, port bound to `127.0.0.1`. **Every command against it ran under the same `flock`**, through a wrapper that refuses any `DB_HOST` other than `127.0.0.1` |
| Production | `192.168.50.38` never contacted. `/etc/globalstrat-plus.env` never read. No systemd unit touched. `backend/.env` does not exist in this worktree, so `settings.py` loaded nothing from it; `DB_HOST` was always set explicitly because its **default is the production host** |
| Settings for the disposable stack | `GLOBALSTRAT_ENV=development`, `LLM_GATEWAY_URL=` (no model: Phase 2 used its template fallback), `COMPETITION_BACKUP_DIR` in the scratchpad, `COMPETITION_RECOVERY_ENABLED=true` (required by `replay_round --restore`; set only in the scratchpad env file) |
| Cleanup | `gsp-fdr-pg` removed at the end; `docker ps` shows no `fdr` container |

Host: Ubuntu 22.04, Python 3.10.12, Django 5.2.4, PostgreSQL server 16 in the
container, client 18.3 (newer client against older server — the direction
STANDING-DISCIPLINE §1.9 permits, and the combination the V6 run used).

## 2. State found at head (`79db2bf`) — inventory before implementation

All three items were **still open**. Each was reproduced before anything was
changed.

| Item | Found at head |
|---|---|
| **V2-116** | `determinism_fixture.py` unchanged since `1d87281` (the CRV2-01 commit). Run against a freshly migrated disposable database it fails exactly as registered — see §3.1. It also has an **undocumented prerequisite**: `initialize_game` raises `No superuser found` on a fresh database (the first attempt died there, 0.9s). |
| **0085 downgrade** | The migration was a single `AlterField`. With a null `retail_price` present, `migrate core 0084` **was already refused — by PostgreSQL, not by us**: a bare `NotNullViolation … column "retail_price" … contains null values` under a traceback, naming no row and no remedy. So the hazard in the checklist is real but its shape is "opaque failure", not "silent data loss". See §4.1. |
| **V2-076** | `reset_simulation.py` has no environment check of any kind; `handle()` goes straight to the SQL. No caller anywhere in the repository (`grep` finds only the file itself and one spec inventory line). |

## 3. V2-116 — the determinism fixture runs again

### 3.1 Red, at head

```
$ python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4 --name RED-FIXTURE     [3.8s, exit 1]
core.engine.advance_round.InvalidPersistedDecisionError: Round 1 cannot be scored: 16 stored
R&D investment(s) remain, and feature-level R&D investment is retired (R10). Develop a new
platform and re-base the product onto it. DecisionRDInvestment row 1 (Prism Tech) targets
"Prism Tech Base Platform" [active]; …
```

### 3.2 The repair

`handoff_readiness_v2/determinism_fixture.py`:

- **No `DecisionRDInvestment` rows.** R10 retired the decision; the engine
  refuses every stored row.
- **R&D is now what R10 left standing: `DecisionPlatformDevelopment`**, seeded
  only where the rules in force allow it, and each condition is asked of the
  *same helper the engine precondition asks* so the fixture cannot drift from
  them the same way again: `rd_costs.unlock_problem`,
  `rd_costs.held_generation_ids`, `rd_costs.platform_development_cost` (the
  authored price, never a number invented in the fixture) and
  `rd_costs.feature_cap`. Two profiles develop, by two methods (`in_house`,
  `license`), because the two are priced from different authored fields.
- **A consequence the docstring now states plainly:** in the shipped scenarios
  Gen 2 unlocks in round 2, so **round 1 carries no R&D decision and
  `decision_platform` is empty there**. `--rounds 2` puts the platform path
  inside a replayable round; the per-round output line now prints
  `platform_developments=N`; `--require-platform-development` exits non-zero
  if no resolved round carried one. (`v6_envelope_fixture.py` has the same
  hole — `decision_rd`/`decision_platform` empty "by design" — and I did not
  change it.)
- The fixture creates a superuser with an unusable password when the database
  has none (the undocumented prerequisite above), and **refuses to run against
  the production database host or `GLOBALSTRAT_ENV=production`**. It previously
  relied on a docstring for that.
- The docstring no longer says "schema-version-2 manifest"; the fixture
  resolves at whatever version the code is on (6 here).

`v6_envelope_fixture.py` was the pattern for everything except R&D, where its
answer was to seed none.

### 3.3 Green — build, resolve, replay, negative control

Backend tree at the moment of resolution and replay was **byte-identical to
`79db2bf`** (only the fixture, which lives outside `backend/`, was modified), so
`replay_round` verified the source digest without an override.
`code_revision` reads `79db2bf…-dirty` for the same reason.

| # | Command (from `backend/`, under the flock) | Duration | Result |
|---|---|---:|---|
| 1 | `manage.py migrate --noinput` | 19.1s | OK, through `0087_merge_20260912_0446` |
| 2 | `manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml` | 1.9s | scenario id 1 |
| 3 | `determinism_fixture.py --teams 4 --name RED-FIXTURE` **(unrepaired)** | 3.8s | **exit 1**, §3.1 |
| 4 | `determinism_fixture.py --teams 4 --rounds 2 --require-platform-development` **(repaired)** | 14.7s | **exit 0**, game 2, two rounds resolved |
| 5 | `replay_round --game-id 2 --round 2 --export-only` | 1.0s | exit 0 |
| 6 | `replay_round --game-id 2 --round 2 --restore --confirm REPLAY-GAME-2-ROUND-2 --expected-manifest … --require-env tz_env=UTC --wait-narrative 0` | 15.2s | **exit 0 — "Replay reproduced the round exactly."** |
| 7 | negative control, clean: `replay_round … --restore --verify-only` | 12.7s | exit 0, input verified |
| 8 | tamper exactly one value | 0.2s | `decision_platform_development[1].committed_cost 15000000.00 -> 15000001.00` |
| 9 | negative control, tampered: `replay_round … --verify-only` | 1.4s | **exit 2 — "INPUT VERIFICATION FAILED — the engine was not run."** |

One resolution run and one replay: within the protocol's development budget of
"1 local replay" plus a negative smoke.

**Hashes (game 2, `DETERMINISM-FIXTURE`, section_id 90001, manifest schema 6):**

| | Round 1 | Round 2 (the replayed round) |
|---|---|---|
| `platform_developments` seeded | 0 | 2 |
| input_sha256 | `bbb9af3df72e331c368b35a24fa92b9779ad55cacd2259036f7ee4e6c7500714` | `ee8041d7f822470acfdd02508263b551e1c8e028ea6c5121eb8f3a2c889ffbf9` |
| output_sha256 (competitive) | `cebe93f7ad5f4603f4134374b2e9bd6acfed844d88b2787d859f77d507667017` | `ec4119f83b20e330595c7aaa13c78d9868049e8aa86eab4b1a5e13c0090dda87` |
| narrative_sha256 (recorded) | `249d113f…` | `dbe9eb05…` |

Replay of round 2: source verified `e23c8f1b442459d0b8494c41546a0b592f075bd3687ab95c6bfedbcf2f2c6acc`;
backup `game-2-round-2-20260921T204424976693Z.dump` sha256 `7470b742…93b` restored;
input verified `ee8041d7…`; **competitive hash expected `ec4119f8…dda87` ==
actual `ec4119f8…dda87`**.

**The narrative hash did NOT match on replay** (`dbe9eb05…` recorded,
`2d378cdd…` replayed), and `replay_round` reported it separately as designed.
The V6 run's narrative hash matched; this one did not. I did not investigate.
A plausible cause is that with `--wait-narrative 0` the hash is taken while the
Phase-2 thread is still writing template prose, but that is a guess, not a
finding. It is outside the competitive envelope by design and does not affect
the claim; it is listed in §8.

Round 2 was chosen for the replay because it is the round that contains what
was repaired: output sections `decision_platform` = **2 rows**, `team_platform`
= 6 (two new `in_development` Gen 2 platforms, `funded_round=2`), `decision_rd`
= 0, `decision_marketing` = 36, `financials` = 12. Stored developments:
Meridian Tech `in_house` 15,000,000.00; Vertex Electronics `license`
35,000,000.00; five features each (the cap).

**Negative control.** Placed deliberately on the repaired surface — a tampered
marketing price would refuse identically with or without this repair:

```
INPUT VERIFICATION FAILED — the engine was not run.
  section decision_platform: 0 missing, 0 added, 1 changed
      decision_platform(decision_submission(team(game("DETERMINISM-FIXTURE")|"Meridian Tech")
        |round(game("DETERMINISM-FIXTURE")|"2"))|platform_generation(scenario("Consumer
        Electronics 2026")|"2")|"Meridian Tech Gen 2 — Smart Connected Platform")
        .committed_cost: '15000000' -> '15000001'
[exit=2]
```

No evidence directory was written into the repository (protocol Phase 2: "Do
not write evidence directories"). The logs and manifests were in the session
scratchpad and are gone with it; the hashes above are the record.

### 3.4 Regression test

`backend/core/tests/test_determinism_fixture_runnable.py` (3 tests) imports the
checked-in script and runs **its own** `seed_round` against the real scenario,
then closes and resolves the round. Nothing in the suite ever ran this fixture,
which is how it drifted unnoticed; now the next rule change that makes it
unresolvable fails in the suite. It also asserts every R&D precondition
`_run_phase_1` asks (`persisted_retired_rd_/cost_/unlock_/ownership_/
feature_cap_/duplicate_generation_/held_generation_violations`) is empty for a
round-1 and a round-2 seeding. It is not replay evidence and says so.

## 4. Migration 0085 — downgrade guard

### 4.1 Red, at head

One `decision_marketing.retail_price` set to NULL on the disposable database,
then:

```
$ manage.py migrate core 0084                                                   [1.3s, exit 1]
  Unapplying core.0087_merge_20260912_0446... OK
  Unapplying core.0085_price_band_blank_price...Traceback (most recent call last):
psycopg2.errors.NotNullViolation: column "retail_price" of relation "decision_marketing" contains null values
```

Refused, but by accident and unreadably; and `0087` was left unapplied.

### 4.2 The change

In the migration's reverse path, which is safe for an already-applied
migration: the forward `AlterField`, the dependencies and the name are
untouched. A `RunPython(RunPython.noop, refuse_downgrade_while_null_prices_exist)`
is appended **after** the `AlterField`, because operations reverse last-to-first
and the guard has to run before NOT NULL is restored. `RunPython` has no state
effect, so an already-migrated database sees nothing, and
`makemigrations --check --dry-run` → **"No changes detected"** (1.0s).

The guard **refuses; it does not "make safe"**. Filling a price or deleting the
rows inside a migration would silently rewrite a decision a team made, and for a
processed round would alter a hashed manifest section. It counts the null rows,
names up to ten (row id, game, round number **and round status**, team), says
nothing was changed, says what to do, and warns that pricing or deleting a row
of a processed round breaks that round's replay.

### 4.3 Green — forward and backward, with and without null rows

| State | Command | Duration | Result |
|---|---|---:|---|
| 1 null row | `migrate core 0084` | 1.4s | **exit 1**, `NullPricesBlockDowngrade: REFUSED: cannot reverse core.0085_price_band_blank_price. 1 decision_marketing row(s) hold a null retail_price … Rows: decision_marketing #1 (game 1, round 1 [closed], team "Prism Tech"). Before retrying: take a competition backup, then price or delete every such row deliberately …` — row still null, column still nullable, 0085 and 0086 still applied |
| 0 null rows | `migrate core 0084` | 1.5s | **OK** — `Unapplying 0085… OK`, `Unapplying 0086… OK`; column `is_nullable = NO`; applied = `[0084]` |
| after that | `migrate core` | 1.5s | **OK** — 0086, 0085, 0087 re-applied; column `is_nullable = YES` |
| refused state | `migrate core` | 13.5s (mostly lock wait) | OK — re-applies the empty merge `0087` |

### 4.4 Test

`backend/core/tests/test_price_band_downgrade_guard.py` (5 tests). The suite
builds its schema from models with migrations disabled
(`globalstrat/test_runner.py`), so a migration **cannot** be reversed inside
it. The tests therefore exercise the guard function the reverse path calls
(refuses with a null row and names it; passes with priced rows; modifies
nothing) and pin the wiring (first operation is still the one `AlterField`;
dependencies unchanged; the guard is the **last** operation, reverse-only,
forward `noop`). The real reversal is §4.3.

## 5. V2-076 — `reset_simulation` withheld

`handle()` now begins with `_competition_refusal()` and raises `CommandError`
before anything else — **the dry run included** — when:

1. `settings.IS_PRODUCTION` (`GLOBALSTRAT_ENV=production`), or
2. `settings.COMPETITION_REQUIRE_CLEAN_BUILD` is on — the same two settings
   `build_identity.require_clean_build` reads, or
3. any row of `simulation_instance` carries `settings['is_competition']` — the
   flag `cohort_caps.is_competition_game` reads, asked of **every** instance
   rather than of `--instance-id`, because the SQL is not scoped to it, or
4. that flag **cannot be read** (fail closed).

**The SQL is untouched.** The diff is 78 insertions, 2 deletions, and the two
deletions are import lines. The file is CRLF-terminated and stays so.

**No override, and why.** None was needed, so none was added — no flag and no
environment variable. The command has no caller in the repository and no role
beside a competition heat; the supported recovery for a competition database is
the backup/restore path. An override reachable from the same shell as the
command is the guard being absent for exactly the operator it exists for. A
test pins the option list to `--confirm`, `--instance-id`,
`--reset-competitors`, and another shows three plausible override variable
names change nothing.

**A consequence to decide on, not a defect:** condition 1 withholds the command
from *every* production process, including non-competition teaching use on the
production host. That is what was asked for. Condition 4 also means it refuses
on a database with no `simulation_instance` table — such a database has none of
the legacy tables the command resets either. Live, on the disposable database:

```
$ manage.py reset_simulation --confirm                                                   [exit 1]
CommandError: REFUSED: reset_simulation is withheld from competition deployments (V2-076), and
the competition flag could not be read from simulation_instance (ProgrammingError: relation
"simulation_instance" does not exist), so it is treated as set. Its TRUNCATE/UPDATE statements
are not scoped to one instance … Nothing was changed. There is no override; …
```

`backend/core/tests/test_reset_simulation_withheld.py` (8 tests). "Touched
nothing" is proven rather than inferred: the command's `connection` is replaced
by a recorder, and each refusal asserts zero mutating statements and no
statement at all other than the guard's one `SELECT`.

## 6. Red, then green

Red was taken with the three test files present and the three repaired files
restored to `HEAD`:

```
$ flock … scripts/test-postgres core.tests.test_determinism_fixture_runnable \
    core.tests.test_price_band_downgrade_guard core.tests.test_reset_simulation_withheld
Ran 16 tests — FAILED (failures=2, errors=12)                                   [14s wall]
```

- downgrade guard: `AttributeError: module 'core.migrations.0085_price_band_blank_price' has no attribute 'refuse_downgrade_while_null_prices_exist'`; `<AlterField …> is not an instance of RunPython`
- reset: `AssertionError: unexpectedly None : the command ran instead of refusing`; `'Command' object has no attribute '_competition_refusal'`; four `InternalError: current transaction is aborted` — the command really ran its SQL against the test database and broke the transaction
- fixture: the first red run failed on **a bug in my test** (`cannot pickle 'module' object` from assigning the module in `setUpTestData`), which is not a red. Fixed and re-run against the unrepaired fixture (35s wall, 3 tests): `InvalidPersistedDecisionError: … 16 stored R&D investment(s) remain … retired (R10)`, `AssertionError: 16 != 0`, and `None != 0` (`seed_round` returned nothing).

Green, with the repairs:

| Command | Wall | Result |
|---|---:|---|
| the same three labels | 18s | **Ran 16 tests in 6.255s — OK** |
| `core.tests.test_reset_simulation_withheld` again after restoring CRLF (see §7) | 17s | Ran 8 tests — OK |
| affected modules: `core.tests.test_price_band core.tests.test_manifest_determinism core.tests.test_cohort_caps core.tests.test_rd_scoring_retired` | 80s (incl. lock wait) | **Ran 141 tests in 19.920s — OK** |
| source-scanning guards that read every `core/*.py`: `core.tests.test_narrative_llm_routing core.tests.test_crv2_12_language core.tests.test_player_language_guard` | 218s (almost all lock wait behind another builder) | **Ran 43 tests in 0.572s — OK** |

No full suite. No release-scale run.

## 7. Defects and observations found along the way

Recorded before repair; repaired only where inside this task.

1. **`determinism_fixture.py` needs a superuser and did not say so.** Repaired
   (in scope — it is the same "fixture is not runnable on a fresh database"
   defect).
2. **A refused downgrade leaves `0087_merge` unapplied**, before and after this
   change: Django commits each migration separately, so the empty merge is
   unapplied before 0085's reverse is reached. Harmless (it has no operations)
   and `manage.py migrate core` restores it; the refusal message says so. **Not
   repaired** — it cannot be fixed from inside 0085.
3. **Observed unapply order was 0087 → 0085 → 0086**, so the refusal arrives
   *before* 0086 drops `decision_research_purchase`. Had the order been the
   other way, a refused downgrade would already have destroyed the paid-research
   rows. I observed this order; I did not prove Django guarantees it. **A
   downgrade below 0086 destroys research purchases regardless** — that is
   outside this task and has no guard. Proposed as a new finding in §9.
4. **I briefly converted `reset_simulation.py` from CRLF to LF** with a patch
   script, which showed as a 1,030-line diff. Caught before commit and
   restored; the committed diff is 78/2. `git diff --check` flags the added
   lines as "trailing whitespace" because of the CRLF — consistent with the
   rest of the file, not new whitespace.
5. `v6_envelope_fixture.py` leaves `decision_platform` empty for the same
   unlock reason. Not changed.

## 8. What I could not verify

- **One environment.** Same host, Python, timezone, locale. Nothing here is
  cross-environment evidence.
- **The replay was taken at `79db2bf`'s backend tree, not at this branch's
  final commit.** The later backend changes are a migration reverse path, a
  management command and tests — none imported by the engine — but the source
  digest at the final commit differs from `e23c8f1b…` and no replay was run
  against it. I judged a second replay to be outside the development budget.
- **The narrative hash mismatch on replay is unexplained** (§3.3).
- **Round 1 was resolved but not replayed**; only round 2 was.
- **No model.** `LLM_GATEWAY_URL` was empty, so nothing about LLM divergence is
  shown.
- **The engine's funding/lead-time outcome for the seeded platforms was
  observed, not checked against a specification** (`in_development`,
  `development_rounds_remaining=1` after the funding round).
- **The 0085 guard was never exercised against a production-shaped database**,
  only a fixture database with one hand-made null row. The refusal path with
  more than ten rows (the "… and N more" branch) was not run.
- **The 0085 guard runs with the historical model state**; I ran it for real
  once per branch (§4.3) and otherwise tested it with live models.
- **`reset_simulation`'s refusal under a real `GLOBALSTRAT_ENV=production`
  process was not run** — production settings were not loaded anywhere. It is
  tested through `override_settings(IS_PRODUCTION=True)`. The is-competition
  path was tested in the suite's model-built schema, not against the legacy
  `simulation_instance` table as it exists in production (where `settings` is
  `jsonb`; the guard handles both a dict and a JSON string, and treats an
  unparseable value as flagged).
- The Phase-0 note "record database name, PID, branch and revision when a
  command starts" was met by the wrapper's log lines, not by a checked-in
  record.

## 9. Proposed register and checklist text (not applied)

**V2-116 — status update.**

> **Status update 2026-09-21 — repaired, pending closure.**
> `completion/FIXTURE_DOWNGRADE_RESET_2026-09-21.md`, branch
> `crv2-01-fixture-downgrade-reset`. The fixture no longer seeds
> `DecisionRDInvestment`; R&D is a `DecisionPlatformDevelopment` seeded only
> where `rd_costs`' own unlock, held-generation, price and feature-cap helpers
> allow. Reproduced red at `79db2bf` (the registered R10 refusal), then on a
> disposable database the repaired fixture resolved two rounds and round 2 —
> carrying two platform developments — replayed with competitive hash
> `ec4119f8…dda87` reproduced exactly, exit 0; one negative control on
> `decision_platform_development.committed_cost` refused before the engine,
> exit 2. **Development-grade, one environment; the narrative hash differed on
> replay and that is unexplained.** In the shipped scenarios round 1 carries no
> R&D decision (Gen 2 unlocks in round 2), so **CRV2-09 should run the fixture
> with `--rounds 2 --require-platform-development` and replay round 2**, or
> accept an empty `decision_platform`. A suite test now runs the fixture's own
> `seed_round` and resolves the round, so it cannot drift silently again. Not
> closed: the four-environment matrix has still not been regenerated.

**V2-076 — status update.**

> **Status update 2026-09-21 — mitigated in code, pending closure.** The
> command now refuses, dry run included, when `IS_PRODUCTION` or
> `COMPETITION_REQUIRE_CLEAN_BUILD` is set, when any `simulation_instance` row
> is flagged `is_competition`, or when that flag cannot be read. There is no
> override of any kind. **The unscoped SQL and the swallowed failures are
> unchanged** — the finding's defect still exists for any environment where the
> guard passes. 8 tests, each proving no statement was issued. Not verified
> under a real production process.

**V2-041 — rollback-hazard note.**

> **2026-09-21:** the downgrade guard exists. Reversing `0085` refuses while any
> `decision_marketing.retail_price` is null, names the rows and changes
> nothing; forward operation, dependencies and name untouched,
> `makemigrations --check` clean. Exercised forward and backward on a
> disposable database with and without null rows. It refuses rather than
> repairs, deliberately: pricing or deleting a row of a processed round changes
> a hashed section.

**Proposed new finding (P2) — downgrade below 0086 destroys paid-research rows.**

> `migrate core 0084` reverses `0086_paid_research_reports`, dropping
> `decision_research_purchase` — charged, hashed decisions — with no guard. The
> 0085 guard happens to fire first in the observed unapply order
> (0087 → 0085 → 0086) but only when a null price exists. P2: a deliberate
> operator action, and the supported recovery is a restore, not a downgrade.
> Owner: operations / CRV2-09.

**Launch checklist — proposed wording; I would leave both boxes for the owner.**

> - [ ] `reset_simulation` withheld from the competition deployment. **Code
>   guard landed 2026-09-21** (refuses under `GLOBALSTRAT_ENV=production`,
>   `COMPETITION_REQUIRE_CLEAN_BUILD`, any `is_competition` instance, or an
>   unreadable flag; no override). Still to do at deployment: confirm the
>   competition stack actually sets one of those (this depends on the unticked
>   `COMPETITION_REQUIRE_CLEAN_BUILD` / `is_competition` items above) and run
>   the command once there to see it refuse.
> - [ ] Downgrade guard for migration `0085_price_band_blank_price`. **Landed
>   2026-09-21** in the migration's reverse path; refuses and names rows.
>   Remaining: owner acceptance, and note the unguarded `0086` reversal.
> - V2-116 note under the v6 replay gate: replace "does not run at head" with
>   "repaired 2026-09-21 on `crv2-01-fixture-downgrade-reset`; run with
>   `--rounds 2`". The gate itself stays open.

## 10. Auditor preflight (applicable questions)

- *Inventory from registries, not from the new helper?* Yes for item 3: the
  refusal reads the same settings and flag the existing guards read; the
  command's callers were searched repository-wide (none).
- *Alternate entry point?* `reset_simulation` has none left — the routed form
  was deleted under R16. The 0085 reversal has one entry (`migrate`).
- *Does each negative test prove mutation/engine execution did not occur?*
  Replay: exit 2 and "the engine was not run". Reset: statement recorder.
  Downgrade: row still null, column still nullable, migration still applied.
- *Do claimed environment values describe the executing process?*
  `--require-env tz_env=UTC` asserted by `replay_round` itself.
- *Do P-labels match?* No severity was changed. The one proposed finding is P2
  by the register's own reasoning for operator-shell actions.

## 11. Files

| File | sha256 |
|---|---|
| `handoff_readiness_v2/determinism_fixture.py` | `d8b8f114bcb95ed02441dd1cef333133abec8e1862c54f4d03c5d7e5b9e90c97` |
| `backend/core/migrations/0085_price_band_blank_price.py` | `0cb8072dbc9ee702a31a14aeaa773f6c64bd3d43e167005e30fd81f58339b8b0` |
| `backend/core/management/commands/reset_simulation.py` | `e7cd96d7d0d033ab03909f4870eaa6ea052a0a7099653313d08fee5d0c9988be` |
| `backend/core/tests/test_determinism_fixture_runnable.py` | `356334dc7e5b535184e911b1af90dfa97542e41bda0232ebd09ad114a9e273bd` |
| `backend/core/tests/test_price_band_downgrade_guard.py` | `a0920fd06527a81bf1d5e00b0dbdc356549c16d6a029faeb4e1ac6b6df6361e3` |
| `backend/core/tests/test_reset_simulation_withheld.py` | `75cd26ddf7c361eedf26a38eaef30768ec07141c8329effe315cb9627563a20d` |
