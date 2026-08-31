# GSP-CRV2-08 — post-close retrieval and dispute walkthrough: completion report

## Revisions

| | |
|---|---|
| Baseline | `ba42484` (CRV2-07 accepted) |
| Freeze | `d69befa` |
| Fixture and first walkthrough | `8554db3` |
| V2-030 / V2-031 repair | `45eb83c` |
| First ownership scan and finding | `ebf40fc` |
| Ownership boundary | `d39ce04` |
| Refusal auditing | `5a777ba` |
| Guard migration and sealing | `8136fad` |
| Data dictionary and archive | `ef9aca6` |
| V2-036 registered before repair | `4523d6c` |

## Outcome

All six defined disputes are answerable through a supported path. Two were
found unanswerable during the walkthrough and repaired; four were answerable as
built, with one runbook correction.

| # | Dispute | Supported path |
|---|---|---|
| 1 | Submitted before the deadline | instructor evidence table / `GET /api/games/{id}/instructor/teams/{tid}/decisions/?round={n}` |
| 2 | Recorded decision differs | same response: per-save `payload` and `payload_sha256` |
| 3 | Rival saw our decisions | `manage.py who_accessed` |
| 4 | Rerun after final | `manage.py replay_round --export-only` |
| 5 | Operator changed something | Operator Log tab / `GET /api/games/{id}/instructor/operator-events/` (V2-030) |
| 6 | Prove the calculation | `manage.py replay_round --restore`; round 1 reproduced exactly, hash `108c4f0a…`, exit 0 |

## Findings and dispositions

| ID | Sev | Disposition |
|---|---|---|
| V2-030 | P1 | Operator actions unreadable outside the Django admin. **Closed** at `45eb83c`. Registered after repair, contrary to the standing rule; the register says so. |
| V2-031 | P2 | Language preference never persisted (404 into a silent catch). **Closed** at `45eb83c`. Same late-registration note. |
| V2-032 | **P0** | Game ownership not enforced for instructor routes — ten GETs disclosed another cohort's data, including raw decisions and their hashes. **Closed** at `d39ce04`. |
| V2-033 | — | Unowned course readable by any instructor. **Withdrawn: not a defect**, adopted shared-pilot rule. Operational consequence: a prize cohort not meant to be shared must have an instructor owner assigned before launch. |
| V2-034 | P1 | Refused non-owner writes left no record. **Closed** at `8136fad`. |
| V2-035 | P1 | Instructor alerts readable by any signed-in student. **Closed** at `d39ce04`. |
| V2-036 | P1 | Refusal evidence had no supported reader. **Closed** at `d69befa`. Registered before repair. |

## Changed files

**Backend.** `core/middleware.py` (game-scope guard, refusal recording),
`core/services/game_scope.py` (new), `core/permissions.py` (JWT identity),
`core/views/results_api.py` (operator events endpoint),
`core/views/instructor_alerts.py` (role check), `core/urls.py`,
`core/models/audit_integrity.py` (refusal model, seal scheduling),
`core/models/__init__.py`, `core/services/audit_guards.py` (per-table SQL),
`core/services/audit_chain.py`, `core/services/read_inventory.json`,
`core/management/commands/who_attempted.py` (new),
`globalstrat/settings.py` (middleware registration).

**Frontend.** `components/instructor/OperatorEventsPanel.js` (new),
`pages/InstructorDashboard.js`, `api/instructor.js`,
`components/LanguageSwitcher.js`.

**Migrations.** `0078_authorization_refusal_event` (table),
`0079_authorization_refusal_guards` (append-only and no-TRUNCATE triggers).
`0070`, `0071` and `0072` were amended to pin the audit-table list they were
written against: they called `install_sql()` with no arguments and so read the
live list, meaning any new audit table broke every fresh install while
already-migrated databases stayed silent.

**Documentation.** `V2_FINDINGS_REGISTER.md`,
`GSP-CRV2-08_AUDIT_CHECKPOINT_2.md`, `OPERATOR_RUNBOOK.md`,
`evidence/post-close-disputes/DATA_DICTIONARY.md`,
`evidence/post-close-disputes/DISPUTE_PATH_INVENTORY.md`.

## Focused tests and commands

| Suite | Tests |
|---|---|
| `test_who_attempted` | 10 |
| `test_refusal_audit_integrity` | 11 |
| `test_refusal_audit` | 8 |
| `test_game_scope_boundary` | 9 |
| `test_operator_events_view` | 7 |
| `test_product_name_uniqueness` (carried from CRV2-07) | 10 |
| `test_audit_integrity`, `test_disclosure_read_gate`, `test_session_readiness`, `test_decision_limits`, `test_permissions`, `test_auth_rounds` | run as directly affected |

Commands exercised: `dump_read_inventory`, `install_audit_guards --check`,
`migrate` (forward and reverse of `0079`), `who_accessed`, `who_attempted`,
`replay_round` (`--export-only` and `--restore`).

## Isolated stack identity

