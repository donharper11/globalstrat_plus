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
| `verify_operator_log_refusal.py` | **new** — W-CE2-04: two refusals an operator can still cause, then the Operator Log | `verify_operator_log_refusal.py <lang>` |
| `verify_round5_unlocks.py` | **new** — the progressive disclosure round 5 opens: the customs classification and the Gen 3 platform | `verify_round5_unlocks.py <lang> <team> <round>` |
| `probe_negative_cash_lock.py` | **new** — W-CE-23's remainder: what a team with negative cash can lock | `probe_negative_cash_lock.py <team> <round>` |
| `probe_irreducible_commitment.py` | **new** — what a team cannot take out of its round, and whether financing helps | `probe_irreducible_commitment.py <lang> <team> <round>` |
| `lock_within_cash.py` | **new** — cut the round back to what the cash allows, the way a player would, then lock | `lock_within_cash.py <lang> <team> <round>` |
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
6. `shrink_screenshots.py` was run between sections and finally at
   **760 px / quality 28**, and `prune_screenshots.py` — widened from
   walkthrough 2's rounds 3–4 to **rounds 3 onwards** — dropped 488
   near-duplicate per-round decision screens (13.9 MB). 741 screenshots
   remain, 19.4 MB; every screen that was ever taken is still named in its
   run's JSON record, which keeps the full list.
7. `verify_plant_collision.py`, `verify_plant_after_acquisition.py`,
   `verify_withdraw.py`, `probe_ma_card.py`,
   `verify_deadline_affordability.py`, `probe_scorecard.py`,
   `verify_coach_language.py`, `verify_operator_log_refusal.py`,
   `verify_round5_unlocks.py`, `probe_negative_cash_lock.py`,
   `probe_irreducible_commitment.py`, `lock_within_cash.py`, `readers.json`
   — new, described above and in (e).
8. `lock_round.py` — a marketing row in a market holding exactly one product
   could not be reached, because `MarketingPage` renders that product's card
   directly with no inner tab and prints the product's name **only** in the
   tab label it therefore does not draw. The driver now takes the market tab
   as the row and records the fact; the missing name is W-CE3-05.
9. `student_play.py` — it clicked the partnership *+* offer unconditionally
   and timed out once the affordability gate started disabling it; it now
   records a disabled offer instead of clicking it.

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
| **W-CE2-04** | P2 | make an action fail or be refused; read the Operator Log | **VERIFIED FIXED** | The P0 that produced the raw `SnapshotError` cannot be reached any more, so two refusals an operator can still cause were driven — processing an already-processed round, and the lifecycle override with no written reason. The Operator Log carries no storage field name, no Python argument, no raw exception and no `engine_failure` token; the rows read as sentences, and the *Before → after* column is labelled words throughout, so W-CE-07 still holds as well | `v-oplog-refusals-en-en.jpg`, `records/verify-operator-log-refusal-en.json` |
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

**The game.** Course `CE26` *Global Strategy Practicum* → section `CE26-A`
*Heat A* → game **CE 2026 Heat A**, scenario *Consumer Electronics 2026*,
**8 teams**, 27 students on the roster, every one of them created from the
console by the instructor. Teams 1–4 played every round; teams 5–8 made no
decision in any round and were resolved by the deadline each time, which is a
path worth having on record. **Team 3, Meridian Tech, played in Simplified
Chinese** — its first enrolment states English and its second states Chinese,
which is the condition W-CE2-05 was found in.

| team | home market | profile | plays |
|---|---|---|---|
| 1 Aurora Devices | Africa (**set by hand from the console**) | The Innovator | EN, the edge-case profile |
| 2 Nova Circuit | South America | The Brand Builder | EN |
| 3 Meridian Tech | North America | The Workhorse | **zh-CN** |
| 4 Solaris Consumer | Africa | The Green Pioneer | EN |
| 5–8 | APAC / APAC / AFR / EU | — | no decisions, deadline-closed every round |

### Part 1 — the instructor builds the game (EN) — `records/instructor-setup-en.json`

26 checks passed, none failed. Course and section created and selected; the
game created with 8 teams (*Game "CE 2026 Heat A" created with 8 teams.*);
`roster.csv` uploaded with the outcome announced on the panel and staying
there (*Added 27 student(s) to the roster. File: roster.csv*); 26 students
assigned and the **sixth member of a full team refused in business language**
(*No students were assigned — Titan Micro already has 5 members, the maximum
this section allows. Choose another team, or raise the team size limit.*);
**team 1's home market set by hand to Africa** and saved as `AFR`; the game
activated with the console staying on *Game Control*; **the round-1 deadline
set from the same card with no page refresh** (W-CE2-10); the deadline
extended 25 → 26 Sep; paused and resumed; an operator event injected; the
Operator Log read; every password issued in bulk; the Team Overview
drill-down opened on the decisions; a grading rubric created, grades
calculated, **a category score overridden** (*Aurora Devices: Performance
Index score overridden.*) and three CSVs exported.

