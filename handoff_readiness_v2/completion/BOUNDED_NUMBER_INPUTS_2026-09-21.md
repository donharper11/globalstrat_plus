# Bounded number inputs, and DRF's numeric refusals re-said

**Date:** 2026-09-21
**Branch:** `crv2-13-bounded-number-inputs`, cut from `crv2-release-integration` at `be54b7d` (verified an ancestor before anything was touched)
**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`
**Input:** §6 of `REMAINING_ENGLISH_REFUSALS_2026-09-21.md` — "DRF's own sentences": *21 of the 37 `InputNumber`s on student pages have no `max`*, so a student can type a sixteen-digit amount and read `Ensure that there are no more than 15 digits in total.` in `DecisionSaveAlert`, in English, whatever language they work in.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md` and the `OWNER_RULINGS` files were not edited; §8 proposes register text for the auditor to apply or reject.

Commits (oldest first):

| Commit | What |
|---|---|
| `6d634eb` | Backend: `core/utils/numeric_refusals.py`, wired into `CompetitionDecisionWriteMixin.handle_exception`; five sentences and fourteen field labels in the participant catalogue; `test_numeric_refusal_language.py` |
| `8b6ed22` | Frontend: `src/decisionInputLimits.js`, a `max` on the 21 unbounded inputs, the finance page's budget text boxes held to the same bound; `decisionInputLimits.test.js` |
| *(next)* | This document |
| *(last)* | Regenerated string inventory, in its own commit |

No runtime code changed after the full backend run in §4.

---

## 1. The inventory, re-derived at head

Derived by scanning every `<InputNumber` under `src/` outside the instructor surfaces (`pages/InstructorDashboard.js`, `pages/InstructorLoginPage.js`, `components/instructor/`), not from the earlier report's count. It agrees: **37, of which 21 had no `max`.** All 37 already had a `min`. Line numbers are at `8b6ed22`.

"Server limit" is what the server accepts today. "Storage" means the only limit is the column's capacity, which DRF enforces from the model field.

