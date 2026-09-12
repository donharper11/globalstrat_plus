# GSP-CRV2-10 Stage 5 — the price band

**Finding:** V2-041 (P1) — no price band. **Repaired, not closed by me.**
**Base:** `e1b744c` (`crv2-release-integration`). Originally built on `cbe2656`
and **rebased onto `e1b744c`** cleanly, no conflicts.
**Commits:** `a4691de` inventory (before any runtime edit) → `e139d3a` band →
`b0a908d` report → `5e9164b` **rework** (current freeze).
`git diff --check` clean; tree clean; `makemigrations --check` reports no
changes pending.
**Inventory:** `handoff_readiness_v2/evidence/decision-rules/stage5/PRICE_WRITE_INVENTORY.md`
**Evidence:** `handoff_readiness_v2/evidence/decision-rules/stage5/`
**Migration:** `0085_price_band_blank_price` (one reversible `AlterField`).

---

## 0. What the rework changed

The owner's clarification of Ruling 2 (2026-09-12) narrowed the blank branch,
and the coordinator's audit added two items. The calculator, audit event,
alerting and anchoring were accepted as built and are unchanged.

| # | Change | Why |
|---|---|---|
| 1 | **No row is invented.** The deadline no longer fabricates `DecisionMarketing` rows for product-markets the team never marketed. `blank_price()` returns a floor **only** when the anchor is a real prior-round price. | "Blank" means a product the team **is selling**. An unmarketed product-market is absence, not a blank price. |
| 2 | **Blank made representable.** `retail_price` is nullable; the serializer accepts an absent price and still refuses zero and negatives. A blank that cannot be resolved is refused at lock and by a new fail-closed engine precondition. | Previously the state the ruling describes could not be stored at all, so the blank branch had nothing to act on. |
| 3 | **Cross-team leakage proved.** New tests on `RoundResultsView`. | The read-inventory widening is only safe if the payloads served belong to the team in the URL. |
| 4 | **Rebased onto `e1b744c`.** | The WIP snapshot was split into reviewed commits. |

**Why item 1 mattered mechanically, verified in the source rather than
accepted on argument:** `bass_engine` builds `retail_prices` from
`DecisionMarketing` rows alone (`:57-66`) and gives a product with no entry
`attractiveness = 0.0` (`:108-110`), so an unmarketed product takes no demand
today. A fabricated floor-priced row with `production_volume=0` would have
entered the attractiveness denominator at a very competitive price, taken share
from every rival, and then booked the entire allocation as `lost_demand`,
because `reported_sold` is capped by available production (`:159-166`). That
penalises rivals for another team's inaction. My own finding 2 in the first
report called this out; the narrowing removes it, and that finding is now
**closed by this rework** rather than left open.

---

## 1. What was built

One calculator, `backend/core/services/price_band.py`, stating the rule once.
Three callers, which is what makes the guarantee structural rather than
maintained by hand (BECSR RW-50):

| Caller | What it takes from the calculator |
|---|---|
| `MarketingContextView` | `price_band()` → the legal range the pricing screen shows |
| `DecisionMarketingSerializer.get_warnings` | `alert_for()` → the alert on the write response, returned by **both** write surfaces |
| `close_round` → `_apply_price_band` | `adjusted_price()` / `blank_price()` → the value actually stored |

**Round 1 is not a special case.** The anchor is the most recent
`RoundResultProductMarket.retail_price` in an earlier round;
`bootstrap_round_zero` writes round 0 from the authored
`FirmStarterProduct.base_price`, so round 1 uses the same lookup as round 7.

**Why this substitutes where BECSR refuses.** BECSR's RW-52 refuses, arguing
that storing 130 against a success response lies to a student who typed 140.
Ruling 2 answers that with two mandatory things: an audit event with actor
`system` recording submitted value, applied value and rule, and the adjustment
shown to the team on its own results screen.

---

## 2. Inventory and coverage mapping

Built from `core/urls.py`, the DRF router and the model registry, committed at
`a4691de` **before** any runtime edit. Summary:

| Disposition | Rows |
|---|---|
| **CHANGED** | W1 whole-submission write, W2 partial `marketing` write, W3 the deadline, D1 pricing surface, D3 results screen, D8 `MarketingPage.js`, D9 `ResultsPage.js` |
| **COVERED, no edit** | W4 deadline cron (shares `close_round`), W9 `bootstrap_round_zero` (anchor source), W10 `calculate_revenue`, D2 products context, D5 instructor drill-down (already renders `user=None` as `system`) |
| **EXEMPT, testable rationale** | W5 rebase, W6 admin (read-only), W7 supply-chain routes, W8 six seed commands, D4 competitor intel (R8), D6/D7 published-result and forecast reads, D10 other display surfaces |

