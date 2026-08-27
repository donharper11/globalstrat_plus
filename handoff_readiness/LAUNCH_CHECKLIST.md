# Competition launch checklist

Status as of 2026-08-27: **conditional NO-GO pending the unchecked gates below.**
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

- [ ] Commit and tag the exact competition build; record the approved revision and deployment artifact.
- [ ] Set `GIT_REVISION` in the deployed environment and verify a newly generated resolution manifest contains the expected non-empty revision.
- [ ] Approve backup and manifest retention, access control, storage monitoring and secure disposal. Confirm that retention covers the dispute window.
- [ ] Run a final consolidated A1–A8 verification against the tagged candidate and record links to its evidence.
- [ ] Build/deploy the tagged candidate and verify the public frontend/API, migrations, authentication and monitoring. Record rollback artifact and procedure.

## Required before live competition approval

- [ ] Execute the guarded `recover_competition_round` workflow end to end in an isolated environment, not only `--dry-run`: validate, restore, re-run, compare manifests and hashes, verify both audit records, and obtain two-operator sign-off.
- [ ] Conduct a volunteer competition cycle on the tagged build with separate identities and real deadlines. Include deliberate late/missing/duplicate submissions, team correction, deadline extension, outage communications, team deactivation and an operator incident drill.
- [ ] Confirm instructors can identify who submitted what and when, distinguish missing from deliberate empty submissions, and apply published dispute and tie rules without direct database intervention.
- [ ] Reconcile any volunteer findings, rerun affected verification, and obtain engineering, competition-operations and rules-owner sign-off.

## Dependency and parallel-work note

Documentation, team-deactivation implementation, release/retention preparation,
and recovery/volunteer rehearsal preparation can proceed in parallel if each
workstream owns separate files. The complete regression suite and consolidated
A1–A8 pass must follow all code changes. The end-to-end recovery drill requires
the release candidate and configured revision/retention policy. The volunteer
cycle must use the final tagged candidate and finalized operator controls and
rules.
