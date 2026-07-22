# GSP-R1-06 Completion Report - Student Guided Navigation And Slow-Load Recovery

**Date:** 2026-07-22
**Branch:** `gsp-r1-06-guided-navigation`
**Status:** Complete, browser-proven on the live site
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Summary

Improved the dashboard path that previously left student3 stuck on passive onboarding/instructional content. The dashboard now shows an explicit Next Required Action card built from the existing decision checklist state, and the onboarding modal can be dismissed through the standard close control. Demo-user onboarding dismissal is remembered for the browser session.

---

## Files Changed

- `frontend/globalstrat-frontend/src/pages/GameDashboard.js`
- `frontend/globalstrat-frontend/src/components/OnboardingModal.js`

---

## What Changed

- Added a `NEXT REQUIRED ACTION` dashboard card.
- The card chooses the first non-complete required decision from the existing decision checklist and routes directly to that page.
- Changed checklist status text from raw values such as `empty` to student-facing labels: `Not started`, `Complete`, `Needs review`, and `Blocked`.
- Made the onboarding modal closable through Ant Design's standard close control.
- Added session-level dismissal for demo users so the modal does not keep blocking the dashboard in the same browser session.

---

## Build Proof

Ran production frontend build in:

`/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend`

Result: build completed successfully.

Warnings remain from pre-existing lint issues across the app. No compiler failure.

---

## Deploy Proof

Ran:

`./frontend/deploy-frontend.sh`

Result:

- Build complete: 39 files, 26M.
- ECS backup created: `/var/www/globalstrat-backup-20260722-104451`.
- Files rsynced to `/var/www/globalstrat/build`.
- Remote file count matched local file count.
- `index.html` verified present.
- Cloudflare purge skipped because `CF_TOKEN` was not set.

---

## Browser Proof

Browser proof used Playwright against the live public site with cache-busted URLs.

Account: `student3 / student3pass`  
Game/team: game `12`, team `20`

Steps:

1. Logged in and opened the dashboard.
2. Confirmed onboarding modal rendered with a standard close control.
3. Closed the modal.
4. Confirmed `NEXT REQUIRED ACTION` rendered.
5. Confirmed the primary action read `Continue to 1. R&D Investment`.
6. Clicked the primary action.
7. Confirmed browser routed to `/games/12/teams/20/decisions/rd`.
8. Returned to dashboard and clicked these target links:
   - R&D Investment -> `/games/12/teams/20/decisions/rd`
   - Finance -> `/games/12/teams/20/decisions/finance`
   - Sourcing -> `/games/12/teams/20/decisions/sourcing`
   - Marketing Mix -> `/games/12/teams/20/decisions/marketing`
   - Review & Submit -> `/games/12/teams/20/decisions/summary`

All target routes matched expected nested game/team decision routes. No bad HTTP responses were observed.

Screenshot captured on the coordinator VM:

- `/tmp/globalstrat-student3-dashboard-next-action.png`

---

## Data Changed

None. This proof used navigation only and did not save decisions, lock a team, advance/process a round, reset/archive/delete a game, or inject events.

---

## Residual Risk

- This handoff does not address the remaining instructor monitoring polish in GSP-R1-07.
- Slow page loads still exist on some decision pages, but the tested links resolved to valid pages rather than shell-only dead ends.
