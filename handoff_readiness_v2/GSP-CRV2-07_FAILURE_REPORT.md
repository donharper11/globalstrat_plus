# GSP-CRV2-07 — Failure injection and recovery

Second half of the load-and-failure handoff. The load half was delivered
separately (`GSP-CRV2-07_LOAD_REPORT.md`) and the authentication checkpoint in
`GSP-CRV2-07_AUTH_ADDENDUM.md`. This half carries one repair, V2-029, which
adds validation to both supported decision-write surfaces. No load profile was
rerun; the rationale is stated under *Not rerun* below.

Evidence: `evidence/load-failure/failure-walkthrough.json`,
`evidence/load-failure/duplicate-product-name.json` and
`evidence/load-failure/duplicate-product-name-repaired.json`. Harness:
`evidence/load-failure/harness/failure_walkthrough_{run,body}.py`,
`duplicate_product_{probe,body}.py`.

## What was run

One disposable database, one disposable gunicorn stack, one seeded game, walked
forward through seven stages. The deploy/restore checks are discharged by that
same walk rather than as a separate exercise: the backup taken in stage 1 is
the dump restored in stage 7.

The cohort is the four fully instantiated teams `setup_test_game` creates. An
earlier run seeded twenty-four, but the extra teams were bare rows with no home
market and no starter state, so they carried no products and could not price or
produce. The harness now refuses any cohort containing a team with no active
product, naming the offenders, rather than resolving a smaller game than the
evidence claims.

## Results

All seven stages pass. Every stage records the user-visible symptom, committed
state, operator action, recovery result, and write reconciliation.

| # | Boundary | Symptom | Committed state | Operator action | Recovery | Writes lost or duplicated |
|---|---|---|---|---|---|---|
| 1 | Normal resolution | none | 1→2 rounds, 4→8 financial rows | resolve the round | dump written and verified | 0 |
| 2 | Two operators resolve at once | the losing operator sees an error | one resolution only; 4 rows added, not 8 | none needed | one attempt refused | 0 |
| 3 | Backend restart after committed Phase 1 | in-flight requests fail | identical before SIGKILL, after SIGKILL, after restart | restart the service | service answers again | 0 |
| 4 | Save arrives after the deadline | refused, HTTP 403 | unchanged, 1→1 rows | none; the deadline control refused it | student informed; nothing to undo | 0 |
| 5 | Pre-resolution backup cannot be written | resolution stops, error names the backup | unchanged; round not processed | fix the backup target and retry | round intact | 0 |
| 6 | Database lost mid-resolution | `OperationalError`, closed socket | unchanged; round returned to `open`; **zero partial results** | restore and replay | via stage 7 | 0 |
| 7 | Restore, and refuse bad dumps | n/a; this is the recovery | restored to the stage 1 point | verify then restore | restored; tampered dump and dump outside the backup root both refused | 0 |

Stage 5 matters because the backup is taken inside `process_round` *before*
`_run_phase_1` (`advance_round.py:218`). A backup that cannot be written must
abort the round before any competitive mutation, and it does — a round that
resolved with no recovery point would be the worst available outcome.

Stage 6 is the strongest result: a backend destroyed mid-Phase-1 committed zero
partial results and returned the round to `open`. That is the property the
two-phase design rests on, now demonstrated rather than assumed.

## Two mechanisms stated plainly

**Stage 5 does not fill a disk.** A genuine `ENOSPC` needs a mounted small
filesystem and this host cannot mount one. The backup directory is made
unwritable instead. The code path is identical — `pg_dump` fails, the exception
leaves `process_round` before resolution, no partial artifact remains — but the
errno differs, and no claim is made that a disk was filled.

**Stage 6's kill is triggered from inside the resolution.** Two attempts to
time it externally terminated nothing: a fixed two-second sleep is slower than a
four-team round, and polling `pg_stat_activity` spawns a process per sample, so
the effective interval exceeded the burst of result writes. The kill now fires
from a `post_save` on the first `RoundResultFinancials` row. The termination
itself is a real `pg_terminate_backend` from the server; the signal chooses only
the moment.

Both earlier attempts reported FAIL rather than a survived database loss,
because the stage requires the error to be attributable to connection loss and
requires at least one backend to have actually died. An earlier revision
accepted any exception and passed on an unrelated `SnapshotError` while proving
nothing.

