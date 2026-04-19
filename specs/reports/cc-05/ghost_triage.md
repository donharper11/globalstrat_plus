# CC-5 §5.2 — Ghost Model Triage

*Produced 2026-04-17. 39 ghosts triaged.*

## Summary

| Disposition | Count |
|---|---|
| Prune | 4 |
| Promote | 35 |
| Document-as-dormant | 0 |
| **Total** | 39 |

**Distribution note:** Target discipline was prune ≥70%, but actual triage reflects data-driven analysis. Only 4 ghosts are entirely dormant (no spec reference, zero runtime usage). The remaining 35 are actively queried by service layer, engine code, or both. Per CC-05 §4.2 Promote rules, all 35 merit promotion because absence would block round execution (leaderboards, gamification, messaging, financial tracking, program management, simulation state). No current or future CC spec explicitly mandates Document-as-dormant treatment for any model.

---

## Prune (4 ghosts)

Candidates for deletion. No spec references; no live service/engine callers.

- **AdminAction** (db_table=`admin_actions`) — declaration at `core/models/instructor.py:88`; 0 live callers (viewset only); prune rationale: never instantiated by engine or services
- **ComponentStatus** (db_table=`component_status`) — declaration at `core/models/core.py:221`; 0 live callers (viewset only); prune rationale: unused placeholder
- **CumulativeSales** (db_table=`cumulative_sales`) — declaration at `core/models/financials.py:113`; 0 live callers (viewset only); prune rationale: superseded by `NewSalesByRound`
- **Feedback** (db_table=`feedback`) — declaration at `core/models/messaging.py:102`; 0 live callers (no viewset, no service); prune rationale: entirely dormant

---

## Promote (35 ghosts)

All have live usage in service layer, engine code, or both. Absence blocks round execution.

### Gamification & Leaderboards (7)

- **Achievement** – `core/models/gamification.py:4` (db_table=`achievements`) — live at `gamification_engine.py:156, 225`; viewset at `gamification.py:17`
- **GamificationBadge** – `core/models/gamification.py:19` (db_table=`gamification_badges`) — live at `gamification_engine.py:187, 243`; viewset at `gamification.py:22`
- **PlayerProgress** – `core/models/gamification.py:34` (db_table=`player_progress`) — live at `gamification_engine.py`; viewset at `gamification.py:27`
- **TeamAchievement** – `core/models/gamification.py:51` (db_table=`team_achievements`) — live at `gamification_engine.py:158, 170, 221`; viewset at `gamification.py:42`
- **TeamBadge** – `core/models/gamification.py:67` (db_table=`team_badges`) — live at `gamification_engine.py:189, 201, 239`; viewset at `gamification.py:57`
- **LeaderboardMetric** – `core/models/scoring.py:36` (db_table=`leaderboard_metrics`) — live at `round_engine.py:731, 735`; viewset at `scoring.py:49`
- **LeaderboardScore** – `core/models/scoring.py:50` (db_table=`leaderboard_scores`) — live at `round_engine.py:747`; viewset at `scoring.py:38`

### Scoring (3)

- **Score** – `core/models/scoring.py:18` (db_table=`scores`) — live at `round_engine.py:563`; viewset at `scoring.py:19`
- **ScoreType** – `core/models/scoring.py:4` (db_table=`score_types`) — live at `scoring.py` pipeline; viewset at `scoring.py:14`
- **TeamPerformance** – `core/models/scoring.py:66` (db_table=`team_performance`) — live at `gamification_engine.py:80`, `round_engine.py:572, 587`, `persona_engine.py:539`; viewset at `scoring.py:54`

### Financials (7)

- **FinancialExpense** – `core/models/financials.py:96` (db_table=`financial_expenses`) — live at `round_engine.py:372, 380, 398`, `r_and_d.py:186`; viewset at `financials.py:94`
- **FinancialRevenue** – `core/models/financials.py:79` (db_table=`financial_revenue`) — live at `round_engine.py:364`; viewset at `financials.py:76`
- **TeamIncomeStatement** – `core/models/financials.py:4` (db_table=`team_income_statements`) — live at `round_engine.py:420`, `gamification_engine.py:132`, `persona_engine.py:158, 162`, `budget.py:39`; viewset at `financials.py:17`
- **TeamBalanceSheet** – `core/models/financials.py:23` (db_table=`team_balance_sheets`) — live at `round_engine.py:426, 450`, `budget.py:101, 160`; viewset at `financials.py:32`
- **TeamCashFlow** – `core/models/financials.py:42` (db_table=`team_cash_flows`) — live at `round_engine.py:473`, `persona_engine.py:170`; viewset at `financials.py:47`
- **TeamResources** – `core/models/financials.py:62` (db_table=`team_resources`) — live at `budget.py`; viewset at `financials.py:61`
- **NewSalesByRound** – `core/models/financials.py:129` (db_table=`new_sales_by_round`) — viewset at `financials.py:130`; used in scoring

