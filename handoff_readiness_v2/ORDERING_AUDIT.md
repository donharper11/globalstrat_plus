# Unordered-queryset audit (GSP-CRV2-01 requirement 5)

An unordered `SELECT` returns rows in whatever order the storage engine finds
convenient. That order can change after a vacuum, an index-only scan, a plan
flip or a restore. Wherever the engine iterates such a query and the iteration
*binds an RNG draw, mutates state, decides a tie, or accumulates a
non-associative numeric value*, the result of the round depends on something
nobody chose.

## What was found

A sweep of `backend/core/engine/` (excluding the four Phase-2 prose modules)
found **168 iterated querysets with no explicit ordering**. Every one now
declares an order, except six that are documented exemptions below.

They came in two waves, and the second wave is the interesting one.

* **93 written inline** — `for row in X.objects.filter(...)`. Found by reading
  the loop's iterator expression.
* **75 reached through a local name** —

      rows = X.objects.filter(...)
      for row in rows:

  Invisible to a check that only inspects the iterator, and by far the more
  common shape in this codebase. They were found because a cross-environment
  replay *failed*: `_score_entry_mode_risk` iterated an unordered
  `TeamMarketPresence` scan, the restored database returned Africa and East
  Asia in the opposite order, and `RoundResultCoherence.breakdown` — which
  lists one entry per presence in iteration order — changed with it. Three
  same-host replays agreed with each other and disagreed with the original
  resolution. Logged as V2-012.

The lesson is worth keeping: a static sweep is a guard, not a proof. The proof
is a round restored from its own backup and re-resolved.

## Two kinds of ordering, and why the difference matters

* **`order_by('id')`** makes a round replayable: a restored database has the
  same primary keys, so the same order comes back. It does **not** make a round
  independent of insertion order, because id order *is* insertion order.
* **Natural-key ordering** (`order_by('team_product__name', 'market__code')`
  and similar) makes the loop independent of insertion order as well.

Rows that students insert in an order of their own choosing are ordered by
natural key. The first version of the forward/reverse test is what forced this
distinction: with `order_by('id')` everywhere, rewriting the same decisions
backwards changed `RoundResultCoherence.breakdown`, because the breakdown lists
one entry per marketing decision in iteration order. Sites now on natural keys:

| Module | Loop | Order |
|---|---|---|
| `coherence.py` | marketing decisions (price and distribution alignment) | `team_product__name, market__code` |
| `coherence.py` | R&D investments | `team_platform__name, feature__code, method` |
| `costs.py` | R&D, platform development, marketing, market entry, acquisitions, plant, product retirement | natural columns per table |
| `rd_processing.py` | platform development, R&D, product create, product retire | natural columns per table |
| `strategy_effects.py` | market entry, partnerships, plant decisions | `market__code` + action/option |
| `alliance_engine.py` | marketing decisions, compliance investment, talent allocation | `team_product__name` / `market__code` / `talent_pool` |
| `instructor_alerts.py`, `derived_features.py` | marketing decisions | `team_product__name, market__code` |
| `talent.py`, `investor_features.py`, `agents/state.py`, `agents/governments.py` | talent allocation | `talent_pool` |
| `performance.py` | R&D investment sum | `team_platform__name, feature__code, method` |
| `sc_engine.py` | sourcing allocation | `critical_input_category, supplier__supplier_id` |
| `fx_engine.py` | hedge decisions and open positions | `team__name, currency_pair[, opened_round]` |

Engine-created state rows — supplier state, lane state, active modifiers,
event impacts, team platforms, plants, presences — are ordered by `id`. Those
rows are written by the engine itself in an order the engine already fixes, so
their id order is a deterministic function of the round, not of anything a
participant controls.

## Exemptions

Six loops are deliberately left unordered. Each is recorded in
`ORDER_EXEMPT` in `core/tests/test_manifest_determinism.py`, and a test fails
if an exemption stops matching any real loop — so the list cannot rot.

| Site | Why order cannot matter |
|---|---|
| `sc_engine.py` — `Supplier.objects.filter(scenario=...)` | Builds a dict keyed by the unique supplier code. |
| `sc_engine.py` — `ShippingLane.objects.filter(scenario=...)` | Builds a dict keyed by the unique lane code. |
| `sc_engine.py` — `SupplierState.objects.filter(round=...)` (×3) | Builds a dict keyed by supplier id, unique per round. |
| `agents/governments.py` — `GovernmentProfile.objects.filter(...)` | Builds a dict keyed by the unique market code. |
| `sc_engine.py` — `Supplier.objects.filter(scenario=scenario)` (second site) | Builds a dict keyed by the supplier primary key. |
| `leaderboard.py` — `RoundResultFinancials...values().annotate()` | Aggregate collected into a dict keyed by team id. Adding an `ORDER BY` would change the `GROUP BY` and the aggregate itself. |

## How this is kept true

`core.tests.test_manifest_determinism.EngineIterationOrderTests` parses every
module under `core/engine/` and fails on any `for` loop or comprehension whose
iterator looks like a queryset and carries no `.order_by(`. It resolves a loop
over a local name back to the expression that assigned it, so the shape that
hid V2-012 cannot pass again. A new unordered loop fails the suite rather than
quietly changing a hash.

The behavioural counterpart is
`ManifestSnapshotIntegrationTests.test_row_insertion_order_does_not_change_the_competitive_hash`:
a fixture game's decisions — budget, marketing, R&D, market entry, plant,
compliance, talent and sourcing — are written, Phase 1 is run and its
competitive hash captured, then the same rows are deleted and rewritten in
reverse order (so every one carries a different primary key and the physical
row order is inverted) and Phase 1 is run again. The two hashes must match.

## Related findings raised by this audit

* **V2-010** — `core/engine/rng.py` seeds on `game.section_id or game.id`, but
  `sc_engine._seed()` and `compliance_engine` seed on `game.id`. Two sections
  of one class share an event stream but not a supply-chain stream.
* **V2-011** — the supply-chain and compliance passes consume a single
  `random.Random` across all teams. The order is explicit and replay is exact,
  but adding or withdrawing a team shifts every later team's draw.

Neither is changed here: both would alter published results, which is a
competition-rules decision rather than a hardening one. Both were re-triaged to
P1 after audit — a behaviour that can change a published result is never
cosmetic — and the register records the specific choice each needs.
