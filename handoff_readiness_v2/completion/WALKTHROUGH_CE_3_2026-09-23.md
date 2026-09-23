# Third full walkthrough — Consumer Electronics 2026, on the repaired tree

**Branch:** `walkthrough-ce-3-2026-09-23`, cut from `crv2-release-integration`
at `3c0ccf2`. The base was checked before anything ran: `29da1c8` — the merge
of both walkthrough-2 repair branches (`walk-ce2-round-blockers` and
`walk-ce2-language`) — is an ancestor of HEAD.
**Date:** 2026-09-23. **Auditor role:** find defects; repair nothing.
`backend/`, `frontend/` and `specs/` have **zero diff** on this branch. The
only edits are to the harness under
`handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/harness/`, every
one of them listed in (a).
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/`
— `harness/` (every driver), `records/` (one JSON per driver run: steps,
screens, API calls, refusals, console, leak scans), `screenshots/` (JPEG),
`exports/`, `runtime/` (stack logs, git-ignored).

> Sections: (a) the stack and the commands · (b) the verification table ·
> (c) the game, round by round, with the money reconciliation ·
> (d) new defects · (e) what could not be driven · (f) the verdict.

---

## (a) The stack, and the exact commands

Disposable, on this host, and this pass's own. **Never** the production
database at 192.168.50.38, never `/etc/globalstrat-plus.env`. Backups go to a
scratch directory **inside the evidence tree**; every LLM endpoint points at
an unreachable port, so Phase 2 narratives and the memo evaluation use the
template/heuristic fallback; `COMPETITION_REQUIRE_CLEAN_BUILD=false`. The
container, the database and both ports are this pass's own
(`globalstrat-walkthrough-ce3-pg`, database `globalstrat_walk3`, ephemeral
host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build       # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/harness
$H/make_db.sh                # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py           # migrate + legacy tables, load_scenario --preset electronics,
                             # a superuser and ONE instructor -- nothing else
python3 $H/start_stack.py    # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin
```

`seed.py` creates **nothing else**: the course, the section, the game, the
teams, the roster, every password and the schedule were all made from the
console by the instructor driver.

**The database readiness wait, as the brief asks.** The host disk is known to
stall, so `make_db.sh`'s `pg_isready` loop was lengthened from 40 × 1 s to
**300 × 1 s**, and `start_stack.py`'s readiness wait from 180 s to **900 s**.
On this run neither was needed: `make_db.sh` returned in **2.0 s**,
`seed.py` (migrate + scenario load) in **18.3 s**, and `start_stack.py` in
**2.7 s**. The longer windows are recorded because they are what the harness
now allows, not because they were consumed.

Drivers, in the order they were first run:

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. the refused 6th member → team configuration with team 1's home market set by hand to Africa → activate → **schedule and deadline with no page refresh (W-CE2-10)** → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, override, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after, operator-log wording and drill-down order checked | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round) | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| `lock_round.py` | completes the product-market rows a new product or market leaves empty, then locks from the Summary | `lock_round.py <lang> <team> <round>` |
| `check_round.py` | results/statement/leaderboard cross-check **and the money reconciliation**, all 8 teams | `check_round.py <round>` |
| `verify_plant_collision.py` | **new** — W-CE2-01 at the decision boundary, both orders, both languages | `verify_plant_collision.py <team> <round>` |
| `verify_plant_after_acquisition.py` | **new** — W-CE2-01 at the round: a plant built where a COMPLETED acquisition already brought one | `verify_plant_after_acquisition.py <team> <round> [after]` |
| `verify_withdraw.py` | **new** — W-CE2-02: withdrawing a queued plant, partnership and acquisition from the real pages | `verify_withdraw.py <lang> <team> <round>` |
| `probe_ma_card.py` | **new** — read-only: what the M&A card offers, and what it says when it does not | `probe_ma_card.py <lang> <team> <round>` |
| `verify_deadline_affordability.py` | **new** — W-CE2-03, W-CE-23, W-CE2-09, W-CE-18b on one screen and then on the statement | `verify_deadline_affordability.py <team> <round> [after]` |
| `verify_results_language.py` | **new** — W-CE-14, W-CE2-06, W-CE2-07 read by two members of one team, one English, one Chinese | `verify_results_language.py <round>` |
| `probe_scorecard.py` | **new** — the Strategic Scorecard read en → zh → en, to show a read does not mutate a hashed field | `probe_scorecard.py <round> [team-id…]` |
| `verify_coach_language.py` | **new** — W-CE2-08: the console's own switch, then the alerts it produces | `verify_coach_language.py set` / `read <round>` |
| `dbq.py`, `apicall.py`, `hold_lock.py`, `mark_competition.py`, `instructor_endgame.py`, `leak_summary.py`, `records_summary.py`, `shrink_screenshots.py`, `prune_screenshots.py` | as in walkthrough 2 | — |

