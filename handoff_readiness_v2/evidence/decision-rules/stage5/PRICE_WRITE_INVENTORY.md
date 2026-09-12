# GSP-CRV2-10 Stage 5 — price write/display inventory

**Finding:** V2-041 (P1) — no price band
**Baseline:** `cbe2656` (branch `crv2-10-stage5-price-band`, detached from `cbe2656`)
**Phase:** EXECUTION_PROTOCOL Phase 1. Produced **before** any runtime edit.
**Method:** built from the authoritative registries — `core/urls.py` (the
`urlpatterns` list and the `DefaultRouter` registrations) and the Django model
registry — then narrowed by field, not by grepping for what looked relevant.
No row below was added because it "seemed related"; every row is a registered
route, a registered model, or a named engine entry point.

---

## 0. Where a retail price physically lives

The model registry has exactly **two** fields that store a product's retail
price. Everything else in the codebase that mentions `retail_price` is a read,
a serializer field, a dict key or a local variable.

| Model | Field | File:line | Role |
|---|---|---|---|
| `core.DecisionMarketing` | `retail_price` `DecimalField(15,2)`, **nullable since migration `0085`** | `core/models/decisions.py:193` | **The decision.** Keyed `unique_together (submission, team_product, market)`. This is the band's subject. Nullable so that "submitted with the price left out" is representable at all — see the rework note below. |
| `core.RoundResultProductMarket` | `retail_price` `DecimalField(15,2)` | `core/models/results_financials.py:19` | **The published result.** Keyed `(game, round_number, team, team_product, market)`. This is the band's *anchor source*, read-only to the band. |

Consequence, and it decides the shape of the rule: both tables are keyed
**per product-market**, not per product. See the rules-owner question in §6.

### Rework note (owner's clarification of Ruling 2, 2026-09-12)

This inventory was written before the blank branch was narrowed. Two things
changed about the rows below; nothing changed about which rows exist.

1. **W3, the deadline, no longer creates rows.** An earlier implementation
   fabricated a floor-priced `DecisionMarketing` row for any active
   product-market that had none. That is now refused by the rule itself:
   "blank" means a product the team **is selling** — one with a real
   prior-round price — and a product-market the team never marketed is
   absence, not a blank price. `bass_engine` scores a product with no row at
   `0.0` attractiveness, so inventing one would have taken share from every
   rival and booked it all as lost demand. W3 therefore **updates existing
   rows only** and never inserts.
2. **A new refusal point, which is not a write path.** `_run_phase_1` gains a
   fail-closed precondition refusing the round if any stored marketing row
   still carries no price when processing begins. It sets no price and writes
   no row, so it adds no row to §1; it is recorded here because it is the
   boundary that keeps a null out of the demand path, which calls `float()` on
   this column.

---

## 1. Write paths that can set a product's retail price

Enumerated from `core/urls.py`. Every registered route whose view source can
write `DecisionMarketing`, plus the engine entry points that can.

| # | Registered route / entry point | View / function | Disposition |
|---|---|---|---|
| W1 | `decision-submission` — `POST`/`PUT /api/games/<game_id>/teams/<team_id>/decisions/round/<round_number>/` | `DecisionSubmissionView._upsert` (`views/decisions.py:364`) → `DecisionSubmissionSerializer` nested `marketing_decisions` | **CHANGED** — alert while the round is open; submission accepted, team's number kept |
| W2 | `decision-partial` — `PATCH .../<decision_type>/` with `decision_type='marketing'` | `DecisionPartialUpdateView.patch` (`views/decisions.py:462`), `_TYPE_MAP['marketing']` (`:442`) → `model_cls.objects.filter(...).delete()` + `bulk_create` (`:547`,`:550`) | **CHANGED** — same serializer, therefore the same alert, by construction |
| W3 | `round-control-close` — `POST /api/games/<game_id>/round-control/close/` | `RoundCloseView` (`views/round_control.py:169`) → `close_round` (`engine/advance_round.py:98`) → `_lock_all_submissions` (`:146`) | **CHANGED** — this is the deadline. Auto-adjustment belongs here |
| W4 | Deadline scheduler (not an HTTP route) | `check_round_deadlines` (`management/commands/check_round_deadlines.py:98`) → the **same** `close_round` | **COVERED by W3** — one function, so cron and operator close cannot diverge |
| W5 | `product-rebase` — `POST .../products/<product_id>/rebase/` | `ProductRebaseView` (`views/decisions.py:588`) | **EXEMPT** — changes a product's platform association only. Testable rationale: `retail_price` does not appear in `product_rebase.py` or in the view |
| W6 | Django admin `DecisionMarketing` | `DecisionMarketingAdmin(CompetitionReadOnlyAdmin)` (`admin.py:548`) | **EXEMPT** — `has_add_permission`/`has_change_permission`/`has_delete_permission` all return `False` (`admin.py:112-119`). Read surface only |
| W7 | `sc-sourcing`, `sc-logistics`, `sc-trade-finance`, `sc-inventory` | `views/sc_views.py` | **EXEMPT** — no retail-price field on any supply-chain decision model. Testable rationale: `retail_price` does not occur in `core/views/sc_views.py` |
| W8 | Seed/dev management commands: `load_demo`, `run_integration_test`, `run_cc31d_test`, `run_cc31f_test`, `run_cc31i_test`, `run_cc32d_test` | direct `DecisionMarketing.objects.create/update_or_create` | **EXEMPT** — not registered routes and not reachable over HTTP; fixture builders for dev/demo. They bypass the serializer today and will continue to |
| W9 | `engine/bootstrap.py:139` — `bootstrap_round_zero` | writes `RoundResultProductMarket.retail_price` from `FirmStarterProduct.base_price` | **COVERED, unchanged** — it *creates the round-1 anchor*. Read by the calculator, never written by it (see §4) |
| W10 | `engine/revenue.py:123,162` — `calculate_revenue` | writes `RoundResultProductMarket.retail_price` from `DecisionMarketing.retail_price` | **COVERED, unchanged** — downstream of the adjusted decision. This is what makes the *applied* price the price that scores and the price that anchors next round |