Every run used a disposable PostgreSQL database on `192.168.50.38` and a
gunicorn bound to a port claimed at run time. Ports are never fixed: the first
configuration used 8002, which already carries a gunicorn serving the live
`globalstrat_plus` database, so the backend failed to bind and requests fell
through to that server. The stack now refuses to start unless a fixture
identity authenticates through its own origin.

- Fixture: `gsp_crv208_disputes` — three teams, three processed rounds, status
  `completed`, one `defaulted_missing` team-round, three submissions saved
  twice with differing hashes, one save refused after the deadline.
- Authorization scan: `gsp_crv208_authscan`, a clone, dropped after the run.
- Replay: `gsp_crv208_replay`, restored from a pre-resolution dump, dropped.
- Migration proof: `gsp_crv208_migrate`, migrated from empty, dropped.

The frontend was served from its production build on one origin with `/api`
proxied to the backend, so no CORS configuration exists that would not exist in
deployment. Browser work used system Chromium driven by `puppeteer-core`
installed to a scratch directory; the project's `package.json` is untouched.

## Evidence

`handoff_readiness_v2/evidence/post-close-disputes/`, 32 files covered by
`ARCHIVE_MANIFEST.json`, which `SHA256SUMS` covers in turn.

| Artifact | What it holds |
|---|---|
| `WALKTHROUGH_RECORD.json` | the concise record, generated from the artifacts, with per-artifact provenance |
| `completed-game.json` | the reusable fixture and its seeding trail |
| `browser-walkthrough.json` | both roles, real Chromium, console and network capture |
| `dispute-answers.json` | the six disputes at `8554db3` |
| `repeat-after-repair.json` | dispute 5 and language persistence after repair |
| `instructor-ownership-scan.json` | the ten original disclosures |
| `ownership-scan-after-repair.json` | 94 routes, 65 reads, 37 writes |
| `who-attempted-walkthrough.txt` | a real 403 and its retrieval by request id |
| `pagination-boundary.json` | the Operator Log paged through its own control |
| `replay/` | manifest export, input verification, replay report |
| `screenshots/` | eight screens across both roles |
| `DATA_DICTIONARY.md`, `DISPUTE_PATH_INVENTORY.md` | end-run sources; dispute paths |

## Expensive runs

| Run | Count | Scale |
|---|---|---|
| Fixture builds | 7 | ~2 min each; six were rejected by the seeder's own checks or by defects it exposed |
| Browser walkthroughs | 4 | ~3 min each |
| Ownership scans | 3 | 94 routes, 65 reads and 37 writes against a clone, ~6 min each |
| Round replay | 1 | full Phase 1 on a restored database, 4.4 s engine time |
| Migration-from-empty | 3 | ~1 min each |
| Pagination browser path | 1 | ~40 s, one table, three page transitions |

No load profile, concurrency matrix, determinism replay, provider drill or
failure walkthrough was run. The full backend and frontend suites were not run:
CRV2-09 owns the one integrated regression suite.

## Pagination boundary

Exercised on the Operator Log, which paginates at 10 against 14 operator
events. Driven through the rendered control, not by slicing the API: page 1
shows 10 rows, page 2 shows the remaining 4 with no row identity in common,
and returning to page 1 restores the original set exactly. No console errors
and no unexpected network failures.

The audit's instructions anticipated 3 rows on page 2 from 13 events; there are
14, because producing a genuine refusal for the dispute-5 repeat added one. The
harness asserts the remainder against the total the table itself reports rather
than a fixed number.

Evidence: `evidence/post-close-disputes/pagination-boundary.json` and
`screenshots/operator-log-page-2.png`.

The audit evidence table in the decision drill-down still paginates at 8 with 6
rows in this fixture, so that particular table's boundary remains unreachable;
the handoff asks for one pagination boundary and this is it.

## Rollback

- `0079` reverses cleanly and removes only the refusal table's two triggers;
  proven by reversing and re-applying it on a disposable database.
- `0078` reverses by dropping the refusal table. Reversing it discards refusal
  evidence, which is why it is separate from the guard migration.
- Removing `GameScopeGuardMiddleware` from `settings.MIDDLEWARE` restores the
  pre-repair behaviour, which is V2-032 — ten disclosing endpoints. A
  contract test fails if a game-scoped instructor route is neither guarded nor
  explicitly exempted, so the boundary cannot be silently dropped.
- The frontend changes are additive; removing the Operator Log tab leaves the
  endpoint reachable.

## Unresolved, outside this handoff

- **V2-017** — 216 admin write routes outside the lifecycle boundary.
- **The non-owner database deployment action**, carried since CRV2-07.
- **No browser view of refused cross-cohort attempts.** Retrievable by command
  (V2-036); an instructor holding a 403 needs an operator to run it. Recorded
  in the data dictionary as a stated limit, not a defect.
- **Write endpoints were exercised only as an unrelated instructor.** They are
  proven to refuse and to mutate nothing in that role; no other role was
  driven against them here.