**Harness changes, all recorded (no runtime code was touched):**

1. `make_db.sh` — its own container (`globalstrat-walkthrough-ce3-pg`) and
   database (`globalstrat_walk3`), and the readiness loop lengthened to 300 s.
2. `start_stack.py` — readiness wait 180 s → 900 s; its own dev secret key.
3. `check_round.py` — three changes. It now covers **all eight teams** rather
   than the first three. It adds the **money reconciliation** the brief asks
   for, per team per round, in two forms (below). And a revenue-equality check
   that read `num(...) or -1` treated a legitimate **$0.00** revenue as a
   mismatch, so every team that did nothing failed a check it should have
   passed; fixed.
4. `student_play.py` — two assertions re-specified against what the repaired
   pages actually render. (i) The M&A assertion failed because since W-CE2-02
   an *Acquire* button exists **only** for a target that is available; the
   driver now reads the target list and its `locked_reasons` and asserts that
   an unavailable target says why. (ii) The plant assertion required the
   stored `decision_plant.capacity_units` to be non-zero, but that field is an
   *addition* to the market's authored `plant_capacity_units`, which is what
   `engine/strategy_effects.py:288` builds with; a row of 0 is correct, and the
   walkthrough-2 version of this check was mis-specified (it failed there too).
5. `verify_results_language.py` — and this is a correction of method worth
   naming: **`Accept-Language` does not decide what a reader is told.** R43 and
   the W-CE2-05 repair make the platform answer in the language of the
   *reader's own stored enrolment*, which the sign-in and the in-game switch
   write. A first version of this driver sent the header and drew a wrong
   conclusion from it. The driver now reads the same round twice, as two
   different members of the same team, each having stated their language
   through `PUT /api/user/preferences/` — the route the switch itself calls.
6. `verify_plant_collision.py`, `verify_plant_after_acquisition.py`,
   `verify_withdraw.py`, `probe_ma_card.py`,
   `verify_deadline_affordability.py`, `probe_scorecard.py`,
   `verify_coach_language.py`, `readers.json` — new, described above.

**The money reconciliation** is recorded per team per round in
`records/check-round<N>.json` under `reconciliation`, in two forms:

* **the identity the platform publishes** — `cash_opening + operating_cash_flow
  + investing_cash_flow + financing_cash_flow == cash_closing`;
* **the plain form the brief asks for** — `opening cash + revenue − charges =
  closing cash`, where *charges* are the expense lines the statement carries,
  with the remainder named by the statement's own cash-flow lines; and, below
  that, the sum **a player can actually do with a finger on the Financial
  Reports screen**, using only the lines that page prints.

**Language** is set the product's own way — the in-game switch, or the
`PUT /api/user/preferences/` route it calls. **No visual claim is made about
Chinese glyphs**: this sandbox has no CJK font, so zh-CN screenshots show
missing-glyph boxes; the standard is the rendered DOM text, recorded per
screen.

