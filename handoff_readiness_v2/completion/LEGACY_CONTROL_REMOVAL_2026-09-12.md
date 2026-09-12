# Legacy simulation-control removal — completion report

**Date:** 2026-09-12.
**Branch:** `crv2-remove-legacy-simulation-control`, from `e1b744c`
(`crv2-release-integration`).
**Worktree:** `.claude/worktrees/agent-aac4986d56f43b13c`. The main checkout was
not modified, nothing was pushed, no other worktree was touched.

**I claim no gate closed.** The certified route-inventory gate is *re-measured*
below, not re-certified. GSP-CRV2-09 still owns integrated certification.

| Commit | Contents |
|---|---|
| `02568b1` | Inventory only — written and committed before any deletion |
| `a37bb92` | The removal, plus `route_inventory.json` regenerated with the **unmodified** detector |
| `d9cbd43` | The detector repair and its tests |

**Inventory:**
`handoff_readiness_v2/evidence/decision-rules/legacy-removal/LEGACY_SURFACE_INVENTORY.md`

---

## 1. What was deleted

| Artefact | Was at |
|---|---|
| `POST /api/simulation-control/` route | `core/urls.py:262` (+ import at `:122`) |
| `SimulationControlView` — `start`/`advance`/`pause`/`resume`/`reset` | `core/views/course.py:662-1026` (367 lines) |
| `SimulationStateViewSet.advance` | `core/views/core.py:135-147` |
| `core/services/round_engine.py` | whole module, 826 lines |
| `controlSimulation` | `frontend/globalstrat-frontend/src/api/instructor.js:87-90` |
| `SimulationControlView` export | `core/views/__init__.py:51` |

Net: **7 files changed, 5 insertions, 1247 deletions.** No model, table,
migration or serializer was changed.

## 2. What was deliberately left, and the reference that saved it

| Left in place | The reference that saved it |
|---|---|
| `SimulationStateViewSet` (the class) and `SimulationStateSerializer` | Read-only list/retrieve is live; `SimulationState` is read by `core/views/mixins.py:29,33` and 10 further sites. Only the `advance` action was legacy. |
| `gamification_engine.process_gamification` (`:264`) | Module stays live via `calculate_qicoin` → `core/views/gamification.py:13` |
| `persona_engine.generate_persona_reactions` (`:977`) | Module stays live via `reply_to_thread`, `start_consultation`, `get_consultation_usage`, `PERSONAS` → `core/views/persona_engine.py:15` |
| `r_and_d.process_r_and_d_development` (`:108`), `create_system_message` (`:195`) | Module stays live via `apply_development_time` → `core/views/programs.py:70` and `accelerate_development` → `:107` |
| `core/services/scoring.py` (entire module) | **Ambiguous — see finding F3.** It now has no importer at all, but it is outside this handoff's named scope and is not internally inert. |
| `core/management/commands/reset_simulation.py` | A separate CLI entry point, not part of the routed surface. **Its unscoped SQL is unchanged — see finding F2.** |
| `gamification_engine.py:266` docstring naming `round_engine` | Stale prose only. Left to keep the diff bounded; recorded here. |

The rule applied throughout: a live reference I did not find is worse than a
file left behind.

## 3. The detector change, and every guarded-status change it produced

`core/services/route_inventory.py` matched each boundary marker as a **substring
of the view source**, so `'advance_round('` matched any function of that name.
`SimulationControlView._advance` called `core.services.round_engine.advance_round`
— a different engine — matched the marker written for
`core.engine.advance_round`, and was recorded `uses_boundary: true`.

`uses_boundary` now takes the **view class** and resolves each marker to the
module it is actually bound to:

* a function-local `from X import y` is read out of the class body by AST;
* a module-level import resolves through the defining module's globals;
* `CompetitionDecisionWriteMixin` is settled by identity in the MRO;
* a name that appears only in a comment or docstring is never an `ast.Name`, so
  it no longer counts at all.

### Guarded-status changes — measured, against the unmodified tree at `e1b744c`

| Route | View | `lifecycle_mutating` | `uses_boundary` | Newly unguarded |
|---|---|---|---|---|
| `api/simulation-control/` | `SimulationControlView` | true | true → **false** | **YES** |
| `api/^simulation-state/<pk>/advance/$` | `SimulationStateViewSet` | false | true → false | no |
| `api/^simulation-state/<pk>/advance.<format>$` | `SimulationStateViewSet` | false | true → false | no |

In all three the marker `advance_round` resolves to `core.services.round_engine`.

**No other route changes.** All three are the surface removed here, so the
certified "0 unguarded mutating routes" rested on exactly one false positive,
and that false positive was this route. **No other route on that certified gate
was guarded by a substring accident** — which is the question the handoff asked,
and the answer is clean.