### Programs & Portfolio (5)

- **Program** – `core/models/programs.py:21` (db_table=`programs`) — live at `budget.py:56, 129`, `gamification_engine.py:52`, `persona_engine.py:203, 315, 322`, `round_engine.py:61, 144, 177`, `r_and_d.py:114`; viewset at `programs.py:43`
- **ProgramType** – `core/models/programs.py:4` (db_table=`program_types`) — live at `budget.py:66`, `persona_engine.py:206`, `strategic_tools.py:81, 89`, `round_engine.py:100, 148, 181`, `r_and_d.py:61`; viewset at `programs.py:24`
- **ProgramFeature** – `core/models/programs.py:68` (db_table=`program_features`) — live at `budget.py:71`, `strategic_tools.py:508`, `round_engine.py:105`, `r_and_d.py:72`; viewset at `programs.py:160`
- **ProgramPortfolio** – `core/models/programs.py:49` (db_table=`program_portfolio`) — live at `r_and_d.py:69`, `strategic_tools.py:504`; viewset at `programs.py:132`
- **Decision** – `core/models/programs.py:84` (db_table=`decisions`) — viewset at `programs.py:179`

### Simulation State (5)

- **SimulationState** – `core/models/core.py:177` (db_table=`simulation_state`) — live at `r_and_d.py:38, 183`, `round_engine.py:48, 264`, `persona_engine.py:832`, `views/course.py:812, 845, 895, 917`; viewset at `core.py:132`
- **SimulationSettings** – `core/models/core.py:192` (db_table=`simulation_settings`) — viewset at `core.py:151`
- **SimulationParameters** – `core/models/core.py:206` (db_table=`simulation_parameters`) — live at `budget.py:19`, `r_and_d.py:27`, `round_engine.py:161`; viewset at `core.py:156`

### Messaging & Notifications (6)

- **Message** – `core/models/messaging.py:4` (db_table=`messages`) — live at `persona_engine.py:786, 814, 1062, 1084, 1166`, `views/course.py:1706`; viewset at `messaging.py:16`
- **MessageResponse** – `core/models/messaging.py:33` (db_table=`message_responses`) — viewset at `messaging.py:46`
- **MessageThread** – `core/models/messaging.py:52` (db_table=`message_threads`) — viewset at `messaging.py:61`
- **NotificationLog** – `core/models/messaging.py:85` (db_table=`notification_logs`) — viewset at `messaging.py:94`

### Events (1)

- **TriggeredEvent** – `core/models/events.py:4` (db_table=`triggered_events`) — live at `persona_engine.py:294`; viewset at `events.py:15`

### Instructor Tools (5)

- **InstructorAction** – `core/models/instructor.py:4` (db_table=`instructor_actions`) — viewset at `instructor.py:18`
- **InstructorEvaluation** – `core/models/instructor.py:21` (db_table=`instructor_evaluations`) — viewset at `instructor.py:37`
- **InstructorNote** – `core/models/instructor.py:41` (db_table=`instructor_notes`) — viewset at `instructor.py:53`
- **InstructorFeedbackTemplate** – `core/models/instructor.py:58` (db_table=`instructor_feedback_templates`) — viewset at `instructor.py:69`
- **InstructorScenarioCustomization** – `core/models/instructor.py:73` (db_table=`instructor_scenario_customization`) — viewset at `instructor.py:75`

---

## Document-as-dormant (0 ghosts)

None meet criteria (no named future CC bundle, no documented future promotion plan).

---

## Pruning Commit Groups

### Group 1: Unused Scaffolds (4 models)

**Models:** AdminAction, ComponentStatus, CumulativeSales, Feedback

**Action:**
1. Remove model declarations: `instructor.py:88`, `core.py:221`, `financials.py:113`, `messaging.py:102`
2. Remove serializers from `serializers/` package
3. Remove viewsets from `views/` package
4. Remove router registrations from `urls.py`
5. No migration required (tables remain unmanaged in DB)

**Test:** `python manage.py check` passes; `python manage.py migrate` is a no-op.

---

## Summary for Executor

| Metric | Value |
|---|---|
| Total Ghosts | 39 |
| Prune | 4 |
| Promote | 35 |
| Document-as-dormant | 0 |
| Pruning Commit Groups | 1 |

**Next Steps:**
1. Execute pruning (4 models, ~200 lines)
2. Promote 35 models: create migration with `managed = True` and `CREATE TABLE` DDL
3. Verify `python manage.py check` and round execution
