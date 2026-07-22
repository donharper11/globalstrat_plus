# GSP-R1-04 Completion Report - Finance Budget Allocation Reliability

**Date:** 2026-07-22
**Branch:** `gsp-r1-04-finance-budget`
**Status:** Complete, browser-proven on the live site
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Summary

Fixed the Finance budget autosave path that could persist stale or corrupted budget values. The page now builds the PATCH payload from the next input state, uses separate debounce timers for budget and financing edits, accepts common currency input formats, and shows visible save/error state instead of silently swallowing failures.

---

## Files Changed

- `frontend/globalstrat-frontend/src/pages/FinancePage.js`

---

## What Changed

- Replaced stale-state budget autosave with `autoSaveBudget(nextBudgetAllocation)`.
- Replaced stale-state financing autosave with `autoSaveFinancing(nextFinancing)`.
- Split the single shared save timer into separate budget and financing timers so edits in one section do not cancel pending saves in the other.
- Added currency input formatting/parsing for raw dollars, comma-formatted dollars, `M`, and `K` shorthand.
- Added visible save states: unsaved, saving, saved, and error.
- Reworded the allocation total line to reference the Round operating budget rather than cash-on-hand unallocated cash.
- Added a short input helper: examples include `2500000`, `$2,500,000`, and `2.5M`.

---

## Build Proof

Ran production frontend build in:

`/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend`

Result: build completed successfully.

Warnings remain from pre-existing lint issues across the app. Finance still has pre-existing unused import warnings for `Statistic`, `Progress`, and `Title`; no compiler failure.

---

## Deploy Proof

Ran:

`./frontend/deploy-frontend.sh`

Result:

- Build complete: 39 files, 26M.
- ECS backup created: `/var/www/globalstrat-backup-20260722-102633`.
- Files rsynced to `/var/www/globalstrat/build`.
- Remote file count matched local file count.
- `index.html` verified present.
- Cloudflare purge skipped because `CF_TOKEN` was not set.
- Live `index.html` referenced the new bundle: `main.a1dcfc65.js`.

---

## Browser Proof

Browser proof used Playwright against the live public site with cache-busted URLs.

### Student 1

Account: `student1 / student1pass`  
Game/team: game `12`, team `18`

First save:

- R&D budget: `1100000`
- Marketing budget: `1200000`
- Strategy budget: `1300000`

After reload, the page displayed:

- `$ 1,100,000`
- `$ 1,200,000`
- `$ 1,300,000`

PATCH response returned HTTP 200 and persisted:

- `rd_budget: "1100000.00"`
- `marketing_budget: "1200000.00"`
- `strategy_budget: "1300000.00"`

Second save/change cycle:

- R&D budget changed down to `900000`
- Marketing budget changed up to `1300000`
- Strategy budget changed up to `1500000`

After reload, the page displayed:

- `$ 900,000`
- `$ 1,300,000`
- `$ 1,500,000`

PATCH response returned HTTP 200 and persisted the matching values.

### Student 4

Account: `student4 / student4pass`  
Game/team: game `12`, team `21`

Tested mixed input formats:

- R&D budget: `$1,400,000`
- Marketing budget: `1.5M`
- Strategy budget: `1600000`

After reload, the page displayed:

- `$ 1,400,000`
- `$ 1,500,000`
- `$ 1,600,000`

PATCH response returned HTTP 200 and persisted:

- `rd_budget: "1400000.00"`
- `marketing_budget: "1500000.00"`
- `strategy_budget: "1600000.00"`

No bad HTTP responses were observed during either proof run.

Screenshots were captured on the coordinator VM:

- `/tmp/globalstrat-student1-finance-after-save.png`
- `/tmp/globalstrat-student1-finance-after-reload.png`
- `/tmp/globalstrat-student1-finance-second-reload.png`
- `/tmp/globalstrat-student4-finance-after-save.png`
- `/tmp/globalstrat-student4-finance-after-reload.png`

---

## Data Changed

The browser proof changed live draft budget allocations in game 12:

- Team 18 Zenith Hardware: R&D `$900,000`, Marketing `$1,300,000`, Strategy `$1,500,000`.
- Team 21 Nova Circuit: R&D `$1,400,000`, Marketing `$1,500,000`, Strategy `$1,600,000`.

No team was locked or submitted. No round was advanced, processed, reset, archived, deleted, or injected.

---

## Residual Risk

- This handoff fixed the Finance budget persistence blocker only. R&D feasibility, Review & Submit guidance, Guided Next navigation, and instructor monitoring polish remain separate Wave 2 handoffs.
- Cloudflare cache was not purged because `CF_TOKEN` was not available. Cache-busted browser proof confirmed the new bundle was reachable.
