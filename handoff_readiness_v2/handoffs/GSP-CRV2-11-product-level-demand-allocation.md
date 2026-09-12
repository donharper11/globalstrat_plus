# GSP-CRV2-11 — product-level demand allocation ruling

**Decision date:** 2026-09-05  
**Owner:** competition rules owner  
**Reason:** Stage 2 exposed that the engine collapses all of a firm's products
to one `best_product` before market share and capacity are calculated.

## Rule in force

Demand is evaluated and allocated for every eligible **product × customer
segment × market** combination. A firm is not represented by one winning
product before demand is allocated.

For each customer segment and market in a round:

1. Calculate the Bass adoption pool.
2. For every eligible marketed human product, calculate that product's own
   attractiveness from its platform/features, price, marketing mix, readiness,
   and applicable strategy/support effects. Include AI competitors in the same
   competitive denominator under their existing rule.
3. Calculate each product's share of the segment from its attractiveness.
4. Calculate that product's unconstrained demand as its share × the Bass pool.
5. Cap that product's sales at its own available production. The difference is
   lost/unserved demand; it is **not** reassigned to a sibling product merely
   because that sibling has stock.
6. Aggregate product sales to the firm for existing firm-level results,
   financials, and the human contribution to Bass cumulative adoption.

Thus, a product with zero sales must be explainable by zero calculated demand
or its own capacity/result state. It may not receive zero merely because a
different product owned by the same firm was selected first.

## Consequences for the repair

- Retire the single firm-level `best_product` as the demand-allocation unit.
  It may remain only as a presentation summary if it cannot affect allocation,
  capacity, financials, or cumulative adoption.
- Preserve product-level evidence of calculated fit/attractiveness, share,
  unconstrained demand, sales, capacity constraint, and lost demand so an
  instructor can answer how a product's result was derived.
- Preserve the AI accounting rule already adopted in CRV2-11: human + AI +
  unserved must reconcile to the Bass pool; AI does not enter human cumulative
  adoption unless a separate Fix-B decision changes that rule.
- The deterministic equal-fit order at `cb7e6f9` remains a useful deterministic
  presentation/compatibility rule, but cannot stand in for product-level demand
  allocation.

## Verification and remeasurement

The runtime owner must add focused tests proving:

- two eligible products of one firm can both receive calculated demand and
  product-level shares;
- a product's own capacity caps only that product's sales and records its lost
  demand;
- product-level allocations aggregate exactly to the existing firm-level result
  and the full human + AI + unserved pool reconciliation;
- reversing product insertion/order cannot change results; and
- a product with no calculated demand is distinguishable from a product with
  positive demand that was stock-constrained.

After repair, regenerate all three CRV2-11 Stage 2 replays and reassess the
competent-field conclusion. Confirm separately that round-zero bootstrap still
gives every team the scenario base index and shared rank. Do not retune
scenario or profile dials in the same change.
