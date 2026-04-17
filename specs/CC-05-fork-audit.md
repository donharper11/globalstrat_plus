# CC-5: globalstrat+ Fork Audit

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — fork audit and ghost model triage
**Depends on:** CC-1 through CC-4 merged. CC-3.5 determinism and TeamNotification work landed.
**Observes:** `specs/STANDING-DISCIPLINE.md`
**Status:** Ready for Claude Code execution

---

## 1. Purpose

CC-5 is an evaluative spec. It does not write production code, add features, or extend schema. Its job is to classify the existing forked GlobalStrat codebase against the globalstrat+ design and produce actionable dispositions for cleanup and extension work that follows in the build pipeline.

Three outputs:

1. **Module classification report** — every Python module in the fork tagged KEEP / ADAPT / DISCARD / NEW-NEEDED, with rationale.
2. **Ghost model triage** — the 40 ghost models identified in CC-1 Amendment A1 D2 triaged into prune / promote / document-as-dormant, with explicit disposition per model.
3. **Instructor panel audit** — classification of existing instructor views against globalstrat+'s SC-specific needs (event injection UI, resilience dashboard, compliance regime toggles, progressive disclosure overrides).

Limited execution is authorized within CC-5: ghost-model pruning (removing dormant scaffolds) and promoting ghosts that globalstrat+ needs. All other cleanup work is scoped into the build pipeline as CC-7.

---

## 2. Why This Comes After CC-4

Running CC-5 after CC-4 has two specific benefits:

- CC-4 has surfaced which existing models globalstrat+ actually depends on as FK targets. CC-5 can use that reference set to classify upstream models by actual usage rather than assumed usage.
- CC-4 introduces new models and potentially surfaces conflicts or interactions with existing code that CC-5 can catch during classification.

CC-5 before CC-4 would have worked, but CC-5 after CC-4 is cleaner for classification.

---

## 3. Precondition — Baseline Inventory

### 3.1 Codebase enumeration

Claude Code enumerates the forked codebase at module granularity:

```bash
cd /home/ubuntu/projects/globalstrat+/

# All Python files in backend (excluding tests, migrations, virtual envs, and vendor directories)
find backend -name "*.py" \
  -not -path "*/migrations/*" \
  -not -path "*/tests/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/venv/*" \
  -not -path "*/node_modules/*" \
  | sort > /tmp/fork_audit_modules.txt

wc -l /tmp/fork_audit_modules.txt
```

The output is the full module surface to classify.

### 3.2 Ghost model enumeration

