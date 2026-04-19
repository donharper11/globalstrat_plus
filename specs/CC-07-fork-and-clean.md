# CC-7: Fork-and-Clean Execution

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Build pipeline — first bundle
**Depends on:** CC-5 merged (with all three classification reports), CC-04 Amendment A1 merged
**Observes:** `specs/STANDING-DISCIPLINE.md`
**Status:** Ready for Claude Code execution

---

## 1. Purpose

CC-5 classified every Python module in the fork as KEEP / ADAPT / DISCARD / NEW-NEEDED and triaged ghost models with limited execution (prune + promote only). CC-7 executes what CC-5 deferred:

- **DISCARD module deletion** — bulk removal of GlobalStrat-specific modules CC-5 classified as not-needed by globalstrat+
- **Surface-level ADAPT touch-ups** — minor modifications to ADAPT-classified modules that don't warrant their own dedicated CC spec (imports, docstrings, removed dead branches)
- **Orphan import cleanup** — references to pruned ghosts or deleted modules that linger in import statements but aren't called at runtime

CC-7 does NOT perform the substantial adaptations — those are individual build-pipeline CCs later in the sequence. CC-7 is cleanup, not refactoring.

**Distinction from CC-5's limited execution:** CC-5 pruned ghost model declarations. CC-7 removes the modules that contained only references to those ghosts, deletes GlobalStrat-specific scenario code globalstrat+ doesn't use, and tidies ADAPT-classified files to the minimum extent that doesn't warrant a dedicated later spec.

---

## 2. Preconditions

### 2.1 CC-5 merge confirmation

```bash
cd /home/ubuntu/projects/globalstrat+/
git log --oneline | grep -i "CC-5\|fork-audit" | head -5
# Expect: merge commit for CC-5 visible

ls specs/reports/cc-05/
# Expect: module_classification.md, ghost_triage.md, instructor_panel_audit.md, summary.md at minimum
```

If CC-5 has not merged, halt.

### 2.2 CC-04 Amendment A1 merge confirmation

```bash
git log --oneline | grep -i "amendment-a1\|instructor.override" | head -5
# Expect: merge commit for CC-04 Amendment A1 visible

python manage.py shell -c "from core.models import ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride; print('override models present')"
# Expect: "override models present"
```

If the amendment has not executed, halt.

### 2.3 Clean working tree

```bash
git status
# Expect: nothing to commit, working tree clean
```

If the tree is not clean, halt and report. Do not attempt to commit or stash existing state.

### 2.4 Test suite baseline

```bash
python manage.py test --verbosity=2 2>&1 | tail -20
```

Record the pass/fail count *before* any CC-7 changes. This is the baseline CC-7 must preserve or improve upon — any test that was passing before CC-7 must still pass after.

Commit the baseline as `specs/reports/cc-07/pre_execution_test_baseline.txt`.

---

## 3. Execution Strategy

CC-7 proceeds in three waves, each a logically-grouped batch of changes with its own verification checkpoint. Each wave commits independently. Failure in any wave halts CC-7 before the next wave begins.

**Wave 1 — DISCARD module deletion.** Remove files classified DISCARD by CC-5.

**Wave 2 — Orphan import cleanup.** Remove import statements that reference pruned ghosts or deleted modules but aren't called at runtime.

**Wave 3 — Surface-level ADAPT touch-ups.** Minor cleanup of ADAPT-classified modules (dead-branch removal, docstring updates, obvious dead code).

No wave refactors logic, renames functions, or changes public interfaces. That's substantive adaptation work reserved for dedicated specs.

---

## 4. Wave 1: DISCARD Module Deletion

### 4.1 Read the classification report

```bash
# Extract DISCARD-classified modules from CC-5's report
grep "DISCARD" specs/reports/cc-05/module_classification.md | awk -F'|' '{print $2}' | sed 's/[[:space:]]//g' > /tmp/discard_modules.txt
wc -l /tmp/discard_modules.txt
```