**The trap the inventory caught:** `_lock_all_submissions` skips an
already-locked submission, so an adjustment folded into that loop would have
exempted exactly the teams that submitted on time. `_apply_price_band` iterates
independently of lock state, with a test pinning it.

**Determinism boundary (CRV2-01), touched read-only.** `prepare_manifest` runs
inside `process_round`, strictly after `close_round`, so the adjustment is
recorded *as input state* and replay reproduces the adjusted round.

---

## 3. Files changed

**New runtime** — `core/services/price_band.py` (the calculator).

**Changed runtime**
- `core/engine/advance_round.py` — `_apply_price_band` (called from
  `close_round` before the freeze) **and** the new unpriced-row precondition in
  `_run_phase_1`.
- `core/models/decisions.py` — `retail_price` nullable.
- `core/migrations/0085_price_band_blank_price.py` — one `AlterField`.
- `core/serializers/decisions.py` — band alert; accepts an absent price, still
  refuses zero and negatives.
- `core/views/decisions.py` — `price_bands` on the marketing context; lock-time
  refusal for an unresolvable blank; null guards on two display paths.
- `core/views/results_api.py` — `price_adjustments`; null guard on the
  instructor drill-down.
- `core/views/cc15_views.py` — null guard on the forecast projection.
- `core/utils/participant_messages.py` — four bilingual keys (EN + zh-CN).
- `core/services/read_inventory.json` — regenerated (§7).
- `core/tests/test_audit_integrity.py` — logged-route count 31 → 32, annotated.

**Authored data** — `price_band_pct: '0.30'` in all three scenario YAMLs.

**Frontend** — `MarketingPage.js` (legal range, out-of-band and blank hints; an
absent price is kept as `null` rather than coerced to 0, and a row the team is
filling in but has not priced is still submitted, or "submitted blank" could
never reach the server); `ResultsPage.js` (adjustment notice);
`locales/en.json` + `zh-CN.json`, key parity verified.

**Migration scope.** Only the nullability change. The band parameter is a
`ScenarioConfig` row (the pattern R3 uses for
`platform_switch_write_off_pct`), and the audit record reuses
`DecisionAuditEvent` with `user=None`, the system-actor shape
`_lock_all_submissions` already writes.

---

## 4. Test commands, counts, durations

Every run used `backend/scripts/test-postgres`, which starts its **own
disposable `postgres:16-alpine` container per run** and removes it on exit. The
production database at `192.168.50.38` was never contacted and no systemd
environment file was read. Runs were serialised under
`flock /tmp/globalstrat-backend-test.lock` (Phase 0).

| # | Command | Result |
|---|---|---|
| 1 | `flock -w 600 … test-postgres core.tests.test_price_band -v 2` | **41 tests, 1.013s, OK** |
| 2 | **freeze regression** — `test_price_band` + `test_operator_concurrency` + `test_competition_hardening` + `test_participant_messages` + `test_product_rebase` + `test_audit_integrity` + `test_decision_limits` + `test_operator_events_view` + `test_cc22_multiround_e2e` | **228 tests, 170.820s, OK** |
| 3 | `manage.py makemigrations --check --dry-run` (DB env pointed at a dead socket) | `No changes detected`, exit 0 |

Pre-rework runs, for the record: 26 tests/0.560s focused; 213 tests/167.051s
regression with one failure (the route-inventory drift, §7).

No full backend suite, load run, concurrency matrix or determinism replay, per
this handoff's verification budget. **I did not touch the seven pre-existing
full-suite failures (V2-071/V2-074).** They are outside the labels above and
were not run.

**The focused tests fail without the change**, established against the original
baseline rather than asserted: `price_band.py` does not exist at `cbe2656`, and
`_apply_price_band` and `price_band_pct` each occur **0 times** there.

---

## 5. How each row of the ruling is proven

