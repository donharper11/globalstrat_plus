# Operator route ownership, roster faults, game delete — 2026-09-21

**Branch:** `crv2-08-operator-route-ownership` (from `crv2-release-integration`
at `f46d173`). **Claims no gate closed.** Nothing here touched production, the
production database or `/etc/globalstrat-plus.env`.

The three claims below came from CONSOLE_AND_ANALYST_LEFTOVERS_2026-09-21 §D3a,
which said of them: "a read-only source sweep by a sub-agent; I did not drive
any of them." Section 1 is what each returned when driven, **written before any
repair** (this section was committed with the red tests, ahead of the code).

## 1. Verified state at `f46d173`, before repair

Inventory was taken from `core/urls.py`, not from the claim. The cohort routes
that carry **no** `game_id` — and are therefore invisible to
`GameScopeGuardMiddleware`, which keys on `game_id` in the route — and that
declare only `IsInstructor` (role, nothing else) are:

| Route | Methods | View |
|---|---|---|
| `api/roster/` | GET POST PUT DELETE | `course.RosterViewSet` |
| `api/team-management/` | GET PUT | `course.TeamManagementView` |
| `api/courses/`, `api/courses/<pk>/`, `…/delete_preview/` | GET POST PUT PATCH DELETE | `course.CourseViewSet` |
| `api/sections/`, `api/sections/<pk>/` | GET POST PUT PATCH DELETE | `course.SectionViewSet` |

Fixture for every request below: instructor **owner** owns course `OWN`
(`Course.instructor_id = owner`), which has one section and one enrolled student
`ada`; instructor **rival** owns nothing in that course; both hold real signed
JWTs. Command: `scripts/test-postgres core.tests.test_operator_route_ownership`
— **41 tests, 29 failures, 1 error** at the unrepaired head (13 s wall).

### Claim 1 — `PUT roster/` has no ownership check: **TRUE, and wider than claimed**

| Request by **rival** | Response at `f46d173` |
|---|---|
| `PUT /api/roster/ {action:update, enrollment_id:<ada>, display_name:"Renamed By Request", email:"changed@example.edu"}` | **200** `{'display_name': 'Renamed By Request', 'email': 'changed@example.edu', …}` — the student row was rewritten |
| `DELETE /api/roster/?enrollment_id=<ada>` | **204** `{'detail': 'Enrollment removed.'}` |
| `POST /api/roster/ {action:add, section_id:<owner's>, student_id:"planted"}` | **201**, enrolment created in the owner's section |
| `POST /api/roster/ {action:upload, section_id:<owner's>, csv:…}` | **201** `{'created': 1, 'updated': 0, 'errors': []}` |
| `GET /api/roster/?section_id=<owner's>` | **200**, the other cohort's names and e-mail addresses |
| `PUT /api/team-management/ {action:rename, team_id:<owner's team>, team_name:"Defaced"}` | **200** `{'team_name': 'Defaced'}` |
| `PUT /api/team-management/ {action:assign, [{owner's student → owner's team}]}` | **200** `{'updated': 1}` |
| `PUT /api/team-management/ {action:assign, [{rival's own student → owner's team}]}` | **200** `{'updated': 1}` — a rival seats their own student on another cohort's firm |
| `GET /api/team-management/?section_id=<owner's>` | **200**, teams, members, e-mail |
| `DELETE /api/courses/<owner's>/` | **204** — the course is gone; the view's own comment says the database cascades sections, teams and game state |
| `PATCH /api/courses/<owner's>/ {instructor_id: <rival>}` | **200** — the rival is now the instructor of record, which then passes every `instructor_can_access_game` check for that cohort's games |
| `PATCH /api/sections/<owner's>/ {max_teams: 1}` | **200** |
| `POST /api/sections/ {course: <owner's>}` | **201** |
| `GET /api/courses/`, `GET /api/sections/` | list every cohort's courses and sections |

V2-033's rule also did not reach the roster: `POST roster/ add` against a section
flagged `is_competition` whose course has **no** instructor of record → **201**.
Every lifecycle action on that heat is refused `competition_course_unowned`; its
roster was open to any instructor account.

### Claim 2 — roster routes return `str(e)`: **TRUE, both sites**

