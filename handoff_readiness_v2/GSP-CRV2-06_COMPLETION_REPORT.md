# GSP-CRV2-06 — adversarial balance: completion report

## Revisions, separated by role

| role | revision | what it means |
|---|---|---|
| **Runtime freeze** | `182480e` | the engine, harness and scenario configuration the accepted tournament ran at |
| **Evidence** | per artifact | each artifact records the `code_revision` it was produced at; the coverage probes ran later than the tournament, on top of the V2-023 per-tier revision and the V2-024/V2-025 repairs |
| **Report-only** | this commit | adds this document and register text; changes no runtime code, no harness and no evidence artifact |

Evidence: `handoff_readiness_v2/evidence/adversarial-balance/`, **26 artifacts**,
`SHA256SUMS` regenerated and verified from a clean tree.

Key evidence revisions: accepted tournament `182480e`; baseline-competency gate
`7630125`; controlled early-lead `92db5d4`; value conservation `e73e5a4`;
progressive disclosure `f2def9a`; V2-024 recheck `525c637`; V2-025 attribution
`facfd6b` and recheck `c42ed70`.

## Outcome

**Nine findings confirmed and closed.** Two withdrawn, each with the reason it
was misfiled.

| ID | Finding | Severity | Status |
|---|---|---|---|
| V2-018 | Thirteen investment and headcount fields accepted negatives; a negative investment was income, and a negative headcount times a salary band was worth $50,002,530,000 | **P0** | Closed — one non-negative policy over 21 fields on both write surfaces, plus a fail-closed engine precondition on persisted rows |
| V2-020 | Equity issuance priced shares off `total_equity` before it was assigned: `UnboundLocalError` for the first team raising equity, failing the round for everyone; later teams priced off the previous team's balance sheet | **P0** | Closed — opening book value per share |
| V2-021 | R&D scored against the team's own declared budget, so $1 against $1 earned full credit | P1 | Closed — scenario target |
| V2-022 | Inactivity classified by decision intent rather than realised outcome | P1 | Closed — material-revenue floor |
| V2-023 | Isolated positioning removed price response entirely; then the clamped high-price tail; then a single global reference made the positioning tiers incoherent | P1 | Closed — per-tier authored reference prices plus a high-price elasticity |
| V2-024 | Equity issuance raised the index at no cost; raising and immediately paying it out won 9 of 9 holdout cells | P1 | Closed — funding-need rule, rejected not clamped, enforced at the API and as an engine precondition |
| V2-025 | Stripping all headcount beat competent play in 9 of 9 cells | P1 | Closed — capability multiplied by staffing adequacy against authored optima |
| V2-026 | Progressive disclosure governed writes only; the read serializers used `fields = '__all__'` and consulted nothing | **P1** | Closed — the registry now governs reads, default-denying without context |
| V2-028 | `/api/users/` is routed and could not answer: both user serializers declared a `team` field that does not exist on `User`, so DRF raised `ImproperlyConfigured`; `assign-team` also wrote an attribute the model does not persist | **P1** | Closed — serializers expose `team_id`, `select_related` removed, assignment persists |

### Withdrawn

**V2-019 — filed in error, no defect existed.** I measured serializers and
described endpoints. The rule I claimed was missing had always been enforced in
the view; my probe simply never exercised the view. The tests written for it
were kept because they pin real behaviour, but no code was changed and nothing
was broken.

**V2-027 — real measurement, wrong cause.** I filed a P1 against the central
scoring rule claiming an early lead was unassailable: a front-loaded leader held
a 17.72 margin that a later identical investment could not close. The cause was
compliance enforcement, not the scoring rule. The leader's challenger drew
`customs_documentation` freezes in its revenue-bearing market; revenue went to
zero, the V2-022 inactivity cap pinned its composite at 0.2500, and it lost
about five index a round. Under controlled conditions the same front-load peaks
at **2.53**, not 17.72. Filed on a single playthrough that could not distinguish
a stochastic freeze from a structural advantage.

## Explicit exploit mechanisms — measured dispositions

