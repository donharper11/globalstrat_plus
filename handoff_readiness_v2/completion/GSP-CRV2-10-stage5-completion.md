# GSP-CRV2-10 Stage 5 — the price band

**Finding:** V2-041 (P1) — no price band. **Repaired, not closed by me.**
**Base:** `4d2169c` (`crv2-release-integration`, the merge of
`crv2-11-round-zero-and-preferences`). Rebased twice, both clean, no conflicts:
`cbe2656` → `e1b744c` → `4d2169c`.
**Commits:** `6b703e0` inventory (before any runtime edit) → `be0fa86` band →
`ae52189` report → `a9b4039` rework 1 (narrow the blank rule) → `ee3cefa`
report → **`49ea50b` rework 2 (not for sale) — the freeze.**
`git diff --check` clean; tree clean; `makemigrations --check` clean.
**Inventory:** `evidence/decision-rules/stage5/PRICE_WRITE_INVENTORY.md`
**Evidence:** `evidence/decision-rules/stage5/`
**Migration:** `0085_price_band_blank_price` (one reversible `AlterField`).

---

## 0. The rule as it now stands

Ruling 2 (2026-08-31), narrowed 2026-09-12, with Q4 ruled the same day.

| Team's input | While the round is open | At the deadline |
|---|---|---|
| Out-of-band price | **Alert** naming the legal range; submission accepted, the team's number kept | Adjusted to the **nearer band edge** |
| Blank, on a product that **sold here last round** | Alert: this will be priced at the floor | Set to **previous round −30%** |
| Blank, on a product that **never sold here** | Alert: set a price yourself — no floor is promised | **Not offered for sale.** Price left null, recorded, round resolves |
| In-band price | Nothing | Used as entered |

Every one of the three deadline outcomes writes a `DecisionAuditEvent` with
actor `system` and is visible to the team on its results screen.

### What the two reworks changed, and why I had it wrong

**Rework 1 — the floor must not reach an unmarketed product-market.** My first
implementation fabricated a floor-priced `DecisionMarketing` row for any active
product-market that had none. Verified in the source rather than argued:
`bass_engine` builds its offer map from `DecisionMarketing` rows alone
(`:57-66`) and scores a product with no entry at `0.0` attractiveness
(`:108-110`), so an unmarketed product takes no demand today. A fabricated
floor-priced row with `production_volume=0` would have entered the
attractiveness denominator at a very competitive price, taken share from every
rival, and booked the whole allocation as `lost_demand`, because `reported_sold`
is capped by available production (`:159-166`). That penalises rivals for
another team's inaction.

**Rework 2 — refusing the round was wrong in consequence.** Having made a blank
price storable, I guarded it with a fail-closed engine precondition on *any*
null. The deciding fact I did not have: **there is no supported way for an
instructor to set a missing price** — `InstructorTeamDecisionsView` is GET-only
(`results_api.py:1061-1065`) and R13 made the Django admin read-only for every
competition model. So one team omitting a price on a new product would have
stalled the entire heat until someone reopened the round. The instinct
(fail closed rather than invent a price) was right in kind; the consequence was
a mid-competition incident caused by a single team's oversight. **The round
must always resolve.**

---

## 1. How "not for sale" is implemented

The owner's suggestion — exclude null-priced rows from the demand path at
source — is what I adopted, because a price that does not exist cannot be a
valid offer. That reads as an invariant rather than a patch, and it makes the
outcome identical to a product with no decision at all, which the engine
already handles correctly.

| Site | Change | Why |
|---|---|---|
| `bass_engine.py:57-66` | `.exclude(retail_price__isnull=True)` | The offer gate. An unpriced product never becomes an offer, so it takes no demand and displaces no rival. |
| `revenue.py:70-124` | null → `Decimal('0')`, **row still processed** | The team ordered production; it must still pay COGS and carry the unsold units as inventory. *Not for sale must not mean free manufacturing.* Skipping the row would have silently refunded a real decision. `units_sold` is already 0 because `bass_engine` allocated it nothing. |
| `coherence.py:302` | skip unoffered rows | No price means nothing to judge positioning against — neither credited nor penalised, and not counted in `max_possible`. |
| `coherence.py:700` | narrative renders `not offered` | Was an unguarded `float()` in an f-string. |
| `preference_engine.py:359` | null scores neutral | Exactly as "no decision" already does; otherwise an unpriced product would earn or lose price competitiveness it never competed on. |

