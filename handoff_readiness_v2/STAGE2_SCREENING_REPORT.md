# GSP-CRV2-06 Stage 2 — sensitivity screening result

**Screen revision:** `e3654ece7b4dcb3cf58633b590bbd3529d252b1d`  
**Seed:** `crv2-06-screen-2-counterfactual`  
**Method:** same-game transactional counterfactual; team compared only with itself from one frozen checkpoint  
**Baseline:** load_demo scripted defaults; see harness/baseline.py  
**Runtime:** 628.9s  
**Evidence:** `handoff_readiness_v2/evidence/adversarial-balance/` (`screening.json`, `screening-summary.json`, checksums in `SHA256SUMS`)

## Self-tests — evidence is refused unless all three pass

| Control | Result |
|---|---|
| `baseline_vs_identical_baseline_is_zero` | pass |
| `known_flat_field_does_not_move` | pass |
| `known_responsive_field_moves` | pass |

Baseline-against-identical-baseline returning exactly zero is what proves the
checkpoint restores. Without it, the two earlier versions of this screen looked
plausible while measuring nothing.

## Coverage

| | |
|---|---:|
| Dimensions planned | 130 |
| Probes screened | 107 |
| Probes that moved | 47 |
| Probes flat | 60 |
| Unreachable (with rule) | 0 |
| Not applied (would abort evidence) | 0 |
| Not screened by rule | 23 |

Not screened by rule: 16 reference dimensions (a foreign key naming which
product, market or feature a row is about — a Stage 3 strategy choice, not a
magnitude), 5 JSON and 2 text. Each carries its reason in `screening.json`.

## Baseline metrics (subject team)

| Metric | Value |
|---|---:|
| `cash_closing` | 7198822.31 |
| `index_value` | 56.54 |
| `net_income` | -16216094.97 |
| `operating_income` | -15736094.97 |
| `satisfaction_score` | 0.5772 |
| `strategy_expense` | 3900000.00 |
| `total_revenue` | 887174.40 |

## Escalation thresholds

- Material money response: **≥0.10** of the subject's own baseline for net income, revenue or closing cash.
- Material index response: **≥0.01** of the baseline performance index. Tighter than the money threshold on purpose — the
  index is a ranking scale where teams finish a few points apart — but not zero,
  because every cost change nudges it through the financial component. The median
  nudge in this screen was 0.09 on a baseline of 56.54, which is 0.16%.
- Known exploit-sensitive mechanism, regardless of measured size.

These thresholds are judgement, not measurement. They are recorded in
`screening-summary.json` so they can be changed without rerunning the screen.

## Verdicts — 44 dimensions: 20 flat, 24 escalate

| Dimension | Kind | Verdict | Reasons |
|---|---|---|---|
| `budget.marketing_budget` | numeric | flat in screening | — |
| `budget.rd_budget` | numeric | escalate | known exploit-sensitive mechanism |
| `budget.strategy_budget` | numeric | flat in screening | — |
| `esg.environmental_investment` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `esg.social_investment` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `financing.debt_repayment` | numeric | escalate | material response against the subject baseline |
| `financing.dividend_per_share` | numeric | escalate | material response against the subject baseline |
| `financing.new_debt` | numeric | escalate | material response against the subject baseline |
| `financing.new_equity` | numeric | escalate | material response against the subject baseline |
| `market-entry.action` | choice | escalate | performance index moved materially |
| `market-entry.initial_investment` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `market-entry.integration_strategy` | choice | flat in screening | — |
| `marketing.channel_digital_pct` | numeric | flat in screening | — |
| `marketing.channel_trade_pct` | numeric | flat in screening | — |
| `marketing.channel_traditional_pct` | numeric | flat in screening | — |
| `marketing.demand_estimate` | numeric | flat in screening | — |
| `marketing.distribution_investment` | numeric | flat in screening | — |
| `marketing.distribution_strategy` | choice | flat in screening | — |
| `marketing.production_volume` | numeric | escalate | known exploit-sensitive mechanism, material response against the subject baseline, performance index moved materially |
| `marketing.promotion_budget` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `marketing.retail_price` | numeric | escalate | known exploit-sensitive mechanism |
| `marketing.sales_team_count` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `partnerships.action` | choice | flat in screening | — |
| `partnerships.annual_investment` | numeric | flat in screening | — |
| `plants.action` | choice | escalate | material response against the subject baseline |
| `plants.capacity_units` | numeric | flat in screening | — |
| `plants.contract_mfg_volume` | numeric | flat in screening | — |
| `platforms.committed_cost` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `platforms.method` | choice | flat in screening | — |
| `product-retires.timing` | choice | flat in screening | — |
| `products.positioning` | choice | flat in screening | — |
| `rd.amount` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `rd.calculated_cost` | numeric | flat in screening | — |
| `rd.method` | choice | flat in screening | — |
| `rd.target_level` | numeric | flat in screening | — |
| `talent.commercial_headcount` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `talent.commercial_salary_level` | choice | escalate | material response against the subject baseline |
| `talent.commercial_training_budget` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `talent.operations_headcount` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `talent.operations_salary_level` | choice | flat in screening | — |
| `talent.operations_training_budget` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `talent.rd_headcount` | numeric | escalate | material response against the subject baseline, performance index moved materially |
| `talent.rd_salary_level` | choice | escalate | material response against the subject baseline |
| `talent.rd_training_budget` | numeric | escalate | material response against the subject baseline, performance index moved materially |

