# GSP-CRV2-11 Stage 2 — competent-field and archetype-parity measurement

## Result: not certified; a deterministic product-allocation defect blocks it

Three fresh disposable PostgreSQL replays were run from the current evidence
runner. Each used the same four Consumer Electronics starter profiles and the
same documented pricing, promotion, distribution, and staffing policy. No
production scenario, runtime, or student game was changed.

The early all-NA control is score-balanced but **not a competent field**:

| round | index range | index spread | 1% materiality threshold (55 × 1%) | produced | sold | unsold |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 58.13–58.26 | 0.13 | 0.55 | 167,000 | 72,000 | 95,000 |
| 2 | 61.32–61.55 | 0.23 | 0.55 | 167,000 | 72,000 | 95,000 |
| 3 | 64.50–64.86 | 0.36 | 0.55 | 167,000 | 72,000 | 95,000 |

The threshold is the existing adversarial-screening material-index threshold:
1% of the scenario's 55-point base index. Thus the four profiles have no
material starting-score advantage in this control. But 57% of output is
unsold in every early round, all profiles make a loss, and their cash declines.
It is a parity control, not evidence of competent play.

## Regional-start variant: reject as a parity configuration

The handoff asks whether four `NA` home markets were intentional. The same
policy with homes assigned `NA, APAC, EU, LATAM` produced first-three-round
index spreads of **3.50, 8.16, and 9.78 points**. This is far above the 0.55
materiality threshold. It is evidence against silently diversifying starter
regions as a calibration remedy; the profiles are not presently equivalent
across those markets.

## Market-responsive production probe: invalidated by a runtime finding

To remove the proven inventory waste without giving any profile a different
rule, a second all-NA run used the same 10% buffer over each product-market's
own prior sales for every team. Human adoption fell from 72,000 in round 1 to
**four units** in round 2. This is not plausible market response to a 10%
buffer and cannot be treated as a competent baseline.

The cause is visible in `preference_engine._get_team_products_in_market`:
it returns `TeamProduct.objects.filter(...)` without an ordering. When two
products have equal best fit, the loop retains its first row. In the control,
the first product consumed demand; after the policy provisioned that product,
the next round could select its tied sibling, whose floor was one unit. A
product-selection order therefore changes competitive allocation and cash.

This is an engine determinism/allocation defect for **GSP-CRV2-13** (or its
runtime owner), not a starter-profile dial for CRV2-11 to tune. Until it is
repaired and independently replayed, there is no valid way to show that a
market-responsive, capacity-adequate field is both competent and archetype
balanced.

## Evidence files

- `stage2_archetype_parity_replay.json` — all-NA ten-round constant-policy
  control, including every team result and product output.
- `stage2_regional_parity_replay.json` — three-round regional-start variant.
- `stage2_competent_parity_replay.json` — three-round uniform responsive
  production probe; retained as a failing measurement, not a baseline.

## Required disposition

CRV2-11 Stage 2 cannot be accepted yet. Preserve the all-NA control result
(early score parity) and the regional-start rejection, then re-run the
competent-field/archetype-parity measurement after the runtime owner defines a
stable product tie-break or an explicit multi-product demand allocation rule.
