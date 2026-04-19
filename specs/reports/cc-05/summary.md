---
name: CC-5 summary report
description: Fork audit final summary — Groups 1 + A–F complete; NewSalesByRound halted; ready for merge decision
type: report
---

# CC-5 — Fork Audit Summary

*Last updated 2026-04-19. Branch `cc-05-fork-audit`, 11 commits ahead of main.*

## Status

CC-5 is **functionally complete**. Classification (§5.1–5.3), Amendment A1, Group 1 prune (4), and Groups A–F promote (34) committed and verified. **1 ghost remains** (NewSalesByRound) awaiting spec-author schema decision. Merge to main pending user approval.

## Counts

### Modules (§5.1)

| Classification | Count |
|---|---|
| KEEP | 175 |
| ADAPT | 10 |
| DISCARD | 0 |
| NEW-NEEDED | 0 |
| **Total** | **185** |

### Ghosts (§5.2) — final disposition

| Disposition | Count | Status |
|---|---|---|
| Prune | 4 | ✅ Group 1 executed |
| Promote | 35 | ✅ 34 executed (A–F) • ⏸ 1 halted (NewSalesByRound) |
| Document-as-dormant | 0 | — |
| **Total at audit start** | **39** | |

Ghost count now: **1** (NewSalesByRound only).

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
| 6 | Prune ghosts removed, `manage.py check` passes | ✅ (Group 1, 4 models) |
| 7 | Promote ghosts promoted, migrated, queryable | ✅ 34 of 35 done • 1 halted |
| 8 | Clean commit history on `cc-05-fork-audit` | ✅ |
| 9 | Branch merged to main | ⏸ pending user approval |
| 10 | DISCARD modules not deleted | ✅ (none classified) |
| 11 | ADAPT modules not modified | ✅ |
| 12 | NEW-NEEDED modules not created | ✅ |

**Verification checkpoints (§7):**
- `python manage.py check` → `System check identified no issues (0 silenced).`
- `python manage.py makemigrations --dry-run core` → `No changes detected in app 'core'.`
- `python manage.py showmigrations` → all 0043–0049 applied.
- Ghost recompute: **1 ghost remaining** (NewSalesByRound, by design).

## Promotions completed (34 models)

### Group A — Gamification & Scoring (10) — commit 8025c67
Achievement, GamificationBadge, PlayerProgress, TeamAchievement, TeamBadge, ScoreType, Score, LeaderboardMetric, LeaderboardScore, TeamPerformance.

### Group B — Financials (6 of 7) — commits d70606e + 3cf89ca
TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow, TeamResources, FinancialRevenue, FinancialExpense. Also retroactively aligned Group A Meta-options state.

### Group C — Programs & Portfolio (5) — commit df32b25
ProgramType, Program, ProgramPortfolio, ProgramFeature, Decision.

### Group D — Simulation State (3) — commit 2a5cab2
SimulationState, SimulationSettings, SimulationParameters.

### Group E — Messaging + Events (5) — commit 8a512a9
Message, MessageResponse, MessageThread, NotificationLog, TriggeredEvent.

### Group F — Instructor Tools (5) — commit 7b7d0f9
InstructorAction, InstructorEvaluation, InstructorNote, InstructorFeedbackTemplate, InstructorScenarioCustomization.

## Halted — NewSalesByRound (1 model)

`round_id` declared `primary_key=True` alongside `unique_together = (('round_id', 'customer_id', 'program_id'),)` — the single-column PK conflicts semantically with per-(round, customer, program) uniqueness. Details and options in `promotion_questions.md`.

## CC-7 handoff items

- **0 DISCARD modules** to delete.
- **10 ADAPT modules** for refactor under their owning CC specs (not CC-7).
- **0 NEW-NEEDED modules** (CC-4 handled the supply-chain module set).
- **5 instructor surfaces** (3 EXTEND + 2 NEW-NEEDED) routed to CC-16.

## Open items requiring spec-author decision

1. **NewSalesByRound schema** — resolve per `promotion_questions.md` (promote as-is, fix PK to be composite or auto, prune, or document-as-dormant).
2. **Merge `cc-05-fork-audit` → `main`?** Ready on user approval. Recommend resolving #1 first (either promote or explicitly defer).

## Commit history on branch (11 commits)

```
7b7d0f9 CC-5 §5.5 Group F: promote Instructor Tools ghosts (5 models)
8a512a9 CC-5 §5.5 Group E: promote Messaging + Events ghosts (5 models)
2a5cab2 CC-5 §5.5 Group D: promote Simulation State ghosts (3 models)
df32b25 CC-5 §5.5 Group C: promote Programs & Portfolio ghosts (5 models)
57f0e91 CC-5 reports: summary.md + promotion_questions.md (state through Group B)
3cf89ca CC-5 §5.5 Group B: set managed=True on promoted Financials models
d70606e CC-5 §5.5 Group B: promote Financials ghosts (6 of 7 models) — recovery commit
8025c67 CC-5 §5.5 Group A: promote Gamification + Scoring ghosts (10 models)
9526c45 CC-5 Amendment A1: relax Promote rule #1 to accept live runtime reference
d634b3e CC-5 §5.4: prune 4 approved ghost models (Group 1)
151ef3d CC-5: baseline inventories for fork audit
```
