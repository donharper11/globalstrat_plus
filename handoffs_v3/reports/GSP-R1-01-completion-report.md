# GSP-R1-01 Completion Report — Student Routing & Deep-Link Recovery

**Date:** 2026-07-22
**Branch:** `gsp-r1-01-student-routing` (commit `cd2eccf`)
**Deployed:** frontend build rsynced to ECS (backup `/var/www/globalstrat-backup-20260722-090956`); backend reloaded (gunicorn HUP, master 408244).
**Browser-proven:** `student1 / student1pass`, game 12 / team 18, `https://globalstrat.camdani.com`.

## Files changed
- `frontend/globalstrat-frontend/src/components/ShallowRouteRecovery.js` (NEW) — catch-all recovery component.
- `frontend/globalstrat-frontend/src/App.js` — import + `<Route path="*" element={<ShallowRouteRecovery/>}>` at the end of the student inner `<Routes>`.
- `frontend/globalstrat-frontend/src/pages/GameDashboard.js` — Strategy Mix shortcut `/decisions/strategy` (dead route) -> `/decisions/corporate-strategy`.
- `backend/core/views/decisions.py` — `DecisionSubmissionView.get`: no-draft state returns typed empty `200 {}` instead of `404` (line ~383 POST 404 left untouched).

## Browser actions verified
- `/sourcing` (shallow) -> redirects to `/games/12/teams/18/decisions/sourcing`; page renders real content (832 chars after load, ~5-7s spinner first).
- Unknown route `/zzz-not-a-route` -> honest recovery screen with "Open my active game" button (not shell-only).
- Stale `/games/12/teams/18/decisions/strategy` -> recovery screen (not shell-only).
- Dashboard checklist shortcuts, none shell-only:
  - R&D Investment -> `/decisions/rd`
  - Product Portfolio -> `/decisions/products`
  - Marketing Mix -> `/decisions/marketing`
  - **Strategy Mix -> `/decisions/corporate-strategy`** (was the broken `/decisions/strategy`)
  - Finance -> `/decisions/finance`
  - Review & Submit -> `/decisions/summary`
- No-draft lookup `GET /api/games/12/teams/18/decisions/round/1/` now returns **200** (was 404). No 404 on the round endpoint in the network capture.

## Data changed
- None. No games advanced/reset/archived; no events injected. Only normal read traffic during the walkthrough.

## Deploy actions
- `npm run build`; `deploy-frontend.sh --skip-build` -> ECS `/var/www/globalstrat/build` (backup created). Cloudflare purge skipped (CF_TOKEN unset); new JS is fingerprinted (`main.76a84d56.js`) so it serves fresh.
- Backend reloaded via `kill -HUP <gunicorn master>` (preload_app off -> workers re-import). Non-interactive sudo was unavailable, so `systemctl restart` was not used; service healthy on `:8002`.

## Unresolved risks / notes
- **Backend durability:** the 404->200 change is committed on the feature branch and picked up by the running/reloaded workers (working tree is on the branch). If the repo is ever checked out to `main` and the service restarted, it reverts to 404 until the branch merges. **Recommend merging `gsp-r1-01-student-routing` to `main`** to make it durable. (Frontend is already deployed as a static build, independent of git.)
- **Not merged to main:** left on the feature branch per STANDING-DISCIPLINE (merge after verification / re-audit). Recommend running GSP-R1-Audit, then merge.
- **SourcingPage slow load** (~5-7s spinner before content). Routing is correct; slow/thin decision-page content is GSP-R1-02 scope, not this handoff.
- **Cloudflare cache** not purged (no CF_TOKEN); fingerprinted assets serve fresh. Hard-reload / purge CF if a stale index.html appears.