`_find_or_create_user` forced to raise `RuntimeError('relation "users" violates
constraint users_email_key DETAIL: secret')`:

| Request by **owner** | Response at `f46d173` |
|---|---|
| `POST /api/roster/ {action:add,…}` | **400** `{'error': 'relation "users" violates constraint users_email_key DETAIL: secret'}` |
| `POST /api/roster/ {action:upload,…}` | **201** `{'created': 0, 'updated': 0, 'errors': [{'row': 2, 'error': 'relation "users" violates constraint users_email_key DETAIL: secret'}]}` |

Nothing was logged on either path (`assertLogs('core.views.course','ERROR')`:
"no logs … triggered"), so the text the client received was the only record.

### Claim 3 — `GameDeleteView` is outside the lifecycle boundary: **TRUE, with one sub-claim FALSE and one finding the sweep missed**

| Request | Response at `f46d173` |
|---|---|
| owner `DELETE /api/games/<id>/delete/` with no body, never-operated game | **200** `'Game "…" and all related data permanently deleted.'` — no reason asked, no lifecycle lock, no `OperatorAuditEvent`, no log line |
| owner, same, game flagged `is_competition` | **200**, heat deleted |
| admin, same, competition heat | **200**, heat deleted |
| **rival** instructor, competition heat whose course has no instructor of record | **200**, heat deleted — the one state in which every other lifecycle action answers `competition_course_unowned` |
| rival instructor, owned course | **403** `This game belongs to another instructor.` |
| owner, game that has any `OperatorAuditEvent` row | **500** `ProtectedError: Cannot delete some instances of model 'Game' because they are referenced through protected foreign keys: 'OperatorAuditEvent.game'` |

* **FALSE sub-claim:** "no competition-ownership check". The route names a
  `game_id`, so `GameScopeGuardMiddleware` already refuses another instructor's
  game with a 403 and an `AuthorizationRefusalEvent`. What was missing is the
  *unowned-competition* precondition, which lives inside `operator_action`.
* **Missed by the sweep:** the audit tables hold `PROTECT` foreign keys to
  `Game` and are append-only under database triggers, so a game that has *ever*
  passed through the boundary — including an attempt that was **refused**, which
  also writes a row — cannot be deleted by anyone. The console's "Delete
  forever" button answered every such game with an unexplained 500.
* **Route inventory:** `api/games/<int:game_id>/delete/|delete` was checked in
  as `lifecycle_mutating: false, uses_boundary: false`. The detector reads a
  view's own source, and the deletes live in the module-level helper
  `_delete_game_cascade`, so the route that removes a game's rounds, teams,
  submissions and events was recorded as not touching lifecycle state — the same
  blind spot V2-112 recorded for `create_game`. It was therefore never an
  "unguarded" offender and no test could have caught it.

### 1b. Found by the auditor-preflight question "is there an alternate entry point?" — **not in the sweep, verified before repair**

After the roster was closed I asked whether the same writes could still be made
some other way. Two generic DRF viewsets, registered on the router, name no
game and declare only a role: `teams/` (`TeamViewSet`, `IsInstructorOrReadOnly`,
`TeamSerializer fields='__all__'`) and `users/` (`UserViewSet`, `IsInstructor`,
`UserWriteSerializer` writing `username`, `password`, `role`, `team_id`). The
console writes through neither; no script in the repository does; the only
test that writes through either is `test_cohort_caps`' `users/<id>/assign-team/`
cap test. Driven at the head that already had the roster repair
(`AlternateEntryPointTests`, 12 tests, **9 failures**):

