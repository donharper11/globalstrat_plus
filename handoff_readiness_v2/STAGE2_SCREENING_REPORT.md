# GSP-CRV2-06 Stage 2 — complete result

**Screen revision:** `e3654ece7b4dcb3cf58633b590bbd3529d252b1d` (retained; see the RNG gate)  
**Characterisation revision:** `cdc700321c5f74d176b7683d643fd0bfb2c2572e`  
**Evidence:** `handoff_readiness_v2/evidence/adversarial-balance/`

## What was reused, and why

The 107-probe screen supplies the minimum / baseline / maximum point for
every dimension and was **not rerun**. Source changed under it when V2-010
and V2-011 were repaired, so the RNG-impact gate resolved the same baseline
and six representative probes under the repaired RNG:

| Gate check | Result |
|---|---|
| Recorded screen revision | `e3654ece7b4dcb3cf58633b590bbd3529d252b1d` |
| Baseline unchanged | True |
| Probe deltas unchanged | 6/6 |
| Screen remains applicable | True |

Narrow claim, stated as such: this shows *this fixture's* outputs did not
move, not that the RNG repair is inconsequential in general. The fixture is a
round-1 game where the supply-chain and compliance subsystems have little to
fire.

## Categorical dimensions — derived, not rerun

| Dimension | Categories evaluated | Verdict from the screen |
|---|---|---|
| `market-entry.action` | enter, change_mode, exit | escalate |
| `market-entry.integration_strategy` | FULL, BRAND_PRESERVE, DUAL_BRAND | flat in screening |
| `marketing.distribution_strategy` | mass_retail, selective_retail, exclusive_retail, direct_online, hybrid | flat in screening |
| `partnerships.action` | establish, modify, terminate | flat in screening |
| `plants.action` | build, expand, contract_mfg | escalate |
| `platforms.method` | in_house, license, partnership | flat in screening |
| `product-retires.timing` | immediate, end_of_round | flat in screening |
| `products.positioning` | budget, mainstream, premium, ultra_premium | flat in screening |
| `rd.method` | in_house, license | flat in screening |
| `talent.commercial_salary_level` | 1, 2, 3, 4, 5 | escalate |
| `talent.operations_salary_level` | 1, 2, 3, 4, 5 | flat in screening |
| `talent.rd_salary_level` | 1, 2, 3, 4, 5 | escalate |

## Formula families — one representative each

Grouped on code evidence, not resemblance.

**esg investment** — representative `esg.environmental_investment`  
members: `esg.environmental_investment`, `esg.social_investment`  
evidence: core/engine/costs.py: `strategy_expense += esg.environmental_investment + esg.social_investment` — one line, both fields, same coefficient.

**talent headcount** — representative `talent.rd_headcount`  
members: `talent.rd_headcount`, `talent.commercial_headcount`, `talent.operations_headcount`  
evidence: core/engine/costs.py: `for prefix in ['rd','commercial','operations']` then `hc = getattr(talent_decision, f'{prefix}_headcount')` and `pool_salary = hc * salary_base[sl]` — one expression, three pool names.

**talent salary level** — representative `talent.rd_salary_level`  
members: `talent.rd_salary_level`, `talent.commercial_salary_level`, `talent.operations_salary_level`  
evidence: core/engine/costs.py indexes one shared salary_base table with `f'{prefix}_salary_level'`.

**talent training budget** — representative `talent.rd_training_budget`  
members: `talent.rd_training_budget`, `talent.commercial_training_budget`, `talent.operations_training_budget`  
evidence: core/engine/costs.py and core/engine/talent.py read `f'{prefix}_training_budget'` inside the same pool loop.

That collapses 11 dimensions to 4 measurements. Sweeping all of them would
have measured the loop rather than the model.

## Interior points — two per monotonic representative

| Dimension | Value | Net income Δ | Revenue Δ | Index Δ |
|---|---:|---:|---:|---:|
| `esg.environmental_investment` | 500000 | -483257.62 | 16813.44 | 0.01 |
| `esg.environmental_investment` | 1000000 | -980407.00 | 19676.16 | -0.01 |
| `market-entry.initial_investment` | 250000 | -150000.00 | 0.00 | 0.00 |
| `market-entry.initial_investment` | 750000 | -650000.00 | 0.00 | -0.02 |
| `marketing.promotion_budget` | 150000 | 247885.45 | -2123.52 | 0.01 |
| `marketing.promotion_budget` | 600000 | -197882.11 | 2126.88 | 0.00 |
| `platforms.committed_cost` | 250000 | -150000.00 | 0.00 | 0.00 |
| `platforms.committed_cost` | 750000 | -650000.00 | 0.00 | -0.02 |
| `talent.rd_headcount` | 25 | 250000.00 | 0.00 | 0.01 |
| `talent.rd_headcount` | 75 | -1000000.00 | 0.00 | -0.03 |
| `talent.rd_training_budget` | 250000 | -250000.00 | 0.00 | 0.00 |
| `talent.rd_training_budget` | 750000 | -750000.00 | 0.00 | -0.02 |