## Escalated dimensions, with the numbers

| Dimension | Probe | Net income Δ | Revenue Δ | Index Δ |
|---|---|---:|---:|---:|
| `budget.rd_budget` | legal_minimum | 0.00 | 0.00 | -0.10 |
| `budget.rd_budget` | funded_maximum | 0.00 | 0.00 | -0.09 |
| `esg.environmental_investment` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `esg.environmental_investment` | funded_maximum | -59652267.68 | 0.00 | -0.58 |
| `esg.social_investment` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `esg.social_investment` | funded_maximum | -59652267.68 | 0.00 | -0.58 |
| `financing.debt_repayment` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `financing.debt_repayment` | funded_maximum | 0.00 | 0.00 | 0.07 |
| `financing.dividend_per_share` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `financing.dividend_per_share` | funded_maximum | 0.00 | 0.00 | -0.53 |
| `financing.new_debt` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `financing.new_debt` | funded_maximum | 0.00 | 0.00 | -0.50 |
| `financing.new_equity` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `financing.new_equity` | funded_maximum | 0.00 | 0.00 | 0.04 |
| `market-entry.action` | category:enter | 0.00 | 0.00 | 0.00 |
| `market-entry.action` | category:change_mode | 150000.00 | 0.00 | 0.92 |
| `market-entry.action` | category:exit | 130000.00 | 0.00 | 0.92 |
| `market-entry.initial_investment` | legal_minimum | 100000.00 | 0.00 | 0.01 |
| `market-entry.initial_investment` | funded_maximum | -59900000.00 | 0.00 | -0.59 |
| `marketing.production_volume` | legal_minimum | 2182320.00 | 0.00 | 0.08 |
| `marketing.production_volume` | funded_maximum | -10909417680.00 | 0.00 | -0.59 |
| `marketing.promotion_budget` | legal_minimum | 396875.03 | -3138.24 | 0.02 |
| `marketing.promotion_budget` | funded_maximum | -59606965.96 | -6995.52 | -0.60 |
| `marketing.retail_price` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `marketing.retail_price` | funded_maximum | 0.00 | 0.00 | 0.00 |
| `marketing.sales_team_count` | legal_minimum | 1000000.00 | 0.00 | 0.04 |
| `marketing.sales_team_count` | funded_maximum | -5999999000000.00 | 0.00 | -0.59 |
| `plants.action` | category:build | 0.00 | 0.00 | 0.00 |
| `plants.action` | category:expand | 3500000.00 | 0.00 | 0.13 |
| `plants.action` | category:contract_mfg | 3500000.00 | 0.00 | 0.13 |
| `platforms.committed_cost` | legal_minimum | 100000.00 | 0.00 | 0.01 |
| `platforms.committed_cost` | funded_maximum | -59900000.00 | 0.00 | -0.59 |
| `rd.amount` | legal_minimum | 100000.00 | 0.00 | -0.09 |
| `rd.amount` | funded_maximum | -59900000.00 | 0.00 | 1.31 |
| `talent.commercial_headcount` | legal_minimum | 299581.78 | -420.00 | 0.01 |
| `talent.commercial_headcount` | funded_maximum | -2399998800163.94 | -164.64 | -0.59 |
| `talent.commercial_salary_level` | category:1 | 448511.12 | -1495.20 | 0.02 |
| `talent.commercial_salary_level` | category:2 | 224267.27 | -735.84 | 0.01 |
| `talent.commercial_salary_level` | category:3 | 0.00 | 0.00 | 0.00 |
| `talent.commercial_salary_level` | category:4 | -299287.34 | 715.68 | -0.01 |
| `talent.commercial_salary_level` | category:5 | -748601.46 | 1404.48 | -0.02 |
| `talent.commercial_training_budget` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `talent.commercial_training_budget` | funded_maximum | -59997343.44 | 2667.84 | -0.59 |
| `talent.operations_headcount` | legal_minimum | 162042.67 | 0.00 | 0.01 |
| `talent.operations_headcount` | funded_maximum | -2399998562654.38 | 0.00 | -0.60 |
| `talent.operations_training_budget` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `talent.operations_training_budget` | funded_maximum | -59210490.35 | 0.00 | -0.60 |
| `talent.rd_headcount` | legal_minimum | 500000.00 | 0.00 | 0.02 |
| `talent.rd_headcount` | funded_maximum | -2399998000000.00 | 0.00 | -0.59 |
| `talent.rd_salary_level` | category:1 | 750000.00 | 0.00 | 0.03 |
| `talent.rd_salary_level` | category:2 | 375000.00 | 0.00 | 0.02 |
| `talent.rd_salary_level` | category:3 | 0.00 | 0.00 | 0.00 |
| `talent.rd_salary_level` | category:4 | -500000.00 | 0.00 | -0.01 |
| `talent.rd_salary_level` | category:5 | -1250000.00 | 0.00 | -0.04 |
| `talent.rd_training_budget` | legal_minimum | 0.00 | 0.00 | 0.00 |
| `talent.rd_training_budget` | funded_maximum | -60000000.00 | 0.00 | -0.59 |

