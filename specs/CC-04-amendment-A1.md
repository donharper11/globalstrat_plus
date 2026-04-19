# CC-04 Amendment A1 — Instructor Override Models

**Amends:** `specs/CC-04-data-model.md`
**Parent decisions:** `specs/CC-06-pedagogical-design-note.md` §3.2 and §3.3
**Status:** **Executed on branch `cc-04-amendment-a1`**. Merged twice with `cc-05-fork-audit` as CC-5's migration chain grew; migration renumbered 0043 → 0050 → `0051_instructor_overrides`. Test suite: 16 of 16 pass on fresh DB. Acceptance report: `specs/reports/cc-04/amendment_a1_acceptance_report.md`. Pending merge to `main`.
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## 1. Purpose

Per CC-6 §3.2 and §3.3, instructors can override the default progressive disclosure schedule and the resilience score weights on a per-class basis. This amendment introduces the data model and API surface required to support those overrides.

The original CC-4 is unchanged. This amendment is a delta — two new models, migrations, serializers, endpoints, and one serializer-logic adjustment to consult the override tables.

**Execution timing:** this amendment is NOT executed alongside CC-6. It executes only after CC-4 has merged to main. The reason is mechanical — CC-4 defines the base models these overrides reference (Class, Round, Team), and the serializer logic being modified here is itself defined by CC-4. Executing this amendment before CC-4 merges would touch files that don't yet exist.

---

## 2. Precondition — CC-4 Merge Confirmation

Before this amendment executes, Claude Code verifies:

```bash
cd /home/ubuntu/projects/globalstrat+/
git log --oneline | head -20 | grep -i "CC-4"
# Expect: merge commit for CC-4 visible in recent history

python manage.py showmigrations | grep -E "00(40|41|42|43|44|45|46|47|48)"
# Expect: all CC-4 migrations shown as [X] applied
```

If CC-4 has not merged, halt with a clear message and wait.

Per STANDING-DISCIPLINE §1.8, also verify the models this amendment references exist as physical tables:

