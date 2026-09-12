# Legacy simulation-control surface — inventory

**Handoff:** bounded removal of the second (legacy) simulation engine.
**Date:** 2026-09-12. **Base:** `e1b744c` (`crv2-release-integration`).
**Branch:** `crv2-remove-legacy-simulation-control`.
**Status:** inventory only. Written and committed **before** any deletion, per
`handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md` Phase 1.

## Method

Built from the authoritative registries, not from grep alone:

* the URL conf `backend/core/urls.py` and the DRF `DefaultRouter` registered at
  `core/urls.py:133-201`, walked the way `core/services/route_inventory.py:93`
  walks it (`_walk(get_resolver())`);
* the Django model registry, `django.apps.apps.get_models()`, mapped
  `db_table → model`;
* `django.contrib.admin.site._registry` enumerated at runtime (72 registrations);
* import edges resolved per symbol, then confirmed by reading each call site.

Grep was used only to *confirm* the absence of edges the registries had already
bounded.

---

## 1. The two entry points

| # | Route | Registered at | View | Methods | Permission | Engine called |
|---|---|---|---|---|---|---|
| E1 | `POST /api/simulation-control/` | `core/urls.py:262` | `SimulationControlView` — `core/views/course.py:666` | `post` | `[IsInstructor]` (`course.py:676`) | `core.services.round_engine.advance_round` (`course.py:786`) |
| E2 | `POST /api/simulation-state/<pk>/advance/` | router, `core/urls.py:143` | `SimulationStateViewSet.advance` — `core/views/core.py:135-147` | `post` | `[IsInstructor]` (`core.py:135`) | `core.services.round_engine.advance_round` (`core.py:138`) |

E2 registers **two** URL patterns — with and without the DRF format suffix — so
the route inventory carries three rows for the two entry points.

Neither reaches the competition engine `core/engine/advance_round.py`. That
module's own entry points are `close_round` (`:98`), `process_round` (`:178`),
`advance_to_next_round` (`:285`) and `advance_round` (`:335`); the name collision
on `advance_round` is the root of the detector defect in §5.

E1 dispatches five actions (`course.py:696-712`): `_start` (`:716`), `_advance`
(`:767`), `_pause` (`:815`), `_resume` (`:838`), `_reset` (`:860-1026`).

---

## 2. Every artefact reachable only through the legacy surface

For each: is it referenced by any live path — competition engine, instructor UI,
tests, admin, migrations?

| Artefact | Location | Referenced by a live path? |
|---|---|---|
| `simulation-control/` path | `core/urls.py:262` | **No.** Sole definition. |
| `SimulationControlView` name import | `core/urls.py:122`, `core/views/__init__.py:51` | **No** — both imports exist only to register E1. |
| `SimulationControlView` class | `core/views/course.py:666-1026` | **No.** No test, command, or other view names it. |
| `SimulationStateViewSet.advance` | `core/views/core.py:135-147` | **No.** |
| `SimulationStateViewSet` (the class) | `core/views/core.py:131` | **YES — retained.** Read-only list/retrieve; `SimulationState` is read by `core/views/mixins.py:29,33` and 10 further live sites. Only the `advance` action is legacy. |
| `SimulationStateSerializer` | `core/serializers` via `core/views/core.py:15-20` | **YES — retained.** Serves the retained read-only viewset. |
| `core/services/round_engine.py` | whole module (826 lines) | **No.** Sole importers are `course.py:786` and `core.py:138` — both removed here. |
| `controlSimulation` | `frontend/globalstrat-frontend/src/api/instructor.js:88-89` | **No.** Zero importers anywhere in `frontend/` (excluding `node_modules`). |

**Negative evidence, stated explicitly.**

* **Tests:** no file under `backend/core/tests/` mentions `round_engine`,
  `simulation-control`, `simulation_control` or `SimulationControl`; none
  mentions `simulation-state`.
* **Management commands:** no command imports `core.services.round_engine`.
  `core/management/commands/advance_round.py:44` imports the *competition*
  engine (`from core.engine.advance_round import advance_round`), as do 9 other
  commands.
* **Migrations:** `0046`, `0047` and `0048` name `round_engine.py` only inside
  explanatory docstrings (`0047_…:9`, `0046_…:16`) — prose, not import edges.
