# GSP-CRV2-10 Stage 6 — cohort cap and concurrent-game inventory

**Baseline revision:** `cbe2656` (branch `crv2-10-stage6-cohort-caps`, isolated worktree)
**Built:** 2026-09-12, before any implementation (EXECUTION_PROTOCOL Phase 1)
**Findings owned:** V2-042 (P1, open), V2-033 (competition reach)
**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoffs/EXECUTION_PROTOCOL.md`

## Method

Built from the authoritative registries, not by grepping for the helper that
correct code is expected to call:

- `backend/core/urls.py` — 137 `path()` entries plus the DRF `DefaultRouter`
  (`router.register` × 40), read in full.
- `core/services/route_inventory.json` — the checked-in mutating-route registry
  (219 mutating routes, 36 lifecycle-mutating), and its generator
  `core/services/route_inventory.py`.
- `core/services/game_scope.py` — the game-scoped instructor route inventory,
  built from registered URL patterns; `EXEMPTIONS` is empty `{}`.
- Django model registry — `core/models/course.py`, `core/models/core.py`,
  plus `scripts/bootstrap/unmanaged_tables_schema.sql` for the physical DDL of
  the `managed = False` tables.

## Verify-before-wire results (STANDING-DISCIPLINE §1)

Recorded because each one changes what the implementation may assume.

| # | Spec/task said | Codebase shows | Disposition |
|---|---|---|---|
| V1 | `CourseSection.max_teams` | Model class is **`Section`** (`core/models/course.py:22`), `db_table='section'`. No class named `CourseSection` exists. | Spec shorthand. A6 cites `core/models/course.py:30-32`, which matches `Section` exactly. Proceeding against `Section`; **not** creating a new model (§2). |
| V2 | — | `Course`, `Section`, `SimulationInstance`, `Enrollment` are all **`managed = False`**. Django migrations neither create nor alter them. | Any schema change to these is a hand-written DDL change to `scripts/bootstrap/unmanaged_tables_schema.sql` + a production migration outside the ORM. Avoided entirely. |
| V3 | — | `Game` is **managed** (`db_table='game'`, absent from the unmanaged DDL). Migration head is `0084_product_level_demand`. | A `Game` field would be an ordinary reversible migration `0085_*`. Proposed, not applied — see "Competition flag". |
| V4 | "verify whether a competition-game flag exists" | **It does not.** No `is_competition`/`mode`/`tournament` field on `Game`, `Section`, `Course` or `Scenario`; no such settings key. `COMPETITION_*` settings exist but are all deployment-global booleans, not per-game. | Least-invasive option chosen below; schema option proposed for ruling. |
| V5 | — | `simulation_instance.settings` is a **real `jsonb` column** in the DDL (not a ghost field, §1.8). | Usable as a per-heat flag with **zero migration**. |
| V6 | caps "read only by a serializer field list" | Confirmed. Only reader is `SectionDetailSerializer.Meta.fields` (`core/serializers/course.py:57-59`), which is `read_only_fields = fields`. Everything else is test fixtures. | Confirms A6/V2-042: nothing enforces them. |

## A. Surfaces that create an enrolment

Authoritative membership row: `Enrollment` (`enrollment` table).

| # | Entry point | Registry source | Callable | Disposition |
|---|---|---|---|---|
| A1 | `POST /api/roster/` `{action:"upload"}` | `urls.py:260` | `course.RosterViewSet._handle_csv_upload` (`course.py:328`) | **CHANGED** — section capacity enforced per row |
| A2 | `POST /api/roster/` `{action:"add"}` | `urls.py:260` | `course.RosterViewSet._handle_add_single` (`course.py:379`) | **CHANGED** — section capacity enforced |
| A3 | `PUT /api/roster/` `{action:"update"}` | `urls.py:260` | `course.RosterViewSet.put` (`course.py:204`) | **EXEMPT** — writes `User.display_name/email/student_id` only. Creates no enrolment and sets no `team_id`; cannot increase occupancy. |
| A4 | `DELETE /api/roster/` | `urls.py:260` | `course.RosterViewSet.delete` (`course.py:252`) | **EXEMPT** — removes an enrolment. Strictly decreases occupancy. |
| A5 | `manage.py load_demo` | model registry | `load_demo.py:327` | **EXEMPT** — demo seed fixture, not a competition surface. Documented, not enforced, so a demo cohort of any shape still loads. |
| A6 | `manage.py setup_test_game` | model registry | `setup_test_game.py:188` | **EXEMPT** — test fixture, same rationale. |
| A7 | `manage.py run_deadline_rehearsal` | model registry | `run_deadline_rehearsal.py:82` | **EXEMPT** — rehearsal harness, same rationale. |
| A8 | `POST /api/users/bulk-upload/` | router `users` | `core.UserViewSet.bulk_upload` (`core.py:49`) | **CHANGED** — creates `User` rows carrying an arbitrary CSV `team_id` with no cap. See structural note S1. |

## B. Surfaces that assign a team — **three, not one**

This is the most consequential result of the inventory.

| # | Entry point | Callable | Writes | Disposition |
|---|---|---|---|---|
| B1 | `PUT /api/team-management/` `{action:"assign"}` | `course.TeamManagementView._handle_assign` (`course.py:623`) | `Enrollment.team_id` | **CHANGED** — `team_size_max` enforced; `team_size_min` reported |
| B2 | `POST /api/users/<pk>/assign-team/` | `core.UserViewSet.assign_team` (`core.py:98-116`) | `User.team_id` **only** | **CHANGED** — same cap, or the cap does not exist |
| B3 | `POST /api/users/bulk-upload/` | `core.UserViewSet.bulk_upload` (`core.py:85`) | `User.team_id` from CSV | **CHANGED** — same cap |
| B4 | `manage.py link_users_to_game` | `link_users_to_game.py:122` | re-syncs both | **EXEMPT** — repair tool whose whole purpose is reconciling B1 against B2/B3. Capping it would block the fix for an already-over-cap cohort. |
| B5 | `TeamMember` model (`team_member` table) | `core/models/core.py:98` | — | **EXEMPT — no production writer.** The only writer in the tree is `test_team_participation_control.py:53`. Read by `middleware._is_team_member`. Not a live membership representation; recorded so a future writer is a deliberate act. |

### S1 — structural note: two live membership representations

`Enrollment.team_id` is authoritative (`results_api.py:585-587`: *"Get team members
from Enrollment (the real source of truth)"*), but `User.team_id` is written
independently by B2/B3 and never synced back. `link_users_to_game.py` exists
precisely because they drift ("Fixes the recurring issue where `User.team_id`,
`Enrollment.team_id` ... "). **Enforcing `team_size_max` on only one is the A6
defect in a new place: two caps that disagree is one cap that does not exist.**
Enforcement therefore counts occupancy as the union of both representations.

## C. Surfaces that create a game / decide team count

| # | Entry point | Callable | Current cap | Disposition |
|---|---|---|---|---|
| C1 | `POST /api/games/create/` | `scenario_views.GameCreateView.post` (`scenario_views.py:237`, teams created at `:326`) | `2 <= num_teams <= 16` — unrelated to the section | **CHANGED** — binds to the section's `max_teams`; reconciles the two disagreeing caps |
| C2 | `manage.py initialize_game` | `initialize_game.py:62,124` | `--teams`, no cap; creates no `section_id` | **EXEMPT** — operator bootstrap command that creates a game with no section, so no section cap is in scope. Recorded so it is a deliberate hole, not an unnoticed one. |

## D. Instructor routes that act on a round

All rows below already pass the `operator_action` lifecycle boundary unless
noted. Disposition here is about **game identity in the confirmation**
(scope item 4), not about locking.

| # | Route | Callable | Boundary | Disposition |
|---|---|---|---|---|
| D1 | `POST …/round-control/close/` | `round_control.RoundCloseView` | `close_round` | **CHANGED** — response names the game |
| D2 | `POST …/round-control/reopen/` | `RoundReopenView` | `reopen_round` | **CHANGED** |
| D3 | `POST …/round-control/process/` | `RoundProcessView` | `process_round` | **CHANGED** |
| D4 | `POST …/round-control/advance/` | `RoundAdvanceView` | `advance_round` | **CHANGED** |
| D5 | `POST …/round-control/deadline/` | `RoundDeadlineView` | `set_deadline` | **CHANGED** |
| D6 | `POST …/instructor/advance-round/` | `results_api.InstructorAdvanceRoundView` | `advance_round_legacy` | **CHANGED** — *alternate entry point*, self-described "legacy one-step route" |
| D7 | `POST …/instructor/extend-deadline/` | `results_api.InstructorExtendDeadlineView` | `extend_deadline` | **CHANGED** |
| D8 | `POST …/instructor/inject-event/` | `results_api.InstructorInjectEventView` | `inject_event` | **COVERED** — competition precondition applies; not a round-state confirmation |
| D9 | `POST …/instructor/inject-sc-event/` | `instructor_sc` | `inject_sc_event` | **COVERED** |
| D10 | `POST …/activate/`,`/pause/`,`/resume/`,`/reset/`,`/archive/` | `scenario_views` | `*_game` | **COVERED** — game-lifecycle, already named by game id in payload |
| D11 | `POST …/round-schedule/` | `course.GameRoundScheduleView.post` | `set_round_schedule` | **COVERED** |
| D12 | `POST /api/simulation-control/` | `course.SimulationControlView` | **NONE** | **NOT COVERED — see F1.** Keyed by `instance_id`, not `game_id`. |
| D13 | `POST /api/simulation-state/<pk>/advance/` | `core.SimulationStateViewSet.advance` (`core.py:135`) | **NONE** | **NOT COVERED — see F1.** Calls `round_engine.advance_round` directly. |

## E. Ownership chain and `instructor_can_access_game`

Chain: `Game.section_id` → `Section.course_id` → `Course.instructor_id`.
Both link directions are unreliable alone — `_game_ids_for_section`
(`course.py:461-483`) documents that the pilot section sets both
`SimulationInstance.game_id` and `Game.section_id` while the demo section sets
only the former. Resolution must try both.

Every caller of `instructor_can_access_game`:

| # | Caller | Disposition |
|---|---|---|
| E1 | `core/permissions.py:47` (definition) | **UNCHANGED** — the single definition of the ownership rule stays as-is, including the unowned-pilot branch |
| E2 | `core/middleware.py:329,333` (`GameScopeGuardMiddleware`) | **UNCHANGED** |
| E3 | `core/views/results_api.py:552,562` | **UNCHANGED** |
| E4 | `core/views/results_api.py:1007,1013` | **UNCHANGED** |
| E5 | `core/views/round_control.py:26,147` | **UNCHANGED** |
| E6 | `test_game_scope_boundary.py:124` — the two-route pin on unowned-course access | **MUST STILL PASS** — pilot behaviour preserved |

**V2-033 disposition.** The repair is a *competition precondition on the game*,
not a change to `instructor_can_access_game`. A non-competition game keeps the
unowned-pilot behaviour exactly, so E6 continues to pass; a competition game on
a course with `instructor_id IS NULL` is refused before it can be opened or
acted on. This is deliberate: narrowing the helper would break the pilot, which
is what the CRV2-08 auditor ruled must not happen.

> **Register conflict to hand to the rules owner.** `V2_FINDINGS_REGISTER.md:909`
> records V2-033 as *"withdrawn, not a defect"* and states *"no code change
> alters that"*. The Stage 6 handoff states *"This handoff owns V2-033 … **The
> repair is here**"*. These reconcile only under the narrow reading adopted
> here (pilot preserved, competition reach refused), but the register entry is
> stale as written. I am barred from editing the register; this needs the
> owner's amendment.

## Competition flag — options, and the one chosen

No flag exists (V4). Options considered:

| Option | Schema cost | Per-heat? | Verdict |
|---|---|---|---|
| O1 `Game.is_competition` boolean | migration `0085_game_is_competition.py`, reversible, default `False` | yes | **Proposed for ruling** — cleanest and most durable, but a schema change I was told not to invent silently |
| O2 `SimulationInstance.settings['is_competition']` | **none** — column already exists (V5) | yes (per section→game) | **CHOSEN** — least invasive, data-driven, reversible by deleting a key |
| O3 Global `COMPETITION_*` env setting | none | **no** | **Rejected** — cannot distinguish concurrent heats on one deployment, which is the entire premise of Stage 6 |

O2 is read through **one** helper so that adopting O1 later is a one-line change
and never produces two flags that disagree.

Migration I would write for O1, if ruled:

```python
# core/migrations/0085_game_is_competition.py
operations = [
    migrations.AddField(
        model_name='game',
        name='is_competition',
        field=models.BooleanField(default=False, help_text=(
            'Competition heat: requires an owned course and refuses '
            'cross-cohort instructor access.')),
    ),
]
```

## F. New findings (register format — for the owner to file; I must not edit the register)

### F1 — V2-056 — round-advancing routes keyed by `instance_id` escape the ownership boundary, and one of them resets every concurrent heat (P1) — new, open

`GameScopeGuardMiddleware` only covers routes whose pattern contains `game_id`
(`game_scope.py`: `if 'game_id' not in route: continue`). Two registered
lifecycle routes are keyed by `instance_id`/`pk` instead and are therefore
reachable by **any** authenticated instructor for **any** cohort:

- `POST /api/simulation-control/` (`course.SimulationControlView`, `IsInstructor`)
- `POST /api/simulation-state/<pk>/advance/` (`core.SimulationStateViewSet.advance`)

Both call `core.services.round_engine.advance_round`, which takes **no lock at
all** — `round_engine.py` contains no `operator_action`, no
`lock_game_for_lifecycle` and no `select_for_update`.

Worse, `SimulationControlView._reset` (`course.py:861-1026`) is **not scoped to
the instance it is called for**. Only step 7 filters by `instance_id`. Every
other statement is deployment-wide:

- `TRUNCATE TABLE "<t>" CASCADE` for all of `FULL_TRUNCATE_TABLES`
- `UPDATE simulation_state SET current_round_id = 1, status='active'` — no filter
- `UPDATE rounds SET status='pending' …` then `status='active' WHERE round_number=1` — no game filter
- `UPDATE team_performance SET total_score = 0 …` — no filter
- `DELETE FROM programs WHERE round_launched != 11` — no filter

**On the one-deployment, several-heats competition this stage exists to make
safe, one judge resetting their own heat silently resets every other heat mid-
competition.** Mitigating: `controlSimulation` is exported in
`frontend/src/api/instructor.js:88` but is called from nowhere in `src/`, so it
is not reachable from the current UI — it is an open API route, not a button.

**Why the existing guard test did not catch it.** `route_inventory.py` computes
`uses_boundary` as a *substring match on view source* against `_BOUNDARY_MARKERS`,
which includes `'advance_round('`. `SimulationControlView` contains the literal
text `advance_round(state.state_id)` — the unguarded `round_engine` function,
not the guarded `advance_to_next_round`. The registry therefore records
`"uses_boundary": true` for that route on a false positive, `unguarded_routes()`
trusts it, and `RouteCoverageTests.test_no_registered_route_mutates_lifecycle_
state_unguarded` passes with `unguarded: 0`. A marker list matched by substring
cannot tell two same-named functions apart.

*Not repaired in this stage* — it is outside Stage 6's five scope items and the
repair (scoping `_reset`, and either retiring or guarding these routes) changes
lifecycle behaviour that CRV2-02's concurrency evidence covers. Raised for the
owner.

### F2 — V2-057 — `RoundControlCard` is entirely untranslated (P2) — new, open

`frontend/src/components/RoundControlCard.js` is the primary round-action
surface (close / process / advance / reopen / deadline) and contains **no `t()`
calls at all** — every string, including all five confirmations, is hardcoded
English. A zh-CN judge drives the competition's most destructive controls in
English. Stage 6 routes its own new strings through the catalogue; converting
the rest belongs to GSP-CRV2-12, whose Stage 1 inventory should take this row
as an input rather than rediscovering it.

## G. Rules-owner questions

Each has a safest-reversible default applied meanwhile; each is reversible by
changing one constant or one branch.

1. **Does the cap bind at enrolment, or only at team assignment?**
   *Default applied:* it binds at both. Enrolment is capped at the section's
   seat capacity, `max_teams × team_size_max` (8 × 5 = 40 by default).
   *Why this default:* refusing at enrolment is recoverable (the instructor
   removes a row or raises the cap); discovering at assignment that 41 students
   cannot be seated is not.
2. **Does `team_size_min` refuse or warn at assignment?**
   *Default applied:* it **reports, never refuses.* A team is legitimately
   below minimum for the entire period it is being filled, so refusing would
   make normal roster-building impossible. The response carries an
   `under_minimum` list so the console can show it.
3. **What happens to teams already over cap in an existing game?**
   *Default applied:* grandfathered. Enforcement binds new writes only; no
   existing row is removed or rejected retroactively, and B4 stays uncapped so
   an over-cap cohort can still be repaired.
4. **Does `max_teams` count `Team` rows in the game, or distinct assigned teams
   in the section?** *Default applied:* `Team` rows in the game, excluding
   `participation_status='withdrawn'` — a withdrawn team is not in the
   competitive field and should not consume a slot.
5. **Should `User.team_id` (B2/B3) be retired in favour of `Enrollment`?**
   Not decided here. Both are capped meanwhile (S1). Retiring one would be the
   real fix and is a larger change than Stage 6 owns.

## H. Coverage summary

| Category | Rows | Changed | Covered | Exempt |
|---|---:|---:|---:|---:|
| A. Enrolment creation | 8 | 3 | 0 | 5 |
| B. Team assignment | 5 | 3 | 0 | 2 |
| C. Game creation | 2 | 1 | 0 | 1 |
| D. Round-acting instructor routes | 13 | 7 | 4 | 0 (2 not covered → F1) |
| E. Ownership callers | 6 | 0 | 6 | 0 |

Every exemption above carries a testable rationale. The two uncovered rows
(D12, D13) are raised as F1 rather than silently exempted.
