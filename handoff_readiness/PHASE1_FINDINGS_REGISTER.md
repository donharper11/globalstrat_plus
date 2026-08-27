# GlobalStrat+ competition-readiness findings register

Audit date: 2026-08-27 UTC
Build: `3d46c06`
Original Phase 1 disposition: **NO-GO. Phase 2 was not to start until this
register was reviewed and prioritised.**

Current disposition (2026-08-27): **all 16 original findings are closed or
accepted as an explicit operational constraint.** This register remains the
unaltered record of what Phase 1 found; it is not a statement that every launch
gate is complete. Remediation details and test evidence are in `FIX_LOG.md`,
with concurrency/replay evidence in `LOAD_TEST_RESULTS.md` and balance evidence
in `EXPLOIT_REPORT.md`. Outstanding release and human-rehearsal gates are tracked
in `LAUNCH_CHECKLIST.md`.

Severity: P0 blocks the competition; P1 materially degrades fairness/operability; P2 cosmetic.

| ID | Area | Severity | Finding | Reproduction | Evidence |
|---|---|---:|---|---|---|
| CR-001 | A2 lifecycle | P0 | The legacy instructor round-lock endpoint is not enforced by student decision endpoints. It sets `Round.decisions_locked`, while `IsRoundOpen` checks only status/deadline/game status. A student can save after the operator sees “locked”. | Keep a round `open`; POST `/api/rounds/{id}/lock/` as instructor; POST any student decision for that round; authorization still permits it. | `backend/core/views/course.py:1316-1333`; `backend/core/views/decisions.py:101-157`; code trace `evidence/static/critical_traces.txt` |
| CR-002 | A2/A5 lifecycle | P0 | Round processing is not protected by one database transaction or a row/advisory lock. Two workers can both observe a non-processed round, set `PROCESSING`, and execute mutating engine stages concurrently. | Send two instructor process requests concurrently for one closed round; both can pass the status check before either commits. | `backend/core/engine/advance_round.py:251-273`; no `atomic`/`select_for_update`; `backend/core/views/round_control.py:207-252` |
| CR-003 | A3 reconstruction | P0 | Decisions are mutable current-state rows, not immutable submitted versions. Generic partial updates delete and recreate detail rows; SC rows are updated in place. The database cannot prove the exact payload that existed at lock time. | Save decision A, then B; inspect `DecisionSubmission` and detail tables: A is gone. `DecisionChangeLog` stores only decision type, not payload before/after. | `backend/core/views/decisions.py:306-367`; `backend/core/models/cc21_models.py:40-57` |
| CR-004 | A3 reconstruction | P0 | Submitting identity is absent from the prize-critical lock record: `DecisionLockView` explicitly leaves `locked_by` null. Coarse change logging is best-effort and exceptions are swallowed. | Lock a valid team submission; query `decision_submission.locked_by_id`; it is null. Force change-log failure; save still succeeds. | `backend/core/views/decisions.py:401-423`; `backend/core/views/decisions.py:338-365` |
| CR-005 | A3/recovery | P0 | No automatic pre-resolution database snapshot or restore procedure exists. Source search found only frontend deployment backup logic. | Search runtime/deploy code for `pg_dump`, database snapshot, restore, or pre-process hook; none exists. Trigger processing failure after an early mutating stage: no snapshot is available. | `evidence/static/searches.txt`; `backend/core/engine/advance_round.py:251-457` |
| CR-006 | A7 integrity | P0 | No DRF throttling/rate limit is configured on decision endpoints. A competitor can flood write paths at deadline and amplify CR-002/CR-007. | Inspect `REST_FRAMEWORK`; send repeated authenticated writes; no throttle class/rate response is defined. | `backend/globalstrat/settings.py:267-289`; `evidence/static/searches.txt` |
| CR-007 | A5 concurrency | P0 | Generic decision replacement is not atomic. It deletes existing detail rows and then recreates them without `transaction.atomic`; concurrent saves can interleave, lose data, or leave an empty category after failure. | Concurrently PATCH the same list-valued decision type from two team members; observe last/interleaved replacement. Inject failure after delete to demonstrate empty result. | `backend/core/views/decisions.py:306-337` |
| CR-008 | A3 determinism | P1 | Randomness is derived deterministically from game/round/operation identifiers, but the seed and resolution input manifest are not stored with the resolution. Reconstruction therefore depends on unchanged code, identifiers, scenario rows and mutable state—not the database record alone. | Re-run RNG tests (passes), then inspect `Round`: no seed/input/output manifest fields. | `backend/core/engine/rng.py:36-52`; `backend/core/models/core.py:106-157`; 246-test log |
| CR-009 | A6 controls | P1 | Operator actions (close/reopen/extend/process/advance/legacy lock) do not record actor and required reason in an immutable operations log. Submission correction is implemented as unlock/edit, destroying the disputed version. | Perform an operator action and inspect tables; only state fields/reason enum change. Unlock and edit a submission; original payload is overwritten. | `backend/core/views/round_control.py`; `backend/core/views/course.py:1316-1388`; `backend/core/views/decisions.py:671-691` |
| CR-010 | A6 recovery | P1 | There is no supported rollback or deterministic re-run control after processing. Processed rounds are rejected, and no compensating restore path exists. | Process a round, then call process again/reopen; API rejects it. Search instructor UI/API for rollback/re-run. | `backend/core/engine/advance_round.py:263-267`; `backend/core/views/round_control.py:143-150,225-231` |
| CR-011 | A4 balance | P1 | FX hedging has no premium, spread, collateral, credit limit or budget cost. A 100% hedge removes modeled FX downside at zero cost; where uncertainty is undesirable it is a dominant legal choice, making the decision strategically degenerate. | Compare otherwise identical teams with 0% and 100% hedge across rate paths; hedge notional is exposure × ratio and only settlement P&L is booked—no hedge cost. | `backend/core/engine/fx_engine.py:54-120`; `backend/core/engine/financials.py:153-156` |
| CR-012 | A2 rules | P1 | Missing submissions are silently materialised as empty locked submissions at close. This is technically uniform but is not accompanied by published student rules or an operator-visible immutable record distinguishing “never submitted” from a deliberate empty payload. | Close a round with a team that never saved; an empty locked `DecisionSubmission` is created with no actor. | `backend/core/engine/advance_round.py:101-119` |
| CR-013 | A3 integrity | P1 | Several engine stages catch exceptions and continue, allowing a prize result to publish after components fail. Supply-chain strictness defaults off in production; other strategic stages also fail open into a text-only transient context log. | Raise in SC/org/alliance/strategic-impact/capital-markets stages; processing continues and can mark results available. | `backend/core/engine/advance_round.py:26-62,302-455`; `backend/globalstrat/settings.py:249-258` |
| CR-014 | A8 parity | P2 | EN/ZH locale key sets are equal (1,794 each), but several supply-chain page labels remain hard-coded English, so key parity does not equal rendered parity. | Set `gs_language=zh-CN`; visit Inventory and inspect labels such as “Input”, “Shift to backup”, and validation messages. | `frontend/globalstrat-frontend/src/pages/InventoryPage.js:126-218`; locale key comparison in `evidence/static/searches.txt` |
| CR-015 | A1 deployment | P1 | The documented local frontend port `8081` serves the code-server login, not GlobalStrat+. A rehearsal relying on the local handoff endpoint is a dead end; the public URL is required. | Open `http://127.0.0.1:8081`; response redirects to code-server `/login`. | Browser evidence from initial pass; `curl -I` trace in `evidence/static/runtime.txt` |
| CR-016 | A1 walkthrough | P1 | The deployed SPA intermittently rendered a completely blank document body on direct navigation. Eight of 46 student EN/ZH route visits were blank, spanning Research, Marketing, Corporate Strategy, Tools, Forecast, Trade Finance and Products. No page exception or failed API response was emitted, leaving the user without recovery guidance. | Authenticate, directly navigate routes in a fresh browser context, wait 1.2 s after DOM ready, and record body text/screenshot. Repeat EN/ZH sweep. | `evidence/browser/results.json` and the named zero-body screenshots |

