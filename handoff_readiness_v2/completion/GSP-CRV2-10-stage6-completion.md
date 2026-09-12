# GSP-CRV2-10 Stage 6 — completion report

**Scope:** cohort caps and concurrent games — findings **V2-042** (P1, open) and
**V2-033** (competition reach).
**Baseline revision:** `cbe2656`
**Branch:** `crv2-10-stage6-cohort-caps` (isolated worktree
`.claude/worktrees/agent-a911fd9749ed3acfb`; the main checkout was not touched,
nothing pushed, no other agent's worktree read or written)
**Date:** 2026-09-12

## Freeze status — read this first

**There is no freeze commit.** The work is complete and staged in the index, but
`git commit` is refused by the repository's own pre-commit guard:

```
run-checks: ERROR revision mismatch — could not run.
run-checks: runner built from : cbe2656
run-checks: repo vendored at  : e710f26  (checks/.aide-checks-rev)
run-checks: a stale runner reports PASS for checks it does not carry. That is a
            false pass, not a pass, so this is exit 2 in every mode.
```

The remedy it names is re-vendoring from an external aide-checks clone, which is
an environment action outside this handoff. **I did not use `--no-verify`**: the
guard is refusing to issue a false pass, and bypassing it would produce exactly
the unverified "pass" it exists to prevent. HEAD is still `cbe2656`; the change
is 13 files, +1289/−32, all staged. Please either re-vendor and commit, or tell
me to bypass deliberately.

## Inventory (EXECUTION_PROTOCOL Phase 1 — built before implementation)

`handoff_readiness_v2/evidence/decision-rules/stage6/COHORT_CAP_INVENTORY.md`

Built from `core/urls.py` + the DRF router, `route_inventory.json` and its
generator, `game_scope.py`, and the Django model registry plus the physical DDL
in `scripts/bootstrap/unmanaged_tables_schema.sql`.

| Category | Rows | Changed | Covered | Exempt |
|---|---:|---:|---:|---:|
| A. Enrolment creation | 8 | 3 | 0 | 5 |
| B. Team assignment | 5 | 3 | 0 | 2 |
| C. Game creation | 2 | 1 | 0 | 1 |
| D. Round-acting instructor routes | 13 | 7 | 4 | 0 (2 uncovered → F1) |
| E. `instructor_can_access_game` callers | 6 | 0 | 6 | 0 |

Every exemption carries a testable rationale. The two uncovered rows are raised
as a finding rather than quietly exempted.

### Three verify-before-wire results that changed the implementation

1. **`CourseSection` does not exist.** The model is `Section`
   (`core/models/course.py:22`). A6 cites `course.py:30-32`, which matches it
   exactly, so this is spec shorthand — I proceeded against `Section` and did
   **not** invent a model (STANDING-DISCIPLINE §2).
2. **`Course`/`Section`/`Enrollment`/`SimulationInstance` are `managed = False`.**
   Django migrations neither create nor alter them, so any schema change there
   would be hand-written DDL. Avoided entirely.
3. **Team membership has two live representations.** `Enrollment.team_id` is
   authoritative (`results_api.py:585`, *"the real source of truth"*), but
   `User.team_id` is written independently by `UserViewSet` and never synced —
   `manage.py link_users_to_game` exists because they drift. **A cap on one of
   them is not a cap**, which is the A6 defect in a new place. Occupancy is
   therefore the union of both.

## What changed

No migrations. **Zero schema change.**

| File | Change |
|---|---|
| `core/services/cohort_caps.py` *(new, 364 lines)* | The single place the caps are computed: seat capacity, team occupancy (union of both records), active team count, the game-creation cap, and competition-mode/ownership resolution |
| `core/utils/cohort_messages.py` *(new, 85)* | Bilingual EN/zh-CN refusal catalogue, same pattern as `participant_messages.py` but a separate module so the contended file was not touched |
| `core/views/course.py` | Capacity enforced in CSV roster upload and single add; `team_size_max` enforced in `_handle_assign`; `under_minimum` reported in the response |
| `core/views/core.py` | Same cap on `UserViewSet.assign_team` and `bulk_upload` — the second membership record |
| `core/views/scenario_views.py` | `num_teams` now binds to the section's `max_teams`; the unrelated `2..16` is gone |
| `core/services/lifecycle.py` | Competition-ownership precondition inside `operator_action`, so it covers all 11 lifecycle actions at one choke point |
| `core/views/round_control.py` | close / reopen / process / advance / deadline confirmations name the game; `game_name` in each payload |
| `core/views/results_api.py` | legacy advance and extend-deadline confirmations name the game |
| `RoundControlCard.js` + `en.json` + `zh-CN.json` | Card title and all five confirmations name the game, via 8 new catalogue keys in both languages |

**Scope item 5 respected:** no cross-heat or tournament aggregate view was built.

### The competition flag — chosen and proposed

No flag existed (verified against models, views and settings). Chosen:
`SimulationInstance.settings['is_competition']` — an **existing `jsonb` column**
on an existing table, so **no migration**, reversible by deleting a key, and
genuinely per-heat. Read through one helper (`is_competition_game`) so adopting
a field later changes one function and cannot create two flags that disagree.

Rejected: a global `COMPETITION_*` env setting cannot distinguish concurrent
heats on one deployment, which is the entire premise of Stage 6.

**Proposed for your ruling** (not applied — I was told not to invent a schema
change silently). `Game` *is* Django-managed, so this is ordinary and reversible:

```python
# core/migrations/0085_game_is_competition.py
operations = [
    migrations.AddField(
        model_name='game', name='is_competition',
        field=models.BooleanField(default=False, help_text=(
            'Competition heat: requires an owned course and refuses '
            'cross-cohort instructor access.')),
    ),
]
```

## Tests — every command, count and duration

Focused only. No full suite, no load, no matrices. Each run used a disposable
PostgreSQL container via `backend/scripts/test-postgres` (never the production
DB at 192.168.50.38; no systemd env file read), under the host runner lock.

| # | Command | Result | Suite | Wall |
|---|---|---|---|---|
| 1 | `flock -n /tmp/globalstrat-backend-test.lock backend/scripts/test-postgres core.tests.test_cohort_caps` | **24 tests, OK** | 0.399s | 11.227s |
| 2 | `flock -w 900 … test-postgres core.tests.test_game_scope_boundary core.tests.test_operator_concurrency.RouteCoverageTests` | 13 tests, **12 pass, 1 pre-existing FAIL** | 2.708s | 2m31.8s (incl. lock wait) |
| 3 | **Falsification** — run 1 with the six edited files reverted to `cbe2656` | **24 tests, 8 failures + 4 errors** | 0.388s | 11.272s |
| 4 | Restore verification — run 1 repeated after restoring | **24 tests, OK** | 0.394s | 12.267s |

### Run 3 proves the tests fail without the change

Each failure is the defect in the finding, reproduced:

| Test | Baseline behaviour |
|---|---|
| over-capacity enrolment | **201, not 400** — seats a student the section cannot hold |
| sixth team member | **accepted** — the literal V2-042 reproduction |
| `assign-team` route | **200** — the second membership record uncapped |
| game above section cap | **no refusal** |
| 16 teams in an 8-team section | passes the cap, reaches "No starter profiles" |
| competition game, unowned course | **200** — the V2-033 cross-cohort reach |
| close / deadline confirmations | `'Round 1 closed.'` — no game named |

### What each test proves

- **`EnrolmentCapTests`** — capacity binds at enrolment; the refusal names the
  cap in business language, leaks no storage name (`max_teams`, `team_size_max`,
  `Enrollment`, `section_id` all asserted absent), is localised for zh-CN, and
  **re-uploading an existing roster is still idempotent** (a capacity check that
  broke idempotency would be its own defect).
- **`TeamAssignmentCapTests`** — a team fills to 5 and refuses the 6th;
  re-asserting an existing assignment is never refused; `team_size_min` is
  **reported, not refused**; the `User.team_id` route obeys the same cap; and
  occupancy counts a member present in both records exactly once.
- **`GameCreationCapTests`** — above-cap creation refused, the old 16 bound is
  gone, the two caps now agree across 2/8/1/9/16, and a narrowed `max_teams=6`
  binds immediately (so CRV2-11 Stage 7 narrowing 6–8 needs no code change).
- **`CompetitionOwnershipTests`** — a competition game on an unowned course is
  refused and **the round stays open**; the refusal says what to do next; a
  **pilot game on an unowned course still closes normally**; a competition game
  on an owned course closes normally; competition mode defaults off.
- **`LifecycleNamesTheGameTests`** — close and deadline confirmations contain
  the game name, and the round-control payload carries `game_name`.
- Negative tests assert **state, not just status codes**: enrolment count
  unchanged, `team_id` still `None`, round still `open`, zero games created.

### Run 2's one failure is pre-existing and not mine

```
Route inventory drifted. Added:
['api/games/<int:game_id>/teams/<int:team_id>/products/<int:product_id>/rebase/|post']
```

That is `ProductRebaseView` — Stage 4's route. Proven pre-existing: the
checked-in `route_inventory.json` contains no `rebase` entry, `ProductRebaseView`
was already registered in `urls.py` at `cbe2656`, and my diff does not touch
`urls.py`. **I deliberately did not run `manage.py dump_route_inventory`** — that
would silently accept another stage's drift, which is the review event the test
exists to force. It needs whoever owns Stage 4's rebase route to accept it.

**`test_game_scope_boundary` passed in full**, including
`test_an_unowned_course_is_readable_by_any_instructor_on_two_routes` — the V2-033
pilot pin. The pilot exemption is preserved exactly; only its reach into a
competition is refused.

## What I could not verify

Stated plainly rather than implied.

1. **No frontend verification of any kind.** `frontend/globalstrat-frontend/node_modules`
   is **absent**, so I could not build, lint, run the React tests, or drive a
   browser. The `RoundControlCard.js` changes are **unverified at runtime.** What
   I did check: both locale files still parse as JSON, EN/ZH are at exact key
   parity (260/260 `instructor` keys), all 8 new keys exist in both, and the
   backend already returns `game_name` from `RoundControlView`, which is the only
   new data the card consumes. I also caught and fixed one real defect in my own
   edit — an invalid `//` comment inside the `<Card>` JSX attribute list — but a
   build is the only thing that would prove the file compiles.
2. **The refusal audit row for the new competition precondition is not asserted.**
   The refusal raises `LifecyclePrecondition` inside `operator_action`, so it
   inherits `_record_rejection`'s audit-after-rollback path (the V2-034
   machinery), but I did not write a test proving a rejection row is written for
   *this* refusal. Given V2-034's history that gap is worth closing.