### The end of the game — `records/instructor-endgame-en.json`

| # | screen | what happened | evidence |
|---|---|---|---|
| end-grading | Grading & Export | *Calculate Grades* on six resolved rounds: *Grades calculated*; the Team Grades table shows Aurora Devices **88.0 Overridden** (the score overridden from the console before round 1), Nova Circuit 54.6, Meridian Tech 60.3, and an *Override* control on every row. The three CSVs downloaded again | `end-grading-after-4-rounds-en.jpg`, `exports/final-*.csv` |
| end-delete-has-record | Delete Game (reason) | **refused**: *CE 2026 Heat A already has a record of instructor actions or team decisions. That record is permanent, so the game cannot be deleted. Archive the game instead…* | `end-delete-has-record-after-en.jpg` |
| end-delete-competition | Delete Game after `mark_competition.py` | **refused**: *CE 2026 Heat A is a competition game, so it cannot be deleted. Its results and records have to stay available after the event…* | `end-delete-competition-after-en.jpg` |
| end-reset | Reset to Setup (reason) | **refused** — W-CE-26 still holds: *CE 2026 Heat A is a competition game, so it cannot be reset to setup. Its rounds, results and records have to stay as they were played…* | `end-reset-modal-en.jpg`, `end-reset-after-en.jpg` |
| end-archive | Archive Game (reason) | **accepted**: *Game archived. You can now create a new game for this section.*; status `archived` | `end-archive-after-en.jpg` |
| after archive | results, statements, leaderboard | still readable: round 1 and round 6 results both `200` with their index values, and the round-6 leaderboard still serves all eight teams | `records/instructor-endgame-en.json` |

*Finish game* itself was not reached — see (e).

### Rounds 1–6

Every round was resolved **from the console**, and the three paths were all
used: *Close round now → Run post-round processing → Advance* (round 1),
*Close & process now* with a written reason (rounds 2, 3, 5, 6) and the
**Game Lifecycle › Advance Round** override with a written reason and four
pending teams (round 4). Every round reached `processed`; rounds 1–4 and 6
reached `FULLY_COMPLETE`, round 5 `RESULTS_AVAILABLE` then `FULLY_COMPLETE`.
**No round failed, and there was no 5xx anywhere in the walkthrough.**

| round | how it was resolved | who locked | phase 1 | standings (rank team index) |
|---|---|---|---|---|
| 1 | Close → process → advance | all four playing teams locked from the screen | 3.84 s | 1 Meridian Tech 57.91 · 2 Nova Circuit 55.29 · 3 Aurora Devices 54.54 · 4 Solaris Consumer 54.42 · 5 Helix Digital 49.98 · 6 Apex Devices 49.93 · 7 Lumen Devices 49.91 · 8 Zenith Hardware 49.88 |
| 2 | Close & process now (reason) | all four locked | 4.39 s | 1 Meridian Tech 60.59 · 2 Nova Circuit 55.11 · 3 Solaris Consumer 53.57 · 4 Aurora Devices 53.14 · 5 Helix Digital 44.98 · 6 Apex Devices 44.88 · 7 Lumen Devices 44.85 · 8 Zenith Hardware 44.78 |
| 3 | Close & process now (reason) | teams 3 and 4 locked; 1 and 2 deadline-closed with drafts the lock refused | 4.55 s | 1 Meridian Tech 62.51 · 2 Nova Circuit 53.71 · 3 Solaris Consumer 53.56 · 4 Aurora Devices 53.29 · 5 Helix Digital 39.98 · 6 Apex Devices 39.83 · 7 Lumen Devices 39.79 · 8 Zenith Hardware 39.69 |
| 4 | **Game Lifecycle › Advance Round** (reason), four teams pending | **none** — every playing team refused for cash | — | 1 Meridian Tech 63.95 · 2 Nova Circuit 53.84 · 3 Solaris Consumer 52.97 · 4 Aurora Devices 52.77 · 5 Helix Digital 34.97 · 6 Apex Devices 34.76 · 7 Lumen Devices 34.71 · 8 Zenith Hardware 34.57 |
| 5 | Close & process now (reason) | **none** | 4.82 s | 1 Meridian Tech 65.34 · 2 Nova Circuit 53.90 · 3 Aurora Devices 52.27 · 4 Solaris Consumer 51.53 · 5 Helix Digital 29.96 · 6 Lumen Devices 29.62 · 7 Zenith Hardware 29.44 · 8 Apex Devices 28.77 |
| 6 | Close & process now (reason) | **none** | 4.45 s | 1 Nova Circuit 54.59 · 2 Aurora Devices 52.86 · 3 Solaris Consumer 52.83 · 4 Meridian Tech 60.34 · 5 Helix Digital 24.95 · 6 Lumen Devices 24.53 · 7 Zenith Hardware 24.31 · 8 Apex Devices 23.69 |