Per STANDING-DISCIPLINE §1.8, re-compute the current ghost set (may differ slightly from CC-1's count given CC-3.5 promoted `messaging.TeamNotification`):

```bash
python manage.py shell <<'PY'
from django.apps import apps
from django.db import connection

# Django-registered models
registered = set()
for m in apps.get_models():
    registered.add((m._meta.label, m._meta.db_table, m._meta.managed))

# Physical tables
with connection.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    physical = {row[0] for row in cur.fetchall()}

# Ghosts = registered with a db_table that isn't in physical
ghosts = [(label, table, managed) for label, table, managed in registered if table not in physical]
for label, table, managed in sorted(ghosts):
    print(f"{label}\t{table}\tmanaged={managed}")
print(f"\nTotal ghosts: {len(ghosts)}")
PY
```

Expected: approximately 39 ghosts (40 original minus TeamNotification promoted in CC-3.5, possibly more if CC-4 surfaced any that it halted on).

### 3.3 Baseline commit

Before classification work begins, create the audit branch and commit the raw inventories:

```bash
git checkout -b cc-05-fork-audit
mkdir -p specs/reports/cc-05
cp /tmp/fork_audit_modules.txt specs/reports/cc-05/module_inventory.txt
# Ghost list also captured
git add specs/reports/cc-05/
git commit -m "CC-5: baseline inventories for fork audit"
```

---

## 4. Classification Framework

### 4.1 Module-level classification

Every enumerated module (§3.1) gets exactly one classification:

- **KEEP** — module is used as-is by globalstrat+. No changes. Examples: authentication middleware, base model classes, utility libraries, Phase 2 orchestration infrastructure.
- **ADAPT** — module is used by globalstrat+ but requires modifications documented in a prior or future CC spec. Examples: `core/engine/costs.py` (CC-3 extends calculate_cogs and calculate_logistics_tariffs), `core/models/plants.py` (CC-4 extends DecisionPlant).
- **DISCARD** — module is GlobalStrat-specific, not referenced by globalstrat+, and carries no dormant value. Safe to delete. Examples: scenario-specific code for Media/Entertainment features that don't exist in globalstrat+ scenarios, abandoned experiments.
- **NEW-NEEDED** — module does not exist in the fork but globalstrat+ requires it. Examples: `core/engine/supply_chain.py`, `core/models/supplier.py` (CC-4 creates these).

DISCARD is applied conservatively. When in doubt, KEEP or ADAPT. The question "does this hurt globalstrat+ if it remains?" is usually "no," and deletion introduces risk. DISCARD is reserved for modules that are clearly orphaned and whose presence creates confusion.

### 4.2 Ghost model triage

Every ghost model from §3.2 gets exactly one disposition:

- **Prune** — model declaration is deleted from `models.py`. No migration needed (no table to drop). Default disposition per CC-1 Amendment A1 §3.
- **Promote** — model is needed by globalstrat+. `managed = False` becomes `managed = True` (or the declaration is cleaned up if it was never `managed = False`), a migration is generated to create the table, and the migration is applied. Only applied to ghosts that a named current or imminent CC spec references.
- **Document-as-dormant** — model declaration stays, with an explicit `# DORMANT: [reason]` comment, and is added to a dormant registry. Only used when a specific future CC bundle is named that will promote it.

**Promote rules:**

A ghost is promoted only if all of:
1. A current or already-drafted CC spec (CC-1 through CC-6, or named amendments) references it by name
2. Its absence would block build pipeline work
3. The promotion doesn't require schema assumptions that haven't been reviewed

Ghosts that might be useful someday but aren't referenced by any drafted spec are pruned, not document-as-dormant'd.

**Document-as-dormant rules:**

Reserved for ghosts where:
1. A specific future CC bundle (not yet drafted) is named, AND
2. The ghost's schema is sufficiently documented to be promoted later without archaeology, AND
3. Deleting it would require re-recreating the same model from scratch later

The default bias is strongly against document-as-dormant. Three or fewer dormant ghosts across the audit is the target.

### 4.3 Instructor panel classification

Every existing instructor view/template/endpoint gets one of:

- **KEEP (SC-compatible)** — works as-is for globalstrat+, no SC-specific additions needed.
- **EXTEND (SC-aware)** — works for GlobalStrat mechanics but requires additions for SC decision visibility, SC event injection, resilience dashboard, or instructor overrides. Routed to CC-16 for implementation.
- **NEW-NEEDED** — globalstrat+ requires an instructor view that doesn't exist. Routed to CC-16.
- **DISCARD** — GlobalStrat-specific, no globalstrat+ relevance.

Per the working assumption that 90% of the instructor panel inherits, the KEEP column is expected to dominate.

---

## 5. Execution Steps

### 5.1 Module classification pass

For each module in `specs/reports/cc-05/module_inventory.txt`, Claude Code:

1. Opens the file
2. Reads the module's purpose (docstring, imports, key exports)
3. Cross-references against CC-1 through CC-6 specs (and their amendments) for any mentions
4. Cross-references against CC-4's reference inventory for FK dependencies
5. Assigns classification with a one-line rationale

Result: `specs/reports/cc-05/module_classification.md` with a table:

```
| Module | Classification | Rationale | References |
|--------|----------------|-----------|------------|
| backend/core/engine/advance_round.py | ADAPT | CC-3 specifies step additions | CC-3 §4 |
| backend/core/engine/costs.py | ADAPT | CC-3 EXTEND for calculate_cogs, calculate_logistics_tariffs | CC-3 §4 steps 16-17 |
| backend/core/models/supplier.py | NEW-NEEDED | CC-4 creates this module | CC-4 §4.1.1 |
| backend/core/media_scenario/specific_thing.py | DISCARD | Media/Entertainment only, no globalstrat+ scenario uses it | — |
| ... | ... | ... | ... |
```

### 5.2 Ghost triage pass

For each ghost model in the §3.2 enumeration, Claude Code:

1. Locates the model declaration in the codebase (`grep -rn "class ModelName" --include="*.py"`)
2. Identifies any imports or references to the model (`grep -rn "ModelName" --include="*.py"`)
3. Classifies references as live (called at runtime) vs. dormant (imported but not called)
4. Cross-references CC-1 through CC-6 for explicit mentions
5. Assigns disposition per §4.2 rules

Result: `specs/reports/cc-05/ghost_triage.md`:

```
## Prune (N ghosts)
- `module.ModelA` — no references in drafted specs, imports appear in 1 dormant location (details)
- `module.ModelB` — ...
- ...

## Promote (N ghosts)
- `financials.FinancialExpense` — referenced dormantly in preference_engine.py:22, CC-5 promotes if build pipeline requires financials subsystem; otherwise prunes
- `module.ModelX` — ...

## Document-as-dormant (N ghosts)
- `module.ModelY` — reason: [specific future CC named]. Schema documented in this report for future promotion.
- ...
```

Target distribution: prune dominates. Promote is small. Document-as-dormant is minimal (≤3).

### 5.3 Instructor panel audit

Locate instructor views:

```bash
grep -rn "instructor" backend/core/views/ --include="*.py" -l
grep -rn "is_instructor\|InstructorRequired" backend/ --include="*.py" -l
```

For each identified instructor view/endpoint/template:

1. Document its current purpose
2. Cross-reference against globalstrat+ instructor needs (from CC-3 §8, CC-6 §3.2, CC-6 §3.3, and sequence plan CC-16 scope)
3. Classify per §4.3

Result: `specs/reports/cc-05/instructor_panel_audit.md` with the classification table and a summary that feeds into CC-16's eventual scope.

### 5.4 Limited execution: prune approved ghosts

After the three classification reports are written and reviewed:

For each ghost classified as **Prune**:

1. Locate and remove the class declaration from `models.py`.
2. Remove related imports where they exist as dormant scaffolding (imports that were flagged during triage as not-called-at-runtime).
3. Run `python manage.py check` after each batch of removals. Zero issues expected.
4. Commit the pruning in logical groups (related ghosts pruned together).

### 5.5 Limited execution: promote required ghosts

For each ghost classified as **Promote**:

1. Change `managed = False` to `managed = True` (or clean up the declaration if the managed attribute wasn't set).
2. Run `python manage.py makemigrations` — a CreateModel migration should be generated.
3. Inspect the migration before applying. Confirm the schema matches the ghost's current field definitions.
4. Apply the migration: `python manage.py migrate`.
5. Verify with `python manage.py dbshell -c "\d table_name"`.
6. Run `python manage.py check`. Zero issues.

If any ghost's promotion reveals schema questions (e.g., the model's fields look incomplete, foreign keys reference other ghosts), halt and add the question to `specs/reports/cc-05/promotion_questions.md` for the spec author to resolve before proceeding.

### 5.6 Deferred execution

These tasks are scoped into CC-5's outputs but executed in CC-7 or later, not during CC-5 itself:

- Deleting modules classified as DISCARD (beyond pure ghost-model scaffolding).
- Refactoring modules classified as ADAPT.
- Building modules classified as NEW-NEEDED.
- Extending instructor views classified as EXTEND.

CC-5 produces the classification; CC-7 (fork-and-clean execution) performs the cleanup in one pass.

---

## 6. Halt Conditions

Per STANDING-DISCIPLINE §3, Claude Code halts with a MISMATCH report if:

1. A ghost's declaration cannot be located or parsed cleanly.
2. A prune operation's `manage.py check` surfaces errors (indicates the ghost was referenced in ways the grep didn't catch).
3. A promote operation's migration has a schema that doesn't match the ghost's current field definitions (drift between model and spec expectation).
4. Any classification decision requires design judgment the spec author hasn't made (example: a ghost that looks useful but has no named CC referencing it — the disposition rule would default to prune, but Claude Code should surface to the spec author first if the model's purpose suggests future value).
5. Instructor panel audit surfaces a view that looks SC-relevant but has no CC-16 scope decision associated with it.

