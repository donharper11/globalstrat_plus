# GSP-CRV2-10 Stage 4 checkpoint — product re-basing

Runtime revision: `ac2883b` (frozen before evidence)
Prior Stage 4 runtime: `729cc2c`
Evidence: `handoff_readiness_v2/evidence/decision-rules/stage4/`

**Status: implemented, pending integrated Stage 3/4 closure. Stage 3 is not closed.**

Stage 4 adds the capability a team switches with, and the round-versioned
history that keeps already-scored rounds reconstructable across that switch.

---

## 1. What Stage 4 changes

| Area | Before | After |
|---|---|---|
| Platform for a product | one live pointer, read by every consumer | `platform_as_of_round(product, round)` over an append-only history |
| Switching platforms | not possible | `POST .../products/<id>/rebase/`, validated and charged in one transaction |
| Stock left behind | n/a | written off at the authored percentage, once, on the association that caused it |
| Past rounds after a switch | would silently re-resolve to the new platform | resolve to the platform they were scored against |

Two services: `core/services/product_platform.py` (resolution and history) and
`core/services/product_rebase.py` (the switch, its refusals and its write-off).
One migration, `0081_product_platform_history`.

---

## 2. The five audit focuses

### 2.1 Fail-closed ownership/readiness and missing-resolution checks

`product_rebase.validate()` refuses in a fixed order and returns the first
thing wrong, so a refusal names a cause rather than whatever was checked last:
absent product → foreign product → inactive product → absent platform →
foreign platform → not-ready platform → already on that platform.

`product_platform.missing_platform_resolutions()` asks the opposite question
from the one that hid BECSR's defect B. That check summed the rows it found;
this one fails on rows that are **absent**. Every active product in the game
must resolve to exactly one platform for the round, that platform must exist,
and it must belong to the same team. `advance_round` calls it as a Phase-1
precondition, before competitive mutation.

Tests: `RebaseRefusalTests` (6), `MissingResolutionTests` (3),
`RebaseEndpointTests.test_another_teams_platform_is_refused_with_400_not_500`,
`…test_an_unknown_platform_is_refused_rather_than_crashing`.

### 2.2 Atomic association switch and history seeding

`rebase()` is `@transaction.atomic`: validation, the write-off, the history row
and the pointer move commit together or not at all. A switch that charged but
did not move — or moved but did not charge — cannot be left behind.

`seed_prior_association()` writes the association that held *before* the first
switch. Without it the pre-switch rounds have no row, `platform_as_of_round`
falls back to the live pointer the switch is about to change, and every earlier
round silently re-attributes to the platform the team moved to.

Tests: `RebaseHistoryTests` (5), `RebaseRefusalTests.test_a_refusal_charges_
nothing_and_writes_no_history`, `RebaseEndpointTests.test_a_refused_call_moves_
nothing`, `…test_the_switch_is_recorded_as_history_not_only_a_pointer_move`.

### 2.3 Authoritative, exactly-once write-off accounting

The percentage is authored (`platform_switch_write_off_pct`, default 0.15) and
read from the scenario, not hardcoded at the call site.

The charge is recorded on the history row the switch created and read back from
there by `write_offs_for_round()`. A second switch in the same round updates
that row rather than adding another, because `(team_product,
effective_from_round)` is unique — so the charge cannot be booked twice.

The base is the **latest closing snapshot**, not a sum across rounds. Summing
would write off stock sold rounds ago.

Tests: `RebaseWriteOffTests` (6), including
`test_only_the_latest_closing_position_is_written_off`,
`test_the_charge_is_read_once_from_the_history_row` and
`test_a_second_switch_in_one_round_updates_rather_than_adds`.

### 2.4 Round-correct resolution at every consumption site

Every product-to-platform read in the engine now goes through the as-of-round
lookup. Measured at `ac2883b`, that is six engine consumption sites —
`preference_engine` (3), `campaign_engine`, `readiness_engine`, `costs` —
reached through `engine/utils.resolved_platform(product, round)`, which
delegates to `platform_as_of_round`. The only remaining mention of the old
direct `product.team_platform` read in `core/engine` is inside a docstring
explaining why it is no longer used.

(An earlier scoping note in this handoff said "18 consumption sites". That was
the count of raw pointer reads found during scoping, not the number of call
sites after they consolidated. Six is the measured figure.)

`platform_ids_as_of_round` is the batched form — present because the
per-product form inside a scoring loop is how an as-of-round lookup becomes too
slow to keep and gets quietly replaced by the live pointer again.

Tests: `SwitchThenReplayTests` (4) —
`test_the_engine_helper_resolves_as_of_the_round`,
`test_the_feature_level_a_past_round_scored_with_is_unchanged`,
`test_demand_and_supply_resolve_identically` (the defect-B shape: both sides
resolved from one source), `test_a_switch_does_not_disturb_an_unswitched_
product`. `RebaseHistoryTests.test_the_batched_resolution_agrees_with_the_
single_one` pins the batched form to the single one.

