# GSP-R1-01 — Student Routing & Deep-Link Recovery

**Status:** Ready for builder dispatch.
**Scope owner:** Student routing, dashboard shortcuts, and no-draft browser noise.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`

---

## Required Reading Before Work

Before taking action, the assigned agent must read:

1. `handoffs_v3/globalstrat_plus_round1_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

The overview gives the Round 1 playtest context and sequencing. `STANDING-DISCIPLINE.md` is binding: verify before wiring, do not invent names, report mismatches explicitly, preserve migration hygiene, and prove changes through browser-visible behavior.

---

## Problem

Synthetic Round 1 student walkthrough found that shallow routes such as `/sourcing` render only
the app shell/sidebar. Valid student pages require nested game/team routes, for example:

`/games/12/teams/18/decisions/sourcing`

Dashboard shortcuts and direct route entry must not strand students on shell-only pages.

The browser also repeatedly shows a `404` for the normal no-draft state:

`GET /api/games/12/teams/18/decisions/round/1/`

Even if this is backend-benign, it reads as a browser-visible failure during live play.

---

## Required Behavior

1. If a logged-in student visits a shallow decision route such as:
   - `/sourcing`
   - `/logistics`
   - `/trade-finance`
   - `/inventory`
   - `/rd`
   - `/products`
   - `/marketing`
   - `/corporate-strategy`
   - `/market-strategy`
   - `/finance`
   - `/forecast`
   - `/communications`
   - `/summary`

   then the frontend should either:
   - redirect to the active nested route using the student's active `game_id` and `team_id`, or
   - show an honest recovery page with a primary button to open the active game/team page.

2. Dashboard shortcut buttons must navigate to the same valid nested routes as the sidebar.

3. No valid route should render only the shell/sidebar with no page body.

4. The no-main-draft lookup should not produce scary browser noise in normal Round 1 use.
   Acceptable fixes include:
   - backend returns a typed empty-state `200`, or
   - frontend handles the `404` as expected and does not surface it as an error state.

---

## Suggested Investigation Targets

Verify before wiring:

- `frontend/globalstrat-frontend/src/App.js`
- `frontend/globalstrat-frontend/src/components/Sidebar.js`
- `frontend/globalstrat-frontend/src/pages/GameDashboard.js`
- `frontend/globalstrat-frontend/src/contexts/GameContext.js`
- `frontend/globalstrat-frontend/src/contexts/DecisionContext.js`
- `frontend/globalstrat-frontend/src/api/decisions.js`

Do not assume route names. Inspect current React routes and navigation helpers first.

---

## Browser Exit Proof

Use `student1 / student1pass`.

1. Login from `https://globalstrat.camdani.com/login`.
2. Visit `/sourcing` directly.
3. Confirm it redirects or recovers to a meaningful active-game Sourcing page.
4. Click dashboard shortcut buttons for:
   - R&D Investment
   - Product Portfolio
   - Marketing Mix
   - Strategy Mix / Corporate Strategy
   - Finance
   - Review & Submit
5. Confirm none land on shell-only pages.
6. Capture browser network failures. Any remaining `404` must be explained and expected.

Report changed files, screenshots, and any remaining route that still renders shell-only.

