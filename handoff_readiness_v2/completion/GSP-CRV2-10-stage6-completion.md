# GSP-CRV2-10 Stage 6 — completion report

**Scope:** cohort caps and concurrent games — **V2-042** (P1) and **V2-033**
(competition reach).
**Original baseline:** `cbe2656`
**Rebased onto:** `crv2-release-integration` head `e1b744c`
**Frozen at:** `f035884` (plus the follow-up commit adding the refusal-record
test and this report)
**Branch:** `crv2-10-stage6-cohort-caps`, isolated worktree. Main checkout never
touched, nothing pushed, no other agent's worktree read or written.
**Date:** 2026-09-12

## Commit and rebase record

**Committed with `--no-verify`, deliberately and on instruction.** The
`run-checks` pre-commit hook fails because `checks/.aide-checks-rev` is absent,
so it has no vendored revision to compare against and refuses rather than emit a
pass it cannot stand behind. Re-vendoring from `~/projects/aide-checks` is
outside this handoff; the hook's own header sanctions `--no-verify`, with the
deploy gate as the non-bypassable layer. I did not bypass it on my own judgement
— my first two commit attempts were refused and reported, and the bypass was
authorised afterwards.

**The rebase needed `--onto`.** A plain `git rebase crv2-release-integration`
tried to replay **two** commits, because `cbe2656` is not an ancestor of the
integration branch — its content was split into reviewed commits there. That
replay conflicted in `handoff_readiness_v2/V2_FINDINGS_REGISTER.md`, a file I am
forbidden to edit and never touched. **I aborted rather than resolve a conflict
in someone else's file**, then used:

```
git rebase --onto crv2-release-integration cbe2656
```

which replays only this handoff's commit. It applied cleanly: the integration
branch's diff against `cbe2656` touches none of the six source files, neither
frontend file, and none of the new modules.

## Inventory (Phase 1 — built before implementation)

`handoff_readiness_v2/evidence/decision-rules/stage6/COHORT_CAP_INVENTORY.md`

Built from `core/urls.py` + the DRF router, `route_inventory.json` and its
generator, `game_scope.py`, the Django model registry, and the physical DDL in
`scripts/bootstrap/unmanaged_tables_schema.sql`.

| Category | Rows | Changed | Covered | Exempt |
|---|---:|---:|---:|---:|
| A. Enrolment creation | 8 | 3 | 0 | 5 |
| B. Team assignment | 5 | 3 | 0 | 2 |
| C. Game creation | 2 | 1 | 0 | 1 |
| D. Round-acting instructor routes | 13 | 7 | 4 | 0 (2 uncovered, reported) |
| E. `instructor_can_access_game` callers | 6 | 0 | 6 | 0 |

Three verify-before-wire results changed the implementation:

1. **`CourseSection` does not exist** — the model is `Section`. Spec shorthand;
   I did not invent a model (STANDING-DISCIPLINE §2).
2. **The cohort tables are `managed = False`** — so this stage makes **zero
   schema change**.
3. **Team membership has two live representations.** `Enrollment.team_id` is
   authoritative; `User.team_id` is written independently by `UserViewSet` and
   never synced (`link_users_to_game` exists because they drift). Team
   assignment had **three** write surfaces. A cap on one of them is not a cap,
   so occupancy is the union of both.

## What changed

No migrations.

| File | Change |
|---|---|
| `core/services/cohort_caps.py` *(new)* | The single place caps are computed: seat capacity, team occupancy (union), active team count, game-creation cap, competition mode and ownership |
| `core/utils/cohort_messages.py` *(new)* | Bilingual EN/zh-CN refusal catalogue; a separate module so the contended `participant_messages.py` was not touched |
| `core/views/course.py` | Capacity enforced on CSV upload and single add; `team_size_max` on `_handle_assign`; `under_minimum` reported |
| `core/views/core.py` | Same cap on `UserViewSet.assign_team` and `bulk_upload` |
| `core/views/scenario_views.py` | `num_teams` binds to the section's `max_teams`; the unrelated `2..16` is gone |
| `core/services/lifecycle.py` | Competition-ownership precondition inside `operator_action` — one choke point covering all 11 lifecycle actions |
| `core/views/round_control.py` | close/reopen/process/advance/deadline confirmations name the game |
| `core/views/results_api.py` | legacy advance and extend-deadline confirmations name the game |
| `RoundControlCard.js`, `en.json`, `zh-CN.json` | Card title and five confirmations name the game; 8 new keys in both languages |

Scope item 5 respected: **no cross-heat or tournament aggregate view was built.**

## Answering the two things that could not be verified from the diff

### The `LifecyclePrecondition` signature is valid

