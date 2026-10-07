# GlobalStrat+ recovery checkpoint — 2026-10-06 UTC

**Candidate:** `f0cf7be47264f41c51400c41b113f0237328b0b5` on
`crv2-release-integration`.

## Execution and scope confirmation

At 2026-10-06T03:03Z, command execution was confirmed on `ai-react`
(`192.168.50.5`).  This workspace is the production-host VM itself; an SSH
attempt to `ubuntu@192.168.50.5` was therefore unnecessary and was not a
production-access test.  No production service, database record, deployment,
or configuration was changed during recovery of this work.

The pre-existing untracked
`docs/COMPETITION_LAUNCH_IMPLEMENTATION_PLAN.md` remains untouched. Existing
worktrees were not changed.

## Preserved Gate 1 evidence

The volatile artifacts under `/tmp` were copied without modification to
`handoff_readiness_v2/evidence/gate1-2026-10-05/`; `SHA256SUMS` covers every
copied file.

* Backend suite: **1,868 tests**, passed (source log records 471.826 seconds).
* Frontend suite: **56 suites / 531 tests**, passed.
* Production frontend build and participant-string/lint logs are preserved.
* Two ten-round deterministic replays have identical normalized SHA-256:
  `7c99fe4f8f965ca76d4c9073efcb61100b992563e45ded406df5e9cfbb6a7071`.

This records and preserves the successful October 5 evidence rather than
restarting those completed gates.

## Current-candidate browser acceptance — partial pass

An isolated current-candidate stack (disposable PostgreSQL on loopback, built
frontend, and a temporary gunicorn) was run on this host.  It was stopped
without processing its open first round; its database container and generated
test credentials were removed afterwards.

The retained records are under
`handoff_readiness_v2/evidence/gate1-browser-2026-10-06-rerun/`.

* The instructor created an eight-team game, uploaded 27 students, verified a
  sixth-member refusal, activated and scheduled the game, set and extended a
  deadline, paused/resumed, injected an event, inspected the operator log,
  and exercised grading/exports.
* The explicit bulk-password control provisioned every roster account.  A
  harness assertion missed its transient success toast, but an authenticated
  read immediately afterwards found **0 accounts without passwords**; this is
  a harness-observation limitation, not a product refusal.
* The English student path completed **33 pass / 0 fail** assertions,
  including persistence, validation, a real 409 autosave refusal and retry,
  and locking.
* The Simplified-Chinese student path completed **27 pass / 0 fail**
  assertions and locked.  Its heuristic flagged English personal and team
  names (for example `Jonas Berg` and `Photon Labs`) on Chinese pages; those
  are scenario proper nouns, not evidence of untranslated UI controls.
* The first copied historical harness selected a per-row password reset rather
  than the bulk control, so student logins failed.  That invalid attempt is
  retained separately at `evidence/gate1-browser-2026-10-06/` and was not
  allowed to resolve a round.  The rerun corrected only that test locator.

This is not yet a full browser acceptance or the production-host rehearsal:
it still needs instructor zh-CN/results paths, post-resolution pages, and the
remaining multi-round/production-host coverage.

## Current Gate 2 state

The October 6 recovery handoff reports that release identity, migrations
through `0092`, audit guards, and audit-chain verification passed.  Those
results are retained as prior evidence pending post-change reconfirmation.

At 2026-10-06T04:43Z a fresh production backup was created before the role
repair.  It was validated with `pg_restore --list` on both the database host
and this host.  The retained local protected copy is
`backend/competition_backups/globalstrat_plus-premigrate-role-repair-20261006T044301Z.dump`
with SHA-256
`422b32b34573aaa52bc2a916e8c34f1b25a91de76d0cced9fba21c497123e490`.

The established `ops/provision-app-role.sh` procedure was run as the database
owner on the database host.  The initial grant repair correctly exposed four
application-owned tables, so their ownership was transferred atomically to
the database owner and the provisioner was rerun.  The final retained check
confirms that `globalstrat_plus_app` has `USAGE` but not `CREATE` on `public`,
owns no public objects, and has no `UPDATE`, `DELETE`, or `TRUNCATE` privilege
on `competition_game_deletion_audit_event`; that protected table is now owned
by the database owner.  Transcripts are in the preserved Gate 1 evidence
directory.  No service restart was required because the application
credentials did not change.

## Candidate alignment and post-cutover Gate 2

The originally inspected production checkout later proved to be at
`e171a8b60fd181f1b2be36a2dd48d4a80511426c` while its environment advertised
the competition candidate.  It was preserved in place, including all of its
existing worktrees and untracked files.  A separate, clean detached worktree
was created at
`/home/ubuntu/projects/globalstrat-plus-candidate-f0cf` for
`f0cf7be47264f41c51400c41b113f0237328b0b5`.

Minimal systemd drop-ins now direct the backend, narrative worker, and deadline
scheduler to the candidate worktree.  The two long-running services were
restarted; both running processes have that worktree as their current
directory, and the deadline timer remains active.  The existing
`GIT_REVISION` already named this same candidate and was not edited.

Post-cutover checks all passed from the candidate worktree:

* `check_release_identity`: verified candidate and clean tree.
* `showmigrations core`: migration `0092_reasoning_analysis` applied.
* `install_audit_guards --check`: all append-only guards installed/enabled.
* `verify_audit_chain --json`: 1,179 entries, no problems, no unsealed
  entries, guards present, and external anchor matched.

The check transcript and systemd cutover transcript are retained under the
preserved Gate 1 evidence directory.

## Scheduling and remaining certification

The host crontab still contains the unrelated legacy GlobalStrat v1 minutely
deadline command and was not changed.  It must not be repointed: the v1
repository and credential are separate, and its authentication failure
predates this work.

GlobalStrat+ now has independent deployment definitions for
`globalstrat-deadline-scheduler.service` and its minutely persistent timer.
They use `/etc/globalstrat-plus.env` and intentionally invoke
`check_round_deadlines` without `--auto-process` or `--auto-advance`.
The timer is enabled and active.  Its deliberate first run at 05:35Z closed
only overdue rehearsal round 1 for games 24, 26, and 27 (24 locked submissions
each); the following minutely runs reported no rounds due.  Unit hashes on the
host match the repository copies, and the legacy cron remains untouched.

During the initial unit installation, a cached `sudo` ticket caused the
password input line to be written as the first line of each mode-0644 unit.
This was identified from the systemd parse warning, then both files were
replaced with verified clean copies before the next timer run.  The password
was not printed in transcripts or journal output, but the VM sudo credential
should be rotated because the files were briefly readable to local users.

Next, repeat the Gate 2 release/migration/audit checks after the role repair,
then resume the unfinished current-candidate EN/zh-CN browser acceptance,
calibration, combined-load, deadline, and recovery certification, followed by
the isolated eight-team production-host rehearsal.  Historical four-team
browser evidence at `../globalstrat-ce10-readiness` is not certification for
this candidate.
