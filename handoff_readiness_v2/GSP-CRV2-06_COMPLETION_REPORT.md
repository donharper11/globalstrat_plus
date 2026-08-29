# GSP-CRV2-06 — adversarial balance: completion report

## Revisions, labelled

| role | revision | meaning |
|---|---|---|
| **Runtime freeze** | `182480effdd40c01dd1be9c60da74214e9edaa26` | the engine, harness and scenario configuration every accepted measurement was produced at |
| **Evidence** | `182480effdd40c01dd1be9c60da74214e9edaa26` | identical: the accepted tournament, the baseline-competency gate and the V2-024/V2-025 rechecks all ran at this revision |
| **Report-only** | see `git log -1` for this file | adds this document and the register text; changes no runtime code, no harness and no evidence artifact |

Evidence: `handoff_readiness_v2/evidence/adversarial-balance/`, 21 artifacts,
`SHA256SUMS` regenerated and verified.

## Outcome

Seven findings raised in this handoff, seven closed. Two of them were
opponent-independent dominant strategies demonstrated by the Stage 3
tournament; each stopped the handoff for a rules disposition before any scoring
change was made.

| ID | Finding | Severity | Status |
|---|---|---|---|
| V2-018 | Thirteen investment and headcount fields accepted negative values; a negative investment was income, and a negative headcount times a salary band was worth $50,002,530,000 | **P0** | Closed — one non-negative policy at 21 fields across both write surfaces, plus a fail-closed engine precondition on persisted rows |
| V2-020 | Equity issuance priced shares off `total_equity` before it was assigned: `UnboundLocalError` for the first team raising equity, failing the whole round for every team; later teams priced off the previous team's balance sheet | **P0** | Closed — opening book value per share |
| V2-021 | R&D scored against the team's own declared budget, so $1 against $1 earned full credit | P1 | Closed — scenario target |
| V2-022 | Inactivity classified by decision intent rather than realised outcome | P1 | Closed — material-revenue floor |
| V2-023 | Isolated positioning removed price response entirely; then the clamped high-price tail; then a single reference made the positioning tiers incoherent | P1 | Closed — per-tier authored reference prices plus a high-price elasticity |
| V2-024 | Equity issuance raised the index at no cost; raising and immediately paying it out won 9 of 9 holdout cells | P1 | Closed — funding-need rule |
| V2-025 | Stripping all headcount beat competent play in 9 of 9 cells | P1 | Closed — capability multiplied by staffing adequacy |

V2-019 was withdrawn as filed in error. **V2-017** (216 admin write routes
outside the lifecycle boundary) remains **open** and is not owned by this
handoff, as does the deployment action to run the stack as a non-owner database
role.

## The accepted tournament

Gated before it ran. The baseline-competency gate passed 6 of 6
(`baseline-competency-gate.json`): R&D spend $2,000,000 equals the scenario
target; pools staffed 60/40/50 exactly at the authored optima; each product
priced at its own tier reference ($700 premium, $420 mainstream); financing
legal with nothing requested against a $40,623,905.56 maximum; no
decision-limit or funding violations; revenue $887,517.12 against a material
floor of $8,875.17. The payload contract then checked all 17 baseline,
opponent and candidate payloads: **0 illegal**. The neutral genome scored
exactly **0.000** against the competent baseline, proving the candidate set had
not drifted from it.

**Discovery** — 15 targeted candidates x 3 populations, one identity, advantage
over competent play:

| candidate | competent | diverse | incumbent | worst | median |
|---|---|---|---|---|---|
| rd-at-target | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| rd-saturated | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| equity-at-legal-max | -0.220 | -0.160 | -0.220 | -0.220 | -0.220 |
| dividend-payout | -0.230 | -0.220 | -0.230 | -0.230 | -0.230 |
| discovery-31 | -0.320 | +1.120 | -0.320 | -0.320 | -0.320 |
| debt-funded-scale | -0.840 | +0.920 | -0.840 | -0.840 | -0.840 |
| price-at-clamp | -2.000 | -2.070 | -2.000 | -2.070 | -2.000 |
| price-above-clamp | -2.120 | -1.470 | -2.120 | -2.120 | -2.120 |
| discovery-15 | -3.630 | -1.780 | -3.630 | -3.630 | -3.630 |
| rd-starved | -4.790 | -4.820 | -4.790 | -4.820 | -4.790 |
| price-above-clamp-lean | -5.110 | -4.300 | -5.110 | -5.110 | -5.110 |
| near-inactive | -7.010 | -5.480 | -7.010 | -7.010 | -7.010 |
| discovery-44 | -7.080 | -4.970 | -7.080 | -7.080 | -7.080 |
| skeleton-crew | -14.590 | -14.560 | -14.590 | -14.590 | -14.590 |
| commercially-inactive | -24.220 | -22.430 | -24.220 | -24.220 | -24.220 |

