---
name: CC-5 promotion questions
description: Halt-flag per §6.4 — 35 Promote-dispositioned ghosts lack explicit CC-spec naming; spec-author judgment required before mass promotion
type: report
---

# CC-5 §5.5 — Promotion Questions (Halt Flag)

*Produced 2026-04-19 during verification pass after Group 1 prune commit.*

## Summary

35 ghosts are currently classified **Promote** in `ghost_triage.md`. Verification of the §5.5 execution checklist surfaces a **§6.4 halt condition** that should be resolved by the spec author before the 35 CREATE TABLE migrations are generated and applied.

## The halt

Per §4.2 **Promote rules**, a ghost is promoted only if **all** of:

1. A current or already-drafted CC spec (CC-1 through CC-6, or named amendments) references it by name.
2. Its absence would block build pipeline work.
3. The promotion doesn't require schema assumptions that haven't been reviewed.

**Rule #2 is clearly met** for all 35 ghosts. Runtime verification confirmed engine code (`round_engine.py`, `persona_engine.py`, `budget.py`, `r_and_d.py`, `gamification_engine.py`) queries these tables; absent tables raise `relation "<table>" does not exist`.

**Rule #1 is *not* met as literally specified.** None of CC-1 through CC-6 name these models individually. They name subsystems (leaderboards, programs, messaging, financials) but not class-by-class.

**Rule #3 is partially unverified.** Each ghost's schema needs per-model review before migration generation.

Per §6.4, "a ghost that looks useful but has no named CC referencing it — the disposition rule would default to prune, but Claude Code should surface to the spec author first if the model's purpose suggests future value."

The triage author already surfaced the deviation in `ghost_triage.md` ("Distribution note: Target discipline was prune ≥70%, but actual triage reflects data-driven analysis"). Verification stops here to confirm the authorization to proceed.

## Scope of promotion work

35 models across 6 subsystems:

| Subsystem | Count | Models |
|---|---|---|
| Gamification & Leaderboards | 7 | Achievement, GamificationBadge, PlayerProgress, TeamAchievement, TeamBadge, LeaderboardMetric, LeaderboardScore |
| Scoring | 3 | Score, ScoreType, TeamPerformance |
| Financials | 7 | FinancialExpense, FinancialRevenue, TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow, TeamResources, NewSalesByRound |
| Programs & Portfolio | 5 | Program, ProgramType, ProgramFeature, ProgramPortfolio, Decision |
| Simulation State | 3 | SimulationState, SimulationSettings, SimulationParameters |
| Messaging & Notifications | 4 | Message, MessageResponse, MessageThread, NotificationLog |
| Events | 1 | TriggeredEvent |
| Instructor Tools | 5 | InstructorAction, InstructorEvaluation, InstructorNote, InstructorFeedbackTemplate, InstructorScenarioCustomization |

## Questions for the spec author

1. **Authorize blanket promotion under rule #2?** The triage's Promote-by-runtime-usage argument is sound but relaxes rule #1. Is CC-5 authorized to promote all 35 under "absence blocks build pipeline work" alone?
2. **Per-model schema review gate.** §5.5 step 3 says "inspect the migration before applying." For 35 models, does the spec author want migrations committed as individual commits (one per model) for review, or one bulk migration? Current suggestion: group by subsystem (6–8 commits).
3. **Instructor Tools (5)** — these have *viewset-only* references (no live engine callers). Should they instead be re-classified to Prune or Document-as-dormant? CC-16 is named as the instructor-panel extension spec; its eventual scope is not yet written.
4. **Decision** (`programs.py:84`) — triage lists only a viewset reference, no engine caller. Same question as #3.

## Recommended path forward

- **Option A (execute as triaged):** Promote all 35. Commit in 6 subsystem groups. After each `makemigrations`, inspect the migration diff before `migrate`. If any schema looks wrong, halt and update this file.
- **Option B (tighten):** Re-triage the 6 viewset-only ghosts (InstructorAction, InstructorEvaluation, InstructorNote, InstructorFeedbackTemplate, InstructorScenarioCustomization, Decision) as Prune; promote the remaining 29.
- **Option C (halt entirely):** Defer all 35 promotions to a new CC spec (CC-5.5 or CC-7 extension) that individually names and authorizes each model. CC-5 closes with Group 1 prune only.

Awaiting spec-author decision.