---

## 7. Verification Checkpoints

Per STANDING-DISCIPLINE §5:

### 7.1 After module classification

- All modules from the §3.1 inventory have exactly one classification.
- Every ADAPT classification references a specific CC spec.
- Every NEW-NEEDED classification references a specific CC spec.
- Classification report is reviewed by the spec author before proceeding to triage.

### 7.2 After ghost triage

- Every ghost from the §3.2 enumeration has exactly one disposition.
- Every Promote disposition cites a specific CC spec that references it.
- Every Document-as-dormant cites a specific future CC bundle.
- Prune-count ≥ 70% of total ghosts. (If lower, the discipline rule is being applied too loosely — review.)

### 7.3 After prune execution

- `python manage.py check` passes.
- `python manage.py test` passes (if tests exist on the code paths touched).
- `git log --oneline` shows one commit per logical pruning group.

### 7.4 After promote execution

- `python manage.py showmigrations` shows new migrations applied.
- `python manage.py dbshell -c "\dt"` shows new tables.
- Tables are queryable via ORM (empty results, no exceptions).

### 7.5 Final audit report

- `specs/reports/cc-05/module_classification.md` complete.
- `specs/reports/cc-05/ghost_triage.md` complete.
- `specs/reports/cc-05/instructor_panel_audit.md` complete.
- `specs/reports/cc-05/promotion_questions.md` if any questions arose.
- Summary report at `specs/reports/cc-05/summary.md` listing counts, decisions, and CC-7 handoff items.

