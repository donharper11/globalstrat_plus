# GSP-R1-08 — Re-Run Against the Fixed Build

**Date:** 2026-07-22 · **Target:** `https://globalstrat.camdani.com`, game 12 · viewport 1440x1000.
**Build under test:** `static/js/main.ffcc7bb2.js` (commit `bfc5418` "Finance budget typing fix").
**Scope:** quick independent re-run of GSP-R1-08 after the finance-input fix. Persona: `student1`.
Companion to `GSP-R1-08-quick-live-reaudit-current-build.md` (the pre-fix baseline).

## Verdict: **B1 RESOLVED — the lone Round-1 completion blocker is fixed. Completion path now PASSES.**

The remaining items are the two GSP-R1-07 instructor-polish frictions (unchanged by this finance-only
fix); neither blocks a student from completing Round 1.

## B1 re-verification (finance budget input) — PASS

Independently reproduced the fix with real per-keystroke typing on all three budget fields:

| Field | Typed (per-keystroke) | On blur | After reload |
|---|---|---|---|
| R&D Budget | `1000000` | `$ 1,000,000` | `$ 1,000,000` |
| Marketing Budget | `1200000` | `$ 1,200,000` | `$ 1,200,000` |
| Strategy Budget (isolated) | `2000000` | `$ 2,000,000` | `$ 2,000,000` |

- Typing no longer mangles digits (pre-fix: `2000000` -> `$ 20`); the field accepts raw input and
  parses/formats on blur/Enter, and the value **persists exactly as entered** across reload.
- No 5xx; finance page renders normally; no regression observed in the R&D/Marketing/Strategy fields.

## Still open (GSP-R1-07 instructor polish — not touched by `bfc5418`, still present)

- **M1** Instructor Game Control shows "Round 1 of 10, STATUS setup" while the student view of the same
  game 12 shows "R1 of 8, IN PROGRESS" — round-total/status inconsistency between surfaces.
- **m1** Instructor Supply Chain "Per-team supply-chain audit" rows render blank.

These are monitoring friction, not student-completion blockers.

## Confirmed good (unchanged, still healthy)

R&D feasible action + honest guidance; Review & Submit checklist with clickable "Fix in X" links;
Dashboard Guided Next opens the next decision page; instructor shows game ID (#12), all 4 teams, and an
honest "not a unique-person count" session label; no shell-only pages, no indefinite spinners, no 5xx.

## Data changed

student1 / team 18 budgets (R&D/Marketing/Strategy) were edited during re-verification and **restored to
originals ($900,000 / $1,300,000 / $1,500,000)**; restoration verified after reload. **Net change: none.**
No game advanced/processed/reset/archived; no events injected; no lock/submit.

## Recommendation

The finance blocker (B1) that caused the pre-fix FAIL is resolved. **Proceed to close GSP-R1-04.** Before
a full Round 1 live-play rehearsal, address the two GSP-R1-07 items (M1 round/status consistency, m1 SC
rows), then run the **full 4-student** GSP-R1-08 protocol (all of student1-4 to Review & Submit) as the
final sign-off.
