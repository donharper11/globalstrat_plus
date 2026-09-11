# GSP-CRV2-11 Stage 2 audit — FAIL / targeted runtime rework

Audited evidence revision: `620f47d`.

> **Superseded allocation scope — 2026-09-05.** The rules owner clarified that
> demand is allocated per product × segment × market, not to one selected
> product per firm. The earlier non-goal excluding multi-product allocation no
> longer applies. See `handoffs/GSP-CRV2-11-product-level-demand-allocation.md`.
>
> **Superseded parity disposition — 2026-09-06.** Later-round Performance
> Index spread is not a starter-parity gate. The only required parity is the
> round-zero base index and shared rank, which bootstrap already provides.

## Decision

**FAIL / REWORK. Stage 2 is not certified.**

The measurements are credible, including the all-NA early index spreads
(`0.13`, `0.23`, `0.36`), the regional-start spreads (`3.50`, `8.16`, `9.78`),
and the responsive-production collapse. A fresh independent disposable replay
of the submitted responsive policy reproduced `72,000` units sold in round 1
and `4` in each of rounds 2 and 3.

The failure is a runtime determinism/allocation defect, not a profile dial.
However, the submitted evidence does not yet prove its claimed causal mechanism
by controlled product-order reversal, and sending a CRV2-11 blocker solely to
CRV2-13 creates a sequencing loop: CRV2-13 follows CRV2-11.

## Finding to register before repair

Register **V2-055 — tied active products have no deterministic selection rule
(P1)** before changing code.

`preference_engine._get_team_products_in_market()` returns an unordered
`TeamProduct` queryset. `calculate_fit_scores()` retains the first product with
a strictly greater fit; equal best-fit products therefore depend on unspecified
database row order. That selected product controls the production cap, demand,
allocation, inventory, cash, and performance result. The Stage 2 responsive
probe exposes the consequence when the formerly selected product and its tied
sibling receive different next-round production volumes.

Record both the submitted evidence and the independent replay in the finding.
This is P1: it can change a team's competitive result without any different
student decision, but it is not a security or data-loss P0.

## Required repair

This is an immediate, bounded runtime-owner repair. Do **not** wait for the
later CRV2-13 breadth sweep.

1. Define the existing single-best-product rule deterministically: order the
   product queryset by `TeamProduct.id` before the strict-greater fit loop, and
   state in code that the lowest id is the tie-break for equal fit. Do not add a
   multi-product demand-allocation system in this rework; that would be a new
   rules/calibration design choice.
2. Add a focused regression fixture with two equal-fit active products in one
   market. It must prove both that the selected product is the lower-id product
   and that the returned queryset is ordered. The latter makes removal of the
   ordering clause fail reliably rather than relying on a database's accidental
   physical order.
3. Add controlled mutation evidence: reverse the product order (or remove the
   ordering clause in the dedicated probe) and show that the old behaviour
   would select the alternate tied product / change its capacity path. Restore
   the repair before commit.
4. Run the focused regression and the directly affected Bass/preference tests.

## Required Stage 2 remeasurement

Because this changes runtime code, regenerate all three Stage 2 replays from
the repaired revision:

- all-NA parity control;
- regional-start variant;
- all-NA responsive-production probe.

The responsive result must now demonstrate a capacity-adequate policy rather
than collapse through an arbitrary tied sibling. Reassess competence and
the round-zero parity record from those new outputs; do not carry forward the
old allocation values as post-repair evidence.

## Non-goals

- Do not retune starter profiles, market populations, Bass parameters, prices,
  regions, AI fit, or the production policy while making this repair.
- Do not silently diversify home regions; regional outcomes are descriptive,
  not a parity-calibration remedy.
- Do not begin CRV2-11 Stage 3 or CRV2-13's broader sweep.

## Acceptance for re-audit

Re-audit requires a pre-repair V2-055 entry, a deterministic selected-product
test that fails without ordering, controlled mutation evidence, focused green
tests, three regenerated Stage 2 artifacts from the repair revision, and a
revised Stage 2 conclusion based only on those artifacts.