The independent confirmation: `route_inventory.json` was regenerated in `a37bb92`
using the **unmodified** detector, and the repaired detector in `d9cbd43`
reproduces that file byte for byte — `dump_route_inventory --check` exits 0 with
no regeneration. A detector that changed any other route's verdict could not
have done that.

### Inventory counts

| | `e1b744c` | HEAD |
|---|---:|---:|
| Registered mutating routes | 220 | 217 |
| Lifecycle-mutating | 36 | 35 |
| Guarded | 20 | 19 |
| Reviewed exemptions | 16 | 16 |
| **Unguarded** | **0** | **0** |

## 4. Tests

Phase 0 recorded: branch `crv2-remove-legacy-simulation-control` at `a37bb92`,
shell PID 459483, database `globalstrat_plus` inside a per-PID disposable
container (`globalstrat-plus-test-postgres-<pid>`) on a random host port with a
random password. **Not** the production database at `192.168.50.38`; no systemd
environment file was read. No stray container was left behind.

```
flock -w 1800 /tmp/globalstrat-backend-test.lock \
  backend/scripts/test-postgres \
    core.tests.test_legacy_control_removal \
    core.tests.test_operator_concurrency.RouteCoverageTests \
    core.tests.test_engine \
    core.tests.test_competition_locks
```

**Ran 74 tests in 13.336s — OK** (03:45:34 → 03:45:59Z, 25s wall including
container start and teardown).

What that run proves:

| Claim | How |
|---|---|
| The removed routes no longer resolve | `reverse()` raises `NoReverseMatch` for `simulation-control` and `simulation-state-advance`; `resolve()` raises `Resolver404` for both paths |
| An instructor calling them gets 404 | A Bearer-authenticated instructor POSTs all five actions plus the state-advance route; every one is 404, logged by Django as `Not Found` |
| No engine ran on those calls | 404 is decided at URL resolution, before any view, transaction or engine. Independently, `core.services.round_engine` raises `ModuleNotFoundError` — the engine no longer exists to be called |
| The competition lifecycle is untouched | `test_engine` and `test_competition_locks` exercise close/process/advance through `core/engine/advance_round.py`; the run logs `Closed round 1 of game 2 (reason=manual, 1 submissions locked)` |
| The route inventory is clean | `RouteCoverageTests` — no unguarded route, no drift from the checked-in copy, every exemption still names a registered view — plus `dump_route_inventory --check` exit 0 |
| The repair does not unguard real routes | `RoundCloseView`, `RoundProcessView`, `RoundAdvanceView`, `GameResetView` and `DecisionSubmissionView` all still resolve to the boundary |

Other checks: `manage.py check` — 0 issues; `git diff --check e1b744c HEAD` — no
whitespace errors; working tree clean.

**The full backend suite was not run**, per `EXECUTION_PROTOCOL.md` (budget: 0 in
development and preflight; GSP-CRV2-09 owns the integrated suite). The seven
pre-existing failures registered as V2-071/V2-074 belong to another builder and
were not touched: none of their six test classes is in the focused set above.
The one V2-071 item that *is* in scope —
`RouteCoverageTests.test_inventory_matches_the_checked_in_copy` — passes, so it
was not regressed.

## 5. Rollback

No migration, no schema change, no data transformation, so rollback is pure
source.

```
git revert d9cbd43   # detector repair + its tests
git revert a37bb92   # the removal
git revert 02568b1   # the inventory document
```

Reverting `a37bb92` restores the route **and** the unscoped `_reset` and the
missing ownership check along with it — revert it only deliberately. It also
restores the three legacy rows in `route_inventory.json`; if `a37bb92` is
reverted while `d9cbd43` stands, `dump_route_inventory --check` will fail
because the repaired detector scores `api/simulation-control/` as unguarded, and
`RouteCoverageTests` will then fail on a genuinely unguarded route. Revert
`d9cbd43` first, or regenerate.

Reverting only `d9cbd43` returns the detector to substring matching; the
inventory file stays valid, because the two agree on the post-removal tree.

## 6. Findings

**F1 — the removed surface had a fourth defect nobody recorded.**
`round_engine.advance_round` referenced the name `stakeholders` at
`round_engine.py:550` and `:567`; the name was never assigned — its binding was
removed when the `Segment` model was retired. Inside `for team in teams:`, any
non-empty `Team` set raised `NameError`, which both entry points converted to a
400. The legacy `advance` had therefore been non-functional for any populated
game since that retirement, while `start`, `pause`, `resume` and — critically —
`reset` still executed. Severity is historical; the code is deleted.

