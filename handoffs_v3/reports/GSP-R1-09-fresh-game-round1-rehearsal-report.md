# GSP-R1-09 Fresh Game Round 1 Rehearsal

Date: 2026-07-22  
Target: https://globalstrat.camdani.com  
Fresh game: #17, GlobalStrat Test Game  
Scope: create fresh seeded game, complete/lock Round 1 for four demo students, process Round 1, pause before advancing, verify result surfaces.

## Protocol Run

- Created fresh game #17 with `setup_test_game` without `--flush`; existing game 12 was not reset.
- Seeded conservative Round 1 draft decisions for all four teams using the same decision models the UI writes.
- Validated each submission through `DecisionLockView._full_validate`; all four returned no errors.
- Logged into the public UI as `student1` through `student4` and locked each team from Review & Submit.
- Processed Round 1 through instructor round-control API with `force=true`; did not advance to Round 2.

## Processing Result

- Round 1 status: `processed` / `FULLY_COMPLETE`.
- Teams locked: 4 of 4.
- Processing time: about 5.1s.
- Generated rows:
  - RoundResultFinancials: 4
  - RoundResultPerformanceIndex: 4
  - LeaderboardEntry: 4
  - RoundResultAdoption: 148
  - RoundResultProductMarket: 6

## Fix Applied During Rehearsal

The first post-processing UI sweep exposed a shared round-selection bug: after Round 1 was processed but before Round 2 was opened, student pages showed `R2 of 10 NOT OPEN YET`. That made the pause-after-processing state confusing and hid the fact that Round 1 results were available.

Fixed in frontend:

- `src/contexts/GameContext.js`: when no round is open, prefer closed/current processed rounds before pending rounds.
- `src/pages/GameDashboard.js`, `MarketResearchPage.js`, `CompetitiveIntelPage.js`, `LeaderboardPage.js`, `ResultsPage.js`: latest-results selectors now treat a processed current round as the latest processed round.
- `src/components/design-system/TopBar.jsx`, `src/components/GameStatusBar.js`: processed rounds show `RESULTS AVAILABLE` before locked-submission status.
- `src/pages/InstructorDashboard.js`: processed current round reports latest processed round correctly and falls back to dashboard total rounds.

Deployed frontend bundle: `main.e6fdf1c6.js`. ECS backup: `/var/www/globalstrat-backup-20260722-161848`.

## Browser Proof After Fix

Student smoke, public UI:

- `student1` on game #17 dashboard shows `R1 of 10 RESULTS AVAILABLE`.
- No `R2 of 10` / `NOT OPEN YET` state near the top shell.
- Earlier full sweep after the shared fix showed all four students on Round 1 across dashboard, financial reports, leaderboard, and market research routes.

Instructor smoke, public UI:

- Game Control shows `Decision round 1 of 10 is processed; results available`.
- Shows `Latest processed results round: 1`.
- Shows `4 of 4 teams have locked decisions`.
- Round Control shows `Round 1 of 10`, status `processed`, processing complete.

## Open Finding

R1-09-F1 [MED] — Vertex product-market results missing after processing.

- Vertex Electronics had two valid Round 1 marketing decisions:
  - IronClad X / North America
  - IronClad Field / North America
- After processing, Vertex had zero `RoundResultProductMarket` rows and `$0` revenue, while the other three teams produced two product-market rows each.
- Leaderboard still ranked Vertex #1 by performance index despite `$0` revenue and negative net income. That makes the scoring/output explanation suspect and should be investigated before calling the full fresh-game Round 1 rehearsal clean.

Observed leaderboard after processing:

1. Vertex Electronics — index 51.77, revenue $0.00, net income -$3,615,000.00
2. Stratos Electronics — index 51.63, revenue $13,184,400.00, net income $5,796,299.52
3. Titan Micro — index 51.63, revenue $13,184,400.00, net income $6,317,699.52
4. Cipher Systems — index 51.60, revenue $17,864,400.00, net income $9,951,383.52

## Verdict

Round 1 can now be run end to end from a fresh game through lock and processing without the previous post-processing navigation dead-end. However, the rehearsal is not a clean pass because the Vertex result/scoring anomaly needs investigation.