Review the list manually before proceeding. Each entry is a file path.

### 4.2 Reference safety check

For each DISCARD module, confirm nothing in a KEEP or ADAPT module imports from it:

```bash
while read module; do
    # Convert file path to module path (backend/core/foo/bar.py -> core.foo.bar)
    module_path=$(echo "$module" | sed 's|backend/||; s|/|.|g; s|.py$||')
    # Search for references
    refs=$(grep -rn "from $module_path\|import $module_path" backend/ --include="*.py" | grep -v "$module" | wc -l)
    if [ "$refs" -gt 0 ]; then
        echo "HALT: $module is referenced by $refs other files"
        echo "  References:"
        grep -rn "from $module_path\|import $module_path" backend/ --include="*.py" | grep -v "$module"
    fi
done < /tmp/discard_modules.txt
```

Any module with non-zero references triggers a halt per STANDING-DISCIPLINE §3. Resolution:
- If the referring files are themselves DISCARD (just not yet deleted), the deletion is safe — delete both together.
- If the referring files are KEEP or ADAPT, CC-5's classification may have missed a dependency. Halt, report the finding, and the spec author reviews whether the DISCARD classification was correct.

### 4.3 Delete in logical groups

Don't delete all DISCARD modules in one commit. Group by concern (e.g., "Media/Entertainment scenario code", "abandoned experiment X", "removed admin views"). Each group gets its own commit with a descriptive message listing what was removed and why.

Example commit structure:
```bash
git rm backend/core/media_scenario/specific_module.py backend/core/media_scenario/other_file.py
git commit -m "CC-7 Wave 1: remove Media/Entertainment scenario code

Per CC-5 module classification (specs/reports/cc-05/module_classification.md),
these modules are GlobalStrat-specific and not referenced by any globalstrat+
scenario. Safe removal verified against reference report §3.3.

Removed:
- backend/core/media_scenario/specific_module.py
- backend/core/media_scenario/other_file.py"
```

### 4.4 Verification after each group

After each logical group deletion:

```bash
python manage.py check
python manage.py test --verbosity=1 2>&1 | tail -20
```

Both must pass. Test count must match or exceed the pre-execution baseline from §2.4. If either fails, halt — don't continue deleting.

---

## 5. Wave 2: Orphan Import Cleanup

CC-5's ghost pruning removed model declarations. Wave 2 removes imports that referenced those declarations but weren't called at runtime (CC-5 classified them as "dormant references" during triage). Also removes imports to modules Wave 1 just deleted.

### 5.1 Enumerate orphan imports

```bash
# Imports referencing pruned ghost models
grep -rn "from.*import.*\(PrunedGhostA\|PrunedGhostB\|PrunedGhostC\)" backend/ --include="*.py" > /tmp/orphan_imports_ghosts.txt

# Imports referencing deleted modules (from Wave 1)
while read deleted_module; do
    module_path=$(echo "$deleted_module" | sed 's|backend/||; s|/|.|g; s|.py$||')
    grep -rn "from $module_path\|import $module_path" backend/ --include="*.py"
done < /tmp/discard_modules.txt > /tmp/orphan_imports_modules.txt
```

Substitute the actual ghost model names from `specs/reports/cc-05/ghost_triage.md` (§prune section) into the first grep.

### 5.2 Review before removing

Each orphan import's removal is a minor change, but collectively they can touch many files. Review the enumerated list. Any import that appears to be called somewhere (e.g., used in string form for a dynamic import, or referenced in `__all__` exports) is NOT an orphan — halt and investigate.

### 5.3 Remove orphan imports

Edit each file to remove the dead import. No other changes in these commits. One commit per logical group (per module that lost imports, typically).

```bash
git add <files with orphan imports removed>
git commit -m "CC-7 Wave 2: remove orphan imports of <pruned model / deleted module>

Imports referenced <target> which was pruned by CC-5 / deleted by CC-7 Wave 1.
No runtime references; confirmed by grep verification."
```

