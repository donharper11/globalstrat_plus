# GSP-CRV2-07 — authentication addendum

Addendum to `GSP-CRV2-07_LOAD_REPORT.md` (`c068f9b`). Covers the adopted
authentication position, the acceptance profile that tests it, and the
`preload_app` decision. **The recovery walkthrough and deploy/restore checks
remain outstanding; CRV2-07 is still not complete.**

Evidence: `evidence/load-failure/auth-acceptance.json`,
`auth-acceptance-drive.json`, `instructor-readiness.json`,
`preload-comparison.json`. Checksums verify.

> **Revision note.** The instructor-readiness section of this addendum was
> withdrawn and rewritten after audit: it had presented an enrollment count as
> session visibility. The authentication traffic profile below is unchanged and
> was not re-run. See *Instructor readiness* for the correction.

## Adopted position

The PBKDF2 work factor is **unchanged**. 288 simultaneous password checks is
recorded as an **unsupported arrival shape, not supported capacity**. Admission
is staged instead, and the procedure is now in `OPERATOR_RUNBOOK.md` with four
gates added to `LAUNCH_CHECKLIST.md`.

## Acceptance profile — all six points pass

96 field users admitted across a five-minute window, interactive traffic
beginning afterwards on the tokens already held.

| acceptance point | threshold | measured |
|---|---|---|
| 96 users distributed over five minutes | 96 | **96/96**, window 299.2 s |
| interactive traffic begins afterwards | — | 1976 requests, p50 62.7 ms, p95 119.9 ms |
| login p95 | < 2000 ms | **1999.2 ms** |
| no 5xx / transport failures | 0 | **0** at sign-in and afterwards |
| all 96 sessions visible in instructor readiness | 96 | **withdrawn — see below** |
| no reauthentication during the window | 0 | **0 events**, every token unchanged |

Write reconciliation over the interactive phase: **864 acknowledged writes, none
lost, duplicated or unexplained.**

Token lifetime is **8 hours** (`JWT_ACCESS_TOKEN_LIFETIME_HOURS`) with no
refresh endpoint, so a student admitted in the window does not authenticate
again for the rest of a class session.

## The one number that needs a decision

**Login p95 passed by 0.8 ms.** That is not a comfortable margin and should not
be read as one.

96 users spread over 300 seconds is only ~0.3 sign-ins per second, yet p50 was
690 ms and p95 nearly 2 s. A single PBKDF2 verification costs roughly 700 ms on
this hardware, so p95 approaching 2 s means arrivals still coincide: random
spread is not uniform spread, and three or four students landing in the same
second is enough to triple the wait.

Consequences for the procedure now in the runbook:

- **The required operational window is now ten minutes** on the reference
  8-core host. Five minutes is the measured lower bound, not the launch
  procedure: it passed by 0.8 ms and a larger cohort or an unlucky arrival
  cluster consumes that entirely. The runbook and checklist carry ten.
- The reference host is 8 cores. **If the deployment host is slower, the
  window must be longer**, established during preflight by running the
  admission profile on that host rather than assuming these numbers.
- This is a concrete argument for the longer-term alternatives — pre-issued
  high-entropy competition access tokens, or authentication scaled separately —
  since neither depends on arrival luck. Neither is a reason to weaken PBKDF2.

## Instructor readiness — the original claim was withdrawn and repaired

**The claim in the first version of this addendum was wrong.** It reported "all
96 sessions visible in instructor readiness" as passed, citing a dashboard
response listing 24 teams and 293 enrolled members. Two things were wrong with
that:

- The primary artifact, `auth-acceptance.json`, records that readiness request
  returning **403 with zero visible members**. The pass was assembled from a
  second, later artifact.
- That second artifact proves only that an instructor can retrieve the
  **roster**. `Enrollment` membership answers "who is in this class". It does
  not change when anybody signs in, and it cannot distinguish an authenticated
  participant from a missing or stale one.

An enrollment count was relabelled as session visibility. Both artifacts are
preserved unaltered; neither is now described as a session-readiness pass.

### The repair

`core/services/session_readiness.py`, exposed at
`GET /api/games/{game_id}/instructor/session-readiness/` behind `IsInstructor`,
reports roster and sessions under separate names:

| field | meaning |
|---|---|
| `roster.expected_participants` | enrolled, active participants for the cohort |
| `sessions.authenticated` | expected participants holding a live session |
| `sessions.missing` | expected participants with no live session |
| `sessions.stale` | had a session, then idled out or logged out |
| `sessions.duplicate_sessions` | one participant holding more than one live session |
| `sessions.unexpected_active_sessions` | live sessions not on this cohort's roster |
| `ready` | true only when every expected participant holds exactly one usable session |
| `blocking_reasons` | what is outstanding, in words |

"Active" is the model's existing definition — `UserSession.active_qs`: no
`logout_at`, `last_seen_at` within `IDLE_TIMEOUT_MINUTES` (15). It was not
redefined for this. Sessions are filtered by `game_id`, so another cohort's
session cannot satisfy this one.

**Duplicates block `ready` rather than being absorbed.** Two browsers is one
participant; counting it as two would let a cohort look complete while somebody
is still locked out — the same class of error as counting enrolments as
sessions.

### Proof — three-user real-login walkthrough

`session-readiness-walkthrough.json`. Real logins through `/api/auth/login/`,
an authenticated request after each so the heartbeat sets `last_seen_at`, and
the instructor reading the readiness endpoint between stages. The 96-user drive
was not repeated.

| stage | authenticated | missing | stale | duplicate | ready |
|---|---|---|---|---|---|
| none signed in | 0 | 3 | 0 | 0 | false |
| two signed in | **2** | **1** | 0 | 0 | **false** |
| third signs in | **3** | **0** | 0 | 0 | **true** |
| one idled past the timeout | 2 | 1 | **1** | 0 | false |
| one logged out | 2 | 1 | **1** | 0 | false |
| session moved to another cohort | 2 | 1 | 0 | 0 | false |
| one participant, two live sessions | **3** | 0 | 0 | **1** | **false** |

All seven acceptance checks pass. The last row is the substantive one: four
active sessions, three participants, counted as three — not four — with the
duplicate surfaced and blocking `ready`.

Ten focused tests cover the same contract at service and endpoint level,
including that a student receives 403 from the endpoint. The CRV2-04 read
inventory was regenerated for the new route.

### Round-opening gate

`OPERATOR_RUNBOOK.md` now directs operators to open a round on `ready`, with
what to do about each blocking category, and states explicitly that the
dashboard's member list is roster membership and is not evidence that anyone
has signed in. `LAUNCH_CHECKLIST.md` gates on `ready` true with `missing`,
`stale` and `duplicate_sessions` all zero.

## preload_app — reverted

Measured both ways on identical stacks, against a rule fixed **before** the run:
keep only if it saves more than one second of time-to-warm.

| | preload on | preload off |
|---|---|---|
| settled at | 38.65 s | **31.64 s** |
| slow requests over 1 s | 29 | 31 |
| slowest request | 1328 ms | 1244 ms |

It saves nothing and is marginally slower, within noise either way. **Reverted.**
It had been adopted to remove a worker cold start that later proved to be
sign-in contamination — the unproven change that should not survive on the
reasoning that it is correct in principle.

**The safety check was inconclusive and is recorded as such.** Only one backend
pid was visible at sample time, because Django opens a connection per request
and `CONN_MAX_AGE` is unset, so no worker connection existed to observe. That
same fact is why the hazard cannot arise: nothing is open at fork time, so
nothing is inherited across the fork. This is reasoning plus an inconclusive
measurement, not a passed test.

## No load profile was re-run

The 288-session steady-state profile was not repeated. Reverting `preload_app`
changes worker start behaviour only; the field and margin measurements exclude
sign-in and warm-up and describe steady-state request handling, which an import
strategy does not change. Worker count (32), database behaviour and
authentication are untouched.

## Harness faults corrected during this work

Recorded because two nine-minute drives were lost to them and the git history
shows the repeats.

1. **A stray host-side Django import** in the runner crashed the run after the
   drive had completed and the stack was torn down.
2. **A token signed with the wrong key**, as above.

Both were auxiliary steps destroying a completed primary measurement. The
runner now **writes the drive to evidence the moment it returns**, and secondary
checks record their status and error without raising. Readiness was also split
into its own two-minute check, since it asks about enrolment and does not need
the traffic drive.

## Still outstanding

- Five failure injections: database loss during resolution, backend restart
  after a committed Phase 1, disk-full/backup failure, deadline partition or
  session expiry during submission, one concurrent-operator conflict.
- Deploy/restore walkthrough: backup and restore/replay, rejection of an
  incompatible old-revision dump, deploy-freeze procedure executable as written.
