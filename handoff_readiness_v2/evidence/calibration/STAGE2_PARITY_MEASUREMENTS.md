# GSP-CRV2-11 Stage 2 — competent-field and archetype-parity measurement

## Result: not certified; the deterministic repair is verified, but the fixed responsive policy is not capacity-adequate

All three disposable PostgreSQL replays were regenerated from `cb7e6f9`, the
bounded V2-055 repair. They use the same four Consumer Electronics starter
profiles and the same pricing, promotion, distribution, staffing, and
production policies as the submitted measurements. No scenario, profile,
market, Bass parameter, AI fit, or student game was changed.

## V2-055 deterministic single-product rule: repaired and mutation-tested

`_get_team_products_in_market()` now orders active products by `TeamProduct.id`.
The existing strict-greater fit loop therefore selects the lower-ID product for
an exact equal-fit tie. `CalibrationDemandAccountingTests` builds two equal-fit
active products with live marketing decisions, verifies both the SQL ordering
and the selected lower-ID product, then controlledly reverses that order and
proves the alternate product becomes selected. The focused calibration and
engine-iteration suites pass (9 tests).

This is a bounded determinism repair, not a multi-product allocation change.

## All-NA control: early parity only; not a competent field

The existing materiality threshold is 1% of the 55-point starting index:
**0.55 points**. The repaired control has no material archetype-score spread
through round 4, but it does not remain parity-safe over the ten-round horizon.

| round | index range | index spread | threshold | produced | sold | unsold |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 58.13–58.26 | 0.13 | 0.55 | 167,000 | 72,000 | 95,000 |
| 2 | 61.32–61.55 | 0.23 | 0.55 | 167,000 | 72,000 | 95,000 |
| 3 | 64.50–64.86 | 0.36 | 0.55 | 167,000 | 72,000 | 95,000 |
| 4 | 67.70–68.19 | 0.49 | 0.55 | 167,000 | 72,000 | 95,000 |
| 5 | 70.89–71.52 | 0.63 | 0.55 | 167,000 | 72,000 | 95,000 |
| 10 | 78.22–88.27 | 10.05 | 0.55 | 167,000 | 72,000 | 95,000 |

Round 1 leaves 57% of output unsold and every profile makes a loss. The
constant-production control is therefore neither competent-field evidence nor
ten-round archetype-parity evidence. Its limited result is only that the
profiles do not start with a material index advantage in the first four rounds.

## Regional-start variant: reject as a parity configuration

With the same policy and homes `NA, APAC, EU, LATAM`, the regenerated spreads
are **3.50, 8.16, and 9.78** in rounds 1–3, respectively. All exceed 0.55.
The configuration remains rejected; regional diversification is not a silent
calibration remedy.

## Responsive production probe: still invalid, for a different and now observable reason

The unchanged uniform policy provisions each product-market at 110% of that
product-market's prior sales. It again sells 72,000 units in round 1 and only
four in each of rounds 2 and 3. The regenerated product trace identifies why:
for every profile, the lower-ID product sells in round 1 and receives 22,000
(or 13,201) units in round 2; the higher-ID sibling then receives the one-unit
floor and sells that one unit.

This cannot be an equal-fit tie: the repaired rule and its controlled mutation
test select the lower ID for a tie. The selected product has genuinely changed
under the fixed scoring inputs, while the test policy has provisioned capacity
from the prior selected product's sales. The trace thus refutes the previous
claim that unspecified row ordering alone caused the collapse. It also proves
the current per-product historical-sales policy cannot establish a
capacity-adequate competent field when the single best product changes.

## Evidence files

- `stage2_archetype_parity_replay.json` — repaired-revision ten-round all-NA
  constant-policy control with product-level output.
- `stage2_regional_parity_replay.json` — repaired-revision three-round regional
  variant with product-level output.
- `stage2_competent_parity_replay.json` — repaired-revision three-round
  responsive probe; retained as a failing measurement, not a baseline.

## Required disposition

Stage 2 is not certified. V2-055 is repaired, but a new explicit, uniformly
applied capacity policy (or a multi-product allocation rule) must be approved
and then measured before competent-field/archetype-parity evidence can be
claimed. The Stage 2 runtime rework expressly prohibits choosing that new
policy during this repair, so no further calibration change is made here.