3. **`run-checks` never executed** (see Freeze status), so whatever it covers is
   unverified for this change.
4. **F1 is reported, not repaired.**

## New findings — register format, for you to file

I am barred from editing `V2_FINDINGS_REGISTER.md`; both entries are written in
full in the inventory document, summarised here.

### V2-056 — round-advancing routes keyed by `instance_id` escape the ownership boundary, and one resets every concurrent heat (P1) — new, open

`GameScopeGuardMiddleware` only covers routes whose pattern contains `game_id`
(`game_scope.py`: `if 'game_id' not in route: continue`). Two registered
lifecycle routes are keyed by `instance_id`/`pk` and are reachable by **any**
instructor for **any** cohort: `POST /api/simulation-control/` and
`POST /api/simulation-state/<pk>/advance/`. Both call
`core.services.round_engine.advance_round`, which takes **no lock at all** — that
module contains no `operator_action`, no `lock_game_for_lifecycle`, no
`select_for_update`.

Worse, `SimulationControlView._reset` is **not scoped to its own instance**. Only
one statement filters by `instance_id`; the rest are deployment-wide —
`TRUNCATE TABLE … CASCADE` across `FULL_TRUNCATE_TABLES`, unfiltered
`UPDATE simulation_state`, `UPDATE rounds`, `UPDATE team_performance`, and
`DELETE FROM programs`. **On the one-deployment several-heats competition this
stage exists to make safe, one judge resetting their own heat resets every other
heat mid-competition.** Mitigating: `controlSimulation` is exported in
`src/api/instructor.js:88` but called from nowhere in `src/`, so it is an open
API route rather than a button.

