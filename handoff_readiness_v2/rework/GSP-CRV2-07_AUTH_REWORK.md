# GSP-CRV2-07 authentication addendum rework

## Decision

**FAIL / REWORK — readiness only.** The authentication traffic profile remains
accepted and must not be repeated.

## Blocking defect

The addendum marks “all 96 sessions visible in instructor readiness” as passed
using a dashboard response that lists 24 teams and 293 enrolled members. That
endpoint reports roster membership, not authenticated sessions.

The primary `auth-acceptance.json` is explicit: its readiness request returned
403 and recorded zero visible members. `instructor-readiness.json` later proves
only that an instructor can retrieve the roster. Combining those artifacts
does not prove that the instructor can distinguish authenticated, missing or
stale participants before opening the round.

## Required repair

Extend the instructor readiness response/UI using the existing `UserSession`
model and its active-session definition. For the selected game/cohort expose:

- expected enrolled participants;
- uniquely authenticated active participants;
- missing participants;
- stale/logged-out participants;
- duplicate active sessions, if any;
- `ready` only when every expected active participant has exactly one usable
  session, or the documented instructor override is exercised.

Roster membership and authentication readiness must remain separately named.
Do not relabel an enrollment count as session visibility.

## Focused acceptance

Use a small real-login walkthrough; do not repeat the 96-user drive:

1. Create at least three expected enrolled students.
2. Log in two through the real login endpoint and make an authenticated request
   so `last_seen_at` is current.
3. Prove readiness reports 2 authenticated, 1 missing, and `ready=false`.
4. Log in the third and prove 3 authenticated, 0 missing, `ready=true`.
5. Prove a stale or logged-out session is not counted active.
6. Prove another game/section's session cannot satisfy this cohort.
7. Prove duplicate sessions are surfaced rather than double-counted as users.

Add focused endpoint/service tests for the same contract. Update the runbook's
round-opening gate to consume this readiness state.

## Admission window disposition

The measured five-minute profile technically passes but has only 0.8 ms of p95
margin. Make **10 minutes the required operational admission window** on the
reference 8-core host; five minutes is the measured lower bound, not the launch
procedure. Slower hosts must establish a longer window during preflight. This
is a runbook/checklist correction and does not require another latency run.

## Evidence/report correction

- Preserve the existing auth profile as immutable evidence.
- Add a separate readiness-walkthrough artifact from the repaired endpoint.
- Correct the addendum so the old roster-only artifact is not described as a
  session-readiness pass.
- Regenerate checksums, verify the inventory and submit from a clean revision.

No field/margin load rerun, 96-user authentication rerun, recovery drill,
deploy/restore walkthrough, full suite or unrelated test is authorized by this
rework.