* **`core/services/budget.py:54`** names `round_engine._calculate_program_costs`
  in a comment only.
* **Admin:** none of the 29 legacy models checked is registered.
  `admin.site._registry` holds 72 entries; `SimulationState`,
  `SimulationInstance`, `Score`, `LeaderboardScore`, `TeamPerformance`,
  `Program`, `Message`, `TeamIncomeStatement`, `TeamGrade` and the rest are all
  **absent**. The admin is not a reference path for this surface.

---

## 3. What becomes dead code once E1 and E2 go

### 3.1 Provably dead — removed in this handoff

| Artefact | Proof |
|---|---|
| `core/services/round_engine.py` | Its only two importers are the two deleted entry points. After removal the module has **zero** importers in `backend/`. |

### 3.2 Orphaned, but living inside modules that stay live — RETAINED and reported

These functions lose their only caller when `round_engine.py` goes. Each lives
in a module that a live path still imports for *other* symbols, so deleting the
module is wrong and deleting individual functions is out of this handoff's
bounded scope. **All retained.**

| Orphaned function | Sole caller (removed) | What keeps its module live |
|---|---|---|
| `process_gamification` — `core/services/gamification_engine.py:264` | `round_engine.py:779` | `calculate_qicoin` → `core/views/gamification.py:13` |
| `generate_persona_reactions` — `core/services/persona_engine.py:977` | `round_engine.py:795` | `reply_to_thread`, `start_consultation`, `get_consultation_usage`, `PERSONAS` → `core/views/persona_engine.py:15` |
| `process_r_and_d_development` — `core/services/r_and_d.py:108`; `create_system_message` — `r_and_d.py:195` | `round_engine.py:285-288` | `apply_development_time` → `core/views/programs.py:70`; `accelerate_development` → `core/views/programs.py:107` |

### 3.3 Ambiguous — RETAINED, flagged for a separate decision

**`core/services/scoring.py`** (12 functions). After this removal it has **no
importer anywhere in `backend/`**: the only external importer was
`round_engine.py:21-27`. By the same test applied to `round_engine.py` it is
dead. It is retained anyway because:

* it is not named in this handoff's scope;
* `calculate_alignment` (`scoring.py:84`) is still called *within* the module at
  `scoring.py:179`, so the module is not internally inert;
* several of its functions (`calculate_sdg_coverage:312`,
  `check_framework_compliance:413`, `get_supplier_modifiers:465`) are named in
  commented-out engine blocks, i.e. they are parked work, not obviously refuse.

This is the strongest follow-up candidate. Recorded, not acted on — a live
reference I did not find is worse than a file left behind.

### 3.4 Confirmed live — untouched

| Module | Kept alive by |
|---|---|
| `core/services/event_engine.py` (`fire_events:22`) | `core/views/events.py:56,58` |
| `core/services/budget.py` | `core/services/r_and_d.py:146`; `core/views/programs.py:61,91,124` |
| `core/engine/*` (the competition engine) | 10 management commands, `core/views/round_control.py`, `core/views/results_api.py`, the test suite |

---

## 4. Legacy MODELS the reset writes

**No model, table or migration is changed by this handoff.** Deleting data
structures is a separate, migration-bearing decision. This section records the
finding only.

`_reset` (`course.py:860-1026`) executes raw SQL over `FULL_TRUNCATE_TABLES` and
`CONDITIONAL_DELETE_TABLES`, imported from
`core/management/commands/reset_simulation.py:17,96`. Scoping, as written:

* `TRUNCATE TABLE "<t>" CASCADE` — **no `WHERE` at all** (`course.py:916-921`);
* `DELETE FROM programs WHERE round_launched != 11` (`:887`) — no instance scope;
* `DELETE FROM messages WHERE instance_id IS NOT NULL` (`:926`) — every instance;
* `UPDATE team_performance SET …` (`:934-940`), `UPDATE simulation_state SET …`
  (`:946-949`), `UPDATE rounds …` (`:966-980`), `UPDATE challenges …` (`:986-990`),
  `UPDATE competitors …` (`:1004-1009`) — **no `WHERE instance_id`**;
* only `UPDATE simulation_instance … WHERE instance_id = %s` (`:955-959`) is scoped.