Checked and **not** changed: `costs.py` reads `rev['retail_price']` from the
revenue dict, not the decision; `campaign_engine`, `derived_features` and
`alliance_engine` read promotion and distribution fields, never `retail_price`.

**The precondition survives as defence in depth, and is now unreachable
normally.** It fires only for a row the deadline *should* have resolved — a
prior-round price exists, yet the value is still null — which means
`close_round` never ran. `test_a_skipped_deadline_is_still_refused_as_defence_in_depth`
holds it there; `test_a_round_with_an_unpriced_never_sold_product_still_resolves`
proves the normal path resolves.

**The lock-time refusal is kept**, as instructed: a team that locks
deliberately is at a moment it can act on, so it is told to price the product.
Only the deadline path must never stall.

---

## 2. R11 check — the anchor did not move

Asked for plainly, and answered plainly: **R11 did not change what my anchor
resolves to, and I adjusted no test.**

- `bootstrap.py` still writes the round-0 result row's price from the authored
  `FirmStarterProduct.base_price` (`:236`, `:255`). R11 rewrote round-zero
  *segment adoption* apportionment — a different table.
- Before making any edit on the new base, I ran the focused suite unchanged:
  **41 tests, 14.767s, OK**, including
  `test_round_one_anchors_to_the_authored_starting_price` (anchor `400.00`,
  source `previous_round`, anchor round 0).

---

## 3. Files changed

**New runtime** — `core/services/price_band.py` (the one calculator).

**Changed runtime** — `core/engine/advance_round.py` (deadline pass + narrowed
precondition), `core/engine/bass_engine.py`, `core/engine/revenue.py`,
`core/engine/coherence.py`, `core/engine/preference_engine.py`,
`core/models/decisions.py` (nullable price) + `migrations/0085`,
`core/serializers/decisions.py`, `core/views/decisions.py`,
`core/views/results_api.py`, `core/views/cc15_views.py`,
`core/utils/participant_messages.py` (five bilingual keys),
`core/services/read_inventory.json` (regenerated), `core/tests/test_audit_integrity.py`
(logged-route count 31 → 32, annotated).

**Authored data** — `price_band_pct: '0.30'` in all three scenario YAMLs.

**Frontend** — `MarketingPage.js` (legal range and blank hints; an absent price
stays `null` rather than becoming 0, and an unpriced row the team is otherwise
filling in is still submitted, or "submitted blank" could never reach the
server), `ResultsPage.js`, `locales/en.json` + `zh-CN.json` (key parity
verified).

---

## 4. Test commands, counts, durations

Every run used `backend/scripts/test-postgres` — its **own disposable
`postgres:16-alpine` container per run**, removed on exit. The production
database at `192.168.50.38` was never contacted and no systemd environment file
was read. Runs were serialised under `flock` (Phase 0), and no container was
left behind.

| # | Command | Result |
|---|---|---|
| 1 | focused, **unchanged, on the new base before any edit** (the R11 check) | **41 tests, 14.767s, OK** |
| 2 | `flock -w 900 … test-postgres core.tests.test_price_band -v 2` | **45 tests, 18.826s, OK** |
| 3 | **freeze regression** — `test_price_band`, `test_operator_concurrency`, `test_competition_hardening`, `test_participant_messages`, `test_product_rebase`, `test_audit_integrity`, `test_decision_limits`, `test_operator_events_view`, `test_cc22_multiround_e2e`, **`test_engine`, `test_calibration`** | **300 tests, 175.780s, OK** |
| 4 | `manage.py makemigrations --check --dry-run` (DB env on a dead socket) | `No changes detected`, exit 0 |

I added `test_engine` and `test_calibration` to the regression set for this
rework specifically, because it changed four engine files on the demand path.

**Read-inventory drift, resolved.** The first regression pass on this base
failed twice in `SensitiveReadInventoryTests`. Diffing the live scan against the
checked-in file showed the route set was **identical** (33 sensitive / 32
logged, nothing added or removed, my results route still `category: audit`,
`logged: true`); only `url_conf_route_count` differed, because the merged
legacy-engine removal deleted routes. Regenerating changed exactly one line,
`781 → 778`. The stale count was also what made the middleware fall back to a
live rebuild, which was the second failure. The `31 → 32` constant is confirmed
correct rather than merely made to pass: upstream at `4d2169c` has `logged: 31`
and asserts 31; the live scan here reports 32 — the single route I added.

**The focused tests fail without the change**, established against the original
baseline: `price_band.py` does not exist at `cbe2656`, and `_apply_price_band`
and `price_band_pct` each occur **0 times** there.

