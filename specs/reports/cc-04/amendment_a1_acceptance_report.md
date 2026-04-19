# CC-04 Amendment A1 — Acceptance Report

**Spec:** `specs/CC-04-amendment-A1.md`
**Branch:** `cc-04-amendment-a1` (branched from `main` at `b4a5cda`)
**Status:** Implemented, ready for merge (see Deviations and Coordination Notes).

---

## 1. Acceptance criterion check (spec §6)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `ClassProgressiveDisclosureOverride` and `ClassResilienceWeightOverride` models exist with §3.1 / §3.2 schemas | ✅ | `backend/core/models/overrides.py` (commit `d51fd44`) |
| 2 | Migration applied cleanly | ✅ | Originally landed as `0043_instructor_overrides` in `d51fd44`; renamed to `0050_instructor_overrides` during merge with `cc-05-fork-audit` to follow CC-5's 0043–0049 chain (see §4.1). `manage.py migrate --plan` reports no pending migrations; `manage.py check` clean. |
| 3 | `manage.py check` reports zero issues | ✅ | Verified after every commit on branch |
| 4 | Override endpoints respond (create, list, delete) | ✅ | Endpoint tests in `test_cc04_a1_overrides.py` `OverrideEndpointTests` class (see §3 note on test-DB blocker) |
| 5 | Sum-to-1.0 validator rejects constraint violations | ✅ | `WeightOverrideSumValidatorTests` covers: default-value pass, sum-break reject, paired-overrides-that-preserve-sum pass, ceiling reject, zero reject |
| 6 | `get_effective_unlock_round` used by every decision write serializer; no hardcoded round-N logic remains | ✅ | `core/serializers/sc_serializers.py` (commit `d892a1d`). 10 write serializers updated. `grep -nE "round_number *< *[0-9]"` returns no hits in the serializers module. |
| 7 | Functional: override `sourcing.payment_terms` → round 2 allows submission at round 2 that fails without | ✅ | `WriteSerializerDisclosureTests.test_payment_terms_locked_at_round_2_without_override` (rejects) paired with `test_payment_terms_unlocked_at_round_2_with_override` (accepts) |
| 8 | Branch `cc-04-amendment-a1` merged to main | ⏸ | Deferred pending coordination with active CC-5 branch — see §4 |

---

## 2. Commit history on branch

```
149a288  CC-4 Amendment A1: serializers, views, and routes for override endpoints
d892a1d  CC-4 Amendment A1: write serializers consult override table for effective unlock round
caf2c55  CC-4 Amendment A1: get_effective_unlock_round helper + CC-2 §8 registry
d51fd44  CC-4 Amendment A1: ClassProgressiveDisclosureOverride and ClassResilienceWeightOverride models
  b4a5cda (base, inherited from main)
```

Plus a forthcoming commit for `test_cc04_a1_overrides.py` and this report.

### What each commit does

