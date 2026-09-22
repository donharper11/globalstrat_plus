# Silent section saves — two decisions no student could make

**Date:** 2026-09-21 (runs finished 2026-09-22 UTC)
**Branch:** `crv2-13-silent-section-saves`, cut from `crv2-release-integration` at `62a27cd` (verified an ancestor before anything was touched)
**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`, owner ruling R17
**Input:** finding F1 of `BOUNDED_NUMBER_INPUTS_2026-09-21.md`; the V2-107 register cell (a student's decisions silently lost while the screen reported success); the V2-064 repair (`OPEN_INTERFACE_DEFECTS_2026-09-17.md`).

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md` and the `OWNER_RULINGS` files were not edited; §9 proposes register text for the auditor to apply or reject.

Commits (oldest first):

| Commit | What |
|---|---|
| `4ac2f3f` | Backend: `talent-allocations` and `compliance-investments` accepted on the per-type route; the allocation rules made to run on both routes; the pair judged together; two catalogue entries; `core/tests/test_silent_section_saves.py` |
| `b3fcdbb` | Frontend: the two pages send the shape the server takes and read it back; `useSectionAutosave`; per-request refusals in `api/saveFailures.js`; every swallowed save catch repaired; `DraftRefreshOnNavigate`; `decisionSaveCatchScan.test.js`; `sectionPayloads.test.js` |
| *(next)* | This document |
| *(last)* | Regenerated string inventory, in its own commit |

No runtime code changed after the full backend run in §5 began.

---

## 1. Driving the two saves through the real route (before)

`core.tests.test_silent_section_saves` at `62a27cd`, with only the test file added: **39 tests, 31 failures, 7 errors** (`scratchpad red_backend.txt`, 13.4 s). The two headline assertions:

```
test_the_section_is_accepted_and_stored (ComplianceInvestmentRouteTests)
AssertionError: 400 != 200 : {'detail': 'This decision section is not available. Refresh the page and try again.'}
test_the_section_is_accepted_and_stored (TalentAllocationRouteTests)
AssertionError: 400 != 200 : {'detail': 'This decision section is not available. Refresh the page and try again.'}
```

Every lock, closed-round and validation refusal in the file failed the same way: the route never got past `unknown_decision_type`, so none of the guards on a decision write had ever applied to these two sections, and none of the serializer's own rules had ever run.

Two things the previous builder had not recorded:

- **The allocation rules had never run on any route.** `TalentAllocationSerializer.validate` reads `self.context['submission']`; the whole-submission route never supplied it, so `PUT .../decisions/round/1/` stored any allocation at all — 1 at HQ, 49 in a market, or 500 staff against a headcount of 50 — and `ADVERSARIAL_BALANCE_INVENTORY.md §3b` recorded that route as the one place the section was reachable. Pinned red by `test_the_whole_submission_route_applies_the_same_rule`.
- **Team notes could block the lock.** `SummaryPage` sent `team_notes` to the `budget` section. `DecisionBudgetAllocationSerializer` requires its three budgets, so a team that had typed any note had its lock refused with three `This field is required.`, and the page fell through to its generic "lock failed" sentence. Pinned by `TeamNotesTests`.

## 2. Inventory — every student decision write, at `62a27cd`

Built from `_TYPE_MAP` (`core/views/decisions.py`), every `CompetitionDecisionWriteMixin` view in `core/urls.py`, and every write call under `src/pages` and `src/contexts`. "Loaded back" says whether the page re-reads what it saved.

### 2a. Per-type route `PATCH .../decisions/round/N/<section>/`

