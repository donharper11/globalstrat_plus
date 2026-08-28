# GSP-CRV2-06 — Adversarial optimizer and sensitivity analysis

**Gate:** V2-B  
**Owner:** simulation/balance engineer independent of rules author

## Objective

Search unintended decision space with reproducible optimizers, not authored
strategy profiles, and produce complete sensitivity evidence.

## Harness requirements

- Discover legal dimensions/ranges from serializers/scenario configuration; do
  not hard-code a convenient subset.
- Generate zero/max/boundary, randomized, incoherent, repeated and oscillating
  vectors. Record seed and canonical payload for every run.
- Explicit probes: deadline timing/resubmit, information leakage/timing, negative
  and oversized numerics, rounding/currency asymmetry, FX/trade-finance/sourcing/
  inventory loops, progressive disclosure, early unassailable lead and collusion.
- Run random search plus hill-climbing/evolutionary self-play across multiple
  opponent populations and seeds. Hold out evaluation seeds to detect overfit.
- Sweep every exposed numeric/categorical dimension while holding a documented
  baseline; output machine-readable data and labeled plots. Flag flat regions,
  cliffs and non-monotonic discontinuities.

## Acceptance

Report strongest legal strategy and margin over competent baseline with
confidence interval/distribution, not one game. Classify each exploit as closed,
accepted-and-covered, or accepted-and-uncovered. Every rejected payload must be
uniform through full and partial APIs. Any risk-free value loop or opponent-
independent dominant strategy opens a P0/P1 finding before repair.

Evidence/harness lives under `handoff_readiness_v2/evidence/adversarial-balance/`;
plots alone without source data and seeds do not pass.