**What was decided, at least once each.** Budget allocation (and an
over-allocation flagged on screen); a **typed** loan, repayment and dividend,
each stored as typed; a tax-structure switch; R&D (the platform modal opened
and refused for budget every round — W-CE-19, deferred calibration); a new
product and a product retired end-of-round; the marketing mix with an
in-band price, an **out-of-band price kept and adjusted at close**, and a
**blank price**; a market entry; a **plant build**; a **partnership**;
**compliance investment** (round 2 on); **talent** headcount, training and
staff allocation; **ESG** investment and a governance commitment; an
**organisation-structure switch**; an **acquisition** completed (round 2) and
another **withheld at the deadline** (round 3); a **board memo** over the word
limit and then within it, evaluated; a **bought research report**; **analyst
questions refused visibly and charged nothing**; an **autosave refused while
an operator held the game lock**, shown with a retry and landing afterwards;
and, at round 5, the **customs classification** on the Logistics page, which
that page locks until round 5.

### The money, per team per round

`opening cash + revenue − charges = closing cash` is checked two ways in
`records/check-round<N>.json`. The identity the platform publishes —
`cash_opening + operating + investing + financing = cash_closing` — **closes
to the cent on all eight teams in all six rounds, every time**. Two other
things do not, and both are new defects:

* the **opening cash of a round is not always the closing cash of the round
  before** (W-CE3-01), and
* the **income statement on the screen does not add up** (W-CE3-03/04).


#### Round 1

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | $48,000,000 | $189,672 | $11,778,540 | $32,511,132 | yes | **no, short by $2,083,250** |
| Nova Circuit | $48,000,000 | $664,020 | $11,962,141 | $26,801,879 | yes | **no, short by $2,802,670** |
| Meridian Tech | $48,000,000 | $2,100,000 | $11,145,050 | $23,054,950 | yes | **no, short by $2,520,000** |
| Solaris Consumer | $48,000,000 | $180,320 | $11,820,060 | $32,460,260 | yes | **no, short by $2,007,600** |
| Apex Devices | $50,000,000 | $0 | $1,010,000 | $48,990,000 | yes | **no, short by $360,000** |
| Zenith Hardware | $50,000,000 | $0 | $1,250,000 | $48,750,000 | yes | **no, short by $600,000** |
| Helix Digital | $50,000,000 | $0 | $650,000 | $49,350,000 | yes | yes |
| Lumen Devices | $50,000,000 | $0 | $1,070,000 | $48,930,000 | yes | **no, short by $420,000** |

#### Round 2

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | $32,511,132 | $283,500 | $23,771,000 | $13,523,632 | yes | **no, short by $2,154,575** |
| Nova Circuit | $26,801,879 | $670,496 | $12,685,185 | $19,287,191 | yes | **no, short by $2,585,520** |
| Meridian Tech | $23,054,950 | $2,601,760 | $11,860,103 | $18,296,607 | yes | **no, short by $2,220,000** |
| Solaris Consumer | $32,460,260 | $211,680 | $12,605,000 | $24,566,940 | yes | **no, short by $1,911,600** |
| Apex Devices | $48,990,000 | $0 | $1,010,000 | $47,980,000 | yes | **no, short by $360,000** |
| Zenith Hardware | $48,750,000 | $0 | $1,250,000 | $47,500,000 | yes | **no, short by $600,000** |
| Helix Digital | $49,350,000 | $0 | $650,000 | $48,700,000 | yes | yes |
| Lumen Devices | $48,930,000 | $0 | $1,070,000 | $47,860,000 | yes | **no, short by $420,000** |

