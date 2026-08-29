# GSP-CRV2-06 — adversarial balance: completion report

**Revision:** `954b931`
**Evidence:** `handoff_readiness_v2/evidence/adversarial-balance/`, 20 artifacts, `SHA256SUMS` verified.

## Outcome

Six findings raised, six closed. Two of them — V2-024 and V2-025 — were
opponent-independent dominant strategies demonstrated by the Stage 3
tournament, and each stopped the handoff for a rules disposition before any
weighting or scoring change was made.

| ID | Finding | Severity | Status |
|---|---|---|---|
| V2-020 | Equity issuance priced off an unbound closing figure | P1 | Closed (opening book value per share) |
| V2-021 | R&D scored against the team's own declared budget | P1 | Closed (scenario target) |
| V2-022 | Inactivity classified by intent rather than outcome | P1 | Closed (material-revenue floor) |
| V2-023 | Isolated positioning removed price response; then the clamped tail | P1 | Closed (reference price + high-price elasticity) |
| V2-024 | Equity issuance raised the index at no cost | P1 | Closed (funding-need rule) |
| V2-025 | Stripping headcount beat competent play | P1 | Closed (staffing adequacy) |

V2-019 was withdrawn as filed in error. V2-017 (admin write routes outside the
lifecycle boundary) remains open and is not owned by this handoff.

## Stage 3, as run

The capped optimizer plan was replaced mid-handoff by a bounded adversarial
tournament. Preserved from the earlier plan: one completed 50-candidate random
discovery batch (`stage3-discovery-batch.json`), not rerun.

- **Fixture identity** varies deterministically by seed through the cohort key,
  the one input reaching every stochastic subsystem. Pre-freeze checks: three
  seeds give distinct, stable identities; every probed engine stream differs
  across every pair; each identity reproduces exactly.
- **Discovery:** 15 targeted candidates x 3 opponent populations on one
  identity, 45 candidate evaluations.
- **Selection:** worst-case advantage across all three populations, median as
  tie-break, so a win against one population cannot reach the finals.
- **Holdout:** 3 finalists x 3 populations x 3 unused identities = 27 candidate
  evaluations, plus 9 matched baselines reported separately.

**Result:** `equity-raise` won 9 of 9 holdout cells, worst case +0.66, with
near-identical advantage against competent (0.670), diverse (0.680) and
incumbent (0.660) opponents. `equity-and-dividend` won all nine at +0.57 with
zero variance. `skeleton-crew` won all nine at +0.22. The handoff stopped.

## What the tournament did not find

No candidate attacking a closed finding paid. V2-023 pricing scored -0.97 at
the clamp, -1.35 above it and -4.25 above it with costs stripped. V2-022
inactivity scored -17.99 and near-inactivity -6.22. The three strongest random
candidates lost against competent opponents (-0.44, -0.52, -0.53) while winning
against diverse ones (+1.63, +0.90, +1.21) — the population-specific win the
selection rule exists to reject.

## Repairs and their verification

**V2-024.** `maximum_new_equity = max(0, eligible_uses - available_funding)`,
dividends excluded, rejected rather than clamped. One calculator:
`funding_need.decision_outlays` holds every outlay line and
`costs.calculate_operating_expenses` calls it and asserts its own lines still
agree. Enforced at the API (partial write, whole-submission write, lock) and as
a fail-closed engine precondition. 14 focused tests. Re-check: both equity
candidates are **refused in every population**, and the incumbent population
cannot be constructed at all because its opponents are refused.

**V2-025.** `capability = earned_capability x staffing_adequacy`, adequacy the
mean of `clamp01(headcount / optimal)` across the three pools. Optima are
scenario-authored and validated positive before competitive mutation; both
consumers fail closed. 12 focused tests. Re-check across the same nine cells:
skeleton-crew moves from 9/9 at +0.22 to **0/9 at -7.17 worst case**.

## Limitations, stated

1. **Holdout across fixture identities is a weak generalisation test here.**
   Streams differ on every probe, but index was 57.99 on all three identities
   and cash and revenue took two distinct values across three. The stochastic
   subsystems have little purchase on this fixture.
2. **The harness baseline underspends R&D by twenty times.** It declares the
   documented $2,000,000 `rd_budget` while writing a $100,000
   `DecisionRDInvestment` placeholder, and only actual spend reaches scoring.
   Every advantage figure here is relative to that competitor. `rd-actual-target`
   wins 9 of 9 at about +4.3 for this reason; it costs $1,900,000 and buys
   capability, which is the game rewarding investment rather than an exploit.
3. **Discovery is 50 random plus 15 targeted candidates**, not an exhaustive
   search. Absence of a further exploit is absence of evidence at this budget.
4. **The V2-024 funding rule excludes resolution-dependent outlays** — admin
   overhead scaled by revenue, COGS, tariffs, tax, interest — because a rule
   running before the first competitive write cannot know them. This makes the
   rule stricter, never more permissive.
5. **Equal pool weighting in staffing adequacy is a choice**, not a derivation.
   The disposition fixed the four semantics; the thirds are mine.

## Evidence integrity

`checksums.py` regenerates and verifies the inventory, and every run that
writes an artifact calls it. The inventory was previously hand-maintained,
which is why a rerun could silently invalidate it — the defect that failed an
earlier audit.
