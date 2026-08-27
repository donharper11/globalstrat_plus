# Competition launch checklist

Status as of 2026-08-27: **A1–A8 gate complete (CR-017 closed).** Remaining
before live competition: the end-to-end recovery drill and the volunteer dry-run
cycle (unchanged, below).
The original CR-001–CR-016 engineering register is closed or accepted; this
checklist tracks the remaining operational path to launch.

## Already evidenced

- [x] CR-001–CR-014 and CR-016 repaired; CR-015 accepted as the documented public-URL constraint (`FIX_LOG.md`).
- [x] All identified student write families coordinate with deadline close and reject a close observed while waiting (`evidence/status-items-1-2.json`).
- [x] Published and implemented tie-break order aligned: performance index, cumulative operating cash flow, cumulative revenue, then final-round resilience; an exact remaining tie shares rank and prize (`evidence/status-items-1-2.json`).
- [x] Expected and 3x multi-identity deadline rehearsals accounted for every request, audited every accepted write, uniformly rejected in-flight late writes and locked all teams (`LOAD_TEST_RESULTS.md`, `evidence/deadline-96.json`, `evidence/deadline-288.json`).
- [x] Concurrent resolution produced exactly one winner, and isolated replay reproduced byte-identical input and output hashes (`evidence/resolution-replay.json`).
- [x] Six-round, FX hedge and R&D order cohorts completed (`EXPLOIT_REPORT.md`).
- [x] EN/ZH browser sweep completed with 48/48 nonblank screens (`FIX_LOG.md`).
- [x] Supported reversible team deactivation/reactivation is instructor/admin
  guarded, reasoned, exactly confirmed, audited, write-blocking and excluded
  from future resolution cohorts.
- [x] Release provenance fails closed in production without an explicit valid
  `GIT_REVISION`; backup inventory is read-only by default and guarded pruning
  is disabled unless explicitly enabled.
- [x] Post-parallel convergence suite passed: 271 tests in 89.173 seconds on a
  clean test database; migration `core.0060_team_participation_status` applied.

## Required before release candidate approval

- [x] Commit and tag the exact competition build: commit
  `86c2ad40fb300a666e154915aa392cb2e56f2ad6`, annotated tag
  `competition-rc-2026.08.27.1`.
- [x] Set `GIT_REVISION` in the deployed environment and verify a newly generated
  rollback-only resolution manifest contains the expected non-empty revision
  (`evidence/release-provenance-verification.json`).
- [x] Approve and configure backup/manifest retention, access control, daily
  integrity/capacity monitoring and guarded disposal. The 90-day backup period
  covers the 24-hour dispute window and extends through final rulings
  (`BACKUP_RETENTION_POLICY.md`).
- [x] Complete the final consolidated A1–A8 verification. A2–A8 pass; CR-017,
  the sole A1 failure, is repaired and the back-navigation scenario re-verified
  against the fixed build (`A1_BROWSER_STATE_LIFECYCLE_REHEARSAL.md`,
  `CONSOLIDATED_A1_A8_VERIFICATION.md`, `evidence/consolidated-a1-a8-20260827.json`,
  `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json`,
  `evidence/a1-lifecycle-20260827/cr017-regression-sweep.json`).
- [x] Build/deploy the CR-017 candidate frontend to the public endpoint with a
  recorded rollback artifact (see `FIX_LOG.md` deploy record). Backend unchanged
  from the tagged candidate; migrations/auth/monitoring already verified for it.

## Required before live competition approval

- [x] Execute the guarded `recover_competition_round` workflow end to end in an
  isolated environment (not only `--dry-run`): validated, restored, re-ran, and
  reproduced a byte-identical result; both operator audit records and the durable
  recovery audit verified. The first end-to-end run exposed three defects
  (RD-01/02/03) which are now fixed and covered by regression tests; the re-run
  passes (`RECOVERY_DRILL.md`, `evidence/recovery-drill-20260827/`). **Two-operator
  sign-off remains outstanding** — a process gate, not a code gate.
- [ ] Conduct a volunteer competition cycle on the tagged build with separate
  identities and real deadlines (deliberate late/missing/duplicate submissions,
  team correction, deadline extension, outage communications, team deactivation,
  operator incident drill). **Scripted precursor done:** `volunteer_cycle_sim.py`
  exercises every one of these mechanics against an isolated stack and passes 8/8
  (`INSTRUCTOR_VISIBILITY_AND_DRYRUN.md`,
  `evidence/volunteer-cycle-sim-20260827/`). The human cycle with real people
  still remains.
- [ ] Confirm instructors can identify who submitted what and when, distinguish
  missing from deliberate empty submissions, and apply published dispute and tie
  rules without direct database intervention. **Verified.** what/when, correction
  and tie-break/leaderboard all work from the UI/API; the missing-vs-empty gap
  (V-1) is now fixed — instructor endpoints and dashboard surface submission_origin
  so a defaulted team is distinguishable without the database (commit 93a09cc).
  Minor open item: the individual submitter (V-2) is still not surfaced (team-level
  visibility only). See `INSTRUCTOR_VISIBILITY_AND_DRYRUN.md`.
- [ ] Reconcile any volunteer findings, rerun affected verification, and obtain engineering, competition-operations and rules-owner sign-off.

## Dependency and parallel-work note

Documentation, team-deactivation implementation, release/retention preparation,
and recovery/volunteer rehearsal preparation can proceed in parallel if each
workstream owns separate files. The complete regression suite and consolidated
A1–A8 pass must follow all code changes. The end-to-end recovery drill requires
the release candidate and configured revision/retention policy. The volunteer
cycle must use the final tagged candidate and finalized operator controls and
rules.
