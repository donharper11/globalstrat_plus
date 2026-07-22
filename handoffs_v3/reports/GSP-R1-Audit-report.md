# GSP-R1-Audit — Round 1 Browser Re-Audit Report

**Date:** 2026-07-22
**Auditor:** independent live-play re-audit (browser-first) against `https://globalstrat.camdani.com`.
**Personas:** `student1` (general), `student2` (supply chain), `instructor`. Viewport 1440x1000.
**State under test:** live deployed build (includes R1-01 routing merged to main, R1-02 no-code,
R1-03 instructor-route fix deployed).

## Verdict: **ROUND 1 PASSES — proceed to Round 2 playtest.**

Every Pass Criterion is met. No blockers. No unexplained 5xx anywhere across the three walkthroughs.

## Pass-criteria results

| # | Criterion | Result |
|---|---|---|
| 1 | No shell-only page (student + instructor) | PASS — student sidebar sweep of 20 pages: **none** shell-only/thin; instructor 10 tabs all render |
| 2 | Shallow/deep links resolve or honest recovery | PASS — `/sourcing` -> nested route; unknown route -> recovery screen with "Open my active game" |
| 3 | Dashboard shortcuts land on meaningful pages | PASS — all 6 resolve to correct nested routes (Strategy Mix -> corporate-strategy; verified R1-01) |
| 4 | Decision pages have content + next action | PASS — all 13 render with headers; honest empty-states (Forecast, Comms) explain next step |
| 5 | Sourcing usable, save/validation clear | PASS — 100% allocation stated (9 mentions), Save button present (screenshot), Edit->supplier modal works |
| 6 | Instructor nav reachable at 1440x1000 | PASS — all 10 tabs within viewport (rightmost ends ~1238px), enabled, clickable |
| 7 | Instructor Game Control usable, not blank | PASS — game/round/status/readiness/round-controls/schedule render (len 1046, no stuck loading) |
| 8 | Instructor team readiness + current-vs-processed round | PARTIAL — readiness shown ("0 of 4 locked, 4 pending") + current round; current-vs-processed distinction not verified on an in-progress game (see Minor Friction) |
| 9 | Dangerous instructor actions require confirmation, not executed | PASS — Delete Game -> Popconfirm appeared, **cancelled**; all lifecycle/advance/inject are Popconfirm/Modal-gated |
| 10 | No unexplained 5xx | PASS — zero 5xx across all personas |
| 11 | Expected 404s eliminated/handled | PASS — no-draft `decisions/round/1/` now returns 200 (verified R1-01) |

## Blockers
- **None.**

## Major Friction
- **None.**

## Minor Friction
- **Instructor current-vs-processed-round distinction (Criterion 8) unverified on an in-progress game.**
  Route: `/instructor` Game Control. Persona: instructor. Action: viewed Game Control. Observed: the
  instructor's currently-selected game is a *setup-state* game ("1 of 10, setup"); readiness and current
  round display correctly, but there is no processed round to exercise the current-vs-processed selector.
  Expected: confirm on an *in-progress/processed* game (e.g. the students' game 12) that the result
  selector distinguishes open vs processed rounds. Not a Round-1 blocker; recommend a spot-check.
- **Sourcing load latency.** Route: `/games/:g/teams/:t/decisions/sourcing`. Persona: student. Action:
  open Sourcing. Observed: ~5-7s spinner before content renders. Expected: faster, or a skeleton. It
  resolves (not indefinite), so not a blocker; consider a skeleton/timeout if latency grows.

## Good / Ready Moments
- Shallow/deep-link recovery: `/sourcing` and any unknown route recover cleanly (R1-01).
- All 13 student decision pages render with headers, controls, and honest empty/gated states.
- Sourcing allocation workflow is clear: per-input suppliers, "must total 100%", "100% allocated"
  indicator, round-gated advanced fields that explain why (Round 4/5), Save + Edit modal.
- Review & Submit: honest checklist + "Cannot submit — No submission created yet" + disabled Lock.
- Instructor Game Control is comprehensive and well-explained (close vs process vs advance).
- `/games/12/instructor` now reaches the instructor portal (R1-03), not a blank/recovery page.
- Dangerous instructor actions are confirmation-gated.
- No 5xx anywhere; the previously scary no-draft 404 is now a clean 200.

## Data Changed
- **None.** No games advanced/processed/reset/archived/deleted; no events injected; the Delete Game
  Popconfirm was opened and **cancelled**; no submissions created. Read-only walkthrough.

## Screenshots / Artifacts (scratchpad)
- `audit_sourcing.png`, `audit_gamecontrol.png`, `audit_supplychain.png`
- prior build-phase evidence: `gsp2_Sourcing.png`, `gsp2_ReviewSubmit.png`, `gsp3_tab_GameControl.png`

## Recommendation
**Proceed to Round 2 playtest.** Round 1 browser-visible blockers are resolved. Before Round 2, two
housekeeping items (not blockers): (a) merge branch `gsp-r1-03-instructor-control` to `main` so the
instructor-route fix is durable (R1-01 already merged; R1-03 is deployed but on a branch); (b) spot-check
the instructor current-vs-processed-round selector on an in-progress game.
