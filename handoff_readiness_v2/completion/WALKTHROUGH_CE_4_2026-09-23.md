# Fourth full walkthrough — Consumer Electronics 2026, the longest game yet

**Branch:** `walkthrough-ce-4-2026-09-23`, cut from `crv2-release-integration`
at `c118a7c`. The base was checked before anything ran: **`2576a65`** — the
merge of both walkthrough-3 repair branches (`walk-ce3-lock-and-money` and
`walk-ce3-display-and-language`) — is an ancestor of HEAD.
**Date:** 2026-09-23. **Auditor role:** find defects; repair nothing.
`backend/`, `frontend/` and `specs/` have **zero diff** on this branch. The
only edits are to the harness under
`handoff_readiness_v2/evidence/walkthrough-ce-4-2026-09-23/harness/`, every
one of them listed in (a).
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-4-2026-09-23/`
— `harness/` (every driver), `records/` (one JSON per driver run: steps,
screens, API calls, refusals, console, leak scans), `exports/`, `runtime/`
(stack logs, git-ignored).

**There are no screenshots.** They reached 161 MB against a ~25 MB budget and
were removed entirely at the owner's instruction, and the branch was rewritten
from its base so the images are not in its history either. Nothing is lost
that this report relies on: **every row in (b) and (d) cites the quoted DOM
text, the API request and response, or the log line**, which is better
evidence than a picture and is what the records carry. All 2,158 screens are
still named in `records/`, each with its URL, its leak scan and the API calls
it made; `walk.Recorder.screen` simply no longer writes the image
(`WALK_SCREENSHOTS=1` restores it).

> Sections: (a) the stack, the commands and the harness fixes ·
> (b) verification of every W-CE3 id and the W-CE2 residues ·
> (c) the game, round by round, with the money reconciliation ·
> (d) new defects · (e) what could not be driven · (f) the verdict.

---

## (a) The stack, the commands, and how the languages were set

Disposable, on this host, and this pass's own. **Never** the production
database at 192.168.50.38, never `/etc/globalstrat-plus.env`. Backups go to a
scratch directory **inside the evidence tree**; every LLM endpoint points at
an unreachable port, so Phase 2 narratives and the memo evaluation use the
template/heuristic fallback; `COMPETITION_REQUIRE_CLEAN_BUILD=false`. The
container, the database and both ports are this pass's own
(`globalstrat-walkthrough-ce4-pg`, database `globalstrat_walk4`, ephemeral
host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build       # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-4-2026-09-23/harness
bash $H/make_db.sh           # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py           # migrate + legacy tables, load_scenario --preset electronics,
                             # a superuser and ONE instructor -- nothing else
python3 $H/start_stack.py    # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin
```

`seed.py` creates **nothing else**: the course, the section, the game, the
teams, the roster, every password and the schedule were all made from the
console by the instructor driver.

**The database readiness wait, as the brief asks.** The host disk is known to
stall, and this pass found out why walkthrough 3's wait was not enough:
`postgres:16-alpine` runs a temporary server on the unix socket while it
initialises the cluster, answers `pg_isready` there, then **shuts it down and
restarts for real**. Walkthrough 3's loop accepted that first answer; on this
run `seed.py` died with *server closed the connection unexpectedly*. The loop
now demands a real `select 1` over TCP, twice in a row, for up to 300 s, and
`start_stack.py` keeps its 900 s readiness wait. After the change `make_db.sh`
returned in 21 s, `seed.py` in 17.9 s and `start_stack.py` in 2.7 s.

### How the languages were set — the harness defect the brief names

Walkthrough 3 reported its own finding (d)4: the harness set a student's
language in `localStorage` and never on the server, so the Chinese team's
enrolment stayed `en` for six rounds and every stored Phase 2 artefact for
that team came out English. Two things were done about it here, **before
round 1 was resolved**:

1. **`set_language.py` is new** and sets a language **through the product**.
   It signs the person in with the interface in English, presses the in-game
   switch — the student top bar, the console header;
   `components/LanguageSwitcher.js`, which calls `PUT /api/user/preferences/`
   whenever there is a token — and then reads the result back three ways:
   `GET /api/user/preferences/` from inside the signed-in browser, the stored
   row straight out of the database, and the switch's own label, which flips
   to `EN` once the interface is Chinese. Nothing is asserted from
   `localStorage`.

   *All three members of team 3 (Cobalt Innovations), including the first
   enrolment, which is what the team rule (R43, decision 17) reads:*

   ```
   python3 set_language.py student 3 zh-CN
     PASS  the in-game switch set s2609 to zh-CN on the SERVER
           before=en after=zh-CN clicks=[{"label": "中文", "server_after": "zh-CN"}]
     PASS  the stored language row for s2609 holds zh-CN   (enrollment.language='zh-CN')
     … the same for s2610 and s2611 …
   ```

   *The instructor, who has no enrolment, so the W-CE2-08 repair writes the
   `user_language_preference` row instead:*

   ```
   python3 set_language.py instructor zh-CN
     PASS  the in-game switch set walk_instructor to zh-CN on the SERVER
     PASS  the stored language row for walk_instructor holds zh-CN
   ```

   The driver's first version looked only at the enrolment table and reported
   the instructor as having no language at all; it now reads both stores, and
   says which one answered.

