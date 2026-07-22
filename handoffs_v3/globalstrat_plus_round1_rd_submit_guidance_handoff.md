# GSP-R1-05 - R&D Feasible Action And Review Submit Guidance

**Status:** Ready for builder dispatch.
**Scope owner:** Student R&D Round 1 action path and Review & Submit blocker guidance.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Required Reading Before Work

Before taking action, read:

1. `handoffs_v3/globalstrat_plus_round1_live_play_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

---

## Problem

Students reached Review & Submit but could not lock because required items remained incomplete. Two blockers were especially unclear:

- R&D showed an obvious Create New R&D Platform path with a `$5.0M` base cost, often over budget for Round 1.
- Existing R&D platform upgrade cards listed costs, but did not present an obvious action path.
- Review & Submit listed incomplete requirements but did not give a clear, clickable route to resolve each one.

A novice student should not need to infer the correct R&D action or guess where each checklist item is fixed.

---

## Required Behavior

### R&D Page

1. The page must clearly distinguish available Round 1 R&D actions from locked/future actions.
2. If creating a new platform is over budget, the page must say why and suggest an available action if one exists.
3. Existing platform upgrades must have clear controls if they are intended to satisfy Round 1 R&D investment.
4. If no R&D action is feasible, show an honest explanation and ensure Review & Submit does not require an impossible action.
5. Save/draft status must be visible after a successful R&D action.

### Review & Submit

1. Required evidence/decision checklist must show:
   - requirement name
   - status
   - why it is blocked
   - one primary action to fix it
2. Each actionable blocker must link to the exact page where the student can fix it.
3. The disabled Lock & Submit button must explain the remaining blockers in plain language.
4. Completed items and optional items must be visually distinct.
5. The page must not mention internal implementation concepts.

---

## Investigation Targets

Verify names before wiring:

- `frontend/globalstrat-frontend/src/pages/RDPage.js`
- `frontend/globalstrat-frontend/src/pages/SummaryPage.js`
- `frontend/globalstrat-frontend/src/contexts/DecisionContext.js`
- `frontend/globalstrat-frontend/src/api/decisions.js`
- Backend decision validation logic for R&D and submission locking.
- Any checklist/requirement definitions that determine Review & Submit readiness.

If checklist rules require an R&D action that the UI cannot perform in Round 1, halt and report the mismatch before inventing a workaround.

---

## Browser Exit Proof

Use `student1 / student1pass` and one additional team.

1. Open R&D from the sidebar.
2. Attempt the visible Round 1 R&D path.
3. Confirm at least one of these outcomes:
   - a valid within-budget action can be saved, or
   - the page honestly explains why no action is possible and Review & Submit reflects that rule.
4. Open Review & Submit.
5. Confirm every unresolved blocker has a clear explanation and a clickable action.
6. Use one blocker action link and confirm it opens the correct decision page.
7. Capture screenshots for R&D and Review & Submit.

Do not lock a team unless the handoff explicitly authorizes a final test lock. If a lock is needed for proof, stop and request approval.
