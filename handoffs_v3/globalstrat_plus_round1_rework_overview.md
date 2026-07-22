# GlobalStrat+ Round 1 Synthetic Playtest Rework Overview

**Status:** Fix handoffs for dispatch. No implementation in this document.
**Date:** 2026-07-22
**Target platform:** `https://globalstrat.camdani.com`
**Runtime reality:** public `globalstrat.camdani.com` currently serves the `globalstrat+`
frontend and the `.5` VM `globalstrat+` backend on port `8002`.
**Goal:** get the platform ready for a real 1-4 round live-play rehearsal by first clearing
Round 1 browser-visible blockers.

---

## 1. Verification Philosophy

This rework is browser-first. Treat the frontend as the truth surface:

- If a student or instructor cannot complete the workflow from the browser, the platform is not
  live-ready.
- Backend checks are allowed only to diagnose a browser-observed failure or to verify that a fix
  has not broken service health.
- Synthetic users should behave like novice participants, not code auditors.
- Pause after each round's walkthrough. Do not advance to Round 2 until Round 1 blockers are fixed
  and audited.

---

## 2. Synthetic Round 1 Findings

### Student Findings

Observed with `student1 / student1pass` on game `12`, team `18`, current round `1`.

- Shallow routes such as `/sourcing` render only the app shell/sidebar.
- Real sidebar clicks navigate to nested routes such as
  `/games/12/teams/18/decisions/sourcing`.
- Dashboard shortcut buttons and/or direct routes can strand a student on shell-only pages.
- Student A reported many pages as blank/thin after navigation:
  Sourcing, Logistics, Trade Finance, Inventory, R&D Investment, Marketing Mix, Corporate Strategy,
  Market Strategy, Finance, Company Forecast, Stakeholder Communications, Review & Submit.
- Quick reproduction showed nested Logistics, Trade Finance, Inventory, and Product Portfolio do
  render content; Sourcing still looked unusually thin and needs focused verification.
- Repeated browser-visible `404` appears for:
  `/api/games/12/teams/18/decisions/round/1/`
  when no main draft exists.
- Competitive Intelligence and Leaderboard were reported as shell-only or empty in one pass.
- Market Research stakeholder section appeared stuck on loading in one pass.

### Instructor Findings

Observed with `instructor / instructorpass`.

- Instructor sidebar does not scroll at normal laptop size (`1440x1000`); key entries fall below
  the viewport.
- `Instructor > Game Control` route `/games/12/instructor` opens blank.
- Direct instructor routes for roster/account/team/config-style views render shell-only or blank.
- Instructor cannot reliably find round controls, roster readiness, event injection, or supply-chain
  monitoring through normal UI.
- Instructor dashboard shows `R1 of 8 IN PROGRESS`, but the main dashboard selector defaults to
  `Round 0`, which is confusing for monitoring.
- Scorecard panels can show indefinite `Loading...`.
- Decision checklist says `empty` without team-level submission count or readiness context.
- Some result-like pages show CSV/export affordances when no data exists.

---

## 3. Dispatchable Builder Handoffs

1. **GSP-R1-01 Student Routing & Deep-Link Recovery**
   - File: `globalstrat_plus_round1_student_routing_handoff.md`
   - Scope: shortcut/deep-link route handling, shell-only route recovery, benign draft 404 cleanup.

2. **GSP-R1-02 Student Decision Page Readiness**
   - File: `globalstrat_plus_round1_student_decision_pages_handoff.md`
   - Scope: verify/fix Round 1 student decision pages, especially Sourcing and pages reported thin
     or blank.

3. **GSP-R1-03 Instructor Control Center Readiness**
   - File: `globalstrat_plus_round1_instructor_control_handoff.md`
   - Scope: instructor nav scroll, Game Control route, roster/readiness/round controls, supply-chain
     instructor panel discoverability.

4. **GSP-R1-Audit Round 1 Re-Audit**
   - File: `globalstrat_plus_round1_reaudit_handoff.md`
   - Scope: browser-first re-test after builders complete. This should be run by a separate agent
     or by the coordinator after implementation.

---

## 4. Ground Rules For Builders

- Work in `/home/ubuntu/projects/globalstrat+`.
- Do not work in the foundational `/home/ubuntu/projects/globalstrat` repo unless explicitly asked.
- Preserve the current public deployment contract unless instructed otherwise:
  `globalstrat.camdani.com` -> ECS static build -> FRP -> `.5:8002` plus backend.
- Do not advance live rounds during fixes.
- Do not reset/archive/delete live games.
- Use the seeded Round 1 playtest accounts:
  - `student1 / student1pass`
  - `student2 / student2pass`
  - `instructor / instructorpass`
- Use browser screenshots or logs as proof.
- Every completed builder handoff must include:
  - files changed
  - browser actions verified
  - any data changed
  - unresolved risks

---

## 5. Round 1 Exit Criteria

Round 1 can proceed to live-play rehearsal only when:

- Student shallow/deep links recover into valid game/team nested routes or show an honest recovery
  screen with a one-click path back into the active game.
- Dashboard shortcuts never strand students on shell-only pages.
- All visible Round 1 decision pages render meaningful content, instructions, and controls or an
  honest unavailable/locked state.
- The draft lookup no longer appears as a scary browser failure for the normal no-draft state.
- Instructor sidebar is fully reachable at `1440x1000`.
- `/games/12/instructor` shows a usable Game Control/Instructor Control landing page.
- Instructor can see team readiness, current round, safe/unsafe round actions, and supply-chain
  monitoring entry points without direct URL guessing.
- Browser walkthroughs for student and instructor have no unexplained blank pages, indefinite
  loading panels, or 5xx responses.