**Untouched:** the seven pre-existing full-suite failures (V2-071/V2-074) are
outside these labels and were neither run nor repaired.

---

## 5. What each test proves

| Behaviour | Tests |
|---|---|
| Out-of-band → alert, number kept, nearer edge at deadline | `test_an_out_of_band_price_alerts_and_names_the_legal_range`, `test_the_teams_number_is_kept_while_the_round_is_open`, `test_a_price_above_the_band_moves_to_the_upper_edge`, `test_a_price_below_the_band_moves_to_the_lower_edge`, `test_the_nearer_edge_is_chosen_not_always_the_floor` |
| Blank on a **selling** product → floor | `test_a_blank_price_on_a_selling_product_is_warned_about_the_floor`, `test_a_blank_price_on_a_selling_product_is_filled_at_the_floor` |
| Blank on a **never-sold** product → **not for sale, round resolves** | `test_a_blank_price_with_no_previous_price_asks_the_team_to_set_one`, `test_a_blank_on_a_never_sold_product_is_recorded_as_not_offered` (price still null, row **not deleted**, receipt under `RULE_NOT_OFFERED`, `applied_price` null), **`test_a_round_with_an_unpriced_never_sold_product_still_resolves`** (`_run_phase_1` does not raise; the product is allocated no demand) |
| Nothing is invented | `test_an_unmarketed_product_market_gets_no_row_and_no_price`, `test_a_team_with_no_submission_at_all_is_left_alone`, `test_the_floor_is_withheld_without_a_real_prior_round_price` |
| Precondition = skipped deadline only | `test_a_skipped_deadline_is_still_refused_as_defence_in_depth` |
| Lock-time refusal kept | `test_locking_with_an_unpriceable_blank_is_still_refused` |
| Blank representable | `test_a_marketing_row_can_be_stored_with_no_price`, `test_the_serializer_accepts_an_absent_price`, `test_a_stated_price_of_zero_is_still_refused`, `test_a_negative_price_is_still_refused` |
| In band | `test_an_in_band_price_says_nothing`, `test_an_in_band_price_is_used_as_entered_and_audits_nothing` |
| Round-1 anchoring | `test_round_one_anchors_to_the_authored_starting_price`, `test_the_anchor_is_the_most_recent_earlier_round` |
| Band authored, not constant | `test_the_width_comes_from_the_scenario_not_a_constant`, `test_an_authored_zero_means_no_band_rather_than_an_inverted_one` |
| Published round immutable | `test_a_processed_round_is_not_repriced`, `test_closing_twice_adjusts_once` |
| Bilingual | `test_the_alert_is_available_in_chinese`, `test_the_adjustment_reads_back_to_the_team_in_both_languages`, `test_the_not_offered_receipt_reads_back_in_both_languages` |
| Team told why, on its own screen | `test_the_team_is_told_why_on_its_results_screen` — authenticated request to the results endpoint, asserting `rule == RULE_NOT_OFFERED`, null `applied_price`, and the message naming the product |

### Cross-team leakage (rework 1, item 3)

- `test_both_teams_were_adjusted_so_the_test_can_actually_leak` — control.
- `test_a_team_sees_only_its_own_price_adjustments`.
- `test_a_team_with_no_adjustments_gets_an_empty_list_not_a_missing_key`.
- `test_a_rivals_student_cannot_read_this_teams_adjustment_payloads` — asserts
  **403 explicitly**. `RoundResultsView` declares no permission class; the
  refusal comes from `TeamScopeGuardMiddleware`. My first version asserted only
  that the rival "did not see 'Aurora'", which would have passed on a 500 and
  proved nothing.
- `test_the_owning_teams_student_is_allowed_through_the_same_guard` — the
  control that keeps the 403 meaningful.

---

## 6. Findings — register entries handed over

**I did not edit `V2_FINDINGS_REGISTER.md`.**

| ID | Area | Sev | Owner | Description | Evidence | Status |
|---|---|---:|---|---|---|---|
| *(next)* | Read authorisation / defence in depth | **P2** | CRV2-08 boundary | `RoundResultsView` declares no `permission_classes`; its team-ownership check comes solely from `TeamScopeGuardMiddleware`. The guard works and is now tested, but the view is one middleware-ordering change from serving one team's audit payloads to another. Stage 5 raised the stakes by routing adjustment payloads through it. | `results_api.py:85-91`; `middleware.py:210-277`; the 403 test above | Open |
| *(next)* | Audit correlation | **P2** | CRV2-04 boundary | Price-band events carry `request_id=''`, so they cannot be correlated by id with the operator close that caused them. Pre-existing shape — `_lock_all_submissions`'s own events share it. | `advance_round._apply_price_band` vs `services/lifecycle.request_id_for` | Open |

