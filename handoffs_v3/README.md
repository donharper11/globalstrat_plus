# GlobalStrat+ Handoffs v3

This folder contains browser-first live-readiness handoffs for GlobalStrat+.

## Required Reading For Every Agent

Before working any handoff in this folder, read:

1. `handoffs_v3/globalstrat_plus_round1_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

The overview explains the Round 1 synthetic playtest findings, work sequence, accounts, and exit criteria. `STANDING-DISCIPLINE.md` is binding governance: verify names before wiring, do not invent fields/routes/models, report mismatches explicitly, preserve migration hygiene, and verify browser-visible behavior.

## Work Sequence

1. `globalstrat_plus_round1_student_routing_handoff.md`
2. `globalstrat_plus_round1_student_decision_pages_handoff.md`
3. `globalstrat_plus_round1_instructor_control_handoff.md`
4. `globalstrat_plus_round1_reaudit_handoff.md`

## Operating Rules

- Work in `/home/ubuntu/projects/globalstrat+`, not the foundational `/home/ubuntu/projects/globalstrat`.
- Use `https://globalstrat.camdani.com` for browser proof.
- Treat the frontend as the truth surface. Backend checks are for diagnosis and safety, not a substitute for browser proof.
- Do not advance/process/reset/archive/delete live games unless the handoff explicitly says to do so.
- Do not inject live events during Round 1 readiness unless the handoff explicitly says to do so.
- Record changed files, browser actions verified, data changed, screenshots/artifacts, and unresolved risks.
