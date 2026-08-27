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
| Distinguish **missing** from **deliberately-empty** submissions from the UI/API | **FAIL (V-1)** |
| See **who** on a team submitted (individual) | Gap (V-2) |

### Findings
- **V-1 (P1).** After close, a never-submitted team (`missing_submission_defaulted`)
  and a deliberately-empty locked submission (`deadline_lock`) both show
  `status: locked`, and **no instructor endpoint surfaces the difference** — it
  exists only in `DecisionAuditEvent`. The spec requires distinguishing these
  "without direct database intervention." CR-012 added the audit action but not
  operator-facing visibility, so this half of CR-012 is effectively unmet.
- **V-2 (P2).** `DecisionSubmission.locked_by` (the submitting user, populated by
  CR-004) is not exposed by any instructor endpoint; visibility is team-level.
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
- **S-1 (P2).** `process_round` raises `ValueError` surfaced as **HTTP 500** (not a
  clean 400) when a team is left unlocked at process time — the state right after
  an operator correction-unlock that was not re-locked. It correctly refuses to
  process, but an actionable 400 ("re-lock team X before processing") would be
  safer under event-day pressure.
- **Lock is strict** (correct): a submission cannot be locked without a complete,
  valid decision set (product portfolio, marketing mix, strategy, budget).
- **No in-app operator broadcast** exists for "outage communications"; this is an
  out-of-band step and belongs in `OPERATOR_RUNBOOK.md`.

### Still human
A real volunteer cycle with people over live deadlines, and the engineering /
competition-ops / rules-owner sign-offs, remain human gates. This script shakes
out the mechanics beforehand; it does not replace the human dry run.
