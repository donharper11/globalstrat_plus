# GSP-R1-08 — Full Four-Student Review & Submit Protocol

Date: 2026-07-22
Target: `https://globalstrat.camdani.com`, game 12
Final live bundle proven: `static/js/main.11e4fed9.js`
Backend reload: gunicorn master `408244` HUP, workers refreshed

## Scope

Ran the four-student GSP-R1-08 protocol to Review & Submit on the current live build. This was not a fresh seeded replay; it used existing game 12 and existing draft state from prior verification. No lock/submit was executed.

Personas:

- `student1` / team 18 / Zenith Hardware
- `student2` / team 19 / Helix Digital
- `student3` / team 20 / Photon Labs
- `student4` / team 21 / Nova Circuit

Visited for each student:

- Dashboard
- R&D Investment
- Product Portfolio
- Marketing Mix
- Corporate Strategy
- Finance
- Review & Submit

## Initial Result

All four students reached Review & Submit with no shell-only pages, stuck loaders, hardcoded `R1 of 8`, 404s, 5xx responses, or console errors.

However, the first pass found a real lock-gate issue: student1, student2, and student4 had visible incomplete checklist items but an enabled `Lock & Submit Decisions for Round 1` button.

## Fix Applied During This Protocol

Changed backend and frontend so the visible Review checklist and lock behavior agree.

Backend: `backend/core/views/decisions.py`

- `DecisionSummaryView` now adds lock blockers when required categories are incomplete:
  - Product Portfolio
  - Marketing Mix
  - Strategy Mix
- Missing financing is now treated as optional: `No financing changes this round.`
- `DecisionLockView._full_validate` now also enforces Product Portfolio, Marketing Mix, and Strategy Mix before lock.

Frontend: `frontend/globalstrat-frontend/src/pages/SummaryPage.js`

- Adds a defensive client-side lock gate for required categories.
- Hides `Fix in Financing` when financing is optional and has no hard error.

## Verification

Checks run:

- `python3 manage.py check` passed.
- `npm run build` passed with pre-existing lint warnings.
- Frontend deployed with `./frontend/deploy-frontend.sh`.
- Deploy backup: `/var/www/globalstrat-backup-20260722-152354`.
- Backend gunicorn workers reloaded.

Final four-student Review & Submit proof:

| Student | Review page reached | R1 of 10 | Lock visible | Lock disabled | Explanation present | Bad HTTP |
|---|---:|---:|---:|---:|---:|---:|
| student1 | yes | yes | yes | yes | yes | 0 |
| student2 | yes | yes | yes | yes | yes | 0 |
| student3 | yes | yes | yes | yes | yes | 0 |
| student4 | yes | yes | yes | yes | yes | 0 |

Observed blockers after fix:

- student1: Product Portfolio, Marketing Mix, Strategy Mix required before locking.
- student2: Marketing Mix and Strategy Mix required before locking; R&D still shown as a recommended Fix path from the checklist.
- student3: Budget Allocation, R&D Investment, Product Portfolio, Marketing Mix, Strategy Mix, and Financing require attention based on current draft state.
- student4: Product Portfolio, Marketing Mix, Strategy Mix required before locking.

Screenshots captured on verifier host:

- `/tmp/gsp-r1-08-student1-summary-lockgate-fixed.png`
- `/tmp/gsp-r1-08-student2-summary-lockgate-fixed.png`
- `/tmp/gsp-r1-08-student3-summary-lockgate-fixed.png`
- `/tmp/gsp-r1-08-student4-summary-lockgate-fixed.png`

Earlier sweep screenshots also captured per student/page at `/tmp/gsp-r1-08-<student>-<page>.png`.

## Data Safety

No lock/submit was clicked. No game advance/process/reset/archive/delete or event injection occurred. The audit navigation itself made no intentional draft edits.

## Verdict

PASS for the requested four-student protocol to Review & Submit after the lock-gate fix.

The students can reach Review & Submit, see clear incomplete-work guidance, use Fix buttons to navigate back to actionable pages, and cannot lock while required core decision categories remain incomplete.

## Recommended Next Step

Run a clean fresh-game rehearsal when ready. The current game 12 audit is useful for regression confidence, but it is not a zero-state live rehearsal because prior verification left existing drafts in several teams.
