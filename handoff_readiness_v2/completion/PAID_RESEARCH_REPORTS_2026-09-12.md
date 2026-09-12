# Paid market research — completion report

Date: 2026-09-12. Branch `crv2-paid-research-reports`, based on `e1b744c`.
Builder report. **No gate is claimed closed here; this is for audit.**

Market research was always intended to cost money. The rails existed and were
wired to zero: `research_expense` is read by `engine/financials.py:96` into
`total_opex`, carried into operating income, cash and
`RoundResultFinancials.research_expense` — and `engine/costs.py:650` handed it a
hardcoded `D('0')` because nothing ever produced a figure. The mechanic is now
built end to end.

---

## 1. Inventory

`handoff_readiness_v2/evidence/decision-rules/paid-research/RESEARCH_SURFACE_INVENTORY.md`

Built from the registries before implementation: `core/urls.py` (781 routes),
the model registry, `manifest_sections.py`, `read_inventory.json`,
`route_inventory.json`, and a frontend grep. 22 rows, each mapped:

| Disposition | Count | Rows |
|---|---|---|
| changed | 13 | A1, A2, B1–B4, C3–C5, D2–D4, D6, D7, E2 |
| covered | 5 | B6, C1, C2, C6, D1, E1 |
| exempt (with rationale) | 4 | A3, A4, B5, C7, C8 |

Exemptions and why: the analyst-query *history* endpoint (A3) re-reads answers
already paid for — charging again would break both "bought once" and post-close
readability; the instructor view (A4) is oversight, not a team purchase;
`bootstrap.py:243` (B5) seeds round 0, which precedes any submission; the top
strip (C7) and the Finance allocation inputs (C8) show *declared* buckets, and
adding a research input there would re-introduce the bucket as a cash gate,
which rule 5 forbids.

## 2. Model decision — a new table, not an extension

**Decided: new model `DecisionResearchPurchase`** (`core/models/research.py`),
leaving `DecisionResearchAllocation` untouched.

The handoff said extending is cheaper "unless report purchases aren't
market-scoped". They are not. Only 2 of the 6 purchasable items (`segments`,
`channels`) are market-scoped; `products`, `markets`, `stakeholders` are
whole-game reports and an analyst query is a question, not a market.

`DecisionResearchAllocation.market` is `NOT NULL`/`PROTECT` **and** is half of a
live manifest natural key (`('submission_id','market_id')`). Extending would
have meant making a natural-key column nullable. PostgreSQL treats NULLs as
distinct, so the unique constraint that enforces "bought once per round" would
have silently stopped enforcing it for exactly the reports that are not
market-scoped. Widening a determinism natural key to hold a value it cannot
identify rows by is the more expensive change, not the cheaper one.

The new table uses a `scope_key` string rather than the nullable FK as its
uniqueness/natural-key column: the market code for a market-scoped report, `''`
for a whole-game report, and the query ordinal for an analyst query. `market`
is kept as a real FK for referential integrity and the admin. Unique on
`('submission','report_type','scope_key')`.

Per R16 there is now **one** path per fact: the allocation table stays
unread/unwritten exactly as it was, and purchases live in their own table. No
half-wired second path.

## 3. The catalogue, and whether each report is worth money

Assessed from `core/views/research_reports.py` as it stands.

| Report | What it actually tells a team | Worth paying for? |
|---|---|---|
| `segments` | Named top competitor and their share, the team's rank among all teams, an "underserved" flag derived from every team's share, plus authored population, growth, price sensitivity and top-valued features | **Yes.** Real competitive intelligence a team cannot otherwise get. |
| `stakeholders` | Non-customer satisfaction, and a per-feature gap table against the authored `ideal_value` and weights that drive scoring, with a 4-round trend | **Yes.** Exposes authored scoring targets that are otherwise hidden. |
| `markets` | Tariff/FX/tax/regulatory/infrastructure/entry cost, a 4-round FX trend, total market size across all teams, competitor count | **Qualified yes**, at a lower price. Much of it is static scenario reference data; the FX/tariff trend and competitor count are the genuinely paid part. |
| `products` | Almost entirely the team's **own** data — own products, own feature levels, own units/revenue/margin. The only outside signal is `market_rank` against other teams' revenue | **Thin.** This is largely a team reading its own file back. Recommend a low price, or enrich it before charging full price. |
| `channels` | A **hardcoded constants table** (`BASE_REACH` and a literal `channel_comparison` list with fixed reach/margin/fit values), plus the team's own current strategy | **No — recommend price 0 as it stands.** It contains no competitive and no scenario data. It is a rules explainer wearing a report's clothes. To justify a price it would need real per-market channel economics or observed competitor channel behaviour. |
| `analyst_query` | LLM/RAG answer over the article corpus | **Yes**, and it is the one item with a real marginal cost per use. Priced per question, not bought once. |

