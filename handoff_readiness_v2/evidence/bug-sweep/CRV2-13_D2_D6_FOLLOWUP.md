# CRV2-13 known-list follow-up — D2 and D6

**Working-tree basis:** current checkout after a521f7a  
**Scope:** repository-verifiable work only. Browser and operational checks remain
open under CRV2-13.

## D2 — budget-versus-cash rule

**Finding recorded before repair.** V2-038 closed the three separate rule
calculations by introducing core.services.rd_costs.budget_assessment. A
follow-up source review found that the lock validator, Decision Summary, and
Finance context had not all finished delegating to the same result:

- the lock validator still referred to its deleted total_budget local while
  calculating projected ending cash;
- the summary and Finance context re-added only the three visible budget
  lines, omitting research_budget and platform development from their cash
  presentation.

This is a participant-facing contradiction: an amount can be refused at lock
but disappear from a Finance or Summary cash figure.

**Repair.** Those three surfaces now read budget_assessment:

- lock and Finance projected cash use committed_total;
- Summary and Finance publish total_allocated, research_allocated,
  platform_development_committed, and committed_total separately;
- their unallocated figure is cash less committed_total.

research_budget remains a legacy model field. This change does not give it a
new in-round charge or alter a competition rule; it makes all existing cash
checks report the already-enforced amount consistently.

**Focused proof.**

AuthoritativePriceTests.test_budget_vs_cash_rule_agrees_on_lock_summary_and_finance_context
creates $900 cash and an otherwise empty $1,000 submission whose four budget
lines are $100/$200/$300/$400. It exercises the actual three participant
surfaces, not a helper directly:

1. POST …/lock/ refuses the $1,000 committed spend;
2. GET …/summary/ returns a $1,000 committed total and -$100 unallocated;
3. GET …/context/finance/ returns the same total and -$100 projected cash.

    backend/scripts/test-postgres core.tests.test_rd_costs.AuthoritativePriceTests

    Ran 16 tests in 0.311s — OK

The expected Bad Request entries are assertions of negative API paths.

**Disposition:** code-level D2 closed in this working tree; retain the three
surface regression in the final CRV2-09 integrated run.

## D6 — round-zero adoption scale factor

**Finding.** bootstrap_round_zero currently writes:

    new_adopters = bass_p * population_size * average_starter_product_share * 10

The * 10 was introduced in the baseline snapshot (111d541, 2026-04-17) with
the sole comment “Scale for meaningful numbers.” It has no earlier commit in
this repository, scenario configuration key, or specification attribution.

**What the authored data establishes.** The three scenario YAML files author
segment population, bass_p, bass_q, starter product share, unit volume, price,
and starting revenue. They do **not** author either a round-zero duration, an
initial cumulative-adoption percentage, or an adoption-scale parameter. For
example, Consumer Electronics’ Innovator starter profile has two shares (8%
and 5%) and 25,000/40,000 unit volumes, while NA Value Seekers has a
population of 3,600,000 and bass_p=0.02. Nothing states why a first-period
Bass increment should be multiplied by ten, nor connects the resulting
per-segment adoption row to the starter volumes.

This cannot be derived honestly from the currently authored data: the
multiplier changes the round-one Bass cumulative state and therefore later
competitive demand, not merely a round-zero display number.

**No behavior change made.** The existing multiplier is retained so this
investigation does not silently recalibrate a running competition.

**Rules-owner blocker.** Before a release candidate can call D6 closed, the
rules owner must choose and record one of:

1. an authored round-zero duration/scale parameter with a pedagogical basis;
2. an explicit initial cumulative-adoption target per segment/market; or
3. an approved decision to retain factor 10, including the intended simulated
   time interval and the calibration evidence that supports it.

The selected rule then needs a fixed-policy measurement and a regression that
pins the authored source, rather than another embedded constant.

**Disposition:** open rules/calibration blocker. It is not safe to close D6
from repository archaeology alone.