| Ruling row | While open | At the deadline |
|---|---|---|
| **Out-of-band** | `test_an_out_of_band_price_alerts_and_names_the_legal_range` (names `$280`/`$520`, names the product, contains no `retail_price`), `test_the_serializer_carries_the_band_alert_to_both_write_surfaces`, `test_the_teams_number_is_kept_while_the_round_is_open` | `test_a_price_above_the_band_moves_to_the_upper_edge` (→520.00), `test_a_price_below_the_band_moves_to_the_lower_edge` (→280.00), `test_the_nearer_edge_is_chosen_not_always_the_floor` (600→520) |
| **Blank, product the team IS selling** | `test_a_blank_price_on_a_selling_product_is_warned_about_the_floor` | `test_a_blank_price_on_a_selling_product_is_filled_at_the_floor` (400−30%=280.00) |
| **Blank, product never sold here** | `test_a_blank_price_with_no_previous_price_asks_the_team_to_set_one` (no floor promised) | `test_a_blank_on_a_never_sold_product_survives_the_deadline_unpriced`, then `test_an_unresolved_blank_is_refused_before_any_competitive_write` |
| **Unmarketed product-market** | — | `test_an_unmarketed_product_market_gets_no_row_and_no_price`, `test_a_team_with_no_submission_at_all_is_left_alone`, `test_the_floor_is_withheld_without_a_real_prior_round_price` |
| **In band** | `test_an_in_band_price_says_nothing` | `test_an_in_band_price_is_used_as_entered_and_audits_nothing` (450 unchanged, zero audit rows) |
| **Blank representable** | `test_a_marketing_row_can_be_stored_with_no_price`, `test_the_serializer_accepts_an_absent_price`, `test_a_stated_price_of_zero_is_still_refused`, `test_a_negative_price_is_still_refused` |
| **Round-1 anchoring** | `test_round_one_anchors_to_the_authored_starting_price` (anchor 400.00, source `previous_round`, round 0), `test_the_anchor_is_the_most_recent_earlier_round` |
| **Band authored, not constant** | `test_the_width_comes_from_the_scenario_not_a_constant` (0.10→360/440, asserts it is *not* the default), `test_the_default_band_is_thirty_percent_of_last_round`, `test_an_authored_zero_means_no_band_rather_than_an_inverted_one` |
| **Published round immutable** | `test_a_processed_round_is_not_repriced` (`changed=False`, price unchanged, **zero** audit rows), `test_closing_twice_adjusts_once` |
| **Bilingual** | `test_the_alert_is_available_in_chinese`, `test_the_adjustment_reads_back_to_the_team_in_both_languages` |
| **Lock-state** | `test_a_team_that_locked_early_is_still_subject_to_the_rule` |

### Cross-team leakage (rework item 3)

- `test_both_teams_were_adjusted_so_the_test_can_actually_leak` — a control:
  both teams really do have an adjustment, so the leakage test is not vacuous.
- `test_a_team_sees_only_its_own_price_adjustments` — exactly one entry,
  `Aurora`, and the rival's product name appears nowhere in the response.
- `test_a_team_with_no_adjustments_gets_an_empty_list_not_a_missing_key`.
- `test_a_rivals_student_cannot_read_this_teams_adjustment_payloads` — asserts
  **403 explicitly**. `RoundResultsView` declares no permission class; what
  refuses the rival is `TeamScopeGuardMiddleware`. I first wrote this as a bare
  "the rival did not see 'Aurora'", which would also have passed on a 500 and
  proved nothing; the status assertion is the fix.
- `test_the_owning_teams_student_is_allowed_through_the_same_guard` — the
  control that keeps the 403 meaningful.

---

## 6. Audit-event evidence

`test_the_payload_carries_the_submitted_value_the_applied_value_and_the_rule`
asserts the stored payload field by field:

```
submitted_price  '99999.00'      applied_price '520.00'
rule             'price_band.out_of_band_adjusted_to_nearer_edge'
band_min '280.00'  band_max '520.00'  anchor_price '400.00'
anchor_source 'previous_round'   product_name 'Aurora'   market_name (name, not id)
```

- **Actor `system`** — `test_an_adjustment_is_recorded_with_actor_system`
  asserts `event.user_id is None`, the exact condition
  `InstructorTeamDecisionsView` renders as `actor: 'system'`. No change to that
  surface was needed.
- **Blank has its own rule** — `test_a_blank_default_is_recorded_under_its_own_rule`
  (`price_blank_defaulted`, null `submitted_price`).
- **Immutable** — `test_the_audit_row_cannot_be_edited_afterwards`.
- **Visible to the team** — rendered from the audit payload, not recomputed, so
  the team's sentence and the instructor's row are one fact.

---

## 7. The two regression failures from the first pass

**Mine, closed.** Making `RoundResultsView` read `DecisionAuditEvent`
reclassified the team's results endpoint as a **logged sensitive audit read** —
the review event the check exists to force. `read_inventory.json` regenerated
(run with `DB_HOST=127.0.0.1 DB_PORT=1`, so nothing could reach production);
the diff adds exactly one row, `logged: true`, not exempt; the middleware count
was bumped 31 → 32 with a comment naming the cause. **This is a deliberate
widening of a disclosure surface**, and the leakage tests in §5 are what make it
safe: the payloads are filtered by team, and a rival account is refused 403.

