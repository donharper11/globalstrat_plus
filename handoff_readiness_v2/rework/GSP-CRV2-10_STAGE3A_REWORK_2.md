# GSP-CRV2-10 Stage 3A re-audit — FAIL / FOCUSED PROOF REWORK 2

Audited runtime revision: `561aa32`
Audited checkpoint revision: `4cbafa1`

## Binary decision

**FAIL / REWORK. Do not begin Stage 4.**

The ownership and feature-cap repairs now pass audit. The remaining blocker is that the accounting test does not prove the report's central funding claim, plus the transcript was not generated from a clean tree.

## Blocking reasons

### 1. The exactly-once test asks a reimplementation, not the accounting path

`FundingAccountingTests.charge_for()` queries `TeamPlatform.funded_round` and re-prices the platform itself. `test_cost_is_booked_exactly_once_in_the_funding_round()` sums that helper. It never calls `calculate_operating_expenses`, never inspects `context.opex`, never reads a financial row, and never observes cash.

That proves that `funded_round` selects one round. It does not prove that the engine booked the cost in that round exactly once—the defect the first implementation had.

### 2. Expense mode is not asserted

`test_the_expense_mode_does_not_capitalise()` asserts only that `capitalized_cost` did not change. A branch that booked nothing anywhere would pass. The report claims both modes are proved, but the test does not assert the expense-mode `rd_expense` or cash effect.

The checkpoint also says the multi-round test records cash, but `snapshot()` has no cash field.

### 3. Evidence provenance says the tree was dirty

The transcript header records:

`tree: 1 modified files (0 = clean)`

This contradicts the report's clean-freeze evidence claim. Even if the modified path was the transcript being written, the artifact does not identify it, so the reader cannot establish that runtime source was clean.

## Required rework

1. Make the existing real-cost-path helper expose the actual values produced by `calculate_operating_expenses`, including at minimum `rd_expense` and `platform_capex` for the subject team.
2. Replace the derived `charge_for()` proof with assertions against the real accounting path across the lifecycle:
   - request round while unfunded: expense 0 and capex 0;
   - funding round in expense mode: `rd_expense == authored`, capex 0;
   - later rounds: expense 0 and capex 0;
   - total actual booked amount across the lifecycle equals the authored cost exactly once.
3. Keep the capitalisation test, but assert the real path reports capex equal to the authored cost in the funding round, expense 0, and both 0 later. Retain the asset-balance assertion as a second check.
4. Either add a focused financial/cash assertion through the smallest real Phase-1 fixture, or correct the report so it does not claim cash was recorded. Do not label a `funded_round`/price lookup as a cash observation.
5. Generate the focused transcript from a demonstrably clean runtime tree. Write output to a temporary path outside the repository, then move it into the evidence directory after the command finishes, or record the exact modified path and a clean runtime-source digest. The simplest option is the temporary path.
6. Run the affected focused set once, update the checkpoint report/transcript/checksum, commit, and stop for re-audit. Runtime code need not change unless the real accounting assertions expose a defect.

## Verification budget

- Add/adjust only the focused funding-accounting tests and checkpoint artifacts.
- Re-run the same affected set once; it previously took about six seconds.
- `makemigrations --check --dry-run`, `git diff --check`, clean tree, checksum verification.
- No full suite, browser, determinism, concurrency, load, tournament, or Stage 4 work.

## Acceptance for re-audit

Stage 3A passes when the actual expense and capitalization outputs—not a parallel selector—show the authored cost booked once in the funding round and nowhere else, the report states only what was observed, and the transcript establishes clean runtime provenance.