Every failure is swallowed by `except Exception: connection.ensure_connection()`,
so a reset that half-succeeds reports success.

### Per-model disposition

| Table targeted | Django model | Competition engine (`core/engine/`) | Live views | Note |
|---|---|---|---|---|
| `team_notifications` | `TeamNotification` (`messaging.py:79`) | **WRITES** — `core/engine/utils.py:352-353` | `views/messaging.py:78` | **The one real collision.** A `TRUNCATE` target the competition engine writes. |
| `programs` | `Program` (`programs.py:43`) | no | 7 sites incl. `views/core.py:242`, `views/course.py:1160,1199` | live-serving |
| `messages` | `Message` (`messaging.py:27`) | no | 5 sites incl. `views/messaging.py:15` | live-serving |
| `scores` | `Score` (`scoring.py:30`) | **no** | `views/core.py:227`, `views/scoring.py:20` | All 14 `Score` hits in `core/engine/` are prose in comments/docstrings ("Score the strategy…"), **not** the model. |
| `leaderboard_scores` | `LeaderboardScore` (`scoring.py:60`) | no | `views/scoring.py:38` | live-serving |
| `team_performance` | `TeamPerformance` (`scoring.py:77`) | no | `views/core.py:262`, `views/scoring.py:55` | live-serving |
| `team_income_statements` | `TeamIncomeStatement` (`financials.py:17`) | no | `views/financials.py:17`, `views/core.py:211` | live-serving |
| `team_balance_sheets` / `team_cash_flows` | `TeamBalanceSheet` / `TeamCashFlow` | no | `views/financials.py:32,47` | live-serving |
| `financial_expenses` | `FinancialExpense` (`financials.py:107`) | **imported but never queried** — `core/engine/preference_engine.py:22` is an unused import; no `FinancialExpense.objects` anywhere in `core/engine/` | `views/financials.py:95` | engine does **not** read it |
| `financial_revenue`, `new_sales_by_round` | `FinancialRevenue`, `NewSalesByRound` | no | `views/financials.py` | live-serving |
| `simulation_state` | `SimulationState` (`core.py:213`) | no | 12 sites incl. `views/mixins.py:29,33`, `views/core.py:132` | live-serving; retained viewset reads it |
| `decisions` | `Decision` (`programs.py:95`) | no | `views/programs.py:180` | **Not** the competition decision store — see below |
| `triggered_events` | `TriggeredEvent` | no | `views/events.py:16` | live-serving |
| `player_progress`, `team_achievements`, `team_badges` | gamification models | no | `views/gamification.py:28,43,58` | live-serving |
| `notification_logs` | `NotificationLog` | no | `views/messaging.py:93` | live-serving |
| `team_grade`, `student_grade_adjustment` | `TeamGrade`, `StudentGradeAdjustment` | no | `views/grading.py:75,89,276` | live-serving |
| `rounds`, `challenges`, `competitors`, `esg_scorecards`, `newsfeeds`, `news_feed`, `news_decisions`, `news_responses`, `chat_messages`, `simulation_logs`, `ethical_*`, `bcorp_certifications`, `team_framework_*`, `team_sdg_coverage`, `team_scope_scores`, `program_supplier`, `post_round_*`, `pestle_analysis`, `tbl_assessment`, `risk_analysis`, `tool_usage_logs`, `team_trend_analysis`, `team_program_initiatives`, `challenge_*` | **no Django model** | — | — | Ghost tables in the sense of `specs/STANDING-DISCIPLINE.md` §1.8: named in SQL, absent from the model registry. |

**Two scoping facts worth stating plainly.**

1. **The competition decision store is not a reset target.** `DecisionSubmission`
   is `db_table = 'decision_submission'` (`core/models/decisions.py:37`), and
   neither it nor any `decision_*` table appears in `FULL_TRUNCATE_TABLES` or
   `CONDITIONAL_DELETE_TABLES`. The `decisions` table the reset truncates is the
   *legacy* `Decision` model (`core/models/programs.py:95`).
2. **The reset's round rewrite does not touch competition rounds.** `Round` is
   `db_table = 'round'` (singular — `core/models/core.py:168`). `_reset` issues
   `UPDATE rounds …` (`course.py:966`), a table with no Django model. Whatever
   `rounds` is, it is not the competition round table; and if it does not exist,
   the failure is swallowed at `:981`.

