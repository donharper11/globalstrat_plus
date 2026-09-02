# GSP-CRV2-10 Stage 3A — checkpoint, not closure

**Runtime revision `83ec2bd`.** Clean tree. Frozen before this evidence was
generated.

**Stage 3 is not closed.** Immutability — freezing a ready platform and
retiring the feature-upgrade path — lands only after Stage 4 delivers
re-basing, so the product is never in a state where neither route to a better
product exists.

Reworked once after the checkpoint audit of `ce163bb`. What that audit found is
recorded below rather than quietly fixed.

## The five items

| # | Item | Implementation | Tests |
|---|---|---|---|
| 1 | **V2-040** timing | decrement loop filters `development_started_round__lt=current_round`; `MIN_DEVELOPMENT_ROUNDS = 1`; maximum from `max_platform_development_rounds` | `PlatformTimingTests` — **5** |
| 2 | **V2-039** unlock | `unlock_problem` on both write surfaces; `persisted_unlock_violations` at the engine | `UnlockGateTests` — **4** |
| 3 | **V2-044** ownership | `ownership_problem` on both write surfaces; `persisted_ownership_violations` at the engine | `PlatformOwnershipTests` — **4** |
| 4 | Funding / draft lifecycle | `unfunded_draft` + `funded_round` (migration `0080`); the charge follows `funded_round`; **`allocate_platform_funding` decides the whole team's funding once per round** | `FundingLifecycleTests` — **4**, `FundingAccountingTests` — **4**, `AggregateFundingTests` — **4** |
| 5 | Feature cap | scenario-scoped `rd_costs.feature_cap` on both write surfaces; `persisted_feature_cap_violations` refuses at the engine | `FeatureCapTests` — **6** |
| — | Old upgrade path operational | untouched | two existing contract tests, below |

**55 tests in `test_platform_lifecycle`; 97 in the affected set.** No class
inherits another's tests — see the per-class table in the transcript.

## What the audit caught, and what it turned out to be

**`funded_round` was a label, not evidence.** The charge still followed the
submission row, so an `unfunded_draft` was billed in the round it was asked
for, and when the money later arrived nothing was booked in the funding round —
the decision belonged to an earlier submission. Payment and the clock were
never the same event.

The charge now follows `TeamPlatform.funded_round`. A draft books nothing; the
authored cost lands **exactly once** in the round funding arrives; the clock
starts in that same round; later rounds neither charge again nor restart it.

**That change broke the V2-024 invariant, and its runtime assertion caught it.**
`funding_need.decision_outlays` still read the submission rows, so the funding
rule and the engine disagreed about the same outlay — *shared 0 vs engine
1,000,000.00*. The shared rule now reads the same funding-round basis. Without
that assertion the two would have diverged silently, which is the failure
V2-024 exists to prevent.

**Activation was rewriting the decision.** It sliced an over-cap feature set to
the cap, so the platform carried an arbitrary subset while the stored row still
named the full set. The engine now refuses the row, naming the row, the
submitted count and the cap. Nothing is truncated.

**The cap was already enforced on both write surfaces** by an existing
serializer validator — the gap was in tests, not enforcement, and the check I
added in the first cut was a second rule for the same thing, so it is removed.
But that validator read `ScenarioConfig` **unscoped by scenario**: one call used
`.get()`, which raises `MultipleObjectsReturned` as soon as a second scenario
authors the key, and another used `.first()`, taking an arbitrary scenario's
value. Both now read the scenario-scoped `rd_costs.feature_cap`.

**The checkpoint overstated its own coverage.** It claimed ownership was proved
on both writes and at the engine, and cap enforcement on both writes, when
neither test existed. Both now do.

## Accounting: observed from the accounting path

`FundingAccountingTests` runs the real `calculate_operating_expenses` with the
engine's own `RoundContext` and reads the figures that call produced for the
team from `context.opex` — `rd_expense` and `platform_capex`. It does **not**
re-derive them.

Across four rounds, in expense mode:

| Round | State | `rd_expense` | `platform_capex` |
|---|---|---|---|
| 1 | requested, unfunded | 0 | 0 |
| 2 | funding lands, clock starts | **authored** | 0 |
| 3 | building | 0 | 0 |
| 4 | active | 0 | 0 |

with the sum across the lifecycle asserted equal to the authored cost — once,
and nowhere else. In capitalisation mode the same platform reports
`platform_capex == authored` in the funding round with `rd_expense` zero, zero
in later rounds, and the asset balance on the platform is checked separately as
a second observation.

