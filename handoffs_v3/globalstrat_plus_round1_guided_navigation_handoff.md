# GSP-R1-06 - Student Guided Navigation And Slow-Load Recovery

**Status:** Ready for builder dispatch.
**Scope owner:** Dashboard Guided Next, checklist navigation, page loading/recovery states.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Required Reading Before Work

Before taking action, read:

1. `handoffs_v3/globalstrat_plus_round1_live_play_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

---

## Problem

One synthetic student got stuck on the Dashboard. Left navigation/checklist clicks initially did not open the expected decision pages. Guided Next changed the dashboard content to an instructional panel but did not clearly take the student to the next required form.

Other students and the coordinator reproduced valid nested decision pages, so this may be a timing, state, or click-target issue rather than a route bug. It still matters because novice users follow the visible guidance, not direct URLs.

---

## Required Behavior

1. Dashboard Guided Next must open the next actionable decision page, not just passive instructions, unless the user explicitly chooses to read guidance.
2. Checklist items that represent work to complete must be clickable and route to the exact decision page.
3. Passive onboarding/instruction panels must not trap the user; they need a clear primary action.
4. Slow-loading decision pages must show useful skeleton/loading text and eventually either content, a retry, or an honest unavailable state.
5. Any shell-only recovery screen must identify that the page was not found and offer a one-click path back to the active game/team.
6. Automated and human users should not accidentally open Trade Finance when choosing Finance from the sidebar.

---

## Investigation Targets

Verify names before wiring:

- `frontend/globalstrat-frontend/src/pages/GameDashboard.js`
- `frontend/globalstrat-frontend/src/components/Sidebar.js`
- `frontend/globalstrat-frontend/src/components/ShallowRouteRecovery.js`
- `frontend/globalstrat-frontend/src/contexts/GameContext.js`
- Any checklist/guided-next components used on the dashboard.

---

## Browser Exit Proof

Use `student3 / student3pass` first because this persona saw the navigation problem.

1. Login and start from the dashboard.
2. Click Guided Next.
3. Confirm the user reaches the next actionable decision page or sees a primary button that does so.
4. Return to dashboard and click at least five checklist/sidebar entries:
   - R&D Investment
   - Finance
   - Sourcing
   - Marketing Mix
   - Review & Submit
5. Confirm each renders meaningful content, not shell-only UI.
6. Slow-load pages must resolve or show an honest recovery state.
7. Capture screenshots and note any network errors.

Avoid saving decisions unless necessary for navigation proof. Report any data changed.