**Not mine — now withdrawn.** `RouteCoverageTests` failed on the
`product-rebase` route missing from `route_inventory.json`. I left it red and
raised it rather than absorb another stage's drift. **The rebase resolved it:**
the route appears 2× in `route_inventory.json` at `e1b744c` and 0× at
`cbe2656`, and the freeze regression is now fully green. The finding is
**withdrawn, not fixed by me** — it was real at the old baseline and the
integration branch had already regenerated the file.

---

## 8. Findings — register entries handed over

The register is owned by another agent; **I did not edit
`V2_FINDINGS_REGISTER.md`.**

| ID | Area | Sev | Owner | Description | Evidence | Status |
|---|---|---:|---|---|---|---|
| *(next)* | Read authorisation / defence in depth | **P2** | CRV2-08 boundary | `RoundResultsView` declares no `permission_classes`; its team-ownership check comes solely from `TeamScopeGuardMiddleware`. The guard works and is now tested, but the view is one middleware-ordering change away from serving one team's audit payloads to another. Stage 5 raised the stakes by routing adjustment payloads through it. | `results_api.py:85-91` (no permission class); `middleware.py:210-277`; `test_a_rivals_student_cannot_read_this_teams_adjustment_payloads` | Open — raised, not repaired |
| *(next)* | Audit correlation | **P2** | CRV2-04 boundary | Price-band adjustment events carry `request_id=''`, so they cannot be correlated by id with the operator close that caused them; an investigator must join on `(game, round, timestamp)`. Pre-existing shape — `_lock_all_submissions`'s own events have the same gap. | `advance_round._apply_price_band` vs `services/lifecycle.request_id_for` | Open — raised, not repaired |

**Withdrawn from my first report:**
- *Stale `route_inventory.json`* — resolved on the integration branch (§7).
- *Blank rule distorts rival demand* — **closed by this rework**; the narrowing
  means no row is invented, so the distortion cannot arise.

---

## 9. Rules-owner questions

**Answered by the owner in this rework:** what "blank" means, and that the
floor must not reach an unmarketed product-market. Implemented as ruled.

**Q1 — what anchors a product with no prior-round price?** *Default taken:* the
authored `reference_price_<positioning>`. It states a legal *range* to a team
that is pricing a new product, and — after the narrowing — deliberately does
**not** license the system to price on their behalf. Reversible by deleting
`_positioning_reference_price`.

**Q2 — a market just entered?** Identical to Q1; no prior-round row, so the
positioning reference. Carrying a price from a different market would invent
cross-market coupling.

**Q3 — per product-market or per product?** **Per product-market**, because
both tables are keyed that way.

**Q4 — NEW, and the one I most want ruled on.** A team leaves the price out on
a product that has **never sold in that market** (a newly launched product).
There is no prior-round price, so per the narrowing no floor applies. *Default
taken, and it is a rule I chose:* refuse it — at lock via `_full_validate`, and
again at the engine precondition if a row reaches processing unpriced. The
alternative would be to let it through unpriced and treat the product as not
for sale. I chose refusal because a null reaches `float()` in `bass_engine`,
and because BECSR's `resolve_blank_price` refuses in exactly this
"no anchor to help from" case. **If you prefer 'not for sale', say so** — it is
a one-branch change plus a demand-side decision that is not mine.

**Q5 — does the deadline rule bind a team that locked early?** *Default:* yes.

**Q6 — for the record:** BECSR refuses out-of-band prices; Ruling 2 substitutes
and audits. Implemented as ruled, deliberate divergence.

---

## 10. Delta for the GSP-CRV2-08 owner

**New dispute-2 case: "our price was recorded differently from what we
entered."** Two shapes now: an out-of-band price moved to the nearer edge, and
a blank price on a product the team was already selling filled at the floor.
The answer path:

1. The team sees it — `price_adjustments` on
   `GET .../results/round/<n>/`, on the results screen in EN or zh-CN.
2. The operator sees it — `GET .../instructor/teams/<team_id>/decisions/`
   lists `audit_events` with `actor: 'system'`, the action, server timestamp,
   endpoint `engine:close_round`, `payload_sha256` and the full payload.
3. The record cannot be edited afterwards.

