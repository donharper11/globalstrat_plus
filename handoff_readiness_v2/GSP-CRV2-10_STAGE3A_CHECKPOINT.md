# GSP-CRV2-10 Stage 3A — checkpoint, not closure

**Revision `9a29672`.** Clean tree.

**Stage 3 is not closed.** Immutability — freezing a ready platform and
retiring the feature-upgrade path — lands only after Stage 4 delivers re-basing,
so the product is never in a state where neither route to a better product
exists. This checkpoint covers the five items that can land while the old
upgrade path stays operational.

## The five items

| # | Item | Implementation | Tests |
|---|---|---|---|
| 1 | **V2-040** timing | `rd_processing.py`: the decrement loop filters on `development_started_round__lt=current_round`; `MIN_DEVELOPMENT_ROUNDS = 1`; maximum from the scenario's `max_platform_development_rounds` | `PlatformTimingTests` — 5 |
| 2 | **V2-039** unlock enforcement | `rd_costs.unlock_problem` on both write surfaces; `persisted_unlock_violations` refuses at the engine before competitive mutation | `UnlockGateTests` — 4 |
| 3 | **V2-044** ownership | `rd_costs.ownership_problem` on both write surfaces; `persisted_ownership_violations` at the engine boundary | covered in the same run via the shared validator; engine helper unit-tested |
| 4 | Funding / draft lifecycle | `rd_costs.can_fund_platform`; `unfunded_draft` status and `funded_round` (migration `0080`); the clock starts in the round the money lands | `FundingLifecycleTests` — 4 |
| 5 | Feature-count cap | `rd_costs.feature_cap` / `feature_count_problem` on both write surfaces **and** at activation | `FeatureCapTests` — 2 |
| — | Old upgrade path operational | untouched | confirmed by two existing contract tests, below |

## Evidence

- `evidence/decision-rules/stage3a/test-transcript.txt` — the focused set, run
  once at this revision: **67 tests, OK**
- `evidence/decision-rules/stage3a/migration-check.txt` —
  `makemigrations --check --dry-run` → **No changes detected**, exit 0;
  migration added: `0080_platform_funding_lifecycle`

## The old upgrade path is still reachable

Confirmed by existing contract tests in the same run, not by a new walkthrough:

- `test_distinct_features_are_still_accepted_on_both_paths` — writes R&D
  investments through **both** supported surfaces and asserts they are accepted
  and persisted
- `test_a_correctly_priced_upgrade_is_accepted_and_stored` — asserts the stored
  row carries the authored price and the level target is honoured

Had Stage 3B removed the upgrade path early — the failure the sequencing exists
to prevent — both would fail rather than pass.

## Two decisions worth recording

**An unfunded draft keeps the decision rather than discarding it.** A team that
cannot pay gets `unfunded_draft`: not building, no clock started, no rounds
remaining. When the money lands the draft starts building *in that round*, and
the authored `development_rounds` counts from there. The alternative was the
behaviour this replaces, where a team that could not pay still got the
platform; refusing the decision outright was the other option, but that
silently discards a choice the team made.

**Funding is tested against the authored price, not the submitted figure.**
After V2-037 the submitted figure is not the team's to choose, so testing
affordability against it would reintroduce the defect through the back door.

## One observation

V2-039 and V2-044 proved to be the same defect in two places: a gate that binds
only the teams who lock binds nobody, because close defaults everyone else
straight into the engine. Both now refuse at the write surfaces *and* at the
engine boundary, in the shape Stage 2's cost guard established.

## `method`

Left affecting price only, per the ruling. Stage 2 made it materially affect
price, which satisfies "lead time, price, or both". No licensing lead-time rule
was invented.

## Status of the findings

**V2-039, V2-040 and V2-044 are implemented at `9a29672`, pending integrated
Stage 3 closure.** They are not closed, and the register records them that way:
closure comes with the integrated Stage 3/4 evidence, after immutability lands.

## Not run

No full suite, browser work, determinism, concurrency or load run, and no
separate multi-round evidence drill. The focused tests exercise the actual
write surfaces and the engine boundary, which is what these repairs change.