Every one is monotonic in cost, with **no material discontinuity or reversal**
against the recorded thresholds — which is what an ordinary accounting cost
should look like.

Not "flat in revenue", which an earlier draft of this report said and which the
table above contradicts: ESG investment moved revenue by +16,813.44 and
+19,676.16, and promotion budget by −2,123.52 and +2,126.88. Those are real
responses, small relative to a baseline revenue of 887,174.40 — under 2.3% — and
below the material threshold, but they are not zero and the report should not
have said they were.

## Joint mechanisms

### R&D budget x R&D spend

V2-021 moved the capability denominator from the declared budget to a scenario constant. The grid shows whether the declared budget still interacts with spend at all, which a curve through either field alone cannot answer.

Applied portfolio-wide: False. Revenue degenerate across the grid: True.

| Cell | Revenue | Net income Δ | Index Δ |
|---|---:|---:|---:|
| rd_budget=1 x amount=0 | 887174.40 | 100000.00 | -0.09 |
| rd_budget=1 x amount=1000000 | 887174.40 | -900000.00 | 0.87 |
| rd_budget=1 x amount=2000000 | 887174.40 | -1900000.00 | 1.84 |
| rd_budget=2000000 x amount=0 | 887174.40 | 100000.00 | -0.09 |
| rd_budget=2000000 x amount=1000000 | 887174.40 | -900000.00 | 0.87 |
| rd_budget=2000000 x amount=2000000 | 887174.40 | -1900000.00 | 1.84 |
| rd_budget=50000000 x amount=0 | 887174.40 | 100000.00 | -0.09 |
| rd_budget=50000000 x amount=1000000 | 887174.40 | -900000.00 | 0.87 |
| rd_budget=50000000 x amount=2000000 | 887174.40 | -1900000.00 | 1.84 |

### retail price x production volume

Revenue is price times units sold, and units sold is bounded by both production and demand. Either field alone traces a curve that depends entirely on where the other one was pinned.

Applied portfolio-wide: True. Revenue degenerate across the grid: False.

| Cell | Revenue | Net income Δ | Index Δ |
|---|---:|---:|---:|
| retail_price=2000 x production_volume=0 | 0.00 | 4936094.97 | -6.54 |
| retail_price=2000 x production_volume=20000 | 4224640.00 | 1782461.63 | 0.07 |
| retail_price=2000 x production_volume=60000 | 4287232.00 | -12705285.35 | -0.09 |
| retail_price=420 x production_volume=0 | 0.00 | 4936094.97 | -6.54 |
| retail_price=420 x production_volume=20000 | 887174.40 | -1454880.00 | -0.05 |
| retail_price=420 x production_volume=60000 | 900318.72 | -15990591.23 | -0.10 |
| retail_price=50 x production_volume=0 | 0.00 | 4936094.97 | -6.54 |
| retail_price=50 x production_volume=20000 | 105616.00 | -2212991.65 | -3.16 |
| retail_price=50 x production_volume=60000 | 107180.80 | -16759935.01 | -3.20 |

**R&D grid.** The declared budget is inert across three orders of magnitude —
identical index delta at each spend level — which is exactly what V2-021's
repair should produce, now measured rather than asserted. Revenue is
degenerate here legitimately: R&D is not a revenue lever within a round.

**Price/volume grid.** Three results: a cliff at volume 0 (index −6.54 at
every price, the V2-022 inactivity cap firing); demand-bound sales above
~2,100 units, so tripling production raises revenue ~1.5%; and units sold
identical across a 40× price range, registered as **V2-023**.

## Every additional evaluation

| Purpose | Evaluations |
|---|---:|
| Baseline, resolved twice to show repeatability | 2 |
| Interior points (6 representatives × 2) | 12 |
| R&D joint grid (3 × 3) | 9 |
| Price/volume joint grid (3 × 3) | 9 |
| **Total** | **32** in 166.9s |

Baseline repeatable: True.

## Remaining uncertainty

1. **V2-023's mechanism is unconfirmed.** The measurement is solid; the
   explanation — that relative price scoring leaves a team alone at its
   positioning free to price without consequence — is a hypothesis. The
   diagnostic that would have settled it was truncated before recording
   which positioning group the measured team occupied.
2. **Everything here is single-round and single-scenario.** Cash advantages
   compound and capability trade-offs bite over a full game; neither is
   visible in one round. That is Stage 3's question.
3. **Escalation thresholds are judgement**, not derived: 10% of baseline net
   income, 1% of baseline index. Both are recorded in
   `screening-summary.json` and can be changed without rerunning anything.

## Analysis-contract test

`core/tests/test_screening_analysis_contract.py` pins a synthetic report with
known flat, material and below-threshold rows, and fails if the analysis
reads absent or obsolete keys. It found the real weakness immediately: given
the previous key layout, or no baseline, `classify()` had been answering
"flat" — the one answer certainly wrong. It now raises
`UnreadableScreeningReport`. The same module carries the audit-runner
regression, since a `SimpleTestCase`-only suite is what exposed the test
runner installing guards into databases Django never created.
