# GSP-CRV2-06 — Bounded adversarial balance and exploit search

**Gate:** V2-B  
**Owner:** simulation/balance engineer independent of rules author

## Objective

Find material value loops, dominant strategies, validation gaps, and unstable
balance boundaries with reproducible search. The goal is risk-proportionate
evidence for the field competition—not a proof of mathematical global optimality.

Expensive optimization starts only after the legal decision space is uniform and
frozen. Do not optimize rules already known to be broken.

## Stage 1 — legal-space gate

Complete this stage before any release-scale search.

1. Generate the decision-field inventory from serializers, scenario
   configuration, and both supported submission APIs.
2. For every field, record type, nullability, legal range/category, cross-row
   constraint, and the shared validator—or explicitly record that one is missing.
3. Compare whole-submission and per-type APIs with the same payloads. A refusal
   counts as agreement only when both return the intended rule and the control
   payload succeeds.
4. Probe zero, negative, maximum, oversized, duplicate, boundary, rounding, and
   missing/default values with focused contract tests.

### Findings already established

- **Duplicate R&D divergence:** the whole-submission API rejects two investments
  for the same platform+feature; the per-type R&D API accepts them. Repair by
  sharing the cross-row rule across both paths. Include a distinct-feature
  accepted control.
- **Negative investments become income:** twelve fields accept negative values
  that flow into `strategy_expense`. Confirm with the current two-team Phase-1
  probe, then reject them through shared validation across both API paths.

Log each finding before repair. These are validation/correctness repairs, not
competition-rule changes. Run focused API and engine tests only. Once they pass,
commit the legal-space freeze and record its source identity.

### Candidate rule findings

Use small controlled probes before escalating these:

- strategic capability rewards `rd_spend / rd_budget`, so `$1/$1` can equal a
  multi-million-dollar programme;
- zero-revenue guards may be evaded by selling one unit.

Log a P0/P1 only if the probe demonstrates a material, repeatable advantage.
Do not silently change a published scoring formula. A confirmed rules-sensitive
finding receives a concrete disposition request and the search continues against
the currently adopted rule unless it creates a risk-free loop or
opponent-independent dominant strategy; either of those stops certification.

## Stage 2 — cheap sensitivity screening

Screen every exposed decision dimension, but do not produce exhaustive plots for
flat or unreachable fields.

- Numeric: legal minimum, documented baseline, and legal maximum.
- Categorical: each legal category once.
- Cross-row rules: one valid and one invalid combination.
- Use one fixed scenario/opponent/seed for screening.

Store machine-readable results for every dimension. Escalate to a denser sweep
and labeled plot only when screening shows a material response, cliff,
non-monotonicity, discontinuity, or known exploit risk. A table stating “flat in
screening” is sufficient for the rest.

## Stage 3 — capped adversarial search

Use canonical payloads and record every seed. A candidate is a multi-round
strategy, not an isolated row.

1. **Random discovery:** batches of 50 candidates, maximum 200 candidates,
   evaluated across three opponent populations: competent baseline, diverse
   legal strategies, and the strongest candidate found so far.
2. **Local improvement:** run one method—hill climbing *or* evolutionary
   mutation—from at most the five best random candidates, capped at 100 new
   candidate evaluations total. Do not run a second optimizer merely for
   algorithm variety.
3. **Discovery seeds:** three fixed seeds. Cheap development uses one opponent,
   one seed, and at most 20 candidates; it creates no evidence.
4. **Holdout:** evaluate the final top five on three previously unused seeds
   across the same opponent populations. Holdout is evaluation only—no tuning.

Stop random discovery before 200 only after two consecutive 50-candidate batches
produce no new exploit class and do not change the leading strategy family or
materially improve its margin. Record the stopping decision. Increase a cap only
when the current result is unstable, and state the reason before running more.

## Explicit exploit probes

Exercise each distinct mechanism once, using automated tests or the search
harness as appropriate:

- deadline timing/resubmit and information leakage/timing;
- negative/oversized numerics and duplicate rows;
- rounding/currency asymmetry;
- FX, trade-finance, sourcing, and inventory value loops;
- progressive disclosure;
- early unassailable lead;
- collusion or opponent-independent dominance.

Do not rerun CRV2-01 determinism, CRV2-02 concurrency, CRV2-03 provider/SIGKILL,
or CRV2-04 integrity evidence. Cite them where the probe crosses those controls.

## Acceptance

- Whole and partial APIs enforce the same legal decision space.
- No negative-cost income loop or duplicate-row ordering dependency remains.
- Report the strongest legal strategy and its distribution/margin over the
  competent baseline on holdout seeds; a simple bootstrap interval is sufficient
  when enough samples exist, otherwise report the complete distribution.
- Classify every demonstrated exploit as closed or open with severity/owner.
  “Accepted-and-uncovered” is not a passing category.
- Any risk-free value loop or opponent-independent dominant strategy is a P0/P1
  finding and stops PASS until repaired or the rules are explicitly changed and
  retested.
- Preserve source data, seeds, canonical payloads, harness revision, focused
  tests, escalated plots, and a concise search summary under
  `evidence/adversarial-balance/`.

## Verification budget

- Development: focused tests and the 20-candidate smoke only.
- Pre-freeze: legal-space contracts, sensitivity screening, and one 50-candidate
  search batch.
- Frozen candidate: the capped search, holdout, affected focused tests, static
  checks, and evidence checksums once.
- No full backend suite in this handoff. CRV2-09 owns the single integrated
  backend/frontend suite and product playthrough.

If a frozen search exposes a code defect, stop, repair with focused tests,
refreeze, and repeat only affected screening plus the capped search. Do not use
full suites or unrelated certification matrices as a debugging loop.