#### Round 3

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | $11,523,632 | $1,047,133 | $15,139,034 | −$6,468,269 | **no, −$2,000,000** | **no, short by $2,780,400** |
| Nova Circuit | $19,287,191 | $472,500 | $31,691,015 | −$7,431,324 | yes | **no, short by $2,523,900** |
| Meridian Tech | $16,296,607 | $2,576,000 | $15,973,720 | $6,998,887 | **no, −$2,000,000** | **no, short by $2,740,000** |
| Solaris Consumer | $22,566,940 | $973,258 | $16,505,798 | $11,134,400 | **no, −$2,000,000** | **no, short by $2,250,000** |
| Apex Devices | $47,980,000 | $0 | $1,010,000 | $46,970,000 | yes | **no, short by $360,000** |
| Zenith Hardware | $47,500,000 | $0 | $1,250,000 | $46,250,000 | yes | **no, short by $600,000** |
| Helix Digital | $48,700,000 | $0 | $650,000 | $48,050,000 | yes | yes |
| Lumen Devices | $47,860,000 | $0 | $1,070,000 | $46,790,000 | yes | **no, short by $420,000** |

#### Round 4

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | −$6,468,269 | $1,009,372 | $15,688,671 | −$21,147,568 | yes | **no, short by $2,535,600** |
| Nova Circuit | −$9,431,324 | $1,350,405 | $11,458,872 | −$19,939,791 | **no, −$2,000,000** | **no, short by $2,533,000** |
| Meridian Tech | $6,998,887 | $2,550,240 | $14,768,507 | −$719,380 | yes | **no, short by $2,478,000** |
| Solaris Consumer | $11,134,400 | $948,444 | $15,313,053 | $1,269,791 | yes | **no, short by $2,043,200** |
| Apex Devices | $46,970,000 | $0 | $1,010,000 | $45,960,000 | yes | **no, short by $360,000** |
| Zenith Hardware | $46,250,000 | $0 | $1,250,000 | $45,000,000 | yes | **no, short by $600,000** |
| Helix Digital | $48,050,000 | $0 | $650,000 | $47,400,000 | yes | yes |
| Lumen Devices | $46,790,000 | $0 | $1,070,000 | $45,720,000 | yes | **no, short by $420,000** |

#### Round 5

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | −$23,147,568 | $1,018,192 | $13,864,516 | −$36,393,892 | **no, −$2,000,000** | **no, short by $2,802,880** |
| Nova Circuit | −$19,939,791 | $1,354,500 | $12,124,565 | −$30,709,856 | yes | **no, short by $2,028,540** |
| Meridian Tech | −$2,719,380 | $2,576,000 | $14,251,200 | −$14,794,580 | **no, −$2,000,000** | **no, short by $3,032,200** |
| Solaris Consumer | −$730,209 | $957,264 | $13,223,938 | −$13,516,883 | **no, −$2,000,000** | **no, short by $2,514,880** |
| Apex Devices | $45,960,000 | $0 | $1,010,000 | $44,710,000 | yes | **no, short by $600,000** |
| Zenith Hardware | $45,000,000 | $0 | $1,250,000 | $43,750,000 | yes | **no, short by $600,000** |
| Helix Digital | $47,400,000 | $0 | $650,000 | $46,750,000 | yes | yes |
| Lumen Devices | $45,720,000 | $0 | $1,070,000 | $44,530,000 | yes | **no, short by $540,000** |

#### Round 6

| team | opening cash | revenue | charges on the statement | closing cash | opening == last closing | the statement adds up |
|---|---|---|---|---|---|---|
| Aurora Devices | −$36,393,892 | $1,499,400 | $14,036,982 | −$49,051,474 | yes | **no, short by $2,425,592** |
| Nova Circuit | −$32,709,856 | $1,499,400 | $11,958,782 | −$43,689,238 | **no, −$2,000,000** | **no, short by $2,476,686** |
| Meridian Tech | −$14,794,580 | $0 | $14,120,000 | −$29,034,580 | yes | **no, short by $2,620,980** |
| Solaris Consumer | −$13,516,883 | $1,499,400 | $14,332,732 | −$26,350,215 | yes | **no, short by $1,962,392** |
| Apex Devices | $44,710,000 | $0 | $1,010,000 | $43,580,000 | yes | **no, short by $480,000** |
| Zenith Hardware | $43,750,000 | $0 | $1,250,000 | $42,380,000 | yes | **no, short by $720,000** |
| Helix Digital | $46,750,000 | $0 | $650,000 | $46,100,000 | yes | yes |
| Lumen Devices | $44,530,000 | $0 | $1,070,000 | $43,460,000 | yes | **no, short by $420,000** |