**What is not observed: cash.** These assertions cover the expense and capex
the cost path reports and the capitalised balance on the platform. No cash
figure is read, and this report does not claim one. An earlier version of this
section said cash was recorded when the test recorded no cash field.

Two earlier versions of this proof were wrong in ways worth recording. The
first summed a helper that queried `funded_round` and re-priced the platform
itself, which proved that `funded_round` selects one round and nothing about
what the engine booked. The second asserted only that nothing was capitalised
in expense mode, which a branch booking nothing at all would have passed. The
helper is deleted rather than left unused.

The test clears the scenario config cache before each run, because `get_config`
memoises per scenario and the capitalisation test would otherwise measure the
default branch twice.

## Evidence

- `evidence/decision-rules/stage3a/test-transcript.txt` — affected set run once
  at `83ec2bd`: **97 tests, OK**. Written to a temporary path outside the
  repository and moved in afterwards, so producing the artifact cannot dirty
  the tree its header reports; the header records **0 modified tracked files
  at the start and at the end**
- `evidence/decision-rules/stage3a/migration-check.txt` —
  `makemigrations --check --dry-run` → **No changes detected**, exit 0; one
  migration: `0080_platform_funding_lifecycle`

## V2-045 — funding is allocated as a set

The independent audit of `f81426c` found the funding decision was made one
platform at a time against the same unreserved balance: two $1,000,000 drafts
against $1,500,000 both started, and the accounting path booked $2,000,000.

`allocate_platform_funding` now decides once per team per round across carried
drafts and new requests together, reserving each accepted cost before
considering the next, and returns the single set both the lifecycle and the
accounting read. Priority is carried drafts first, then new requests, in
generation then name then id order — stated because it must be deterministic,
and drafts-first so an old draft cannot starve behind later requests.

`AggregateFundingTests` covers the reported case, the same-round control, a
pair written straight to the table, and the capitalisation mode. The allocator
was also exercised directly against the audit's figures and funds one of the
two.

## V2-046 — one platform per generation

The V2-045 refactor lost an invariant the old code got for free. Creating each
platform inside the decision loop meant the next row's existing-platform query
saw the one just created; collecting candidates first — which the aggregate
allocation needs — made every row see the same pre-loop state, so two rows
naming one generation were both funded, created and charged. The allocator was
internally consistent and allocating over the wrong inventory.

Refused now on both write surfaces as a cross-row rule, at the Phase-1
precondition for rows that bypass the API, and excluded from the allocator's
inventory independently of either. `DuplicateGenerationTests` — 8 tests,
including the positive controls that two distinct generations still allocate as
V2-045 specifies and a retired generation remains re-buildable.

## V2-047 and the V2-046 carried state — held generations

Two gaps the first duplicate repair left, both about **state** rather than
payload. A request for an already-held generation was accepted with a 200,
persisted at its price, then silently skipped by the engine, which booked
nothing — a stored decision replaced with no decision at all. And a carried
draft was never reconciled against another non-retired platform of its
generation, so an upgrade residue from `f39b853` promoted into a second live
platform.

Both writes now refuse a held generation before replacement; Phase 1 refuses a
stored one, and refuses existing state holding more than one non-retired
platform per team and generation, naming every conflicting row rather than
repairing it. The allocator declines to promote such a draft as a defence
behind the refusal.

**The candidate database was inventoried, not assumed:** 302 non-retired
platform rows across 302 distinct team/generation pairs, zero duplicates today.
The state is reachable from the predecessor revision, which is why the guard
exists.

`HeldGenerationTests` — 16 tests, including the retired positive control.

## The old upgrade path is still reachable

- `test_distinct_features_are_still_accepted_on_both_paths` — R&D investments
  through **both** supported surfaces, accepted and persisted
- `test_a_correctly_priced_upgrade_is_accepted_and_stored` — the stored row
  carries the authored price

Had Stage 3B removed the path early, both would fail rather than pass.

## `method`

Left affecting price only, per the ruling. Stage 2 made it materially affect
price, satisfying "lead time, price, or both". No licensing lead-time rule was
invented.

## Status of the findings

**V2-039, V2-040, V2-044, V2-045, V2-046 and V2-047 are implemented at
`83ec2bd`, pending integrated Stage 3 closure.** Not closed; the register records them the same way. Closure
comes with the integrated Stage 3/4 evidence, after immutability lands.

## Not run

No full suite, browser work, determinism, concurrency, load or tournament run,
and no Stage 4 work.