**No other write path exists.** The sweep for
`DecisionMarketing.objects.create|bulk_create|update`, `marketing_decisions.create`
and `retail_price=` across non-test code returns only W8 and the generic
`model_cls` writes of W2.

### The lock-state trap this inventory exposes

`_lock_all_submissions` (`advance_round.py:146`) iterates active teams and
`continue`s on a submission that is **already locked**. A team that locks its
own submission early (`decision-lock` → `DecisionLockView`) with an out-of-band
price would therefore be skipped by anything written inside that loop's
branches. The adjustment pass must run over **every active team's submission
for the round regardless of lock state**, not inside the lock bookkeeping.
Recorded here because it is the defect this inventory exists to prevent.

---

## 2. Surfaces that display a product's retail price

| # | Registered route | View | Disposition |
|---|---|---|---|
| D1 | `context-marketing` — `GET .../context/marketing/` | `MarketingContextView` (`views/decisions.py:1859`); `prev_round_decisions[].retail_price` (`:2011`) | **CHANGED** — the pricing surface. Gains the legal range from the one calculator |
| D2 | `context-products` — `GET .../context/products/` | `ProductContextView` (`views/decisions.py:1752`); `products[].retail_prices` (`:1832`) | **COVERED** — display of the stored decision. The band is stated on the pricing surface (D1), not duplicated here |
| D3 | `round-results` — `GET .../results/round/<round_number>/` | `RoundResultsView` (`views/results_api.py:85`); `products[].retail_price` (`:197`) | **CHANGED** — the adjustment must be visible to the team here (ruling) |
| D4 | `competitor-intel` — `GET .../competitors/round/<n>/` | `CompetitorIntelView`; price ranges (`results_api.py:405`), market report `price` (`:498`) | **EXEMPT** — rival-facing aggregates of already-published results. R8's precedent: a team's own adjustment is not volunteered to rivals |
| D5 | `instructor-team-decisions` — `GET .../instructor/teams/<team_id>/decisions/` | `InstructorTeamDecisionsView` (`results_api.py:1061`); `marketing[].retail_price` (`:1156`), `audit_events` (`:1114`) | **COVERED, no change needed** — already maps `user=None` → `actor: 'system'` (`:1117-1118`). The adjustment event appears in the CRV2-08 drill-down by construction |
| D6 | `financial-reports-history` | `FinancialReportsHistoryView` (`cc15_views.py:309`, price at `:380`) | **EXEMPT** — published results history |
| D7 | `forecast` | `ForecastView` (`cc15_views.py:443`, price at `:472`) | **EXEMPT** — projects revenue from whatever the team currently has stored; reads the adjusted value automatically after close |
| D8 | Frontend `MarketingPage.js` (price input `:266`, last-round hint `:270`) | — | **CHANGED** — the alert must reach the student here |
| D9 | Frontend `ResultsPage.js` (product table `:270`) | — | **CHANGED** — the adjustment must show here |
| D10 | Frontend `ProductsPage.js` (`:222`), `FinancialReportsPage.js` (`:302`), `InstructorDashboard.js` | — | **EXEMPT** — render stored/published values; no rule is stated on these screens |

---

## 3. Where the deadline/lock path runs