**Reading the rounds.** Rounds 1 and 2 are ordinary: every team locks, the
numbers agree, the only exception is the statement that will not add up. From
round 3 the game changes shape. Three teams open round 3 exactly $2,000,000
below the cash their round-2 statement closed at (W-CE3-01). Aurora Devices
and Nova Circuit are deadline-closed with drafts the lock refused and close
the round at −$6,468,269 and −$7,431,324. From round 4 **no team locks
again**: the affordability blocker compares committed spend — which includes
$4,000,000 of payroll and $6,000,000 of standing commitments no screen can
reduce — with cash that is now negative, and raising financing does not move
it (W-CE3-02). Rounds 4, 5 and 6 are therefore resolved by the operator with
every playing team pending, and the four teams end round 6 at −$49.1M,
−$43.7M, −$29.0M and −$26.4M.

**The cross-checks that did pass, every round:** the leaderboard is ordered
by performance index with ranks 1..8 (rounds 1–5; round 6 is the R32
inactivity case, W-CE3-15); the index on a team's Round Results equals the
leaderboard's; the statement's revenue equals the results' revenue; every
statement carries its research and compliance rows (R47); and gross profit
equals revenue minus COGS.

### Console and network, the whole walkthrough

`harness/records_summary.py` over every record: **67 recorded runs**,
**1,252 screens**, **8,547 API calls**, **734 driver checks passed**, 53
failed and 121 observed. The 53 failures are the defects in (d) and the
correct refusals in (b) — 24 lock refusals the server was right to give and
the page had already shown, the statement-arithmetic checks that fail by
design once W-CE3-03/04 are open, the cash-carry checks that fail once
W-CE3-01 is open, the five language checks that fail on the residues, and the
Gen 3 generation that is not offered.

* **No 5xx of any kind**, on any route, in any round — against walkthrough 2's
  one 500 that stopped a round dead.
* **No JavaScript exception and no `pageerror` on any screen in either
  language.**
* Console errors, excluding the harness's own aborted Google-Fonts requests:
  **79**, every one the browser's line for a non-2xx response — 67 × 400,
  10 × 409, 2 × 404 (one the harness's own probe of `/api/grades/`, a route
  that does not exist, and one a harness path since corrected).
* Every 4xx is accounted for: analyst refusals (deliberate, shown, nothing
  charged), `409 lifecycle_in_progress` (deliberate, shown, retried), the
  plant-collision refusals this pass drove on purpose, cash refusals for
  research purchases and organisation switches (each shown with its figures),
  the lock refusals, and the two end-game refusals.
