# Walkthrough CE — student-side numbers (2026-09-22)

**Branch:** `walk-ce-student-numbers`, cut from `crv2-release-integration` at
`4756ffc` (contains `4b152f8` and
`completion/WALKTHROUGH_CE_2026-09-22.md`; both verified before anything was
touched).
**Observes:** `specs/STANDING-DISCIPLINE.md`,
`handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`,
`DETERMINISM_BOUNDARY.md`, owner ruling R48 (bugs first, calibration
deferred, no new rule and no changed number unless plainly computed wrong).
**Defects:** W-CE-02, W-CE-14, W-CE-18/18b, W-CE-23, W-CE-25, W-CE-03,
W-CE-04 from `completion/WALKTHROUGH_CE_2026-09-22.md`. W-CE-19 is
calibration and was not touched: no price, budget or scenario number moved.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`,
`LAUNCH_CHECKLIST_V2.md`, every `OWNER_RULINGS` file and
`INTEGRATOR_DECISIONS_UNDER_R48.md` were left untouched; §9 proposes
register text for the auditor to apply or reject.

Method throughout: reproduce first (a test that fails on the tree as it
was, recorded), repair, run the same test green. One commit per defect.

| Commit | Defect | What |
|---|---|---|
| `e001c47` | W-CE-02 | Finance tabs are render functions, not components declared inside the render |
| `6c53928` | W-CE-14 | Shareholder return is a per-share quantity; base is the round-0 price |
| `e0cd389` | W-CE-18/18b, W-CE-23 | One calculator for what the round's decisions will cost; the bar, Summary and Finance read it |
| `ccb7ec1` | W-CE-25 | The Summary's blockers are the lock validator's list; V2-024 enforced at lock |
| `5c7d8c5` | W-CE-03 | R&D page offers no feature-level upgrade; the server says why |
| `b0d3c35` | W-CE-04 | A refused marketing row is named; the refusal is shown once |
| `bbb4255` | W-CE-18 (follow-up) | Regenerated `read_inventory.json`: the Finance context no longer reads `DecisionESG` itself, the one test the first full run failed |
| *(next)* | — | This document |
| *(last)* | — | Regenerated string inventory, alone |

---

## 1. W-CE-02 (P0) — a typed loan amount stores $5, $0 or $50

**Reproduction.** `frontend/.../src/pages/FinancePage.typing.test.js`
renders the real `FinancePage` with the real antd `InputNumber`, opens
Capital Management, clears the box as the probe did, and presses `5000000`
one key at a time (keydown, an input event with the text so far, keyup),
with the page's own 700 ms autosave live and `patchDecision` mocked. On the
page as it was (`git show 4756ffc:…/FinancePage.js` swapped in for one run):
**3 failed** — after the first key press `document.contains(loan)` is false:
the input the student was typing into is no longer in the document. On the
repair: **3 passed**, the box reads `$ 5,000,000` after blur and the last
financing PATCH carries `new_debt: 5000000`; the slow-cadence case (the
autosave fires between the first and second digit) stores `6` then
`6000000`; every financing box on the tab keeps focus across a key press.

**Cause.** `BudgetTab`, `CapitalTab` and `TaxTab` were components declared
*inside* `FinancePage`'s render. Every keystroke set financing state and
re-rendered the page, which created three new component types, and React
unmounted the whole tab and mounted it again — destroying the focused
`InputNumber` mid-word. The first digit reached the state; the rest went to
an input that no longer existed. Cadence decided how many digits landed
before the remount: $5, $0 or $50. A pasted value is one change event, so it
worked. A second, cosmetic defect: `formatMoneyInput`/`parseMoneyInput` were
created inside the render, and rc-input-number re-formats the box from the
value whenever the `formatter` prop's identity changes
(`useLayoutUpdateEffect(…, [precision, formatter])`).

**Repair.** The three tabs are render functions of the page (`renderBudgetTab()`
…), and the money formatter, parser and normaliser are module-level. No
autosave, API or server behaviour changed.

**The other autosaving numeric fields.** Nested component declarations that
hold decision inputs: `FinancePage` only (the pattern also exists in
`CompetitiveIntelPage`, `GameDashboard`, `ResultsPage`, all read-only). A
state reset from the server mid-typing: `loadContext` re-runs only when the
provider's `draft` object changes identity, which happens on navigation
(`DraftRefreshOnNavigate`) and never from a page's autosave — no page calls
`loadDraft`/`updateDraft` after a save except `ProductsPage` on create. A
`formatter` on an `InputNumber`: `FinancePage` only. Nothing else needed
changing.

## 2. W-CE-14 (P0) — shareholder return 999,966.5 %

**Reproduction.** `backend/core/tests/test_shareholder_return.py` resolves a
two-team round through `process_round` with one team paying $0.50 a share.
Red on `e001c47`: **3 failed** — stored `99999.0000` (the clamp) where the
per-share arithmetic gives `-0.3750`. Green on the repair: **3 OK**.

**Cause — the number was wrong, not mis-scaled.** `financials.py` computed
`(share_price + cumulative_dividends − initial_share_price) / initial_share_price`
with `cumulative_dividends` the sum of `dividends_paid`, which is money:
$500,000 for a million shares at $0.50, added to a per-share price. For the
walkthrough's team, (33.25 + 500,000 − 50) / 50 = **9,999.665**, the API
figure exactly; the page's `pct()` (×100) was right. The base was also
`starting_cash / 1,000,000`, not the price the team was shown at round 0
(`bootstrap` publishes `total_equity / shares`, which differs whenever a
starter profile carries debt: the CE team started at $45, and was measured
against $50).

**Repair.** Dividends are brought to per share (cumulative dollars over the
team's shares outstanding) before they meet the price, and the base is the
round-0 statement's share price, keeping `starting_cash / 1,000,000` only for
a game with no round-0 row (`test_a_game_without_a_round_zero_row_keeps_the_old_base`).
Cumulative dividends over the *current* share count is exact while the count
is unchanged and an approximation across an equity issue; the exact per-round
series is not stored, and this is a display and derived-feature figure.

**Determinism.** `financials.shareholder_return_cumulative` is in the hashed
`financials` section (`manifest_schema_v2.json`), and
`derived_features.dividend_consistency` reads it (it scored *any* dividend as
a ≥ 20 % return before), so a round in which a team pays a dividend, or whose
round-0 price differs from `starting_cash / 1e6`, now resolves to a different
competitive hash than it did on `4756ffc`. No section changes shape;
`MANIFEST_SCHEMA_VERSION` stays **7**. Any replay evidence of such a round
recorded before `6c53928` is evidence for its own commit only.

## 3. W-CE-18 / W-CE-18b / W-CE-23 (P1) — three spend figures, and an over-spend the lock let through

**Reproduction.** `backend/core/tests/test_committed_spend_one_calculator.py`,
red on `6c53928`: **8 tests — 5 failed, 2 errors, 1 passed.** A $1,500,000
acquisition queued through the real `acquisitions` route against $1,000,000
of cash and a $100,000 declared strategy budget: `committed_total` was
$100,000, the lock refused for the missing product portfolio and marketing
mix but never for cash, and the Summary and Finance context had no
`strategy_spent`/`rd_spent` in the assessment at all (`KeyError`). With a
market entry, ESG, a talent decision and a marketing row: the Finance
context's `marketing_spent` was $1,059,999 (promotion plus
`distribution_investment`, a field the engine never charges) where the engine
charges $260,000 (promotion plus sales reps). Green on the repair: **8 OK.**

**Cause.** Three calculators where one exists:

* `rd_costs.committed_outlay` — *the* affordability figure (V2-038, V2-057)
  — counted the declared budget lines plus the four extras later rulings
  added (platform development, bought research, the structure switch,
  compliance). What the engine actually charges from cash for the round's
  decisions — `funding_need.decision_outlays`, the calculator the engine
  books from (V2-024) — was in no affordability figure: not the acquisition
  (charged in full at resolution, `costs.py:515`), not market entries,
  partnerships or ESG, not sales reps, not payroll, not a plant. The
  strategy line is a declaration (A5/R14) and, unlike R&D and marketing, its
  spend is not held to it at lock (the validator's comment at the ESG check
  says so: "don't validate in isolation here"), so an $18M acquisition
  against a $1.5M strategy budget passed the lock and was charged.
* The Summary view and the Finance context each summed "spent" a private
  way (entries at full cost even on exit, `partnerships` decision rows
  rather than active partnerships, `distribution_investment`).
* The engine books payroll, the structure switch, governance, integration
  and org overhead into `strategy_expense`, so the bar's "Strategy" ($3.3M)
  and the statement's line ($9.55M, three identical teams: it was payroll)
  could never agree.

The round-3 screen's three figures were three concepts, each consistent with
itself: the banner (`BudgetAlert`) is spend against the scenario's operating
budget, the bar is spend against the declared budget lines, the blocker and
"Unallocated" are committed spend against cash. W-CE-18b's "the $18M
acquisition … counted in round 3's spend again" is not what the record
shows: `records/student-play-t1-r3-en.json` step "corporate: acquisition
queued" is a **second** acquisition (`acquisition_target: 1`, id 4) queued
in round 3; round 2's was target 2. Nothing was double-counted.

**Repair — the existing rule, enforced.** R47's consequence states it:
"charged from cash means it counts toward committed spend, so the
affordability check and the equity funding rule see it". `committed_outlay`
now reads, through `funding_need.decision_outlays`, the marketing, strategy,
talent and plant-capex outlays the engine charges, plus queued acquisitions
at their authored base cost (added here and not to `decision_outlays`, which
V2-024 requires to stay *below* what the engine charges, because an
acquisition is charged only if fulfilled). `budget_assessment.committed_total`
= declared budget lines **+ the spend above each declared line** (a declared
budget is a floor, as V2-057 pinned, not a cap) + platform development +
research purchases + structure switch + compliance + payroll + plant capex.
`within_cash`, `unallocated`, the lock's projected cash and
`committed_spend_exceeds_cash` all follow from it unchanged. The assessment
publishes `rd_spent`, `marketing_spent`, `strategy_spent`,
`talent_committed`, `plant_committed`; the Summary and the Finance context
read those and nothing else (their private sums are gone); the shared
`BudgetBar` shows payroll and plant construction as committed rows beside
compliance and platform development, so a student can reconcile the bar with
the statement: Strategy + Payroll = the statement's strategy line, for the
decision-driven part. `total_spent` on the Finance context (the banner's
figure) is the sum of the same three lines.

What did **not** change: no engine charge, no scenario number, `budget_total`
(declared, which coherence scoring reads), the funding-need rule's eligible
uses, the R&D-budget and marketing-budget lock checks, and the queuing of an
acquisition (still accepted at save; the Summary now shows the blocker and
the lock refuses).

**What the walkthrough's team would see now.** Round 2: the bar reads
Strategy $18.0M+ / $1.5M and *Unallocated* negative the moment the
acquisition is queued; the Summary lists "Committed spend of $… exceeds
available cash of $18,250,223.00" and the lock is refused. The team can
un-queue it or fund it. The round-3 lock-out cannot arise from a locked
over-spend.

**W-CE-23, second half — a team at negative cash.** What the rules as coded
say, precisely:

1. `committed_spend_exceeds_cash` compares committed spend (≥ $0) to
   `cash_on_hand` and does not count new debt or equity. With negative cash
   it cannot be satisfied by any submission, including one with $0 of
   spend and an equity raise that would restore the cash.
2. The projected-cash rule (`cash_negative`) *does* count financing, and its
   own sentence tells the team to "raise financing before locking"; so does
   the research-purchase refusal ("Reduce committed spend or raise financing
   before buying it"). Two of the rule's sentences name a remedy the first
   check's arithmetic ignores.
3. A distressed team (negative cash) cannot raise debt — the engine refuses
   it at resolution (`financials.py`, "lenders will not extend credit") — and
   cannot acquire; it *can* raise equity, up to the shortfall, under V2-024
   (`maximum_new_equity = eligible_uses − (cash + new_debt)`, positive when
   cash is negative).
4. A team that cannot lock is not out of the game: at the deadline
   `_lock_all_submissions` locks its draft as it stands (`deadline_lock`)
   and the round resolves it, financing included. It loses only what
   requires a *locked* submission of its own (acquisitions) and the
   "Decisions Locked" state on screen.

So the team is not stuck in the engine, but it is locked out of the lock
button, and the affordability sentence contradicts the projected-cash
sentence beside it. Whether "available cash" in
`committed_spend_exceeds_cash` should count the financing the team has
decided (making the two checks one) is a **rules question for the owner**,
recorded in §8 and not decided here: it changes what a team may lock.

## 4. W-CE-25 (P1) — lock refused for a blocker the Summary never showed

**Reproduction.** `backend/core/tests/test_summary_blockers_match_lock.py`,
red on `6c53928`: **5 failed** of 5 (7 of 9 in the run shared with W-CE-04).
With $2,500,000 of new debt against $1,000,000 of equity (2.50 > 2.0) the
Summary said `can_lock: true, lock_blockers: []`, in English and in Chinese,
and the lock returned 400 with `预计资产负债率 2.50 超过上限 2.0。请调整融资。`.
Green on the repair: **5 OK**.

**Cause.** `DecisionLockView._full_validate` and `DecisionSummaryView` kept
two lists. The Summary's was a hand-picked subset: the budget-vs-cash rule,
projected cash (only inside the financing branch), the V2-024 funding rule
and the three required sections. The debt ceiling, the repayment cap, the
dividend cap, the R&D and marketing budget caps, the channel split, the
price rule, the market-entry rules and mandatory communications were
enforced at lock and shown nowhere before it. Conversely the V2-024 check
was on the Summary and at save and at resolution — but not at lock, so a
lock could accept a raise the engine would then refuse to resolve for every
team.

**Repair.** The validator is one module-level function,
`lock_blockers_for(submission, language)`; `_full_validate` delegates to it
and the Summary publishes its result as `lock_blockers` with `can_lock` its
emptiness (the category checklist is unchanged presentation). The validator
gains the V2-024 check with the same sentence the Summary already used
(`funding_need.describe`). `test_the_summary_lists_exactly_what_the_lock_refuses`
asserts list equality, in both languages.

## 5. W-CE-03 (P1) — five "Invest next level" buttons, five refusals

**Reproduction.** `frontend/.../src/pages/RDPage.upgradeOffer.test.js`,
red on `6c53928`: **3 failed** — the page rendered "Invest next level" for
every feature below its ceiling and "Upgrade an existing feature when a new
platform is over budget", while the server refuses every feature-level R&D
row (R10, `rd_investment_retired`, `test_platform_freeze`). Green: **3 OK**.

**Cause.** The page offered an action the server has retired.

**Repair.** The R&D context (`RDContextView`) publishes
`feature_investment: {available: false, reason: <rd_investment_retired in
the reader's language>}`. The page drops the Platform Upgrade panel, the
`investInNextLevel` handler and the per-feature "Next lvl: $X" hint, and its
guidance line is now `rd.round_guidance` ("You have {{remaining}} of R&D
budget remaining.") followed by the server's sentence when
`available === false`. The Summary's R&D guidance no longer says "upgrade an
existing feature". An older server that says nothing still gets no offer.
The `rd.platform_upgrade`, `rd.next_level`, `rd.upgrade_exceeds_budget`,
`rd.investment_saved`, `rd.investment_save_failed`, `rd.slots_all_used`
catalogue keys are now unreferenced; they were left in place to keep the
locale diff additive while other builders edit the catalogues.

W-CE-19 (the cheapest platform costs more than the round-1 budget) is
calibration and untouched; the page now says only what the team has and what
the server accepts.

## 6. W-CE-04 (P1) — one bad marketing row, an unnamed refusal, shown twice

**Reproduction.** Server: `backend/core/tests/test_marketing_refusal_names_row.py`,
red on `6c53928`: **2 failed, 2 passed** — two products, one row with
promotion spend and no campaign focus: 400 with
`{"campaign_focus_feature_ids": ["Choose one to three campaign focus
features."]}`, naming nothing; the two contract tests (nothing stored on a
refusal, everything stored when nothing is refused) already held. Page:
`frontend/.../src/pages/MarketingPage.refusal.test.js`, red: **1 failed** —
after a refused autosave the page rendered its own
`marketing.save_failed_title` banner beside the shared
`DecisionSaveAlert`. Green: **4 OK / 1 OK**.

**Cause and contract.** The per-type write replaces the whole section:
every row is validated, then `delete()` + `bulk_create()`. A partial save is
not in the contract and would be wrong under it (the rows not reached would
be deleted), so the whole-page save is kept. The refusal came straight from
the first row's serializer errors, with no product or market; and the page's
own banner duplicated the shared R17 notice the axios interceptor feeds for
every decision write.

**Repair.** A refused marketing row's errors are wrapped by
`_name_refused_marketing_row` as `{"marketing_decisions": ["<product> in
<market>: <sentence>", …]}` through the new catalogue key
`marketing_row_refused` (`{product} in {market}: {reason}` /
`{product}（{market}）：{reason}`), the market name through
`get_localized_field` (checker A7). The page's duplicate banner is removed;
`saveError` still marks the edited entries unsaved. The shared notice shows
the sentence once, with the retry.

## 7. Commands and results

All backend runs through `scripts/test-postgres` (disposable
`postgres:16-alpine`, never the production database, never
`/etc/globalstrat-plus.env`) under `flock -w 1800
/tmp/globalstrat-backend-test.lock`. The docker daemon was slow to start
containers for most of the session (~75 s from create to network join;
`journalctl -u docker` shows SIGKILLs on container teardown) and another
builder's `core --parallel 8` held the lock for ~65 minutes with idle
workers; a retry wrapper (`retry_test.sh`, scratch) re-ran the runner when
the container never became ready or the lock wait expired, and every result
below is a single complete run recorded with branch, revision and PID.

| # | Command | Result | Wall |
|---|---|---|---|
| 1 | Jest `FinancePage.typing.test.js` on `4756ffc`'s page | 3 F of 3 (red) | 1 s |
| 2 | Jest `FinancePage.typing.test.js` | 3 OK | 5 s |
| 3 | `test-postgres core.tests.test_shareholder_return` at `e001c47` | 3 F of 3 (red) | ~1 min |
| 4 | `test-postgres core.tests.test_shareholder_return` | 3 OK | ~1 min |
| 5 | `test-postgres core.tests.test_committed_spend_one_calculator` at `6c53928` | 5 F, 2 E of 8 (red) | (queued 64 min behind another builder) |
| 6 | `test-postgres test_summary_blockers_match_lock test_marketing_refusal_names_row` at `6c53928` | 7 F of 9 (red) | 0.5 s + container |
| 7 | Jest `RDPage.upgradeOffer.test.js` at head | 3 F of 3 (red) | 1 s |
| 8 | Jest `RDPage.upgradeOffer.test.js` | 3 OK | 1 s |
| 9 | Jest `MarketingPage.refusal.test.js` at head | 1 F (red) | 2 s |
| 10 | Jest `MarketingPage.refusal.test.js` | 1 OK | 2 s |
| 11 | `test-postgres` the three repaired modules | 17 OK | 1.5 s + container |
| 12 | Jest `BudgetBar.test.js` (two new rows) | 8 OK | 1 s |
| 13 | `test-postgres` focused batch: the five new modules + test_rd_costs, test_compliance_investment_charge, test_org_transition_charge, test_funding_need, test_marketing_default_row, test_platform_freeze, test_participant_messages, test_paid_research + the standing labels (test_silent_section_saves, test_equity_issuance, test_decision_limits, test_scoring_dispositions, test_manifest_determinism, test_engine, test_player_language_guard, test_crv2_12_language, test_zh_terminology) | **367 OK**, 40.9 s | about 1 min with the container |
| 14 | `CI=true npx react-scripts test --watchAll=false` (full) | **33 suites / 334 tests OK** | 10 s |
| 15 | `check-participant-strings` / selftest | PASS 5203 units, 0 findings / 34 ok | 2 s |
| 16 | `CI=false BUILD_PATH=<scratch> npx react-scripts build`; `node eslint-warning-count.js` | Compiled with warnings; **55 (baseline 57)**, none in a file this branch adds; exit 0 | 35 s |
| 17 | `test-postgres core --parallel 8` at `b0d3c35` (first freeze candidate) | `Ran 1541 tests in 271.514s`, **FAILED (errors=1)**: `test_audit_integrity.SensitiveReadInventoryTests.test_the_checked_in_inventory_matches_the_live_url_conf`. The checked-in sensitive-read inventory listed `DecisionESG` under `context/finance/`, which `e0cd389` stopped reading directly | 4 min 32 s |
| 18 | `test-postgres core.tests.test_audit_integrity` after `dump_read_inventory` | 61 OK | 22 s |
| 19 | **`test-postgres core --parallel 8`, once more, at `bbb4255`** | `Ran 1541 tests in 226.881s`, **OK**, exit 0 (log records branch, revision and PID) | 3 min 47 s plus the container |

`git diff --check` clean at every commit; every touched file kept LF line
endings. No runtime code changed after #17 began: the failed freeze candidate was repaired by regenerating a checked-in inventory file (`bbb4255`, no runtime code), the one case the protocol budget allows a second full run for, and #19 is that run.

Not run, because not release-scale and not touched: concurrency matrix,
replay, load, soak, browser archive. W-CE-14 touches a hashed value (§2), so
replay evidence for a dividend-paying round predates this branch's engine.

## 8. Questions for the owner (plain language)

1. **A team whose cash is negative cannot lock anything.** What the player
   sees: after a round that ended in the red, every Decision Summary shows
   "Committed spend of $X exceeds available cash of $−Y" no matter what the
   team cuts, and beside it "Projected ending cash is … raise financing
   before locking" — but raising financing does not clear the first line,
   because that check compares spend to cash on hand and ignores the debt
   or equity the team has decided to raise. The team can still play (its
   draft is locked for it at the deadline and resolved, financing included)
   but it can never press Lock, and it cannot acquire. Should "available
   cash" in the affordability check count the financing the team has
   decided, as the projected-cash check and the funding-need rule already
   do? If yes, the two checks become one; if no, the sentence that says
   "raise financing" is misleading beside it.
2. **What counts against the round's operating budget.** The Finance page's
   banner ("Over budget by … total spending …") compares *spend* to the
   operating budget; the coherence penalty the engine applies compares the
   *declared allocations* to it (`coherence.py`). One concept, two figures.
   This was not changed (it is display, and the penalty is a scoring rule).
3. **Payroll inside "Strategy expense".** The engine books payroll, the
   structure switch, governance and integration costs into the statement's
   strategy line (hashed). The bar now shows payroll as its own committed
   row so the two can be reconciled; splitting the statement line is a
   presentation ruling, like R47's.

## 9. zh-CN — new sentences

| Where | Key | English | 中文 |
|---|---|---|---|
| `participant_messages.py` | `marketing_row_refused` | `{product} in {market}: {reason}` | `{product}（{market}）：{reason}` |
| `locales/*.json` | `rd.round_guidance_title` | Your R&D action this round | 本回合的研发行动 |
| `locales/*.json` | `rd.round_guidance` | You have {{remaining}} of R&D budget remaining. | 研发预算剩余 {{remaining}}。 |
| `locales/*.json` | `budget.talent_committed` | Payroll and talent | 薪酬与人才 |
| `locales/*.json` | `budget.plant_committed` | Plant construction | 工厂建设 |

`test_zh_terminology` passes (回合 for round; no retired term). Whether the
four short labels read naturally is for a native speaker (§10).

## 10. Proposed register text

* **W-CE-02** — *Repaired at `e001c47`.* The Finance tabs were components
  declared inside the page's render; each keystroke remounted the tab and
  destroyed the focused input. Render functions now; `FinancePage.typing.test.js`
  drives the real InputNumber key by key and fails on the old page.
* **W-CE-14** — *Repaired at `6c53928`.* Dividends in dollars were added to a
  per-share price; the base was starting cash over a million shares rather
  than the round-0 price. Per share throughout; `test_shareholder_return`.
  Hashed value changes for dividend-paying rounds; schema version 7 kept.
* **W-CE-18 / 18b** — *Repaired at `e0cd389`.* Three private "spent" sums
  replaced by `rd_costs.budget_assessment` reading
  `funding_need.decision_outlays`; payroll and plant capex shown as
  committed rows. The "counted again" reading in 18b was a second
  acquisition queued in round 3, not double counting.
* **W-CE-23** — *Repaired at `e0cd389` (first half); rules question (second
  half).* Committed spend counts the spend above each declared budget line
  and queued acquisitions, so the lock refuses the over-spend in the round it
  is made. The negative-cash lock-out is the existing affordability rule's
  arithmetic against its own sentence — §8.1.
* **W-CE-25** — *Repaired at `ccb7ec1`.* One validator; the Summary
  publishes its list. V2-024 now also refused at lock.
* **W-CE-03** — *Repaired at `5c7d8c5`.* No feature-level offer; the
  server's `rd_investment_retired` sentence shown in place of it.
* **W-CE-04** — *Repaired at `b0d3c35`.* Whole-page save kept (the
  contract); the refused row is named; shown once.

## 11. Distrust

Only what needs the owner, the production host, a browser or a native
speaker:

* §8 — the three questions.
* A browser: the walkthrough drivers (`student_play.py`, `probe_loan_input.py`)
  have not been re-run against this branch; the Jest tests drive the real
  components under jsdom, which is not Chromium.
* A native speaker: the four zh-CN labels in §9.
