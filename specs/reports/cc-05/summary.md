---
name: CC-5 summary report
description: Fork audit final summary — all 39 ghosts disposed (4 pruned + 35 promoted); ready for merge
type: report
---

# CC-5 — Fork Audit Summary

*Last updated 2026-04-19. Branch `cc-05-fork-audit`, 13 commits ahead of main.*

## Status

CC-5 is **complete**. Classification (§5.1–5.3), Amendment A1, Group 1 prune (4), Groups A–F promote (34), and NewSalesByRound promote with corrected composite-unique PK (1) all committed and verified. **Zero ghosts remaining.** Ready for merge to main.

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
| Promote | 35 | ✅ All 35 executed |
| Document-as-dormant | 0 | — |
| **Total at audit start** | **39** | ✅ |

Ghost count now: **0**.

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
| 7 | Promote ghosts promoted, migrated, queryable | ✅ All 35 done |
| 8 | Clean commit history on `cc-05-fork-audit` | ✅ |
| 9 | Branch merged to main | ⏸ pending this commit |
| 10 | DISCARD modules not deleted | ✅ (none classified) |
| 11 | ADAPT modules not modified | ✅ |
| 12 | NEW-NEEDED modules not created | ✅ |

**Verification:**
- `python manage.py check` → `System check identified no issues (0 silenced).`
- Ghost recompute → **0 ghosts remaining**.
- All 8 new CC-5 migrations (0043–0050) applied.

## All dispositions executed

| Group | Commit | Models | Notes |
|---|---|---|---|
| 1 Prune | d634b3e | 4 (AdminAction, ComponentStatus, CumulativeSales, Feedback) | dormant; no DDL |
| A Promote | 8025c67 | 10 (Gamification + Scoring) | |
| B Promote | d70606e + 3cf89ca | 6 of 7 (Financials) | also aligns Group A state |
| C Promote | df32b25 | 5 (Programs & Portfolio) | |
| D Promote | 2a5cab2 | 3 (Simulation State) | |
| E Promote | 8a512a9 | 5 (Messaging + Events) | TeamNotification already in CC-3.5 |
| F Promote | 7b7d0f9 | 5 (Instructor Tools) | CC-16 will EXTEND |
| NewSalesByRound | 385750c | 1 (with corrected PK schema) | R1 per promotion_questions.md |
| **Total** | | **4 pruned + 35 promoted = 39 of 39** | |

## CC-7 handoff items

- **0 DISCARD modules** to delete.
- **10 ADAPT modules** for refactor under their owning CC specs.
- **0 NEW-NEEDED modules** (CC-4 handled the supply-chain module set).
- **5 instructor surfaces** (3 EXTEND + 2 NEW-NEEDED) routed to CC-16.

## Commit history on branch (13 commits)

```
385750c CC-5 §5.5: promote NewSalesByRound with corrected composite-unique PK
0be67e1 CC-5 reports: final summary + promotion_questions after Groups A-F
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