### 2.5 Switch-then-replay determinism across the CRV2-01 boundary

Stage 4 touched the certified boundary in two ways, both recorded here rather
than left for the auditor to find.

**The manifest envelope grew.** `team_product_platform_history` is now an
enumerated section (`manifest_sections.py`), keyed `(team_product_id,
effective_from_round)`, excluding `switched_at` because a wall-clock stamp is
not competitive state. Covered by `ManifestEnvelopeTests` (10).

**The ordering guard did not reach the new code.** `EngineIterationOrderTests`
scanned `core/engine` only, but Stage 4 put round-correct resolution in
`core/services`. `missing_platform_resolutions()` iterated an unordered
queryset there — the refusal list it builds was ordered by whatever the
database returned — and the guard could not see it.

The scan now also covers the services the engine calls, and **derives that list
from the engine's own imports** rather than a remembered one, because a scan
scoped by a hand-kept list decays the first time someone adds an import. That
derivation immediately caught `narrative_jobs.py`, which is genuinely Phase-2
prose (its `FOR UPDATE SKIP LOCKED` claim order is deliberately unspecified and
nothing it produces enters the competitive hash) and is marked narrative.

Nine further sites in `funding_need`, `rd_costs` and `product_rebase` now
declare their order.

Control run, recorded because a guard that only ever passes proves nothing —
with the Stage 4 fix reverted the new test fails and names the site:

```
product_platform.py:140 list(TeamProduct.objects.filter(team__game=game,
    status='active').select_related('team', 'team_platform'))
FAILED (failures=1)
```

and passes once restored.

Tests: `EngineIterationOrderTests` (5, was 3) — the two new ones are
`test_resolution_services_declare_their_order` and
`test_the_scanned_service_list_is_what_the_engine_actually_calls`.

---

## 3. The supported write path

The re-base service existed at `729cc2c` with no endpoint, so the capability
was real but no team could reach it. `POST /api/games/<game_id>/teams/
<team_id>/products/<product_id>/rebase/` closes that.

The round is taken from the game, never from the request body. A client-named
round would let a team backdate a switch into an already-scored round, which is
the exact history-rewrite the rest of Stage 4 exists to prevent.

The cross-team case is refused by the shared scope-guard middleware from
CRV2-08 — the new route **inherits** default-deny rather than opting into it,
and the test asserts on `response.content` because the refusal is a plain
`JsonResponse`, not a DRF one. That difference is the evidence it came from the
middleware.

Tests: `RebaseEndpointTests` (8).

---

## 4. Verification

Affected focused set, run once from clean revision `ac2883b`:

| Class | Distinct tests |
|---|---|
| `test_product_rebase.RebaseRefusalTests` | 6 |
| `test_product_rebase.RebaseWriteOffTests` | 6 |
| `test_product_rebase.RebaseHistoryTests` | 5 |
| `test_product_rebase.MissingResolutionTests` | 3 |
| `test_product_rebase.SwitchThenReplayTests` | 4 |
| `test_product_rebase.RebaseEndpointTests` | 8 |
| `test_platform_lifecycle` (10 classes) | 53 |
| `test_rd_costs.AuthoritativePriceTests` | 15 |
| `test_decision_limits` (4 classes) | 17 |
| `test_product_name_uniqueness.ProductNameUniquenessTests` | 10 |
| `test_manifest_determinism` (6 classes) | 52 |
| **Total** | **179** |

179 distinct, 179 executed — no test-class inheritance inflation. `OK`, exit 0.

`makemigrations --check --dry-run` → `No changes detected`.

**Provenance.** The transcript was generated to a path outside the repository
and moved in afterwards, so writing it could not dirty the tree it reports. It
records `backend/` clean at both ends. One file outside the audited scope is
modified in the working tree — `frontend/deploy-frontend.sh`, an operator change
moving Cloudflare credentials into a config file — and is named in the
transcript header rather than silently included; it is not part of this
checkpoint and is not committed here.

---

## 5. What this checkpoint does not claim

- **Stage 3 is not closed.** Stage 3B (freezing ready platforms and removing
  the old feature-upgrade path) has not started. The old upgrade path remains
  reachable, as required while re-basing was built alongside it.
- V2-039, V2-040, V2-044, V2-045, V2-046 and V2-047 remain *implemented,
  pending integrated Stage 3/4 closure*. None is closed.
- No full suite, browser, concurrency, load or tournament run.
- Unordered iteration remains in `core/services` modules **outside** the
  resolution set (grading, gamification, strategic tools, the legacy round
  engine and scoring). None is reached from `advance_round` — verified from the
  engine's imports, not by grep, after a grep on `grading` produced a hit that
  turned out to be a comment. The two audit-service instances build dicts keyed
  by primary key and are order-independent; the chain walk itself is
  `.order_by('seq')`. Their behaviour on non-resolution surfaces is unassessed.
- **V2-048 (P0, committed database credential) is open and unrepaired**, owned
  by security/operations. Integrated release approval is blocked on it
  independently of Stage 4.