| # | Page : line | Input | Sent as | Backend declaration | Server limit | `max` before | `max` now |
|---|---|---|---|---|---|---|---|
| 1 | `CorporateStrategyPage.js:87` | HQ staff | `TalentAllocation.hq_count` | `IntegerField` | storage (2147483647); sum must equal pool headcount | pool headcount | unchanged |
| 2 | `:118` | staff per market | `TalentAllocation.market_allocation` (JSON) | `JSONField` | none stated; same sum rule | pool headcount | unchanged |
| 3 | `:199` | headcount | `DecisionTalent.{rd,commercial,operations}_headcount` | `IntegerField` | storage | 200 | unchanged |
| 4 | `:226` | training budget | `DecisionTalent.*_training_budget` | `DecimalField(15, 2)` | storage 9,999,999,999,999.99 | **none** | `training_budget` = 9999999999999.99 |
| 5 | `:881` | environmental investment | `DecisionESG.environmental_investment` | `DecimalField(15, 2)` | storage | **none** | `MONEY_MAX` |
| 6 | `:895` | social investment | `DecisionESG.social_investment` | `DecimalField(15, 2)` | storage | **none** | `MONEY_MAX` |
| 7 | `FinancePage.js:369` | new borrowing | `DecisionFinancing.new_debt` | `DecimalField(15, 2)` | storage | **none** | `MONEY_MAX` |
| 8 | `:410` | debt repayment | `DecisionFinancing.debt_repayment` | `DecimalField(15, 2)` | storage | team's total debt | unchanged |
| 9 | `:446` | new equity | `DecisionFinancing.new_equity` | `DecimalField(15, 2)` | storage; the funding-need rule (V2-024) is tighter and stays on the server | **none** | `MONEY_MAX` |
| 10 | `:484` | dividend per share | `DecisionFinancing.dividend_per_share` | `DecimalField(10, 4)` | storage 999,999.9999 | **none** | `DIVIDEND_PER_SHARE_MAX` = 999999.9999 |
| 11 | `InventoryPage.js:186` | buffer days | `InventoryDecision.buffer_days` | `IntegerField` | storage | **none** | `INTEGER_MAX` = 2147483647 |
| 12 | `:187` | reorder point % | `InventoryDecision.safety_stock_trigger_pct` | `IntegerField` | storage | 100 | unchanged |
| 13 | `:203` | backup-rule amount | `ContingencyPlan.alt_supplier_activation_rules[].threshold` | `JSONField` | none stated | **none** | `INTEGER_MAX` |
| 14 | `:205` | backup-rule shift % | `…[].shift_pct` | `JSONField` | 0–100 (serializer) | 100 | unchanged |
| 15 | `:220` | mode-rule days | `ContingencyPlan.mode_switch_triggers[].threshold_days` | `JSONField` | none stated | **none** | `INTEGER_MAX` |
| 16 | `:227` | mode-rule shift % | `…[].shift_pct` | `JSONField` | 0–100 (serializer) | 100 | unchanged |
| 17 | `LogisticsPage.js:182` | insurance % | `IncotermsDecision.insurance_coverage_pct` | `IntegerField` | storage | 200 | unchanged |
| 18 | `:192` | returns capacity % | `CustomsClassificationDecision.reverse_logistics_capacity_pct` | `IntegerField` | storage | 100 | unchanged |
| 19 | `:222` | mode share % | `LogisticsDecision.mode_*_pct` | `IntegerField` | storage; must sum to 100 | 100 | unchanged |
| 20 | `:229` | volume (TEU) | `LogisticsDecision.volume_commitment_teu` | `IntegerField(null=True)` | storage | **none** | `INTEGER_MAX` |
| 21 | `MarketingPage.js:366` | unit price | `DecisionMarketing.retail_price` | `DecimalField(15, 2)` | storage; the price band *alerts and accepts* (Ruling 2), so it is not a limit | **none** | `MONEY_MAX` |
| 22 | `:419` | production volume | `DecisionMarketing.production_volume` | `IntegerField` | storage; capacity is a warning, not a refusal | **none** | `INTEGER_MAX` |
| 23 | `:445` | demand estimate | `DecisionMarketing.demand_estimate` | `IntegerField` | storage | **none** | `INTEGER_MAX` |
| 24 | `:472` | promotion budget | `DecisionMarketing.promotion_budget` | `DecimalField(15, 2)` | storage | **none** | `MONEY_MAX` |
| 25 | `:568` | reps per channel | `DecisionMarketing.distribution_channel_detail` (JSON) → summed into `sales_team_count` | `JSONField` / `IntegerField` | storage | 20 | unchanged |
| 26 | `MarketStrategyPage.js:177` | compliance investment | `ComplianceInvestment.investment_amount` | `DecimalField`; `validate_investment_amount` refuses > 10,000,000 | **$10M business validator** | **none** | `COMPLIANCE_INVESTMENT_MAX` = 10000000 |
| 27 | `SourcingPage.js:199` | supplier share % | `SourcingAllocation.allocation_pct` | `IntegerField` | storage; must sum to 100 | 100 | unchanged |
| 28 | `:205` | volume commitment | `SourcingAllocation.volume_commitment_units` | `IntegerField` | storage | **none** | `INTEGER_MAX` |
| 29–34 | `StrategyPage.js:164, 177, 190, 203, 332, 346` | new debt, repayment, new equity, dividend, environmental, social | as rows 7–10, 5–6 | as above | as above | **none** ×5; repayment = total debt | as rows 7, 9, 10, 5, 6 |
| 35 | `StrategyToolsPage.js:980` | criterion weight | analysis JSON | — | — | 5 | unchanged |
| 36 | `TradeFinancePage.js:222` | Sinosure coverage % | `SinosureEnrollment.coverage_pct` | `IntegerField` | storage | 100 | unchanged |
| 37 | `:236` | hedge ratio % | `FXHedgeDecision.hedge_ratio` | `IntegerField` | storage | 100 | unchanged |