**Leak scan** on every screen (`walk.scan`), the CRV2-13 standard. Console
errors and every API status ≥ 400 are captured per screen; the harness's own
aborted Google-Fonts requests (`net::ERR_FAILED`) are excluded from the
counts.

---

## (b) Verification of the walkthrough-2 defects

Every id was reproduced through the step walkthrough 2 recorded, on this
stack, in the language(s) it was found in. Screenshots are under
`handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/screenshots/`.

| id | sev (walkthrough 2) | the step, repeated | state | what is on the screen now | evidence |
|---|---|---|---|---|---|
| **W-CE2-01** | **P0** | a team builds a plant in its home market and acquires a target whose market is the same and `includes_plant`; close and process | **VERIFIED FIXED** | Both halves hold. **At the save**, in either order, the boundary refuses and names the market and the target: *The acquisition of AfriConnect Mobile already brings a plant in Africa, so a plant build there cannot be queued as well. Withdraw one of the two.* — and in Chinese, *收购非洲互联移动已在非洲带来一座工厂，因此不能同时安排在该市场建设工厂。请撤回其中一项。* Two builds in one market are refused too (*Your company has already queued a plant in Africa. One plant per market in a round.* / *贵公司本回合已在非洲安排建设工厂。每个市场每回合只能建设一座工厂。*), and a refused save leaves the draft untouched. **At the round**, Aurora Devices completed the AFR acquisition in round 2 and then built a plant in AFR in round 3: the round processed `FULLY_COMPLETE`, and the team holds three AFR plant rows with construction starts 1, 2 and 3 — three different natural keys, so the snapshot cannot collide. 13 of 13 checks | `v-collision-t1-r2-market-strategy-en.jpg`, `v-collision-t1-r2-corporate-en.jpg`, `v-paa-t1-r3-home-market-en.jpg`, `records/verify-plant-collision-t1-r2-en.json` |
| **W-CE2-02** | P1 | queue an acquisition costing more than the team's cash, then open Review & Submit | **VERIFIED FIXED** | Each queued commitment is shown where it was made, with a **Withdraw** control that empties the stored row: a plant (*Plant build queued* → Withdraw → the Build Plant offer is back), a partnership and an acquisition, all three driven on the real pages and read back from the draft. The strategy context publishes `affordability` (`cash_on_hand`, `committed_total`, `unallocated`). An offer the team cannot fund is **disabled with the figures beside it**, in Chinese too: *收购 — $18.0M* disabled, *需要 $18.0M；未分配资金 $10.5M*; the partnership *+* offer is likewise disabled once cash is short. Every unavailable target states its reason (*第 3 回合起可用*, *需要先进入西欧*, *已被 … 收购*). 14 of 14 checks | `v-wd-t1-r2-01-plant-queued-en.jpg` … `v-wd-t1-r2-07-acquisition-withdrawn-en.jpg`, `v-ma-card-t3-r2-zh-CN.jpg` |
| **W-CE2-03** | P1 | let a team with a refused lock be deadline-closed, then read its statement | **VERIFIED FIXED for the acquisition; the rest of the draft is still executed** | Nova Circuit went into round 3's close as a **draft** the lock had refused (*Committed spend of $49,287,190.00 exceeds available cash of $19,287,190.91.*). After the close its bid was **withheld**: no `team_acquisition` row, nothing charged, the decision row kept, and the team told in those words — *Your bid for AsiaElec Manufacturing was not fulfilled: Nova Circuit has committed more this round than its available cash, which is the same reason the round's decisions could not be locked. No cost has been charged.* **But the rest of the draft was executed anyway**, and the team closed at **−$7,431,324.09**; Aurora Devices, whose over-cash draft carried a plant build rather than an acquisition, closed at **−$6,468,269.34**. That is the remainder the repair discloses in its §7.1, and it is what starts W-CE3-02 | `v-deadline-t2-r3-summary-en.jpg`, `v-deadline-t2-r3-after-statement-en.jpg`, `records/verify-deadline-affordability-t2-r3-*.json` |
| **W-CE2-04** | P2 | make an action fail or be refused; read the Operator Log | **VERIFIED FIXED** | The P0 that produced the raw `SnapshotError` cannot be reached any more, so two refusals an operator can still cause were driven — processing an already-processed round, and the lifecycle override with no written reason. The Operator Log carries no storage field name, no Python argument, no raw exception and no `engine_failure` token; the rows read as sentences, and the *Before → after* column is labelled words throughout, so W-CE-07 still holds as well | `v-oplog-refusals-en.jpg`, `records/verify-operator-log-refusal-en.json` |
| **W-CE2-05** | P1 | sign in as the second member of a team in zh-CN, ask the analyst | **VERIFIED FIXED** | In **round 1** — the round it failed in before — Meridian Tech's first enrolment was English (`s2609 → en`, which is what the team rule would answer) and its second member signed in in Chinese (`s2610 → zh-CN`). The analyst answered the student who asked: *本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。* No second sign-in by the first member was needed | `p3-r1-83-research-analyst-asked-zh-CN.jpg`, `harness/dbq.py enrollments` |
| **W-CE2-06** | P2 | any zh-CN team with a market, Products or Round Results | **VERIFIED FIXED where it was found; two places it did not reach** | Market names are Chinese on Market Strategy (北美 / 东亚 / 西欧 / 非洲 / 南美), on Products, on Round Results (`.markets[].market_name`, `.products[].market_name`), on the events ticker (全球) and **inside the price-adjustment notice**: *非洲 中的 Nexus One：您输入的价格为 $1,755，超出本回合允许的区间…*. `Western Europe`, which walkthrough 2 counted 51 times, appears **0 times** on a Chinese screen. Still English: the market names inside the Strategic Scorecard's detail tables (W-CE3-06) and on the Logistics and Trade Finance pages (W-CE3-08) | `p3-r1-30-products-zh-CN.jpg`, `records/verify-results-r1.json`, `records/verify-results-r3.json` |
| **W-CE2-07** | P2 | zh-CN team, Round Results → Strategic Scorecard | **VERIFIED FIXED for two of the three criteria** | On a Chinese read `budget_discipline` and `financial_prudence` come back in Chinese — *支出未超出经营预算。财务纪律良好。*, *杠杆水平保守。财务状况稳健。* — while the **English reader still gets the byte-identical stored English**, and a Chinese read does **not** mutate the stored row (driven en → zh → en on four teams, `probe_scorecard.py`). The third criterion, `governance_tax`, is still *No governance-tax conflict detected.* on a Chinese screen — W-CE3-05 | `records/verify-results-r1.json`, `records/verify-results-r3.json` |
| **W-CE2-08** | P1 | zh-CN console → AI Coach after a processed round | **VERIFIED FIXED, with two conditions** | The console header's switch now **writes to the server** for an instructor with no enrolment: `PUT /api/user/preferences/` answered `{"language": "zh-CN"}` and a `GET` read it back. The alerts written after it are Chinese — round 3 **32 of 34**, round 4 **32 of 33** (*Lumen Devices 的绩效指数下降了 5.1 点…*) — where walkthrough 2 had none. Condition (i): an alert is written in the language stored **at processing time**, so rounds 1 and 2, processed before the switch, are **0 of 56** Chinese and stay English for ever, leaving the panel permanently mixed. Condition (ii): the `distress` alert type is English in every round — W-CE3-07 | `v-coach-console-switched-zh-CN.jpg`, `v-coach-panel-r3-zh-CN.jpg`, `records/verify-coach-language-*.json` |
| **W-CE2-09** | P2 | spend past the budget, open Review & Submit | **VERIFIED FIXED for the formatting; the sentence around it is still wrong** | No unformatted negative anywhere on the Decision Summary: a scan for `$-<digits>` with no magnitude suffix found **nothing**, and the figure reads `$-30.0M`. But the line it sits in says *Committed this round: $49.3M of $19.3M cash — **$-30.0M not yet committed***: a team that is $30.0M **over**-committed is told that amount is "not yet committed", and the sign is written `$-30.0M` rather than −$30.0M — W-CE3-09 | `v-deadline-t2-r3-summary-en.jpg` |
| **W-CE2-10** | P1 | new game → Activate Game → Round control › Set deadline, without reloading | **VERIFIED FIXED** | On the very first attempt, with no page refresh: *CE 2026 Heat A: deadline updated.*, `deadline=2026-09-25T18:00:00+00:00` on the server, and the console still on *Game Control*. The driver's "reload and repeat" branch — the one that had to run in walkthrough 2 — did not fire at all (`observed.deadline_first_attempt` is absent from the record). Extend, pause and resume all followed on the same card with no reload | `i12-game-activated-en.jpg`, `i14-set-deadline-modal-en.jpg`, `i14b-after-set-deadline-en.jpg` |