So the reset's blast radius is: **live instructor-facing read surfaces**
(grading, gamification, scoring, financials, messaging, programs), **one table
the competition engine writes** (`team_notifications`), and a long tail of
ghost tables — across **every instance on the deployment**, not the one named.

---

## 5. The detector that certified this route as guarded

`core/services/route_inventory.py:125-126`:

```python
def uses_boundary(source):
    return any(marker in source for marker in _BOUNDARY_MARKERS)
```

`_BOUNDARY_MARKERS` (`:61-67`) contains `'advance_round('`. `_view_source`
(`:101`) returns the view class's source, in which `SimulationControlView._advance`
contains `from core.services.round_engine import advance_round` (`course.py:786`)
and `advance_round(state.state_id)` (`:788`). The substring matches, so the route
was recorded `uses_boundary: true` and excluded from `unguarded_routes()`
(`:160-165`) — even though the symbol resolves to the legacy engine.

Checked-in inventory at `e1b744c` (`core/services/route_inventory.json`):
220 mutating routes, 36 lifecycle-mutating, 20 guarded, 16 exempt, **0 unguarded**.
`api/simulation-control/|post` is recorded `lifecycle_mutating: true`,
`uses_boundary: true` (`route_inventory.json:2482-2490`).

**Measured counterfactual.** A resolver that binds each marker to the symbol
actually imported was run against the unmodified tree at `e1b744c`. Exactly
three route rows change `uses_boundary` `true → false`, and all three are this
legacy surface:

| Route | View | `lifecycle_mutating` | Newly unguarded |
|---|---|---|---|
| `api/simulation-control/` | `SimulationControlView` | true | **YES** |
| `api/^simulation-state/<pk>/advance/$` | `SimulationStateViewSet` | false | no |
| `api/^simulation-state/<pk>/advance.<format>$` | `SimulationStateViewSet` | false | no |

In all three the marker `advance_round` resolves to `core.services.round_engine`,
which is not a boundary module.

**No other route's guarded status changes.** The certified "0 unguarded mutating
routes" rested on exactly one false positive, and that false positive is this
route. No other route on the certified gate was guarded by a substring accident.

---

## 6. A fourth defect, found while reading

`round_engine.advance_round` references the name `stakeholders` at
`round_engine.py:550` (`for s in stakeholders:`) and `:567`
(`stakeholders.count()`). **The name is never assigned.** The only nearby
binding, the stakeholder query, was removed when the `Segment` model was retired
— `round_engine.py:300-304` now defines only `teams` and an empty
`adoption_results`.

The reference sits inside `for team in teams:` (`:341`), so with any non-empty
`Team` set the function raises `NameError`. Both entry points convert that to a
400 (`course.py:789-793`, `core.py:143-147`).

So the legacy `advance` action cannot have completed a round for any populated
game since the `Segment` retirement. This strengthens the removal: E1's
`advance` and E2 were already non-functional, while `start`, `pause`, `resume`
and — critically — `reset` still executed.

---

## 7. Disposition

| Artefact | Action |
|---|---|
| `core/urls.py:262` path, `:122` import | **Delete** |
| `core/views/__init__.py:51` export | **Delete** |
| `SimulationControlView` (`course.py:662-1026`) | **Delete** |
| `SimulationStateViewSet.advance` (`core.py:135-147`) | **Delete** |
| `core/services/round_engine.py` | **Delete** — zero importers after the above |
| `controlSimulation` (`instructor.js:87-89`) | **Delete** |
| `uses_boundary` substring matching (`route_inventory.py:125`) | **Repair** — resolve markers to imported symbols |
| `SimulationStateViewSet` class + serializer | **Retain** — live read surface |
| `gamification_engine` / `persona_engine` / `r_and_d` orphaned functions | **Retain** — modules live for other symbols |
| `core/services/scoring.py` | **Retain** — ambiguous, flagged (§3.3) |
| `reset_simulation` management command | **Retain** — separate CLI entry point, not part of the routed surface; its unscoped SQL is recorded as a finding |
| All models, tables, migrations | **Unchanged** |
