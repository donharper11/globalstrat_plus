# GSP-R1-07 Follow-Up — Round/Status Alignment Report

Date: 2026-07-22
Target: `https://globalstrat.camdani.com`
Live bundle proven: `static/js/main.a4bfe251.js`

## Issue

The GSP-R1-08 re-run left one real instructor/student mismatch:

- Student shell showed `R1 of 8, IN PROGRESS`.
- Instructor Game Control showed `Decision round 1 of 10 ... setup`.

Read-only database check for game 12 showed the authoritative state:

- Game 12: `active`
- Current round: `1`
- Scenario decision rounds: `10`
- Round 1 status: `open`

So the UI was mixing three different concepts: scenario round count, round-open status, and game lifecycle status.

## Fix

Changed frontend only:

- `GameContext.js`
  - derives `totalRounds` from the real `/rounds/?game_id=...` response instead of relying on hardcoded UI totals.
- `GameStatusBar.js`
  - uses `totalRounds` instead of hardcoded `8`.
  - labels open decision rounds as `DRAFT OPEN` instead of generic `IN PROGRESS`.
- `components/design-system/TopBar.jsx`
  - uses `totalRounds` instead of hardcoded `8`.
  - uses the same student-facing status wording.
- `InstructorDashboard.js`
  - syncs `gameStatus` from the instructor dashboard response.
  - separates `Round status` from `Game status`.
  - describes the current state as: decision round is open for student decisions, game status is active.

No game data was changed.

## Build And Deploy

- `npm run build` passed with pre-existing lint warnings.
- Deployed using `./frontend/deploy-frontend.sh`.
- Latest deploy backup: `/var/www/globalstrat-backup-20260722-150930`.
- Cloudflare purge skipped because `CF_TOKEN` is not set.

## Browser Proof

Live proof against `static/js/main.a4bfe251.js`:

```json
{
  "studentHasR1Of10": true,
  "studentHasDraftOpen": true,
  "studentStillHardcoded8": false,
  "instructorHasRound10": true,
  "instructorHasOpenForDecisions": true,
  "instructorHasActiveGame": true,
  "instructorShowsSetupConflict": false,
  "bad": []
}
```

Observed student snippet:

- `R1 of 10DRAFT OPEN`

Observed instructor snippet:

- `Decision round 1 of 10 is open for student decisions. Game status: active. Latest processed results round: 0.`

Screenshots captured on verifier host:

- `/tmp/globalstrat-student-round-status-aligned-final.png`
- `/tmp/globalstrat-instructor-round-status-aligned-final.png`

## Data Safety

No game advance, process, reset, archive, delete, event injection, lock, or submit action was executed.