Per the owner's instruction only the final prices are deferred, so all six are
seeded at the same placeholder. The `channels` recommendation above is a
recommendation, not a unilateral change.

## 4. Authored price keys and placeholder values

Authored per scenario, read through `core/engine/utils.py::get_config`.

| Key | Placeholder |
|---|---|
| `research_report_price_segments` | `'50000'` |
| `research_report_price_products` | `'50000'` |
| `research_report_price_markets` | `'50000'` |
| `research_report_price_channels` | `'50000'` |
| `research_report_price_stakeholders` | `'50000'` |
| `research_analyst_query_price` | `'50000'` |

Seeded in all three scenario YAMLs and, for existing databases, by
`0086_paid_research_reports` (`get_or_create`, and the reverse deletes only rows
carrying the placeholder value, so a calibrated price is never discarded).

**Correction to the handoff's premise:** `price_band_pct` **does not exist**
anywhere in the code, YAML or tests — it is an unimplemented Stage 5 plan
(`GSP-CRV2-10-decision-rules-and-economics.md:202`, V2-041 open). I followed the
shipped precedent instead: `reference_price_*` (V2-023), which is the same shape
— per-scenario key, string value, `[value, description]` YAML pair, data
migration for existing rows.

One deliberate deviation from that precedent, flagged as a question below:
`reference_price_*` is **fail-closed** (raises when unauthored). Report prices
fall back to `DEFAULT_RESEARCH_PRICE` instead, because a fail-closed price would
turn every existing test fixture that builds a `Scenario` inline without config
rows into a failure in other builders' suites. The test
`test_the_price_comes_from_the_scenario_not_a_constant` proves the scenario
value wins and explicitly asserts the figure under test is not the fallback.

## 5. The one-calculator invariant, shown in both places

