# GSP Round 1 Readiness Battlecard

Date: 2026-07-23

## Current State

Round 1 is substantially playable on the live GlobalStrat+ site. The main blocker chain found during browser-first walkthroughs has been addressed and pushed to `origin/main`.

Latest pushed commit at handoff:

- `979dc86 GSP-R1-11: rebalance performance index composite`

Live site:

- `https://globalstrat.camdani.com`

Working repo:

- `/home/ubuntu/projects/globalstrat+`

## Completed Readiness Work

- `GSP-R1-01`: fixed student shallow-route recovery and bad Strategy Mix shortcut.
- `GSP-R1-02`: verified decision pages; no additional code needed after routing fix.
- `GSP-R1-03`: fixed instructor `/games/:gameId/instructor` dead route.
- `GSP-R1-04`: fixed finance budget typing/formatting so normal keystrokes persist correctly.
- `GSP-R1-05`: verified/improved R&D and submit guidance.
- `GSP-R1-06`: verified guided navigation into actionable pages.
- `GSP-R1-07`: aligned instructor/student round status language.
- `GSP-R1-08`: full four-student Review & Submit rehearsal completed.
- `GSP-R1-09`: fresh-game Round 1 rehearsal fixes.
- `GSP-R1-10`: compliance freeze now gates customer adoption before it becomes demand/sales credit.
- `GSP-R1-11`: Performance Index rebalanced to a five-component strategic-management composite.

## Current PI Formula

The live scorer now uses:

- Market performance: 30%
- Strategic capability: 25%
- Financial discipline: 15%
- Stakeholder confidence: 15%
- Execution resilience: 15%

The user is considering the next calibration trial:

- Market performance: 35%
- Strategic capability: 20%
- Financial discipline: 25%
- Stakeholder confidence: 10%
- Execution resilience: 10%

Do not apply that second mix without an explicit user request. It was discussed as a possible next trial, not committed policy.

## Latest Verification

Passed:

- `python3 manage.py check`
- `python3 manage.py test core.tests.test_cc18_compliance.CC18ComplianceTest --verbosity=2`

Important replay result from controlled Game 18 / Round 1:

| Team | New Replay PI | Old PI | Interpretation |
| --- | ---: | ---: | --- |
| Lumen Devices | 57.54 | 51.60 | Revenue/profit leader, now rises to top. |
| Nova Circuit | 57.52 | 51.63 | Close second because strategic capability remains strong. |
| Solaris Consumer | 56.36 | 51.63 | Middle performer. |
| Meridian Tech | 52.44 | 49.81 | Clearly last after compliance freeze and zero revenue. |

## Known Carry-Forward Items

1. PI component persistence:
   - `RoundResultPerformanceIndex.satisfaction_score` currently stores the final composite score.
   - Future migration should add explicit component fields or JSON breakdown for market/capability/financial/stakeholder/resilience.

2. Compliance engine scope:
   - Customs enforcement can still generate noisy events in inactive/non-home markets.
   - PI freeze penalties now ignore inactive-market freezes, but the compliance engine itself still needs cleanup.

3. PI calibration:
   - Current spread is better but still modest in Round 1.
   - User may want a stronger market/financial mix after seeing another fresh-game result.

4. Fresh-game score/report audit:
   - Next useful playtest is a new clean Round 1 run, pause after processing, and inspect:
     - leaderboard
     - score/report pages
     - stakeholder reactions
     - event explanations
     - student-facing interpretation of why scores changed

## Operational Notes

- Backend runs on VM `.5`.
- Gunicorn master observed during this work: `408244`.
- Reload pattern used:
  - `kill -HUP 408244`
- Frontend rebuild was not needed for `GSP-R1-10` or `GSP-R1-11`; both were backend-only.

## Future Agent Guidance

- Stay browser-first when judging readiness. Backend checks are necessary but not sufficient.
- Do not fabricate fixes for symptoms that no longer reproduce.
- Preserve the handoff/report discipline under `handoffs_v3/reports`.
- Treat scoring changes as calibration work: test against processed game data before changing live weights.
- Keep Round 1 context in mind. A narrower spread is not automatically wrong because firms start from similar initial positions.