Rows without a `max` before: 4, 5, 6, 7, 9, 10, 11, 13, 15, 20, 21, 22, 23, 24, 26, 28, and five of 29–34 — **21**.

**One numeric entry the `InputNumber` count could not see.** The finance page's three budget fields (`rd_budget`, `marketing_budget`, `strategy_budget`, each `DecimalField(15, 2)`) are not `InputNumber`s: `MoneyTextInput` is a text box that parses `2.5M`. It had no bound of any kind and reaches the same DRF sentence. It has no `max` prop to set, so `updateBudget` now holds the parsed amount to `DECISION_INPUT_LIMITS[field]` through `boundTo`. Every other numeric decision a student makes is a slider, a select, or a figure the page computes (`initial_investment`, `annual_investment`, `distribution_investment`), none of which can be over-typed.

`StrategyPage.js` is imported by nothing in `App.js`; it was bounded anyway so the scan has no exemptions.

The sixteen bounds that already existed are tighter than storage and were left exactly as they were: they are earlier interface decisions, not this task's, and none was widened or narrowed.

## 2. What changed

### Frontend — `src/decisionInputLimits.js`

One module, keyed by the backend field each input is sent as, each entry naming the declaration it was read from. Four constants: `MONEY_MAX` (9999999999999.99, `DecimalField(15, 2)`), `DIVIDEND_PER_SHARE_MAX` (999999.9999, `DecimalField(10, 4)`), `INTEGER_MAX` (2147483647, `IntegerField`), `COMPLIANCE_INVESTMENT_MAX` (10000000, the serializer's validator). Pages say `max={DECISION_INPUT_LIMITS.new_debt}`; no page carries a literal.

**No business rule moved.** Every bound equals what the server accepts for that field; none is tighter. The price band, the funding-need limit, the budget ceiling and plant capacity stay server-side with their own sentences. The two contingency thresholds are JSON with no server limit at all; they take the integer range their sibling fields have.

`decisionInputLimits.test.js` (11 tests):

* a source scan of every non-instructor file under `src/` — exclusions are listed, so a new page is scanned by default — fails on an `InputNumber` with no `max`, or no `min`; it also asserts it found at least 37, so it cannot pass by finding nothing;
* each bound is re-derived from the backend source (`max_digits` / `decimal_places` read out of `models/decisions.py` and `models/talent.py`; `IntegerField` for the integer fields; the `10000000` in `validate_investment_amount`), so a bound cannot drift below the server's;
* `JSON.stringify(MONEY_MAX)` is `9999999999999.99` — the bound itself is storable and does not become `1e13`;
* rendered against the installed antd 5.23.0 / rc-input-number 9.4.0: sixteen typed numerals never reach `onChange`, and blur settles on `max`; a legitimate large amount passes through untouched.

### Backend — `core/utils/numeric_refusals.py`

Every decision write — the per-type PATCH, the whole-submission POST/PUT, the four supply-chain views, and the rest of the fourteen view classes built on it — passes through `CompetitionDecisionWriteMixin`, and every one of them validates with `is_valid(raise_exception=True)`. So `handle_exception` on that mixin is the one place that sees all of them, whichever serializer raised. It rewrites `ValidationError.detail` and hands it back to DRF's handler.

| DRF code | Sentence |
|---|---|
| `max_digits`, `max_whole_digits`, `max_value`, `max_string_length` | `number_too_large` |
| `max_decimal_places` | `number_too_many_decimals` |
| `min_value` | `number_too_small` |
| `invalid` from `IntegerField` | `whole_number_required` |
| `invalid` from `FloatField` / `DecimalField` | `number_required` |

* Recognised by `ErrorDetail.code`, never by English text.
* **`invalid` needed one more step, and this is the part to read.** `invalid` is also the code DRF gives every `ValidationError` raised without one — which is every business sentence this codebase raises from a serializer. Rewriting on the code alone would turn "new borrowing cannot be negative" into "new borrowing must be a number". An `invalid` refusal is therefore rewritten only when its text *is* DRF's own `default_error_messages['invalid']` for one of the three numeric field classes — compared against DRF's message objects at run time, in the same thread and locale, not against an English literal kept here. It stays correct if `LocaleMiddleware` is ever switched on. `test_this_codebases_own_sentences_are_left_alone` pins it.
* The field is named by `FIELD_LABELS`, found as the nearest enclosing dictionary key, which is how DRF says whose refusal it is at any depth (`financing.new_debt`, `market_entries[0].initial_investment`). A field with no label is called "This number" / 该数值 — never its storage name, which is what `field_label`'s own fallback would have produced.
* Language is `language_for_request`, the same function the decision serializers use for their own field errors, so one response speaks one language. `LocaleMiddleware` was not enabled.
* Shape, keys, status and each refusal's `code` are unchanged; only the sentence differs.
* The sentences do not state the limit. `ErrorDetail` carries DRF's code and sentence but not the number, and reading it out of the English sentence is what this replaces.

Fourteen numeric fields a student can write had no business label (`allocation_pct`, the four `mode_*_pct`, `volume_commitment_teu`, `insurance_coverage_pct`, `reverse_logistics_capacity_pct`, `coverage_pct`, `hedge_ratio`, `tenor_days`, `buffer_days`, `safety_stock_trigger_pct`, `hq_count`). They have one now, and `LabelCoverageTests` enumerates every serializer in `_NESTED_CONFIG`, `_TYPE_MAP` and every `*WriteSerializer` in `sc_serializers` and fails when a writable numeric field is unlabelled.

The previous report judged `A valid integer is required.` unreachable ("`InputNumber` cannot send text"). It is reachable: none of the integer inputs sets `precision`, so `1000.5` units is sent as typed and an `IntegerField` refuses it with exactly that sentence. It now reads "production volume must be a whole number." / 生产数量必须是整数。 I did not add `precision={0}` to the integer inputs: that is a change to what a page sends, not a bound, and the sentence is now a good one.

## 3. Red, then green

**Backend, red** — the five sentences and the labels in place, the boundary not yet wired (so the failures show what a student read, not a missing key). `scripts/test-postgres core.tests.test_numeric_refusal_language`: `Ran 17 tests … FAILED (failures=21)`. Verbatim from that run:

```
AssertionError: Lists differ: ['Ensure that there are no more than 15 digits in total.'] != ['新增借款超出了系统可记录的上限。请输入较小的数值。']
  {'new_debt': [ErrorDetail(string='Ensure that there are no more than 15 digits in total.', code='max_digits')]}
AssertionError: Lists differ: ['Ensure this value is less than or equal to 2147483647.'] != ['研发人数超出了系统可记录的上限。请输入较小的数值。']
AssertionError: Lists differ: ['A valid integer is required.'] != ['R&D headcount must be a whole number.']
```

Both languages failed on every route test: zh-CN and en alike received DRF's English. The label test failed listing the fourteen fields above.

**Backend, green** — same command after wiring: `Ran 17 tests … OK`. What is driven, each in zh-CN and en through the real route with a real token:

| Route | Payload | Code | Asserted |
|---|---|---|---|
| `PATCH …/financing/` | `new_debt` = 1234567890123456 | `max_digits` | exact catalogue sentence; label present; CJK iff zh-CN; no storage name anywhere in the body; no DRF default; no six-numeral run; nothing written |
| `PATCH …/financing/` | `dividend_per_share` = 12345678.5 | `max_whole_digits` | same |
| `PATCH …/financing/` | `dividend_per_share` = 0.123456 | `max_decimal_places` | same |
| `PATCH …/talent/` | `rd_headcount` = 99999999999 | `max_value` | same |
| `PATCH …/talent/` | `rd_headcount` = −99999999999 | `min_value` | same, followed by this codebase's own non-negative sentence in the same language |
| `PATCH …/talent/` | `rd_headcount` = "10.5" | `invalid` (integer) | same |
| `PATCH …/esg/` | `environmental_investment` = "lots" | `invalid` (decimal) | same |
| `PATCH …/financing/` | two bad fields | `max_digits` ×2 | both named |
| `PATCH …/financing/` | `new_debt` = −5 | `invalid` (ours) | **left alone** — still `non_negative` |
| `PATCH …/financing/` | `dividend_per_share` = 999999.9999 | — | **200, stored exactly**: the bound the frontend now sets is accepted |
| `POST …/decisions/round/1/` | nested `financing.new_debt`, `market_entries[0].initial_investment` | `max_digits` | both rewritten at depth |
| `POST …/sc/round/1/inventory/` | `buffer_days` = 99999999999 | `max_value` | exact sentence |

Plus four unit tests of shapes no route produces (unlabelled field, code preserved, other codes untouched, unsupported language falls back to English).

**Frontend, red** — `decisionInputLimits.test.js` before the pages were edited: `no InputNumber is without a max` failed listing exactly 21 sites (`CorporateStrategyPage.js:225, 880, 894`; `FinancePage.js:368, 445, 483`; `InventoryPage.js:185, 202, 219`; `LogisticsPage.js:228`; `MarketStrategyPage.js:176`; `MarketingPage.js:365, 418, 444, 471`; `SourcingPage.js:204`; `StrategyPage.js:163, 189, 202, 331, 345`), and the finance-page test failed. **Green** after: 11 of 11.

## 4. Commands, results, durations

Backend tests ran only through `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres …` (a disposable `postgres:16-alpine` container per run). The production database and `/etc/globalstrat-plus.env` were never touched.

| Command | Result | Wall time |
|---|---|---|
| `scripts/test-postgres core.tests.test_numeric_refusal_language` (red, unwired) | 17 tests, 21 failures | 11 s |
| same (green) | 17 tests, OK | 11 s |
| `scripts/test-postgres` with `test_numeric_refusal_language test_player_language_guard test_crv2_12_language test_zh_terminology test_decision_limits test_price_band test_student_refusal_language test_competition_locks` | **141 tests, OK** | 23 s |
| `CI=true npx react-scripts test --watchAll=false` | **23 suites, 183 tests, all passed** (22 suites / 172 tests at the base, plus this suite's 11) | 4 s |
| `python3 backend/scripts/check-participant-strings` | PASS, 5212 units, 0 findings; 27 computed `t()` keys, the same 27 as before | < 1 s |
| `python3 backend/scripts/check-participant-strings-selftest` | 34 ok, 0 failed | — |
| `CI=false BUILD_PATH=<scratch> npx react-scripts build`, then `node eslint-warning-count.js build.log` | build exit 0; `eslint warnings: 55 (baseline 57)` — the same 55 as the previous report; baseline file not lowered (shared file, not my warnings) | not timed |
| `git diff --check`; `file` on every changed file | clean; every changed file was LF before and is LF after (no CRLF file was touched) | — |
| **`scripts/test-postgres core --parallel 8` — the one full run, from `8b6ed22`** | **Ran 1447 tests in 108.4 s — OK**, exit 0 | 124 s |

The build and the full backend run were taken with the runtime code as committed in `6d634eb` and `8b6ed22`. The full Jest run in the table is from the committed head; an earlier full run, before the two render tests were added to the new suite, gave 181 of 181.

A temporary probe test (§6, F1) was run once and deleted; it was never committed.

## 5. zh-CN — the complete list for one native review

All mine, none read by a native speaker. Terms follow `test_zh_terminology.py` (no 比赛 / 队伍 / 小组 / 轮; none of these needs 游戏, 回合 or 团队). The field labels follow the label the page itself shows for the same input.

#### `backend/core/utils/participant_messages.py` — `MESSAGES`

| Key | en | zh-CN |
|---|---|---|
| `number_too_large` | {field} is larger than the simulation can record. Enter a smaller number. | {field}超出了系统可记录的上限。请输入较小的数值。 |
| `number_too_small` | {field} is below the lowest value allowed. Enter a larger number. | {field}低于允许的最小值。请输入较大的数值。 |
| `number_too_many_decimals` | {field} has more decimal places than can be recorded. Round it and try again. | {field}的小数位数过多。请四舍五入后重试。 |
| `number_required` | {field} must be a number. | {field}必须是数字。 |
| `whole_number_required` | {field} must be a whole number. | {field}必须是整数。 |
| `this_number` | This number | 该数值 |

#### `FIELD_LABELS`

| Field | en | zh-CN | Page label it follows |
|---|---|---|---|
| `allocation_pct` | supplier share | 供应商份额 | `sc.sourcing.share_pct` 份额 % |
| `mode_sea_pct` | sea share of shipments | 海运比例 | `sc.logistics.mode_sea` 海运 |
| `mode_air_pct` | air share of shipments | 空运比例 | 空运 |
| `mode_rail_pct` | rail share of shipments | 铁路比例 | 铁路 |
| `mode_road_pct` | road share of shipments | 公路比例 | 公路 |
| `volume_commitment_teu` | shipping volume commitment (TEU) | 承诺运量（TEU） | `sc.logistics.volume_teu` 运量（TEU） |
| `insurance_coverage_pct` | insurance percentage | 保险比例 | 保险比例 % |
| `reverse_logistics_capacity_pct` | returns capacity | 退货处理能力 | 退货处理能力 % |
| `coverage_pct` | export-credit coverage | 出口信用保险覆盖比例 | 中信保出口信用保险覆盖 / 覆盖比例 % |
| `hedge_ratio` | hedge ratio | 对冲比例 | 对冲比例 % |
| `tenor_days` | hedge tenor in days | 对冲期限（天） | 期限（天） |
| `buffer_days` | inventory buffer in days | 库存缓冲天数 | 缓冲（天） |
| `safety_stock_trigger_pct` | reorder point | 补货触发点 | 补货触发点（%） |
| `hq_count` | headquarters staff | 总部人数 | `corporate_strategy.hq_talent` 总部人才 |

The ones I trust least: 超出了系统可记录的上限 (is 系统 the word the rest of the product uses for "the simulation"? the catalogue already says 系统给出的原因, which is why I chose it); 总部人数 against the page's 总部人才; and the English sentences begin with a lower-case label ("new borrowing is larger than…"), which is the existing convention of `non_negative` on the same screen, kept for consistency rather than liked.

No frontend catalogue key was added: the frontend change shows no new text.

## 6. New findings (none closed here)

**F1. Two sections the pages save are refused by the route on every call.** `MarketStrategyPage` autosaves with `patchDecision(…, 'compliance_investments', …)` and `CorporateStrategyPage` with `'talent_allocations'`. Neither is in `_TYPE_MAP` (`core/views/decisions.py`), so both answer `400 unknown_decision_type` ("This decision section is not available. Refresh the page and try again."). Confirmed by driving both through the route (temporary probe, deleted). The page sends compliance as `{market_code: amount}` while `ComplianceInvestmentSerializer` expects a list of `{market, investment_amount}`, so adding the map entry alone would not repair it. Both serializers *are* in the whole-submission `_NESTED_CONFIG`. This is a route and payload repair, not a bound or a sentence, so nothing was changed; row 26's bound (the $10M validator) is correct for whenever the write works. Whoever owns the route inventory should decide whether these two decisions are meant to be live for the competition.

**F2. The supply-chain write serializers speak English throughout** — "Modal mix must sum to 100; got 90", "logistics.modal_mix not yet unlocked at round 2…" (which also names a storage path), "Rule 1 shift % must be between 0 and 100." They are this codebase's literals inside `serializers/sc_serializers.py`, which the CRV2-12 view scans do not read, and the views construct those serializers without a request context, so they could not localise even if they tried. Only DRF's numeric refusals on those routes are covered here. Same shape as the residuals in the previous report's §6; belongs with the supply-chain conversion.

**F3. Interface bounds tighter than the server, pre-existing.** Headcount ≤ 200, reps per channel ≤ 20 and insurance ≤ 200 % exist only in the page; the server accepts any integer. Harmless for language (a student cannot exceed them), recorded because the API does not enforce them and an instructor reading the page would assume it does.

## 7. What a reviewer should distrust

Only what could not be resolved here:

1. **The twenty zh-CN strings in §5 are mine and unread by a native speaker.**
2. **Nothing was seen in a browser.** The clamp is tested against the installed antd in jsdom (typing past the bound never reaches `onChange`; blur settles on `max`), but how it *feels* — a student typing sixteen numerals sees them until blur, then sees 9,999,999,999,999.99 with no explanation — has not been looked at by anyone, and whether that silent settle is acceptable or wants a hint under the field is a product call.
3. **For the owner:** whether the two unsaveable sections (F1) are meant to be live; and, already pending from the previous report, whether `LocaleMiddleware` is switched on — this work does not depend on the answer and stays correct either way.

Everything else I doubted, I checked: that every bound equals the server's limit and none is below it (re-derived from the backend source in a test, and the largest dividend driven through the route and stored exactly); that the bound itself serialises as storable digits; that antd really withholds an out-of-range value (rendered, not remembered); that this codebase's own `invalid`-coded sentences are not rewritten (driven); that nested and list-row refusals are reached (driven); that a field with no label cannot leak a storage name (unit test, plus a coverage test so the case should not arise); that no test anywhere pinned a DRF English sentence on these routes (grep: none); that there is no second serializer-validated student write outside the mixin (grep: only `views/overrides.py`, instructor-side); that the `InputNumber` count missed a numeric entry (it did — the budget text boxes — fixed); that the previous report's "cannot send text, so `invalid` is unreachable" holds (it does not — covered); that no computed `t()` key was added (27 before and after); that no CRLF file was touched.

## 8. Proposed register text (for the auditor to apply or reject)

**D3 — operator/participant refusals (residual: DRF's own sentences):**
> **Repaired, pending native review and observation.** `8b6ed22`: all 37 student `InputNumber`s carry a `max` (21 had none) from `src/decisionInputLimits.js`, each equal to the server's own limit for that field and re-derived from the backend source in a Jest test; the finance page's budget text boxes are held to the same bound; a source scan fails on a new unbounded input. `6d634eb`: behind that, `CompetitionDecisionWriteMixin.handle_exception` re-says DRF's `max_digits`, `max_whole_digits`, `max_decimal_places`, `max_value`, `min_value`, `max_string_length` and numeric `invalid` refusals from the participant catalogue, in the request's language, naming the field by business label, recognised by error code; shape, status and codes unchanged; driven red then green in both languages on the per-type, whole-submission and supply-chain routes. No business rule changed. **Residual:** DRF's non-numeric sentences (`This field may not be null.`, `Not found.`, the throttle message) are as the previous report left them; the supply-chain serializers' own English literals (F2). zh-CN unreviewed; not seen in a browser.

**New — two decision sections refused on every save (F1):**
> **Open.** `PATCH …/decisions/round/N/compliance_investments/` and `…/talent_allocations/` are not in `_TYPE_MAP` and answer 400 to the pages that call them; the compliance payload shape also differs from its serializer. Recorded in `BOUNDED_NUMBER_INPUTS_2026-09-21.md` §6; nothing changed.

**New — supply-chain serializer literals English-only (F2):**
> **Open.** Same defect as V2-080's residuals; belongs with the supply-chain conversion.
