# CC-03 Amendment A1 — Supplier-Origin-Trust Phase Reordering

**Amends:** `specs/CC-03-engine-logic.md`
**Parent decision:** `specs/CC-06-pedagogical-design-note.md` §3.4
**Status:** Ready for Claude Code execution (applies immediately, alongside CC-6)
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## 1. Purpose

Per CC-6 §3.4, supplier-origin-trust adjustment folds into segment preference initialization rather than standing as a standalone Phase 1 step. This amendment documents the change formally so CC-3 remains authoritative as the engine specification.

The original CC-3 document is unchanged (historical record). This amendment is the delta.

---

## 2. What Changes

### 2.1 Phase 1 step sequence

CC-3 §4 specified 29 Phase 1 steps. This amendment reduces that to 28 by removing the standalone step 11.

**Before (CC-3 §4):**
- Step 10: Marketing mix matching to segments
- **Step 11: Supplier-origin trust adjustment (applied to segment preferences)** — NEW standalone step
- Step 12: Bass adoption & competitive share calculation

**After this amendment:**
- Preference initialization step (which occurs before step 10 in CC-3's sequence) is extended to include supplier-origin-trust computation as part of preference hydration.
- Step 10: Marketing mix matching to segments (now operates on preferences that already carry supplier-origin-trust modulation).
- [Former step 11 removed.]
- Step 11 (was step 12): Bass adoption & competitive share calculation.
- All subsequent steps renumber accordingly (step 12 through step 28 are what CC-3 originally numbered 13 through 29).

### 2.2 Algorithm placement

CC-3 §6.6's `apply_supplier_origin_trust` function is unchanged in its logic. Only its invocation site shifts — it is called from within preference initialization rather than as a discrete pipeline step.

Pseudocode relocation:

```
# Original CC-3 pipeline (removed):
# Step 11: apply_supplier_origin_trust(team, segment_preferences, round_state)

# New placement: within preference initialization step
FUNCTION initialize_segment_preferences(team, round_state):
    preferences = load_baseline_preferences(scenario)
    preferences = apply_market_entry_adjustments(preferences, team, round_state)
    preferences = apply_supplier_origin_trust(team, preferences, round_state)   # NEW: folded in here
    preferences = apply_event_preference_perturbations(preferences, round_state)
    RETURN preferences
```

The exact pseudocode shape of `initialize_segment_preferences` depends on the existing GlobalStrat preference initialization (surfaced in CC-3's engine inventory report Section A). Claude Code locates the actual preference-init call site and inserts `apply_supplier_origin_trust` at that point, preserving existing initialization order.

### 2.3 Pedagogical framing

CC-3's original framing treated supplier-origin-trust as an adjustment applied to preferences. This amendment reframes it as a foundational component of preference hydration. The narrative in CC-3 §6.6 should be understood accordingly:

> Supplier-origin-trust is a foundational preference modifier. A buyer's perception of a firm is shaped from the start by the provenance of its supply chain — not as a late-arriving adjustment, but as part of how preferences are constituted in the first place.

This framing is pedagogically correct (matches how executives actually experience buyer perception) and simplifies the pipeline.

---

## 3. What Does NOT Change

- CC-3 §6.6 `apply_supplier_origin_trust` function body — unchanged.
- The symmetric extension of `origin_trust` matrix to supplier origins — unchanged.
- Interaction with existing buyer-side origin trust — both still apply, both still compound. Unchanged.
- `SupplierState`, `LaneState`, or any other data model — unchanged.
- Phase 2 pipeline — unchanged.
- Event system integration — unchanged.
- Determinism guarantees — unchanged.

---

## 4. Execution Steps for Claude Code

### 4.1 Branch

```bash
cd /home/ubuntu/projects/globalstrat+/
git checkout main
git pull --ff-only
git checkout -b cc-03-amendment-a1
```

### 4.2 File placement

Place this amendment at `specs/CC-03-amendment-A1.md`. No modifications to `specs/CC-03-engine-logic.md` — the original remains as historical record.

### 4.3 Commit

```bash
git add specs/CC-03-amendment-A1.md
git commit -m "CC-3 Amendment A1: supplier-origin-trust folds into preference initialization per CC-6 §3.4"
```

### 4.4 Verification

```bash
# Confirm CC-03-engine-logic.md is unchanged
git diff main..cc-03-amendment-a1 -- specs/CC-03-engine-logic.md
# Expect: no output (no diff)
```

### 4.5 Merge

Merges with CC-6's merge, not independently. See CC-6 §8 for merge sequencing.

---

## 5. Acceptance Criteria

1. `specs/CC-03-amendment-A1.md` exists and is committed.
2. `specs/CC-03-engine-logic.md` is byte-identical to its pre-amendment state.
3. No code changes.
4. No model changes.
5. No migrations.

---

## 6. Forward Impact

When engine implementation work happens in a future build-pipeline CC, the implementer reads:

1. CC-3 as the primary engine specification.
2. CC-03 Amendment A1 to adjust the step ordering before writing code.

The sequence plan's §3 foundation table reflects this amendment status.

No other specs need amending for this change — CC-4's data model does not reference the step numbering directly.