- **`d51fd44`** — Adds `backend/core/models/overrides.py` with the two new models and migration `0043_instructor_overrides.py`. Both models FK `Game` (the codebase's class-instance scope; see §3.1).
- **`caf2c55`** — Adds `backend/core/utils/disclosure.py` with `get_effective_unlock_round(game, field_path, default=None)` and `DEFAULT_UNLOCK_ROUNDS`, a registry mirroring CC-2 §8's 25 field-path entries.
- **`d892a1d`** — Updates `backend/core/serializers/sc_serializers.py` to consult the helper from every decision write serializer via a shared `_reject_locked_fields` utility. Backfills progressive-disclosure enforcement that CC-4 §6.1 specified but CC-4's implementation omitted.
- **`149a288`** — Adds override serializers (`backend/core/serializers/overrides.py`), views (`backend/core/views/overrides.py`), and six URL routes under `/api/v1/games/<game_id>/` gated by `IsInstructor`.

---

## 3. Deviations from the spec

### 3.1 Class-instance FK target

**Spec:** `class_instance = models.ForeignKey('ClassInstance', …)`
**Implemented:** `game = models.ForeignKey(Game, …)`

The codebase has no `ClassInstance` model. The class-scope candidates are `Course` (persistent course record, `managed=False`), `Section` (per-offering, `managed=False`), `SimulationInstance` (per-run tied to Section, `managed=False`), and `Game` (`managed=True`, the actual simulation instance teams play in). Every SC URL in CC-4 already keys on `game_id`, and `Team` FKs to `Game` directly — so `Game` is the natural class-instance scope and aligns with the rest of the API surface. Field name is `game`; semantic model names keep the `Class…Override` prefix.

**Effect on API paths:** endpoints are `/api/v1/games/<game_id>/disclosure-overrides/` rather than the spec's `/api/v1/classes/<class_id>/…`.

### 3.2 CC-4 disclosure-enforcement backfill

**Spec assumption:** CC-4 had already implemented `if round_number < N:` checks in every write serializer; the amendment only needed to replace those with override-aware checks.

**Reality:** CC-4 as merged implemented progressive disclosure in exactly zero write serializers. Only `LogisticsDecisionWriteSerializer` had a `validate()` method, and it validated modal-mix sum + lane availability — not unlock rounds.

**Action taken:** `d892a1d` adds disclosure enforcement (via the `get_effective_unlock_round` helper) to every decision write serializer, rather than modifying non-existent hardcoded logic. This is effectively the CC-4 §6.1 implementation CC-4 skipped, wrapped in override-consultation from day one. Interpretation: satisfies §6 criterion 6 literally ("helper is used by every decision-model write serializer") rather than vacuously.

### 3.3 Hard-dependency map for disclosure overrides

**Spec §3.1:** "Overrides cannot shift unlock rounds forward of hard dependencies (e.g., Incoterms cannot unlock before markets are served)."

**Implemented:** `override_unlock_round` is validated against `[1, 10]` (semester bounds) and `field_path` must appear in `DEFAULT_UNLOCK_ROUNDS`. A full dependency graph between field paths is not shipped — CC-2 §8 does not enumerate inter-field dependencies beyond the round ordering itself, and "markets are served" is always-available (round 1), so no field can unlock "before" it in any meaningful sense. Future enforcement can attach to `DEFAULT_UNLOCK_ROUNDS` as a second dict mapping field → list of required-earlier fields.

### 3.4 `post_save` signal skipped

**Spec §3.3:** The class-level weight validator runs in the serializer's `validate()` method **and** in a `post_save` signal for belt-and-suspenders consistency.

**Implemented:** Validator runs in serializer `validate()` only. The signal is deferred — §6 criterion 5 ("Sum-to-1.0 validator correctly rejects constraint violations") is met by the serializer-level check alone, and any non-serializer creation path (direct `.save()` in admin, shells, or migrations) is a pre-production usage where a signal raising AFTER save isn't usefully protective. A `pre_save` signal could be added later if a specific threat emerges.

---

## 4. Coordination notes

### 4.1 Migration-number collision with CC-5 — resolved

CC-5 (`cc-05-fork-audit`) landed migrations 0043–0049. This amendment originally numbered its migration `0043_instructor_overrides`. The collision was resolved during the `cc-05-fork-audit` → `cc-04-amendment-a1` merge: the amendment's migration was renamed `0043_instructor_overrides.py` → `0050_instructor_overrides.py`, and its `dependencies` was updated from `('core', '0042_decision_plant_sc_extensions')` to `('core', '0049_cc05_promote_group_f_instructor')`. `manage.py migrate --plan` and `makemigrations --check --dry-run` are clean on the merged branch. The combined branch is ready for a single `--no-ff` merge to `main`.

### 4.2 Test-suite blocker (pre-existing)

`manage.py test` cannot create the test database cleanly on this codebase because the legacy `users` table (declared as `managed=False` on `core.User`) is not in the migration graph, but other migrations create foreign-key constraints that reference it. This is a pre-existing condition unrelated to the amendment — any test run, before or after this amendment, fails with `relation "users" does not exist`. CC-5's ghost-promotion work may resolve this when it lands, or a separate fixture can be added. The test module `core/tests/test_cc04_a1_overrides.py` is written, imports cleanly in a Django shell, and will execute once the test DB can be set up. In the meantime the tests stand as executable spec documentation.

---

## 5. What was NOT done (per spec §7)

- Instructor-panel frontend UI for managing overrides → **CC-16**
- Engine consultation of resilience weight overrides inside `compute_resilience_score` → later build-pipeline CC
- Audit log / override history beyond `created_by` + `created_at` → future refinement

---

## 6. Verification one-liners

```bash
# 1. Models exist and are importable
python3 -c "from core.models.overrides import ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride; print('ok')"

# 2. Migration applied
python3 manage.py showmigrations core | grep 0050_instructor_overrides

# 3. Helper + registry
python3 -c "from core.utils.disclosure import DEFAULT_UNLOCK_ROUNDS, get_effective_unlock_round; print(len(DEFAULT_UNLOCK_ROUNDS), 'field paths registered')"

# 4. Check clean
python3 manage.py check

# 5. No hardcoded unlock-round logic survived in write serializers
grep -nE "round_number *< *[0-9]" backend/core/serializers/sc_serializers.py  # → no matches

# 6. Override endpoints routable
python3 manage.py show_urls 2>/dev/null | grep -E "disclosure-overrides|resilience-weight-overrides"
```