| Page : line | Section sent | Accepted at `62a27cd` | Failure surfaced or swallowed | Loaded back | Now |
|---|---|---|---|---|---|
| `CorporateStrategyPage.js:689` | `talent_allocations` | **refused, every call** (`unknown_decision_type`); payload a dict keyed by pool, serializer takes a list | **swallowed** (`catch { /* ignore */ }`) | from `context/talent-allocation/` `draft_allocations` — correct shape, but nothing was ever stored | **repaired** — sent as rows with staffing, to `talent` |
| `MarketStrategyPage.js:438` | `compliance_investments` | **refused, every call**; payload `{code: amount}`, serializer takes `[{market, investment_amount}]` | **swallowed** | read as `draft.compliance_investments[code]` from a **list** — always 0 even had a row been stored | **repaired** — `compliance-investments`, rows by market id, read back by id |
| `CorporateStrategyPage.js:697` | `talent` | accepted | **swallowed** | yes (`context/talent/`) | repaired (shared hook) |
| `CorporateStrategyPage.js:864..981` | `esg` | accepted | **swallowed** | yes (`draft.esg`) | repaired (shared hook) |
| `CorporateStrategyPage.js:338` | `acquisitions` | accepted | **swallowed**; list rebuilt from a draft read once a session, so a second acquisition replaced the first | yes, stale | repaired (local list; draft re-read on navigation) |
| `MarketStrategyPage.js:482,602,641,684` | `market-entry`, `plants`, `partnerships` | accepted | **swallowed**; one timer for the page, so an edit to another section inside 2 s cancelled the pending save | yes | repaired (one timer per section) |
| `StrategyPage.js:105..366` | `market-entry`, `financing`, `plants`, `partnerships`, `esg` | accepted | **swallowed** | yes | repaired — but this page is **routed nowhere** (`App.js` imports it not); dead code, like `GameStatusBar` |
| `FinancePage.js:149,170` | `budget`, `financing` | accepted | surfaced, in the page's own hardcoded-English line | yes | unchanged (see §7) |
| `ProductsPage.js:53,106,111,134` | `products`, `product-retires` | accepted | **swallowed** ×3; modal closed only on success, so a refusal left it open with no explanation; list rebuilt from a stale draft, so a second product created in one sitting was sent as `[second]` | `context/products/` for products; `draft.product_creates` stale | repaired (server sentences in the modal; draft re-read after every save) |
| `RDPage.js:90` | `platforms` | accepted | bound, **unused**: a generic "Failed to create platform" hid the server's reason | yes | repaired (server sentences) |
| `RDPage.js:414` | `rd` | accepted | surfaced (`detail`) | yes | unchanged |
| `MarketingPage.js:148` | `marketing` | accepted | surfaced with retry (V2-107) | yes | unchanged |
| `SummaryPage.js:91` | `budget` carrying `team_notes` | **refused whenever notes were typed** — three required budgets missing; notes not a field of that section | surfaced as a generic lock failure | **never** — the box was empty on every reload | **repaired** — notes go to the whole-submission route; read back from `draft.team_notes` |
| — | `event-responses`, `product-retires` (direct), `platforms` (`rd`) | accepted | no page sends `event-responses` at all | — | unchanged |

### 2b. Other student writes (`CompetitionDecisionWriteMixin` views)

| Page : line | Route | Accepted | Failure | Now |
|---|---|---|---|---|
| `FinancePage.js:199` | `POST context/tax-structure/` | accepted | **swallowed**; not a `/decisions/` URL, so the interceptor did not announce it either | repaired: counted as a decision write; page reports what the interceptor cannot see |
| `CommunicationsPage.js:64` | `POST communications/<id>/draft/` | accepted | **swallowed**; same | repaired, same |
| `CommunicationsPage.js:74` | `POST communications/<id>/submit/` | accepted | surfaced (`alert(detail)`) | unchanged |
| `CorporateStrategyPage.js:419` | `POST context/org-structure/` | accepted | surfaced (`Modal.error`, `data.error`) | unchanged |
| `MarketResearchPage.js:60,926` | research purchase / analyst query | accepted | surfaced | unchanged |
| `SourcingPage`, `LogisticsPage`, `TradeFinancePage`, `InventoryPage` | `POST sc/round/N/...` | accepted | surfaced (`serverErrors` + toast, 400/403 distinguished) | unchanged |
| `SummaryPage.js:93` | `POST .../lock/` | accepted | surfaced | unchanged |
| `StrategyToolsPage.js` ×4 | `POST tools/analysis/` | accepted | catch discards the error, but a toast says it failed; this is a worksheet, not a decision | left to the page (scanner exempts non-decision routes by URL) |
| `DecisionContext.js:156` | `POST .../decisions/round/N/` | accepted | surfaced (V2-064) — but `updateDraft` is called by no page, so unreachable | unchanged |

