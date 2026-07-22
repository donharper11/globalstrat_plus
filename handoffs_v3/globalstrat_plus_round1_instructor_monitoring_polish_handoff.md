# GSP-R1-07 - Instructor Monitoring Clarity Polish

**Status:** Ready for builder dispatch.
**Scope owner:** Instructor Round 1 monitoring language, game identity, readiness clarity, and Supply Chain table polish.
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

The instructor can now reach Game Control, but monitoring language is still confusing during live play.

Observed friction:

- One instructor surface says `R1 of 8 IN PROGRESS`; Game Control says `CURRENT ROUND 1 of 10` and `STATUS setup`.
- The instructor cannot always confirm they are looking at game 12 by ID.
- Readiness wording shows `0 of 4 teams locked`, but other panels show drafts/no submissions with different language.
- `Students & Logins` appears to show `43 online`, likely activity/session rows rather than unique active users.
- Supply Chain risk rows have concatenated text such as `semiconductorpower_management...` and blank-looking rows before real rows.

---

## Required Behavior

1. Instructor screens must use consistent round count and status language for the same selected game.
2. Game identity must be visible: game name and game ID.
3. Current decision round and latest processed results round must be distinguished where both concepts appear.
4. Team readiness must use consistent terms:
   - no submission
   - draft
   - locked/submitted
   - processed, if applicable
5. Online/user activity counts must be labeled honestly. If the metric counts events or sessions, do not label it as unique online people.
6. Supply Chain risk tables must have readable separated values and no blank-looking rows without explanation.

---

## Investigation Targets

Verify names before wiring:

- `frontend/globalstrat-frontend/src/pages/InstructorDashboard.js`
- `frontend/globalstrat-frontend/src/components/instructor/InstructorSCPanel.js`
- `frontend/globalstrat-frontend/src/components/StudentAccountsPanel.js`
- `frontend/globalstrat-frontend/src/api/instructor.js`
- Backend instructor endpoints that provide round/game/readiness/session metrics.

Do not change round progression semantics unless the backend state proves the UI is wrong. Prefer relabeling and small view-model fixes where the underlying data is already correct.

---

## Browser Exit Proof

Use `instructor / instructorpass`.

1. Login and open Instructor portal.
2. Confirm game name and game ID are visible.
3. Confirm round/status labels are consistent across the main instructor view and Game Control.
4. Confirm team readiness displays all four teams with clear statuses.
5. Open Students & Logins and verify the activity metric label is accurate.
6. Open Supply Chain panel and verify risk rows are readable.
7. Open but cancel any dangerous modal touched during proof. Do not advance/process/reset/delete/inject.
8. Capture screenshots for Game Control, readiness, and Supply Chain.

Report changed files and any unresolved inconsistency that reflects backend state rather than UI copy.
