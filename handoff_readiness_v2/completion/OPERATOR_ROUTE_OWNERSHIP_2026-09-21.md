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