### 2c. `_TYPE_MAP` keys with no page

`event-responses`. Not a finding of this record; noted so the inventory is complete.

## 3. What was repaired, and how

### Backend (`4ac2f3f`)

- `_TYPE_MAP` gains `talent-allocations` and `compliance-investments`, spelled like the route's other hyphenated sections (`market-entry`, `product-retires`), with the serializers `_NESTED_CONFIG` already used. No new route: the same view, guards, throttle scope, `record_decision_event` and `DecisionChangeLog` apply.
- `validate_talent_allocations` (`core/serializers/decisions.py`) holds the rules that used to live unreachably in the serializer's `validate`: total equals the pool's headcount, at least a fifth (min 1) at headquarters, active markets only, plus a duplicate-pool refusal (the table is unique on `(submission, pool)`; the alternative was a 500). Both routes call it.
- **Staffing and allocation are judged together.** A `talent` save may carry `talent_allocations`; the pair is validated against the headcounts being saved and stored in one transaction. A `talent` save arriving alone is judged against the allocation already stored and refused if it would strand it (`talent_allocation_total`), because accepting it would leave staff deployed to markets who are no longer on the payroll. A `talent-allocations` save is judged against the stored staffing decision (`talent_decision_required` if none).
- `validate_compliance_investments`: one row per market, and only a market the team has an active presence in — `strategy_effects._process_compliance` reads a row only for an active presence, so any other row would be a decision the engine silently ignores. New sentence `compliance_market_inactive`.
- `TalentAllocationSerializer.validate_market_allocation`: the column is JSON and nothing checked its contents; it now requires whole, non-negative counts (a negative market count could otherwise balance a total that is not an allocation). New field label `market_allocation`.
- **Not changed:** the engine, `funding_need`, `costs.py`, the manifest sections, `MANIFEST_SCHEMA_VERSION` (still 6 — `ManifestTests` asserts it and that a re-save of the same decision hashes the same), `disclosure.py` (neither section is in `DEFAULT_UNLOCK_ROUNDS`, so both are available from round 1 on both sides), the route and read inventories (no route was added or changed).

### Frontend (`b3fcdbb`)

- `pages/sectionPayloads.js`: the two sections' send and read-back shapes, and the allocation arithmetic the screen needs now that the server enforces the total: moved staff come from headquarters, a headcount change is absorbed at headquarters, an untouched pool shows everyone at headquarters (what the engine assumes) and is not sent.
- `hooks/useSectionAutosave.js` replaces the three pages' private `autoSave`: one timer **per section**, failure announced to the shared notice, nothing sent once locked, pending saves not cancelled on unmount.
- `api/saveFailures.js` keeps **one refusal per request** rather than one in all. Before, any accepted decision write cleared the notice — a refused allocation followed by an accepted ESG save on the same page took the notice down with the allocation unsaved. `publishSaveSuccess(config)` clears only that request; with another still outstanding the listeners are told so again. The tax-structure choice and the communication draft now count as decision writes. `reportUnpublishedFailure(err)` lets a page's own catch announce a failure that never became a request (nothing for the interceptor to see) without announcing an interceptor-seen one twice.
- `components/DraftRefreshOnNavigate.js`: the stored submission is re-read on every move between student screens. The provider mounts once per session, so pages that rebuild a whole section from `draft` were building on the round as it stood at login. A refresh that finds nothing new keeps the same object, so a page is not reset for no change; a refresh that fails keeps what it had (blanking it would make the next replace-style save delete what the server holds).
- `SummaryPage`: notes to the whole-submission route, only when changed; read back.
- `ProductsPage`: the server's sentences inside the open modal (the shared notice sits behind it); the draft re-read after every save.
- `RDPage`: the server's sentences for a refused platform create.
- `decisionSaveCatchScan.test.js`: parses every file under `src/pages` and `src/contexts` with Babel and fails when a `try` around a student write has no `catch`, a `catch` that does not bind the error, or a bound error that is never used; likewise a `.catch(() => …)` chained onto a write. The scanner's own eight cases are asserted first. Direct `client.post` calls count when their URL is a decision route, so a page's worksheet notes are left to that page.
- `api/decisionSections.js` + `sectionPayloads.test.js`: every section a page names must be in the list; `SectionNamesAgreeTests` (backend) holds the list equal to `_TYPE_MAP`. A section added on one side and not the other fails a build rather than a student.