| Mechanism | Disposition | Evidence |
|---|---|---|
| Deadline timing / resubmit | Closed, prior evidence | GSP-CRV2-02 concurrency matrix, cited not rerun |
| Information leakage / timing | Closed, prior evidence | GSP-CRV2-04 sensitive-read logging and read inventory |
| Negative / oversized numerics | Closed this handoff | V2-018; `negative-sweep.json`, 8 of 8 fields paid before repair |
| Duplicate rows | Closed this handoff | duplicate-R&D regression uniform across the API intersection; `dimension-inventory.json` |
| Rounding / currency asymmetry | Screened, nothing found | `screening.json`: every numeric dimension probed with a fractional value alongside zero, negative, 2^31 and 10^15 |
| **Progressive disclosure** | **Measured; defect found and repaired (V2-026)** | `progressive-disclosure-probe.json`: real student walkthrough, signed JWT, positive control 200. `inventory.buffer_days` (unlock round 3) returned at round 1 by two surfaces. Thirteen focused authorization tests now cover hiding before unlock, direct-object access matching list rendering, override-then-restore re-hiding, cross-class isolation, appearance after legitimate unlock, and default-deny on missing or partial context |
| **FX value conservation** | **Measured; conserves value** | `value-conservation-probe.json`: a hedge on a currency the team does not trade is correctly skipped. Two pairs naming the same foreign currency **do** each open a full-notional position against one exposure — the over-hedge is constructible — but the premium is charged per notional, so it costs 20,000 a round and creates nothing |
| **Trade finance value conservation** | **Measured; conserves value** | Instrument cycled with the trade held constant: 0.00 across every round, `letter_of_credit` proved persisted. Run on a **capable fixture populated from the authoritative `consumer_electronics_2026` definition through the scenario loader** — 6 instruments, 25 suppliers, 20 lanes, 5 regimes — not the earlier fixture, which selected the first available scenario and declared none |
| **Sourcing value conservation** | **Measured; conserves value** | 100% allocation and a 500,000-unit commitment with production and sales at zero: 0.00 across every round |
| **Inventory value conservation** | **Measured; conserves value** | Stock built and carried with sales suppressed to 1.37 units against 20,000 normal; cash plus inventory falls every round, 11.9M to -56.4M |
| **Early unassailable lead** | **Measured; no lock-in. V2-027 withdrawn** | `controlled-early-lead.json`: exogenous shocks silenced in scenario data, baseline exactly repeatable, no sales stopping, cap never applied. Unaided the lead decays 2.53 → 1.88 with a composite gap of -0.0007. Against the strongest legal counter the challenger leads by round 4 and finishes **4.39 ahead** with an adopter base 111,034 larger |
| Collusion / opponent-independent dominance | Closed this handoff | V2-024 and V2-025, each demonstrated at 9 of 9 cells and each repaired; re-measured at refused-everywhere and 0 of 9 |

## The controlled early-lead measurement

Every exogenous shock was silenced **in scenario data, not by mocks or patches**:
`baseline_enforcement_probability_per_round` on five `ComplianceRegime` rows and
`probability_per_round` on thirty-eight `EventTemplateDefinition` rows, twenty
of them supply-chain. The configuration applied is recorded in the artifact and
asserted every round; the run refuses if any freeze or event fires, or if the
two baseline playthroughs differ round for round. They did not.

| arm | gap when front-load ended | gap at end | composite gap at end | adopter gap at end |
|---|---|---|---|---|
| both return to baseline | 2.53 | **1.88** | -0.0007 | +48,965.70 |
| challenger plays the strongest legal counter | 2.53 | **-4.39** | -0.0867 | **-111,034.30** |

A composite gap of -0.0007 means current-round performance is equal to four
decimal places. What persists is the accumulated index plus an adopter
advantage the leader paid for — an intended first-mover return. It reverses
under a legal counter.

**No performance-index change is warranted.** The index integrates with no decay
term, so a gap persists unless the trailing team scores a higher composite;
under control the trailing team does score higher, slightly by playing on and
decisively when it counters. Changing that rule would have repaired something
that is not broken.

### The diagnostic that was missing, now required

The original probe recorded index, rank, cash and adopters and could not say
*why* a team's revenue went to zero, so two rounds of enforcement were
indistinguishable from a structural advantage. Every playthrough probe now
records, per team per round: whether sales stopped, whether the inactivity cap
applied, and which compliance freezes and events fired, with regime, market and
freeze window. A balance measurement that cannot explain its own outliers will
eventually report one as a finding. This one did.

## Scope and residual risk

These bound what the handoff establishes. They are not unresolved acceptance
gaps: every acceptance mechanism above carries a measured disposition.

1. **Search volume is bounded by design.** Discovery was 50 random candidates
   plus 15 targeted ones, not an exhaustive search. Absence of a further exploit
   is absence of evidence at this budget. Residual risk: an exploit outside the
   sampled and targeted space.
2. **The incumbent population was degenerate in the accepted tournament.** No
   candidate beat competent play, so the incumbent was the baseline and that
   column equals the competent column throughout. Three populations ran; two
   carried independent information. Residual risk: strategies that beat an
   incumbent unlike the baseline are untested.
3. **Outcome variation across fixture identities is weak.** Every probed engine
   stream differs across identities and each identity reproduces exactly, but
   the resolved outcome barely follows: index was identical across all three in
   the pre-freeze check. Holdout across identities therefore tests opponent
   composition more than engine stochasticity. Residual risk: identity-specific
   behaviour that the fixture cannot express.
4. **Two rate paths, one field, one scenario.** The FX over-hedge costs its
   premium on the path measured; whether some rate movement makes double
   notional net-positive is not established. Component-level scoring beyond
   capability is not persisted by the engine, so the five-way breakdown was not
   available without an engine change outside this budget.

## Evidence integrity

`checksums.py` regenerates and verifies the inventory, and every run that writes
an artifact calls it. The inventory was previously hand-maintained, which is how
a rerun once invalidated it without anyone noticing.

## Process note

Four tournaments were discarded before the accepted one. Each was invalidated by
the same defect in a different place: the baseline, or the genome standing in
for it, stopped being competent in the terms a newly adopted rule scores —
actual R&D spend, staffing against authored optima, per-tier pricing, and
finally the neutral genome itself. None was a game exploit; each would have been
reported as one. The baseline-competency gate, the payload contract and the
neutral self-check exist so that this class of error refuses to publish rather
than being caught in review.