**Withdrawn:** *stale `route_inventory.json`* (resolved upstream — the rebase
brought the regenerated file; the freeze regression is green) and *blank rule
distorts rival demand* (**closed by rework 1** — no row is invented, so the
distortion cannot arise).

---

## 7. Rules-owner questions

**Answered by the owner:** what "blank" means (rework 1), and **Q4** — an
unpriceable blank is not for sale and the round must resolve (rework 2). Both
implemented as ruled.

**Q1 — what anchors a product with no prior-round price?** *Default:* the
authored `reference_price_<positioning>`. It states a legal *range* to a team
pricing a new product and, after the narrowing, deliberately does **not**
license the system to price on their behalf. Reversible in one function.

**Q2 — a market just entered?** Identical to Q1.

**Q3 — per product-market or per product?** **Per product-market**; both tables
are keyed that way.

**Q5 — does the deadline bind a team that locked early?** Yes.

**Q7 — NEW, and it is a decision I made.** A team produces units for a product
that then turns out not to be for sale. I kept the row in `revenue.py`, so the
team **still pays COGS and carries the unsold units as inventory**; only the
revenue is zero. The alternative — skipping the row — would silently refund a
production decision the team really made. I think charging is right, but it is
a rules call and it is yours: if production for an unoffered product should
cost nothing, that is a one-line change in `revenue.py`.

**Q6 — for the record:** BECSR refuses out-of-band prices; Ruling 2 substitutes
and audits. A deliberate divergence, implemented as ruled.

---

## 8. Delta for the GSP-CRV2-08 owner

**New dispute-2 cases — now three shapes**, all answerable the same way: an
out-of-band price moved to the nearer edge; a blank price on a product already
selling, filled at the floor; and **a product not offered for sale at all
because it could not be priced**. For each: the team sees it in
`price_adjustments` on `GET .../results/round/<n>/` in EN or zh-CN; the
operator sees the `DecisionAuditEvent` with `actor: 'system'`, the action, the
server timestamp, `endpoint='engine:close_round'`, `payload_sha256` and the
full payload; and the record cannot be edited afterwards.

No CRV2-08 evidence is invalidated — its disputes were not replayed and its
game was not rebuilt. **Not walked through a live operator stack** (§9).

---

## 9. Rollback, and what is not proven

**Rollback.** `git revert 49ea50b a9b4039 be0fa86` removes the band. Migration
`0085` reverses cleanly, but **only after confirming no `retail_price` is
null** — and note that the not-for-sale rule means a resolved round can now
legitimately *contain* nulls, so a downgrade must price or delete those rows
first. This is the one rollback hazard worth flagging. `read_inventory.json`
and the middleware count revert with the code; the `price_band_pct` YAML
entries are additive and inert once the code is gone. Audit events are
immutable by design and remain as the record.

**Not proven — I claim no gate is closed:**

1. **The frontend was not built, linted or exercised.** `node_modules` is
   absent in this worktree (re-checked after both rebases), so no
   `react-scripts build`, no lint, no browser verification. The JS is
   syntactically reviewed and both locale files parse with EN/zh-CN key parity,
   but a backend 200 is not evidence of frontend completion
   (STANDING-DISCIPLINE §5). **The student-visible half — the legal-range hint,
   the blank alert, the "clear the price box" interaction, and the results-screen
   notice — is unverified in a browser.** That interaction is the thing I would
   most want a human to click before a competition.
2. **The new dispute-2 cases have not been walked through a live operator
   stack**; they are proven by focused tests only.
3. **No full suite, load run, concurrency matrix or determinism replay**, per
   the verification budget. The seven V2-071/V2-074 failures were not run or
   touched.
4. **Q7 is a rules call I made**, not one I was given.

**Commit hygiene.** All commits used `--no-verify`. The vendored `aide-checks`
pre-commit runner refuses on a revision mismatch; its own header documents
`--no-verify` as the sanctioned bypass and names the deploy gate as the
non-bypassable layer, and nothing here deploys. One factual note:
`checks/.aide-checks-rev` is **present** in this worktree and at the base (it
reads `e710f26`); the runner reports a revision *mismatch* against it rather
than an absent file. Re-vendoring remains outside this handoff.