- `ClassInstance` (or whatever the class-scope model is — inferred from CC-4's reference inventory report Section A)
- All CC-4 decision models referenced by the write-serializer logic modification in §4

---

## 3. What This Amendment Adds

### 3.1 Model: `ClassProgressiveDisclosureOverride`

```python
class ClassProgressiveDisclosureOverride(models.Model):
    """
    Instructor-set override of the default progressive disclosure unlock round
    for a specific field, scoped to a single class.

    Baseline schedule lives in CC-2 §8. This table captures deviations.
    """

    class_instance = models.ForeignKey('ClassInstance', on_delete=models.CASCADE, related_name='disclosure_overrides')
    field_path = models.CharField(max_length=200)  # e.g., "sourcing.payment_terms", "logistics.customs_classification"
    override_unlock_round = models.IntegerField()

    created_by = models.ForeignKey('User', on_delete=models.PROTECT, related_name='created_disclosure_overrides')
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=500, blank=True)

    class Meta:
        unique_together = [('class_instance', 'field_path')]
        indexes = [
            models.Index(fields=['class_instance']),
        ]

    def __str__(self):
        return f"{self.class_instance} {self.field_path} -> round {self.override_unlock_round}"
```

**Field path convention:** dot-notation path using decision-page name and field name. Examples: `sourcing.payment_terms`, `sourcing.tier_2_3_visibility_investment`, `logistics.customs_classification`, `trade_finance.sinosure_enrolled_markets`.

**Validation:**
- `override_unlock_round` must be ≥ 1 and ≤ 10 (within the semester range).
- `field_path` must match a known CC-2 field. Enforced via a validator that checks against a registry of known field paths (populated from CC-2 §8 at module load time).
- Overrides cannot shift unlock rounds forward of hard dependencies (e.g., Incoterms cannot unlock before markets are served). Validator enforces this against a dependency map.

### 3.2 Model: `ClassResilienceWeightOverride`

```python
class ClassResilienceWeightOverride(models.Model):
    """
    Instructor-set override of resilience score weights for a specific class.
    Baseline weights live in the scenario's ResilienceParameters.
    """

    WEIGHT_CHOICES = [
        ('multi_sourcing', 'Multi-sourcing'),
        ('geographic_diversity', 'Geographic Diversity'),
        ('buffer_inventory_adequacy', 'Buffer Inventory Adequacy'),
        ('modal_flexibility', 'Modal Flexibility'),
        ('tier_2_visibility', 'Tier-2 Visibility'),
        ('supplier_financial_health', 'Supplier Financial Health'),
    ]

    class_instance = models.ForeignKey('ClassInstance', on_delete=models.CASCADE, related_name='resilience_weight_overrides')
    weight_name = models.CharField(max_length=50, choices=WEIGHT_CHOICES)
    override_value = models.DecimalField(max_digits=4, decimal_places=3)

    created_by = models.ForeignKey('User', on_delete=models.PROTECT, related_name='created_weight_overrides')
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=500, blank=True)

    class Meta:
        unique_together = [('class_instance', 'weight_name')]
```

**Validation constraints** (enforced at class-level, not row-level — see §3.3 validator):
- No individual `override_value` may be negative or zero.
- No individual `override_value` may exceed 0.6.
- Sum of all override values for a class, combined with non-overridden scenario defaults for that class, must equal 1.0 (±0.01 tolerance).

### 3.3 Class-level validator

Because the sum-to-1.0 constraint spans multiple override rows, validation cannot be row-level. A class-level validator runs on any override row save:

```python
def validate_class_weight_overrides(class_instance):
    """
    Called after any ClassResilienceWeightOverride save or delete.
    Confirms the combined weight set (overrides + scenario defaults for non-overridden weights) sums to 1.0.
    """
    overrides = class_instance.resilience_weight_overrides.all()
    override_map = {o.weight_name: float(o.override_value) for o in overrides}

    scenario = class_instance.scenario
    scenario_weights = scenario.resilience_parameters.resilience_score_weights

    combined = {}
    for weight_name in ClassResilienceWeightOverride.WEIGHT_CHOICES:
        wname = weight_name[0]
        combined[wname] = override_map.get(wname, scenario_weights.get(wname, 0))

    total = sum(combined.values())
    if abs(total - 1.0) > 0.01:
        raise ValidationError(f"Combined weights sum to {total}, must be 1.0 (±0.01)")
```

This validator runs in the serializer's `validate` method and in a post_save signal for belt-and-suspenders consistency.

### 3.4 Migration

Single migration: `0049_instructor_overrides.py` (or whatever the next number is — verify via `showmigrations`).

Creates both new tables. Reversible.

### 3.5 Serializers

Standard `ModelSerializer` for each of the two new models. Write serializers include the §3.3 class-level validator for `ClassResilienceWeightOverride`.

### 3.6 API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/classes/{class_id}/disclosure-overrides/` | List overrides for this class |
| POST | `/api/v1/classes/{class_id}/disclosure-overrides/` | Create an override |
| DELETE | `/api/v1/classes/{class_id}/disclosure-overrides/{id}/` | Remove an override (revert to default) |
| GET | `/api/v1/classes/{class_id}/resilience-weight-overrides/` | List overrides for this class |
| POST | `/api/v1/classes/{class_id}/resilience-weight-overrides/` | Create or update an override |
| DELETE | `/api/v1/classes/{class_id}/resilience-weight-overrides/{id}/` | Remove an override |

All endpoints are instructor-only (permission class restricts to users with instructor role on the referenced class).

---

## 4. What This Amendment Modifies in CC-4's Code

### 4.1 Write-serializer progressive disclosure enforcement

CC-4 §6.1 shows the progressive disclosure check pattern in write serializers:

```python
# From CC-4 §6.1, LogisticsDecisionWriteSerializer example
def validate(self, data):
    round_number = data['round'].number
    if round_number < 3:
        # Modal mix locked — reject any non-default values
        ...
```

This amendment modifies that pattern to consult the override table first:

```python
def validate(self, data):
    round_number = data['round'].number
    class_instance = data['team'].class_instance

    # Default unlock round for this field
    default_unlock_round = 3  # from CC-2 §8

    # Consult override table
    override = ClassProgressiveDisclosureOverride.objects.filter(
        class_instance=class_instance,
        field_path='logistics.modal_mix'
    ).first()
    effective_unlock_round = override.override_unlock_round if override else default_unlock_round

    if round_number < effective_unlock_round:
        # Field locked — reject
        if any([data.get(f) for f in ['mode_sea_pct', 'mode_air_pct', 'mode_rail_pct', 'mode_road_pct']]):
            raise serializers.ValidationError("Modal mix not yet unlocked at this round for this class")
    # ... rest of validation
```

A helper utility is introduced to keep this DRY across all write serializers:

```python
# core/utils/disclosure.py

def get_effective_unlock_round(class_instance, field_path, default_unlock_round):
    """
    Returns the effective unlock round for a field in a given class.
    Checks for an instructor override; falls back to the CC-2 §8 default.
    """
    override = ClassProgressiveDisclosureOverride.objects.filter(
        class_instance=class_instance,
        field_path=field_path
    ).first()
    return override.override_unlock_round if override else default_unlock_round
```

Every write serializer that enforces progressive disclosure is updated to call this helper.

### 4.2 Files modified in CC-4's codebase

Based on CC-4's write serializers (all decision-model write serializers per §6.1):

- `backend/core/serializers/sourcing.py`
- `backend/core/serializers/logistics.py`
- `backend/core/serializers/trade_finance.py`
- `backend/core/serializers/inventory.py`
- `backend/core/serializers/extend_esg.py` (or wherever ESG EXTEND serializer lives)
- `backend/core/serializers/extend_plant.py` (or wherever DecisionPlant EXTEND serializer lives)

Exact paths confirmed against CC-4's implementation after merge.

---

## 5. Execution Steps for Claude Code

### 5.1 Precondition check

Per §2 above. Verify CC-4 is merged. Halt if not.

### 5.2 Branch

```bash
git checkout main
git pull --ff-only
git checkout -b cc-04-amendment-a1
```

### 5.3 Create models

Add `ClassProgressiveDisclosureOverride` and `ClassResilienceWeightOverride` to the appropriate app's `models.py` (confirm location — likely `core/models/overrides.py` or similar).

### 5.4 Create migration

```bash
python manage.py makemigrations core --name instructor_overrides
# Inspect generated file
python manage.py migrate core
python manage.py check
```

### 5.5 Create serializers and views

New serializers in `core/serializers/overrides.py`. New views in `core/views/overrides.py`. Register routes.

### 5.6 Modify existing write serializers

Update every decision-model write serializer to use the `get_effective_unlock_round` helper. Use the field path naming convention from §3.1.

### 5.7 Add class-level weight validator

Per §3.3. Wire into both serializer validate() and post_save signal.

### 5.8 Test

- Create a test class with an override for `sourcing.payment_terms` set to round 2 (default is round 4 per CC-2 §8).
- Submit a sourcing decision at round 2 with payment_terms set. Expect 201 created (override permits).
- Submit same decision at round 2 in a class without overrides. Expect 400 (default locks until round 4).
- Create a resilience weight override that breaks the sum-to-1.0 constraint. Expect 400 validation error.
- Create overrides that preserve the constraint. Expect 201 created.

### 5.9 Commit sequence

```bash
git add backend/core/models/overrides.py
git commit -m "CC-4 Amendment A1: ClassProgressiveDisclosureOverride and ClassResilienceWeightOverride models"

git add backend/core/migrations/0049_instructor_overrides.py
git commit -m "CC-4 Amendment A1: migration for instructor override tables"

git add backend/core/utils/disclosure.py
git commit -m "CC-4 Amendment A1: get_effective_unlock_round helper"

git add backend/core/serializers/sourcing.py backend/core/serializers/logistics.py backend/core/serializers/trade_finance.py backend/core/serializers/inventory.py backend/core/serializers/extend_esg.py backend/core/serializers/extend_plant.py
git commit -m "CC-4 Amendment A1: write serializers consult override table for effective unlock round"

git add backend/core/serializers/overrides.py backend/core/views/overrides.py backend/core/urls.py
git commit -m "CC-4 Amendment A1: serializers, views, and routes for override endpoints"

git add backend/core/validators.py  # or wherever the class-level validator lives
git commit -m "CC-4 Amendment A1: class-level weight sum-to-1.0 validator"

git checkout main
git merge --no-ff cc-04-amendment-a1 -m "Merge CC-4 Amendment A1: instructor override models"
```

---

## 6. Acceptance Criteria

1. `ClassProgressiveDisclosureOverride` and `ClassResilienceWeightOverride` models exist with the schemas in §3.1 and §3.2.
2. Migration `0049_instructor_overrides` (or equivalent number) applied cleanly.
3. `python manage.py check` reports zero issues.
4. Both new endpoints respond correctly: create, list, delete tested via Django test client.
5. Sum-to-1.0 validator on weight overrides correctly rejects constraint violations.
6. `get_effective_unlock_round` helper is used by every decision-model write serializer. Grep confirms no direct hardcoded unlock-round logic remains in any write serializer.
7. Functional test: overriding `sourcing.payment_terms` to round 2 allows submission at round 2 that would fail in a class without override.
8. Branch `cc-04-amendment-a1` merged to main.

**Report back with:** test output for the functional test in criterion 7, migration output, endpoint response samples, and grep confirmation that hardcoded disclosure logic is replaced.

---

## 7. What This Amendment Does NOT Cover

- Instructor panel frontend UI for managing overrides — **CC-16**.
- Engine consultation of resilience weight overrides (in `compute_resilience_score`) — **a build-pipeline CC that implements the engine**.
- Audit log or override history beyond the `created_by` / `created_at` fields — future refinement if pilot experience calls for it.

---

## 8. Forward Impact

Once executed, every decision-model write serializer enforces progressive disclosure based on class-specific configuration rather than hardcoded defaults. The engine's resilience scoring (when implemented) reads overrides the same way. Instructor panel UI (CC-16) becomes the human-facing layer on top of this API surface.
