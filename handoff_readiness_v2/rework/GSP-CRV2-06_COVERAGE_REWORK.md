# GSP-CRV2-06 explicit-mechanism coverage rework

## Decision

**FAIL / REWORK.** Revision
`c914da24634871388d9ff9b21e4603d0e51dcf4a` explicitly leaves required
acceptance mechanisms uncovered.

The accepted tournament itself is retained. Its baseline gates, payload
contract, discovery, selection and holdout do not need to be repeated.

## Blocking gaps

1. Progressive disclosure is recorded as “not exercised”.
2. Dedicated FX, trade-finance and inventory value loops are recorded as only
   partially covered; those decision families were not in the 44-dimension
   screen.
3. “No tournament candidate exceeded competent play” does not exercise an
   early-unassailable-lead mechanism. No candidate first established a legal
   lead and then tested whether it remained mechanically locked without
   continued superior play.

The handoff specification requires each distinct exploit mechanism to be
exercised once. An open coverage gap is not a passing disposition.

## Required focused probes

### Progressive disclosure

Use one real student/API walkthrough against a field or report whose authored
unlock round is later than the current round:

- before unlock, request it through every supported student read surface that
  can expose it and prove the protected value is absent—not merely hidden by
  the UI;
- attempt the direct-object/direct-endpoint form as well as the normal list or
  page form;
- after advancing to the authored unlock condition, prove the same student can
  read it;
- prove another game/section's disclosure state cannot unlock it.

Reuse route/read inventories where they establish surface coverage. Do not
repeat CRV2-04's general read evidence.

### FX, trade finance, sourcing and inventory value conservation

First inventory only the legal fields and engine cash/value effects for these
four decision families. Then run one small multi-round counterfactual per
distinct mechanism, with an unchanged baseline control:

- **FX:** no underlying exposure plus the largest legal hedge, and any legal
  inverse/opposite construction. It must not create positive cash or income
  from nothing or pay both sides of one exposure.
- **Trade finance:** change/cycle the legal instrument while holding the trade
  constant. Fees, coverage and settlement must not duplicate proceeds or turn
  a cost into income.
- **Sourcing:** vary supplier allocation/commitment while production and sales
  are held at zero. The decision must not create inventory, revenue, or negative
  expense.
- **Inventory:** build/carry/release inventory across rounds with sales held at
  zero. Closing cash plus inventory value must not increase absent an external
  inflow, and the same stock must not be monetised twice.

Each mutation must prove it reached the intended persisted/scoring row.
Compare complete cash/value ledgers, not only final index. A repeatable positive
value loop stops the handoff as a new finding.

### Early-lead lock-in

Run one bounded multi-round playthrough that deliberately front-loads the
strongest legal investment strategy to establish an early lead, then returns
the subject to baseline/no-superior play while competent opponents continue.
Record the per-round index, rank, cash and margin. The probe passes only if the
lead can erode or reverse when the subject stops outperforming, or if a retained
lead is fully explained by persistent purchased state rather than a mechanical
ranking lock/floor. If the leaderboard becomes mathematically unreachable
regardless of later opponent performance, register and stop on a finding.

## Completion

- Add machine-readable artifacts and concise results to the existing evidence
  inventory.
- Replace each open-gap row with its measured disposition or a new open finding.
- Do not describe bounded search volume, a degenerate incumbent, or varied RNG
  influence as accepted limitations; state them as scope/residual risk.
- Regenerate and verify `SHA256SUMS`, label revisions unambiguously, and submit
  from a clean tree.

## Verification budget

No tournament rerun, random batch, Stage 1/2 rerun, full backend suite,
determinism/concurrency matrix, narrative drill or unrelated fixture. Use only
the focused authorization walkthrough, value-conservation probes, early-lead
playthrough, directly affected tests, static checks and checksum verification.