| Request by an **instructor** account | Response |
|---|---|
| `PATCH /api/users/<own id>/ {role:"admin"}` | **200** `{'role': 'admin'}` — an instructor makes themselves an administrator, after which every ownership rule in the product answers "admin: allowed" |
| `POST /api/users/ {username:"backdoor", role:"admin", password:…}` | **201** `{'role': 'admin'}` — or mints a fresh admin with a password they chose |
| `PATCH /api/users/<another instructor>/ {password:…}` | **200** — takes over a rival instructor's account |
| `PATCH /api/users/<another cohort's student>/ {password:…, username:"defaced"}` | **200** `{'username': 'defaced'}` — and can then log in as that student and submit their team's decisions |
| `POST /api/users/<another cohort's student>/assign-team/` | **200** |
| `POST /api/users/<own student>/assign-team/ {team_id:<rival's team>}` | **200** |
| `PATCH /api/teams/<any team>/ {cash_on_hand:"1.00", name:"Defaced"}` | **200** `{'name': 'Defaced', 'cash_on_hand': '1.00', …}` — a competitor's cash, equity, performance index and `participation_status` are writable by any instructor account, with no lock, no reason and no audit row |
| `POST /api/users/bulk-upload/` with a failing row | the row error is `str(e)` again, unlogged |

The first and the seventh are, in my judgement, **P0 for a multi-institution
competition**: one PATCH defeats every cohort boundary, and one PATCH rewrites a
rival firm's balance sheet. The route inventory did not flag `teams/` because
its detector reads a view's own source and a bare `ModelViewSet` has none.

## 2. What changed

Eight commits on `crv2-08-operator-route-ownership`, `b2c1c31..cc855f6`.

