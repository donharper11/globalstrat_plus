# GSP-R1-03 Report — Instructor Control Center Readiness

**Date:** 2026-07-22
**Branch:** `gsp-r1-03-instructor-control` (commit `3bcf3f4`) — deployed to ECS.
**Browser-proven:** `instructor / instructorpass`, `https://globalstrat.camdani.com`, viewport 1440x1000.

## Fix (the one confirmed structural bug)

`/games/:gameId/instructor` was not a route. The student sidebar "Game Control" link
(instructor/admin-only, `Sidebar.js`) pointed at it, so it fell through to the student shell —
post-R1-01, the recovery page — instead of the instructor Game Control.

- `App.js`: added a top-level redirect `/games/:gameId/instructor` -> `/instructor`.
- `Sidebar.js`: the "Game Control" link now goes straight to `/instructor`.

**Proof:** as instructor, `/games/12/instructor` now lands on `/instructor` with the full portal
(10 tabs, Game Control reachable); the student recovery page is no longer shown.

## Verified functional — NO fix warranted (per STANDING-DISCIPLINE: verify before wiring; do not invent)

Most of the overview's instructor findings do **not** reproduce in the current deployed state:

- **Nav reachability (overview: "sidebar does not scroll, entries fall below viewport"):** the
  instructor nav is a horizontal 10-tab bar, and **all 10 tabs are within the 1440px viewport**
  (rightmost tab ends at ~1238px < 1440), all enabled and clickable. No entry is cut off. Not
  reproduced.
- **Game Control** (`/instructor` -> Game Control tab) is comprehensive and usable: current game,
  "CURRENT ROUND 1 of 10", STATUS, TEAMS, team readiness ("0 of 4 teams have locked decisions,
  4 pending"), Round Control (status/deadline/decisions-in/processing) with clearly-staged
  Set-deadline / Close-round / Close-&-process buttons + an explanation of close vs process vs advance,
  a full Round Schedule, and Team Configuration. Meets the handoff's "minimum content" list.
- **Dangerous controls (problem 3):** Activate / Pause / Resume / Reset / Archive / **Delete** game are
  all `Popconfirm`-gated (delete/reset use danger styling, "delete_forever"). Advance / Extend-deadline
  / Inject-event are staged `Modal`s. Not one-click. Satisfied.
- **Empty/loading states (problem 5):** no indefinite "Loading..." on any tab checked; Research Monitor
  ("No research queries yet") and AI Coach ("No alerts found") show honest empty states. No 5xx on any
  instructor page. Satisfied.
- **Supply Chain (problem 6):** present as a top-level tab, functional ("Inject supply-chain event",
  "Per-team supply-chain audit" table). Discoverable. Satisfied.
- **Roster/accounts/team status (problem, "shell-only"):** Students & Logins, Team Overview render real
  tables (team members, index, cash, revenue, decision status). Not shell-only.

## Not fully verified — reported honestly, not fixed

- **Result selector / round-context (overview items: "R1 of 8", "selector defaults to Round 0",
  "scorecard indefinite Loading"):** these were reported on the students' in-progress game 12. The
  instructor account's currently-selected game presents a **setup-state game ("1 of 10, setup")**, and
  I did **not** complete the Switch-Game drill-down (course -> section -> game) to view game 12, so the
  round-selector-default and scorecard-loading on an *in-progress* game remain unverified. No fabricated
  fix. **Recommendation:** confirm the instructor can select game 12, then re-check items 4/5 there. (I
  retract an earlier working hypothesis that the instructor was not associated with game 12 — my
  verification used the wrong auth model and did not confirm it.)

## Data changed
- None. No game advanced/processed/reset/archived/deleted; no event injected; no destructive modal
  confirmed. "Switch Game" is a view action; no alternate game was selected destructively.

## Deploy
- `deploy-frontend.sh` -> ECS `/var/www/globalstrat/build` (backup `/var/www/globalstrat-backup-20260722-094526`).
  Frontend-only change; backend untouched. New JS is fingerprinted so it serves fresh (CF purge skipped,
  no CF_TOKEN).
