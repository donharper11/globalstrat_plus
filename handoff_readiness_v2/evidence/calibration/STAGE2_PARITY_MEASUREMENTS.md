# GSP-CRV2-11 Stage 2 — competent-field and archetype-parity measurement

## Result: competent field established; archetype parity not certified

The product-level allocation ruling is implemented at `0644cf5`, with the
cent-accurate product-capacity correction at `836cf2e`. The three disposable
PostgreSQL replays below were regenerated at `836cf2e`; each exports the new
product-demand ledger. No scenario, starter profile, market, Bass parameter,
AI fit, price, or production-policy dial was changed.

The implementation follows the useful part of BECSR's current demand path:
calculate a product/program's own pull, normalise the eligible product pool
into shares, and apply supply at product grain. GlobalStrat keeps its existing
shared Bass pool and CRV2-11 AI accounting rule.

## Product-level rule verification

For every eligible product × customer segment × market, the runtime now stores
fit, adjusted fit, readiness, attractiveness, share, unconstrained demand,
available production, sales, and lost demand in
`round_result_product_demand`. Firm-level adoption remains the exact aggregate
used by existing financial, performance, and cumulative-Bass consumers.

The focused contract creates three products for one firm: two have positive
demand, one is stock-constrained, and one has zero calculated demand. It
proves both positive-demand products receive shares, a stockout affects only
its own sales, the zero-demand product is distinguishable from a stockout,
product results sum exactly to the firm result, the human/AI/unserved pool
reconciles, and reversing product insertion order changes no result. Focused
calibration and compliance tests pass (25 tests).

All three replay artifacts also pass these ledger checks:

- `human + AI + unserved = Bass pool` to cents for every segment-market row;
- `sales + lost demand = unconstrained demand` to cents for every product row;
- summed product sales never exceed that product-market's production.

## All-NA control: competent, but not archetype-parity safe

The fixed constant policy is now economically competent: all four profiles
make a profit in round 1, only 398.63 of 167,000 units (0.24%) are unsold, and
rounds 2–5 sell all production. The 10% per-product historical-sales policy
also remains capacity-adequate: all products sell their allocated production
in rounds 2–3 and every profile is profitable.

The materiality threshold remains 1% of the scenario's 55-point starting
index: **0.55 points**. The repaired all-NA control exceeds it immediately,
so it cannot certify starter-archetype parity:

| round | index range | spread | threshold | total profit range |
|---:|---:|---:|---:|---:|
| 1 | 58.31–59.33 | 1.02 | 0.55 | $118,461.50–$2,016,096.80 |
| 2 | 61.79–63.73 | 1.94 | 0.55 | $570,248.86–$2,479,626.72 |
| 3 | 65.26–68.13 | 2.87 | 0.55 | $480,438.50–$2,256,636.00 |
| 10 | 81.22–98.24 | 17.02 | 0.55 | $480,438.50–$2,376,636.00 |

The responsive probe has the same conclusion: its round 1–3 spreads are
**1.02, 1.85, and 2.63** points, even though it is capacity-adequate and each
profile earns positive net income.

## Regional-start variant: reject as a parity configuration

The unchanged `NA, APAC, EU, LATAM` assignment remains less parity-safe than
the all-NA control: its repaired-revision spreads are **3.77, 8.52, and
10.61** in rounds 1–3. It is evidence against silently diversifying starter
regions as a remedy.

## Evidence files

- `stage2_archetype_parity_replay.json` — ten-round all-NA constant-policy
  control: 304 product-demand rows and 76 product-market rows.
- `stage2_regional_parity_replay.json` — three-round regional variant with the
  same product-level ledger.
- `stage2_competent_parity_replay.json` — three-round all-NA responsive probe:
  96 product-demand rows and no product capacity overrun.

## Required disposition

The product-level demand-allocation runtime repair and competent-field evidence
are complete. **Archetype parity remains an open calibration gate.** A separate
rules-owner-approved profile or scoring calibration is required before changing
any dial; it must then be replayed against the same threshold. Do not use the
regional-start configuration as that remedy.
