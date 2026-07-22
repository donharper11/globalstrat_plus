# GSP-R1-08 - Round 1 Live-Play Re-Audit

**Status:** Ready after GSP-R1-04 through GSP-R1-07 are complete, merged, and deployed.
**Scope owner:** Independent browser-first readiness audit.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Required Reading Before Work

Before taking action, read:

1. `handoffs_v3/globalstrat_plus_round1_live_play_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`
3. Completion reports for GSP-R1-04 through GSP-R1-07.

---

## Purpose

This is not a code task. It is an independent browser-first replay to decide whether Round 1 is ready for a real live-play rehearsal.

Do not re-audit until all builder handoffs are merged, deployed, and reported.

---

## Audit Protocol

Use the public UI only except for read-only state checks requested below.

Personas:

- `student1 / student1pass`
- `student2 / student2pass`
- `student3 / student3pass`
- `student4 / student4pass`
- `instructor / instructorpass`

Recommended state:

- Prefer a fresh seeded game or explicit user-approved reset before the final replay.
- If using existing game 12, clearly state that prior drafts exist and may affect proof.

---

## Student Audit

For each student/team:

1. Login.
2. Start from the dashboard.
3. Use Guided Next and sidebar navigation only.
4. Complete the required Round 1 decisions as a novice user would.
5. Verify Finance values persist after reload.
6. Verify R&D has a clear feasible action or honest non-required state.
7. Open Review & Submit.
8. Confirm the checklist accurately distinguishes complete, incomplete, optional, and blocked items.
9. Do not lock/submit unless the user has explicitly approved lock testing.

Record:

- pages visited
- decisions saved
- remaining blockers
- screenshots of Finance, R&D, Review & Submit
- browser console/network failures

---

## Instructor Audit

As instructor:

1. Confirm selected game identity and game ID.
2. Confirm current round/status/readiness language is consistent.
3. Confirm all four teams appear with correct readiness statuses.
4. Confirm Supply Chain monitor rows are readable.
5. Open dangerous actions only far enough to confirm they are gated, then cancel.
6. Do not advance/process/reset/delete/archive/inject.

---

## Pass Criteria

PASS only if:

- All four students can reach Review & Submit with understandable remaining blockers, or complete all required decisions if lock testing is approved.
- No finance persistence failure is observed.
- No impossible required R&D action blocks a student.
- Dashboard guidance reliably opens actionable pages.
- Instructor monitoring clearly distinguishes game identity, round state, processed state, and team readiness.
- No unexplained shell-only pages, indefinite spinners, 5xx errors, or route dead-ends remain.

If any student cannot determine the next required action from the UI, mark the audit FAIL or PARTIAL and write a new targeted handoff.