* **Leak scans:** no raw catalogue key, no `undefined`, no `NaN`, no
  `[object Object]` and no exception text on any screen in either language.
  The English word *None* still appears in authored copy (*IP Exposure: None*),
  as in both earlier passes.

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
| **W-CE3-14** | R&D Investment › Create New R&D Platform | student | EN, zh | The scenario's third platform generation carries `unlock_round: 5`, but at round 5 it is **not listed at all and no reason is given**: `views/decisions.py:1910-1917` `continue`s past Gen 3 unless the team already holds an **active Gen 2 platform**, so the generation simply is not there. Every other gate on the platform now names itself — the M&A card says *第 3 回合起可用*, the platform round check says *available from round N* — and this one does not | the generation listed with its requirement stated, like every other locked offer | P2 | round 5, a team with no Gen 2 platform, R&D → Create New R&D Platform | `v-r5-t4-rd-en.jpg`, `records/verify-round5-unlocks-t4-r5-en.json` |
| **W-CE3-15** | Leaderboard | student, instructor | EN, zh | **The top score is shown in fourth place with nothing to explain it.** Round 6: *1 Nova Circuit 54.59 · 2 Aurora Devices 52.86 · 3 Solaris Consumer 52.83 · **4 Meridian Tech 60.34***. The ordering is R32 working as ruled — a commercially inactive firm ranks below every active one, and Meridian Tech had $0 of revenue — and the team's own **Round Results** screen explains it fully and in Chinese (*…未参与竞争的公司无论得分高低，都会排在所有参与竞争的公司之后…绩效指数本身并未被扣减，受影响的只是排名。*). But the leaderboard payload has no field for it (`rank, team_name, team_id, performance_index, index_change, total_revenue, net_income, shareholder_return, market_share, share_price, investor_confidence`) and `pages/LeaderboardPage.js` contains no mention of inactivity or demotion. The leaderboard is the screen a competition is read from, and on it the standings contradict the numbers beside them | a marker on the row, or the rule named under the table | **P1** | let a team be resolved with no sales while others sell, then open the Leaderboard | `records/check-round6.json` (`leaderboard_entries`), `s-after-r6-10-leaderboard-en.jpg`, `backend/core/engine/leaderboard.py:215-244` |
| **W-CE3-16** | Decision Summary | student | EN, zh | **A dividend of $0.00 is reported as exceeding projected equity**: *Total dividends of $0.00 exceed projected equity. Reduce the dividend.* — and in Chinese, *股利总额 $0.00 超过预计股东权益。请降低每股股利。* It fires for every team whose projected equity is negative, and it is un-clearable, because there is nothing below zero to reduce it to. It sits in the same blocker list as the cash blocker of W-CE3-02 | no dividend blocker when the dividend is zero | P1 | a team with negative projected equity, dividend set to 0, open Review & Submit | `records/probe-irreducible-commitment-t4-r5-en.json` (`zero_dividend_blocker`), `v-negcash-t2-r4-stripped-en.jpg` |
| **W-CE3-17** | Stakeholder Communications › the evaluation | student | EN, zh | The evaluation's criterion names are the **storage keys**, prettified: `framework_grounding` → *Framework Grounding*, and likewise *Risk Acknowledgment*, *Stakeholder Awareness*, *Strategic Consistency*, *Clarity And Persuasion*. `pages/CommunicationsPage.js:179` does `key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())`, and `:149` prints a hard-coded English *(weight: N%)* beside it. So a Chinese student reads five English storage keys on a screen whose feedback prose is otherwise correctly Chinese (*自动评估不可用。得分基于提交内容的完整性。*) | the criterion's authored name from the catalogue, in the reader's language | P2 | zh-CN team → Stakeholder Communications → submit a memo → read the evaluation | `p3-r2-72-communications-submitted-zh-CN.jpg` |
| **W-CE3-18** | Instructor › Operator Log | instructor | EN, zh | The refusal code is **run onto the end of the sentence with no separator**: *Refused: This action overrides an integrity check, so it requires a written reason of at least 10 characters.**reason_required*** and *Refused: The game has moved to round 5; this request was for round 4.**state_moved***. W-CE2-04 moved the raw exception out of this row; the code beside it is what is left of walkthrough 2's *`engine_failure`* | the code in its own column, or not on the row at all | P2 | cause any refusal, open the Operator Log | `v-oplog-refusals-en-en.jpg`, `records/verify-operator-log-refusal-en.json` (`refused_rows`) |
| **W-CE3-19** | Grading & Export › Export Team Summary CSV | instructor | EN | The end-of-game team export says **`Status: No decisions saved`** for every team, including the four that played all six rounds. The column reads the **currently open** round — round 7, which had just been opened by the advance after round 6 — so in an export taken at the end of a game it states the opposite of what happened. The same file's `Cash` column is right (−$49,051,474 for Aurora Devices) | the status of the game that was played, or a column heading that says which round it describes | P2 | play a game, advance past the last played round, Grading & Export → Export Team Summary CSV | `exports/final-game_1_teams.csv` |
| **W-CE3-20** | Grading & Export › Export Team Grades CSV | instructor | EN | The grades export carries **88.0** for Aurora Devices, a score overridden from the console before a single round was played, beside a real performance index of 52.86 — and the CSV has **no column saying it is an override**, though the console's own Team Grades table tags the row *Overridden*. An instructor grading from the file cannot see that the number was set by hand | an override marked in the export, as it is on the screen | P2 | override a category score, play the game, export the grades | `exports/final-team_grades.csv`, `i29c-grading-after-override-en.jpg` |


---

## (e) What could not be driven, and why