## Finding V2-029: an accepted student write could stall a round — repaired

Severity P0. Found while diagnosing stage 6's false pass, audited as blocking at
`16d49fc`, repaired at `357e3e4`.

**The defect.** `PATCH /api/games/{id}/teams/{id}/decisions/round/{n}/products/`
returned 200 for either of these, and the round could then never be resolved:

- **A** — two product creates sharing one name. Refused at `prepare_manifest`
  on `decision_product_create`'s key `(submission_id, product_name)`, before
  Phase 1 runs.
- **B** — one product create reusing the name of a product the team already
  owns. The decision rows are unique, so Phase 1 ran and created the second
  `TeamProduct`; `complete_manifest` then tripped `team_product`'s key
  `(team_id, name)`, and the whole resolution rolled back because it shares
  Phase 1's transaction (`advance_round.py:230`).

In both cases the round stayed `open`, the error was identical on retry, and
the instructor could not close the round. Nothing was corrupted — no duplicate
was ever persisted and no decisions were lost — but the round was stalled for
the whole cohort, and the only recovery was editing decision rows directly in
PostgreSQL. Rollback integrity is not a substitute for validating an ordinary
student decision, and manual SQL is not an acceptable launch disposition.

Reproduction at `16d49fc`, both variants through the student endpoint:
`evidence/load-failure/duplicate-product-name.json`. That file is historical
evidence for the unrepaired revision.

**The repair.** One shared validator, `validate_product_names(creates, team)`
in `core/serializers/decisions.py`, enforcing both rules and raising an
actionable 400 naming `product_name`. It is called from the per-type endpoint
before the replacement delete, so a refused payload leaves the team's persisted
decisions untouched, and from `DecisionSubmissionSerializer.validate`, so the
whole-submission endpoint enforces the identical rule rather than a copy of it.

Names are compared exactly, after the serializer's own string handling. No case
folding or fuzzy matching was introduced; that would be a new competition rule
rather than a repair. A retired product does not release its name, because the
manifest key spans the whole table and accepting a reused name would stall the
round exactly as before.

The manifest natural-key refusals are unchanged, and remain the backstop for
rows introduced outside the supported APIs.

**Acceptance.** `core/tests/test_product_name_uniqueness.py`, 10 tests, all
passing: both endpoints refuse both variants; neither writes a replacement row;
two distinct names are accepted; another team may use the same name; a retired
name stays taken; a rejected payload leaves the previous set intact; a
corrected payload is accepted and the round then resolves; and ORM-inserted
duplicates are still refused at the manifest boundary with zero partial
results. Directly affected contract suites — `test_decision_limits`,
`test_permissions`, `test_auth_rounds`, 91 tests — pass unchanged.

The same probe that reproduced the defect now asserts the repair at the running
HTTP surface (`evidence/load-failure/duplicate-product-name-repaired.json`):
both payloads refused with a 400 naming `product_name`, no decision rows
written by the refusal, corrected payloads accepted, and both rounds resolved
with no database intervention.

`OPERATOR_RUNBOOK.md`'s manual-SQL procedure is withdrawn as a supported
action. If that `SnapshotError` appears now it means rows arrived outside the
supported APIs, so the runbook routes it to the defect procedure instead of an
operator workaround.

## Reconciliation

No stage lost or duplicated an acknowledged write. Stage 4's refused save left
no partial row; stage 6's killed resolution committed nothing; stage 7 restored
to exactly the stage 1 state.

## Not rerun

Field and margin load profiles, the 96-user authentication drive, CRV2-01
determinism, CRV2-02 concurrency and race matrix, CRV2-03 provider and SIGKILL
drills, and the full backend suite.

V2-029 does touch request handling: it adds validation to both supported
decision-write surfaces, and the earlier claim that no repair in this half did
so was wrong. The decision not to rerun the load profiles is proportionate for
a narrower reason. The change is a bounded deterministic validation and refusal
path. It does not alter how an accepted request executes, the worker
configuration, authentication, database concurrency, or the traffic model the
existing profiles measured — a refused payload is a 400 raised before the
endpoint's replacement delete, which is strictly less work than the accepted
path already measured. The load, authentication and readiness evidence
therefore carries forward by revision.
