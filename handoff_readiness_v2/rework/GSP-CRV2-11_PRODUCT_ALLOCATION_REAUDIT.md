# GSP-CRV2-11 product-level allocation re-audit — conditional pass / provenance rework

Audited revisions: `0644cf5`, `836cf2e`, `86d8241`, and `d3b6b23`.

## Allocation decision

**The runtime allocation repair passes.** It implements the rules-owner ruling
at `handoffs/GSP-CRV2-11-product-level-demand-allocation.md`:

- every eligible product × customer segment × market receives its own fit,
  attractiveness, share, demand, available production, sales, and lost-demand
  ledger row;
- product sales aggregate to the existing firm adoption, product-market
  revenue, financial, and cumulative-Bass paths;
- a sibling product cannot consume or receive another product's capacity;
- the legacy `best_product` is presentation/compatibility only in the new
  allocation path; and
- the focused contract covers positive multi-product demand, product-local
  stockout, zero-demand distinction, firm/pool reconciliation, and order
  invariance.

Independent verification on the submitted three replay artifacts found zero
violations of all of these cent-precision identities:

```
product sales + product lost demand = product unconstrained demand
product sales <= product available production
sum(product sales) = firm human adoption
human + AI + unserved = Bass pool
```

A fresh, disposable, three-round all-NA responsive replay from `d3b6b23`
produced 96 product-demand rows and the same substantive results as the
submitted competent-field artifact: no capacity overrun or accounting mismatch,
all round-one profiles profitable (`$118,461.50` to `$2,016,096.80`), and
`398.63` units unsold in round one.

The competent-field claim is therefore accepted. The later-round all-NA
performance-index spread (`1.02` in round one) is retained as a measurement,
not a parity failure: the owner has clarified that only round-zero index and
rank equality are required. Bootstrap already provides that equality. No
profile, pricing, production, market, AI, or scoring dial is to be changed to
erase later-round variation.

## Remaining release rework: provenance and lifecycle coverage

**CRV2-11 is not yet certification-ready.** `RoundResultProductDemand` is now
authoritative competitive result state, but the repository does not yet treat
it that way outside the resolver.

1. Add it to `RESULT_SECTIONS` in
   `backend/core/services/manifest_sections.py`, with its complete natural key
   and an explanation that it is the product-grain demand allocation ledger.
   It must be in both the input/replay snapshot and the output competitive
   result manifest.
2. Bump `MANIFEST_SCHEMA_VERSION` from 4 to 5, retain the v4 inventory as the
   historical definition, generate `manifest_schema_v5.json`, and add a test
   that a product-demand row is represented in a round manifest and changes its
   digest. Merely regenerating v4 is not acceptable: it would redefine old v4
   receipts.
3. Add `round_result_product_demand` to the explicit result-table cleanup
   lists in both `load_scenario --flush` and `load_demo --flush`. Otherwise a
   scenario/demo refresh can leave product-demand rows behind or hit their
   `PROTECT` foreign keys when deleting products.
4. Run the manifest determinism suite, the focused allocation/compliance suite,
   a migration check, and a clean scenario/demo lifecycle probe. Regenerate the
   Stage 2 evidence only if the manifest/lifecycle repair changes resolved
   result bytes; otherwise preserve the already accepted runtime measurements.

This is deliberately not a request to retune calibration. It is the minimum
provenance closure required for an instructor or dispute replay to establish
how a product result was derived and for the signed result to cover the ledger
that determined it.

## Re-audit closure — accepted at `a521f7a`

The provenance/lifecycle rework is **accepted**.

- `RoundResultProductDemand` is now an input and output manifest section with
  its complete six-part natural key.
- Manifest schema version 5 is a new, separately pinned definition; the
  version-4 file and its recorded checksum remain intact. Independent checksum
  verification matched both the checked-in files and their provenance record.
- The manifest contract explicitly creates a product-demand row, mutates its
  sold quantity, and proves the competitive envelope digest changes.
- Scenario and demo cleanup remove product-demand rows before `TeamProduct`.
  Their best-effort SQL operations are isolated so a missing legacy table
  cannot abort subsequent cleanup.
- Migration and inventory checks were clean; the submitted manifest and
  allocation/compliance suites were re-run against isolated test databases.

No allocation, profile, price, production, market, AI, or scoring dial changed
in this closure. The product-allocation implementation, its competent-field
evidence, and the round-zero parity requirement are accepted. This re-audit
does not close CRV2-11's separate field-size, sensitivity, or Fix-B work.
