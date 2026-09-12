# GSP-CRV2-10 Stage 5 — the price band

**Finding:** V2-041 (P1) — no price band. **Repaired, not closed by me** (the
handoff owner audits behind this report).
**Baseline:** `cbe2656` (`WIP: snapshot competition readiness work`), branch
`crv2-10-stage5-price-band`, detached from `cbe2656` in an isolated worktree.
**Inventory commit:** `a32589b` — checked in **before** any runtime edit.
**Freeze commit:** `16cd350`. `git diff --check` clean; working tree clean.
**Inventory:** `handoff_readiness_v2/evidence/decision-rules/stage5/PRICE_WRITE_INVENTORY.md`
**Evidence:** `handoff_readiness_v2/evidence/decision-rules/stage5/`
**Migrations:** none. See "Files changed" for why none is required.

---

## 1. What was built

One calculator, `backend/core/services/price_band.py`, stating the rule once.
Three callers, which is what makes the guarantee structural rather than
maintained by hand (BECSR RW-50):

| Caller | What it takes from the calculator |
|---|---|
| `MarketingContextView` (`context-marketing`) | `price_band()` → the legal range the pricing screen displays |
| `DecisionMarketingSerializer.get_warnings` | `evaluate()`/`alert_for()` → the alert on the write response, returned by **both** write surfaces |
| `close_round` → `_apply_price_band` | `adjusted_price()`/`blank_price()` → the value actually stored |

The price shown as legal, the price accepted and the price applied are the same
function's output, so the range a team is told is legal is the range enforced,
to the cent.

**Round 1 is not a special case.** The anchor is the most recent
`RoundResultProductMarket.retail_price` for this `(team, product, market)` in an
earlier round. `bootstrap_round_zero` writes exactly such a row for round 0 from
the authored `FirmStarterProduct.base_price`, so round 1 resolves through the
same lookup round 7 uses. Reading the round-0 **result row** rather than
`FirmStarterProduct` is deliberate: `TeamProduct` has no FK back to the starter
product (bootstrap matches on product name) and the team's assigned home market
may differ from the starter product's market, so re-deriving that join here
would duplicate a fragile match for no gain.

**Why this substitutes where BECSR refuses.** BECSR's RW-52 refuses an
out-of-band price on the argument that storing 130 against a success response
lies to a student who typed 140. That objection is answered here by the two
things Ruling 2 makes mandatory: an audit event with actor `system` recording
submitted value, applied value and rule, and the adjustment shown to the team on
its own results screen. A substitution the team can see, with a receipt naming
what they submitted, is not the silent clamp BECSR rejected.

---

## 2. Inventory and coverage mapping

Built from `core/urls.py`, the DRF router and the Django model registry — not by
grepping for likely-looking code. Full detail in the inventory file; summary:

| Disposition | Rows |
|---|---|
| **CHANGED** | W1 whole-submission write, W2 partial `marketing` write, W3 the deadline (`close_round`), D1 pricing surface, D3 results screen, D8 `MarketingPage.js`, D9 `ResultsPage.js` |
| **COVERED, no edit needed** | W4 deadline cron (shares `close_round`), W9 `bootstrap_round_zero` (the anchor source), W10 `calculate_revenue` (carries the applied price into results and thus into next round's anchor), D2 products context, D5 instructor drill-down (already renders `user=None` as actor `system`) |
| **EXEMPT, with testable rationale** | W5 rebase (no price field), W6 Django admin (`CompetitionReadOnlyAdmin` denies add/change/delete), W7 supply-chain routes (no price field), W8 six seed/dev management commands (not HTTP-reachable), D4 competitor intel (R8: a team's own adjustment is not volunteered to rivals), D6/D7 published-result and forecast reads, D10 remaining frontend display surfaces |

Two model fields in the registry store a retail price:
`DecisionMarketing.retail_price` (the decision — the band's subject) and
`RoundResultProductMarket.retail_price` (the published result — the anchor,
read-only to the band). Both are accounted for.

**A trap the inventory caught before it was written into the code.**
`_lock_all_submissions` `continue`s on an already-locked submission. An
adjustment folded into that loop would have exempted precisely the teams that
submitted and locked on time. `_apply_price_band` therefore iterates every
active team's submission independently of lock state, and
`test_a_team_that_locked_early_is_still_subject_to_the_rule` holds it there.

**Determinism boundary (CRV2-01), touched read-only.** `decision_marketing` is
a manifest section. `prepare_manifest` runs inside `process_round`, strictly
after `close_round`, so the adjustment is recorded *as input state* rather than
rewriting a sealed manifest, and replay reproduces the adjusted round. No
CRV2-01 artifact is invalidated.

---

## 3. Files changed

**New runtime**
- `backend/core/services/price_band.py` — the calculator: `band_pct`,
  `price_anchor`, `price_band`, `evaluate`, `adjusted_price`, `blank_price`,
  `alert_for`, `adjustment_notice`, `audit_payload`.

**Changed runtime**
- `backend/core/engine/advance_round.py` — `_apply_price_band`, called from
  `close_round` before the freeze so each lock event's snapshot already holds
  the price that will be scored.
- `backend/core/serializers/decisions.py` — band alert appended to the existing
  `warnings` channel, so both write surfaces alert identically.
- `backend/core/views/decisions.py` — `price_bands` on the marketing context.
- `backend/core/views/results_api.py` — `price_adjustments` on round results.
- `backend/core/utils/participant_messages.py` — four bilingual keys
  (`price_band_alert`, `price_blank_alert`, `price_band_adjusted`,
  `price_blank_applied`), EN and zh-CN.
- `backend/core/services/read_inventory.json` — **regenerated**, see §7.
- `backend/core/tests/test_audit_integrity.py` — logged-route count 31 → 32,
  with a comment naming the cause, matching that file's existing convention.

**Authored data**
- `backend/scenarios/{consumer_electronics,clean_energy_tech,media_entertainment}_2026.yaml`
  — `price_band_pct: '0.30'` in the `config:` block.

**Frontend**
- `MarketingPage.js` — legal range, out-of-band and blank hints under the price
  input. `min`/`max` come from the server; the page chooses which
  server-supplied numbers to show and never derives a range of its own.
- `ResultsPage.js` — the adjustment notice as a warning block.
- `locales/en.json`, `locales/zh-CN.json` — `marketing.price_band_range`,
  `marketing.price_out_of_band`, `marketing.price_blank`,
  `results_page.price_adjustments`. Key parity between the two files verified.

**No migration, and why.** Nothing changes the schema. The band parameter is a
`ScenarioConfig` row (the authored-parameter pattern R3 already uses for
`platform_switch_write_off_pct`), and the audit record reuses
`DecisionAuditEvent` with `user=None`, which is the system-actor shape
`_lock_all_submissions` already writes. An existing game with no
`price_band_pct` row takes the ruling's 0.30 default.

---

## 4. Test commands, counts and durations

Every run used `backend/scripts/test-postgres`, which starts its **own
disposable `postgres:16-alpine` container per run** with a random password and
removes it on exit. The production database at `192.168.50.38` was never
contacted and no systemd environment file was read. Runs were serialised under
`flock /tmp/globalstrat-backend-test.lock` (EXECUTION_PROTOCOL Phase 0).

| # | Command | Result |
|---|---|---|
| 1 | `flock -w 300 /tmp/globalstrat-backend-test.lock backend/scripts/test-postgres core.tests.test_price_band -v 2` | **26 tests, 0.560s, OK** |
| 2 | same harness, 8 boundary labels (first pass) | 187 tests, 159.908s, 2 failures — both diagnosed in §7 |
| 3 | same harness, `SensitiveReadInventoryTests` + `RouteCoverageTests` | 9 tests, 16.221s, 1 failure (pre-existing, §7) |
| 4 | **freeze candidate**: `core.tests.test_price_band` + `test_operator_concurrency` + `test_competition_hardening` + `test_participant_messages` + `test_product_rebase` + `test_audit_integrity` + `test_decision_limits` + `test_operator_events_view` + `test_cc22_multiround_e2e` | **213 tests, 167.051s, 1 failure** — the pre-existing route-inventory drift, §7 |

No full backend suite, no load run, no concurrency matrix, no determinism
replay, per this handoff's verification budget.

**The focused tests fail without the change**, established against the baseline
rather than asserted: `backend/core/services/price_band.py` does not exist at
`cbe2656` (every test imports it), and `_apply_price_band` and `price_band_pct`
each occur **0 times** at `cbe2656`.

**Boundaries touched, and the focused regression run for each:** the lifecycle
close path certified by CRV2-02 (`test_operator_concurrency`,
`test_competition_hardening`), the audit-record boundary certified by CRV2-04
(`test_audit_integrity`), the decision write surfaces
(`test_decision_limits`, `test_participant_messages`), Stage 4's re-basing
(`test_product_rebase`), CRV2-08's operator-events surface
(`test_operator_events_view`), and a multi-round end-to-end
(`test_cc22_multiround_e2e`) chosen specifically because it is where the blank
rule's new row would surface if it disturbed the engine. It did not.

---

## 5. How each row of the ruling is proven

| Ruling row | While open | At the deadline |
|---|---|---|
| **Out-of-band price** | `test_an_out_of_band_price_alerts_and_names_the_legal_range` (alert names `$280`/`$520`, names the product, and does **not** contain `retail_price`), `test_the_serializer_carries_the_band_alert_to_both_write_surfaces`, `test_the_teams_number_is_kept_while_the_round_is_open` (99999 stored as entered) | `test_a_price_above_the_band_moves_to_the_upper_edge` (→ 520.00), `test_a_price_below_the_band_moves_to_the_lower_edge` (→ 280.00), `test_the_nearer_edge_is_chosen_not_always_the_floor` (600 → 520, not 280) |
| **Blank / no price** | `test_a_blank_price_is_warned_about_the_floor` | `test_a_blank_product_market_is_priced_at_the_floor` (400 − 30% = 280.00) |
| **In-band price** | `test_an_in_band_price_says_nothing` | `test_an_in_band_price_is_used_as_entered_and_audits_nothing` (450 unchanged, zero audit rows) |
| **Round-1 anchoring** | `test_round_one_anchors_to_the_authored_starting_price` (anchor 400.00, source `previous_round`, anchor round 0 — the row bootstrap writes from the authored `base_price`); `test_the_anchor_is_the_most_recent_earlier_round` |
| **Band from the scenario, not a constant** | `test_the_width_comes_from_the_scenario_not_a_constant` (authored 0.10 → 360/440, and asserts the value is *not* the default), `test_the_default_band_is_thirty_percent_of_last_round`, `test_an_authored_zero_means_no_band_rather_than_an_inverted_one` |
| **Published round immutable** | `test_a_processed_round_is_not_repriced` (`changed=False`, price still 99999.00, **zero** audit rows), `test_closing_twice_adjusts_once` |
| **Bilingual** | `test_the_alert_is_available_in_chinese`, `test_the_adjustment_reads_back_to_the_team_in_both_languages` |

---

## 6. Audit-event evidence

`test_the_payload_carries_the_submitted_value_the_applied_value_and_the_rule`
asserts the stored payload field by field:

```
submitted_price  '99999.00'
applied_price    '520.00'
rule             'price_band.out_of_band_adjusted_to_nearer_edge'
band_min         '280.00'      band_max '520.00'
anchor_price     '400.00'      anchor_source 'previous_round'
product_name     'Aurora'      market_name  (name, never an id)
```

- **Actor `system`:** `test_an_adjustment_is_recorded_with_actor_system` asserts
  `event.user_id is None`, which is exactly the condition
  `InstructorTeamDecisionsView` renders as `actor: 'system'`
  (`results_api.py:1117-1118`). No change to that surface was needed — the
  CRV2-08 drill-down displays these events by construction.
- **The blank case is a separate rule:**
  `test_a_blank_default_is_recorded_under_its_own_rule` (action
  `price_blank_defaulted`, `submitted_price` null, rule
  `price_band.blank_priced_at_band_floor`).
- **Immutability holds:** `test_the_audit_row_cannot_be_edited_afterwards`
  (re-`save()` raises), so the receipt cannot be rewritten after the fact.
- **Visible to the team:** `RoundResultsView` returns `price_adjustments`,
  rendered from the audit payload rather than recomputed, so the sentence the
  team reads and the row an instructor produces in a dispute are one fact.

---

## 7. The two regression failures, and which one is mine

**Mine, and now closed.** `SensitiveReadInventoryTests` failed because making
`RoundResultsView` read `DecisionAuditEvent` reclassifies the team's own
round-results endpoint as a **logged sensitive audit read**. That is the review
event the check exists to force, not a defect. I regenerated
`read_inventory.json` (`manage.py dump_read_inventory`, run with
`DB_HOST=127.0.0.1 DB_PORT=1` so nothing could reach the production database).
The diff adds exactly one row — `results_api.RoundResultsView`, category
`audit`, `logged: true`, not exempt — taking sensitive routes 32 → 33 and logged
31 → 32, and the hardcoded middleware count was bumped with a comment naming the
cause. All `SensitiveReadInventoryTests` now pass.

**This is a deliberate widening of a disclosure surface and should be reviewed
as one:** a team can now read its own price-band audit payloads through the
results endpoint, and the middleware logs those reads. It is scoped by
`game`/`team` and to the two band actions.

**Not mine, and left red on purpose.**
`RouteCoverageTests.test_inventory_matches_the_checked_in_copy` fails on
`.../products/<product_id>/rebase/|post`. Established against the baseline: the
route is present in `urls.py` at `cbe2656` (2 occurrences) and **absent** from
`route_inventory.json` at `cbe2656`, and `git status` confirms I modified
neither `urls.py` nor `route_inventory.json`. This is Stage 4 drift that
predates this branch. I did not run `dump_route_inventory`, because absorbing
another stage's un-reviewed drift into this commit is exactly what that test
exists to prevent. It is raised as a finding below. It is **not** V2-017, which
is about admin function-based routes being invisible to the scanner.

---

## 8. New findings, in register format

The register is owned by another agent right now, so these are handed over
rather than landed. **I did not edit `V2_FINDINGS_REGISTER.md`.**

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| *(next)* | Route inventory / Stage 4 | **P1** | GSP-CRV2-10 Stage 4 (CRV2-02 boundary) | `core/services/route_inventory.json` was never regenerated after Stage 4 registered `product-rebase`, so `RouteCoverageTests.test_inventory_matches_the_checked_in_copy` fails at `cbe2656` and on every branch cut from it. The certified "0 unguarded mutating routes" claim does not cover the rebase route. The standing red also trains reviewers to ignore the one check that would catch the *next* real drift. | `git show cbe2656:backend/core/urls.py \| grep -c rebase` → 2; `git show cbe2656:backend/core/services/route_inventory.json \| grep -c rebase` → 0. Freeze transcript, `stage5/freeze-regression-transcript.txt`. | Open — logged, deliberately not repaired here |
| *(next)* | Demand engine / blank price | **P1** | GSP-CRV2-11 (calibration) + rules owner | Ruling 2's blank branch requires a price where no marketing decision exists. In GlobalStrat that means **creating** a `DecisionMarketing` row, because the serializer refuses a price ≤ 0 and the pricing screen drops unpriced rows from its payload. The row is written at the band floor with production 0, so the blank team earns nothing — but the preference engine reads `retail_price`, so a floor-priced product that cannot supply now participates in price-competitiveness and share allocation, which can move **rivals'** outcomes. This is an engine-behaviour consequence of the ruling; per the handoff I implemented the rule and did not adjust the engine. | `_apply_price_band` in `core/engine/advance_round.py`; `preference_engine.py:359` reads `mkt_decision.retail_price`. | Open — raised, not repaired |
| *(next)* | Audit correlation | **P2** | GSP-CRV2-10 / CRV2-04 boundary | Price-band adjustment events carry `request_id=''`. The operator close that caused them mints a `request_id` on its `OperatorAuditEvent`, so the two records cannot be correlated by id — an investigator must join on `(game, round, timestamp)`. Pre-existing shape: `_lock_all_submissions`'s own events have the same gap. | `advance_round._apply_price_band` / `_lock_all_submissions` vs `services/lifecycle.request_id_for`. | Open — raised, not repaired |

---

## 9. Rules-owner questions

I picked the safest reversible default for each and say so; none of these is
mine to settle.

**Q1 — what anchors a product with no prior-round price (a newly launched
product)?** *Chosen default:* the authored `reference_price_<positioning>` for
the product's tier (`reference_price_budget` and siblings — already authored in
every scenario and already used by the preference engine). *Alternative:* no
anchor, therefore no band, therefore any price legal. I rejected "no band" as
the default because it leaves V2-041's exposure open on exactly the path a team
would exploit — launch a product and price it at 1. Reversible by deleting
`_positioning_reference_price` from `price_anchor`; `price_band` already
returns a bandless result when no anchor exists.

**Q2 — what happens when a team prices for a market it has just entered?**
*Chosen default:* identical to Q1. There is no prior result row for that
`(product, market)`, so it falls through to the positioning reference. The
alternative — carrying the product's price from a *different* market — invents
cross-market coupling, so I did not.

**Q3 — does the band apply per product-market or per product?** *Chosen
default:* **per product-market**, because both tables are keyed that way:
`DecisionMarketing` is unique on `(submission, team_product, market)` and
`RoundResultProductMarket` on `(game, round, team, product, market)`. Per-product
would require choosing which market's price is "the" price.

**Q4 — (not on your list; I hit it) what should a system-created blank row
carry besides the price?** `DecisionMarketing` has no nullable decision fields,
so writing a price means writing a whole row. *Chosen default:* price at the
floor and everything else neutral — production 0, demand estimate 0, promotion
0, distribution investment 0, no campaign focus, channel split 0/0/0,
`distribution_strategy='mass_retail'`, production source = the row's own market.
Production 0 means the team still sells nothing, so no invented decision earns
them anything. See the second finding in §8 for the rival-facing consequence.

**Q5 — (not on your list) does the deadline rule bind a team that locked
early?** *Chosen default:* **yes.** The alternative would exempt the teams that
submitted on time, which cannot be the intent.

**Q6 — for the record, a deliberate divergence, not a drift.** BECSR refuses
out-of-band prices; Ruling 2 substitutes and audits. Implemented as ruled.

---

## 10. Delta for the GSP-CRV2-08 owner (obligation from the handoff)

This handoff requires Stage 5 to hand CRV2-08 the dispute case its frozen
inventory cannot have covered.

**New dispute-2 case: "our price was recorded differently from what we
entered."** A team submits a price, the deadline passes, and the stored price
legitimately differs from the number they typed. The answer path, end to end:

1. The team sees it themselves — `price_adjustments` on
   `GET .../results/round/<n>/`, rendered on the results screen in EN or zh-CN.
2. The operator sees it — `GET .../instructor/teams/<team_id>/decisions/`
   already lists `audit_events` with `actor: 'system'`, the action
   (`price_band_adjusted` / `price_blank_defaulted`), the server timestamp, the
   endpoint (`engine:close_round`), the `payload_sha256` and the full payload
   naming submitted value, applied value, rule, band and anchor.
3. The record cannot be edited afterwards (`DecisionAuditEvent` raises on
   re-save; the CRV2-04 chain seals it).

**No CRV2-08 evidence is invalidated** — its five passing disputes are
untouched and were not replayed, and its completed game was not rebuilt. This
adds a seventh case to its inventory. The case has **not** been re-verified
through the supported operator path in a live stack; it is proven by focused
tests here. That walkthrough remains outstanding, and I flag it rather than
claim it (see §12).

---

## 11. Auditor preflight checklist

- **Did inventory start from registered routes/models/jobs, not only code using
  the new abstraction?** Yes. From `core/urls.py`, the DRF router and the model
  registry, committed at `a32589b` before any runtime edit at `16cd350`. It
  found both price-bearing model fields and the lock-state trap in §2.
- **Is there an active legacy or alternate entry point?** Enumerated, all
  dispositioned: two student write surfaces (both covered by one serializer),
  two deadline entry points (operator close and the cron, sharing `close_round`),
  Django admin (read-only by `CompetitionReadOnlyAdmin`), six seed/dev
  management commands (not HTTP-reachable, exempt), supply-chain routes (no
  price field).
- **Does a failure/refusal audit survive rollback?** `close_round` is one
  atomic transaction, so a price change and its audit row commit or roll back
  together and cannot diverge. By design this rule refuses nothing — Ruling 2
  substitutes — so there is no refusal record to preserve.
- **Is each correlation ID generated once and identical in response/audit/log?**
  **No, and I am not claiming otherwise.** The adjustment is engine-initiated
  and has no response; its events carry `request_id=''`, matching the existing
  `_lock_all_submissions` events. Raised as a P2 finding in §8.
- **Is background/external work delayed until the outer transaction commits?**
  No background or external work was added. The existing audit-seal scheduling
  is unchanged.
- **Do claimed environment values describe the executing process?** Yes.
  Django 5.2.4, Python 3.10, Docker 29.4.3, a fresh `postgres:16-alpine`
  container per run. The regeneration command ran with `DB_HOST=127.0.0.1
  DB_PORT=1`; settings default to `192.168.50.38`, which was never contacted.
- **Does provenance identify runtime bytes, including required untracked
  files?** Freeze commit `16cd350`, `git diff --check` clean, tree clean, no
  untracked runtime files.
- **Do README commands run exactly as written against stored artifacts?** The
  §4 commands are the literal commands run; transcripts are in
  `evidence/decision-rules/stage5/`.
- **Do P0/P1/P2 labels match their definitions?** V2-041 remains **P1** —
  it degrades competitive fairness, it does not block play. The new findings are
  labelled against the same definitions (P0 blocks; P1 degrades; P2 cosmetic).
- **Does each negative test prove mutation/engine execution did not occur?**
  Yes. `test_a_processed_round_is_not_repriced` asserts `changed=False`, the
  price unchanged **and** zero audit rows; `test_an_in_band_price_is_used_as_
  entered_and_audits_nothing` asserts no audit row was written;
  `test_closing_twice_adjusts_once` asserts exactly one event across two closes.

---

## 12. Rollback, and what is not proven

**Rollback.** `git revert 16cd350` removes the band entirely; there is no
migration to unwind. `read_inventory.json` reverts with it and the middleware
count returns to 31. The `price_band_pct` YAML entries are additive and take
effect only when a scenario is loaded; deleting the `ScenarioConfig` rows
returns the 0.30 default while the code stands, and reverting the code makes
them inert. Rows the blank rule created are ordinary `DecisionMarketing` rows
and can be deleted; the audit events are immutable by design and would remain as
the record of what happened, which is the intent.

**Not proven, stated plainly — I do not claim any gate is closed:**

1. **The frontend was not built, linted or exercised.** `node_modules` is absent
   in this worktree, so no `react-scripts build`, no lint, no browser
   verification. The JS edits are syntactically reviewed and the locale files
   parse with EN/zh-CN key parity verified, but STANDING-DISCIPLINE §5 is
   explicit that a backend 200 is not evidence of frontend completion. The
   student-visible half of this ruling is therefore **unverified in a browser**.
2. **The new dispute-2 case has not been walked through a live operator stack**
   (§10). It is proven by focused tests only.
3. **No full suite, load run, concurrency matrix or determinism replay** was run,
   per this handoff's verification budget; CRV2-09 owns the integrated
   regression.
4. **One regression test is red at this freeze** — the pre-existing Stage 4
   route-inventory drift (§7), deliberately not absorbed.
5. The blank rule's effect on rival share allocation (§8) is **raised, not
   measured**; quantifying it belongs to CRV2-11.

**Commit hygiene note.** Both commits used `--no-verify`. The vendored
`aide-checks` pre-commit runner refuses on a revision mismatch that predates
this branch (runner built from `cbe2656`, repo vendored at `e710f26`); its own
header documents `--no-verify` as the sanctioned bypass and names the deploy
gate as the layer that is not bypassable. Nothing here deploys. Re-vendoring
would have meant reaching into another tool's clone, which is outside this
task's scope.