## Audit coverage and limits

### Phase 2 verification finding

| ID | Area | Severity | Finding | Reproduction | Evidence |
|---|---|---:|---|---|---|
| CR-017 | A1 walkthrough | P1 | Navigating away from a dirty decision page provides no warning or route guard. Browser Back reconstructs the page from server state and silently loses the unsaved edit. | In an open round, change an enabled Marketing numeric field without saving; navigate to another decision page; use browser Back. No confirmation appears and the original server value returns. | `A1_BROWSER_STATE_LIFECYCLE_REHEARSAL.md`; `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json` |

**CR-017 resolution (Phase 2).** Closed. `useUnsavedChangesGuard` now guards all five dirty-tracking decision pages (Marketing, Sourcing, Logistics, Trade Finance, Inventory) against `beforeunload`, same-origin link clicks, and browser Back while an edit is unsaved. Re-run of the identical scenario against the fixed build now raises the discard confirmation (`leave_dialog` populated, `warning_visible: true`, `pass: true`) rather than silently reverting the field. See `FIX_LOG.md` and `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json`.

- A1: automated EN/ZH route sweep of 23 student routes plus two instructor entry routes against the deployed UI; screenshots and console/API traces are in `evidence/browser/`. Eight student visits produced blank bodies (CR-016).
- A2/A3/A6/A7: API, model, engine and permission trace plus existing integration tests.
- A4: adversarial engine inspection focused on FX and order/repeat behavior. CR-011 is confirmed by formula inspection; a calibrated multi-strategy tournament remains required after P0 repair.
- A5: baseline application tests passed, but a valid concurrent-write load result is intentionally not claimed: the only live game was already processed and the repository has no isolated load fixture. CR-002, CR-006 and CR-007 make a prize-load rehearsal unsafe until triage.
- A8: exact key parity check plus rendered-route sweep and hard-coded-string inspection.

## Verification record

- `python3 manage.py test core.tests core.engine.tests --verbosity 1`: **246 tests passed** in 83.449 s.
- Plain `pytest -q`: collection fails because Django settings are not configured and management scripts named `*_test.py` are collected. This is test-runner ergonomics, not itself a competition blocker.
- No application source was fixed during Phase 1. Only audit scripts, evidence and reports were added.