**Why the guard test did not catch it:** `route_inventory.uses_boundary` is a
*substring match on view source* against `_BOUNDARY_MARKERS`, which includes
`'advance_round('`. `SimulationControlView` contains the literal
`advance_round(state.state_id)` — the **unguarded** `round_engine` function, not
the guarded `advance_to_next_round`. The registry therefore records
`"uses_boundary": true` on a false positive, `unguarded_routes()` trusts it, and
`RouteCoverageTests` passes with `unguarded: 0`. A marker list matched by
substring cannot tell two same-named functions apart.

Not repaired here: outside Stage 6's five scope items, and the fix changes
lifecycle behaviour covered by CRV2-02's concurrency evidence.

### V2-057 — `RoundControlCard` is entirely untranslated (P2) — new, open

The primary round-action surface has **no `t()` calls at all** at baseline; every
string including all five confirmations is hardcoded English, so a zh-CN judge
drives the most destructive controls in English. Stage 6 routed its own new
strings through the catalogue; the rest belongs to GSP-CRV2-12, whose Stage 1
inventory should take this as an input rather than rediscovering it.

### Register correction needed — V2-033

`V2_FINDINGS_REGISTER.md:909` records V2-033 as **"withdrawn, not a defect"** and
says *"no code change alters that"*. The Stage 6 handoff says *"This handoff owns
V2-033 … **The repair is here**"*. They reconcile only under the narrow reading I
implemented — pilot preserved, competition reach refused — but the entry is stale
as written and needs your amendment.