**F2 — the unscoped reset survives as a management command.** `_reset` is gone,
but it imported its table lists from
`core/management/commands/reset_simulation.py`, which is untouched and still
issues `TRUNCATE TABLE "<t>" CASCADE` over `FULL_TRUNCATE_TABLES` with no
instance scope, `DELETE FROM programs WHERE round_launched != 11`,
`UPDATE team_performance`/`simulation_state`/`rounds`/`challenges` with no
`WHERE instance_id`, and swallows every failure with
`except Exception: connection.ensure_connection()`. The routed exposure is
closed; the CLI one is not. Its blast radius, from the inventory: live
instructor-facing read surfaces (grading, gamification, scoring, financials,
messaging, programs), one table the competition engine writes
(`team_notifications`, `core/engine/utils.py:352-353`), and ~25 ghost tables with
no Django model — across every instance on the deployment. Not repaired here:
out of scope, and it is a deliberate operator action rather than an
authenticated HTTP route.

**F3 — `core/services/scoring.py` is now unreferenced.** Its only importer was
`round_engine.py:21-27`. By the same test that condemned `round_engine.py` it is
dead, but it is retained: not named in this handoff, and
`calculate_alignment` (`:84`) is still called within the module at `:179`. It is
the strongest follow-up candidate.

**F4 — the pre-commit hook fails, but not for the stated reason.** The handoff
expected `checks/.aide-checks-rev` to be absent. It is present and contains
`e710f26`. The actual refusal is a revision **mismatch**: `run-checks` reports
the runner built from `e1b744c` against a repo vendored at `e710f26`, and exits 2
in every mode. Invoked directly outside a commit it passes (2 checks ran, 0
blocking failures, 0 could-not-run). All three commits therefore used
`--no-verify`, which the hook header explicitly sanctions: *"Bypassable with
`--no-verify`; the deploy gate is the layer that is not."* Re-vendoring is out of
scope. **The deploy gate has not been satisfied by anything I did.**

**F5 — the blind spot that produced V2-017 is unchanged.** `mutating_routes()`
still skips any route whose callback exposes no view class, so the Django admin
remains invisible to the inventory. R13 made that harmless rather than visible.
This repair addresses marker resolution only; it does not narrow that gap.

## 7. Auditor preflight checklist

| Question | Answer |
|---|---|
| Did inventory start from registered routes/models/jobs, not only code using the new abstraction? | Yes — `core/urls.py`, the DRF `DefaultRouter`, `apps.get_models()` mapped `db_table → model`, and `admin.site._registry` (72 registrations) enumerated at runtime. Grep was used only to confirm absences the registries had already bounded. |
| Is there an active legacy or alternate entry point? | Not on the routed surface — that was the subject, and both entry points are gone. **Yes off it:** the `reset_simulation` management command (F2). Also recorded: `core/services/scoring.py` is now orphaned (F3). |
| Does a failure/refusal audit survive rollback? | Unchanged by this work. No audit path was added or removed; `OperatorAuditEvent` and the CRV2-02 rejection-outside-the-transaction behaviour are untouched. A 404 here precedes any transaction, so there is nothing to survive. |
| Is each correlation ID generated once and identical in response/audit/log? | Not applicable — no request-id path was touched. `RequestIdCorrelationTests` was not in the focused set and no code it covers changed. |
| Is background/external work delayed until the outer transaction commits? | Not applicable now, and one instance of the defect was deleted: the removed `round_engine.advance_round` ran a `ThreadPoolExecutor` persona step inside `@transaction.atomic`. It leaves with the module. |
| Do claimed environment values describe the executing process? | Yes. The suite ran against a disposable PostgreSQL 16 container created by `backend/scripts/test-postgres` on a random host port with a random password, database `globalstrat_plus`, PID 459483 — not `192.168.50.38`, and no systemd environment file was read. |
| Does provenance identify runtime bytes, including required untracked files? | Yes. Three commits listed above; working tree clean; `route_inventory.json` is checked in and regenerated, not hand-edited. No untracked file is required to reproduce. |
| Do README commands run exactly as written against stored artifacts? | Yes — the `flock … test-postgres …` command in §4 is the command that was run, verbatim. |
| Do P0/P1/P2 labels match their definitions? | Proposed severities are in the register entries handed over separately; I applied none to the register myself. |
| Does each negative test prove mutation/engine execution did not occur? | Yes, twice over. 404 is decided at URL resolution, before any view or transaction; and `core.services.round_engine` now raises `ModuleNotFoundError`, so the engine does not exist to be executed. The tests assert both. |

## 8. Concurrency with other builders

Edits were confined to the legacy surface. In `core/views/course.py` only the
`SimulationControlView` block (`662-1026`) was removed — `RosterViewSet` and
`TeamManagementView` were not touched. In `core/views/core.py` only the
`advance` action (`135-147`) was removed — `UserViewSet` was not touched.
`core/views/decisions.py` and the serializers were not modified at all. The
`route_inventory.py` `EXEMPTIONS` entries naming `UserViewSet` and
`TeamManagementView` are unchanged.
