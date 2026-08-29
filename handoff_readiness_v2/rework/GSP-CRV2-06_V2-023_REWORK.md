# GSP-CRV2-06 — V2-023 rework

## Decision

**FAIL / REWORK.** V2-023 is not closed.

## Blocking defect

The repair removes roster-dependent price scoring, but the adopted bounded
feature reaches `price_fit == 0` and then clamps. `retail_price` has no upper
bound beyond its decimal field and API positivity check. Once the score is at
the floor, increasing price further cannot reduce demand through this path,
while revenue continues to multiply by price.

The submitted evidence already exposes the residual: at production 20,000,
raising price from $420 to $2,000 reduces units only about 20% but increases
revenue from $887,174.40 to $3,373,840 and improves net income by about $2.4m.
Calling that only a later balance question is insufficient because the current
formula has a hard response floor and no legal price ceiling. The original
unbounded price-scaling mechanism therefore remains above the clamp point.

## Required correction

Add an absolute high-price demand response that does not become constant at
the bounded preference-feature floor. Use a scenario-authored elasticity for
prices above the reference, applied to demand/adoption after preference fit:

```text
high_price_multiplier = (retail_price / reference_price) ** (-elasticity)
```

Apply it when `retail_price > reference_price`, with a positive configured
elasticity **strictly greater than 1** so revenue cannot grow without bound as
price rises. Seed and document the current scenario value; include it in the
existing scenario configuration/manifest digest. Missing, non-finite, or
`<= 1` values must fail before competitive mutation.

Keep the absolute reference-price repair. Do not restore cohort-relative
pricing and do not impose an undocumented price cap as a substitute.

## Focused acceptance evidence

Use the same-game counterfactual harness and fixed production. Test prices at:

- the reference price;
- the existing $2,000 point;
- at least two higher legal prices spanning an order of magnitude.

Prove:

1. demand/units continue to fall above the price-fit clamp point;
2. revenue and net income do not increase without bound at higher prices;
3. isolated and shared-positioning teams receive the same absolute price
   treatment;
4. adding, removing, or repricing another team changes nothing for the subject;
5. invalid elasticity configuration fails before competitive writes;
6. the reference price and elasticity are present in the deterministic input
   envelope;
7. ordinary reference-price behavior remains intact.

Re-run only the focused V2-023 gate, the affected price/volume grid, and direct
tests of the demand multiplier/configuration precondition. Do not rerun the
107-probe screen, full backend suite, determinism matrix, concurrency matrix,
or unrelated fixtures.

V2-023 may close only when the high-price tail is bounded by measurement, not
merely when $50/$420/$2,000 produce different unit counts. Stage 3 search stays
stopped until then.
