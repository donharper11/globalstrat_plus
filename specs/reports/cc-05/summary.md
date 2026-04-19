---
name: CC-5 summary report
description: Fork audit summary — counts, decisions, CC-7 handoff items, status through Group B promotion
type: report
---

# CC-5 — Fork Audit Summary

*Last updated 2026-04-19. Branch `cc-05-fork-audit`, 6 commits ahead of main.*

## Status

CC-5 is **partially complete through Group B**. Classification, Amendment A1, Group 1 prune (4), Group A promote (10), Group B promote (6) committed. Groups C–F (19 models across 5 subsystems) pending. Merge to main pending.

## Counts

### Modules (§5.1)

| Classification | Count |
|---|---|
| KEEP | 175 |
| ADAPT | 10 |
| DISCARD | 0 |
| NEW-NEEDED | 0 |
| **Total** | **185** |

### Ghosts (§5.2)

| Disposition | Count | Executed |
|---|---|---|
| Prune | 4 | ✅ Group 1 |
| Promote | 35 | 🟡 16 of 35 (Groups A–B) |
| Document-as-dormant | 0 | — |
| **Total at audit start** | **39** | |

Remaining ghosts to promote: **19** (Groups C–F).

### Instructor surfaces (§5.3)

| Classification | Count |
|---|---|
| KEEP | 25 |
| EXTEND | 3 |
| NEW-NEEDED | 2 |
| DISCARD | 0 |
| **Total existing** | **28** |

EXTEND + NEW-NEEDED (5 surfaces total) routed to CC-16.

## Acceptance criteria status (§9)

| # | Criterion | Status |
|---|---|---|
| 1 | `module_inventory.txt` exists | ✅ |
| 2 | `module_classification.md` exists | ✅ |
| 3 | `ghost_triage.md` exists | ✅ |
| 4 | `instructor_panel_audit.md` exists | ✅ |
| 5 | `summary.md` exists | ✅ (this file) |
| 6 | Prune ghosts removed, `manage.py check` passes | ✅ (Group 1, 4 models, commit d634b3e) |
| 7 | Promote ghosts promoted, migrated, queryable | 🟡 16 of 35 done (Groups A+B) |
| 8 | Clean commit history on `cc-05-fork-audit` | ✅ |
| 9 | Branch merged to main | ⏸ pending #7 completion |
| 10 | DISCARD modules not deleted | ✅ (none classified) |
| 11 | ADAPT modules not modified | ✅ |
| 12 | NEW-NEEDED modules not created | ✅ |

`python manage.py check` → `System check identified no issues (0 silenced).`
`python manage.py makemigrations --dry-run core` → `No changes detected in app 'core'.`

## Promoted so far (16 models)

### Group A — Gamification & Scoring (10) — commit 8025c67

Achievement, GamificationBadge, PlayerProgress, TeamAchievement, TeamBadge, ScoreType, Score, LeaderboardMetric, LeaderboardScore, TeamPerformance. Tables created, `managed=True`, migration 0044 applied.

### Group B — Financials (6 of 7) — commits d70606e + 3cf89ca

TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow, TeamResources, FinancialRevenue, FinancialExpense. Tables created, `managed=True`, migration 0045 applied. Also retroactively realigns Group A Meta-options state.

**Halted (1):** NewSalesByRound — schema concern (see `promotion_questions.md`): `round_id` primary_key conflicts with unique_together on (round_id, customer_id, program_id).

## Remaining work

### Groups C–F (19 models)

- **Group C — Programs & Portfolio (5):** Program, ProgramType, ProgramFeature, ProgramPortfolio, Decision
- **Group D — Simulation State (3):** SimulationState, SimulationSettings, SimulationParameters
- **Group E — Messaging + Events (5):** Message, MessageResponse, MessageThread, NotificationLog, TriggeredEvent
- **Group F — Instructor Tools (5):** InstructorAction, InstructorEvaluation, InstructorNote, InstructorFeedbackTemplate, InstructorScenarioCustomization
- **Plus 1 halted:** NewSalesByRound (Group B)

### Environment note

Mid-session the working branch repeatedly switched away from `cc-05-fork-audit` to `cc-04-amendment-a1` (parallel worker active on CC-04 Amendment A1). Multiple recovery cherry-picks were required. This made multi-step migration work fragile. Groups C–F should be executed with the parallel CC-04 worker paused, or in a separate worktree.

## CC-7 handoff items

- **0 DISCARD modules** to delete.
- **10 ADAPT modules** for refactor under their owning CC specs.
- **0 NEW-NEEDED modules** (CC-4 already created the supply-chain module set).
- **5 instructor surfaces** (3 EXTEND + 2 NEW-NEEDED) routed to CC-16.

## Open items requiring spec-author decision

1. **NewSalesByRound schema** — details in `promotion_questions.md`. Blocks full Group B closure.
2. **Execute Groups C–F?** If yes, recommend pausing parallel CC-04 work for clean branch discipline.
3. **Merge `cc-05-fork-audit` → `main`?** Blocked on Groups C–F completion.

## Commit history on branch

```
3cf89ca CC-5 §5.5 Group B: set managed=True on promoted Financials models
d70606e CC-5 §5.5 Group B: promote Financials ghosts (6 of 7 models) — recovery commit
8025c67 CC-5 §5.5 Group A: promote Gamification + Scoring ghosts (10 models)
9526c45 CC-5 Amendment A1: relax Promote rule #1 to accept live runtime reference
d634b3e CC-5 §5.4: prune 4 approved ghost models (Group 1)
151ef3d CC-5: baseline inventories for fork audit
```