**No CRV2-08 evidence is invalidated**; its five disputes were not replayed and
its game was not rebuilt. This adds a case. **It has not been walked through a
live operator stack** — it is proven by focused tests only (§12).

---

## 11. Auditor preflight checklist

- **Inventory from registered routes/models/jobs?** Yes — `urls.py`, the DRF
  router, the model registry; committed at `a4691de` before any runtime edit.
  It found both price-bearing fields and the lock-state trap.
- **Active legacy or alternate entry point?** Enumerated and dispositioned: two
  write surfaces (one serializer), two deadline entry points (sharing
  `close_round`), admin (read-only), six seed commands, supply-chain routes.
- **Does a failure/refusal audit survive rollback?** `close_round` is one
  atomic transaction, so a price change and its audit commit or roll back
  together. The new refusals (lock-time, engine precondition) reject before any
  write, so there is nothing partial to preserve.
- **Correlation ID generated once and identical across response/audit/log?**
  **No — stated plainly.** Engine-initiated adjustments have no response and
  carry `request_id=''`, matching existing `_lock_all_submissions` events.
  Raised as P2 in §8.
- **Background/external work delayed until the outer transaction commits?** No
  background or external work was added.
- **Do claimed environment values describe the executing process?** Yes. Django
  5.2.4, Python 3.10, Docker 29.4.3, fresh `postgres:16-alpine` per run;
  management commands run with `DB_HOST=127.0.0.1 DB_PORT=1` (settings default
  to `192.168.50.38`, never contacted).
- **Provenance identifies runtime bytes?** Freeze `5e9164b` on base `e1b744c`,
  clean tree, no untracked runtime files.
- **README commands run exactly as written?** The §4 commands are literal;
  transcripts are in the evidence directory.
- **P0/P1/P2 labels match definitions?** V2-041 remains **P1** (degrades, does
  not block). New findings are P2 under the same definitions.
- **Does each negative test prove mutation/engine execution did not occur?**
  Yes. `test_a_processed_round_is_not_repriced` asserts `changed=False`, price
  unchanged **and** zero audit rows; `test_an_unmarketed_product_market_gets_no_row_and_no_price`
  asserts no `DecisionMarketing` row exists at all;
  `test_an_in_band_price_is_used_as_entered_and_audits_nothing` asserts no audit
  row; `test_closing_twice_adjusts_once` asserts exactly one event across two
  closes; `test_an_unresolved_blank_is_refused_before_any_competitive_write`
  asserts the round stops before Phase 1 mutates anything.

---

## 12. Rollback, and what is not proven

**Rollback.** `git revert 5e9164b e139d3a` removes the band. Migration `0085`
is a single `AlterField` and reverses cleanly, but **reverse it only after
confirming no `retail_price` is null**, or the column cannot go back to NOT
NULL; the engine precondition means no null should survive a processed round.
`read_inventory.json` and the middleware count revert with the code. The
`price_band_pct` YAML entries are additive and inert once the code is gone;
deleting the `ScenarioConfig` rows returns the 0.30 default while the code
stands. Audit events are immutable by design and remain as the record.

**Not proven — I claim no gate is closed:**

1. **The frontend was not built, linted or exercised.** `node_modules` is
   absent in this worktree (re-checked after the rebase), so no
   `react-scripts build`, no lint, no browser verification. The JS is
   syntactically reviewed and both locale files parse with EN/zh-CN key parity,
   but STANDING-DISCIPLINE §5 is explicit that a backend 200 is not evidence of
   frontend completion. **The student-visible half of this ruling — including
   the new "clear the price box to submit blank" interaction — is unverified in
   a browser.** That interaction is the one I would most want a human to click.
2. **The new dispute-2 case has not been walked through a live operator stack**
   (§10); it is proven by focused tests only.
3. **No full suite, load run, concurrency matrix or determinism replay**, per
   the verification budget. The seven pre-existing full-suite failures
   (V2-071/V2-074) were neither run nor touched.
4. **Q4 in §9 is a rule I chose, not one I was given.** If the owner prefers
   "not for sale" to "refuse", that is a one-branch change.

**Commit hygiene.** All commits used `--no-verify`. The vendored `aide-checks`
pre-commit runner refuses on a revision mismatch; its own header documents
`--no-verify` as the sanctioned bypass and names the deploy gate as the
non-bypassable layer, and nothing here deploys. One factual correction to the
coordinator's note: `checks/.aide-checks-rev` is **present** in this worktree
and at `e1b744c` (it reads `e710f26`); the runner reports a revision *mismatch*
against it rather than an absent file. Re-vendoring remains outside this
handoff.
