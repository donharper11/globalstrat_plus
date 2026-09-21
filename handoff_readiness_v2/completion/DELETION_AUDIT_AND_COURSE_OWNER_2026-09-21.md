# Deletion audit record (R45) and course creator owns (R46) — 2026-09-21

**Branch:** `crv2-08-deletion-audit-and-course-owner`, from
`crv2-release-integration` at `ba6a1c7` (verified an ancestor before any work).
**Claims no gate closed.** Nothing here touched production, the production
database, `/etc/globalstrat-plus.env` or systemd. Every database this work
spoke to was a disposable PostgreSQL 16 container on `127.0.0.1`.

| Commit | What |
|---|---|
| `ab266de` | R46: the creator is the instructor of record; tests |
| `05213e3` | R45: the deletion record, every registration, migration `0088`, tests, inventories, docs. First freeze |
| `bbfaa4b` | Test-only: a participation fixture that depended on sequence positions (section 6). Certified freeze |
| after | this report; then the string inventory, in its own commit, last |

Specification: owner rulings R45 and R46 (`OWNER_RULINGS_2026-09-21.md`), with
R44 (audit rows are English only).

## 1. State at head, before the change

Driven, not read — this is the red run in section 5.

**R45.** `DELETE /api/games/<id>/delete/` on a never-operated game answered 200
and left a `core.lifecycle` WARNING line and nothing else. There was no table a
committed deletion could be written to: `OperatorAuditEvent.game` is
`on_delete=PROTECT`, so the row would have refused the deletion it described.

**R46.** `POST /api/courses/` with the body the console sends
(`course_code`, `course_name`, `is_active`) created a course with
`instructor_id = NULL`. A second instructor then read it (200), changed its
section's `max_teams` (200) and could do everything else V2-133 refuses on an
owned course, because an unowned course is the shared pilot cohort. The
serializer is `fields='__all__'`, so an instructor could also *name* any
`instructor_id`, including another instructor's or none.

**Course-creation paths, from the registry and a source sweep:**

