# GSP-R1-05 Completion Report - R&D Feasible Action And Review Submit Guidance

**Date:** 2026-07-22
**Branch:** `gsp-r1-05-rd-submit-guidance`
**Status:** Complete, browser-proven on the live site
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Summary

Made Round 1 R&D actionable from the browser and improved Review & Submit guidance. The R&D page now gives students a clear path when creating a new platform is over budget: invest in the next level of an existing feature. Review & Submit now uses plain status labels, shows specific guidance, and provides direct Fix buttons for incomplete items.

---

## Files Changed

- `frontend/globalstrat-frontend/src/pages/RDPage.js`
- `frontend/globalstrat-frontend/src/pages/SummaryPage.js`

---

## What Changed

### R&D Investment

- Added a top guidance alert that shows R&D budget remaining and investment slots available.
- Prevented the Create Platform modal from allowing an over-budget platform creation.
- Added `Invest next level` buttons for upgradeable active-platform features.
- New buttons call the existing `rd` decision endpoint with `rd_investments` payloads.
- Existing draft R&D investments are preserved when adding/replacing one feature investment.
- Added a `CURRENT R&D DRAFT` table so students can see what they have saved this round.

### Review & Submit

- Changed raw statuses like `empty` and `configured` into student-facing labels: `Not started`, `Complete`, `Needs review`, and `Blocked`.
- Added plain guidance for incomplete checklist items.
- Added `Fix in ...` buttons that route directly to the relevant decision page.
- Corrected the Strategy Mix route from `/decisions/strategy` to `/decisions/corporate-strategy`.
- Added a clear note above the disabled Lock & Submit button when the round is not ready to lock.

---

## Build Proof

Ran production frontend build in:

`/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend`

Result: build completed successfully.

Warnings remain from pre-existing lint issues across the app, including unused imports and hook dependency warnings. No compiler failure.

---

## Deploy Proof

Ran:

`./frontend/deploy-frontend.sh`

Result:

- Build complete: 39 files, 26M.
- ECS backup created: `/var/www/globalstrat-backup-20260722-103426`.
- Files rsynced to `/var/www/globalstrat/build`.
- Remote file count matched local file count.
- `index.html` verified present.
- Cloudflare purge skipped because `CF_TOKEN` was not set.

---

## Browser Proof

Browser proof used Playwright against the live public site with cache-busted URLs.

### Student 1 R&D Save

Account: `student1 / student1pass`  
Game/team: game `12`, team `18`

Steps:

1. Opened `/games/12/teams/18/decisions/rd`.
2. Confirmed five enabled `Invest next level` buttons rendered.
3. Clicked the first enabled upgrade action.
4. Confirmed PATCH to `/api/games/12/teams/18/decisions/round/1/rd/` returned HTTP 200.
5. Confirmed `CURRENT R&D DRAFT` appeared.
6. Opened Review & Submit.
7. Confirmed R&D displayed as complete and remaining incomplete items displayed Fix buttons.

Saved R&D draft from response:

- `team_platform: 13`
- `feature: 214`
- `method: in_house`
- `amount: 650000.00`
- `target_level: 9`
- `calculated_cost: 650000.00`

### Student 4 R&D Save

Account: `student4 / student4pass`  
Game/team: game `12`, team `21`

Steps:

1. Opened `/games/12/teams/21/decisions/rd`.
2. Confirmed four `Invest next level` buttons rendered.
3. Clicked the first enabled upgrade action.
4. Confirmed PATCH to `/api/games/12/teams/21/decisions/round/1/rd/` returned HTTP 200.
5. Confirmed `CURRENT R&D DRAFT` appeared.

Saved R&D draft from response:

- `team_platform: 16`
- `feature: 212`
- `method: in_house`
- `amount: 600000.00`
- `target_level: 9`

### Review & Submit Fix Link

Account: `student1 / student1pass`

Steps:

1. Opened `/games/12/teams/18/decisions/summary`.
2. Clicked `Fix in Product Portfolio`.
3. Confirmed browser routed to `/games/12/teams/18/decisions/products`.
4. Confirmed Product Portfolio content rendered.

No bad HTTP responses were observed during proof.

Screenshots were captured on the coordinator VM:

- `/tmp/globalstrat-student1-rd-before-invest.png`
- `/tmp/globalstrat-student1-rd-after-invest.png`
- `/tmp/globalstrat-student1-summary-guidance.png`
- `/tmp/globalstrat-student1-summary-fix-route.png`
- `/tmp/globalstrat-student4-rd-after-invest.png`

---

## Data Changed

The browser proof changed live draft R&D decisions in game 12:

- Team 18 Zenith Hardware: one in-house R&D investment, feature `214`, target level `9`, cost `$650,000`.
- Team 21 Nova Circuit: one in-house R&D investment, feature `212`, target level `9`, cost `$600,000`.

No team was locked or submitted. No round was advanced, processed, reset, archived, deleted, or injected.

---

## Residual Risk

- This handoff does not make every remaining Round 1 checklist item complete. Product, marketing, strategy, sourcing, logistics, trade finance, inventory, and financing completion remain part of the broader live-play re-audit.
- The `rd` endpoint replaces the full current R&D investment list for the draft. The UI preserves existing current investments in the payload, but concurrent multi-user editing on the same team could still overwrite a teammate's very recent unsynced R&D edit. This is an existing collaboration risk outside this scoped fix.