2. **Every sign-in in every driver now reads the server back.**
   `walk.sign_in` asserts `GET /api/user/preferences/` against the language
   the driver asked for and records the answer, so no run can quietly
   conclude something about a Chinese team from a browser that never told the
   server anything. A mismatch is a failure for a student (whose sign-in does
   restate the language, because the login response carries the enrolment's)
   and an observation for the instructor (whose does not).

**A second harness defect, found the same way and worth naming.**
`walk.api` — the helper every driver uses to read the product's API from
inside the signed-in page — sent only `Authorization`, while the product's own
`api/client.js` also sends `Accept-Language` from `localStorage.gs_language`.
Some routes choose their language from that header. Reading the AI Coach with
the header missing returned 27 of 31 alerts in English while the panel beside
it was showing them in Chinese, and a walkthrough that trusted the driver
would have raised a defect that does not exist. The helper now sends the
header exactly as the client does.

### Drivers

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. the refused 6th member → team configuration with team 1's home market set by hand to Africa and team 1 renamed → activate → schedule and deadline with no page refresh → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, override, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| **`set_language.py`** | **new** — sets a language through the in-game switch and proves it from the server and the database | `set_language.py student <team> <lang> [member]` / `set_language.py instructor <lang>` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after, operator-log wording and drill-down order checked; **now records which teams locked themselves before the close** | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round); **now gives back on the server the language its W-CE-11 check borrows** | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| **`follow_the_blocker.py`** | **new** — reads the Decision Summary's refusal, does what it says on the Finance page, reads it again, presses the lock button | `follow_the_blocker.py <lang> <team> <round>` |
| **`drive_overproduction.py`** | **new** — types a production volume into the Marketing page's own box, to take a team's cash negative the ordinary way (stock built and not sold) or to stop its sales dead | `drive_overproduction.py <lang> <team> <round> <units>` |
| **`probe_de_ceiling.py`** | **new** — every financing adjustment the product offers, against the debt-to-equity blocker | `probe_de_ceiling.py <lang> <team> <round>` |
| **`verify_ce3.py`** | **new** — one signed-in browser, one check per W-CE3 display/language id | `verify_ce3.py <lang> <team> <round>` |
| **`verify_briefing.py`** | **new** — the Strategic Briefing modal, per member, with a raw-Markdown check | `verify_briefing.py <lang> <team> <member>` |
| **`verify_fresh_browser_language.py`** | **new** — what a Chinese-speaking player gets on a browser that has never been used | `verify_fresh_browser_language.py <user> [password] [lang]` |
| **`verify_tax_charge.py`** | **new** — W-CE3-01 from both sides: cash carried between statements, and the setup cost inside a printed line | `verify_tax_charge.py <round>` |
| **`finish_game.py`** | **new** — the last round and the *Finish game* control | `finish_game.py <lang> <round>` |
| `lock_round.py` | completes the product-market rows a new product or market leaves empty, **now also sets a budget allocation when the Summary asks for one**, then locks from the Summary | `lock_round.py <lang> <team> <round>` |
| `check_round.py` | results/statement/leaderboard cross-check **and the money reconciliation**, all 8 teams; **the page's income-statement line list is now read from the page's own source** | `check_round.py <round>` |
| `verify_coach_language.py` | **now takes the language to read in**, because an alert renders for its reader instead of being frozen at processing time | `verify_coach_language.py read <round> <lang>` |
| `verify_round5_unlocks.py`, `verify_withdraw.py`, `probe_ma_card.py`, `verify_plant_collision.py`, `verify_plant_after_acquisition.py`, `verify_deadline_affordability.py`, `verify_results_language.py`, `probe_scorecard.py`, `verify_operator_log_refusal.py`, `probe_negative_cash_lock.py`, `probe_irreducible_commitment.py`, `lock_within_cash.py`, `instructor_endgame.py`, `dbq.py`, `apicall.py`, `hold_lock.py`, `mark_competition.py`, `leak_summary.py`, `records_summary.py`, `shrink_screenshots.py`, `prune_screenshots.py` | as in walkthrough 3 | — |
| `run_round.sh`, `run_game.sh`, `run_last.sh`, `hooks/r<N>.sh` | **new** — one round end to end, the game, the last round, and a named hook per round for the auditor's own deliberate acts | `./run_round.sh <round> <way> <console-lang> [profile]` |

### Every harness change, listed

1. `make_db.sh` — its own container (`globalstrat-walkthrough-ce4-pg`) and
   database (`globalstrat_walk4`), and a readiness loop that demands a real
   query over TCP twice before calling the database ready.
2. `walk.py` — `sign_in` reads the server's language back and records it;
   `server_language`, `language_switch` and `switch_language_in_product` are
   new; `api` sends `Accept-Language` exactly as `api/client.js` does.
3. `set_language.py`, `follow_the_blocker.py`, `drive_overproduction.py`,
   `probe_de_ceiling.py`, `verify_ce3.py`, `verify_briefing.py`,
   `verify_fresh_browser_language.py`, `verify_tax_charge.py`,
   `finish_game.py`, `round_table.py`, `run_round.sh`, `run_game.sh`,
   `run_last.sh`, `finish_round4_then_go.sh`, `hooks/` — new.
4. `check_round.py` — the page's income-statement line list is read out of
   `frontend/.../pages/incomeStatementRows.js` instead of being copied into
   the driver, so the arithmetic check cannot pass merely because the harness
   was edited to match a repair; `other_operating_expense` and
   `other_non_operating_expense` join the charge lines.
5. `lock_round.py` — sets a budget allocation when the Summary refuses for the
   want of one, which is what the refusal tells a student to do.
6. `instructor_round.py` — records the per-team decision status **before** the
   close, because *Close round now* locks every outstanding submission and
   afterwards every team reads `locked` whether it submitted or was submitted.
7. `student_tour.py` — its W-CE-11 check presses the language switch, which
   now writes to the server; it puts the language back on the server and
   reads it back, not just in `localStorage`.
8. `verify_coach_language.py` — takes the language to read in.
9. `leak_summary.py` — the five English market names are no longer excused on
   a Chinese screen.
10. `prune_screenshots.py` — widened from rounds 3–6 to rounds 3–10.
11. `verify_tax_charge.py`'s first version named a `tax_structure` table that
    does not exist (it is `tax_structure_type`), and `verify_ce3.py`'s first
    version grouped the marketing context on a `market_id` its rows do not
    carry and read the whole page with one market tab open. Both are
    corrected; both would have reported a defect that is not there.

**The money reconciliation** is recorded per team per round in
`records/check-round<N>.json` under `reconciliation`, in the same two forms
walkthrough 3 used: the identity the platform publishes (`cash_opening +
operating + investing + financing == cash_closing`), and the plain form the
brief asks for (`opening cash + revenue − charges = closing cash`), plus the
sum a player can do with a finger on the Financial Reports screen, using only
the lines that page prints.

**Leak scan** on every screen (`walk.scan`), the CRV2-13 standard. Console
errors and every API status ≥ 400 are captured per screen; the harness's own
aborted Google-Fonts requests are excluded from the counts. **No visual claim
is made about Chinese glyphs**: this sandbox has no CJK font, so the standard
is the rendered DOM text, recorded per screen — which is also why removing the
images costs this report nothing.

**Across the whole run:** 90 recorded driver runs, **2,158 screens**, **17,028
API calls**, 1,504 driver checks passed, 141 failed and 355 observed. The 141
failures are the defects in (d), the correct refusals in (b), and the
processing refusals in (c). **No JavaScript exception and no `pageerror` on
any screen in either language.** `POST …/round-control/process/` answered
**400 seven times and 500 six times**; every other non-2xx is accounted for in
(b) and (d).

---


## (b) Verification of every walkthrough-3 defect, and the walkthrough-2 residues

Every id was reproduced through the step walkthrough 3 recorded, on this
stack, in the language(s) it was found in. **Evidence is the quoted DOM text,
the API request and response, or the log line** — one JSON record per driver
run under `records/`, named in each row. No screenshots are kept (see §(a)).

### The W-CE3 list

| id | sev (W3) | the step, repeated | state | what is there now | evidence |
|---|---|---|---|---|---|
| **W-CE3-01** | **P0** | switch the tax structure, resolve the round, compare the previous round's `cash_closing` with this round's `cash_opening` | **VERIFIED FIXED** | Nothing leaves a team between statements, anywhere in the game: over **80 team-rounds** (ten rounds × eight teams) the worst difference between one round's closing cash and the next round's opening cash is **$0.00**. For the four teams that switched to the Regional Hub Structure in round 1 the $2,000,000 setup cost is inside the **strategy expense line the statement prints** (`strategy_expense` $11,550,000 against an authored `setup_cost` of $2,000,000, read from `tax_structure_type` in the database so the expected figure does not come from the code that books it) | `records/verify-tax-charge-r1.json`, `records/check-round{1..10}.json` (`reconciliation.*.cash_carried_between_rounds`) |
| **W-CE3-02** | **P0** | let a team's cash go negative; try to lock the next round | **VERIFIED FIXED** | This is the one the brief calls the whole point, and it holds. Photon Labs opened round 4 at **−$2,120,650.70** and Aurora Devices at −$168,269.34; both **locked round 4 themselves**, from the pages, by doing what the Decision Summary told them to do. The refusal now names the amount to cut, the largest reducible commitment, and what to raise: *Committed spend of $16,500,000.00 exceeds available funds of $-168,269.34 — $-168,269.34 of cash plus $0.00 of financing decided this round. Cut $16,668,269.34: your largest reducible commitment is the strategy budget at $7,250,000.00. Raising more debt or equity has the same effect.* and *New debt of $5,000,000.00 is not counted: lenders will not extend credit while the company is in financial distress. Raise equity instead.* All four playing teams locked round 4, and **the four playing teams locked themselves in nine of the ten rounds**. What it costs to get there is W-CE4-02..05 | `records/follow-blocker-t{1,2,3,4}-r4-*.json`, `records/instructor-round*-*.json` (`locked_themselves`) |
| **W-CE3-03** | P1 | open Financial Reports › Income Statement and add the columns up | **VERIFIED FIXED** | The page prints twenty lines and the printed lines sum to the printed net income within the precision of the print itself. Read off a Chinese screen at round 1: 营业收入 $378K · 销售成本 $540K · 毛利润 $-162K · 研发 $0 · 营销 $300K · 战略 $11.6M · 市场调研 $50K · 合规投入 $0 · 行政管理 $511K · 物流与关税 $505K · 库存持有成本 $0 · 平台摊销 $0 · 平台切换减值 $0 · **其他营业费用 $1.8M** · 营业利润 $-14.9M · 利息费用 $120K · 所得税 $0 · 其他费用 $0 · 净利润 $-15.0M · 利润率 -3967.7%. Gross profit less the fourteen printed charges is −$15,048,000 against a printed net income of −$15,000,000: a gap of $48,000 against a rounding allowance of $153,004, which is half of the last printed digit of every cell added up. Exactly, on the served figures, the gap is **$0.00 on all 80 team-rounds** | `records/verify-ce3-t*-r*.json` (`income_statement_by_key`, `printed_statement_gap`), `records/check-round*.json` (`page_income_statement_gap`) |
| **W-CE3-04** | P1 | subtract the expense fields from gross profit on the served row | **VERIFIED FIXED to the extent the repair claimed** | `page_gap_not_in_any_served_field` is **$0.00 on all 80 team-rounds**: every charge inside operating income now reaches a served field, with the residue published as `other_operating_expense` and `other_non_operating_expense`. The repair's own disclosure still stands — depreciation, the tax structure's maintenance cost, product retirement, supply-chain disruption and compliance enforcement are inside *Other operating charges* rather than named, because naming them needs five columns on a hashed section. A team that built a plant still cannot find the word "depreciation" | `records/check-round*.json` (`page_gap_not_in_any_served_field`) |
| **W-CE3-05** | P1 | any team with one product in a market, Marketing Mix | **VERIFIED FIXED** | Each market tab was opened in turn and the product name looked for in the active pane: `[{"market": "Africa", "product": "Nexus One", "named_on_the_card": true}, {"market": "North America", "product": "Nova Aurora R4", "named_on_the_card": true}]` | `records/verify-ce3-t1-r4-en.json` (`single_product_markets`) |
| **W-CE3-06** | P2 | zh-CN team → Round Results → Strategic Scorecard | **VERIFIED FIXED** | `coherence.breakdown.governance_tax.feedback` = *未发现治理与税务之间的冲突。*, beside *支出未超出经营预算。财务纪律良好。* and *杠杆水平保守。财务状况稳健。* An English reader gets *No governance-tax conflict detected.* on the same round | `records/verify-ce3-t3-r{1,2,10}-zh-CN.json`, `records/verify-ce3-t1-r*-en.json` (`scorecard_criteria`) |
| **W-CE3-07** | P2 | the scorecard's own detail tables, zh-CN | **VERIFIED FIXED** | A walk of the whole results payload for English market names returns **0** — the detail tables read `"market": "南美"`, `"market": "北美"` | `records/verify-ce3-t3-r*-zh-CN.json` (`english_market_names_in_results`) |
| **W-CE3-08** | P2 | zh-CN console, AI Coach, after a round in which a team went into distress | **VERIFIED FIXED** | The distress alert is Chinese — *Aurora Devices 已进入财务困境*, round 3 — and reading the whole game's alerts as a Chinese-reading instructor gives **100 of 100 in Chinese, 0 in the other language**. Walkthrough 3's named condition (i) on W-CE2-08 is closed too: round 1's alerts, written before any switch, read in Chinese, because an alert now renders for its reader | `records/probe-alert-language.json`, `records/verify-coach-language-read-r1-zh-CN.json` |
| **W-CE3-09** | P2 | zh-CN team, Supply Chain › Logistics and Trade Finance | **VERIFIED FIXED** | A scan of the four supply-chain screens for *North America, East Asia, Western Europe, Africa, South America* returns nothing on any of them, at rounds 1, 2 and 10 | `records/verify-ce3-t3-r{1,2,10}-zh-CN.json` (`logistics_text`, `trade-finance_text`, …) |
| **W-CE3-10** | P2 | zh-CN team → Products, R&D, Create Product modal, dashboard | **VERIFIED FIXED** | Every served platform name is *Cobalt Innovations基础平台* — `products[].platform_name`, `active_platforms[].name`, `rd.owned_platforms[].platform_name` and the scorecard read. No English suffix anywhere | `records/verify-ce3-t3-r*-zh-CN.json` (`platform_names`) |
| **W-CE3-11** | P2 | zh-CN student signs in after a processed round | **VERIFIED FIXED** | The Strategic Briefing is Chinese: *第2回合战略简报 您的团队绩效摘要和战略展望 … 收入增长 20.2%，达到 $454,406。净利润：$-13,179,296。现金状况：$19,482,944。继续到仪表板 完整简报可在「战略简报」标签中查看* — 59 Chinese characters, **no English left on the screen**; 74 at round 10. An English team's briefing is fully English. What it prints raw is W-CE4-07 | `records/verify-briefing-t3-m2-zh-CN.json`, `records/verify-briefing-t1-m4-en.json` |
| **W-CE3-12** | P2 | zh-CN team → Financial Reports, the tab bar | **VERIFIED FIXED** | Every tab label carries Chinese; the scan for a label with Latin letters and no Han character returns `[]` at rounds 1, 2 and 10 | `records/verify-ce3-t3-r*-zh-CN.json` (`financial_report_tabs`) |
| **W-CE3-13** | P2 | commit past the cash, open Review & Submit | **VERIFIED FIXED** | The Budget Summary line reads *本回合已承诺支出：$11.8M，可用资金共 $12.4M；尚未承诺 $578K* — committed, available funds, and what is genuinely uncommitted, all positive. The over-commitment is stated by the blocker instead, as an amount to cut: *需要削减 $5,421,575.79*. A scan for an unformatted negative (`$-` followed by four or more digits with no magnitude suffix) returns nothing | `records/follow-blocker-t3-r4-zh-CN.json` (`summary_text`), `records/summary-wording-t*-r8-*.json` |
| **W-CE3-14** | P2 | round 5+, a team with no Gen 2 platform, R&D → Create New R&D Platform | **VERIFIED FIXED** | Three generations are offered — *Gen 1 — Standard Electronics, Gen 2 — Smart Connected Platform, **Gen 3 — AI-Native Sustainable Platform*** — and Gen 3 states its requirements rather than being absent: `[{"requirement": "Round 5 or later", "met": true, "detail": "Current round: 6"}, {"requirement": "Generation 2 must be active", "met": false, …}]` | `records/verify-round5-unlocks-t1-r6-en.json` |
| **W-CE3-15** | P1 | let a team be resolved with no sales while others sell, then open the Leaderboard | **VERIFIED FIXED** | Round 8 produced the exact shape: Nova Circuit, index **46.64**, ranked **sixth**, below Prism Tech on 33.08 and Eclipse Gadgets on 21.20. With that round chosen the page carries the marker on the row — **Did not compete** — and the rule under the table: *A company that sold nothing in a round did not compete in it, and is placed below every company that did, whatever its score. The performance index itself is not reduced; only the placing.* Both were found in the page's own visible text, not only in the payload. Finding it uncovered W-CE4-06 | `records/leaderboard-marker-t1-en.json` (`markers`, `rank_rule_note`, `page_text_on_round_8`) |
| **W-CE3-16** | P1 | a team with negative projected equity, dividend 0, Review & Submit | **VERIFIED FIXED** | Cobalt Innovations at round 4 with a dividend of $500,000 is correctly refused — *股利总额 $500,000.00 超过预计股东权益。请降低每股股利。* — and once the dividend is zeroed the blocker is gone; the remaining blockers list carries no dividend line | `records/follow-blocker-t3-r4-zh-CN.json` (`attempts[0].blockers` vs `after_equity.blockers`) |
| **W-CE3-17** | P2 | zh-CN team → Stakeholder Communications → the evaluation | **VERIFIED FIXED** | Neither the raw keys (`framework_grounding`, …) nor their prettified forms (*Framework Grounding*, …) appear on the Chinese screen | `records/verify-ce3-t3-r*-zh-CN.json` (`evaluation_criterion_labels`) |
| **W-CE3-18** | P2 | cause any refusal, open the Operator Log | **VERIFIED FIXED** | The code is on its own row, not run onto the sentence: *Refused: Round 10 has already been processed.* then *Refusal code round_already_processed*; *Refused: The game has moved to round 10; this request was for round 9.* then *Refusal code state_moved* | `records/verify-operator-log-refusal-en.json` (`refused_rows`) |
| **W-CE3-19** | P2 | play a game, Grading & Export → Export Team Summary CSV | **VERIFIED FIXED** | The column names the round it describes and reports what happened: `Team,Index,Cash,Revenue,Coherence,Status (round 10),Markets` → `Aurora Devices,54.35,-2130194.17,6174000,85.56,Locked,NA;APAC;EU;AFR;LATAM` | `exports/final-game_1_teams.csv` |
| **W-CE3-20** | P2 | override a category score, play the game, export the grades | **VERIFIED FIXED** | The export carries the override and the figure it replaced: `Team ID,Team Name,Performance Index,Overall,Overridden Categories` → `1,Aurora Devices,88.0,90.0,Performance Index (computed 54.4)`, and the row for a team with no override is blank in that column | `exports/final-team_grades.csv` |

### The walkthrough-2 residues

| id | the step, repeated | state | what is there now | evidence |
|---|---|---|---|---|
| **W-CE2-01** | a plant build in the market of a completed acquisition | **VERIFIED FIXED for the half that could be driven; the collision itself NOT DRIVABLE** | A plant build in the market of a completed acquisition is accepted and the round processes. The *collision* half could not be set up this game: by round 7 no acquisition target that brings a plant in the team's home market was still available — every target had been bought — so the boundary refusal could not be provoked again. It was driven in both orders and both languages in walkthrough 3 | `records/verify-plant-after-acquisition-t6-r7-en.json`, `records/verify-plant-collision-t6-r7-en.json` |
| **W-CE2-02** | queue a commitment, then take it back | **VERIFIED FIXED** | A queued plant and a queued partnership can both be withdrawn from the real pages: *a Withdraw control is offered* → *Withdraw removes the queued plant from the stored draft* → *the Build Plant offer is back*. The affordability block is published (`{"cash_on_hand": 46897995.8, "available_funds": 46897995.8, "committed_total": 0, "unallocated": 46897995.8}`), and an unaffordable acquisition is offered **disabled with the figures beside it in Chinese**: *收购 — $18.0M* disabled, *先收购的团队获得独家权限。需要 $18.0M；未分配资金 $-872K*, and every unavailable target says why (*已被Photon Labs收购*, *需要先进入非洲*). The acquisition-withdrawal third of the check was NOT DRIVABLE: no target was left to queue | `records/verify-withdraw-t6-r7-en.json`, `records/probe-ma-card-t3-r4-zh-CN.json` |
| **W-CE2-03** residue (decision 14) | let a team be closed with a draft the lock refused | **CHANGED — and it is now the cause of a round-stopper** | The close no longer executes an unaffordable draft as it stands: it reduces what the draft commits until it fits, and locks it (`deadline_lock`). But it leaves the team's equity raise sized against the commitments it has just removed, and the round then cannot be scored. That is W-CE4-02 | `records/round-wont-process-r5-en.json`, `runtime/preflight-r6.log`, `runtime/backend.log` |
| **W-CE2-04** | make an action fail or be refused; read the Operator Log | **VERIFIED FIXED** | No storage name, Python argument or raw exception in the Operator Log: the scan returns `[]` and the rows read as sentences. Note that the round-8 crash's raw Python text (`ActiveModifier() got unexpected keyword arguments…`) is in the HTTP body only; the Operator Log row says `process_round · rejected · Operator requested process_round`, which is the other half of W-CE4-01 | `records/verify-operator-log-refusal-en.json` |
| **W-CE2-05** | a zh-CN student asks the analyst | **VERIFIED FIXED** | From round 1 and in every round: *本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。* for the Chinese team, *The research analyst is not part of this game, so your question was not asked and nothing was charged.* for an English one | `records/student-play-t3-r*-zh-CN.json`, `records/student-play-t1-r*-en.json` (`analyst_refusal`) |
| **W-CE2-06** | market names on a zh-CN screen | **VERIFIED FIXED** | With the five English market names **no longer excused by the leak scan** (a harness change this pass made deliberately), they appear on no freshly loaded Chinese screen. They do appear once, on the screen captured immediately after the in-game switch is pressed, before the page refetches — which is the page not yet having new data, not a translation gap | `records/verify-ce3-t3-r*-zh-CN.json`, `harness/leak_summary.py` output |
| **W-CE2-07** | scorecard criteria in the reader's language | **VERIFIED FIXED** | See W-CE3-06; and a Chinese read does not mutate the stored row — `probe_scorecard.py` reads en → zh → en on three teams | `records/probe-scorecard-r10.json` |
| **W-CE2-08** | zh-CN console → AI Coach after a processed round | **VERIFIED FIXED, both walkthrough-3 conditions closed** | 100 of 100 alerts in Chinese for a Chinese-reading instructor, including rounds processed before any switch. Reading the same alerts in English exposes W-CE4-08 | `records/probe-alert-language.json` |
| **W-CE2-09 / W-CE-18b** | spend past the budget, open Review & Submit | **VERIFIED FIXED** | One total for what the round costs, no unformatted negative, and the overrun stated as an amount to cut. See W-CE3-13 | `records/summary-wording-t*-r8-*.json` |
| **W-CE2-10** | new game → Activate → Set deadline with no page refresh | **VERIFIED FIXED** | First attempt, no refresh: *CE 2026 Heat A: deadline updated.*, `deadline=2026-09-25T18:00:00+00:00`, console still on *Game Control*. The reload-and-repeat branch did not fire | `records/instructor-setup-en.json` |
| **W-CE-23** | spend past the budget, then try to lock the next round | **VERIFIED FIXED** | Same as W-CE3-02: the lock is reachable from negative cash | `records/follow-blocker-t*-r4-*.json` |
| **W-CE-24** | Game Lifecycle › Advance Round with teams pending | **VERIFIED FIXED** | Round 7 was resolved entirely through the lifecycle card's *Advance Round*, with the four absentee teams pending; the round processed and round 8 opened | `records/instructor-round7-lifecycle-zh-CN.json` |
| **W-CE-26** | Reset to Setup on a competition heat | **CHANGED** | The control is no longer on the screen at all once the game is completed — *reset offered: button not on screen* — so the refusal sentence walkthrough 3 recorded could not be re-read. The game stayed `completed`, which is the outcome the ruling wanted | `records/instructor-endgame-en.json` |
| **W-CE-13** | the supply-chain sections on the Decision Summary | **VERIFIED FIXED** | `{"sourcing": true, "logistics": true, "trade_finance": true, "inventory": true}` on the optional flags, every round | `records/lock-t*-r*.json` (`summary_optional_flags`) |
| **W-CE-11** | a student changes language inside the game | **VERIFIED FIXED** | The top-bar switch changes the interface **and** the server: one click, `PUT /api/user/preferences/` → `{"language": "zh-CN"}`, and the enrolment row reads `zh-CN` | `records/set-language-t3-zh-CN.json` |
| **W-CE-10** | the decorative bell | **VERIFIED FIXED** | No bell icon in the student shell | `records/student-tour-t*-after-r10-*.json` |

---

## (c) The game, round by round

**The game.** Course `CE26` *Global Strategy Practicum* → section `CE26-A`
*Heat A* → game **CE 2026 Heat A**, scenario *Consumer Electronics 2026*,
**8 teams**, 27 students, every one of them created from the console by the
instructor. **Ten rounds were played and the game was finished from the
console.**

| team | home market | profile | plays |
|---|---|---|---|
| 1 Aurora Devices | Africa (**set by hand from the console**, and **renamed** from its generated name) | The Innovator | EN, the edge-case profile |
| 2 Photon Labs | Western Europe | The Brand Builder | EN; driven to negative cash in round 3 and to no sales in rounds 6 and 9 |
| 3 Cobalt Innovations | South America | The Workhorse | **zh-CN throughout — all three enrolments** |
| 4 Nova Circuit | South America | The Green Pioneer | EN; left deliberately over-committed in round 8 |
| 5 Eclipse Gadgets, 6 Prism Tech | East Asia, North America | — | completed and locked from the Decision Summary in most rounds |
| 7 Quantum Edge, 8 Zenith Hardware | North America, Western Europe | — | never submitted: the absentee path the close has to handle |

**Who decided.** The four playing teams went through **every decision screen
every round** and then did what the Decision Summary told them to do. They
pressed the lock button themselves in nine of the ten rounds (round 5: teams
2, 3, 4; round 8: teams 1, 2, 3; every other round: all four). Teams 5 and 6
completed and locked from the Summary in most rounds. That is **four to six of
eight teams deciding every round**, against the brief's floor of four.

**Every decision type, at least once.** Budget allocation and an
over-allocation flagged on screen; a typed loan, repayment, **equity raise**
and dividend, each stored as typed; a tax-structure switch; R&D feature
upgrades and the platform modal (refused for budget, with the reason shown);
a new product and a product retired end-of-round; the marketing mix with an
in-band price, an out-of-band price kept and adjusted at close, a **blank
price** (not for sale) and a production volume of 600,000 units; a market
entry; a plant build; a partnership, **and a partnership withdrawn**;
compliance investment; talent headcount, training and staff allocation; ESG
investment and a governance commitment; an organisation-structure switch; an
acquisition; a board memo over the word limit and then within it, evaluated;
a bought research report; analyst questions refused visibly and charged
nothing; an autosave refused while an operator held the game lock; and at
round 5 the **customs classification** and the **Gen 3 platform generation**.

**How each round was resolved, and what it cost.**

| round | path | processing | 
|---|---|---|
| 1 | Close → process → advance (zh-CN console) | first attempt |
| 2 | Close → process → advance (zh-CN) | first attempt |
| 3 | Close → process → advance (EN) | first attempt |
| 4 | **Close & process now** with a written reason (zh-CN) | first attempt |
| 5 | Close → process → advance (zh-CN) | **REFUSED**, 2 teams; reopened, equity resized, closed again |
| 6 | Close → process → advance (EN) | **REFUSED**, 4 teams; reopened, resized, closed again |
| 7 | **Game Lifecycle › Advance Round** with four teams pending (zh-CN) | first attempt |
| 8 | Close → process → advance (zh-CN) | **HTTP 500 × 4**, then REFUSED once more; a database intervention was needed |
| 9 | Close → process → advance (EN) | **REFUSED**, 1 team; reopened, resized, closed again |
| 10 | Close → process → **Finish game** (EN) | first attempt; `game_status` **completed** |

`POST /api/games/1/round-control/process/` answered **400 seven times and 500
six times** across the game. Four of the ten rounds needed an operator to
reopen them and edit a team's financing before they would score; one needed a
change to the database.

**The end of the game.** At round 10 the console offered **Finish game in
place of Advance** (`advance buttons=0 finish buttons=1`), the game reported
itself `completed`, and round 1's results, round 10's results, the leaderboard
and the financial-report history were all still `200` afterwards. Grades were
calculated on ten rounds, the three CSVs exported, *Delete Game* refused twice
(record, then competition heat), and *Archive Game* accepted.

### The money, per team per round

`opening cash + revenue − charges = closing cash` is checked per team per
round in `records/check-round<N>.json`. **Over 80 team-rounds:**

* the identity the platform publishes (`cash_opening + operating + investing +
  financing == cash_closing`) closes to the cent, every team, every round;
* **the worst difference between one round's closing cash and the next
  round's opening cash is $0.00** — walkthrough 3's W-CE3-01 is gone;
* **the worst gap between the printed income-statement lines and the printed
  net income is $0.00** on the served figures — W-CE3-03 is gone;
* **the worst charge that reaches no served field is $0.00** — W-CE3-04's
  measurable half is gone.

Exactly **one** cross-check failed in the whole game: *the leaderboard is
ordered by performance index and ranks are 1..n*, at round 8. That is the R32
inactivity rule firing — Nova Circuit sold nothing — and the screen now
explains it (W-CE3-15). The check asserts strict ordering, so it cannot pass
when the rule is working.

```

### Round 1
resolved: console (console language zh-CN); 9 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 57.95 | 2 Cobalt Innovations 54.52 | 3 Nova Circuit 54.48 | 4 Aurora Devices 54.38 | 5 Prism Tech 52.60 | 6 Eclipse Gadgets 51.54 | 7 Quantum Edge 49.99 | 8 Zenith Hardware 49.92
commercially inactive: ['Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | $50,000,000 | $189,672 | $14,978,540 | $32,511,132 | yes | yes |
| Photon Labs | $50,000,000 | $3,984,120 | $14,055,364 | $44,428,756 | yes | yes |
| Cobalt Innovations | $50,000,000 | $378,000 | $15,375,760 | $26,902,240 | yes | yes |
| Nova Circuit | $50,000,000 | $405,720 | $15,527,392 | $26,778,328 | yes | yes |
| Eclipse Gadgets | $50,000,000 | $173,460 | $1,863,204 | $48,310,256 | yes | yes |
| Prism Tech | $50,000,000 | $1,407,000 | $1,900,450 | $49,506,550 | yes | yes |
| Quantum Edge | $50,000,000 | $0 | $650,000 | $49,350,000 | yes | yes |
| Zenith Hardware | $50,000,000 | $0 | $1,070,000 | $48,930,000 | yes | yes |

### Round 2
resolved: console (console language zh-CN); 9 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 60.58 | 2 Cobalt Innovations 53.85 | 3 Nova Circuit 53.73 | 4 Aurora Devices 52.84 | 5 Prism Tech 50.18 | 6 Eclipse Gadgets 48.09 | 7 Quantum Edge 44.99 | 8 Zenith Hardware 44.86
commercially inactive: ['Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | $32,511,132 | $283,500 | $24,491,000 | $13,523,632 | yes | yes |
| Photon Labs | $44,428,756 | $4,064,029 | $12,370,561 | $40,622,225 | yes | yes |
| Cobalt Innovations | $26,902,240 | $454,406 | $13,633,702 | $19,482,944 | yes | yes |
| Nova Circuit | $26,778,328 | $466,754 | $13,768,073 | $19,237,010 | yes | yes |
| Eclipse Gadgets | $48,310,256 | $173,460 | $1,866,144 | $46,617,572 | yes | yes |
| Prism Tech | $49,506,550 | $1,421,070 | $1,904,112 | $49,023,508 | yes | yes |
| Quantum Edge | $49,350,000 | $0 | $650,000 | $48,700,000 | yes | yes |
| Zenith Hardware | $48,930,000 | $0 | $1,070,000 | $47,860,000 | yes | yes |

### Round 3
resolved: console (console language en); 8 checks passed, 1 failed
   instructor FAIL: the server holds the language this reader stated -- asked en, server zh-CN
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 62.52 | 2 Cobalt Innovations 52.46 | 3 Nova Circuit 52.30 | 4 Aurora Devices 51.39 | 5 Prism Tech 46.59 | 6 Eclipse Gadgets 43.09 | 7 Quantum Edge 39.99 | 8 Zenith Hardware 39.79
commercially inactive: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | $13,523,632 | $1,047,133 | $19,887,034 | -$168,269 | yes | yes |
| Photon Labs | $40,622,225 | $64,948,487 | $88,177,000 | -$2,120,651 | yes | yes |
| Cobalt Innovations | $19,482,944 | $1,134,000 | $19,872,520 | $6,378,424 | yes | yes |
| Nova Circuit | $19,237,010 | $1,146,600 | $20,007,898 | $6,009,712 | yes | yes |
| Eclipse Gadgets | $46,617,572 | $169,991 | $1,873,840 | $44,913,723 | yes | yes |
| Prism Tech | $49,023,508 | $1,407,000 | $1,906,930 | $48,523,578 | yes | yes |
| Quantum Edge | $48,700,000 | $0 | $650,000 | $48,050,000 | yes | yes |
| Zenith Hardware | $47,860,000 | $0 | $1,070,000 | $46,790,000 | yes | yes |

### Round 4
resolved: force (console language zh-CN); 8 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 64.23 | 2 Cobalt Innovations 51.71 | 3 Nova Circuit 51.52 | 4 Aurora Devices 50.41 | 5 Prism Tech 44.26 | 6 Eclipse Gadgets 39.64 | 7 Quantum Edge 34.98 | 8 Zenith Hardware 34.71
commercially inactive: ['Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$168,269 | $1,009,372 | $16,321,871 | -$7,477,242 | yes | yes |
| Photon Labs | -$2,120,651 | $3,764,880 | $17,120,906 | $17,291,455 | yes | yes |
| Cobalt Innovations | $6,378,424 | $1,127,700 | $15,661,701 | -$1,134,977 | yes | yes |
| Nova Circuit | $6,009,712 | $1,140,426 | $15,782,083 | -$1,611,345 | yes | yes |
| Eclipse Gadgets | $44,913,723 | $173,460 | $1,873,944 | $43,213,240 | yes | yes |
| Prism Tech | $48,523,578 | $1,392,930 | $1,909,748 | $48,006,760 | yes | yes |
| Quantum Edge | $48,050,000 | $0 | $650,000 | $47,400,000 | yes | yes |
| Zenith Hardware | $46,790,000 | $0 | $1,070,000 | $45,720,000 | yes | yes |

### Round 5
resolved: console (console language zh-CN); 9 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 65.93 | 2 Cobalt Innovations 50.98 | 3 Aurora Devices 49.57 | 4 Nova Circuit 49.34 | 5 Prism Tech 41.97 | 6 Eclipse Gadgets 33.79 | 7 Quantum Edge 29.97 | 8 Zenith Hardware 29.62
commercially inactive: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$7,477,242 | $1,059,050 | $15,840,621 | -$12,233,933 | yes | yes |
| Photon Labs | $17,291,455 | $3,717,000 | $19,019,470 | $1,988,985 | yes | yes |
| Cobalt Innovations | -$1,134,977 | $1,134,000 | $17,536,490 | -$9,526,438 | yes | yes |
| Nova Circuit | -$1,611,345 | $882,000 | $17,630,290 | -$10,110,422 | yes | yes |
| Eclipse Gadgets | $43,213,240 | $0 | $1,450,000 | $41,763,240 | yes | yes |
| Prism Tech | $48,006,760 | $1,407,000 | $1,913,410 | $47,500,350 | yes | yes |
| Quantum Edge | $47,400,000 | $0 | $650,000 | $46,750,000 | yes | yes |
| Zenith Hardware | $45,720,000 | $0 | $1,190,000 | $44,530,000 | yes | yes |

### Round 6
resolved: console (console language en); 8 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 66.73 | 2 Cobalt Innovations 52.72 | 3 Nova Circuit 51.05 | 4 Aurora Devices 50.28 | 5 Prism Tech 41.38 | 6 Eclipse Gadgets 30.55 | 7 Quantum Edge 24.96 | 8 Zenith Hardware 24.53
commercially inactive: ['Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$12,233,933 | $1,629,531 | $14,587,028 | -$13,077,071 | yes | yes |
| Photon Labs | $1,988,985 | $1,683,990 | $16,114,080 | -$6,910,597 | yes | yes |
| Cobalt Innovations | -$9,526,438 | $1,649,088 | $15,068,189 | -$11,830,634 | yes | yes |
| Nova Circuit | -$10,110,422 | $1,656,572 | $15,194,793 | -$12,241,746 | yes | yes |
| Eclipse Gadgets | $41,763,240 | $173,460 | $2,033,484 | $39,903,216 | yes | yes |
| Prism Tech | $47,500,350 | $1,435,140 | $2,037,494 | $46,897,996 | yes | yes |
| Quantum Edge | $46,750,000 | $0 | $650,000 | $46,100,000 | yes | yes |
| Zenith Hardware | $44,530,000 | $0 | $1,070,000 | $43,460,000 | yes | yes |

### Round 7
resolved: lifecycle (console language zh-CN); 8 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 67.28 | 2 Cobalt Innovations 53.33 | 3 Nova Circuit 51.64 | 4 Aurora Devices 50.87 | 5 Prism Tech 35.47 | 6 Eclipse Gadgets 24.70 | 7 Quantum Edge 19.95 | 8 Zenith Hardware 19.44
commercially inactive: ['Prism Tech', 'Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Prism Tech', 'Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$13,077,071 | $2,646,000 | $17,272,803 | -$14,090,186 | yes | yes |
| Photon Labs | -$6,910,597 | $2,646,000 | $18,795,460 | -$11,954,759 | yes | yes |
| Cobalt Innovations | -$11,830,634 | $2,646,000 | $17,843,567 | -$13,718,867 | yes | yes |
| Nova Circuit | -$12,241,746 | $2,646,000 | $17,968,247 | -$14,049,103 | yes | yes |
| Eclipse Gadgets | $39,903,216 | $0 | $1,450,000 | $38,453,216 | yes | yes |
| Prism Tech | $46,897,996 | $0 | $1,810,000 | $45,087,996 | yes | yes |
| Quantum Edge | $46,100,000 | $0 | $650,000 | $45,450,000 | yes | yes |
| Zenith Hardware | $43,460,000 | $0 | $1,070,000 | $42,390,000 | yes | yes |

### Round 8
resolved: console (console language zh-CN); 9 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 68.81 | 2 Cobalt Innovations 54.81 | 3 Aurora Devices 51.62 | 4 Prism Tech 33.08 | 5 Eclipse Gadgets 21.20 | 6 Nova Circuit 46.64 | 7 Quantum Edge 14.91 | 8 Zenith Hardware 14.31
commercially inactive: ['Nova Circuit', 'Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Nova Circuit', 'Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$14,090,186 | $3,822,000 | $9,068,338 | -$9,208,793 | yes | yes |
| Photon Labs | -$11,954,759 | $3,822,000 | $8,551,220 | -$8,006,599 | yes | yes |
| Cobalt Innovations | -$13,718,867 | $3,822,000 | $9,515,726 | -$9,183,543 | yes | yes |
| Nova Circuit | -$14,049,103 | $0 | $8,029,616 | -$21,409,103 | yes | yes |
| Eclipse Gadgets | $38,453,216 | $173,460 | $1,884,024 | $36,742,652 | yes | yes |
| Prism Tech | $45,087,996 | $1,407,000 | $1,923,130 | $44,571,866 | yes | yes |
| Quantum Edge | $45,450,000 | $0 | $650,000 | $44,800,000 | yes | yes |
| Zenith Hardware | $42,390,000 | $0 | $1,070,000 | $41,320,000 | yes | yes |

failed cross-checks (1):
  - leaderboard is ordered by performance index and ranks are 1..n -- [('Photon Labs', 1, 68.81), ('Cobalt Innovations', 2, 54.81), ('Aurora Devices', 3, 51.62), ('Prism Tech', 4, 33.08), ('Eclipse Gadgets', 5, 21.2), ('Nova Circuit', 6, 46.64), ('Quantum Edge', 7, 14.91), ('Zenith Hardware', 8, 14.31)]

### Round 9
resolved: console (console language en); 8 checks passed, 0 failed
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 67.50 | 2 Cobalt Innovations 56.16 | 3 Aurora Devices 52.97 | 4 Nova Circuit 47.93 | 5 Prism Tech 30.41 | 6 Eclipse Gadgets 15.27 | 7 Quantum Edge 9.87 | 8 Zenith Hardware 9.18
commercially inactive: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Eclipse Gadgets', 'Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$9,208,793 | $4,998,000 | $11,543,774 | -$7,055,796 | yes | yes |
| Photon Labs | -$8,006,599 | $3,528,000 | $11,267,280 | -$8,042,580 | yes | yes |
| Cobalt Innovations | -$9,183,543 | $4,998,000 | $12,109,044 | -$7,350,162 | yes | yes |
| Nova Circuit | -$21,409,103 | $4,998,000 | $12,246,544 | -$13,600,441 | yes | yes |
| Eclipse Gadgets | $36,742,652 | $0 | $1,330,000 | $35,412,652 | yes | yes |
| Prism Tech | $44,571,866 | $1,407,000 | $1,926,370 | $44,052,496 | yes | yes |
| Quantum Edge | $44,800,000 | $0 | $650,000 | $44,150,000 | yes | yes |
| Zenith Hardware | $41,320,000 | $0 | $1,070,000 | $40,250,000 | yes | yes |

### Round 10
locked: Aurora Devices, Photon Labs, Cobalt Innovations, Nova Circuit, Eclipse Gadgets, Prism Tech, Quantum Edge, Zenith Hardware
standings: 1 Photon Labs 68.94 | 2 Cobalt Innovations 57.48 | 3 Aurora Devices 54.35 | 4 Nova Circuit 49.21 | 5 Prism Tech 27.49 | 6 Eclipse Gadgets 11.49 | 7 Quantum Edge 4.78 | 8 Zenith Hardware 3.96
commercially inactive: ['Quantum Edge', 'Zenith Hardware']; marked on the leaderboard: ['Quantum Edge', 'Zenith Hardware']

| team | opening cash | revenue | charges | closing cash | opening == last closing | statement adds up |
|---|---:|---:|---:|---:|---|---|
| Aurora Devices | -$7,055,796 | $6,174,000 | $9,343,336 | -$2,130,194 | yes | yes |
| Photon Labs | -$8,042,580 | $6,174,000 | $9,102,740 | -$4,150,030 | yes | yes |
| Cobalt Innovations | -$7,350,162 | $6,174,000 | $9,909,549 | -$2,577,246 | yes | yes |
| Nova Circuit | -$13,600,441 | $6,174,000 | $10,038,859 | -$7,322,691 | yes | yes |
| Eclipse Gadgets | $35,412,652 | $147,441 | $1,889,243 | $33,670,850 | yes | yes |
| Prism Tech | $44,052,496 | $1,407,000 | $2,049,610 | $43,409,886 | yes | yes |
| Quantum Edge | $44,150,000 | $0 | $650,000 | $43,500,000 | yes | yes |
| Zenith Hardware | $40,250,000 | $0 | $1,070,000 | $39,180,000 | yes | yes |
```

---

## (d) New defects

Same severity scale as the earlier passes: **P0** data loss / cannot proceed /
wrong number shown to a player · **P1** wrong or missing behaviour ·
**P2** wording or cosmetic.

> The first two are round-stoppers and are **already being repaired on branch
> `walk-ce4-round-stoppers`**. They are recorded here as found; nothing was
> repaired in this pass.

| id | screen | role | lang | what the user sees | what they should see | sev | repro | evidence |
|---|---|---|---|---|---|---|---|---|
| **W-CE4-01** | Game Control › Round control | instructor | EN, zh | **A partnership dissolving stops the game dead, with a 500 and an empty screen.** In round 8 a partner walked away and Phase 1 raised `TypeError: ActiveModifier() got unexpected keyword arguments: 'team', 'modifier_key', 'source', 'round_applied'` at `core/engine/alliance_engine.py:392`. `ActiveModifier` has `game, modifier_type, source_event, target_segment, target_feature, target_market, target_field, modifier_value, started_round, expires_round, is_cumulative` — four of the eight keyword arguments the call passes do not exist. `POST /api/games/1/round-control/process/` answered **500** on every attempt, the round stayed `closed / processing_status FAILED`, and **the console showed the operator nothing**: no toast, no modal, no line on the page; the card still read *Closed; awaiting processing · 8 of 8 teams have locked decisions*. The Operator Log records only `process_round · rejected · Operator requested process_round`. The alliance row is never saved, so it recurs on every retry: the game cannot pass the round in which a partnership dissolves. It is dead code no six-round game could reach — this is the first game long enough to reach it | the round processes; and if a round cannot be processed, the console says why | **P0** | establish a partnership early, let its satisfaction fall below the partner's floor, and process the round it dissolves in | `records/round-wont-process-r8-en.json`, `runtime/backend.log` (the traceback), `harness/unstick_alliance_dissolution.py` |
| **W-CE4-02** | Game Control › Round control, after a deadline close | instructor, student | EN, zh | **A round every team locked cannot be scored, and again nothing is shown.** *Round 5 cannot be scored: 2 equity raise(s) exceed the funding shortfall they claim to finance. Correct the row(s) and retry. Cobalt Innovations: equity raise of $14,334,976.79 exceeds the funding shortfall of $14,184,976.79 …* — answered **400**, with an empty console. It happened in rounds 5, 6 and 9 as well as 8, to nine team-rounds in all, always by exactly $150,000. The cause is visible in the record rather than inferred: the pre-flight taken from the platform's own published figures **immediately before the close** said every team was inside the cap by $100,000, and the same comparison after the close said all four were outside it by $150,000. The close is what moved the number — `deadline_lock`, integrator decision 14's repair, makes an unaffordable draft fit by reducing what it commits, and leaves the equity raise sized against the commitments it has just removed. Nothing on any student screen says so: the Decision Summary offered the lock and the server accepted it | the close resizes what it has made stale, or the round is scoreable whatever the close did; and the console says why a round will not process | **P0** | let a team raise the equity the Decision Summary asks for, leave it unlocked, close the round, then press *Run post-round processing* | `records/round-wont-process-r5-en.json`, `runtime/preflight-r6.log`, `runtime/backend.log`, `records/fix-equity-t*-r*.json` |
| **W-CE4-03** | Finance › Capital Management | student | EN, zh | **The equity a team is told to raise is refused by a different rule with a different figure.** The Decision Summary says *Cut $11,968,269.34 … Raising more debt or equity has the same effect*; the financing route answers *New equity of $12,000,000.00 exceeds the current-round funding shortfall of **$6,968,269.34***. The difference is exactly the $5,000,000 of new debt the lock has just declined to count for a company in distress: while that refused debt is still on the round it reduces the equity cap by the same amount. Nothing tells the team to take the debt off the round first — the team has to work out that removing a request the platform has already refused is what unlocks the remedy | one shortfall figure, or a sentence that names the order to do things in | **P1** | a team in financial distress: leave `new_debt` on the round and try to raise the equity the blocker asks for | `records/follow-blocker-t1-r4-en.json` (`attempts`, `refused`) |
| **W-CE4-04** | Finance › Capital Management | student | EN, zh | **The equity box keeps a number the server refused.** After *New equity of $14,000,000.00 exceeds the current-round funding shortfall of $13,920,650.70*, the box still reads `$ 14,000,000` while the stored `new_equity` is `0.00`. The refusal is shown, so the save does not fail silently — but the Finance page then displays money the round does not have, and every figure the Decision Summary computes comes from the server | the box shows what was stored | **P1** | type an equity raise above the cap and look at the box afterwards | `records/follow-blocker-t2-r4-en.json` (`round_figure_box` = `"$ 14,000,000"`, `round_figure_stored` = `"0.00"`) |
| **W-CE4-05** | Finance › Capital Management | student | EN, zh | **The cap is exact to the cent and the box steps in millions.** $14,000,000 is refused for exceeding $13,920,650.70 by $79,349.30, and the refusal names the cap but no figure the box's own step can produce. A player has to type cents into a control that offers millions | the largest acceptable amount, in a form the control can produce | P2 | type a round number into the equity box when the shortfall is not a round number | `records/follow-blocker-t*-r*.json` (`round_figure_typed` vs `exact_typed`) |
| **W-CE4-06** | Leaderboard | student, instructor | EN, zh | **The Leaderboard opens on Round 0.** At round 9 of 10 the page opens on the bootstrap round — subtitle *Round 0 · Team Rankings*, selector *Round 0* — where all eight teams read `55.00 +0.00` and rank 1, and nobody has played. It never moves to the latest processed round; the reader has to find the selector. `LeaderboardPage.js:28` computes `latestProcessed` from a `currentRound` that is `undefined` on the first render, `useState` captures the resulting 0, and the corrective effect at `:49` only fires when `selectedRound < 0`, which 0 is not. This is the screen a competition is read from | the latest processed round | **P1** | open the Leaderboard at any round after the first | `records/leaderboard-marker-t1-en.json` (`round_the_page_opened_on`, `page_text_as_opened`) |
| **W-CE4-07** | the post-login Strategic Briefing | student | EN, zh | **Raw Markdown is printed to the player**: *`**Quarter 3 Results**` Revenue declined 3.6% to $1,009,372…* and *`**第 2 回合业绩**` 收入增长 20.2%，达到 $454,406。* The asterisks are on the screen in both languages. `core/engine/narratives.py:554` and `:575` author the heading as `'**Quarter {round} Results**'` / `'**第 {round} 回合业绩**'`, and the modal renders the string as text | a heading, not asterisks | P2 | sign in as a member who has not yet opened the round | `records/verify-briefing-t1-m4-en.json`, `records/verify-briefing-t3-m2-zh-CN.json` (`raw_markdown`) |
| **W-CE4-08** | Instructor › AI Coach | instructor | EN | **Half-Chinese sentences on an English console.** *Nova Circuit entered 北美 via 从母国市场出口* — 12 of the game's 100 alerts, every one a `notable_move`, because the values interpolated into the alert are localised when it is **written** and the sentence around them when it is **read**. A Chinese-reading instructor sees 100 of 100 correctly; an English-reading one sees twelve mixed | one language per sentence | **P1** | write alerts with the instructor's stored language set to zh-CN, then read the AI Coach in English | `records/probe-alert-language.json` (`by_language.en.wrong_language`) |
| **W-CE4-09** | Instructor › AI Coach | instructor | EN, zh | **A sentinel printed as a figure**: *Nova Circuit debt-to-equity ratio at 99999.00* / *Nova Circuit 的资产负债率达到 99999.00*, on seven alerts, in both languages. It is what the engine stores for a company whose equity is not positive | the condition in words, not a placeholder number | P2 | let a team's equity go negative and read the AI Coach | `records/probe-alert-language.json` (`sentinel_figures`) |
| **W-CE4-10** | Decision Summary, Finance | student | EN, zh | **The debt-to-equity ceiling is the wrong way round for a company with negative equity, and it blocks the lock.** Cobalt Innovations, equity **−$415,575.79** and debt $17,000,000, is refused — *预计资产负债率 3.40 超过上限 2.0。请调整融资。* — the moment it raises the $5,421,575.79 of equity the lock itself asks for, because that turns its equity positive and the ratio finite. **Borrowing $10,000,000 more is accepted and clears the blocker**, since a company with negative equity has a negative ratio and passes a ceiling of 2.0. On the same Finance page `capital.available_credit` is `0` and `capital.max_total_debt` is `0.0`, and the debt is accepted anyway. Aurora Devices was refused the same way in round 3 (*ratio of 4.00*) and was closed by the deadline. `key_ratios.debt_to_equity` is served as **null**, so the number the team is refused for is on no screen | a ceiling that treats negative equity as the worst case, not the best; and the ratio shown to the team | **P0** | a team whose equity has gone negative: raise the equity the Decision Summary asks for, then try to lock | `records/probe-de-ceiling-t3-r4-zh-CN.json` (`levers_tried`, `finance_context`), `records/follow-blocker-t{3,4}-r4-*.json` |
| **W-CE4-11** | everywhere | student, instructor | zh | **The stored language is never read back.** A person whose enrolment says `zh-CN`, signing in on a browser that has not stored the choice, gets an English interface: `i18next` looks at `localStorage` then `navigator` and never at the server (`i18n.js:19-22`), and nothing sets `gs_language` from the language the server holds. The first screen is then half and half — *Round 2 Strategic Briefing / Your team's performance summary and strategic outlook* in English above *收入增长 20.2%，达到 $454,406。净利润：$-13,179,296。* in Chinese, because the prose comes from the server by enrolment and the chrome from i18next. The instructor's console comes up English (2 Chinese characters on the page) while the server holds `zh-CN` for them | the interface in the language the server holds for that person | **P1** | sign in as a zh-CN student or instructor on a clean browser profile | `records/fresh-browser-s2609-zh-CN.json`, `records/fresh-browser-walk_instructor-zh-CN.json` |
| **W-CE4-12** | Products, R&D, Create Product, Dashboard | student | EN, zh | **A team renamed from the console keeps its old company name on its R&D platform.** Team 1 was renamed *Aurora Devices* before the game was activated; its platform is *Vertex Electronics Base Platform* on every read — `products[].platform_name`, `active_platforms[].name`, `rd.owned_platforms[].platform_name` — and *Vertex Electronics* is a company that exists nowhere else in the game. Every other team, not renamed, reads correctly (`Photon Labs Base Platform`, `Cobalt Innovations基础平台`) | the platform named after the team as it is now called | P2 | rename a team on Game Control before activating, then open Products as that team | `records/verify-ce3-t1-r*-en.json` (`platform_names`), `harness/dbq.py sql "select t.name, p.name from team_platform p join team t on t.id=p.team_id"` |
| **W-CE4-13** | Finance › Tax Structure | student | zh | **The tax card's risk copy is English on a Chinese screen**: *audit risk*, *expected audit cost*, *per audit*, *Expected value over*, *remaining rounds*, and the authored *Tax benefit: None* / *Repatriation: No improvement* beside them. Seven screens across the game | the card in the reader's language | P2 | zh-CN team → Finance → Tax Structure | `records/student-play-t3-r10-zh-CN.json` (screen `p3-r10-14-finance-tax`), `harness/leak_summary.py` |
| **W-CE4-14** | Stakeholder Communications | student | zh | **The audience names are English on a Chinese screen**: *Board of Directors*, *Investor Community* | the audience in the reader's language | P2 | zh-CN team → Stakeholder Communications | `records/student-play-t3-r10-zh-CN.json` (screen `p3-r10-70-communications`) |
| **W-CE4-15** | Instructor › Operator Log | instructor | zh | **The audit reason is English on a Chinese console**: every row reads *Operator requested close_round*, *Operator requested process_round*, while the *Before → after* column beside it is Chinese | the reason in the console's language | P2 | zh-CN console → Operator Log | `records/instructor-round1-console-zh-CN.json` (screen `r1-12-operator-log`) |
| **W-CE4-16** | Industry News | student | zh | **The headlines are English on a Chinese screen** — *Government tightening standards due to poor foreign firm compliance*, *…global surge in shipping demand against tight vessel capacity…*, *Government increasing scrutiny of firms from LATAM*. This is the carry-over walkthrough 3 named as authored content: `MarketConditionByRound.market_outlook_narrative` has no `_zh` column. Recorded again because it is the largest block of English a Chinese player reads, 56 screens this game | authored Chinese, which needs a column and a translation | P2 | zh-CN team → Industry News | `harness/leak_summary.py` output |

---

## (e) What could not be driven, and the auditor's own interventions

| item | why |
|---|---|
| **The plant-collision refusal (W-CE2-01's first half)** | By round 7 every acquisition target that brings a plant had already been bought by another team, so the collision could not be set up again. The other half — a plant built in the market of a completed acquisition — was driven and the round processed. The boundary itself was driven in both orders and both languages in walkthrough 3. |
| **Withdrawing a queued acquisition (W-CE2-02's third case)** | Same reason: no target was left to queue by round 7. The plant and the partnership withdrawals were driven on the real pages. |
| **A refused marketing row that names its product (W-CE-04)** | The path needs a product-market row with no stored decision, and by round 7 every row already carried one. |
| **Round 8 without a database intervention** | W-CE4-01 stops the round with a 500 on every attempt. To reach round 10 and the *Finish game* control at all, `unstick_alliance_dissolution.py --apply` marked four `team_alliance_state` rows DISSOLVED and terminated thirteen `team_partnership` rows. **It changes the game**: the four teams lose their partnership benefits from round 8 on and the dissolution penalty is never applied, so every figure after round 8 is on a game that was nudged. |
| **Rounds 5, 6, 8 and 9 without an operator reopening them** | W-CE4-02. Each was reopened from the console, the named teams' equity resized from the Finance page, and the round closed again. `resolve_with_recovery.sh` is that sequence; `preflight_equity.py` is the check the console does not have. |
| **Phase 2 narratives and the memo evaluation from a model** | By design of this stack: every LLM URL points at an unreachable port, so the round narrative and the memo evaluation use the template/heuristic fallback, which is what is on record and is correctly localised. |
| **An answer from Ask the Analyst** | The scenario has no analyst, so only the refusal path exists. It was driven every round, in the asking student's own language, with nothing charged. |
| **Marking a competition heat from the console** | Unchanged from all three earlier passes: nothing in the frontend writes `SimulationInstance.settings['is_competition']`. `harness/mark_competition.py` does it, so the delete and reset refusals for a heat can be driven at all. |
| **Chinese glyphs** | No CJK font in the sandbox and no route to a font CDN. Every zh-CN claim in this report is about the rendered DOM text, which is what the records carry. |
| **Screenshots** | Removed entirely at the owner's instruction, mid-run: the tree had reached 161 MB of images against a ~25 MB budget. `walk.Recorder.screen` now records the screen, its URL, its leak scan and the API calls it made without writing the picture (`WALK_SCREENSHOTS=1` restores it). **Every row in (b) and (d) cites quoted DOM text, an API request and response, or a log line instead** — 2,158 screens are still named and scanned in `records/`. |

### Disclosed interventions by the auditor

Everything below is an auditor's action on a disposable database, named here so
nothing in the record is taken for the platform's own behaviour.

1. `harness/mark_competition.py` marks the game a competition heat, because the
   console cannot.
2. **`unstick_alliance_dissolution.py --apply`** — the database change described
   above, without which the game ends at round 8.
3. `reopen_round.py` + `fix_equity_and_lock.py` in rounds 5, 6, 8 and 9: the
   round reopened from the console and the named teams' equity resized from the
   Finance page. Both are recorded per round.
4. `drive_overproduction.py` typed 600,000 units into Photon Labs' production
   boxes in round 3 (to take its cash negative the ordinary way) and 0 units
   with a blank price in rounds 6 and 9 (to make a high-scoring firm
   commercially inactive, which is what W-CE3-15 needs). Both are numbers a
   student can type on the Marketing page.
5. `hooks/skip-blocker-r8` deliberately left Nova Circuit over-committed in
   round 8, so that what the close does with an unaffordable draft could be
   seen.
6. `verify_coach_language.py read 1 en` and `verify_operator_log_refusal.py en`
   press the console's language switch, which writes to the server. The
   instructor's language was set back to `zh-CN` through the switch before the
   next round was processed, and the run is on record.
7. `probe_de_ceiling.py` and `probe_equity_cap` typed financing figures into a
   **draft** to ask what the platform would allow; the draft was restored to the
   team's own decision before the round was resolved.

### Harness limits, not defects

* `verify_tax_charge.py` first named a `tax_structure` table that does not
  exist (it is `tax_structure_type`); `verify_ce3.py` first grouped the
  marketing context on a `market_id` its rows do not carry, and read the page
  with one market tab open; `probe_leaderboard_marker.py` first compared a page
  showing one round with a payload for another; `verify_coach_language.py`
  first asserted Chinese while reading as an English reader. **Each of those
  would have reported a defect that is not there**, and each is corrected and
  named in §(a).
* `walk.api` was sending no `Accept-Language`, so it read the AI Coach in a
  different language from the panel beside it. Fixed; §(a).

---

## (f) Verdict, in plain language

### Can a full game be played start to finish with no intervention?

**No. Ten rounds were played and the game was finished from the console — but
four of the ten rounds refused to score until an operator reopened them and
edited a team's financing by hand, and one of them could not be got past at
all without a change to the database.**

That is the headline, and it is worse than walkthrough 3's, because
walkthrough 3's problem was that teams could not submit. This time the teams
could. **The four playing teams pressed the lock button themselves in nine of
the ten rounds**, including from cash of −$2,120,650.70, by doing what the
Decision Summary told them to do. Integrator decision 13 worked: the lock is
reachable, and the refusal names the amount to cut, the largest commitment
that can be cut, and what to raise instead. That was the question the owner
was waiting on, and the answer is yes.

What fails now is the round itself.

1. **A partnership dissolving crashes the round.** In round 8 a partner walked
   away and Phase 1 raised `TypeError: ActiveModifier() got unexpected keyword
   arguments: 'team', 'modifier_key', 'source', 'round_applied'`. The route
   answered **500** on every one of four attempts, and it recurs for ever
   because the alliance row is never saved. It is code that has never run:
   a partnership has to survive long enough to dissolve, and no six-round game
   ever got there. Nothing could be done from any screen; the game only went on
   because the auditor edited the database.

2. **A round every team locked can still refuse to score.** Nine team-rounds
   across rounds 5, 6, 8 and 9 were refused with *N equity raise(s) exceed the
   funding shortfall they claim to finance*, always by exactly $150,000. The
   close is what causes it: decision 14's repair makes an unaffordable draft
   fit by reducing what it commits, and leaves the team's equity raise sized
   against the commitments it has just removed.

3. **In both cases the console tells the operator nothing.** The operator
   presses *Run post-round processing*; no toast appears, no modal, no line on
   the page; the card still reads *Closed; awaiting processing · 8 of 8 teams
   have locked decisions*. The Operator Log records `process_round · rejected ·
   Operator requested process_round` and nothing more. In a competition hall
   an instructor would have a room of students, a round that will not advance,
   and no way whatever to find out why.

Both are being repaired on `walk-ce4-round-stoppers`.

### Is anything a player sees wrong?

**Yes — five things, and the money is no longer one of them.**

The numbers are right. Over **80 team-rounds**: the cash identity closes to
the cent; the closing cash of one round is the opening cash of the next to the
cent; the printed income statement sums to the printed net income; and every
charge reaches a served field. Walkthrough 3's three money defects — W-CE3-01,
W-CE3-03 and W-CE3-04 — are gone, and the $2,000,000 tax-structure charge is
on the strategy expense line where a student can see it. **Every one of
walkthrough 3's twenty defects is verified fixed**, and so is every
walkthrough-2 residue that could be driven.

What a player still sees wrong:

1. **The Leaderboard opens on Round 0.** At round 9 of 10, the screen a
   competition is read from opens on the bootstrap round where all eight teams
   read 55.00 and rank 1 and nobody has played. The reader has to find the
   round selector. When they do, the screen is right — the marker *Did not
   compete* is on the row and the rule is printed under the table, which is
   W-CE3-15 properly fixed.

2. **A team with negative equity is refused for improving it.** Raise the
   equity the Decision Summary asks for and the debt-to-equity ceiling refuses
   the lock; borrow ten million more instead and it is accepted, because a
   negative ratio passes a ceiling of 2.0. The same page says the team has no
   credit left. The ratio it is refused for is served as `null`, so it appears
   on no screen.

3. **Following the instructions takes four attempts.** The blocker asks for an
   amount the financing route then caps lower — by exactly the debt it has just
   refused to count — the cap is exact to the cent while the box steps in
   millions, and after a refusal the box keeps the number the server threw away.

4. **A Chinese player on a fresh browser gets an English screen.** The platform
   now writes the language to the server properly — the in-game switch set
   `enrollment.language = 'zh-CN'` for all three of team 3's members in one
   click — but nothing ever reads it back, so the first briefing is half
   English chrome over Chinese prose. Beside that, an English-reading
   instructor gets twelve half-Chinese alerts (*Nova Circuit entered 北美 via
   从母国市场出口*), seven alerts print the sentinel *debt-to-equity ratio at
   99999.00*, the briefing prints `**Quarter 3 Results**` with the asterisks
   showing, and a team renamed from the console keeps its old company name on
   its R&D platform for the whole game.

5. **The remaining English on a Chinese screen is small and findable**: the tax
   card's risk copy, the two communications audience names, the Operator Log's
   *Operator requested*, and the Industry News headlines, which are authored
   content with no Chinese column — the one item on the list that needs a
   migration rather than a string.

### What I would fix before the first clean game

1. **W-CE4-01** — the dissolution crash. Any game long enough for a partnership
   to fail cannot be finished.
2. **W-CE4-02** — a round that every team locked must be scoreable, and a
   refusal to process must appear on the console.
3. **W-CE4-10** — a team must not be refused for repairing its balance sheet.
4. **W-CE4-06** — the Leaderboard must open on the round that was played.
5. **W-CE4-03/04/05** — one shortfall figure, a box that keeps what was stored,
   and a cap a player can type.
6. **W-CE4-11** — read the stored language back into the interface.

The rest is wording. **What is now true, and was asked for by three
walkthroughs in a row, is that a team in trouble can still play and that the
platform's numbers agree with each other on every line of every statement of
every round.** What is not yet true is that the rounds themselves always
resolve: three times out of four, when this game stopped, it stopped after the
students had done everything right.
