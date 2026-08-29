# GSP-CRV2-06 completion rework

## Decision

**FAIL / REWORK.** CRV2-06 does not meet its acceptance criteria at revision
`7aa182845db4053496e52adddfe93d4082a762b6`.

## Blocking reasons

### 1. The named competent baseline is not competent under the adopted rule

The harness declares a $2,000,000 R&D budget but writes only $100,000 of actual
`DecisionRDInvestment.amount`. V2-021 deliberately made declared budget inert
and scores actual spend against the $2,000,000 scenario target. The submitted
report therefore compares every strategy with a baseline that earns only 5% of
available R&D capability credit. `rd-actual-target` wins all 9 holdout cells by
about +4.3.

The acceptance criterion requires the strongest legal strategy and its margin
over **competent** play. Calling this a limitation does not discharge that
criterion, and it can change finalist ranking and absolute margins.

### 2. One opponent population is invalid after V2-024

The report states that the incumbent population can no longer be constructed
because its opponent payloads violate the adopted equity funding-need rule.
A three-population tournament cannot pass when one population is illegal under
the final rules.

### 3. The completion report is materially incomplete/inaccurate

- V2-018, the P0 negative-cost income loop found and closed in CRV2-06 Stage 1,
  is omitted from the outcome and finding count.
- V2-020 is reported as P1 although the registered finding is P0: an ordinary
  legal equity decision could crash resolution for the whole round and later
  teams could receive another team's equity value.
- The requested row-by-row disposition for the explicit exploit mechanisms is
  absent. The report must map deadline/resubmit, information timing,
  negative/oversized values, duplicates, rounding/currency, FX/trade
  finance/sourcing/inventory loops, progressive disclosure, early lead, and
  collusion/opponent-independent dominance to current evidence, prior named
  evidence, or an open blocking finding.
- The report header names revision `954b931` while the submitted revision is
  `7aa1828`; runtime freeze, evidence revision, and report-only revision must be
  labeled unambiguously.

### 4. V2-024's actual eligible-use rule is described as a limitation

The implementation excludes outcome-dependent costs. Record the final rule
explicitly: eligible uses are deterministic decision-controlled outlays known
before resolution plus debt repayment; dividends and outcome-dependent COGS,
tax, interest, tariffs, and revenue-scaled overhead are not eligible uses.
They must be funded from opening capital and operating revenue. This is a rules
definition, not an accepted limitation.

## Required rework

1. Correct the documented competent baseline so actual R&D spend reaches the
   scenario target. Do not merely change `rd_budget`.
2. Repair all three opponent-population builders so every payload is legal
   under V2-024 and every other final validation rule. Add a cheap contract test
   that constructs and validates each baseline/opponent payload.
3. Freeze the corrected harness/runtime.
4. Rerun only the bounded targeted tournament:
   - 15 targeted candidates x 3 populations on one discovery identity;
   - select by worst-case advantage, median tie-break;
   - top 3 x 3 populations x 3 unused identities;
   - matched baselines as separate controls.
5. Preserve the earlier 50-candidate batch as historical discovery evidence;
   do not rerun it and do not combine its old-baseline margins with the corrected
   tournament margins.
6. Report the complete discovery and holdout distributions under the corrected
   baseline. Stop again for any risk-free loop or opponent-independent dominant
   strategy.
7. Correct the completion report issues above, regenerate `SHA256SUMS`, verify
   the complete inventory, and submit from a clean revision.

## Verification budget

Do not rerun Stage 1, Stage 2, the 50-candidate random batch, full backend suite,
determinism/concurrency matrices, narrative drills, or unrelated fixtures. The
expected expensive work is one bounded tournament, previously measured at about
26 minutes, plus focused payload-contract tests and reporting.
