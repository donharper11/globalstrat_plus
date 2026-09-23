# Second full walkthrough — Consumer Electronics 2026, on the repaired tree

**Branch:** `walkthrough-ce-2-2026-09-22`, cut from `crv2-release-integration`
(contains `b890976`, the merge of all four walkthrough repair branches, and
`completion/WALKTHROUGH_CE_2026-09-22.md`; both verified before anything ran).
**Date:** 2026-09-22. **Auditor role:** find defects; nothing in `backend/` or
`frontend/` was changed. The only edits are to the harness under
`handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/harness/`, listed in (a).
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/`
— `harness/` (every driver), `records/` (one JSON per driver run: steps, screens,
API calls, refusals, console, leak scans), `screenshots/` (JPEG), `exports/`.

> Sections: (a) stack and commands · (b) the W-CE verification table ·
> (c) the walkthrough log · (d) new defects · (e) what could not be driven ·
> (f) verdict.

---

## (a) The stack, and the exact commands

Disposable, on this host. **Never** the production database (192.168.50.38),
never `/etc/globalstrat-plus.env`; backups to a scratch directory inside the
evidence tree; every LLM endpoint pointed at an unreachable port, so Phase 2
uses the template fallback; `COMPETITION_REQUIRE_CLEAN_BUILD=false`. The
container and both ports are this pass's own
(`globalstrat-walkthrough-ce2-pg`, database `globalstrat_walk2`, ephemeral
host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build        # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/harness
$H/make_db.sh                    # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py               # migrate + legacy tables, load_scenario --preset electronics, superuser, ONE instructor
python3 $H/start_stack.py        # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin
```

`seed.py` again creates **nothing else**: the course, section, game, teams,
roster, passwords and schedule were all made from the console by the
instructor driver. The harness readiness window did not need lengthening on
this host: `make_db.sh`'s 40 × 1 s `pg_isready` loop and `start_stack.py`'s
180 s wait were enough on both runs (no `TEST_POSTGRES_READY_SECONDS` was set).

Drivers, in the order they were run:

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. the refused 6th member → **team configuration with team 1's home market set by hand to Africa** → activate → schedule → deadline → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, **override**, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after, **operator-log wording and drill-down order checked** | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round), **bell / in-game language switch / team-activity route checked** | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| `lock_round.py` | **new**: completes the product-market rows a round's new product or new market leaves empty, then locks from the Summary; records the blockers and any lock refusal | `lock_round.py <lang> <team> <round>` |
| `verify_marketing_refusal.py` | **new**: drives W-CE-04's path — a row with promotion and no campaign focus — and reads the refusal | `verify_marketing_refusal.py <lang> <team> <round>` |
| `probe_dom.py` | **new**: read-only DOM probe (team-configuration table, the student decision screens, the marketing pane, the Round Results performance block) | `probe_dom.py <what> …` |
| `dbq.py` | **new**: read-only SQL against the disposable database (used for the enrolment-language evidence) | `dbq.py enrollments` |
| `check_round.py`, `apicall.py`, `hold_lock.py`, `mark_competition.py`, `instructor_endgame.py`, `leak_summary.py`, `records_summary.py` | as in the first walkthrough | — |

**Harness changes, all recorded (no runtime code was touched):**