| Path | Actor | Disposition |
|---|---|---|
| `POST api/courses/` (`CourseViewSet`, the only route; the console's `createCourse` calls it with no `instructor_id`) | instructor or admin | **Changed** |
| `manage.py load_demo` | host operator | Already sets `instructor_id` to its demo instructor on create and on re-run. Unchanged |
| `manage.py setup_test_game` | host operator | Same. Unchanged |
| `manage.py run_deadline_rehearsal` | host operator | Creates its own rehearsal instructor and names it. Unchanged |
| `handoff_readiness_v2/evidence/*/harness/seed_*.py` | none (ORM seeders) | Evidence of their own named commits; no request actor exists. Unchanged |

No frontend change was needed: the console already sends no `instructor_id`,
and the rule is applied server-side where it cannot be bypassed.

**Game-deletion paths** (auditor preflight: "is there an alternate entry
point?"): `GameDeleteView` is the only operator route. `_delete_game_cascade`
has one caller. Course deletion does not reach a game: `game.section_id` is a
plain integer in a managed table (migration `0001`) and
`scripts/bootstrap/unmanaged_tables_schema.sql` holds no key from `game` to
`section`. `manage.py setup_test_game` bulk-deletes games named "Test Game" on
the host; it is a development fixture command with no request, no operator and
no reason, and it is stopped by the same PROTECT keys as soon as such a game has
any record. It was left alone.

## 2. Design, and why

### R45 — `GameDeletionAuditEvent` / `competition_game_deletion_audit_event`

| Column | Carries |
|---|---|
| `game_id_deleted` (bigint), `game_name` | the game, as plain values |
| `scenario_id_value` (bigint, null), `scenario_name` | the scenario, as plain values |
| `actor_user_id`, `username` | the actor, as plain values |
| `action` | `'delete_game'`, the same action name the refused attempts carry in `OperatorAuditEvent` |
| `reason` | the operator's written reason (at least 10 characters, enforced by `require_reason`) |
| `before` | the `_game_state` snapshot: `game_id`, `name`, `status`, `current_round` |
| `request_id` | the id in the operator's response — `action.request_id`, resolved once per request |
| `created_at` | server time |

* **No foreign key to anything**, asserted two ways: no relation field on the
  model, and no `contype='f'` row in `pg_constraint` for the table.
* **Same transaction.** The row is written inside `operator_action`'s
  `transaction.atomic()`, after the cascade's savepoint has succeeded and before
  the response. A failed write raises out of the block and the deletion rolls
  back; anything failing after the write rolls the row back with the deletion.
  There is deliberately no `except` around it (`competition_audit.py` is
  "fail-closed" by its own docstring).
* **Only committed deletions.** A refused deletion leaves the game in place, so
  it stays a rejected `OperatorAuditEvent` exactly as before.
* **English only** (R44). Nothing in the row depends on `Accept-Language`.
* **Sealed after commit**, never inside the write, by the same
  `_schedule_seal()` every audit row uses — the seal takes a global advisory
  lock and this write sits under the lifecycle locks GSP-CRV2-02 certified. A
  rolled-back deletion discards the callback with the row.
* **Log line kept**, unchanged.
* **Read back** through the read-only Django admin (search by request id, game
  name, actor, reason). The game is gone, so there is no game-scoped API route
  it could hang from, and none was added — the read inventory is unchanged.

### R46

`CourseViewSet.perform_create`: a non-admin caller's course gets
`instructor_id = <caller>`, whatever the body carried; an admin's body is
honoured as sent, and no `instructor_id` means unowned. Update paths are not
touched, and no stored course is reassigned.

Two decisions worth stating:

* An instructor who *names* someone else (or `null`) is not refused; the value
  is replaced and the 201 body shows the real owner. The ruling is
  unconditional ("has that instructor as its instructor of record from the
  moment it exists"), and a refusal would have needed a new bilingual sentence
  and code for a body the console never sends.
* The owner is set on `serializer.validated_data` and handed to DRF's own
  `perform_create`, rather than the usual `serializer.save(instructor_id=…)`.
  The route inventory reads a view class's source, and a `.save(` call in the
  same class as `delete_preview`'s `Team.objects` count matches its "re-saves a
  lifecycle row" heuristic: the first version of this change flagged all four
  `courses` routes as unguarded lifecycle writers. A course row is not
  lifecycle state, so the honest alternatives were this or an exemption that
  would have blinded the detector to those routes for good. The comment in the
  code says the same.

An admin may name any integer as `instructor_id`; it is not validated against
the instructor accounts. That is the pre-existing behaviour of create and update
alike, R46 does not speak to it, and the failure mode is a course only admins
can open, which an admin repairs with a PATCH.

## 3. Every place the new table was registered

| Where | What |
|---|---|
| `core/models/audit_integrity.py`, `core/models/__init__.py` | The model; `save()` refuses a re-save and schedules the seal |
| `core/migrations/0088_game_deletion_audit_event.py` | **One migration**: `CreateModel` then `RunPython(install_guards, remove_guards)`. Table and triggers arrive together — 0078 created the refusal table without triggers and 0079 had to catch up. Reverse drops this table's two triggers and the table; the shared functions stay. No existing migration altered |
| `core/services/audit_guards.py` `PROTECTED_TABLES` | Drives the append-only + truncate triggers (`install_audit_guards`, its `--check`, `verify_audit_chain`'s guard check, the test runner), `provision_app_role_sql` (REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER) and `privilege_report` |
| `core/services/audit_chain.py` `PROJECTIONS`, `SEAL_ORDER` | All 12 columns chained; nothing in `UNCHAINED_FIELDS`. Appended **last** in `SEAL_ORDER`, so the relative order of the existing tables — and a chain rebuilt from rows that predate this table — is unchanged. `verify_chain` and `_pending` pick it up from these two |
| `core/admin.py` | `GameDeletionAuditEventAdmin(AppendOnlyAdmin)` (R13: no add, change or delete; every field read-only) |
| `core/services/competition_audit.py` | `record_game_deletion`, the single writer |
| `ops/provision-app-role.sh` `APPEND_ONLY_TABLES` | The shell list that cannot import the Python one |
| `core/services/route_inventory.json` | Regenerated: +2 admin redirect routes (see section 4) |
| `core/services/read_inventory.json` | Regenerated: `url_conf_route_count` only. No route serves the table, so no sensitive-read row was added |
| Manifest schema inventory | **Not applicable, checked.** `manifest_sections` enumerates competitive state, not audit tables; `test_manifest_determinism` passes unchanged |
| `AUDIT_INTEGRITY_OPERATIONS.md`, `AUDIT_INTEGRITY_INVENTORY.md`, `ops/V2-072_CUTOVER_RUNBOOK.md` | Sealing list, truncate-guard count, retention/access row, a section for the deletion record with the operator steps, migration note, inventory disposition row, drift paragraph |

### Fixed counts and lists that were updated deliberately

* `test_audit_integrity.AdminTamperingTests.test_the_admin_offers_no_way_in_for_any_audit_record`
  named five models. Now seven: `GameDeletionAuditEvent`, and
  `AuthorizationRefusalEvent` (below).
* `route_inventory.json`: `total_mutating_routes` **215 → 217**. The two added
  keys are `admin/core/gamedeletionauditevent/<path:object_id>/` and
  `admin/core/authorizationrefusalevent/<path:object_id>/`, both Django's admin
  `RedirectView`, `lifecycle_mutating: false`. Lifecycle counts unchanged:
  38 lifecycle-mutating, 22 guarded, 16 exempt, 0 unguarded.
* `read_inventory.json`: `url_conf_route_count` **785 → 797** (twelve admin URL
  patterns for two registrations). 34 sensitive routes, 33 logged, 1 exempt —
  unchanged. `test_audit_integrity`'s `len(middleware._routes) == 33` still
  holds.
* Every other assertion in `test_audit_integrity` iterates `PROTECTED_TABLES`,
  `ALL_TABLES` or `PROJECTIONS`, so it now covers the new table without an
  edit: guard presence, truncate refusal per table, the provisioned role's
  REVOKE per table, and "every column is chained or excluded with a reason".
* Docs: "all five tables" in the operations guide and "six audit tables" in the
  runbook's drift section.

### Two defects found on the way, both fixed

1. **`ops/provision-app-role.sh` excluded audit tables from its "application
   tables the role cannot write (must be empty)" report by fixed array index
   `[0]`…`[4]`.** With a sixth append-only table the last element,
   `competition_audit_chain`, would have fallen out of the exclusion and been
   reported as a missing grant on every `--check` — report-only (the verdict
   loop iterates the whole array), but a standing false alarm in the output an
   operator is told to read. Now built from the array. Rehearsed in section 4.
2. **`AuthorizationRefusalEvent` was never registered in the admin.**
   `AppendOnlyAdmin`'s own docstring explains why an audit table is "registered
   rather than left out". New test
   `test_every_audit_model_is_registered_read_only_in_the_admin` walks
   `ALL_TABLES` and was red on exactly that table; it is registered now.

And one gap closed rather than reported: nothing compared the shell script's
table list with `PROTECTED_TABLES` (the runbook said "the two lists are not
derived from one another"). `test_the_provisioning_script_names_every_append_only_table`
reads the script and fails on any difference.

## 4. Production operator steps after migration 0088

V2-072 was cut over on production on 2026-09-16, so the application role
exists there and `ALTER DEFAULT PRIVILEGES` will hand it `UPDATE` and `DELETE`
on the new table the moment the owner's migration creates it. The triggers
refuse both regardless; the privilege layer is restored by re-running the
script. As the database owner, from the application host:

```bash
cd backend && python3 manage.py migrate core 0088      # as the owner, as for every migration
ops/provision-app-role.sh            # no password file: re-applies grants only, changes no credential
ops/provision-app-role.sh --check    # must end PASS and exit 0
cd backend && python3 manage.py install_audit_guards --check
```

`--check` **on its own, before the re-run, fails** — that is the designed
signal, not a fault. Note also that the *new* script refuses to run at all
("has no table competition_game_deletion_audit_event") against a database that
has not had 0088 applied, so the order is migrate first.

**Rehearsed** on a disposable PostgreSQL 16 with the production role shape
(owner-owned tables, role provisioned by the script as it stood at `ba6a1c7`,
then the new table created by the owner as a migration would):

```
=== 3. NEW script --check before re-provisioning (expect FAILED, exit 1) ===
competition_game_deletion_audit_event   owner=probe_owner  select=t insert=t update=t delete=t truncate=f
FAIL: globalstrat_plus_app can rewrite or own the audit table competition_game_deletion_audit_event
FAILED: globalstrat_plus_app does not meet the V2-072 least-privilege contract.
exit=1
=== 4. NEW script, apply (no password file: grants only) ===
grants applied.
PASS: globalstrat_plus_app is a least-privilege, non-owning application role.
exit=0
=== 5. NEW script --check (expect PASS, exit 0) ===
competition_game_deletion_audit_event   owner=probe_owner  select=t insert=t update=f delete=f truncate=f
competition_audit_chain                 owner=probe_owner  select=t insert=t update=f delete=f truncate=f
PASS: globalstrat_plus_app is a least-privilege, non-owning application role.
── application tables the role cannot write (must be empty) ───────
── sequences the role cannot use (must be empty) ──────────────────
exit=0
```

The empty "must be empty" section in step 5 is defect 1 above, fixed: with the
indexed exclusion it would have listed `competition_audit_chain`.

Separately, `ProvisionedRolePrivilegeTests` executes the Python
`provision_app_role_sql()` statements inside the test database and asserts, via
`has_table_privilege`, INSERT and SELECT true and UPDATE, DELETE, TRUNCATE,
REFERENCES, TRIGGER false on the new table, with `DELETE` on `game` true as the
control and `USAGE` on the table's sequence true.

## 5. Red, then green

Red: both new test files against runtime code at `ba6a1c7`, 37 tests,
`FAILED (failures=6, errors=22)`, 29.9 s wall.

| Red result | Tests |
|---|---|
| `ImportError: cannot import name 'GameDeletionAuditEvent'` ×18, `relation "competition_game_deletion_audit_event" does not exist` ×1, `competition_audit has no attribute 'record_game_deletion'` ×3 (the failure-injection tests, which patch it) | every R45 test that needs the record, the table, the chain entry, the admin entry, the migration or the role privileges |
| `unexpectedly None : competition_authorization_refusal_event is not in the admin` | `test_every_audit_model_is_registered_read_only_in_the_admin` — defect 2 |
| `None != 41` (the creator's id) | `test_the_creator_is_the_instructor_of_record_from_creation` |
| `39 != 38`, `None != 50` | an instructor naming someone else / naming `null` |
| `200 != 403` with body `{'course_id': 18, … 'instructor_id': None …}` | `test_another_instructor_is_refused_on_the_new_course` — the second instructor **read** the first one's new course |
| `200 != 403` with body `{… 'max_teams': 1 …}` | `test_the_other_instructor_is_refused_at_every_step` — the second instructor **rewrote** the new course's section |

The nine tests green on red are the ones that assert behaviour R45/R46 must not
change (admin-created course stays shared; an admin may name an instructor;
stored unowned courses are not reassigned; creator and admin succeed; the three
list-agreement tests that did not yet involve the new table).

Green: same 37 tests, `OK`.

**Both directions of the transaction claim**, each in a `TestCase` and again in
a `TransactionTestCase` with real commits:

* *No deletion without its record* — `record_game_deletion` patched to raise:
  500, game, both teams and the round still present, table empty.
* *No record without its deletion* — `record_game_deletion` patched to call the
  real writer **and then** raise, with an assertion inside the patch that the
  row count is 1 at that moment, so the injection is provably after the write:
  500, table empty again, game and teams present, and (real-commit variant) no
  chain entry for the table.

**Triggers on real PostgreSQL** (the disposable container): raw-SQL UPDATE and
DELETE, ORM `.update()` and `.delete()`, and TRUNCATE with the test allowance
withdrawn are each refused with the trigger's own message; `save()` on a loaded
row raises. `test_an_edit_made_with_the_trigger_dropped_is_detected` drops the
trigger, edits the row and gets `row_modified` from `verify_chain`.

**The migration itself.** The test runner builds its database from the models
and then installs today's guard list, which is the masking that let 0078 ship a
table with no triggers. `DeletionMigrationTests` therefore drops the table the
runner built and runs migration 0088's own operations through a schema editor:
after `apply` the table exists with both triggers and refuses an UPDATE; after
`unapply` the table is gone, the only missing guards are this table's, and the
shared reject function is still there.

## 6. Commands, results, durations

All backend runs: `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`.

| # | Labels | Result | Wall |
|---|---|---|---|
| 1 | `test_game_deletion_audit test_course_creator_owns` — **red**, runtime at `ba6a1c7` | 37 tests, FAILED (failures=6, errors=22) | 0:30 |
| 2 | same, after the change | 37 tests, 1 error — my migration test could not see migration modules the runner hides; test fixed (`override_settings(MIGRATION_MODULES={})`), no runtime change | 1:12 |
| 3 | `test_game_deletion_audit.DeletionMigrationTests` | 2 tests, OK | 0:11 |
| 4 | the two new files + `test_audit_integrity test_refusal_audit_integrity test_refusal_audit test_who_attempted test_operator_route_ownership test_operator_concurrency test_cohort_caps test_console_defects test_manifest_determinism --parallel 8` | 319 tests, FAILED (failures=3, errors=1): route and read inventories stale (expected, +2 admin routes) **and** the four `courses` routes flagged as unguarded lifecycle writers — the detector false positive described in section 2. `perform_create` reworked, inventories regenerated | 1:47 |
| 5 | same labels | **319 tests, OK** | 1:30 |
| 6 | `core --parallel 8` — the full run, at freeze commit `05213e3` | 1372 tests, **FAILED (errors=1)**: `test_team_participation_control…test_student_cannot_operate_control`, in `setUp`, `duplicate key … "auth_user_pkey"`. See below | 2:11 |
| 7 | `test_team_participation_control` with a new test that forces the collision, fixture unchanged — **red** | 5 tests, FAILED (errors=1), the same `auth_user_pkey` error | 0:11 |
| 8 | `test_team_participation_control test_legacy_control_removal`, fixture repaired | 17 tests, OK | 0:12 |
| 9 | `core --parallel 8` — certification, from the new freeze commit `bbfaa4b` | **1373 tests, OK** | 2:04 |

### Why there are two full runs

The budget is one. Run 6 was a real failed freeze candidate, so per the
execution protocol ("stop, diagnose with focused tests, repair, create a new
freeze commit, then certify once from that commit") it was not re-run to see
whether it flaked. It was diagnosed:

`TeamParticipationControlTests.setUp` gives the student's `auth_user` row the
explicit id of their `users` row, and took the owner's `auth_user` id from that
table's sequence. Sequences are not rolled back between tests, so whenever the
tests a worker has already run leave the two sequences aligned, the owner takes
exactly the id the student is about to be given, and one test of the class dies
in `setUp`. It is a latent defect in a fixture from `2592f93`, not in anything
this work changed at runtime; the two new test modules create enough `users`
and `auth_user` rows to move the counts onto it.

Proved rather than argued: `FixtureSequenceAlignmentTests` sets the
`auth_user` sequence so that its next value is the student's id and runs the
fixture. Red with the fixture as it was (run 7, the identical error); green with
the owner given an explicit id clear of both sequences (run 8). The only other
test that inserts an explicit `auth_user` id (`test_legacy_control_removal`)
creates no sequence-issued `auth_user` row beside it, so it cannot collide; it
was included in run 8 anyway. **The repair is test-only** — `bbfaa4b` touches
one test file — so the runtime code certified by run 9 is byte-identical to
`05213e3`.

Static guards at `05213e3` (runtime identical at `bbfaa4b`): `manage.py check` clean; `makemigrations --check
--dry-run` "No changes detected"; `dump_route_inventory --check` and
`dump_read_inventory --check` current (run with `DB_HOST=127.0.0.1 DB_PORT=1`,
so they could not have reached any database); `bash -n
ops/provision-app-role.sh`; `git diff --check` clean.
`python3 backend/scripts/check-participant-strings`: PASS, 4829 units, 0
findings. No frontend file changed, so Jest was not run.

No runtime code changed after run 6, and nothing at all changed after run 9
except this report and the regenerated string inventory.

## 7. Auditor preflight

* *Inventory from registries?* Course-creation and game-deletion paths from
  `urls.py` plus a source sweep for ORM creates/deletes; audit-table
  registrations from a sweep for every reference to the most recently added
  audit table, then closed with tests that walk `ALL_TABLES`.
* *Alternate entry point?* Section 1.
* *Does a refusal audit survive rollback?* Unchanged: refusals are still
  written by `_record_rejection` after the rollback;
  `test_a_refused_delete_writes_no_deletion_record` asserts the rejected
  operator row is there and the deletion table is empty.
* *Correlation id once?* The row, the response and the log line all carry
  `action.request_id`; asserted with a caller-supplied `X-Request-ID`.
* *Work delayed until commit?* The seal is `on_commit`. The log line is emitted
  inside the transaction, as it was before this work; it is a log line, not
  external work, and the task said to keep it.
* *Negative tests prove non-execution?* Each refusal and each injected failure
  asserts the game, its teams and its round are still present and the table is
  empty.

## 8. New zh-CN sentences for review

**None.** Neither item adds an operator-facing sentence or code: R45 writes an
English-only audit row (R44) and changes no response; R46 changes a stored value
on a 201 and reuses the existing `cohort_belongs_to_another_instructor` refusal
for the second instructor. `operator_messages.py`, `cohort_messages.py` and
`bilingualServerReason.js` are untouched.

## 9. Proposed register and checklist text (for the auditor to apply or reject)

**V2-134 — append:**

> **R45 implemented, pending closure** at `05213e3`. A committed deletion
> writes `GameDeletionAuditEvent` (`competition_game_deletion_audit_event`,
> migration `0088`): no foreign keys; game id and name, scenario id and name,
> actor id and username, reason, prior state, request id, time; English only.
> Written inside the deleting transaction — both directions tested, including a
> failure injected after the row is written. Append-only and truncate triggers
> installed by the migration that creates the table; every column hash-chained
> and sealed on commit; read-only admin; application role INSERT and SELECT
> only after `ops/provision-app-role.sh` is re-run. The log line is kept.
> Also fixed: the provisioning script's indexed audit-table exclusion, and
> `AuthorizationRefusalEvent` missing from the admin. **Open:** the production
> operator step below has not been performed.

**V2-133 — append:**

> **R46 implemented, pending closure** at `ab266de`. An instructor who creates a
> course is its instructor of record from creation, whatever the body carried;
> an admin may name one, and naming none leaves the course unowned. Existing
> unowned courses are not reassigned. The creator passes the course, section,
> roster and team-management ownership checks immediately; a second instructor
> is refused at each.

**New finding, proposed (test infrastructure, P3):**

> **A test fixture depended on where two sequences sat.**
> `TeamParticipationControlTests.setUp` gave the student's `auth_user` row the
> explicit id of their `users` row and drew the owner's id from the `auth_user`
> sequence; sequences survive test rollback, so an aligned pair killed one test
> in `setUp` with `auth_user_pkey`. Surfaced when two new test modules moved the
> counts; failed the full suite once at `05213e3`. Repaired at `bbfaa4b` with a
> test that forces the alignment (red before, green after). Test-only.

**Launch checklist, under V2-072 — add:**

> - [ ] After migration `0088` on the competition host: `ops/provision-app-role.sh`
>   then `ops/provision-app-role.sh --check` (must PASS), then
>   `manage.py install_audit_guards --check`. Until the first is re-run, `--check`
>   fails on `competition_game_deletion_audit_event` by design.

## 10. What a reviewer should distrust

Only what could not be resolved from here.

1. **The production step has not been run**, and cannot be from this worktree.
   Until it is, the application role on production holds UPDATE and DELETE
   *privileges* on the new table (the triggers still refuse both). The rehearsal
   in section 4 used a disposable server built to the production role shape; it
   is not the production server.
2. **Retention for the new table is not ruled.** The operations guide now says
   "same as the operator audit row it stands in for", which is a derivation, not
   an owner decision.