### 5.4 Verification

Same as Wave 1: `python manage.py check` and `python manage.py test` must pass after each commit.

---

## 6. Wave 3: Surface-level ADAPT Touch-ups

CC-5 classified many modules as ADAPT — meaning they need modifications in some later CC. Most of that modification work is deferred (it's what CC-8, CC-9, CC-16, CC-18, etc. are *for*). CC-7 handles only the surface-level touch-ups that don't warrant their own spec.

### 6.1 Eligible touch-ups

Touch-ups eligible in CC-7:

- **Obvious dead branches** — code paths flagged by CC-5 as unreachable in globalstrat+ (e.g., an `if scenario.type == "media":` branch when Media is a DISCARD scenario). Remove the branch, simplify the containing function.
- **Stale docstrings** — module or class docstrings that reference GlobalStrat-only concerns and would mislead a future reader of globalstrat+. Update or remove.
- **Commented-out code blocks** — that CC-5 flagged as obsolete. Delete.
- **Unused imports within ADAPT modules** — that became unused due to globalstrat+ not calling certain paths. Remove.

### 6.2 NOT eligible in CC-7

Explicitly out of scope — these are for later dedicated specs:

- Renaming functions or classes.
- Changing function signatures.
- Modifying business logic.
- Adding new capabilities.
- Changing migration strategies.
- Refactoring class hierarchies.
- Anything that would require a rollback if wrong.

When in doubt about whether a change is "surface-level," it's not. Defer to the later CC.

### 6.3 Read CC-5 ADAPT flags

CC-5's `module_classification.md` rationale column indicates which CC spec will handle each ADAPT module's substantive work. If CC-5 flagged specific surface-level touch-ups as "handled in CC-7," those are the eligible targets. Anything else is deferred.

### 6.4 Execute touch-ups

One commit per logical group. Each commit message explicitly states what was touched and cites CC-5's rationale.

### 6.5 Verification

Same as Waves 1 and 2. Tests pass. `manage.py check` clean.

---

## 7. Scenario YAML Hygiene

Adjacent to the Python module work: CC-5 may have flagged scenario YAML files for cleanup. Typical cases:

- GlobalStrat scenarios present in `backend/scenarios/` that globalstrat+ won't use (per CC-6 §5 authoring priorities — Media/Entertainment is Tier 4 / deliberately light).
- Per-scenario seed scripts or loaders that are no longer needed.

If CC-5's classification flagged scenario files for removal, handle them as a separate wave after Wave 3:

**Wave 4 — Scenario file cleanup.**

```bash
# Per CC-5 findings
git rm backend/scenarios/media_entertainment_full.yaml  # example
git commit -m "CC-7 Wave 4: remove Media/Entertainment full scenario per CC-5 / CC-6 §5 tier classification

Media/Entertainment is Tier 4 in CC-6's authoring priority (deliberately light
SC treatment). The full scenario file is GlobalStrat-era content no longer
needed. Scenario schema still supports a light or empty Media scenario if
future need emerges."
```

If CC-5 flagged no scenario files, skip Wave 4.

---

## 8. Post-execution audit

After all waves complete, produce a final report at `specs/reports/cc-07/execution_report.md`:

```markdown
# CC-7 Execution Report

## Summary
- Wave 1 (DISCARD deletion): N files deleted across M groups
- Wave 2 (orphan imports): K imports removed across L files
- Wave 3 (ADAPT touch-ups): P changes across Q files
- Wave 4 (scenario cleanup): R files (if applicable)

## Pre- vs. post-execution comparison
- Test count before: X passing, Y failing
- Test count after: X' passing, Y' failing
- `manage.py check` before: 0 issues
- `manage.py check` after: 0 issues

## Lines-of-code delta
```
# Generate via git diff stat
git diff main..cc-07-fork-and-clean --stat | tail -1
```

## Deferred items
List of CC-5 ADAPT items that require dedicated later specs, with the owning CC bundle named.

## Deviations from spec
Any halt that was resolved by spec-author adjustment, documented per STANDING-DISCIPLINE §3 format.
```

---

## 9. Halt Conditions

Per STANDING-DISCIPLINE §3, Claude Code halts with a MISMATCH report if:

1. Test count regresses from the pre-execution baseline (§2.4). Any test that was passing and is now failing is a halt.
2. `python manage.py check` reports any issue at any wave boundary.
3. A DISCARD module's reference-safety check (§4.2) surfaces an unexpected dependency from a KEEP or ADAPT module.
4. An orphan import turns out to have a dynamic reference (string-form import, `__all__` entry, `getattr` lookup) that grep didn't catch.
5. Any change exceeds the "surface-level" bar in §6.2.
6. CC-5's reports are incomplete, inconsistent, or cannot be parsed.

Halt, report, wait for spec-author resolution. Do not attempt to self-heal.

---

## 10. Git Strategy

All work on branch `cc-07-fork-and-clean`. Each wave is one or more commits. Merge to main via `--no-ff` after acceptance criteria pass.

```bash
git checkout main
git pull --ff-only
git checkout -b cc-07-fork-and-clean

# Execute Waves 1-3 (and 4 if applicable) with commits per group

# After acceptance verification:
git checkout main
git merge --no-ff cc-07-fork-and-clean -m "Merge CC-7: fork-and-clean execution"
```

Retain the branch post-merge per STANDING-DISCIPLINE §6.

---

## 11. Acceptance Criteria

CC-7 is complete when:

1. `specs/reports/cc-07/pre_execution_test_baseline.txt` exists and was committed at the start of the branch.
2. All DISCARD modules classified by CC-5 are deleted (Wave 1).
3. All orphan imports are removed (Wave 2).
4. All surface-level ADAPT touch-ups flagged by CC-5 for CC-7 handling are applied (Wave 3).
5. Scenario file cleanup is applied if CC-5 flagged it (Wave 4, if applicable).
6. `python manage.py check` reports zero issues.
7. `python manage.py test` passes with count matching or exceeding the pre-execution baseline.
8. `specs/reports/cc-07/execution_report.md` exists with the summary, comparison, LOC delta, deferred items, and any deviations.
9. Branch `cc-07-fork-and-clean` is merged to main.
10. No substantive refactoring occurred — all ADAPT modules requiring logic changes remain untouched pending their dedicated later specs.

**Report back with:** the execution report contents, pre- vs. post-test count comparison, LOC delta, and explicit confirmation that no substantive refactoring was performed.

---

## 12. What CC-7 Does NOT Do

| Concern | Owning spec |
|---|---|
| New scenario seed data (Consumer Electronics full content) | **CC-8** |
| Decision API validation logic implementation | **CC-9** |
| Frontend decision pages | **CC-10 through CC-14** |
| RAG content migration and new corpus ingestion | **CC-11** |
| Substantive refactoring of ADAPT-classified modules | Various later specs per CC-5 rationale |
| Engine pipeline implementation (Phase 1 algorithm execution) | **CC-18, CC-19, CC-20** |
| Phase 2 LLM narrative authoring | **CC-17** |

---

## 13. Forward Impact

With CC-7 merged, the codebase is:

- Trimmed of GlobalStrat-specific modules globalstrat+ doesn't use
- Free of orphan imports and dormant scaffolding
- Consistent between model-registry state and physical tables (via CC-5's ghost work)
- Aligned docstrings and dead-branch-free in ADAPT modules

This is the clean foundation the build pipeline operates against. CC-8 through CC-22 build features on top of a codebase that now has zero archaeology to navigate around.

---

## 14. Revision Log

| Date / Milestone | Change |
|---|---|
| CC-7 drafted | Initial fork-and-clean execution spec. Consumes CC-5's three classification reports. Three-wave structure (DISCARD deletion, orphan imports, surface-level ADAPT touch-ups) plus optional Wave 4 for scenario files. |
