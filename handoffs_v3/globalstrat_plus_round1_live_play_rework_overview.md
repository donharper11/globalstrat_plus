# GlobalStrat+ Round 1 Live-Play Rework Overview

**Status:** Fix handoffs for dispatch. No implementation in this document.
**Date:** 2026-07-22
**Target platform:** `https://globalstrat.camdani.com`
**Runtime reality:** public `globalstrat.camdani.com` serves the `globalstrat+` frontend and the `.5` VM `globalstrat+` backend on port `8002`.
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Required Reading For Every Agent

Before taking any action, read:

1. `handoffs_v3/globalstrat_plus_round1_live_play_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

This overview records the second Round 1 synthetic live-play attempt. The first rework wave fixed shell routing and instructor entry points. This wave targets completion blockers discovered when four synthetic student teams tried to play Round 1 through the browser.

---

## Operating Rules

- Work in `/home/ubuntu/projects/globalstrat+`.
- Use the public UI for proof: `https://globalstrat.camdani.com`.
- Treat browser-visible behavior as the readiness standard.
- Backend inspection is allowed for diagnosis, persistence checks, and safety confirmation.
- Do not advance, process, reset, archive, or delete game 12 unless explicitly approved.
- Do not inject events unless explicitly approved.
- Record any data changed while testing.
- Verify names, routes, endpoints, model fields, and database columns before wiring.

---

## Current Round 1 State After Synthetic Attempt

Game `12` remains open in Round 1. No team locked/submitted.

Observed draft state during the coordinator check:

| Team | Student | Status |
| --- | --- | --- |
| 18 Zenith Hardware | `student1 / student1pass` | draft submission exists |
| 19 Helix Digital | `student2 / student2pass` | draft submission exists |
| 20 Photon Labs | `student3 / student3pass` | no submission observed |
| 21 Nova Circuit | `student4 / student4pass` | draft submission exists |

Leave this state intact while diagnosing. Before a clean Round 1 replay, use a fresh seeded game or obtain explicit approval before resetting/reseeding game 12.

---

## Findings From The Live-Play Attempt

### Student Completion Blockers

- No synthetic student reached Lock & Submit.
- Finance budget inputs are unreliable from the browser:
  - Strategy budget entered by student1 appeared to save but reloaded as `$0`.
  - Student2 entered budget values but the request persisted zeros.
  - Student4 entered large currency values but saved tiny or zero values.
  - Totals and unallocated budget labels are confusing against the Round 1 budget context.
- R&D Round 1 action is unclear or infeasible:
  - The obvious Create New R&D Platform path shows a `$5.0M` base cost and can be over budget.
  - Existing platform upgrade cards list costs but do not present an obvious clickable, within-budget action.
- Review & Submit explains that work is incomplete, but does not guide a novice through the shortest path to resolve each blocker.
- Dashboard/Guided Next navigation can strand a novice on instructional content instead of opening the required decision form.
- Some route/page load concerns remain intermittent: coordinator reproduced working Supply Chain pages for student2, but earlier agents reported shell-only pages and slow spinners.

### Instructor Monitoring Friction

- Instructor Game Control showed Round 1 open and `0 of 4 teams locked`, which is correct for advance safety.
- The instructor UI presents inconsistent round/status language: workspace says `R1 of 8 IN PROGRESS`, while Game Control shows `CURRENT ROUND 1 of 10` and `STATUS setup`.
- Instructor cannot visibly confirm game identity by game ID in some locations.
- `Students & Logins` appears to count activity/session rows rather than unique people.
- Supply Chain risk rows have formatting issues, including concatenated risk text and blank-looking rows.

---

## Dispatch Sequence

1. `globalstrat_plus_round1_finance_budget_handoff.md`
2. `globalstrat_plus_round1_rd_submit_guidance_handoff.md`
3. `globalstrat_plus_round1_guided_navigation_handoff.md`
4. `globalstrat_plus_round1_instructor_monitoring_polish_handoff.md`
5. `globalstrat_plus_round1_live_reaudit_handoff.md`

Run the re-audit only after the builder handoffs are complete, merged, deployed, and browser-proven.

---

## Round 1 Live-Ready Exit Criteria

Round 1 can be replayed with confidence when:

- Each student can complete a valid set of Round 1 required decisions through the browser.
- Finance inputs persist exactly as entered, with clear units and budget totals.
- R&D presents at least one clear Round 1-feasible action or an honest explanation if no action is possible.
- Review & Submit shows a clear checklist with clickable paths to each unresolved item.
- Dashboard/Guided Next opens the next actionable decision page rather than passive instruction panels.
- Instructor can accurately see game ID, current round, round status, processed-results state, and team lock/readiness counts.
- A clean browser-first replay has no unexplained shell-only pages, no indefinite spinners, no unexplained 5xx, and no team blocked by UI ambiguity.