| Step | Location | Note |
|---|---|---|
| Operator close | `RoundCloseView` (`views/round_control.py:169`) | takes `operator_action` |
| Scheduled close | `check_round_deadlines` (`:98`) | same `close_round`; races are a no-op by `changed=False` |
| **The deadline action** | `close_round` (`engine/advance_round.py:98`), `@transaction.atomic`, holds `lock_game_for_lifecycle` | sets `status='closed'`, `decisions_locked=True`, then `_lock_all_submissions` |
| Submission freeze | `_lock_all_submissions` (`:146`) | already writes a `DecisionAuditEvent` with `user=None` — the existing system-actor precedent |
| Manifest | `prepare_manifest` (`services/resolution_manifest.py:403`) called from `process_round` (`advance_round.py:220`) | **strictly after close.** An adjustment at close is recorded *as input state*; it does not rewrite a sealed manifest |

**Determinism boundary (CRV2-01):** `decision_marketing` is a manifest section
(`services/manifest_sections.py:330`, "Price, promotion, channels and
production volume"). Because the manifest is prepared during `process_round`
and the adjustment lands during `close_round`, the manifest records the
*applied* prices. Replay therefore reproduces the adjusted round. No CRV2-01
artifact is invalidated; the boundary is touched read-only.

---

## 4. The authored starting price, and why round 1 is not a special case

```
YAML starter_profiles (scenarios/*.yaml:5563)
  → load_scenario.py  → core.FirmStarterProduct.base_price  (models/scenario.py:557)
    → bootstrap_round_zero (engine/bootstrap.py:120-139)
      → RoundResultProductMarket(round_number=0, retail_price=base_price)
```

`bootstrap_round_zero` is called from `initialize_game.py:254` and
`views/scenario_views.py:465`, so every game has round-0 result rows for each
starter product in its home market.

The anchor lookup is therefore **one rule for every round**: the most recent
`RoundResultProductMarket.retail_price` for `(team, product, market)` with
`round_number < current`. In round 1 that resolves to the round-0 row, which
holds the authored `base_price`. Round 1 obeys the same code path as round 7 —
exactly the property BECSR's module docstring argues for, reached through a
table GlobalStrat already populates.

**Gap worth naming:** `TeamProduct` has no FK to `FirmStarterProduct`;
`bootstrap_round_zero` matches them by `product_name` (`bootstrap.py:116-118`),
and `initialize_game` may place the product in an assigned home market that
differs from `FirmStarterProduct.market` (`initialize_game.py:181`). Reading
the anchor from the **round-0 result row** rather than from
`FirmStarterProduct` avoids re-deriving that fragile match, and is the reason
the calculator reads results rather than scenario rows.

---

## 5. How decision audit events are written and exposed

| Concern | Fact |
|---|---|
| Model | `core.DecisionAuditEvent` (`models/competition_audit.py:27`), `db_table='competition_decision_audit_event'` |
| Immutability | re-`save()` raises (`:44-46`); `payload_sha256` auto-set via `canonical_hash`; `_schedule_seal()` chains it (CRV2-04) |
| Request-bound writer | `record_decision_event(request, game, team, round_obj, action, payload)` (`services/competition_audit.py:6`), user from `get_request_user` |
| **System-actor precedent** | `_lock_all_submissions` writes `DecisionAuditEvent.objects.create(..., user=None, action='deadline_lock'/'missing_submission_defaulted', endpoint='engine:close_round', ...)` (`advance_round.py:168-174`) |
| Exposure (CRV2-08) | `InstructorTeamDecisionsView` (`results_api.py:1113-1126`) renders `actor = 'system'` when `event.user` is null, with `action`, `server_timestamp`, `endpoint`, `request_id`, `payload_sha256`, `payload` |

So **actor `system` already means `user=None`** on the one surface that answers
dispute 2, and no new model, field or migration is required to satisfy the
audit half of the ruling.

---

## 6. The authored band parameter

Pattern in force (verified, per STANDING-DISCIPLINE §1): `core.ScenarioConfig`
`(config_key, config_value)` (`models/scenario.py:43`), read through
`core.engine.utils.get_config(scenario, key, default, cast_type)`
(`engine/utils.py:191`), authored in the YAML `config:` block as
`key: ['<value>', '<description>']` (`load_scenario.py:501-513`).

Direct precedent: R3's `platform_switch_write_off_pct` (`services/product_rebase.py:50`).

**Band key:** `price_band_pct`, default `0.30`. Authored into the `config:`
block of all three scenario YAMLs. **No migration** — `ScenarioConfig` rows are
scenario data, and an existing game without the row takes the 0.30 default.

---

## 7. Coverage summary

| Disposition | Rows |
|---|---|
| **CHANGED** | W1, W2, W3, D1, D3, D8, D9 |
| **COVERED (no edit required, proven by test)** | W4, W9, W10, D2, D5 |
| **EXEMPT (with testable rationale)** | W5, W6, W7, W8, D4, D6, D7, D10 |

Every registered route that can write or display a product's retail price
appears above. The two price-bearing model fields in the registry are both
accounted for.
