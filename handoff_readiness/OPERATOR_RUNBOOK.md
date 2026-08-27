# Competition operator runbook

This runbook applies to the Phase 2 hardened build. The original Phase 1
findings are retained in `PHASE1_FINDINGS_REGISTER.md`; their current
dispositions and verification are recorded in `FIX_LOG.md`.

## Before the event

- Use only the supported public GlobalStrat URL. Port 8081 is the code-server
  service and is not a competition endpoint.
- Deploy the approved, tagged build and verify that `GIT_REVISION` is populated
  in a newly generated resolution manifest.
- Confirm database-backup retention, available storage, monitoring, the
  bilingual announcement channel, maintenance-mode access, and two named
  recovery approvers.
- Complete the launch gates in `LAUNCH_CHECKLIST.md`. Do not treat the automated
  rehearsal as a substitute for the volunteer dry run.

## Before each round

Confirm the game and round, server UTC time, published deadline, roster and
submission counts. Announce the deadline in both languages and verify monitoring
from a second device. Confirm the supported team-removal/deactivation procedure
before play begins; do not improvise by deleting database rows.

The instructor lock is enforced by student write paths. Deadline close and all
identified student write families share the same database coordination boundary;
requests that were waiting when close committed re-read the closed state and are
rejected uniformly. The final rehearsal evidence is in `LOAD_TEST_RESULTS.md`.

## Close and resolve a round

1. Verify the intended game and round and record the operator reason.
2. Close the round once. Missing submissions are materialised uniformly and
   recorded as `missing_submission_defaulted` audit events.
3. Verify the locked count and investigate any discrepancy before processing.
4. Process once. Resolution creates and verifies a pre-mutation database dump,
   then records the seed, canonical input and output hashes, code revision slot,
   backup path and completion time in the resolution manifest.
5. Verify results and the operator audit record before publishing.

Two simultaneous resolution attempts cannot both run: the rehearsal recorded
one completion and one already-processed rejection. This is a guardrail, not a
reason to issue duplicate process requests deliberately.

## Team disputes a decision or result

Freeze further lifecycle actions for the affected round. Record the game, team,
round, user, reported time, request ID and screenshots. Preserve application,
access and database logs and the pre-resolution snapshot.

Compare the append-only submission audit payload/hash, actor, timestamp, endpoint
and request ID with the resolution input manifest, stored seed and output
manifest. Do not overwrite a disputed submission. If a correction is authorized,
use the logged correction workflow with a substantive reason and retain the
written ruling.

## Submission appears lost

Do not reconstruct it from memory. Check gateway and application logs for the
request ID and response, then inspect the append-only decision audit ledger. If
the server acknowledged an accepted version before the deadline, use that exact
version through the logged correction workflow. If no accepted version exists,
apply the published missing-submission rule uniformly.

## Resolution fails or a scoring defect is confirmed

Stop application workers, schedulers and other database writers and keep the
application in maintenance mode. Preserve logs and database state. Follow
`RECOVERY_RUNBOOK.md`; first execute its guarded dry run, then perform the
approved restore/re-run with two-operator sign-off.

The recovery control validates the manifest, dump path and SHA-256 and requires
maintenance enablement, an instructor/admin identity, a substantive reason and
an exact confirmation token. Do not substitute manual SQL or an unrecorded
process retry.

## Platform unreachable at deadline

Record monitoring timestamps and outage scope. Announce a competition-wide
pause through the predeclared channel. Do not accept decisions by ad-hoc email or
chat. When service is stable, extend the deadline equally for all teams by at
least the outage duration plus the published recovery buffer, record actor and
reason, and announce the new UTC and local deadline in both languages.

## Evidence to retain

Retain operator and decision audit events, resolution manifests, dump files and
SHA-256 sidecars, access/application logs, incident rulings and bilingual event
announcements according to the approved retention policy. Restrict recovery
artifacts because a full database dump can contain credentials and participant
data.