**Ownership of cohort routes (claim 1).** New `core/services/cohort_scope.py`
and `core.permissions.instructor_can_access_course / _section`. The rule is the
adopted one, asked of a course instead of a game: admin always; a course with no
`instructor_id` is the shared pilot cohort; otherwise its instructor of record.
Applied to `roster/` (GET, POST add, POST upload, PUT, DELETE),
`team-management/` (GET, PUT rename, PUT assign), `courses/` and `sections/`
(detail routes via `get_object`; create/move of a section under another
instructor's course; lists narrowed to owned-or-unowned). A refusal is **403**
(the status `GameScopeGuardMiddleware` uses for the same thing),
`{'error': <bilingual>, 'code': 'cohort_belongs_to_another_instructor',
'request_id'}`, and a refused *mutation* writes an `AuthorizationRefusalEvent`
through the middleware's own recorder with the same request id. One foreign item
refuses a whole `assign`, before anything is written. V2-033 now reaches cohort
membership: a write to the roster or teams of a section flagged `is_competition`
whose course has no instructor of record is **400
`competition_course_unowned`**, the existing code and sentence. Course and
section CRUD are deliberately *not* under that second rule — `PATCH courses/<id>/
{instructor_id}` is how the instructor of record gets assigned.

**Exception text (claim 2).** Both roster sites, and the third one found in
`users/bulk-upload/`, return a catalogue sentence in the caller's language with
a reference (the request id) and a `code` (`roster_add_failed`,
`roster_row_failed`, `account_row_failed`), and `logger.exception` the fault with
that reference. Status codes and response shapes are unchanged (400; per-row
entry inside the 201), plus the added `code`/`request_id` keys.

**Game delete (claim 3).** `GameDeleteView.delete` runs under
`@lifecycle_view` + `operator_action(request, game_id, 'delete_game')`:
lifecycle advisory lock, game row lock, the `competition_course_unowned`
precondition, and rejected-attempt auditing, exactly as archive and reset.
Inside it, in this order: a competition heat → **409
`competition_game_not_deletable`**; a game any append-only audit table refers to
→ **409 `game_has_record`** (was the 500); then `require_reason()` → 400
`reason_required`. Both 409s are bilingual and carry bilingual guidance to
archive instead — archiving is the existing convention for retiring a game and
it keeps every record, which is why I chose refusal over any softer delete. 409
rather than 400 by the boundary's own definition: "the state is terminal for
this action; nothing the operator types will change that." A `ProtectedError`
the pre-check did not anticipate is caught around a savepoint, logged, and
answered with the same 409, with the half-run cascade undone. A missing game is
now the boundary's 400 `No game N.` instead of a 404.

*What a committed deletion leaves behind.* Every refusal is an ordinary rejected
`OperatorAuditEvent`. A **committed** deletion cannot be one: that row holds a
`PROTECT` foreign key to the game it would say was deleted, and is itself
undeletable. It is written as a `WARNING` on the `core.lifecycle` logger — game
id and name, actor username and id, the reason, the prior state, and the
request id returned to the operator. See §6 item 1.

**Route inventory** (`manage.py dump_route_inventory`, twice, each deliberate):

| | before | after | why |
|---|---|---|---|
| `total_mutating_routes` | 219 | **215** | the four `teams/` write routes no longer exist |
| `lifecycle_mutating_routes` | 37 | **38** | `games/<id>/delete/` is now counted |
| `guarded` | 21 | **22** | …and guarded |
| `exempt` / `unguarded` | 16 / 0 | 16 / 0 | |

Two detector blind spots closed in `route_inventory.py`, both the same shape as
V2-112's `create_game`: `_delete_game_cascade(` is a write marker, and
`generic_lifecycle_writer()` flags a writable DRF model viewset whose model is a
lifecycle model (a bare `ModelViewSet` has no source of its own to read).

**Alternate entry points (§1b).** `TeamViewSet` is now a
`ReadOnlyModelViewSet`: removed rather than scoped, because a scoped version
would still let an instructor edit their own teams' cash behind the lifecycle
boundary, and every sanctioned team write already has a guarded route.
`UserViewSet` keeps its surface; for a non-admin caller the queryset is the
students `_visible_users_qs` allows (the rule the student-accounts screen
already used, so a foreign or staff account is a 404 as it is there), `role` may
only be Student on create/update/bulk upload (**403
`staff_account_admin_only`**, bilingual, recorded as an
`AuthorizationRefusalEvent`), and a team may only be assigned inside a cohort
the caller may access.

**Console.** `resetGame`, `archiveGame` and `deleteGame` carry a reason
(`DELETE` via axios `data`); the three Popconfirms (four call sites) became
`components/instructor/ReasonedAction.js`, which will not send until ten
characters are written and tells the instructor the reason is kept. Found on the
way: **reset and archive had posted an empty body since they joined the
boundary, so both buttons answered 400 `reason_required` on every click.**
`BILINGUAL_REFUSAL_CODES` gains four codes; a refused delete shows the server's
sentence plus its guidance. `delete_confirm` now says what can be deleted. Every
other console call to a route touched here was checked against
`api/instructor.js` and its call site: request shapes are unchanged, success
shapes are unchanged, and the new refusals arrive in the `error` key those catch
blocks already read.

## 3. Red, then green

| Repair | Red (before the change) | Green |
|---|---|---|
| Claims 1–3 | `test_operator_route_ownership`: **41 tests, 29 F + 1 E** at `b2c1c31` | 43/43 after `58e6bd9` |
| Claim 2, bodies | `RosterFaultTests` re-cut so the leak shows in the message: 6/6 F, e.g. `400 {'error': 'relation "users" violates constraint users_email_key DETAIL: secret'}` | 6/6 |
| Delete in the inventory | detector change alone, view untouched: `RouteCoverageTests` 2 F — `test_no_registered_route_mutates_lifecycle_state_unguarded` names `api/games/<int:game_id>/delete/` | 4/4 |
| Console reason | `reasonedActions.test.js`: 3 F of 4 (`Expected: "/games/7/delete/", {"data": {"reason": …}} Received: "/games/7/delete/"`; `Expected: 4 Received: 0` reasoned call sites) | 4/4 |
| Alternate entry points | `AlternateEntryPointTests` at `3c43605`: **9 F of 12** | 12/12 after `6b7972f` |
| `teams/` in the inventory | new detector with `TeamViewSet` put back to `ModelViewSet`: 2 F, four `api/^teams/…` routes named unguarded | green with the read-only viewset |
| A defect in my own repair | `test_every_refused_course_or_section_write_leaves_a_record`: `['DELETE', 'PATCH'] != ['DELETE', 'PATCH', 'POST']` — `perform_create` refused inside its own atomic block and rolled back the refusal record | green after `07e6662` |

Not red-first, and said so: `test_a_protected_row_the_precheck_missed_undoes_the_whole_cascade`
guards code I had already written; `ConsoleReasonContractTests` and
`test_a_rival_is_refused_by_the_game_scope_guard` are characterisations of
behaviour that was already correct.

Every negative test asserts the write did not happen (row re-read, counts, the
planted user absent), not only the status code.

## 4. Commands, results, durations

All backend runs: `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock
scripts/test-postgres <labels>` — a disposable `postgres:16-alpine` container per
run, random password, never the production database.

| Command | Result | Wall |
|---|---|---|
| `… core.tests.test_operator_route_ownership` (unrepaired) | 41 run, 29 F, 1 E | 13 s |
| `… test_operator_route_ownership test_cohort_caps test_operator_concurrency test_audit_integrity test_console_defects test_player_language_guard test_crv2_12_language` (after claims 1–3) | **199 OK** | 293 s incl. lock wait; 166 s test time |
| `… test_operator_route_ownership test_user_endpoint test_cohort_caps` (after §1b repair) | **95 OK** | — |
| `… core.tests.test_operator_route_ownership` (frozen code) | **62 OK** | 3.5 s test time |
| `… core --parallel 8` — **once**, at the frozen commit `07e6662` | **1275 OK** | 112 s |
| `… test_player_language_guard test_crv2_12_language` (after the inventory commit) | 22 OK | — |
| `CI=true npx react-scripts test --watchAll=false` | **16 suites, 98 tests passed** | 3–6 s |
| `npx eslint -c node_modules/eslint-config-react-app/index.js <5 changed files>` | 0 errors; 6 warnings, all pre-existing unused names in `InstructorDashboard.js` | |
| `python3 backend/scripts/check-participant-strings` | PASS, 4697 units, 0 findings | |
| `generate_inventory.py --check` | stale after the code → regenerated in its own commit `cc855f6` → current | |
| `manage.py dump_route_inventory --check` equivalent (`test_inventory_matches_the_checked_in_copy`) | green in the full run | |

The frontend suite ran with `node_modules` symlinked from the main checkout
(identical `package.json`; the link is git-ignored and not committed). No
runtime code changed after the full run; `cc855f6` is generated evidence only.

Auditor preflight, applicable items. *Inventory from registered routes:* yes,
`urls.py` and the router, plus a probe of every writable viewset's model.
*Alternate entry point:* asked, found two, §1b. *Refusal audit survives
rollback:* tested, and it caught one of mine. *One correlation id:*
`request_id_for` throughout; tests compare the response's id with the row's.
*Negative tests prove no mutation:* yes.

## 5. Proposed register text (for the auditor to apply or reject)

**New row — cohort routes without a game id. Proposed P0 (competition), P1 (pilot).**
> **Repaired, pending closure.** `roster/`, `team-management/`, `courses/` and
> `sections/` name no game, so the game-scope boundary (V2-034) never saw them,
> and `IsInstructor` checks a role only. Driven with two instructor JWTs at
> `f46d173`: the second instructor renamed, removed and planted students in the
> first's section, seated their own student on the first's team, renamed the
> team, deleted the course, and PATCHed themselves in as its instructor of
> record. `90e8540`/`07e6662`: one helper applies the adopted ownership rule —
> 403, bilingual, request id, `AuthorizationRefusalEvent` on a refused write;
> V2-033 extended to the roster of an unowned competition section. **Residual,
> owner:** the console creates courses with no `instructor_id`, so a course is
> shared with every instructor until an admin assigns one (§6 item 3).

**New row — generic `users/` and `teams/` viewsets. Proposed P0.**
> **Repaired, pending closure.** Any instructor account could
> `PATCH /api/users/<self>/ {role:"admin"}`, create an admin with a chosen
> password, set another instructor's or another cohort's student's password,
> and `PATCH /api/teams/<id>/ {cash_on_hand}` on any team, unaudited. None was
> in any prior inventory; the route inventory's detector could not see a bare
> model viewset. `6b7972f`: `teams/` read-only; `users/` scoped to the caller's
> students, role fixed to Student for non-admins, attempts recorded; detector
> extended. **Not established:** whether either was ever used against the
> production database (§6 item 4).

**New row — roster/account exception text. Proposed P2.**
> **Repaired, pending closure.** Three sites returned `str(e)` (roster add,
> roster CSV row, account bulk-upload row) and logged nothing. Now a bilingual
> sentence with a reference, and `logger.exception`.

**New row — game delete outside the lifecycle boundary. Proposed P1.**
> **Repaired, pending closure.** `DELETE games/<id>/delete/` took no lock, asked
> no reason, left no record, deleted competition heats (for any instructor when
> the heat's course was unowned), answered 500 `ProtectedError` for any game
> with an audit row, and was checked in as `lifecycle_mutating: false`.
> `58e6bd9`: an operator action; heats and games with a record are refused 409
> toward archive; inventory 37→38 lifecycle-mutating, 21→22 guarded. The
> sweep's sub-claim "no competition-ownership check" was false — the game-scope
> boundary already covered the route. **Open, owner:** a committed deletion is a
> log line, not an audit-table row (§6 item 1).

**New row — console reset/archive never worked. Proposed P1.**
> **Repaired, pending closure.** `resetGame`/`archiveGame` posted an empty body
> to routes that require a written reason; both buttons answered 400 on every
> click. `fa23936`: a reason modal on reset, archive and delete. Unobserved in a
> browser (§6 item 2).

## 6. What a reviewer should distrust

Only what I could not settle from here.

1. **A committed game deletion is recorded in the process log, not in an audit
   table** — *owner / schema decision.* `OperatorAuditEvent.game` is `PROTECT`
   and the table is append-only, so a row about a deletion would forbid the
   deletion. A durable, chained record needs a new table with no foreign key to
   the game, registered in `audit_guards.PROTECTED_TABLES` and
   `audit_chain.PROJECTIONS` — a change to certified audit machinery that I did
   not make unasked. In the repository, `LOGGING` sends everything to the
   console handler, which under systemd is the journal; **what the production
   host's journal retains, and for how long, I cannot see.** What is deletable
   at all is narrow: a non-competition game that no audit table refers to.
   A corollary the owner should know: because *refused* actions are audited too,
   one refused click (including a delete sent without a reason by an old client)
   makes a game permanently undeletable. That is the audit design working, and
   the refusal says "archive instead", but it is a behaviour someone should
   choose rather than inherit.
2. **Nothing was seen in a browser** — *needs a human.* `ReasonedAction` is
   rendered for real by Jest; `InstructorDashboard` is rendered by no test, so
   the four replaced buttons, the modal's placement and the delete refusal toast
   are proven by a source scan and the component's own test.
3. **The ownership rule only bites where a course has an instructor of record**
   — *owner ruling.* That is the adopted pilot rule and I preserved it. But the
   console's "create course" sends no `instructor_id`, so every console-created
   course is unowned and therefore shared with every instructor account. Whether
   a new course should be owned by its creator changes the pilot rule's reach
   and is not mine to decide. Competition heats are covered regardless: an
   unowned competition course is refused at the lifecycle boundary and now at
   the roster.
4. **Whether the §1b holes were ever used** — *needs the production host.* Look
   for instructor-token `PATCH|POST|PUT|DELETE` on `/api/users/` and
   `/api/teams/` in the access log, and for `role='admin'` rows nobody
   provisioned. I did not and may not query production.
5. **Eleven zh-CN sentences are mine and unreviewed by a native reader** —
   *needs a human:* the nine new `cohort_messages` entries and the two new
   locale keys (plus the reworded `delete_confirm`). They follow the existing
   backend vocabulary (比赛场次 for a competition game); the frontend's 游戏 vs
   the backend's 比赛 (LEFTOVERS D4) is untouched.

## 7. Inventoried, out of scope, not driven

The same probe that cleared "no writable viewset sits on a lifecycle model"
lists these writable generic viewsets behind `IsInstructor` with no cohort
scope: `grading.{GradingRubric, GradingRubricCategory, GradingComponentMapping,
TeamGrade, StudentGradeAdjustment}ViewSet` and `instructor.{InstructorAction,
InstructorEvaluation, InstructorNote, InstructorFeedbackTemplate,
InstructorScenarioCustomization}ViewSet`. By reading, another instructor's
grades and notes are writable the same way the roster was. They are grading,
not cohort membership or competitive state, several sit on BECSR-era models that
may have no table (STANDING-DISCIPLINE §1.8), and I did not drive any of them.
LEFTOVERS D3a's other two items — `Section` accepting `max_teams: 9999`, and
500s on a non-numeric id — were not part of this assignment; the ownership
helper itself does not 500 on a non-numeric id (`section_for_id` absorbs it),
the views' own lookups after it still can.