### The three rows walkthrough 2 marked CHANGED

| id | sev | the step, repeated | state | what is on the screen now | evidence |
|---|---|---|---|---|---|
| **W-CE-18b** | P1 | queue an acquisition in one round, open Review & Submit | **VERIFIED FIXED** | The screen carries **one** total for what the round costs — *Committed this round: $49.3M of $19.3M cash* and the blocker's *Committed spend of $49,287,190.00* are the same figure from the same assessment — and the other figure on the page is explicitly a different concept, labelled as such: *R&D, marketing and strategy spending totals $42.5M, which is $37.5M over the operating budget of $5.0M*. The unformatted `Unallocated: $-12553689` is gone. What remains is the wording of the negative line (W-CE3-09) | `v-deadline-t2-r3-summary-en.jpg` |
| **W-CE-23** | P1 | spend past the budget in one round, then try to lock the next | **STILL PRESENT, and in a long game it stops the team** | The half that was repaired holds: the lock is refused **in the round the spend is committed**, with the figures on the page before the click, and the team can now **withdraw** what it queued. The half left to a ruling is now decisive: once cash is negative, the affordability check compares committed spend with a negative number, so **the lock can never be offered again**. Driven on Nova Circuit at round 4, cash −$7,431,324.09: every declared budget zeroed, no plant, no partnership, no acquisition, no ESG, no dividend — still refused; and **raising $30,000,000 of new debt did not move the available-cash figure by a cent**. Both teams that went negative were deadline-closed in every remaining round — W-CE3-02 | `v-negcash-t2-r4-stripped-en.jpg`, `v-negcash-t2-r4-after-financing-en.jpg` |
| **W-CE-24** | P1 | Game Control › Game Lifecycle › Advance Round with teams pending | **VERIFIED FIXED** | With a written reason and **all four playing teams pending**, the override closed the round and advanced it: round 4 went `processed / FULLY_COMPLETE` and round 5 opened, with no `round_not_ready` refusal anywhere in the run. The operator row reads *advance_round_legacy · committed · Walkthrough: advancing round 4 with teams still pending.* | `r4-01-lifecycle-advance-modal-en.jpg`, `records/instructor-round4-lifecycle-en.json` |

