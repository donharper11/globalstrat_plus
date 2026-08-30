# GSP-CRV2-07 — authentication addendum

Addendum to `GSP-CRV2-07_LOAD_REPORT.md` (`c068f9b`). Covers the adopted
authentication position, the acceptance profile that tests it, and the
`preload_app` decision. **The recovery walkthrough and deploy/restore checks
remain outstanding; CRV2-07 is still not complete.**

Evidence: `evidence/load-failure/auth-acceptance.json`,
`auth-acceptance-drive.json`, `instructor-readiness.json`,
`preload-comparison.json`. Checksums verify.

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
| all 96 sessions visible in instructor readiness | 96 | **24 teams, 293 members** |
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

- **Five minutes is close to the minimum that works, not a comfortable
  choice.** A shorter window, a larger cohort, or a slower production host
  would push this over the bar.
- The reference host is 8 cores. **If the deployment host is slower, the
  admission window must be longer**, and that should be established before a
  live competition rather than discovered during one.
- This is a concrete argument for the longer-term alternatives — pre-issued
  high-entropy competition access tokens, or authentication scaled separately —
  since neither depends on arrival luck. Neither is a reason to weaken PBKDF2.

## Instructor readiness

Instructor authenticates through the real login endpoint (200) and the
dashboard returns 200 listing **24 teams and 293 distinct members** against a
field cohort of 96. The dashboard enumerates enrolled members rather than live
sessions, which is what "visible in readiness" means for this product: it
answers "is the cohort present" before round 1 opens.

An earlier attempt returned 403 "Invalid token". That was a harness fault, not
a product one: the token had been minted in a `manage shell` that never
receives the `DJANGO_SECRET_KEY` the stack runs with, so it was signed with one
key and validated against another. Using the login endpoint is both correct and
what an instructor actually does.

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
