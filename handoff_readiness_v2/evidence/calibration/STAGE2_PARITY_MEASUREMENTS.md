# GSP-CRV2-11 Stage 2 — competent-field measurement and round-zero parity record

## Result: competent field established; round-zero parity is the only parity gate

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

## All-NA control: competent field; later-round index variation recorded, not gated

The fixed constant policy is now economically competent: all four profiles
make a profit in round 1, only 398.63 of 167,000 units (0.24%) are unsold, and
rounds 2–5 sell all production. The 10% per-product historical-sales policy
also remains capacity-adequate: all products sell their allocated production
in rounds 2–3 and every profile is profitable.

The earlier 1% / **0.55-point** threshold was an exploratory measurement, not
an adopted rule. The competition owner has clarified the governing rule:
**only round zero requires identical Performance Index and shared rank.**
Different starter positions are deliberate and their interaction with markets
and subsequent decisions may produce different indexes from round one onward.

The all-NA results below are therefore retained as outcome characterisation,
not as a starter-archetype-parity failure:

| round | index range | recorded spread | total profit range |
|---:|---:|---:|---:|
| 1 | 58.31–59.33 | 1.02 | $118,461.50–$2,016,096.80 |
| 2 | 61.79–63.73 | 1.94 | $570,248.86–$2,479,626.72 |
| 3 | 65.26–68.13 | 2.87 | $480,438.50–$2,256,636.00 |
| 10 | 81.22–98.24 | 17.02 | $480,438.50–$2,376,636.00 |

The responsive probe likewise records round 1–3 spreads of **1.02, 1.85, and
2.63** points, even though it is capacity-adequate and each profile earns
positive net income. Those values are not an acceptance threshold.

## Regional-start variant: outcome characterisation, not a parity configuration

The unchanged `NA, APAC, EU, LATAM` assignment produces repaired-revision
spreads of **3.77, 8.52, and 10.61** in rounds 1–3. It is evidence about the
consequences of that market assignment, not a reason to alter the intentional
round-zero equality rule or to treat regional diversification as a parity fix.

## Evidence files

- `stage2_archetype_parity_replay.json` — ten-round all-NA constant-policy
  control: 304 product-demand rows and 76 product-market rows.
- `stage2_regional_parity_replay.json` — three-round regional variant with the
  same product-level ledger.
- `stage2_competent_parity_replay.json` — three-round all-NA responsive probe:
  96 product-demand rows and no product capacity overrun.

## Disposition

The product-level demand-allocation runtime repair and competent-field evidence
are complete. Round-zero bootstrap already writes the scenario base index and
shared rank for every team; this is the complete starter-parity requirement.
No profile or scoring retune is authorised or required to erase later-round
Performance Index variation.

This record does not close CRV2-11's separate field-size, sensitivity, or
AI-adoption (Fix-B) work.