**Holdout** — top three x 3 populations x 3 unused identities, 27 candidate
evaluations plus 9 matched baselines as separate controls:

| candidate | distribution | worst-case | median | cells won |
|---|---|---|---|---|
| rd-at-target | nine values of 0.00 | 0.00 | 0.00 | 0/9 |
| rd-saturated | nine values of 0.00 | 0.00 | 0.00 | 0/9 |
| equity-at-legal-max | -0.23 x6, -0.16 x2, -0.15 | -0.23 | -0.23 | 0/9 |

**No candidate wins across every population and holdout fixture.** The
strongest legal strategy found is indistinguishable from competent play: its
margin is exactly 0.000, because the candidates that achieve it *are* the
baseline in every respect scoring reads.

## Explicit exploit mechanisms — disposition matrix

| Mechanism | Disposition | Evidence |
|---|---|---|
| Deadline timing / resubmit | Closed, prior evidence | GSP-CRV2-02 concurrency matrix; not rerun here, cited |
| Information leakage / timing | Closed, prior evidence | GSP-CRV2-04 sensitive-read logging and read inventory |
| Negative / oversized numerics | **Closed this handoff** | V2-018. `negative-sweep.json`: 8 fields measured, all 8 paid before repair. `decision_limits` covers 21 fields at both write surfaces plus a persisted-row precondition |
| Duplicate rows | Closed this handoff | Duplicate-R&D regression is uniform across the API intersection; `dimension-inventory.json` path uniformity |
| Rounding / currency asymmetry | Screened, nothing found | `screening.json`: every numeric dimension probed with a fractional value (0.005) alongside zero, negative, 2^31 and 10^15 |
| Progressive disclosure | **Not exercised — open coverage gap** | No probe in this handoff. Owner: CRV2-09 or a follow-on; recorded rather than claimed |
| FX / trade finance / sourcing / inventory value loops | **Partially covered — open coverage gap** | The non-negative policy covers `SourcingAllocation`; `value-loop.json` measured the ESG loop. Dedicated FX, trade-finance and inventory loops were **not** screened: none appears among the 44 dimensions in `screening-summary.json` |
| Early unassailable lead | Closed this handoff | Tournament: no candidate exceeds competent play on worst case across nine holdout cells |
| Collusion / opponent-independent dominance | **Closed this handoff** | V2-024 and V2-025, each demonstrated at 9/9 cells and each repaired; re-measured at 0/9 and -14.59 respectively |

## Rules adopted in this handoff

**V2-024 eligible uses — a rule, not a limitation.** Eligible uses are the
deterministic, decision-controlled outlays knowable before resolution, plus
debt repayment. Dividends are **not** an eligible use, and neither are the
outcome-dependent costs — COGS, tax, interest, tariffs and revenue-scaled
administrative overhead. Those must be funded from opening capital and
operating revenue. `maximum_new_equity = max(0, eligible_uses -
(opening cash + new debt))`, and a request above it is rejected, never clamped.

**V2-023 per-tier references.** `reference_price =
scenario_reference_prices[product.positioning]`, seeded 250 / 420 / 700 / 1000.
A single global reference scored a premium product at its own authored price as
1.667x, clamping competitiveness to zero and removing 53% of its demand.

**V2-025 staffing adequacy.** `capability = earned_capability x mean over pools
of clamp01(headcount / optimal)`, optima authored at 60/40/50 and validated
before competitive mutation. Equal pool weighting is a choice, not a
derivation.

## Limitations, stated

1. **The incumbent population was degenerate in the accepted run.** No candidate
   beat competent play, so the incumbent *is* the baseline and the incumbent
   column equals the competent column for every candidate. Three populations
   were run; two carried independent information.
2. **Holdout across fixture identities is a weak generalisation test here.**
   Streams differ on every probe, but the resolved outcome barely follows:
   index was identical across all three identities in the pre-freeze check.
3. **Discovery is 50 random plus 15 targeted candidates**, not an exhaustive
   search. Absence of further exploits is absence of evidence at this budget.
4. **Two exploit mechanisms are not covered**, as the matrix above records:
   progressive disclosure, and the dedicated FX / trade-finance / inventory
   value loops.
5. **The 50-candidate discovery batch is historical.** It ran against the
   pre-correction baseline; its margins are not comparable with this
   tournament's and are not combined with them.

## Evidence integrity and process note

`checksums.py` regenerates and verifies the inventory, and every run that
writes an artifact calls it.

Four tournaments were discarded before this one. Each was invalidated by the
same defect in a different place: the baseline, or the genome that represents
it, stopped being competent in the terms a newly adopted rule scores — actual
R&D spend, staffing against authored optima, per-tier pricing, and finally the
neutral genome itself. None was a game exploit; each would have been reported
as one. The baseline-competency gate and the neutral self-check exist so that
this class of error refuses to publish rather than being caught by review.