`LifecyclePrecondition` (`services/lifecycle.py:79-83`) overrides only
`status_code`. It inherits `__init__(self, detail, guidance='', code='')` from
`LifecycleError` at **line 42**, so `LifecyclePrecondition(unowned,
guidance=..., code=...)` is correct. This is also proven at runtime, not just by
reading: `test_the_refusal_says_what_to_do_next` asserts the rendered
`guidance`, and `test_a_competition_game_on_an_unowned_course_is_refused`
asserts `code == 'competition_course_unowned'`. Neither could pass if the
keywords were rejected or silently dropped.

### The refusal **is** audited — now pinned by a test

`test_the_refusal_is_recorded` (new) proves the rejection row exists. It
asserts an `OperatorAuditEvent` with `action='close_round'`,
`outcome='rejected'`, `conflict.code == 'competition_course_unowned'`, a
`request_id` **equal to the one returned to the operator**, `round_id is None`
and `after == {}`.

Two details make it work, both deliberate:

- The precondition is raised **after** `holder.game = game`. `_record_rejection`
  runs only under `if holder.game is not None`, so raising one line earlier
  (where the "No game" precondition lives) would have produced **no record at
  all** — the exact V2-034 failure shape.
- `OperatorAuditEvent.round` is `null=True, blank=True`
  (`models/competition_audit.py:65`) and `record_operator_event` passes it
  through unchanged, so a refusal raised before the round is ever read still
  produces a row rather than an exception swallowed by `_record_rejection`'s
  broad `except`.

## Operating procedure — the flag this protection depends on

**This is the load-bearing operational consequence of the design.** The
competition refusal keys off
`SimulationInstance.settings['is_competition']`. That choice needs no migration,
is per-heat and is reversible — but **if nobody sets it, the refusal never fires
and the protection is silently absent.** There is no error, no banner and no log
line to notice. It must be a launch step, not tribal knowledge.

### Setting it, per heat

Read-modify-write, so other settings keys survive:

```python
from core.models.course import SimulationInstance
instance = SimulationInstance.objects.get(game_id=<GAME_ID>)
instance.settings = {**(instance.settings or {}), 'is_competition': True}
instance.save(update_fields=['settings'])
```

**Do not** use `SimulationInstance.objects.filter(...).update(settings={...})`:
that replaces the whole JSON blob and would discard any other key it holds.

### Verifying every heat before launch

```python
from core.models.core import Game
from core.services.cohort_caps import (
    is_competition_game, competition_ownership_error)
for game in Game.objects.filter(status__in=('setup', 'active')):
    print(game.id, game.name,
          'competition' if is_competition_game(game) else 'NOT FLAGGED',
          competition_ownership_error(game) or 'ownership OK')
```

Every heat must print `competition` **and** `ownership OK`. A heat printing
`NOT FLAGGED` is running without the V2-033 protection. A heat that is flagged
but prints a refusal message has no instructor of record and will refuse every
lifecycle action until one is assigned.

### What a judge sees in each state

| State | What happens |
|---|---|
| Flagged, course owned | Normal. No behaviour change of any kind. |
| Flagged, course unowned | **Every** lifecycle action (close, reopen, process, advance, deadline, extend, inject) is refused **400** with `competition_course_unowned`: *"… is a competition game with no instructor of record, so it cannot be opened or changed. Assign an instructor to its course, then try again."* Recovered by setting `Course.instructor_id`; no deploy. |
| **Not flagged, course unowned** | **Nothing visible — and this is the dangerous one.** The game behaves exactly like a pilot game, so the unowned course stays readable by every instructor on the deployment. The protection is absent and silent. |

### Launch-checklist entry (for you to file — I did not edit the checklist)

> For every competition heat, set `SimulationInstance.settings['is_competition'] = True` and confirm its course has a non-null `instructor_id`; verify all heats with the audit snippet in `completion/GSP-CRV2-10-stage6-completion.md` — an unflagged heat silently loses the V2-033 cross-cohort protection.

## Tests — every command, count and duration

Focused only; no full suite, no load, no matrices. Each run used a disposable
PostgreSQL container via `backend/scripts/test-postgres` (never the production
DB at 192.168.50.38, no systemd env file read), serialised on the host runner
lock.

### Post-rebase, on `e1b744c`

| # | Command | Result | Suite | Wall |
|---|---|---|---|---|
| 1 | `flock -w 900 … test-postgres core.tests.test_cohort_caps` | **25 tests, OK** | 0.416s | 10.8s |
| 2 | `flock -w 900 … test-postgres core.tests.test_game_scope_boundary core.tests.test_operator_concurrency.RouteCoverageTests` | **13 tests, OK** | 2.759s | 14.5s |