1. `make_db.sh` — its own container and database name, so the first walkthrough's stack cannot be reused by accident.
2. `instructor_setup.py` — team 1's home market is now **chosen by hand (Africa)** in the Team Configuration table instead of only randomised (the W-CE-21 check needs a home market that is not the scenario default); the roster-upload outcome is read off the panel, not only from a toast/modal; the grading **override** control is driven; when a round-control action is refused for a stale round the driver reloads and repeats, so the record says whether the control works at all or only after a refresh.
3. `student_tour.py` — the bell check is inverted (its absence is the repair), the in-game language switch is exercised, the `team-activity` route is visited and the `…/changes/` call counted; any modal is dismissed before the top-bar checks.
4. `student_play.py` — the home-market tab is read from the strategy context instead of assuming tab 0 (this game's team 1 is Africa, the fourth tab); the loan, repayment and dividend boxes are typed key by key and read back; the R&D page is checked for the absence of *Invest next level*; the plant and partnership labels are captured; the W-CE-04 probe was moved out (see 5); products are retired through the row's *Retire product* button and the modal's *Retire End of Round*.
5. `verify_marketing_refusal.py`, `lock_round.py`, `probe_dom.py`, `dbq.py` — new, described above.
6. `instructor_tour.py` — the *Students & Logins* tab is found through `t('instructor.students_logins')`; the hard-coded English label no longer matches, which is itself W-CE-17 working.
7. `instructor_round.py` — the Operator Log rows and the drill-down modal are read and checked (W-CE-07, W-CE-20); a `reprocess` path runs *Run post-round processing* on a round that is already closed (needed after W-CE2-01), and the `lifecycle` path fills the reason box and records the refusal (W-CE-24).
8. `instructor_endgame.py` — *Reset to Setup* is now checked as a refusal (W-CE-26), not merely recorded.
9. `verify_post_activate_deadline.py` — new: reproduces W-CE2-10 from scratch in its own section (`CE26-B`, a two-team game), which is why a second game exists in the database.
10. `unstick_plant_collision.py` — new: the disclosed database intervention that let round 2 be processed after W-CE2-01. It deletes one `decision_plant` row and nothing else; it is an auditor's intervention in a disposable database, not a repair.
11. `shrink_screenshots.py`, `prune_screenshots.py` — new: the evidence is re-encoded at 950 px / quality 38 and the near-duplicate round-3 and round-4 decision screens are dropped (198 files), leaving 632 screenshots at 28 MB against the first walkthrough's 62 MB. Every screen is still named in its run's JSON record.

**Language** is set the product's own way (`localStorage.gs_language`, the key the switch writes) and, since the repair, is also recorded as the student's preference at sign-in. **No visual claim is made about Chinese glyphs**: this sandbox has no CJK font, so zh-CN screenshots show missing-glyph boxes; the standard is the rendered DOM text, recorded per screen.

**Leak scan** on every screen (`walk.scan`), same standard as the first pass.
Console errors and every API status ≥ 400 are captured per screen; the
harness's own aborted Google-Fonts requests (`net::ERR_FAILED`) are excluded
from the counts.

---

## (b) Verification of W-CE-01 … W-CE-26

Every id was reproduced through the step the first walkthrough recorded, on
this stack, in the language(s) it was found in. Screenshots are under
`handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/screenshots/`.

| id | sev (first pass) | the step, repeated | state | what is on the screen now | screenshot |
|---|---|---|---|---|---|
| W-CE-01 | P1 | Game Control → Activate Game; then Save deadline, Extend Deadline, Run post-round processing | **VERIFIED FIXED** | the active tab is still *Game Control* after every one of them (`observed.tab_after_activate` / `…_set_deadline` / `…_extend` = "Game Control") | `i12-game-activated-en.jpg`, `i14b-after-set-deadline-en.jpg` |
| W-CE-02 | **P0** | Finance › Capital Management → click Loan Amount → type `5000000` key by key → Tab | **VERIFIED FIXED** | the box reads `$ 5,000,000` and the draft stores `new_debt 5000000.00`; a typed `250000` into Repayment stores `250000.00`, a typed `0.5` into Dividend stores `0.5000`. Driven on three teams, both languages, every round | `p1-r1-13-finance-capital-en.jpg`, `p3-r1-13-finance-capital-zh-CN.jpg` |
| W-CE-03 | P1 | R&D Investment → *Invest next level* | **VERIFIED FIXED** | there is no *Invest next level* button in either language (0 English, 0 localised, every round, every team) and the guidance no longer points at one; not one `PATCH …/rd/` 400 in the whole walkthrough | `p1-r1-20-rd-en.jpg`, `p1-r1-21-rd-after-upgrade-en.jpg` |
| W-CE-04 | P1 | two products; one product-market row with promotion and no campaign focus; edit another row | **VERIFIED FIXED** | the refusal names the row — *Nova Aurora R1 in Africa: Choose one to three campaign focus features.* — shown once, under the shared *Your last change was not saved* notice with its retry. The whole-section save is still refused (the repair kept that deliberately) but now says which row | `v-wce04-1-r2-01-refusal-en.jpg` |
| W-CE-05 | P1 | Courses & Sections › Bulk Upload (CSV) → `harness/roster.csv` | **VERIFIED FIXED** | a green panel on the roster card: *Added 27 student(s) to the roster. File: roster.csv*, with a dismiss ✕, and it stays until dismissed | `i06-roster-uploaded-en.jpg` |
| W-CE-06 | P2 | Event Manager → Inject Event with no target market → the student ticker | **VERIFIED FIXED** | *…launched an aggressively priced Gen 2 product in global markets.* — no `{market}` on any screen in either language | `s-pre-10-dashboard-en.jpg` |
| W-CE-07 | P2 | Operator Log → *Before → after* | **VERIFIED FIXED** | labelled words: *Status: processed → open \| Closed at: … → — \| Opened at: … \| Closed by: closed by instructor → —*. (The text of a **refused** action is a separate matter — W-CE2-04) | `r3-12-operator-log-en.jpg` |
| W-CE-08 | P2 | Team Overview → View Decisions on a team with no submission | **VERIFIED FIXED** | one translated status, *No submission*; the raw `no_submission` token is gone | `i26-team-decisions-drill-en.jpg` |
| W-CE-09 | P1 | the student sidebar's Team Activity | **VERIFIED FIXED** | no Team Activity entry in the sidebar, no data call from the route, and **no `…/changes/` request** on any student screen (0 across six student tours); no 403 anywhere in the walkthrough | `s-pre-10-team-activity-en.jpg` |
| W-CE-10 | P1 | click the top-bar bell | **VERIFIED FIXED** | there is no bell (`.anticon-bell` count 0) in the student shell, in both languages | `s-pre-10-dashboard-en.jpg` |
| W-CE-11 | P2 | sign in as a student, look for EN / 中文 | **VERIFIED FIXED** | the top bar carries the switch; clicking it changes the interface and writes `gs_language` (`en` → `zh-CN` → `en` on record) and records the choice as the student's preference (see W-CE-15) | `s-pre-03-language-switched-en.jpg` |
| W-CE-12 | P1 | Grading & Export → an override control | **VERIFIED FIXED** | an *Override* button on every row of Team Grades (8 of 8); the modal *Override a category score — Aurora Devices* takes a category, a score and a reason; saving answered *Aurora Devices: Performance Index score overridden.* and the grades were recalculated | `i29b-grading-override-modal-en.jpg`, `i29c-grading-after-override-en.jpg` |
| W-CE-13 | P2 | Review & Submit before any decision | **VERIFIED FIXED** | Sourcing, Logistics, Trade Finance and Inventory are marked *Optional* (`optional: true` on all four in the summary API), carry no *Fix in …* link, and never appear among the lock blockers | `x-t3-r2-95-summary-zh-CN.jpg` |
| W-CE-14 | **P0** | play round 1 with a $0.50 dividend, resolve, open Round Results | **VERIFIED FIXED** | *SHAREHOLDER RETURN −22.2 %* (EN) and *股东回报 −19.4 %* (zh), against API `shareholder_return_cumulative` −0.2221 / −0.1938; the PERFORMANCE INDEX on the page equals the leaderboard's (54.62 / 58.03) | `v-results-t1-r1-en.jpg`, `v-results-t3-r1-zh-CN.jpg` |
| W-CE-15 | P1 | zh-CN, Market Research → Ask the Analyst → Ask | **VERIFIED FIXED**, with a condition | once the team states Chinese the refusal is Chinese: *本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。* In round 1 it was still English: the team's language is its **first enrolment's**, and only the second member had signed in in Chinese. After the first member signed in in Chinese it was Chinese. That condition is W-CE2-05 | `p3-r2-83-research-analyst-asked-zh-CN.jpg` |
| W-CE-16 | P1 | every zh-CN student screen | **VERIFIED FIXED for the strings it listed**, residue remains | the R&D guidance box, *Invest next level* ×5, the Finance save states and hints, the tax cards, the M&A locks, the Summary checklist, the dashboard's next-action copy and the login taglines are Chinese. Still English on a Chinese student screen: the scenario's news headlines and the sourcing / trade-finance names (both named as remaining by the repair itself), plus three it does not name — the market name in Products, Results and the price notices (*Western Europe*, 51 occurrences — W-CE2-06), the Strategic Scorecard sentences (*Conservative leverage. Strong financial position.* — W-CE2-07) and the *… Base Platform* suffix | `p3-r1-20-rd-zh-CN.jpg`, `p3-r1-30-products-zh-CN.jpg`, `records/*zh-CN.json` `leaks` |
| W-CE-17 | P1 | zh-CN instructor session, Game Control and every tab | **VERIFIED FIXED**, one residue | the *Students & Logins* tab is 学生与登录 (the harness's hard-coded English label stopped matching — that is the proof); the Game Control statistics, the monitoring banner, the Extend modal's unit, the Supply Chain panel and the drill-down's audit table are Chinese. Still English: the **AI Coach alerts**, 23 distinct sentences — W-CE2-08 | `zh-r2-i20-team-configuration-zh-CN.jpg`, `zh-r2-i29-ai-coach-zh-CN.jpg` |
| W-CE-18 | P1 | spend on Corporate / Market Strategy, then Review & Submit, then the statement | **VERIFIED FIXED** | the bar and the banner agree — *Budget $11.5M/$5.0M over budget* with *Over budget by $6.5M — total spending $11.5M exceeds available budget $5.0M* — and the statement's `strategy_expense` is the spend the round committed | `p1-r2-95-summary-en.jpg` |
| W-CE-18b | P1 | queue an acquisition in one round, open Review & Submit | **CHANGED** | the three-figure screen is gone and every blocker is a sentence carrying its own numbers; but one screen still shows two totals for what the round costs (*total spending $28.5M* and *Committed spend of $38,000,000.00*) and an unformatted *Unallocated: $-12553689* — W-CE2-09 | `x-t1-r3-95-summary-en.jpg` |
| W-CE-19 | P1 (calibration) | R&D Investment → Create New R&D Platform in round 1 | **STILL PRESENT (calibration, deferred under R48)** | the cheapest platform is $7.6M against a $4.0M round-1 R&D budget: *Over Budget: $3.7M — Cost exceeds R&D budget*; with W-CE-03's buttons gone a team still has no R&D action it can take in round 1, and the checklist keeps *R&D Investment* unstarted | `p1-r1-22-rd-create-platform-modal-en.jpg` |
| W-CE-20 | P2 | Team Overview → View Decisions on a team that saved many times | **VERIFIED FIXED** | the modal opens on the decisions; the audit table is a closed collapse below them (its heading starts at offset 386–455 of the modal text, never 0) | `r1-06-decision-drill-en.jpg` |
| W-CE-21 | P1 | Team Configuration → home market = **Africa** → Save → Activate → the student's Market Strategy | **VERIFIED FIXED** | the console saved `home_market_code AFR`; the student's strategy context says `AFR … is_home_market: true, entry_status: active`, the tab reads *Africa Active*, and the team's talent allocation went to AFR. The same held for team 2 (LATAM, *South America Active*) and team 3 (EU, 西欧 已进入) | `i11-team-config-saved-en.jpg`, `p1-r2-52-market-home-en.jpg` |
| W-CE-22 | P2 | Market Strategy, the home market | **VERIFIED FIXED** | *Build Plant — $14.0M, 2 rounds, 55000 units* (and *$8.0M, 3 rounds, 40000 units* elsewhere) — no $0 plant, and the charge is real: team 2's cash fell by $14.0M and its statement shows `plant_book_value 12,600,000`. Partnerships read *+ Distribution Partner — $2.0M/round* / *每回合 $2.0M*; the cultural-distance enum is a translated phrase | `p2-r1-52-market-home-en.jpg` |
| W-CE-23 | P1 | spend past the budget in one round, then try to lock the next | **CHANGED — a different trap in the same place** | the lock is now refused **in the round the spend is committed**, with the figures on the page before the click (*Committed spend of $38,000,000.00 exceeds available cash of $25,446,310.88*) — the repair working. But nothing on any screen can withdraw a queued acquisition, a plant or a partnership, so the team cannot clear the blocker (W-CE2-02), and when the deadline closes the round the engine executes the very spend the lock refused: the team ends round 3 at −$12.4M cash (W-CE2-03) | `x-t1-r3-95-summary-en.jpg`, `records/check-round3.json` |
| W-CE-24 | P1 | Game Control › Game Lifecycle › Advance Round with teams pending | **CHANGED — still cannot advance** | the modal now asks for a written reason (*Write why this is the right thing to do…*) and OK is disabled until one is typed — that half is fixed. With the reason typed, `POST …/instructor/advance-round/ {force:true, reason:…}` is refused **400 `round_not_ready`**: *Team "Aurora Devices" has not locked decisions for round 3. Re-lock the team (or close the round) before processing.* — while the modal above it promised *8 team(s) have not locked decisions. Their previous round's decisions will carry forward. Proceed?* The round had to be resolved from the Round Control card instead | `r3-01-lifecycle-advance-modal-en.jpg`, `records/instructor-round3-lifecycle-en.json` |
| W-CE-25 | P1 | borrow until projected D/E > 2.0, open Review & Submit, lock | **VERIFIED FIXED** | the D/E check is a blocker on the page: *The projected debt-to-equity ratio of 8.48 exceeds the maximum of 2.0…* is in the Summary's blocker list with the lock button disabled. Across twelve team-rounds no lock was offered and then refused (`POST …/lock/` 400 count: 0) | `x-t2-r4-95-summary-en.jpg` |
| W-CE-26 | P1 | mark a heat, resolve four rounds, Reset to Setup with a reason | **VERIFIED FIXED** | refused: *CE 2026 Heat A is a competition game, so it cannot be reset to setup. Its rounds, results and records have to stay as they were played. Archive the game instead…*; the game was left `active` at round 5 with rounds 1–4 still processed. Delete was refused twice on the same game (it has a record; it is a heat) and Archive was accepted | `end-reset-modal-en.jpg`, `end-reset-after-en.jpg` |

---

## (c) The walkthrough log

### Part 1 — the instructor builds the game (EN) — `records/instructor-setup-en.json`, `instructor-bulk-reset-en.json`

| # | screen | what happened | evidence |
|---|---|---|---|
| i00–i03 | /instructor/login, Courses & Sections | signed in as `walk_instructor`; course `CE26`, section `CE26-A` created and selected | `i00-instructor-login-en.jpg`, `i02-course-created-en.jpg`, `i03-section-selected-en.jpg` |
| i04–i05 | Step 1: Create a Game | *Consumer Electronics 2026*, `CE 2026 Heat A`, **8 teams**; toast *Game "CE 2026 Heat A" created with 8 teams.* | `i04-create-game-form-en.jpg`, `i05-game-created-en.jpg` |
| i06 | Bulk Upload (CSV) | `roster.csv` (27 rows) → **the outcome is announced on the panel** and stays: *Added 27 student(s) to the roster. File: roster.csv* — W-CE-05 fixed | `i06-roster-uploaded-en.jpg` |
| i07–i08 | Assign Students to Teams | 26 assigned; the **sixth member of the first team refused**: *No students were assigned — Cipher Systems already has 5 members, the maximum this section allows. Choose another team, or raise the team size limit.* | `i07-sixth-member-refused-en.jpg`, `i08-teams-assigned-en.jpg` |
| i09–i11 | Game Control › Team Configuration | home markets previewed at random, then **team 1's home market set by hand to Africa**, team 1 renamed *Aurora Devices*, saved → `AFR` on the server. Teams 2–8 kept LATAM/EU/APAC/AFR | `i10-team-config-edited-en.jpg`, `i11-team-config-saved-en.jpg` |
| i12 | Activate Game | popconfirm → active, round 1 open; **the console stayed on Game Control** — W-CE-01 fixed | `i12-game-activated-en.jpg` |
| i13 | Round Schedule › Quick Schedule | *Schedule saved for 10 round(s).* | `i13-round-schedule-en.jpg` |
| i14 | Round Control › Set deadline | on the first pass, straight after Activate, refused — *The game has moved to round 1; this request was for round 0. Refresh the console…* (W-CE2-10, reproduced cleanly later on its own game); after a refresh: *CE 2026 Heat A: deadline updated.*, and the console stayed on Game Control | `i14-set-deadline-modal-en.jpg`, `i14b-after-set-deadline-en.jpg`, `v-activate-deadline-*.jpg` |
| i15–i18 | Extend Deadline, Pause, Resume | +24 h moved the deadline 25 → 26 Sep; *Game paused* / *Game resumed*, the server agreeing each time | `i15-extend-deadline-modal-en.jpg`, `i17-paused-en.jpg`, `i18-resumed-en.jpg` |
| i19–i21 | Event Manager › Inject Event | *Major Competitor Product Launch (medium)*, no market → *Event injected*; the ticker then reads *…in global markets* — W-CE-06 fixed | `i20-inject-event-modal-en.jpg`, `i21-event-injected-en.jpg` |
| i22 | Operator Log | 11 rows, *Before → after* in labelled words — W-CE-07 fixed | `i22-operator-log-en.jpg` |
| i23–i24 | Students & Logins | per-row *Reset to ID* → reveal modal; then *Set all to student ID* → popconfirm *Set 26 passwords? Each student's password becomes their own student ID…* → 27 of 27 accounts have a password | `i24-passwords-issued-en.jpg`, `i24b-bulk-password-reset-en.jpg` |
| i25–i26 | Team Overview › View Decisions | the drill-down opens on the decisions; the status reads *No submission* with no raw token — W-CE-08 and W-CE-20 fixed | `i26-team-decisions-drill-en.jpg` |
| i27–i30 | Grading & Export | default rubric created; *Calculate Grades* at round 0; **the override driven**: *Override* on every team row → *Override a category score — Aurora Devices* → 88 with a reason → *Aurora Devices: Performance Index score overridden.* — W-CE-12 fixed; the three CSV exports downloaded | `i28-grading-rubric-en.jpg`, `i29b-grading-override-modal-en.jpg`, `i29c-grading-after-override-en.jpg`, `exports/` |
| i31–i34 | Briefings, Research Monitor, AI Coach, Supply Chain | all render | `i31-briefings-en.jpg` … `i34-supply-chain-en.jpg` |

### Part 2 — the students, round 1 (teams 1–2 EN, team 3 zh-CN)

Records: `student-tour-t1-pre-en.json`, `student-play-t{1,2}-r1-en.json`, `student-play-t3-r1-zh-CN.json`.

| # | screen | what happened | evidence |
|---|---|---|---|
| s-pre | every student screen before play | all render; **no bell**, **a 中文 / EN switch in the top bar that works** (`gs_language` en → zh-CN → en), **no Team Activity entry and no `…/changes/` call** — W-CE-09, 10, 11 fixed. The only leak scan hit is the word *None* in English copy (*IP Exposure: None*), as in the first pass | `s-pre-10-*-en.jpg`, `s-pre-03-language-switched-en.jpg` |
| 10–13 | Finance › Budget, Capital | 3,000,000 / 2,500,000 / 1,500,000 typed and stored exactly; R&D 9,000,000 → the over-allocation banner; **Loan Amount typed key by key stores 5,000,000**, Repayment 250,000, Dividend 0.50 — W-CE-02 fixed | `p1-r1-11-finance-budget-saved-en.jpg`, `p1-r1-13-finance-capital-en.jpg` |
| 14–15 | Finance › Tax Structure | *Regional Hub* card clicked → `direct → regional_hub` (driven in both languages this time) | `p1-r1-15-finance-tax-switched-en.jpg` |
| 20–23 | R&D Investment | **no *Invest next level* button at all**; Create New R&D Platform opens, is priced at $7.6M against a $4.0M budget and cannot be submitted (*Over Budget: $3.7M*) — W-CE-03 fixed, W-CE-19 unchanged | `p1-r1-20-rd-en.jpg`, `p1-r1-22-rd-create-platform-modal-en.jpg` |
| 30–34 | Product Portfolio | *Nova Aurora R1* created; the last product retired through the row's *Retire product* → *Retire End of Round* (the edit modal of the first pass is now a per-row button) | `p1-r1-31-products-create-modal-en.jpg`, `p3-r1-33-products-edit-modal-zh-CN.jpg` |
| 40–44 | Marketing Mix | in-band price, volume, focus, channel and promotion stored; **1,755 out of band** → *Outside the allowed range… adjusted at close*, stored; a **blank price** → *No price set… priced at $154*, stored `null` | `p1-r1-41-marketing-in-band-en.jpg`, `p1-r1-42-marketing-out-of-band-en.jpg`, `p1-r1-43-marketing-blank-price-en.jpg` |
| 50–53 | Market Strategy | **the home market is Africa and it is *Active*** (tab *Africa Active*, `entry_status active`) — W-CE-21 fixed; a foreign market entered ($500K); *Build Plant — $14.0M, 2 rounds, 55000 units* and *+ Distribution Partner — $2.0M/round* — W-CE-22 fixed | `p1-r1-52-market-home-en.jpg`, `p2-r1-52-market-home-en.jpg` |
| 60–66 | Corporate Strategy | talent headcount 60 and training 100,000; staff allocation 5 to the home market; ESG 500,000 / 250,000 + *Board diversity*; the organisation switch confirmed. M&A offers no target in round 1 | `p1-r1-61-corporate-allocation-en.jpg`, `p1-r1-63-corporate-esg-en.jpg` |
| 80–84 | Market Research | segment report bought ($50,000, on the statement later); **Ask the Analyst → refused visibly five times, nothing charged** (`queries: []`). On the Chinese screen in round 1 the refusal was still English — W-CE2-05 | `p1-r1-83-research-analyst-asked-en.jpg`, `p3-r1-83-research-analyst-asked-zh-CN.jpg` |
| 90–91 | Finance while an operator holds the lock | three `409 lifecycle_in_progress`, the *not saved … will be sent again* banner with *Retry now*, then the value stored once the lock was released | `p1-r1-90-autosave-refused-en.jpg`, `p1-r1-91-autosave-retried-en.jpg` |
| 95–97 | Decision Summary & Submit | the four supply-chain sections are marked **Optional** — W-CE-13 fixed; all three teams locked (zh: 锁定并提交) | `p1-r1-96-lock-confirm-en.jpg`, `p3-r1-97-locked-zh-CN.jpg` |

### Part 3 — round 1 resolved from the console — `records/instructor-round1-console-en.json`, `check-round1.json`

Close round now → Reopen modal opened and cancelled → Run post-round processing (3.8 s, `RESULTS_AVAILABLE`, no narrative error) → Advance to round 2. The cross-check passed on all three teams: the leaderboard is ordered by index with ranks 1..8, the index on Round Results equals the leaderboard's, statement revenue equals results revenue, and *Research $50,000* / *Compliance investment $0* are on every statement. **SHAREHOLDER RETURN reads −22.2 % (EN) / −19.4 % (zh)** — W-CE-14 fixed.

### Part 4 — rounds 2, 3 and 4

**Round 2** (three teams; *Close & process now* with a written reason). Compliance investment 250,000 was set on an entered foreign market, appears on the Summary before the lock and as `compliance_expense 250,000` on every played team's statement, with cash charged; an acquisition was queued; the **over-limit memo** was driven in Chinese (*字数: 315 / 300 (超出限制！)*, *提交评估* disabled) and then submitted within the limit — the assignment name is Chinese (*董事会备忘录：国际扩张战略*), the audience tag is still the English *Board of Directors*, which the language repair listed as remaining; a product was retired.
**Post-round processing then failed with a 500 and the round could not be processed at all — W-CE2-01.** The round was unstuck by deleting the colliding plant decision (`harness/unstick_plant_collision.py`, disclosed), after which the same *Run post-round processing* succeeded (`FULLY_COMPLETE`) and round 3 opened. `check-round2.json` then passed on every line.

**Round 3** (three teams). Every team's lock was refused, with the reason on the page before the click (*Committed spend of $38,000,000.00 exceeds available cash of $25,446,310.88*, *Projected ending cash is $-8,053,689.12*) — and none of them could withdraw the acquisition that caused it (W-CE2-02). The **Game Lifecycle › Advance Round** path was driven: the modal now asks for a written reason, and the route still refuses with `round_not_ready` (W-CE-24, changed). The round was resolved from the Round Control card instead; the three teams were deadline-closed with the decisions the lock had refused, and Aurora Devices ended at **−$12.4M cash** (W-CE2-03).

**Round 4** (three teams). Same again, with the D/E blocker now shown on the page before the click (*The projected debt-to-equity ratio of 8.48 exceeds the maximum of 2.0*) — W-CE-25 fixed. Closed, processed `FULLY_COMPLETE` in 4.3 s, round 5 opened; `check-round4.json` passed on every line (leaderboard order, index equality, statement == results, the R47 rows).

**Every screen again, both languages** — `student-tour-t1-after-r4-en.json`, `student-tour-t3-after-r4-zh-CN.json`, `instructor-tour-en-final-en.json`, `instructor-tour-zh-final-zh-CN.json`. The zh-CN leak list is the one in W-CE-16/17 above: scenario-authored English (news, supply-chain names), market names on Products and Results (W-CE2-06), the Strategic Scorecard sentences (W-CE2-07) and the AI Coach alerts (W-CE2-08).

### End of game — `records/instructor-endgame-en.json`

| # | screen | what happened | evidence |
|---|---|---|---|
| end-grading | Grading & Export | *Calculate Grades* on four resolved rounds: *Grades calculated*, raw 34.6–34.9 → 60.0–60.1 for the unplayed teams, with an *Override* control on every row; the three CSV exports downloaded again | `end-grading-after-4-rounds-en.jpg`, `exports/final-*.csv` |
| end-delete-has-record | Delete Game (reason) | **refused**: *CE 2026 Heat A already has a record of instructor actions or team decisions. That record is permanent, so the game cannot be deleted. Archive the game instead…* | `end-delete-has-record-modal-en.jpg`, `end-delete-has-record-after-en.jpg` |
| end-delete-competition | Delete Game after `mark_competition.py` | **refused**: *CE 2026 Heat A is a competition game, so it cannot be deleted. Its results and records have to stay available after the event…* | `end-delete-competition-after-en.jpg`, `end-operator-log-refusals-en.jpg` |
| end-reset | Reset to Setup (reason) | **refused** — W-CE-26 fixed: *CE 2026 Heat A is a competition game, so it cannot be reset to setup. Its rounds, results and records have to stay as they were played. Archive the game instead…*; the game stayed `active` at round 5 with rounds 1–4 processed | `end-reset-modal-en.jpg`, `end-reset-after-en.jpg` |
| end-archive | Archive Game (reason) | accepted: *Game archived. You can now create a new game for this section.*; status `archived`, every result still readable | `end-archive-after-en.jpg`, `end-courses-after-archive-en.jpg` |

### Console and network, whole walkthrough (`harness/records_summary.py`)

31 recorded runs, **835 screens**, **5,707 API calls**, 412 driver checks passed / 62 failed / 44 observed.

* **Console errors (excluding the harness's aborted Google-Fonts requests):** 88, every one of them the browser's own line for a non-2xx response — 61 × 400, 25 × 409, **1 × 500** (W-CE2-01) and 1 × 404 (the harness's own probe of a route that does not exist, `GET /api/grades/`). **No JavaScript exception and no `pageerror` on any screen in either language.**
* **API responses ≥ 400:** 88, all accounted for: 40 analyst refusals (deliberate, shown, nothing charged), 21 × 409 `lifecycle_in_progress` (deliberate, shown, retried), 8 marketing 400s (W-CE-04's named refusal, driven), 6 cash refusals on the report purchase and the org switch (shown, correct), 2 delete 409s and 1 reset 409 (the refusals above), 1 advance-round 400 (W-CE-24), 1 deadline 409 (W-CE2-10), 1 harness 404 — and **the one 500, W-CE2-01**.
* **Leak scans:** no raw catalogue key, `undefined`, `NaN` or `[object Object]` on any screen in either language. `None` still appears as an English word in copy (*IP Exposure: None*). Storage field names reach a screen once: the Operator Log's row for the failed processing (W-CE2-04).
* **The 62 failed driver checks** are: 14 locks the server refused for cash or D/E (correct behaviour, W-CE2-02/03), 6 report purchases refused for cash (correct, shown), 5 rounds where M&A offered no enabled target, 10 harness locator limits on the marketing tab bar, 4 from the W-CE-04 probe before it became its own driver, 3 from the Operator Log check tripping on W-CE2-04's raw text, 3 from the round-2 failure and the lifecycle path (W-CE2-01, W-CE-24), 1 from W-CE2-10, and the rest first-run harness mismatches that later passed (the plant capacity row, the Chinese "每回合" wording, the `entry_status` key, the translated tab label).

---

## (d) New defects

Same severity scale as the first pass: **P0** data loss / cannot proceed /
wrong number shown to a player · **P1** wrong or missing behaviour ·
**P2** wording or cosmetic.

| id | screen | role | lang | what the user sees | what they should see | sev | repro | evidence |
|---|---|---|---|---|---|---|---|---|
| **W-CE2-01** | Game Control › Round control › Run post-round processing (and *Close & process now*) | instructor | EN, zh | A round a team played with **a plant built in the same market as an acquisition it completed** cannot be processed at all: the console shows *Post-round processing failed: Natural key ('team_id', 'market_id', 'construction_started_round') is not unique in section "team_plant" … appears twice* and the round stays `closed` / `processing_status FAILED`. The game cannot advance. `_process_plants` creates a `TeamPlant` for the build and `acquisitions.py` creates a second one for the target's included plant, both with the same (team, market, round), and the competition manifest snapshot refuses the round. Nothing on any screen can remove either decision, so the instructor has no way out of it | a round always processes; two plants in one market in one round are one plant, or the snapshot tolerates them | **P0** | a team builds a plant in its home market and acquires a target whose market is the same and `includes_plant` (here Aurora Devices: AFR plant + *AfriConnect Mobile*, AFR, in round 2), then close and process | `r2-04-processed-en.jpg`, `r2-12-operator-log-en.jpg`, `records/instructor-round2-force-en.json` (`observed.operator_log_rows`), `runtime/backend.log` (the traceback, `POST /api/games/1/round-control/process/ 500`), `harness/unstick_plant_collision.py` (the intervention that let the walkthrough go on) |
| **W-CE2-02** | Corporate Strategy › M&A, Market Strategy › plant / partnerships, Decision Summary | student | EN, zh | A queued acquisition, a plant build and a partnership can be **added but never removed**: the M&A card turns into *Queued*, the plant card into a status tag, and no screen offers a cancel. The *Acquire — $25.0M* button is offered although the team holds $23.4M, and when the team then opens Review & Submit the lock is refused: *Committed spend of $38,000,000.00 exceeds available cash of $25,446,310.88.* The team cannot clear the blocker it just created; all three teams ended rounds 3 and 4 unable to lock | a queued commitment can be withdrawn while the round is open (or an unaffordable one cannot be queued) | **P1** | queue an acquisition costing more than the team's cash, then open Review & Submit | `x-t1-r3-95-summary-en.jpg`, `p1-r3-62-corporate-ma-en.jpg`, `records/lock-t{1,2,3}-r{3,4}-*.json` |
| **W-CE2-03** | round close on the deadline | student, instructor | EN, zh | The cash check that refuses the lock is **not applied when the round closes on its deadline**: the team is deadline-locked with the draft it could not submit, and the engine executes the spend anyway. Aurora Devices closed round 3 with `strategy_expense $37.95M` against $23.4M of opening cash and **−$12,369,069.71 of cash**, having been told an hour earlier that it could not submit those decisions | the same rule at the deadline as at the lock: refuse the spend, or let the team submit it | **P1** | let a team with a refused lock be deadline-closed, then read its statement | `records/check-round3.json` (`Aurora Devices.statement_round`), `s-after-r4-10-financial-reports-en.jpg` |
| **W-CE2-04** | Instructor › Operator Log | instructor | EN, zh | The row for a refused action prints the server's internal error verbatim: *Refused: Post-round processing failed: Natural key ('team_id', 'market_id', 'construction_started_round') is not unique in section "team_plant": team_plant(team(game("CE 2026 Heat A")|"Aurora Devices")|…)|"2") appears twice. Declare a key that identifies a row, or set key=None to use a content key.* with `engine_failure` beside it — storage names, a Python argument and an instruction addressed to a developer | a sentence an operator can act on | P2 | make any processing fail; read the Operator Log | `r2-12-operator-log-en.jpg`, `records/instructor-round2-reprocess-en.json` (`leaks`: `field_name team_id`, `junk None`) |
| **W-CE2-05** | every server sentence a Chinese student reads | student | zh | A team's language is **its first enrolment's**, so a Chinese-speaking student whose team-mate enrolled first is answered in English however often they choose 中文. In round 1, team 3's Chinese player got *The research analyst is not part of this game…* in English; the same click returned Chinese only after the team's **first** member had also signed in in Chinese. On a mixed team the setting is unreachable for everyone but one member | the language of the student being answered (or a team language the console can set) | P1 | sign in as the second member of a team in zh-CN, ask the analyst | `p3-r1-83-research-analyst-asked-zh-CN.jpg` (English) vs `p3-r2-83-research-analyst-asked-zh-CN.jpg` (Chinese), `harness/dbq.py enrollments` (`s2609 en → zh-CN` between the two) |
| **W-CE2-06** | Products, Round Results, price-adjustment notices | student | zh | The market's **English name** on an otherwise Chinese screen: *Western Europe* (51 occurrences across the zh records) in the product table's Active Markets, in the results tabs and inside an otherwise Chinese sentence — *Western Europe 中的 IronClad Field：未输入价格…* — while the same market is 西欧 on the Market Strategy tabs and the marketing page | 西欧 everywhere | P2 | any zh-CN team with a market, Products or Round Results | `p3-r3-30-products-zh-CN.jpg`, `v-results-t3-r1-zh-CN.jpg` |
| **W-CE2-07** | Round Results › Strategic Scorecard | student | zh | English sentences written by the engine: *Conservative leverage. Strong financial position.*, *Spending within operating budget. Good fiscal discipline.* and the other six in `core/engine/coherence.py`, which are f-strings with no catalogue entry | the same sentences in the team's language | P2 | zh-CN team, Round Results → Strategic Scorecard | `s-after-r1-12-results-tab3-zh-CN.jpg`, `records/student-tour-t3-after-r1-zh-CN.json` `leaks` |
| **W-CE2-08** | Instructor › AI Coach | instructor | zh | The coach alerts are **always English**, whatever the console's language: 23 distinct sentences (*Classic short-term thinking trap…*, *Revenue decline in a growing market suggests competitive pressure…*). `get_instructor_language(game)` reads the game creator's `Enrollment`, and an instructor created from the console has none, so it always answers `en`; nothing the instructor can click changes it | the console's language, as W-CE-17 intended | P1 | zh-CN console → AI Coach after a processed round | `zh-r2-i29-ai-coach-zh-CN.jpg`, `harness/dbq.py enrollments` (no instructor row) |
| **W-CE2-09** | Decision Summary › Budget Summary | student | EN, zh | Two totals for what the round costs sit on one screen — *Over budget by $23.5M — total spending $28.5M exceeds available budget $5.0M* and *Committed spend of $38,000,000.00 exceeds available cash…* — and the line below them is unformatted: **Unallocated: $-12553689** (every other figure on the page is `$28.5M`-style). In round 2 the same line read *Unallocated: $13.5M* while the banner said the team was over budget | one total per concept; a formatted figure; no "unallocated" while the same panel says over budget | P2 | spend past the budget, open Review & Submit | `x-t1-r3-95-summary-en.jpg`, `x-t2-r4-95-summary-en.jpg` |
| **W-CE2-10** | Game Control › Round control, straight after *Activate Game* | instructor | EN, zh | The first round-control action after activating a game is **always refused**: *The game has moved to round 1; this request was for round 0. Refresh the console and repeat the action if it is still what you want.* The card still holds the pre-activation round because the console now stays on the tab (the W-CE-01 repair) and nothing re-reads the round. After a page refresh the same click works | the card reloads with the game; the action the instructor takes next works | P1 | new game → Activate Game → Round control › Set deadline, without reloading | `v-activate-deadline-no-refresh-en.jpg`, `v-activate-deadline-after-refresh-en.jpg`, `records/verify-post-activate-deadline-en.json` |

---

## (e) What could not be driven, and why

| item | why |
|---|---|
| **Round 2 could not be processed at all** without touching the database | W-CE2-01. The console's own controls (*Run post-round processing*, *Close & process now*, the lifecycle *Advance Round*) all end in the same 500, and no screen can remove either of the two decisions that collide. The walkthrough went on only after `harness/unstick_plant_collision.py` deleted the plant decision — disclosed here, and the reason the P0 is graded *cannot proceed*. |
| **Withdrawing a queued acquisition, plant or partnership** | W-CE2-02: there is no such control on any screen, so the teams that were refused a lock in rounds 3 and 4 could not be driven to a lockable state. Their rounds were resolved by the deadline, which is itself on record. |
| **A lock in rounds 3 and 4 for the three played teams** | the server refused it for cash and, in round 4, for the D/E ratio. That refusal is correct behaviour and it is shown on the page before the click (W-CE-25 fixed); it is listed here because "every team locks every round" was not achieved after round 2. |
| **Marking a competition heat from the console** | unchanged from the first pass: nothing in the frontend writes `SimulationInstance.settings['is_competition']`; `harness/mark_competition.py` does it (disclosed) so that the delete and reset refusals for a heat can be driven. |
| **Phase 2 narratives from a model** | by design of this stack: every LLM URL points at an unreachable port, so the round narrative and the memo evaluation use the template/heuristic fallback. The fallback path is what is on record. |
| **An answer from Ask the Analyst** | the scenario has no analyst, so only the refusal path exists — driven five times per team per round, with the quota untouched and nothing charged (which is what the brief asks to see). |
| **The AI Coach in Chinese** | W-CE2-08: the alerts are English whatever the console's language, so a Chinese reading of that panel could not be produced. |
| **Chinese glyphs** | no CJK font in the sandbox and no route to a font CDN; every zh-CN claim is about the rendered DOM text, not the pixels. |
| **8 teams actively playing** | three teams (1–2 EN, 3 zh-CN) played every round; teams 4–8 were deadline-closed with no decisions each round, which is a path worth having on record. |
| **Rounds 5–10** | four rounds were played end to end (the brief's minimum); the remaining six were not. |
| **The supply-chain decision pages** (Sourcing, Logistics, Trade Finance, Inventory) | opened and photographed in both languages, not edited: they are optional to the lock (W-CE-13) and outside the brief's list. |
| **A second processing attempt without the intervention** | not driven: one attempt failed with the 500 and the failure is deterministic in its cause (the two rows are created every time the round is processed), so the next action taken was the disclosed deletion, and the same *Run post-round processing* button then succeeded. Whether a bare retry would ever pass was not tested. |

---

## (f) Verdict, in plain language

**Is the platform playable end to end today? Almost — but not on its own.**
An instructor built a course, a section, an eight-team game, a roster and
every password from the console, set a home market by hand, activated the
game, scheduled it, injected an event, graded and overrode a grade, exported
three CSVs, and resolved four rounds; three teams, one of them playing in
Chinese, made every kind of decision — budget, a typed loan, dividends, a tax
structure, products, a retirement, marketing with out-of-band and blank
prices, a market entry, a $14.0M plant, a partnership, compliance investment,
talent and staff allocation, ESG, an organisation switch, an acquisition, a
board memo over and then under its word limit, a bought research report and
analyst questions that found nothing and charged nothing — and saw results,
statements and a leaderboard that agree with each other and with what they
decided. The server answered no 5xx except one, and no screen threw a
JavaScript error in either language.

**But one round could not be processed at all.** A team that built a plant in
the same market as an acquisition it completed made round 2 unprocessable:
every console control answered a 500, the round sat `closed / FAILED`, and no
screen could undo either decision. The walkthrough only continued because the
auditor deleted a row from the database. In a competition heat that is a heat
that stops, in front of the room, with no operator remedy. That alone is the
answer to the second question.

**Is it bug-free enough to play clean games? No, not yet.** The repairs held:
of the twenty-seven rows in the table, **twenty-three are verified fixed** on
the real screens — including both P0s, since a typed loan now stores what was
typed and the shareholder return reads −22.2 % instead of 999,966 %. Three of
those twenty-three carry a named residue or condition (W-CE-15 works only once
the team's *first* member states the language; W-CE-16 and W-CE-17 leave
English in the places listed above). **Three changed rather than disappeared**
(W-CE-18b, W-CE-23, W-CE-24) and **one is unchanged calibration** (W-CE-19,
deferred under R48).
Against that, ten new defects, one of them P0 and four P1: a round that cannot
be processed (W-CE2-01), commitments a team can make but never withdraw
(W-CE2-02), a deadline that executes the spend the lock refused and leaves a
team at −$12.4M (W-CE2-03), a Chinese player answered in English because a
team-mate enrolled first (W-CE2-05), coach alerts that are always English
(W-CE2-08), and a console whose first round-control action after activation is
always refused until the page is refreshed (W-CE2-10).

**What I would fix before the first clean game:** W-CE2-01 (a round must always
process), W-CE2-02 and W-CE2-03 together (a team must be able to undo what it
queued, and the deadline must apply the same rule as the lock), W-CE2-10 (the
console must work straight after Activate), and W-CE2-05 (the language a
student chooses must be the language they are answered in). W-CE-24 is the
last of the first pass's *cannot proceed* items still true: the lifecycle
*Advance Round* button promises a carry-forward and is refused. Everything
else on both lists is wording or cosmetic and can wait.

One thing the first walkthrough's verdict asked for is now true: **the
platform's numbers agree with each other**. Four rounds of results,
statements and leaderboards cross-checked clean on every line, in both
languages. What is not yet true is that a game can be relied on to finish.