## Flat in screening

A table stating "flat in screening" is sufficient for these; no dense sweep or
plot is produced for them.

- `budget.marketing_budget` (numeric)
- `budget.strategy_budget` (numeric)
- `market-entry.integration_strategy` (choice)
- `marketing.channel_digital_pct` (numeric)
- `marketing.channel_trade_pct` (numeric)
- `marketing.channel_traditional_pct` (numeric)
- `marketing.demand_estimate` (numeric)
- `marketing.distribution_investment` (numeric)
- `marketing.distribution_strategy` (choice)
- `partnerships.action` (choice)
- `partnerships.annual_investment` (numeric)
- `plants.capacity_units` (numeric)
- `plants.contract_mfg_volume` (numeric)
- `platforms.method` (choice)
- `product-retires.timing` (choice)
- `products.positioning` (choice)
- `rd.calculated_cost` (numeric)
- `rd.method` (choice)
- `rd.target_level` (numeric)
- `talent.operations_salary_level` (choice)

## Two corrections made after the run

**The report read a format that no longer existed.** It looked for `control` and
`probe` keys from the pre-counterfactual design, so every fraction came out
`None`. Nothing escalated on measurement and the only three dimensions flagged
were the ones on the hard-coded exploit-sensitive list. It printed a confident
"41 flat, 3 escalate" while measuring nothing — the same failure as the earlier
40/40 and 42/42 screens: a component left behind by a format change.

**The index criterion had no threshold**, so any nudge counted. Adding the 1%
relative threshold moved four dimensions from escalate to flat.

## Not yet done in Stage 2

- Dense sweeps and labelled plots for the 24 escalated dimensions.
- The two candidate rule probes (`$1 budget / $1 spend`; one-unit revenue bypass
  of the zero-revenue guards). Harness written, not yet run.

Stage 3 remains blocked on the V2-010/V2-011 rules disposition.
