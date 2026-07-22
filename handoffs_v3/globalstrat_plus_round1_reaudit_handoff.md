# GSP-R1-Audit - Round 1 Browser Re-Audit

**Status:** Run only after GSP-R1-01, GSP-R1-02, and GSP-R1-03 builders report complete.
**Scope owner:** independent verification / coordinator.
**Target:** `https://globalstrat.camdani.com`

---

## Required Reading Before Work

Before taking action, the assigned agent must read:

1. `handoffs_v3/globalstrat_plus_round1_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

The overview gives the Round 1 playtest context and sequencing. `STANDING-DISCIPLINE.md` is binding: verify before wiring, do not invent names, report mismatches explicitly, preserve migration hygiene, and prove changes through browser-visible behavior.

---

## Orientation

This is not a code review first. It is a synthetic live-play re-audit:

- behave like a student/team/instructor
- use the public frontend
- do not assume backend knowledge
- only inspect backend/API if a browser-visible issue needs diagnosis
- pause after Round 1; do not continue to Round 2 until Round 1 passes

---

## Required Personas

### Student General Walkthrough

Use `student1 / student1pass`.

Cover:

- login
- dashboard
- all visible sidebar items
- dashboard shortcut buttons
- all decision pages
- all information/results pages
- review/submit page

### Student Supply-Chain Walkthrough

Use `student2 / student2pass`.

Cover:

- Sourcing
- Logistics
- Trade Finance / FX
- Inventory / Resilience
- Supply Chain Dashboard if visible
- Financial Reports / Results
- Review & Submit

### Instructor Walkthrough

Use `instructor / instructorpass`.

Cover:

- instructor landing
- Game Control
- roster/account/team readiness pages
- round controls, opened but not executed
- supply-chain instructor panel
- event injection modal/control, opened but not executed
- result dashboards

---

## Pass Criteria

Round 1 passes only if:

- No student or instructor page renders shell-only content.
- Shallow/deep links either resolve to active context or present an honest recovery action.
- Dashboard shortcuts land on meaningful pages.
- Every visible Round 1 decision page has clear content and next action guidance.
- Sourcing is usable and its save/validation path is clear.
- Instructor nav is reachable at `1440x1000`.
- Instructor Game Control is usable, not blank.
- Instructor can understand team readiness and current-vs-processed-round status.
- Dangerous instructor actions require confirmation and are not executed in the audit.
- No unexplained 5xx responses.
- Any expected 404s are either eliminated or explicitly handled as non-error UI states.

---

## Report Format

Produce a short report grouped by:

- Blockers
- Major Friction
- Minor Friction
- Good / Ready Moments
- Data Changed
- Screenshots / Artifacts
- Recommendation: proceed to Round 2 playtest or rework again

Each finding must include:

- route/page
- persona
- action taken
- observed behavior
- expected behavior
- screenshot path if captured