| item | why |
|---|---|
| **A lock in rounds 4, 5 and 6 — for any team** | W-CE3-02. The affordability blocker counts $4,000,000 of payroll and about $6,000,000 of standing commitments that no screen can reduce, and compares them with cash that the deadline has already driven negative. Stripping every reachable decision to zero did not clear it and raising $25,000,000 of debt did not move the figure. Those rounds were resolved by the operator, which is on record; "every team locks every round" was achieved for rounds 1 and 2 only. |
| **The Gen 3 platform, the scenario's round-5 unlock** | `views/decisions.py:1910-1917` hides the third generation until the team holds an **active Gen 2** platform, and Gen 2 costs $15,000,000 against an R&D budget of $1.5–4.2M (W-CE-19, deferred calibration under R48). No team could reach it, and the screen gives no reason for its absence — recorded as W-CE3-14. The **customs classification**, the other round-5 unlock, was driven and stored. |
| **The *Finish game* control** | `components/RoundControlCard.js:277-293` renders *Finish game* in place of *Advance* only when `current_round >= total_rounds`. This scenario authors **10** rounds and the brief asked for six, so the button never appeared. What the end of a game does was driven through the flows that are reachable — final grading, the three exports, and the delete / reset / archive refusals. |
| **Marking a competition heat from the console** | unchanged from both earlier passes: nothing in the frontend writes `SimulationInstance.settings['is_competition']`. `harness/mark_competition.py` does it (disclosed), so that the delete and reset refusals for a heat can be driven at all. |
| **Phase 2 narratives and the memo evaluation from a model** | by design of this stack: every LLM URL points at an unreachable port, so the round narrative and the memo evaluation use the template/heuristic fallback. That fallback is what is on record, and it is correctly localised (*模型评估不可用——未生成详细反馈*). |
| **An answer from Ask the Analyst** | the scenario has no analyst, so only the refusal path exists. It was driven 24 times across the game, with the quota untouched and nothing charged — and, this time, **in the asking student's own language from round 1** (W-CE2-05). |
| **The engine's plant-merge path (`engine/plants.record_plant`)** | it exists for a game that already carries the walkthrough-2 collision. The decision boundary now refuses both collisions before they can be stored, so a game started on this tree cannot reach the merge. The boundary was driven instead, in both orders and both languages. |
| **Chinese glyphs** | no CJK font in the sandbox and no route to a font CDN; every zh-CN claim in this report is about the rendered DOM text, not the pixels. |
| **8 teams actively deciding** | four teams (1, 2, 4 EN; 3 zh-CN) played every round, which is the brief's minimum; teams 5–8 made no decision in any round and were deadline-closed every time. |
| **Rounds 7–10** | six rounds were played end to end (the brief's minimum); the remaining four were not. |
| **The supply-chain pages other than Logistics** | Sourcing, Trade Finance and Inventory were opened and photographed in both languages every round and read for leaks, but only Logistics was edited (the round-5 customs classification). They are optional to the lock (W-CE-13). |

### Disclosed interventions by the auditor

Everything below is an auditor's action on a disposable database, named here
so that nothing in the record is taken for the platform's own behaviour.

1. `harness/mark_competition.py` marks the game a competition heat, because
   the console cannot (as in both earlier passes).
2. `verify_deadline_affordability.py` raised one of Nova Circuit's promotion
   budgets to $19,287,190 in round 3 to push the round past the team's cash.
   That is a figure a student can type on the Marketing page, and the point
   was to reach the state W-CE2-03 describes; the resulting −$7.4M close is
   the platform's, not the harness's.
3. `probe_negative_cash_lock.py` and `probe_irreducible_commitment.py` zero a
   team's budgets and then raise debt on a **draft**, to ask what the platform
   will allow. The budgets were restored to what the team had decided before
   round 5 was resolved.
4. `verify_operator_log_refusal.py` signs the instructor in and states
   **English**, which is why round 5's AI Coach alerts are English while
   rounds 3, 4 and 6 are Chinese. The preference was set back to Chinese
   before round 6 and the result is on record (30 of 30 Chinese).
5. `verify_plant_after_acquisition.py` queued Aurora Devices' round-3 plant
   through the decision route the page saves with, because the Market Strategy
   page does not offer Build Plant in a market that already holds a plant.

### Harness limits, not defects

* `student_play.py`'s M&A step reported *unaffordable notice on the card=False*
  because it searched for the raw catalogue template (`需要 {{cost}}；…`)
  rather than its stem. `probe_ma_card.py` checks the stem and finds the
  sentence; the notice is there.
* The `decision_plant.capacity_units` assertion (see (a) §4) was mis-specified
  in walkthrough 2 and is re-specified here.
* `verify_operator_log_refusal.py`'s first version scanned the **structured**
  before/after payload of an audit row, which legitimately carries storage
  keys. Scoped to the prose fields, it passes.

---

## (f) Verdict, in plain language

### Can a full 6+ round game be played start to finish with no intervention?

**No. An instructor can get to the end of round 6, but from round 4 onward
the game only moves because the instructor makes it move.**

The good news first, and it is real. Every one of walkthrough 2's ten new
defects is either fixed or fixed with a named residue, and the P0 that
stopped a round dead is gone: a team built a plant in the same market as an
acquisition it completed, the round processed, and the two ways of creating
that collision are now refused at the save with a sentence that names the
market — in English and in Chinese. **Six rounds processed. Not one 5xx on
any route. Not one JavaScript exception on any screen in either language.**
The instructor built the whole game from the console and never had to refresh
a page to make a control work. The lifecycle *Advance Round* button, refused
in both earlier passes, advanced a round with four teams pending. A queued
acquisition, plant or partnership can now be taken back, and one the team
cannot fund is offered disabled with the figures beside it. A Chinese-speaking
student was answered in Chinese from round 1.

**But no team locked a round after round 3.** The Decision Summary refuses the
lock because committed spend exceeds cash — and committed spend includes
$4,000,000 of payroll and about $6,000,000 of commitments made in earlier
rounds that no screen can withdraw. Setting every budget, every promotion
budget, the dividend, the plant, the partnership, the acquisition and the ESG
investment to zero still leaves $10,250,000 committed. Raising $25,000,000 of
new debt — which is what the blocker's own sentence asks for — does not change
the figure by a cent. Solaris Consumer hit that wall with **positive** cash of
$1,269,790.55, so this is not only a negative-cash problem. From round 4 the
instructor resolved every round with every playing team pending, and the teams
were deadline-locked with drafts they had been told they could not submit.

In a competition heat, that is four teams who stop being able to press the
button, in front of the room, with nothing they can do about it.

### Is anything a player sees wrong?

**Yes — three things, and one of them is money.**

1. **Money leaves a team between rounds and appears on no screen.** Aurora
   Devices' round-2 statement closes at $13,523,631.84 and its round-3
   statement opens at $11,523,631.84. It happens to every team that switches
   its tax structure, every round it switches, and the amount is always
   exactly the structure's setup cost. The statement's own cash-flow identity
   still closes perfectly, because the charge is taken before the opening
   figure is read — so nothing on the page is inconsistent, the money is
   simply gone. Solaris Consumer was carried from +$1,269,790.55 to
   −$730,209.45 by it. The same class of defect was found and fixed for the
   **organisation structure's** transition cost under R36 / V2-088, and the
   code that did it says so in a comment; the tax structure's setup cost was
   not moved with it.

2. **The income statement does not add up.** Revenue minus COGS minus the six
   expense lines the page prints does not reach the Net Income printed beside
   them — every team, every round, by $0.36M to $3.03M. Part of that is
   interest, tax, logistics/tariff and inventory, which the server sends and
   the page does not draw. The rest — up to $2.4M for a team that built a
   plant — is depreciation and the tax structure's maintenance cost, which are
   inside operating income and are not a field of anything.

3. **The leaderboard shows the top score in fourth place with no reason
   given.** Round 6 ranks Meridian Tech fourth on 60.34, below three firms on
   54.59, 52.86 and 52.83. That is R32 working — a firm with no sales ranks
   below every firm that sold — and the team's own Round Results page explains
   it at length and in Chinese. The Leaderboard, which is the screen everybody
   in the room looks at, says nothing at all.

Beyond those, the language work has held up well. The market names, the price
notices, the analyst refusal, the coach alerts and two of the three scorecard
sentences are all in the reader's language now. What is still English on a
Chinese screen is a list of small, findable places: one scorecard sentence,
the market names inside the scorecard's own tables, the Logistics and Trade
Finance market names, the platform's *Base Platform* suffix, the
`Trade Finance & FX` tab label, the memo evaluation's five criterion keys, the
financial-distress coach alert, and the whole Strategic Briefing — which is
ninety English f-strings and no catalogue at all.

### What I would fix before the first clean game

1. **W-CE3-02** — a team must be able to submit a round. Whatever the ruling
   on the affordability rule, the present behaviour ends a team's game.
2. **W-CE3-01** — the tax structure's setup cost must be booked where the
   org structure's transition cost already is, so that closing cash equals
   opening cash.
3. **W-CE3-03 and W-CE3-04** together — the income statement must add up on
   the page a student reads it on.
4. **W-CE3-15** — the leaderboard must say why a firm is below a lower score.
5. **W-CE3-16** — a dividend of $0.00 cannot be a blocker.
6. **W-CE3-05** — a decision screen must name the product being decided.

Everything else on the list is wording. **What is now true, and was asked for
by the first walkthrough's verdict and again by the second, is that the
platform's numbers agree with each other and its rounds always process**: six
rounds of results, statements and leaderboards cross-checked on every line, in
both languages, with the identity the platform publishes closing to the cent
on all eight teams every round. What is still not true is that a game can be
relied on to be *played* to the end — it can only be *driven* to the end.
