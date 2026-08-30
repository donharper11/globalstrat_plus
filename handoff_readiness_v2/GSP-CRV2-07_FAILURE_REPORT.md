# GSP-CRV2-07 — Failure injection and recovery

Second half of the load-and-failure handoff. The load half was delivered
separately (`GSP-CRV2-07_LOAD_REPORT.md`) and the authentication checkpoint in
`GSP-CRV2-07_AUTH_ADDENDUM.md`. Nothing in this half changed request handling,
worker count, database behaviour or authentication, so no load profile was
rerun.

Evidence: `evidence/load-failure/failure-walkthrough.json`,
`evidence/load-failure/duplicate-product-name.json`. Harness:
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

## Finding: an accepted student write can stall a round

Severity: high. Found while diagnosing that false pass. Reproduced end to end
through the student HTTP endpoint, both variants, at `duplicate-product-name.json`.

`PATCH /api/games/{id}/teams/{id}/decisions/round/{n}/products/` returns **200**
for either of these:

- **A** — two product creates sharing one name. Refused at `prepare_manifest`
  on `decision_product_create`'s key `(submission_id, product_name)`, before
  Phase 1 runs.
- **B** — one product create reusing the name of a product the team already
  owns. The decision rows are unique, so Phase 1 runs and creates the second
  `TeamProduct`; `complete_manifest` then snapshots the output state, trips
  `team_product`'s key `(team_id, name)`, and the whole resolution rolls back
  because it shares Phase 1's transaction (`advance_round.py:230`).

In both cases the round stays `open`, the error is identical on retry, and the
instructor cannot close the round. `product_name` is free text with no
uniqueness validation on the write path, so nothing warns the student and
nothing warns the operator.

Nothing is corrupted, and this is worth being clear about: no duplicate is ever
persisted, Phase 1's work is rolled back with the rest, and no team's decisions
are lost. The round is stalled, not damaged.

The only recovery is deleting the surplus decision row directly in the database.
There is no endpoint, no management command, and — until this handoff — nothing
in the runbook. `OPERATOR_RUNBOOK.md` now carries the diagnosis queries and the
procedure, marked as the one deliberate exception to its own "do not substitute
manual SQL" rule.

**Not repaired here.** The obvious fix is uniqueness validation on the write
path, returning 400 instead of 200. That changes request handling, which under
this handoff's own terms would require rerunning the load profiles — the loop
the handoff exists to avoid. Recommended as a separate scheduled item; the
runbook procedure covers the competition in the meantime.

## Reconciliation

No stage lost or duplicated an acknowledged write. Stage 4's refused save left
no partial row; stage 6's killed resolution committed nothing; stage 7 restored
to exactly the stage 1 state.

## Not rerun

Field and margin load profiles, the 96-user authentication drive, CRV2-01
determinism, CRV2-02 concurrency and race matrix, CRV2-03 provider and SIGKILL
drills, and the full backend suite. No repair in this half touched request
handling, worker count, database behaviour or authentication.