**The `ProductRebaseView` route drift has cleared.** Run 2 previously failed on
`test_inventory_matches_the_checked_in_copy`; the integration branch's
route-inventory refresh repaired it, and I did not work around it in the
meantime. `test_game_scope_boundary` passes in full, including
`test_an_unowned_course_is_readable_by_any_instructor_on_two_routes` — the
V2-033 pilot pin. The pilot exemption is preserved exactly; only its reach into
a competition is refused.

### Pre-rebase, on `cbe2656` (includes the falsification)

| # | Command | Result | Suite | Wall |
|---|---|---|---|---|
| 3 | `test-postgres core.tests.test_cohort_caps` | 24 tests, OK | 0.399s | 11.2s |
| 4 | same as run 2 | 13 tests, 12 pass, 1 **pre-existing** fail (route drift, now repaired upstream) | 2.708s | 2m31.8s |
| 5 | **Falsification** — run 3 with the six edited files reverted to `cbe2656` | **8 failures + 4 errors of 24** | 0.388s | 11.3s |
| 6 | Restore verification | 24 tests, OK | 0.394s | 12.3s |

### Run 5 proves the tests fail without the change

| Test | Baseline behaviour |
|---|---|
| over-capacity enrolment | **201, not 400** — seats a student the section cannot hold |
| sixth team member | **accepted** — the literal V2-042 reproduction |
| `assign-team` route | **200** — the second membership record uncapped |
| game above section cap | **no refusal** |
| 16 teams in an 8-team section | passes the cap, reaches "No starter profiles" |
| competition game, unowned course | **200** — the V2-033 cross-cohort reach |
| close / deadline confirmations | `'Round 1 closed.'` — no game named |

### What the tests prove

- **`EnrolmentCapTests`** — capacity binds at enrolment; the refusal names the
  cap in business language, leaks no storage name (`max_teams`,
  `team_size_max`, `Enrollment`, `section_id` asserted absent), is localised for
  zh-CN, and re-uploading an existing roster stays idempotent.
- **`TeamAssignmentCapTests`** — a team fills to 5 and refuses the 6th;
  re-asserting an existing assignment is never refused; `team_size_min` is
  reported, not refused; the `User.team_id` route obeys the same cap; a member
  present in both records is counted once.
- **`GameCreationCapTests`** — above-cap creation refused, the old 16 bound
  gone, the two caps agree across 2/8/1/9/16, and a narrowed `max_teams=6` binds
  immediately (so CRV2-11 narrowing 6–8 needs no code change).
- **`CompetitionOwnershipTests`** — a competition game on an unowned course is
  refused and the round **stays open**; the refusal says what to do next; the
  refusal **is recorded**; a pilot game on an unowned course still closes
  normally; competition mode defaults off.
- **`LifecycleNamesTheGameTests`** — close and deadline confirmations contain
  the game name; the round-control payload carries `game_name`.
- Negative tests assert **state, not just status**: enrolment count unchanged,
  `team_id` still `None`, round still `open`, zero games created.

## Still unverified

1. **The frontend `RoundControlCard` change is unproven and stays that way.**
   `frontend/globalstrat-frontend/node_modules` is absent in this worktree, so I
   could not build, lint, run React tests or drive a browser. **It needs a
   browser pass in the main checkout before it can be called done.** What I did
   check: both locale files parse, EN/ZH are at exact key parity (260/260
   `instructor` keys), all 8 new keys exist in both, and the backend already
   returned `game_name`, which is the only new data the card consumes. I also
   found and fixed a real defect in my own edit — an invalid `//` comment inside
   the `<Card>` JSX attribute list — but only a build proves the file compiles.
2. **`run-checks` never executed** (no vendored revision), so whatever it covers
   is unverified for this change; the deploy gate remains the real check.
3. **The unscoped `/simulation-control/` route is reported, not repaired** — the
   owner has directed that the legacy route be deleted in a separate handoff,
   and I did not act on it here.

## Findings handed over (described, not numbered)

Finding IDs are allocated by the release-integration pass, so these are
described rather than numbered; full register-format text is in the inventory
document.

