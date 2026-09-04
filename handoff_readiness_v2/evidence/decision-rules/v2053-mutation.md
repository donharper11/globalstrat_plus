# V2-053 mutation evidence

Each removal restored in isolation in the real source, the focused test re-run,
and the source restored immediately afterwards.

## A — direct R&D spend scoring in `performance.py`

Restored the retired term (`_ratio(rd_spend, rd_spend_target) * 0.40`):

```text
AssertionError: Decimal('0.67000') != Decimal('0.27000')
  : R10: spend must not earn capability credit.
Ran 1 test ... FAILED (failures=1)
```

Real values through the engine's own component: **0.27 corrected, 0.67 with
spend scoring restored.**

## B — the R&D market-alignment component in `coherence.py`

Restored the component and its breakdown entry:

```text
AssertionError: 'rd_market_alignment' unexpectedly found in {...}
Ran 1 test ... FAILED (failures=1)
```

Restored source: `Ran 14 tests ... OK`.

## What the first attempt at these controls proved — and why it is recorded

The first version of both tests **passed under mutation**, which is the outcome
that matters most here.

- The performance test compared an unstaffed team's score with itself.
  Strategic capability is multiplied by staffing adequacy, so with no
  headcount the component is zero whatever else changes: the assertion was
  `0 == 0` and could not detect anything. The fixture now staffs every pool at
  the scenario's own optimum, and a separate sensitivity control asserts the
  score is non-zero and *does* move when a scored action is added — so a future
  change that pins the component cannot make this suite vacuous again.
- The coherence test only scanned source text for `rd_investments`, so a
  restoration that scored R&D by another route would have passed. It now reads
  the stored `RoundResultCoherence` row through `calculate_coherence`.

Removing a term makes tests pass more easily. Mutation is the only thing that
distinguishes "the term is gone" from "the test stopped looking".