The handoff labels this V2-024. **V2-024 is actually the equity-dominance
finding**; the "one calculator" doctrine is V2-037's repair plus the
`funding_need.py` docstring ("One calculator, not two") and V2-038 ("three rules
that disagree is one rule that does not exist"). The substance is implemented as
required; only the label is corrected.

Both halves read the **same rows** — not the same formula recomputed twice:

**Funding rule** — `core/services/funding_need.py::decision_outlays`:
```python
from core.services.research_catalogue import purchase_total
lines['research'] = purchase_total(submission)
```

**Engine** — `core/engine/costs.py::calculate_operating_expenses`:
```python
from core.services.research_catalogue import purchase_total
research_expense = purchase_total(submission)
```
and `'research_expense': research_expense` replaces the hardcoded `D('0')`.

Crucially, the existing V2 parity assertion compared only
`rd + platform_capex + marketing`, so adding a research line would **not** have
tripped it. I widened the assertion itself, so the invariant is now *enforced*
for research rather than merely satisfied:
```python
_shared = (_outlays['rd'] + _outlays['platform_capex']
           + _outlays['marketing'] + _outlays['research'])
_engine = (rd_expense + platform_capex + marketing_expense
           + research_expense)
if _shared != _engine:
    raise AssertionError(...)
```

Prices are frozen onto the purchase row, so both sides read the price actually
charged and a later calibration cannot restate an already-resolved round.

**Affordability uses the one existing rule, not a second copy.** The purchase
writes its row inside a transaction, asks `rd_costs.budget_assessment` whether
the team can still afford what it has committed, and rolls the row back if not.
Research purchases are a new committed line in `committed_outlay`, in exactly
the position `platform_development` occupies — and deliberately **not**
`research_budget`, which stays a declaration feeding coherence scoring
(A5/R14: budgets declare, decisions spend).

## 6. Behaviour

- **Delivered immediately, charged at resolution.** The row is written at
  purchase; the cash moves in the engine with every other outlay.
- **Bought once per round**, enforced by a database unique constraint, per
  report type and per market where market-scoped. Re-reading or re-posting
  charges nothing; a racing double-click is resolved by the constraint.
- **Affordability before delivery.** A refused purchase writes nothing and
  delivers nothing.
- **GET never charges.** Purchase is an explicit POST. This matters: the
  `markets` report is fetched by `StrategyToolsPage.js` four times and by the
  Segments/Channels market dropdowns. An unbought `markets` GET still returns
  market names and codes so that navigation keeps working; the paid analysis is
  what is withheld.
- **Post-close readable.** Access is granted by a purchase in the round being
  viewed as well as the current one, so a report bought in round 3 is still
  readable when round 3 is viewed after close and after the game completes
  (CRV2-08). It is deliberately *not* granted across all rounds — the content
  changes each round, and one purchase must not buy every future edition.
- **Audited.** Every purchase writes a `DecisionAuditEvent`
  (`action='purchase_research_report'`) via `record_decision_event`, the same
  path every other decision write uses. A refused purchase writes none, per R21.
- **R7:** the round is the game's current round; the request body cannot name one.
- **R13:** the new model is registered `CompetitionReadOnlyAdmin`.
- **V2-037:** a client-submitted price that disagrees with the authored one is
  refused with the authored figure named, never silently corrected.

## 7. Determinism / manifest impact — a deliberate boundary change

- New section `decision_research_purchase` in `DECISION_SECTIONS`, natural key
  `('submission_id','report_type','scope_key')`.
- **`MANIFEST_SCHEMA_VERSION` bumped 5 → 6.** A new output section changes what
  bytes a round hashes to, which the module docstring names as exactly when to
  bump; V2-052 forbids redefining a version in place.
- `manifest_schema_v6.json` generated (102,023 bytes, sha256
  `61a7a504f294ef56f181b23fabb739d4fffb31aad764570d34f0f85287659f1b`) and
  recorded in `manifest_schema_history/PROVENANCE.json`.
- `EXPECTED_OUTPUT_SECTIONS` in `test_manifest_determinism.py` extended.
- `research_catalogue.py` added to `RESOLUTION_SERVICES` — the engine now
  imports it, and the ordering scan's scope follows the code.
- `read_inventory.json` regenerated (32 sensitive read routes, unchanged).
- `route_inventory.json` regenerated: 222 mutating routes, 38 lifecycle-mutating,
  **0 unguarded** — see below.

**Consequence to expect (R11's warning):** any hash comparison across this
change shows every round differing even where no outcome differs, because the
envelope gained a section.

**A real defect found and fixed on the way.** Regenerating the route inventory
showed `unguarded` going 0 → 2. It was not a scanner false positive: the
purchase view calls `DecisionSubmission.objects.get_or_create(...)`, genuinely
creating a lifecycle row, and adding the charge to `ResearchQueryView` made it
do the same — both outside the lock every other student decision write takes.
Fixed by putting both on `CompetitionDecisionWriteMixin` rather than writing an
exemption. `unguarded` is back to 0 and `guarded` rose 20 → 22.

## 8. Tests

All via `backend/scripts/test-postgres` (own disposable PostgreSQL container)
under `flock -w 1800 /tmp/globalstrat-backend-test.lock`. The production
database at 192.168.50.38 was never used; no systemd environment file was read.
`DB_PASSWORD` was set to a throwaway value for the metadata-only management
commands, which open no connection. **The full backend suite was not run** —
CRV2-09 owns it.

| # | Command (labels) | Tests | Time | Result |
|---|---|---|---|---|
| 1 | `test_paid_research test_manifest_determinism test_funding_need test_rd_costs test_participant_messages test_decision_limits` | 130 | 19.218s | **FAILED (1)** — `test_the_scanned_service_list_is_what_the_engine_actually_calls`: the engine now imports `research_catalogue`. Fixed by adding it to `RESOLUTION_SERVICES`. |
| 2 | the six above **+** `test_operator_concurrency test_audit_integrity` | 219 | 167.897s | **OK** |
| 3 | `test_paid_research` (after adding the P&L/cash test) | 17 | 0.436s | **OK** |
| 4 | all eight modules (final) | 220 | 184.535s | **OK** |

Also run: `manage.py check` — no issues (twice); `dump_manifest_schema`,
`dump_read_inventory`, `dump_route_inventory`.

**Tests fail without the change.** The new module asserts behaviour that did not
exist: before this branch the reports were free and unlimited, `research_expense`
was hardcoded to zero, and `DecisionResearchPurchase` had no table.

Coverage of the handoff's required list, in `core/tests/test_paid_research.py`
(17 tests):

- charges exactly once and appears in **both** calculators —
  `test_a_purchase_appears_in_both_calculators` runs `decision_outlays` *and*
  `calculate_operating_expenses`, so the widened parity assertion is itself
  under test; `test_a_purchase_is_charged_exactly_once`
- re-opening charges nothing — `test_reopening_a_bought_report_charges_nothing`,
  `test_a_market_scoped_report_is_bought_per_market`
- unaffordable refused, delivers nothing —
  `test_an_unaffordable_purchase_is_refused_and_delivers_nothing`
- **P&L and cash move by the authored price** —
  `test_the_pnl_and_cash_move_by_the_authored_price`: two identical teams, one
  of which bought a report, asserting `operating_income` and `cash_closing`
  differ by exactly the price, so the test measures the charge and not the rest
  of the round
- audited — `test_a_purchase_is_audited`; and
  `test_a_refused_purchase_writes_no_audit_event`
- price from the scenario, not a constant —
  `test_the_price_comes_from_the_scenario_not_a_constant` (asserts the figure
  used is not the fallback), `test_the_charged_price_is_frozen_against_later_calibration`
- readable after close —
  `test_a_bought_report_is_still_readable_after_the_round_closes`, with
  `test_a_report_bought_in_an_earlier_round_is_not_free_in_a_later_one`
- refusal language — `test_the_refusal_is_in_business_language` (asserts no
  storage identifier leaks) and `test_the_refusal_is_localised`

## 9. What is NOT verified

**The frontend is entirely unexecuted.** `node_modules` is absent in the
worktree, so nothing was built, linted, rendered or snapshot-tested. I am not
claiming it works. Specifically unverified:

- that `MarketResearchPage.js` compiles — the JSX changes were written by hand;
- that `ReportPaywall` renders, that the Buy button's request succeeds against
  a live server, or that the paywall branch is reached in each of the five tabs;
- that `BudgetBar` / `DSBudgetBar` render a fourth category correctly at any
  width, or that `--color-header-neutral` reads well beside the existing three;
- that `refreshBudgets()` after purchase updates the top bar in a real session.

What *was* verified about the frontend, mechanically: both locale files parse as
JSON, and the `market_research` blocks have exact EN/ZH key parity (138 keys
each, zero one-sided keys), including all nine new keys.

**Also not covered:**

- **The analyst query's price is not shown in the UI.** No endpoint publishes
  it — the reports endpoint returns a price per *report type*, and the analyst
  tab does not fetch a report. The charge happens and the refusal names the
  price, but a team does not see the price before asking. This is a real
  shortfall against "price shown before buying" and needs either a catalogue
  endpoint or the price folded into an existing analyst payload.
- No replay regression was run. Per R18, a change inside the CRV2-01
  determinism boundary warrants a focused replay; this change alters the
  envelope (§7) and one was not performed.
- `MarketResearchPage.js` still hardcodes `MAX_QUERIES = 5` rather than reading
  `max_research_queries_per_round`. Pre-existing; untouched.

## 10. Rollback

Self-contained on `crv2-paid-research-reports`; nothing was pushed and no other
worktree was touched. 25 files changed, 6 added (+650/−39).

- Whole feature: revert the branch. The two new tables/files
  (`core/models/research.py`, `core/services/research_catalogue.py`) are
  referenced only by the code added here, plus one import line in
  `core/models/__init__.py`.
- Schema: `0086_paid_research_reports` reverses cleanly — it drops the table and
  removes only price rows still carrying the placeholder value.
- **Turning research free again without reverting code:** set the six price keys
  to `'0'`. The mechanic keeps working, the charge becomes zero, and the
  determinism envelope is unaffected.
- The manifest version bump is the one change that is not cheap to undo: v6 has
  a recorded provenance entry, and per V2-052 a version's definition is evidence
  and must not be rewritten. Reverting means bumping to 7, not deleting 6.

## 11. Findings to register (not entered by me — the register is yours)

1. **`price_band_pct` does not exist.** The handoff's cited precedent is an
   unimplemented Stage 5 plan (V2-041 still open). Anything else citing it as
   landed is wrong. P2 (documentation), but it misdirects builders.
2. **The `channels` report is a hardcoded constants table.**
   `research_reports.py:454-522` — `BASE_REACH` plus a literal comparison list.
   It contains no scenario or competitive data and cannot honestly be sold. P2.
3. **The `products` report is mostly the team's own data**, with `market_rank`
   as the only outside signal. Sold as research, it is a mirror. P2.
4. **`research_allocated` was emitted and rendered nowhere.** Both backend
   payloads published it; grep across `frontend/` returned zero hits. Research
   spend was invisible on every screen. Fixed here. P2.
5. **`StakeholdersTab` had no `.catch`** (`MarketResearchPage.js:916`), so any
   refusal left the tab on "Loading stakeholder data..." indefinitely. Fixed
   here. P2, participant-facing.
6. **Two lifecycle-mutating routes were unguarded** once research became a
   write. Found by the route inventory, fixed with the boundary (§7). Worth a
   register line because the inventory earned its keep.
7. **`cc32b_views.py:141-149` charges cash directly** —
   `team.cash_on_hand -= cost; team.save()` inside a view, outside the engine
   and outside `decision_outlays`. That is precisely the second cash path the
   one-calculator rule forbids, and it is *not* mine. **P1 candidate**, worth a
   look independently of this handoff.
8. **V2-057's open question is now materially different.** Research purchases
   are a separate committed line; `research_budget` remains a declaration that
   the API cannot write and the engine never charges. The question of whether
   that bucket should count toward committed spend at all is still open and now
   cleanly separable.

## 12. Questions for the rules owner

1. **Final prices.** All six are a uniform `50000` placeholder. Calibration is a
   data-only change to the YAMLs plus one migration.
2. **The analyst query is charged per question, with a quota of 5 per round.**
   At the placeholder that is up to $250,000 per team per round — plausibly the
   largest research line in the game. Is per-question charging the intent, and
   is the quota still the right cap once it costs money?
3. **Should `channels` be priced at 0** until it carries real data (§3)?
4. **Should report prices be fail-closed** like `reference_price_*`, instead of
   falling back to a default (§4)? Fail-closed is the stricter V2 norm; it would
   require adding config rows to a number of existing test fixtures.
5. **Is per-round re-purchase right?** A report bought in round 3 is readable
   for round 3 for ever, but round 4's edition must be bought again. That is
   what makes a per-round charge meaningful, but it is a rules choice.
6. **Is the unbought `markets` identity list acceptable?** Names and codes are
   returned unpaid so other screens' market pickers keep working. I judged this
   scenario identity rather than paid intelligence; it is a disclosure call.
7. **R19 note:** the owner instruction behind this work reached me through the
   handoff, not through a dated `OWNER_RULINGS_*` document. It should be
   recorded in one to count as a ruling.

## 13. Integration notes for whoever merges

- **Migration numbering.** `crv2-10-stage5-price-band` holds
  `0085_price_band_blank_price`; mine is `0086_paid_research_reports` and also
  depends on `0084`. Merging produces two leaf nodes and needs a merge
  migration — deliberate and visible, rather than a filename collision.
- **`PROVENANCE.json` carries `"commit": "PENDING"` and
  `"canonical_is": "PENDING"` for version 6.** These are stamped with this
  branch's commit sha in a follow-up commit on the branch; if the branch is
  rebased or squashed at integration, re-stamp them to the sha that actually
  lands. The recorded `sha256` of `manifest_schema_v6.json` is correct and is
  what `test_every_recorded_definition_still_hashes_to_its_record` checks.
- **Files also touched by other branches** (kept minimal and appended at the end
  of their blocks): `participant_messages.py`, the three scenario YAMLs, both
  locale files, `read_inventory.json`, `route_inventory.json`. Avoided entirely:
  `core/serializers/decisions.py`, `core/engine/bootstrap.py`,
  `core/models/decisions.py`. `core/views/decisions.py` has exactly two
  additions, both a single `research_spent` key beside the existing
  `research_allocated`, without which the charge is invisible on every screen.
- Committed with `--no-verify`: `checks/.aide-checks-rev` pins `e710f26` and the
  runner is built from the branch, so the hook refuses on a vendored-revision
  mismatch. The hook's own header sanctions the bypass and names the deploy gate
  as the non-bypassable layer.
