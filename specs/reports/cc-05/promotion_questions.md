---
name: CC-5 promotion questions
description: Post-execution — Option A completed under CC-5 Amendment A1; one schema halt remains (NewSalesByRound)
type: report
---

# CC-5 §5.5 — Promotion Questions (Status: Resolved except NewSalesByRound)

*Originally raised 2026-04-19 as §6.4 halt flag. Updated same day after spec-author authorized Option A via `CC-05-amendment-A1.md` (rule #2 — live runtime reference — sufficient for Promote).*

## Resolution

**Original question (Q1): Authorize blanket promotion under rule #2?**
→ **Resolved.** CC-5 Amendment A1 (commit 9526c45) relaxed §4.2 rule #1: "live runtime reference is sufficient grounds for Promote; named-in-CC-spec is sufficient but not necessary."

**Original question (Q2): Per-model schema review gate / commit grouping?**
→ **Resolved.** Executed as 6 subsystem-grouped commits (Groups A–F). Each migration generated, inspected, and applied with `SeparateDatabaseAndState` + idempotent `CREATE TABLE IF NOT EXISTS`. `python manage.py check` clean after each group.

**Original questions (Q3, Q4): Viewset-only ghosts — prune or promote?**
→ **Resolved via Option A.** All viewset-only ghosts (Instructor Tools set + Decision) promoted. Rationale: CC-16 is the named consumer for instructor extensions; the tables need to exist for that work. Decision is part of the Programs subsystem coherence.

## Execution results

| Group | Commit | Models promoted | Notes |
|---|---|---|---|
| 1 (Prune) | d634b3e | 4 (AdminAction, ComponentStatus, CumulativeSales, Feedback) | dormant; no DDL |
| A | 8025c67 | 10 (Gamification + Scoring) | options={} retroactively aligned in Group B |
| B | d70606e + 3cf89ca | 6 of 7 (Financials) | NewSalesByRound halted — see below |
| C | df32b25 | 5 (Programs & Portfolio) | |
| D | 2a5cab2 | 3 (Simulation State) | |
| E | 8a512a9 | 5 (Messaging + Events) | TeamNotification already done in CC-3.5 |
| F | 7b7d0f9 | 5 (Instructor Tools) | CC-16 will EXTEND |
| **Total** | | **4 pruned + 34 promoted = 38 of 39** | |

Post-execution verification:
- `python manage.py check` → no issues
- `python manage.py makemigrations --dry-run core` → no changes detected
- Ghost recompute → **1 remaining** (NewSalesByRound by design)

## Outstanding — NewSalesByRound (1 ghost)

This is the only remaining halt. Surfaced under §6.4 and §5.5 step 3 ("schema doesn't match the ghost's current field definitions").

### The problem

```python
class NewSalesByRound(models.Model):
    round_id = models.IntegerField(primary_key=True)   # PK on single column
    customer_id = models.IntegerField()
    program_id = models.IntegerField()
    new_sales = models.IntegerField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'new_sales_by_round'
        unique_together = (('round_id', 'customer_id', 'program_id'),)
```

`round_id` is declared `primary_key=True`, which means the PK constraint would enforce at most one row per `round_id`. But the `unique_together` on `(round_id, customer_id, program_id)` strongly suggests the intended semantics is one row per (round, customer, program) — which means many rows per round. These two constraints are mutually inconsistent: if you have multiple rows with the same `round_id` (different customers or programs), the PK is violated.

### Options

- **Option R1 — Promote with composite PK:** Drop the `primary_key=True` from `round_id`, add an `AutoField(primary_key=True)` (e.g., `sales_id`), keep `unique_together`. This matches the apparent semantics and parallels how e.g. `financial_revenue` keys itself.
- **Option R2 — Promote with PK on the composite:** Drop `primary_key=True` from `round_id`, mark `(round_id, customer_id, program_id)` as the PK instead of just unique. Requires a Django model change (no single-column AutoField).
- **Option R3 — Promote as-declared:** Create the table with `round_id INTEGER PRIMARY KEY`. Runtime will fail on the second insert for the same round. Likely incorrect.
- **Option R4 — Prune (re-triage):** Classify NewSalesByRound as Prune. The triage lists only a viewset (`financials.py:130`) and "used in scoring" with no named line — no hard runtime dependency was proven. If the rest of the system works without it (Group B promotions applied cleanly and all engine code references already resolved), the viewset-only usage is consistent with Prune.
- **Option R5 — Document-as-dormant:** Keep the declaration, comment it `# DORMANT — schema needs redesign before promotion`, ship to main as-is.

### Recommendation

R4 (Prune) or R1 (Promote with corrected PK). Both are clean. R1 requires a model source change that should be explicitly authorized. R4 is the lowest-risk path and aligns with the original prune-default discipline for ghosts whose runtime usage isn't demonstrated.

Awaiting spec-author decision before merging `cc-05-fork-audit` to main.
