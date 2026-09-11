# CRV2-13 known-list disposition — D1, D3, D4, D5

**Base revision:** `a521f7a`  
**Status:** focused repair and verification complete in the current working tree;
the broader CRV2-13 sweep remains open.

| Item | Disposition | Focused proof |
|---|---|---|
| D1 | Fixed. Both immediate and end-of-round product retirement now deactivate every `TeamProductMarket` row. | New `core.tests.test_product_retirement.ProductRetirementTests` creates an end-of-round retirement and proves the product and offered-market state are both retired/inactive. |
| D3 | Already fixed. The allocator and write boundary exclude only non-retired platforms, so a retired generation can be rebuilt. | `core.tests.test_platform_lifecycle.DuplicateGenerationTests.test_a_retired_generation_may_be_requested_again` drives a retired platform plus a new decision through the allocator and verifies `Rebuilt` enters development. |
| D4 | Fixed. The organisational speed lookup no longer swallows all failures. Missing organisation state still has its normal no-modifier result; a persistence/query failure now aborts processing instead of silently changing the rule. | `PlatformTimingTests.test_active_org_structure_applies_its_development_speed_modifier` and `test_org_structure_lookup_errors_are_not_silently_ignored`. |
| D5 | Fixed. `preference_engine.calculate_fit_scores` now names the `context.segments` key `segment_id`, matching the dictionary contract. This is a naming-only correction; the value was not read. | Reviewed against `core.engine.utils` segment-state construction; existing preference behavior is unchanged. |

Verification used the disposable PostgreSQL runner and did not require a
production database secret:

```text
backend/scripts/test-postgres core.tests.test_product_retirement \
  core.tests.test_platform_lifecycle.PlatformTimingTests \
  core.tests.test_platform_lifecycle.DuplicateGenerationTests \
  core.tests.test_platform_lifecycle.HeldGenerationTests \
  core.tests.test_calibration.ScenarioPreferenceValidationTests.test_all_shipped_scenarios_pass_the_preference_contract

Ran 26 tests in 1.954s — OK
```

The expected `Bad Request` log entries are assertions from negative API tests
in the duplicate-generation suites, not test errors.
