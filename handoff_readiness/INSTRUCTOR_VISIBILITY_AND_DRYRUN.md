# Instructor visibility (#2) and scripted volunteer cycle (#1)

Date: 2026-08-27 UTC. Both exercises ran against an **isolated** disposable
`postgres:16` (`:15434`) seeded read-only from production, driven through an
isolated Django backend on `:8056`. No production database, service, or
competition record was mutated.

## #2 — Instructor visibility & dispute tooling

Verified against game 24 (24 teams, round 1). Evidence:
`evidence/instructor-visibility-20260827/visibility.json`.

| Capability | Verdict |
|---|---|
| Instructor sees each team's **decision status** and members | Pass (`/instructor/dashboard/`) |
| Instructor sees **what** a team submitted and **when** (`locked_at`) | Pass (`/instructor/teams/{id}/decisions/`) |
| Operator **correction** of a locked submission, without the database | Pass — `unlock` returns the submission to draft, writing `correction_unlock` (decision) and `unlock_submission_for_correction` (operator) audit events |
| **Tie-break / leaderboard** viewable by instructor | Pass — `/leaderboard/round/{n}/`; published order implemented in prior CR work |
| Distinguish **missing** from **deliberately-empty** submissions from the UI/API | **FIXED (V-1)** |
| See **who** on a team submitted (individual) | Gap (V-2) |

### Findings
- **V-1 (P1) — FIXED (commit 93a09cc).** Instructor endpoints now return
  `submission_origin` (`defaulted_missing` / `deadline_locked` / `student_locked`
  / `draft` / `no_submission`, plus a human label), derived from the immutable
  close-round audit events, on both the team-decisions detail view and the
  dashboard; the instructor UI shows an origin tag (a red "Never submitted" for a
  defaulted team). An instructor can now distinguish a missing team from a
  deliberately-empty one without touching the database. Regression test added;
  verified end-to-end on an isolated stack (defaulted_missing vs deadline_locked).
- **V-2 (P2) — FIXED (commit 19716a7).** The instructor team-decisions endpoint
  now returns `locked_by` and the drill-down modal shows the submitter's name.
- **V-3 (P2).** `/api/rounds/{id}/decision-status/` returns HTTP 500 (stale
  legacy view: `Cannot resolve keyword 'round_id'`). The instructor UI does not
  call it, so it is orphaned dead code rather than a live-path break.

## #1 — Scripted volunteer competition cycle

`volunteer_cycle_sim.py` drives one round lifecycle against a running backend and
asserts the system's response to each adversarial event. Re-runnable against any
isolated stack (`GS_SIM_BASE`, `GS_SIM_GAME`). Latest run: **8/8 pass**
(`evidence/volunteer-cycle-sim-20260827/sim_result.json`).

| Injected event | Asserted behaviour | Result |
|---|---|---|
| Deadline extension | students can still submit after the original deadline | Pass |
| Duplicate submission (two concurrent writers, one team) | exactly one canonical submission row, no corruption | Pass |
| Missing submission | team defaulted at close with `missing_submission_defaulted` | Pass |
| Operator correction | deadline-locked submission unlocked by operator, audited | Pass |
| Team deactivation | guarded (action+reason+confirmation), `withdrawn`, excluded from resolution | Pass |
| Late submission (post-close) | rejected (HTTP 403) | Pass |
| Incident drill (accidental close → operator reopen) | round reopened, submissions unlocked, resubmission accepted | Pass |
| Deactivated team excluded from resolution | absent from the processed leaderboard | Pass |

### Observations
- **S-1 (P2) — FIXED (commit 19716a7).** `process_round` now raises a distinct
  `RoundNotReadyError` and the process view returns an actionable **HTTP 400**
  ("Team X has not locked ... Re-lock the team (or close the round) before
  processing") instead of a raw 500 when a team is left unlocked.
- **Lock is strict** (correct): a submission cannot be locked without a complete,
  valid decision set (product portfolio, marketing mix, strategy, budget).
- **No in-app operator broadcast** exists for "outage communications"; this is an
  out-of-band step and belongs in `OPERATOR_RUNBOOK.md`.

### Still human
A real volunteer cycle with people over live deadlines, and the engineering /
competition-ops / rules-owner sign-offs, remain human gates. This script shakes
out the mechanics beforehand; it does not replace the human dry run.

## #1 extended — full multi-round bot playthrough

`full_playthrough_sim.py` runs a complete N-round game with every team a bot that
makes strategy-differentiated decisions (budget split + marketing price/volume per
product-market, across aggressive-R&D / marketing-heavy / balanced / conservative
profiles), with adversarial events injected every round (a missing team, an
operator correction, and a mid-game team deactivation/reactivation), then the
operator closes → processes → advances each round. After every round it asserts
the system stayed healthy.

Latest run — **game 24, 24 bot teams, 6 rounds: all rounds healthy, 0 issues**
(`evidence/full-playthrough-20260827/report.json`):

| Round | process | leaderboard | manifest | decisions | marketing | advance |
|---|---|---|---|---|---|---|
| 1 | 200 | 24 | complete | 23 | 23 | 200 |
| 2 | 200 | 23 | complete | 23 | 23 | 200 |
| 3 | 200 | 24 | complete | 23 | 23 | 200 |
| 4 | 200 | 24 | complete | 23 | 23 | 200 |
| 5 | 200 | 24 | complete | 23 | 23 | 200 |
| 6 | 200 | 24 | complete | 23 | 23 | — |

Round 2's leaderboard correctly drops to 23 (the deactivated team is excluded from
resolution). Each round processed with real LLM narrative generation (DashScope/Qwen)
running in Phase 2. This exercises the engine and full lifecycle under a realistic
competition-scale, multi-round load with diverse decision data — the closest
automated stand-in for the human volunteer cycle. It does not replace it (see the
"different kind of test" limits above: comprehension, incentivised adversarial
behaviour, real duration, operator judgement), but it front-loads the mechanical
and engine risk before volunteers are involved.
