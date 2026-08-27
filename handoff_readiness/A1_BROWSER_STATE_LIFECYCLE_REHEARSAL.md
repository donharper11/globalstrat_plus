# A1 browser-state and six-round lifecycle rehearsal

Date: 2026-08-27 UTC  
Candidate: `competition-rc-2026.08.27.1`  
Commit: `86c2ad40fb300a666e154915aa392cb2e56f2ad6`  
Verdict: **FAIL — CR-017, silent loss of an unsaved decision on navigation.**

> **Update — 2026-08-27, CR-017 closed.** The record below is the original
> failing rehearsal. After the `useUnsavedChangesGuard` repair, the identical
> back-navigation scenario was re-run against the fixed production build served
> to the isolated tagged backend. Browser Back during an unsaved Marketing edit
> now raises the discard confirmation *"You have unsaved changes. Leave this
> page and discard them?"* (plus a `beforeunload` guard on tab close / full
> navigation) instead of silently reverting the field. Re-verification evidence:
> `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json`
> (`leave_dialog` populated, `warning_visible: true`, `edit_created: true`,
> `pass: true`) and `evidence/a1-lifecycle-20260827/cr017-regression-sweep.json`
> (all five guarded decision pages render and stay inert when clean). The A1
> verdict is therefore **PASS**; all other scenarios in this record already
> passed and are unaffected by the frontend-only guard change.

## Isolation and scope

The exact tagged source ran on loopback against a disposable PostgreSQL 16
container and a dedicated backup directory. A temporary nginx instance served
the tagged production frontend and proxied only to the isolated Gunicorn
backend. The fixture contained four teams, two identities on Team 1, one
instructor, and exactly six rounds. No live competition record, public service,
or production database was mutated.

The browser exercised student and instructor session expiry, browser
close/return, back navigation during an edit, refresh during an in-flight save,
two tabs writing the same team/round, direct later-round URLs, and student plus
instructor views at open, closed and processed states in every round.

## Results

- **Passed:** browser close and return restored the authenticated route.
- **Passed:** invalid student and instructor sessions converged to their correct
  login pages without a blank or redirect loop.
- **Passed:** refresh during submission recovered to a usable page and did not
  display a false success.
- **Passed:** both duplicate-tab writes received explicit successful outcomes;
  both tabs reloaded to a usable canonical state.
- **Passed:** direct `?round=6` URLs in Rounds 1–5 remained bound to the actual
  server round; Round 6 rendered normally when it became current.
- **Passed:** Rounds 1–6 each traversed open → closed → processed → advance;
  the final advance completed the game. Both role UIs were nonblank at every
  captured state.
- **Failed:** on the Round 1 Marketing page, the probe changed an enabled field
  from `0` to `1`, navigated away, and used browser Back. The application showed
  no leave/discard warning and restored the server value `0`; the unsaved edit
  was silently lost (`back-mid-decision-targeted.json`).

## Integrity record

The six-round fixture finished with all six rounds `processed` and
`FULLY_COMPLETE`. It produced six completed manifests, all containing the exact
tag revision, six checksum-valid backups, 18 operator events with substantive
reasons, and 26 decision events. Backup inventory reported zero invalid or
expired artifacts.

The loopback environment could not reach Google Fonts; those requests timed out
and account for the recorded console resource errors and cold-load delay.
Application API aborts in the trace correspond to the deliberate refresh and
navigation tests. No page exception was recorded.

Evidence: `evidence/a1-lifecycle-20260827/results.json`, its 36 lifecycle/state
screenshots, and the targeted back-navigation JSON/screenshot in the same
directory.
