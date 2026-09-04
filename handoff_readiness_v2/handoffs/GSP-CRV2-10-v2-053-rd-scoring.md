# GSP-CRV2-10 V2-053 — retire direct R&D-spend scoring

**Owner:** CRV2-10 builder  
**Rules decision:** R10, `GSP-CRV2-10_RULE_DECISIONS.md`  
**Finding:** V2-053, `V2_FINDINGS_REGISTER.md`  
**Status:** authorised for implementation; not yet audit-accepted

## Objective

After R9 retired feature upgrades, a legacy `DecisionRDInvestment` still
consumes money and directly earns strategic-capability and R&D-market-alignment
credit despite changing no product. Retire that decision for future play and
remove its direct scoring path. Spending remains financial; delivered platform
capabilities and their market outcomes remain competitive.

## Required implementation

1. Refuse a new `DecisionRDInvestment` on every supported decision write
   surface with an actionable message: feature upgrades are retired; develop a
   new platform and re-base the product instead.
2. Add or retain a fail-closed engine precondition that refuses any unprocessed
   persisted legacy row before competitive mutation. Do not silently discard it
   and do not charge it.
3. Remove direct use of `DecisionRDInvestment.amount` from
   `engine/performance.py` strategic-capability scoring. Do **not** replace it
   with `DecisionPlatformDevelopment.committed_cost` or any other spend amount.
4. Remove `DecisionRDInvestment` feature/segment scoring from
   `engine/coherence.py`. Do not manufacture an equivalent score from a cost
   field.
5. Preserve historical rounds, decisions, results, and hashes. The new refusal
   applies only to future writes and unprocessed rows.
6. Preserve platform-development's normal cash, budget, expense/capitalisation,
   and later product/market/financial effects. Do not broaden this change into
   a recalibration of those mechanics.

## Proof required

- A new decision is refused by each supported write surface, naming the
  platform-development/re-base route.
- A deliberately planted persisted legacy row causes the engine to refuse
  before any competitive mutation or charge.
- The old mutation proves the fix: restoring direct R&D amount scoring changes
  the targeted strategic-capability/coherence result; the corrected behavior
  does not.
- Platform development remains accepted, affordable only within its existing
  budget/cash rules, and produces its existing real downstream effects.
- Historical-result fixtures remain unchanged.
- Run the focused Stage 3A, 3B, and 4 verification set plus migrations,
  manifest-schema, and read-inventory checks from a clean committed revision.

## Non-goals

- Do not score platform-development cost directly.
- Do not restore feature upgrades, licensing, time lags, or
  `PendingFeatureGain`.
- Do not tune `rd_spend_target`, platform costs, or performance weights in this
  change; that is a future calibration task only if the owner explicitly opens
  it.
- Do not alter published rounds or use a data rewrite to hide legacy rows.

## Re-audit gate

Submit one narrowly scoped implementation commit, a clean-tree verification
transcript, mutation evidence, and the precise test inventory. V2-053 is not
closed until independent re-audit accepts both the refusal boundary and the
absence of direct spend scoring.
