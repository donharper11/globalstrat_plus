# GSP-R1-03 — Instructor Control Center Readiness

**Status:** Ready for builder dispatch.
**Scope owner:** Instructor Round 1 browser workflow.
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

Synthetic instructor walkthrough found the instructor experience is not Round 1 ready:

- Instructor sidebar does not scroll at `1440x1000`, hiding key pages below viewport.
- `Instructor > Game Control` route `/games/12/instructor` renders blank.
- Roster/account/team/config-style views appear shell-only or blank.
- Instructor cannot reliably find round controls, roster readiness, event injection, or supply-chain
  monitoring through normal UI.
- Dashboard says `R1 of 8 IN PROGRESS`, while result selector defaults to `Round 0`.
- Scorecard panels can show indefinite `Loading...`.
- Decision checklist says `empty` without team-level readiness counts or next action guidance.

---

## Required Behavior

1. Instructor navigation must be fully reachable at normal laptop size (`1440x1000`).
   The sidebar or content area must scroll where needed.

2. `/games/12/instructor` must render a usable Instructor Control / Game Control landing page.
   Minimum content:
   - current game
   - current round
   - round status
   - team readiness/submission summary
   - safe round actions, clearly disabled or protected if not ready
   - links/cards to roster, student accounts, team status, supply-chain panel, event injection

3. Dangerous controls must not be casual one-click actions.
   Round advance/process/reset/archive/delete/inject actions need confirmation or clearly staged
   modals.

4. Instructor dashboard result selectors must distinguish:
   - current open decision round
   - latest processed results round

5. Empty/loading states must be explicit:
   - "No Round 1 submissions yet"
   - "Round 0 baseline results only"
   - "Supply-chain impacts appear after an event fires or a round is processed"
   - no indefinite `Loading...`

6. Supply Chain instructor panel must be discoverable from normal nav and must explain what an
   instructor can inspect or stage in Round 1.

---

## Suggested Investigation Targets

Verify before wiring:

- `frontend/globalstrat-frontend/src/pages/InstructorDashboard.js`
- `frontend/globalstrat-frontend/src/components/InstructorRoute.js`
- `frontend/globalstrat-frontend/src/components/Sidebar.js`
- `frontend/globalstrat-frontend/src/components/StudentAccountsPanel.js`
- `frontend/globalstrat-frontend/src/components/instructor/InstructorSCPanel.js`
- `frontend/globalstrat-frontend/src/api/instructor.js`
- `backend/core/views/instructor_sc.py`
- `backend/core/views/round_control.py`
- `backend/core/views/instructor_accounts.py`

Backend changes are allowed only if needed to support browser-visible instructor state.

---

## Browser Exit Proof

Use `instructor / instructorpass`.

1. Login through the public frontend.
2. At `1440x1000`, confirm every instructor nav entry is reachable without zooming.
3. Open `Game Control`; confirm it is not blank and shows current game/round/readiness.
4. Open roster/account/team status pages if present.
5. Open Supply Chain panel.
6. Open event injection modal/control, then cancel. Do not inject.
7. Open round advance/process controls, then cancel. Do not advance.
8. Confirm no indefinite loading panels remain on the instructor landing page.
9. Capture screenshots for the main Instructor Control page and Supply Chain panel.

Do not advance, process, reset, archive, delete, or inject during proof.