---

## 8. What This Spec Does NOT Cover

| Concern | Spec |
|---|---|
| Deleting modules classified DISCARD | **CC-7** (fork-and-clean execution) |
| Refactoring modules classified ADAPT | Specific later CCs that implement each adaptation |
| Building modules classified NEW-NEEDED | Build pipeline CCs starting at CC-7 |
| Instructor panel SC-extension implementation | **CC-16** |
| Any non-ghost schema changes | Out of scope for CC-5 entirely |

---

## 9. Acceptance Criteria

CC-5 is complete when:

1. `specs/reports/cc-05/module_inventory.txt` exists with the full module enumeration.
2. `specs/reports/cc-05/module_classification.md` exists with every module classified.
3. `specs/reports/cc-05/ghost_triage.md` exists with every ghost dispositioned.
4. `specs/reports/cc-05/instructor_panel_audit.md` exists with every instructor view classified.
5. `specs/reports/cc-05/summary.md` exists with counts and CC-7 handoff list.
6. All ghosts dispositioned as Prune have been removed from `models.py`. `python manage.py check` passes.
7. All ghosts dispositioned as Promote have been promoted, migrated, and are queryable. `python manage.py check` passes.
8. `git log --oneline` on branch `cc-05-fork-audit` shows a clean commit history (inventories, classification reports, prune groups, promote operations).
9. Branch `cc-05-fork-audit` merged to main after verification.
10. No modules classified as DISCARD have been deleted (deferred to CC-7).
11. No modules classified as ADAPT have been modified (deferred to specific later CCs).
12. No NEW-NEEDED modules have been created (deferred to build pipeline).

**Report back with:** the summary report contents, ghost prune/promote counts, `python manage.py check` output, and explicit confirmation that deferred categories (DISCARD modules, ADAPT modules, NEW-NEEDED modules) were not executed.

---

## 10. Named Triage Inputs

Items surfaced in prior specs that CC-5 specifically addresses:

- **`financials.FinancialExpense`** — named in CC-SEQUENCE-PLAN.md §3 and CC-3.5 as a deferred triage target. CC-5 disposition expected to be Prune (dormant import, no live caller), unless cross-referencing surfaces dependencies not yet observed.
- The 39 other ghosts from the CC-1 count (minus TeamNotification promoted in CC-3.5) — triaged per §4.2 rules.
- Instructor panel extensions flagged in CC-3 §8 (event injection, state override, scenario parameter override per class) — classified per §4.3.
- Instructor panel override UI surfaces from CC-6 §3.2 and §3.3 — classified per §4.3 and routed to CC-16.

---

## 11. Post-CC-5 Sequence

With CC-5 merged, the foundation layer is fully complete. The post-foundation state:

- **CC-1 through CC-6** — all foundation specs merged, with companion amendments
- **CC-04 Amendment A1** — can execute now (CC-4 is merged)
- **CC-7 and onward** — build pipeline begins per sequence plan §4

The CC Sequence Plan's revision log gets an entry marking foundation completion.

---

## 12. Revision Log

| Date / Milestone | Change |
|---|---|
| CC-5 drafted | Initial fork audit spec with module classification, ghost triage, and instructor panel audit. Limited execution authorized for ghost pruning and promotion only. |