## 4. Red, then green

| Suite | At `62a27cd` + tests only | After |
|---|---|---|
| `core.tests.test_silent_section_saves` (backend) | 39 run: **31 F, 7 E** | 43 run (2 manifest, 1 names added): **OK** |
| `src/decisionSaveCatchScan.test.js` | **9 files flagged** (15 sites: Communications 1, Corporate 1, Finance 1, MarketStrategy 1, Products 3, RD 1, Strategy 1, StrategyTools 4 — the latter since exempted by route, DecisionContext 1) | all pass |
| `src/api/saveFailures.test.js` | 4 new fail (cross-section clearing, tax/draft routes, unpublished) | pass |
| `src/pages/sectionPayloads.test.js` | module absent; section scan would flag both old names | pass |
| `src/hooks/useSectionAutosave.test.js` | module absent | pass |
| `src/contexts/DecisionContext.test.js` | 3 new fail (cross-section notice, `loadDraft` refresh, failed refresh keeps draft) | pass |

Backend evidence in the same file: save, reload (submission GET and the page's own `context/talent-allocation/`), lock refusal, closed-round refusal (403), the lifecycle refusal with `code: lifecycle_in_progress` and nothing stored, another team's student (403), anonymous (401/403), the `decision_write` throttle scope, the audit event with endpoint and payload, over-maximum / inactive market / duplicate / negative / malformed JSON refusals in both languages with no English in a zh-CN response, and **one resolved round** (`ResolvedRoundTests`, `process_round` on `build_minimal_game`) where `TeamMarketCompliance` carries `cumulative_investment = 2,500,000.00`, `compliance_level = 0.39` (1 − e^−0.5 on the default 5,000,000 scale) and `effective_rd > effective_commercial > effective_operations` from allocations of 10 / 5 / 0 in the market — with a control round that saves nothing and reads 0 / 0 / equal.

## 5. Commands, results, durations

| Command | Result | Duration |
|---|---|---|
| `flock … scripts/test-postgres core.tests.test_silent_section_saves` (red) | 39 tests, failures=31, errors=7, exit 1 | 13.4 s |
| same (green, first) | 39 tests OK | 13.7 s |
| `… core.tests.test_silent_section_saves core.tests.test_numeric_refusal_language core.tests.test_zh_terminology core.tests.test_competition_locks core.tests.test_manifest_determinism core.tests.test_student_refusal_language core.tests.test_decision_limits` | 175 tests OK | 46.8 s |
| `flock … scripts/test-postgres core --parallel 8` (once, after the last runtime change) | 1489 tests OK, exit 0 | 125.0 s (2 min 23 s wall) |
| `CI=true npx react-scripts test --watchAll=false` (full) | 26 suites, 288 tests, all pass (was 22 suites / ~240) | ~40 s |
| `python3 backend/scripts/check-participant-strings` | exit 0 — 5216 units, 0 findings, 0 suppressions | — |
| `python3 backend/scripts/check-participant-strings-selftest` | exit 0 — 34 ok, 0 failed | — |
| `CI=false BUILD_PATH=<scratch> npx react-scripts build` then `node eslint-warning-count.js build.log` | build exit 0, "Compiled with warnings"; `eslint warnings: 55 (baseline 57)` — none in any file this branch adds; baseline not lowered (shared file, not my warnings) | 36 s |
| `git diff --check` | clean | — |

Line endings: every file touched was LF (`file` reported no CRLF among them) and stays LF.

### 5a. Full backend run

`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres core --parallel 8`, started 2026-09-22 00:24:19 UTC at `b3fcdbb`, after the last runtime change: **Found 1489 test(s) … Ran 1489 tests in 125.001s — OK**, exit 0; wall clock 2 min 23 s including the disposable PostgreSQL container. Run exactly once. No runtime code changed after it started.

## 6. What this invalidates in the stored evidence, and what changes for balance

- **`evidence/adversarial-balance/dimension-inventory.json`** and `ADVERSARIAL_BALANCE_INVENTORY.md §3b` enumerate `_TYPE_MAP` at their commit: 14 sections, with `compliance_investments` and `talent_allocations` recorded as "reachable only whole-submission". At this branch there are 16, and both are reachable per-type with rules the whole-submission route also applies now. That inventory is stale for this commit; it remains a true record of its own.
- **Balance.** Neither decision could be made by any team from the screen before this branch, so every playthrough, calibration and screening run to date was played with both levers at zero for every team. After it:
  - **Compliance investment is a live lever that costs nothing.** `ComplianceInvestment.investment_amount` is read by `strategy_effects._process_compliance` (raises `compliance_level` and, through it, trust and the localisation factor) and by the alliance engine's investment ratio, but it is **not** in `funding_need.decision_outlays` and **not** booked by `engine/costs.py` — the only compliance charge there is CC-18 detentions from `compliance_engine`. So a team may put up to $10,000,000 per market per round into compliance with no cash leaving the business. That was harmless while no team could do it; it is a free lever now. Per the brief I created no charge and no rule; **this needs the owner's ruling** (charge it — from which table, and whether it counts toward the equity funding need — or cap it, or accept it).
  - **Staff allocation** moves headcount the team already pays for, so it adds no spend. Its effect is the market localisation factor (`talent._calculate_market_talent_multipliers`) and the government-agent and investor-feature reads of `TalentAllocation`; with no rows the engine had been treating every team as fully at headquarters.
  - The manifest hashes the same tables it always did; a competition where teams use the levers will produce different section digests from one where they cannot, as it should. No replay evidence is invalidated by the schema (still 6).
- `evidence/player-language/STATIC_STRING_INVENTORY.md` regenerated in the final commit.

## 7. Broken, and not repaired here — precisely

1. **`FinancePage`'s own status line is hardcoded English** (`'Budget saved'`, `'Budget save failed'`, `'Unsaved financing changes'`, and `saveErrorMessage` prints `${firstField}: …` — a storage name) and is not cleared when a retry through the shared notice succeeds. Already on the record as `OPEN_INTERFACE_DEFECTS_2026-09-17.md §6.3`; the shared notice now stands beside it in the reader's language. Not changed here because it is a wording decision on a page whose refusals are not swallowed, and GSP-CRV2-12 wording is the owner's.
2. **Editing an existing product on `ProductsPage`** (`handleEditSave`, the non-pending branch) sends a new `product_creates` row carrying `existing_product_id`, which `DecisionProductCreateSerializer` does not declare and DRF drops. The server therefore treats a rename as creating a second product (refused as `product_name_taken` if the name is unchanged; a duplicate product if renamed). The refusal is now shown; the semantics are wrong and need a product-edit decision the serializer does not have. Out of this record's scope (not a save-path defect) and noted for the register.
3. **`StrategyPage.js` is routed nowhere** (`App.js` neither imports it nor routes `/decisions/strategy`). It was moved to the shared hook so the scan guard is clean, but it renders to nobody — the same finding as `GameStatusBar`. Whether it goes is not mine to decide.
4. **`StrategyToolsPage`'s four worksheet saves** discard the error and show a generic toast. They are the team's own analysis notes, not decisions, and the scanner exempts them by route on purpose. Left as found.
5. **Compliance investment is uncharged** — §6. A rule, so not created.

## 8. zh-CN — the complete list for one native review

Backend catalogue (`core/utils/participant_messages.py`), new:

| key | en | zh-CN |
|---|---|---|
| `FIELD_LABELS.market_allocation` | staff assigned to a market | 派驻市场的人数 |
| `MESSAGES.compliance_market_inactive` | You can invest in compliance only in a market your company operates in. Remove the other market and try again. | 只能在公司已进入的市场进行合规投入。请移除其他市场后重试。 |

No frontend catalogue entry was added: the modal notice on `ProductsPage` reuses `decision_save.not_saved_title` and `decision_save.network_failed`, and every other sentence a student now reads for these sections is the server's, already in both languages (`talent_decision_required`, `talent_allocation_total`, `talent_market_inactive`, `talent_hq_minimum`, `compliance_maximum`, `request_incomplete`, `whole_number_required`, `non_negative`). `test_zh_terminology` passes (no retired term). No computed `t()` keys were added.

## 9. What a reviewer should distrust

Only what I could not resolve here:

1. **No browser.** Every screen change is covered by unit tests of the pure functions and the hook, and the routes by JWT tests; none of the eight pages was driven in a browser in either language. The allocation screen's rebalancing (headquarters gives up what a market takes) and the modal notice on `ProductsPage` in particular are asserted, not seen.
2. **The two zh-CN sentences** in §8 are mine, unreviewed by a native speaker.
3. **Whether compliance investment should cost money** (§6) is the owner's.

## 10. Proposed register text (for the auditor to apply or reject)

**New — proposed P0, by the V2-107 reasoning** (the register's own three tests: the failing path is the default one; the loss is silent and the screen contradicts it; R17 already ruled on the failure mode).

*Staff allocation and compliance investment could not be saved by any team, and no team was told.* At `62a27cd`, `CorporateStrategyPage` autosaved staff allocation as section `talent_allocations` and `MarketStrategyPage` compliance investment as `compliance_investments`; neither was a key of `_TYPE_MAP`, so `DecisionPartialUpdateView` answered every such save `400 unknown_decision_type`, and both pages ended in `catch { /* ignore */ }` while the typed number stayed on screen. The payloads were also the wrong shape (dict keyed by pool / by market code against serializers that take rows), and compliance was read back from a list as if it were a dict, so a stored value would have displayed as 0. The tables, serializers and engine consumers (`engine/talent.py`, `strategy_effects._process_compliance`, the government agents, the alliance engine) all exist: two live competitive levers, unavailable to every team in every run to date. Two further defects found on the same sweep: the allocation rules had never run on any route (the whole-submission route stored any allocation), and `SummaryPage` sent team notes to the budget section, which refused them and with them the lock. **Repaired at `4ac2f3f` / `b3fcdbb`, pending closure:** both sections on the existing per-type path (`talent-allocations`, `compliance-investments`), the pair judged together, the rules on both routes, the pages sending and reading the server's shape, one autosave timer per section, one outstanding refusal per request in the shared notice, a source-scan guard against any discarded save failure, and a section-name guard held equal to `_TYPE_MAP` from both sides. Route tests with JWT students in both languages including one resolved round. **Open for the owner:** compliance investment is not charged anywhere (`funding_need`, `costs.py`) — a free $10M-per-market lever now that it can be pulled. Balance evidence to date was gathered with both levers at zero.

**New — P2.** `ProductsPage` edit of an existing product sends a create row with an undeclared `existing_product_id`; the server treats it as a new product (§7.2).

**New — P3.** `StrategyPage.js` is imported and routed by nothing (§7.3).
