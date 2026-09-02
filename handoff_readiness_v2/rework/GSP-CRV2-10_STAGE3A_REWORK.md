# GSP-CRV2-10 Stage 3A checkpoint audit — FAIL / REWORK

Audited runtime revision: `9a29672`
Audited checkpoint revision: `ce163bb`

## Binary decision

**FAIL / REWORK. Do not begin Stage 4.**

Timing and unlock enforcement are acceptable. The funding lifecycle and feature/ownership proof are not.

## Blocking defects

### 1. `unfunded_draft` does not control when the cost is charged

`rd_processing.can_fund_platform()` only compares the authored price with current cash. It does not book or prove payment.

Meanwhile `core/engine/costs.py` still adds every current submission's `DecisionPlatformDevelopment.committed_cost` to `rd_expense` or platform capex regardless of whether the resulting platform is `unfunded_draft`. Therefore:

- an unaffordable platform can be charged in the original submission round while being labelled unfunded;
- when cash later becomes available, the draft starts building based on another cash comparison, but the old decision is not a current-round decision and its cost is not booked in that funding round;
- `funded_round` currently records a state transition, not evidence that the authored price was charged exactly once in that round.

This contradicts the Stage 3 rule: the funding round must be the round payment lands and the clock starts.

### 2. The submitted test coverage overstates ownership and cap enforcement

The checkpoint says V2-044 is covered through both writes and an engine helper test, but the focused test files contain no ownership test. `persisted_ownership_violations()` is not directly exercised.

The feature-cap section has only an activation test and a service-unit test. It does not exercise either write surface despite claiming both.

### 3. Activation silently rewrites an over-cap persisted decision

`rd_processing.py` sorts the chosen feature map and slices it with `[:cap]`. A row arriving outside the supported APIs therefore activates with an arbitrary subset while the stored decision still names more features. That silently changes the team's submitted decision and leaves the stored evidence disagreeing with the platform produced from it.

The engine boundary must refuse an over-cap persisted row before competitive mutation, naming the row, submitted count, and cap. Do not truncate it.

## Required rework

1. Make platform funding and accounting one lifecycle:
   - an `unfunded_draft` books no platform expense/capex;
   - the authored cost is booked exactly once in `funded_round`;
   - the development clock starts in that same round;
   - subsequent rounds neither charge it again nor restart the clock;
   - both expense and `capitalize_platform_development` paths obey the rule.
2. Add a multi-round focused test that records cash, R&D expense/capex, status, `funded_round`, start round and remaining rounds before funding, in the funding round, and after it. Derive the expected amount from the authoritative cost service.
3. Add focused API tests proving V2-044 refusal on the per-type and whole-submission surfaces, with no row persisted, plus a stored foreign-platform row refused by the actual Phase-1 boundary before competitive mutation.
4. Add focused API tests proving the feature cap on both write surfaces, with no row persisted.
5. Replace activation truncation with a fail-closed persisted-row precondition. Test that an ORM-inserted over-cap row refuses Phase 1 before platform/result mutation and names the row/count/cap. Keep the within-cap activation control.
6. Correct the checkpoint report and test-count mapping. Leave V2-039, V2-040 and V2-044 implemented-pending-closure; do not close Stage 3.
7. Freeze runtime before evidence, run the directly affected focused set once, update the checkpoint artifacts/checksums, commit, and stop for re-audit.

## Verification budget

- Focused lifecycle, authoritative-cost, decision-limit and product-name tests only.
- One accounting/lifecycle playthrough may be implemented as a focused integration test; no separate large harness is required.
- `makemigrations --check --dry-run`, `git diff --check`, clean tree and checkpoint checksum verification.
- No full suite, browser, determinism, concurrency, load, tournament, or Stage 4 work.

## Acceptance for re-audit

Stage 3A passes only when payment, accounting and clock start are the same exactly-once event; ownership and feature caps are demonstrated on both writes and at the actual engine boundary; an invalid persisted feature set is refused rather than silently truncated; and the checkpoint report matches the tests that exist.