---

## (c) The game, round by round

*(filled in below as the run proceeds)*

---

## (d) New defects

Same severity scale as the earlier passes: **P0** data loss / cannot proceed /
wrong number shown to a player · **P1** wrong or missing behaviour ·
**P2** wording or cosmetic.

| id | screen | role | lang | what the user sees | what they should see | sev | repro | evidence |
|---|---|---|---|---|---|---|---|---|
| **W-CE3-01** | Financial Reports › Cash Flow, and the engine | student, instructor | EN, zh | **Money leaves a team between rounds and appears on no statement.** Aurora Devices' round-2 statement closes at **$13,523,631.84**; its round-3 statement opens at **$11,523,631.84**. Meridian Tech: $18,296,607.20 → $16,296,607.20. Solaris Consumer: $24,566,940.00 → $22,566,940.00. Nova Circuit the same $2,000,000 between rounds 3 and 4, and every team that switched its tax structure in round 1 opened round 1 $2,000,000 below the $50,000,000 the round-0 row shows. The amount is always exactly the tax structure's `setup_cost` (`regional_hub: 2000000`). `engine/costs.py:1165` does `team.cash_on_hand -= structure.setup_cost` during Phase 1, **before** `engine/financials.py:136` reads `cash_opening = team.cash_on_hand` — so the statement's own identity (`opening + OCF + ICF + FCF == closing`) closes perfectly on every team in every round, and the money is simply not there any more. The team is never told, and no line, tab or figure on any screen accounts for it | the charge booked at resolution through the cost pipeline, the way R36 / V2-088 already moved the **org structure's** transition cost out of exactly this pattern (`views/cc32b_views.py:166-185` says so in as many words) — or, failing that, a line on the statement | **P0** | switch the tax structure from Finance › Tax Structure, resolve the round, compare the previous round's `cash_closing` with this round's `cash_opening` on Financial Reports | `records/check-round3.json` and `check-round4.json` (`reconciliation.*.cash_carried_between_rounds`), `harness/check_round.py`, `harness/dbq.py sql "select * from team_tax_structure"` |
| **W-CE3-02** | Decision Summary, every round after a team's cash goes negative | student | EN, zh | **A team whose cash is negative can never lock again.** The affordability blocker compares committed spend with cash on hand; once cash is negative no spend can ever be small enough. Driven on Nova Circuit at round 4 (cash −$7,431,324.09): with every declared budget set to 0 and no plant, partnership, acquisition, ESG investment or dividend, the Summary still refuses — *Committed spend of $8,800,000.00 exceeds available cash of $-7,431,324.09* — and **raising $30,000,000 of new debt does not change the available-cash figure by a cent**, because the check ignores the financing the team has decided. Two of the four playing teams reached that state by round 4 and were deadline-closed in every round afterwards; they never submitted a decision again. They reach it because the deadline executes the very draft the lock refused for everything except an acquisition (W-CE2-03's disclosed §7.1 remainder) | either the deadline applies the same rule to the rest of the draft as it now does to an acquisition, or the affordability check counts the financing the team has decided — this is the unruled question already before the owner as `WALK_CE_STUDENT_NUMBERS_2026-09-22.md` §8.1 and `WALK_CE2_ROUND_BLOCKERS_2026-09-23.md` §7.3, and the walkthrough is what it looks like on a real game | **P0** | let a team be deadline-closed with a draft the lock refused; in the next round strip every decision back to nothing and try to lock | `v-negcash-t2-r4-stripped-en.jpg`, `v-negcash-t2-r4-after-financing-en.jpg`, `records/probe-negative-cash-lock-t2-r4-en.json` |
| **W-CE3-03** | Financial Reports › Income Statement | student | EN, zh | **The income statement on the screen does not add up.** The page prints Revenue, COGS, Gross Profit, R&D, Marketing, Strategy, Research, Compliance, Admin, Net Income and Margin (`pages/incomeStatementRows.js` `INCOME_STATEMENT_LINES`) and nothing else. It does **not** print interest, tax, logistics/tariff or inventory, all four of which the same API serves on the same row. So `Gross Profit − the expense lines shown` differs from the `Net Income` printed beside them by **$0.36M to $2.80M**, every team, every round — Aurora Devices round 1: gross profit −$349,928, the lines shown take it to −$10,705,618, and Net Income reads −$12,788,868 | every charge that makes up net income on the statement that shows net income | **P1** | open Financial Reports › Income Statement for any team after any round and add the columns up | `records/check-round{1,2,3,4}.json` (`reconciliation.*.page_income_statement_gap`), `s-after-r1-10-financial-reports-en.jpg` |
| **W-CE3-04** | the served income statement itself | student | EN, zh | **Some charges are on no served field at all.** `operating_income` also subtracts depreciation (10 % of plant book value), the tax structure's `annual_maintenance_cost` ($400,000 for Regional Hub), product-retirement cost and the supply-chain disruption and compliance costs — none of which is a field of `RoundResultFinancials`. So even `gross_profit − every expense field the API serves` differs from the served `operating_income` by **$0.58M to $2.40M** for a playing team. A team that built a plant cannot find its depreciation anywhere | a line, or at least a field, for every charge inside operating income | **P1** | read `/api/games/N/teams/T/financial-reports/history/` and subtract the expense fields from gross profit | `records/check-round{1,2,3,4}.json` (`reconciliation.*.page_gap_not_in_any_served_field`), `backend/core/engine/financials.py:163-171` |
| **W-CE3-05** | Marketing Mix | student | EN, zh | **The page never names the product** in a market that holds exactly one. `MarketingPage.js:697` prints `d.product_name` only inside the inner product tab label, and that inner `Tabs` is rendered only when `items.length > 1`; with one product the card is rendered directly. A team with one product in each of two markets sees two tabs named only *Africa (1)* and *North America (1)* and sets a price, a volume, a campaign focus and a channel split without being told which product it is deciding for | the product named on the card, as it is when a market holds two | **P1** | any team with one product in a market, Marketing Mix | `x-t4-r3-marketing-completed-en.jpg`, `records/lock-t4-r3-en.json` (`observed.row_reached_without_product_name`) |
| **W-CE3-06** | Round Results › Strategic Scorecard | student | zh | The **governance/tax sentence is still English** on a Chinese screen — *No governance-tax conflict detected.* — while the budget-discipline and financial-prudence sentences beside it are Chinese. Every team, every round | the same sentence in the reader's language, as its two siblings now are | P2 | zh-CN team, Round Results → Strategic Scorecard | `records/verify-results-r1.json`, `records/verify-results-r3.json` |
| **W-CE3-07** | Round Results › Strategic Scorecard, the detail tables | student | zh | The market's **English name** inside the scorecard's own tables — `coherence.breakdown.entry_mode_risk.details[].market`, `…positioning_price…`, `…distribution_positioning…` all carry *Africa*, *North America*, *East Asia*, *Western Europe*, *South America* on a Chinese read, while the same market is 非洲 / 北美 everywhere else on the same response | 非洲, as the rest of the response already says | P2 | zh-CN team, Round Results → Strategic Scorecard | `records/verify-results-r1.json` (`market_names` with the path each name sits at) |
| **W-CE3-08** | Instructor › AI Coach | instructor | zh | The **financial-distress alert is English** whatever the console's language — *Aurora Devices has entered financial distress · Cash closing: $-6,468,269. Net income: … Consequences, in force from the next round until the company returns to positive cash and profitability: +10% talent turnover, share price floor at 0.7x book value, no new debt, and no acquisitions.* — while the other 32 alerts of the same round are Chinese. It is the alert that matters most, and it is the one an instructor cannot read | the alert in the instructor's language, like its 32 siblings | P2 | zh-CN console, AI Coach, after a round in which a team went into distress | `v-coach-panel-r3-zh-CN.jpg`, `harness/dbq.py sql "select alert_type, title from instructor_alert"` |
| **W-CE3-09** | Supply Chain › Logistics, Trade Finance | student | zh | The market's **English name and code** on a Chinese decision screen: *North America NA*, *East Asia APAC*, *Western Europe EU*, *Africa AFR*, *South America LATAM*, in the routes table, the terms-by-market table and the customs table. `views/sc_views.py:365` serves `{'id': m.id, 'code': m.code, 'name': m.name, …}` — the stored English name with no `get_localized_field`, the one read W-CE2-06's repair did not cover | 北美, 东亚, 西欧, 非洲, 南美, as on every other page | P2 | zh-CN team, Supply Chain › Logistics | `s-after-r1-10-d-logistics-zh-CN.jpg`, `s-after-r1-10-d-trade-finance-zh-CN.jpg` |
| **W-CE3-10** | Products, R&D, Dashboard › Balanced Scorecard, the post-login modal | student | zh | The platform's generated default name keeps its **English suffix** on a Chinese screen — *Meridian Tech Base Platform*. W-CE2-06's repair added `platform_display_name` and `ProductContextView.products[].platform_name` uses it, but three reads beside it do not: `ProductContextView.active_platforms[].name` (the Create Product modal's platform selector, `views/decisions.py:2031-2040`), the R&D context's `owned_platforms[].platform_name`, and `views/scorecard.py:177`, which also hard-codes the English literal `'None'` as the value a team with no platform would read | 基础平台, as `platform_display_name` already renders it | P2 | zh-CN team → Product Portfolio → Create Product; and the dashboard | `p3-r1-31-products-create-modal-zh-CN.jpg`, `s-after-r1-10-dashboard-zh-CN.jpg` |
| **W-CE3-11** | the post-login modal, Strategic Briefing | student | zh | The **Strategic Briefing is English only**. `core/engine/briefing.py` builds every sentence as an f-string with no catalogue entry — 21 `parts.append(f"…")` calls and 90 distinct English literals, none of them passing through `participant_message` — so a Chinese student's first screen after signing in reads *Revenue declined 55% to $0.5M — investigate segment performance.* and *Cash reserves critically low at $-7.4M. Immediate action required.* It is the same class as W-CE2-07, on a bigger surface | the briefing in the team's language | P2 | zh-CN student, sign in after a processed round | `s-after-r1-01-post-login-modal-zh-CN.jpg`, `backend/core/engine/briefing.py` |
| **W-CE3-12** | Financial Reports, the tab bar | student | zh | The tab label **`Trade Finance & FX` is a hard-coded English string** — `pages/FinancialReportsPage.js:975` has `label: 'Trade Finance & FX'` where every sibling tab uses `t(...)` — so it is English on a Chinese screen | the label from the catalogue, like the eight tabs around it | P2 | zh-CN team → Financial Reports | `s-after-r1-10-financial-reports-zh-CN.jpg` |
| **W-CE3-13** | Decision Summary › Budget Summary | student | EN, zh | A team that is **over**-committed is told the amount it is over by is *not yet committed*: *Committed this round: $49.3M of $19.3M cash — **$-30.0M not yet committed***. The figure is correctly abbreviated now (W-CE2-09's repair), but the sign is written `$-30.0M` rather than −$30.0M and the label contradicts it | a sentence that says the team is over by $30.0M | P2 | commit past the cash, open Review & Submit | `v-deadline-t2-r3-summary-en.jpg` |
| **W-CE3-14** | R&D Investment › Create New R&D Platform | student | EN, zh | The scenario's third platform generation carries `unlock_round: 5`, but at round 5 it is **not listed at all and no reason is given**: `views/decisions.py:1910-1917` `continue`s past Gen 3 unless the team already holds an **active Gen 2 platform**, so the generation simply is not there. Every other gate on the platform now names itself — the M&A card says *第 3 回合起可用*, the platform round check says *available from round N* — and this one does not | the generation listed with its requirement stated, like every other locked offer | P2 | round 5, a team with no Gen 2 platform, R&D → Create New R&D Platform | `v-r5-t4-rd-create-modal-en.jpg`, `records/verify-round5-unlocks-t4-r5-en.json` |

---

## (e) What could not be driven

*(filled in below as the run proceeds)*

---

## (f) Verdict

*(filled in below as the run proceeds)*