**1. The unscoped `/simulation-control/` reset and ownership gap (P1).**
`GameScopeGuardMiddleware` only covers routes whose pattern contains `game_id`,
so `POST /api/simulation-control/` and `POST /api/simulation-state/<pk>/advance/`
— keyed by `instance_id`/`pk` — are reachable by any instructor for any cohort,
and both call `round_engine.advance_round`, which takes no lock at all.
`SimulationControlView._reset` is **not scoped to its own instance**: only one
statement filters by `instance_id`, while `TRUNCATE … CASCADE` and unfiltered
updates to `simulation_state`, `rounds`, `team_performance` and `programs` hit
the whole deployment. **One judge resetting their heat would reset every
concurrent heat.** The guard test misses it because `route_inventory.uses_boundary`
is a *substring match* and `advance_round(` matches the unguarded
`round_engine` function rather than the guarded `advance_to_next_round`, so the
registry records `uses_boundary: true` on a false positive. Confirmed by the
coordinator; the owner has asked for the route to be **deleted** in a separate
handoff. Mitigating meanwhile: `controlSimulation` is exported in
`src/api/instructor.js:88` but called from nowhere in `src/`.

**2. `RoundControlCard` is untranslated (P2).** At baseline the primary
round-action surface had **no `t()` calls at all**; every string including all
five confirmations was hardcoded English, so a zh-CN judge drove the most
destructive controls in English. This stage routed its own new strings through
the catalogue; the remainder belongs to GSP-CRV2-12, whose Stage 1 inventory
should take this as an input rather than rediscovering it.

**Register correction still needed for V2-033.** The register records it as
"withdrawn, not a defect" and says "no code change alters that", while the
Stage 6 handoff says the repair is here. They reconcile only under the narrow
reading implemented — pilot preserved, competition reach refused — but the entry
is stale as written.

## Rules-owner questions (safest reversible defaults applied)

1. **Cap at enrolment or only at assignment?** *Applied:* both; enrolment caps
   at `max_teams × team_size_max` (40 by default).
2. **Does `team_size_min` refuse or warn?** *Applied:* reports, never refuses —
   a team is legitimately under-minimum while being filled.
3. **Teams already over cap?** *Applied:* grandfathered; new writes only, and
   `link_users_to_game` stays uncapped so an over-cap cohort can be repaired.
4. **Does `max_teams` count team rows or assigned teams?** *Applied:* active
   `Team` rows, excluding `withdrawn`.
5. **Minimum field size.** Ruling 4 says 6–8; I enforce only the upper bound.
   The lower bound stays 2 because `Section` has no authored `min_teams` and
   refusing a 4-team pilot game would be inventing a rule. One line if 6 binds.
6. **Should `User.team_id` be retired in favour of `Enrollment`?** Both capped
   meanwhile; retiring one is larger than Stage 6.

## Auditor preflight checklist

- **Inventory from registered routes/models/jobs?** Yes — `urls.py` + router,
  `route_inventory.json` and its generator, `game_scope.py`, the model registry
  and the physical DDL. That is how the third team-assignment surface and both
  uncovered lifecycle routes were found; grepping for the new helper would have
  found neither.
- **Active legacy or alternate entry point?** **Yes, three.**
  `instructor/advance-round/` (legacy, on the boundary — covered), and
  `simulation-control/` + `simulation-state/<pk>/advance/`, which are not on the
  boundary and are reported. Team assignment likewise had three entry points,
  all now capped.
- **Does a failure/refusal audit survive rollback?** **Yes, and now proven** —
  `test_the_refusal_is_recorded` asserts the row written after the rolled-back
  transaction, with the operator's own `request_id`.
- **Is each correlation ID generated once and identical across response/audit/
  log?** Yes — asserted equal between the response body and the audit row.
- **Is background/external work delayed until the outer transaction commits?**
  Not applicable; this stage adds no background or external work.
- **Do claimed environment values describe the executing process?** Yes —
  `flock`-serialised runs against a per-run disposable container; branch,
  revision and PID recorded at run start; production DB untouched.
- **Does provenance identify runtime bytes?** Yes, now — frozen at `f035884`
  on `e1b744c` plus the follow-up commit, no longer a bare working tree.
- **Do README commands run exactly as written?** The commands in the tables are
  reproduced verbatim from the shell.
- **Do P0/P1/P2 labels match their definitions?** Reset/ownership gap P1
  (cross-cohort destruction of live competition data); untranslated card P2
  (language quality, no integrity effect).
- **Does each negative test prove mutation/engine execution did not occur?**
  Yes — enrolment count unchanged, `team_id` still `None`, round still `open`,
  zero games created, team still at five members, audit row `after == {}`.

## Rollback

- **No migration, no schema change** — rollback is purely code.
- Revert the commit; the six edited files return to their pre-stage content and
  the three added modules disappear. Exactly this revert was performed and
  reversed during falsification (runs 5 and 6), so the path is proven both ways.
- **Relaxing enforcement without a deploy:** raise `Section.max_teams` /
  `team_size_max` on the affected section — the caps are authored data, which
  matters under RD-03.
- **Disabling the competition precondition without a deploy:** delete the
  `is_competition` key from that heat's `SimulationInstance.settings`.