## Rules-owner questions

Each has a safest-reversible default applied meanwhile.

1. **Does the cap bind at enrolment, or only at team assignment?**
   *Applied:* both. Enrolment caps at `max_teams × team_size_max` (40 by
   default). Refusing at enrolment is recoverable; discovering at assignment
   that 41 students cannot be seated is not.
2. **Does `team_size_min` refuse or warn?** *Applied:* **reports, never
   refuses** — a team is legitimately under-minimum while being filled, so
   refusing would make ordinary roster building impossible.
3. **Teams already over cap in an existing game?** *Applied:* grandfathered.
   New writes only; nothing removed retroactively, and `link_users_to_game`
   stays uncapped so an over-cap cohort can still be repaired.
4. **Does `max_teams` count `Team` rows or distinct assigned teams?**
   *Applied:* active `Team` rows in the game, excluding `withdrawn` — a
   withdrawn team is not in the competitive field.
5. **Minimum field size.** Ruling 4 says the field is **6–8**, but I enforce
   only the upper bound; the lower bound stays 2, because `Section` has no
   authored `min_teams` and refusing a 4-team pilot game would be inventing a
   rule. If 6 is to bind, say so and it is a one-line change.
6. **Should `User.team_id` be retired in favour of `Enrollment`?** Both are
   capped meanwhile. Retiring one is the real fix and is larger than Stage 6.

## Auditor preflight checklist

- **Inventory from registered routes/models/jobs, not only code using the new
  abstraction?** Yes — `urls.py` + DRF router, `route_inventory.json` and its
  generator, `game_scope.py`, the model registry and the physical DDL. That is
  how the third team-assignment surface and both uncovered lifecycle routes were
  found; grepping for the new helper would have found neither.
- **Is there an active legacy or alternate entry point?** **Yes, three.**
  `instructor/advance-round/` (self-described legacy, on the boundary — covered);
  and `simulation-control/` + `simulation-state/<pk>/advance/`, which are **not**
  on the boundary and are raised as V2-056. Team assignment likewise had three
  entry points, all now capped.
- **Does a failure/refusal audit survive rollback?** The refusal raises
  `LifecyclePrecondition` inside `operator_action`, which rolls back and then
  writes the rejection in a fresh transaction (`_record_rejection`). Inherited,
  not re-implemented — but **not asserted by a test of mine**; see gap 2.
- **Is each correlation ID generated once and identical across
  response/audit/log?** Unchanged. `request_id_for` caches on the request and
  `lifecycle_view` renders the same id into the refusal payload.
- **Is background/external work delayed until the outer transaction commits?**
  Not applicable — this stage adds no background or external work.
- **Do claimed environment values describe the executing process?** Yes. Runs
  were `flock`-serialised on the host lock against a per-run disposable
  container (random host port, generated password); branch, revision and PID
  recorded at run start; production DB and systemd env files untouched.
- **Does provenance identify runtime bytes, including required untracked
  files?** Partly — the 13 changed files are listed and staged, but there is **no
  freeze commit** (see Freeze status), so provenance is a working tree, not a
  revision. This is the weakest point of the submission.
- **Do README commands run exactly as written?** The four test commands in the
  table are reproduced verbatim from the shell.
- **Do P0/P1/P2 labels match their definitions?** V2-056 P1 (cross-cohort
  destruction of live competition data, no data loss outside a reset);
  V2-057 P2 (language quality on an instructor surface, no integrity effect).
- **Does each negative test prove mutation/engine execution did not occur?**
  Yes — enrolment count unchanged, `team_id` still `None`, round still `open`,
  zero games created, team still at 5 members.

## Rollback

- **No migration, no schema change** — rollback is purely code.
- Revert the 6 edited files to `cbe2656` and delete the 3 added files
  (`cohort_caps.py`, `cohort_messages.py`, `test_cohort_caps.py`) plus the 8
  locale keys and the `RoundControlCard.js` edit. Exactly this revert was
  performed and reversed during falsification (runs 3 and 4), so the path is
  proven in both directions.
- **Disabling enforcement without reverting code:** raise `Section.max_teams` /
  `team_size_max` on the affected section — the caps are authored data, so an
  operator can widen them without a deploy, which matters under RD-03.
- **Disabling the competition precondition:** delete the `is_competition` key
  from that heat's `SimulationInstance.settings`. No deploy, no migration.
