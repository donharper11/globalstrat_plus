# Full walkthrough — Consumer Electronics 2026, both roles, both languages

**Branch:** `walkthrough-ce-2026-09-22`, cut from `crv2-release-integration` at `83a50bb` (R48 recorded).
**Date:** 2026-09-22. **Auditor role:** find defects; nothing in `backend/` or `frontend/` was changed.
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-2026-09-22/` — `harness/` (every driver), `records/` (one JSON per driver run: steps, screens, API calls, refusals, console, leak scans), `screenshots/` (JPEG, `<screen>-<lang>.jpg`), `exports/` (CSV files the console produced).

> Sections: (a) stack recipe · (b) walkthrough log · (c) defects · (d) not driven · (e) verdict.

---

## (a) The stack, and the exact commands

Disposable, on this host, never the production database (192.168.50.38), never `/etc/globalstrat-plus.env`, LLM endpoints pointed at an unreachable port so Phase 2 uses the template fallback, backups to a scratch directory, `COMPETITION_REQUIRE_CLEAN_BUILD=false`. Container and ports are this pass's own (`globalstrat-walkthrough-ce-pg`, ephemeral host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build           # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-2026-09-22/harness
$H/make_db.sh                    # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py               # migrate + legacy tables, load_scenario --preset electronics, superuser, ONE instructor
python3 $H/start_stack.py        # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin; writes runtime/stack.ports
```
`seed.py` deliberately creates **nothing else**: the course, section, game, teams, roster, passwords and schedule were all made from the console by the instructor driver.

Drivers (Playwright / Chromium, `walk.py` is the shared recorder):

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. refused 6th member → team configuration → activate → schedule → deadline → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round) | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| `probe_loan_input.py` | typed vs pasted entry into the Loan Amount box | `probe_loan_input.py <team>` |
| `hold_lock.py` | holds the lifecycle lock so an autosave is refused for real | used by `student_play.py probe` |
| `apicall.py` | signed-in API probe for cross-checking a screen against the server | `apicall.py <user[:pw]> GET <path>` |

**Language:** set through the product's own mechanism (`localStorage.gs_language`, the same key the login-page switch writes). **No visual claim is made about Chinese glyphs**: this sandbox has no CJK font and no route to a font CDN, so zh-CN screenshots show missing-glyph boxes; the standard is the rendered DOM text (recorded per screen in the JSON), as in the CRV2-13 passes.

**Leak scan** on every screen (`walk.scan`): raw catalogue keys, storage field names, `undefined`, `NaN`, `[object Object]`, exception text; on zh-CN screens additionally runs of English words. Console errors and every API status ≥400 are captured per screen; the aborted Google-Fonts requests (`net::ERR_FAILED`) are the harness's and are excluded from the counts below.

---

## (b) Walkthrough log

_Filled from the records as each part completed; see the JSON for the per-screen API calls._

### Part 1 — instructor, English (`records/instructor-setup-en.json`, `instructor-bulk-reset-en.json`)

| # | screen | what happened | evidence |
|---|---|---|---|
| i00 | /instructor/login | signed in as `walk_instructor` | `i00-instructor-login-en.jpg` |
| i01–i03 | Courses & Sections | course `CE26`, section `CE26-A` created and selected (`POST /api/courses/`, `POST /api/sections/` 201) | `i02-…`, `i03-…` |
| i04–i05 | Step 1: Create a Game | scenario *Consumer Electronics 2026*, name `CE 2026 Heat A`, **8 teams**; toast `Game "CE 2026 Heat A" created with 8 teams.` | `i04-create-game-form-en.jpg`, `i05-game-created-en.jpg` |
| i06 | Bulk Upload (CSV) | `roster.csv` (27 rows) → 27 enrolled; **no on-screen confirmation** (toast/modal both empty) — W-CE-05 | `i06-roster-uploaded-en.jpg` |
| i07–i08 | Assign Students to Teams | 26 assigned by clicking `→ <team>`; the **6th member of Apex Devices refused**: modal *No students were assigned — Apex Devices already has 5 members, the maximum this section allows…* | `i07-sixth-member-refused-en.jpg`, `i08-…` |
| i09–i11 | Game Control › Team Configuration | Random home markets previewed, team 1 renamed *Aurora Devices*, saved (`PUT …/instructor/team-config/` 200) | `i10-…`, `i11-…` |
| i12 | Activate Game | popconfirm → active, round 1 open; **console jumped back to Courses & Sections** — W-CE-01 | `i12-game-activated-en.jpg` |
| i13 | Round Schedule › Quick Schedule | `Schedule saved for 10 round(s).` | `i13-round-schedule-en.jpg` |
| i14 | Round Control › Set deadline | modal names the game; `CE 2026 Heat A: deadline updated.`; **tab reset again** (W-CE-01) | `i14-set-deadline-modal-en.jpg`, `i14b-…` |
| i15–i16 | Extend Deadline | modal `Extend round deadline — CE 2026 Heat A`, +24 h → deadline moved 25→26 Sep | `i15-…`, `i16-…` |
| i17–i18 | Pause / Resume | `Game paused` / `Game resumed`; server agrees | `i17-paused-en.jpg`, `i18-resumed-en.jpg` |
| i19–i21 | Event Manager › Inject Event | *Major Competitor Product Launch (medium)*, no market → `Event injected`; the news ticker then shows `… in {market}` — W-CE-06 | `i20-…`, `i21-…` |
| i22 | Operator Log | 11 rows; *Before → after* column is raw JSON with storage names (`round_number`, `target_market: null`) — W-CE-07 | `i22-operator-log-en.jpg` |
| i23–i24 | Students & Logins | per-row *Reset to ID* → reveal modal; then *Set all to student ID* → 26 passwords issued (server: 27/27 `has_password`) | `i24-…`, `i24b-bulk-password-reset-en.jpg`, `records/student-accounts-after-bulk-reset.txt` |
| i25–i26 | Team Overview › View Decisions | drill-down shows tag `no_submission` next to *No submission* — W-CE-08 | `i26-team-decisions-drill-en.jpg` |
| i27–i30 | Grading & Export | default rubric created; *Calculate Grades* at round 0 → all 55.0 → 75.0; three CSV exports downloaded (`exports/`) | `i28-…`, `i29-…`, `i30-…` |
| i31–i34 | Briefings, Research Monitor, AI Coach, Supply Chain | rendered; Supply Chain panel is English-only by construction (see zh-CN) | `i31-…`…`i34-…` |

### Part 2 — students, round 1 (EN teams 1–2, zh-CN team 3)

Records: `student-tour-t1-pre-en.json` (every student screen before play), `student-play-t1-r1-en.json` (team 1, probe profile — the record of the final of three runs; the first two runs are why the harness has re-run guards), `student-play-t2-r1-en.json`, `student-play-t3-r1-zh-CN.json`. Screens `p<team>-r1-<nn>-<screen>-<lang>.jpg`.

| # | screen | what happened (team 1 unless said) | evidence |
|---|---|---|---|
| 00–01 | /login, first sign-in | `s2601`…`s2611` sign in with the issued password; onboarding modal *Your Global Challenge* shown once (Skip/Next) | `s-pre-00-login-en.jpg`, `s-pre-01-post-login-modal-en.jpg` |
| 10 | Dashboard, News, Research, Competitors, Tools, Financial Reports, Forecast, Team Activity, Results, Leaderboard, every decision page, Sourcing/Logistics/Trade Finance/Inventory | all render before play; Team Activity's data call is refused 403 (W-CE-09); the bell does nothing (W-CE-10); ticker shows `{market}` (W-CE-06) | `s-pre-10-*-en.jpg` |
| 10–12 | Finance › Budget Allocation | R&D 3,000,000 / Marketing 2,500,000 / Strategy 1,500,000 typed → stored exactly (`PATCH …/budget/` 200); then R&D 9,000,000 → red banner *Allocated budget … exceeds the Round 1 operating budget* and the over-allocation **is stored** (`rd_budget 9000000`) | `p1-r1-11-…`, `p1-r1-12-finance-over-allocated-en.jpg` |
| 13 | Finance › Capital Management | Loan Amount typed `5000000` → **$50 stored** (run 3; $5 in run 1) — W-CE-02; Dividend 0.5 stored; team 3 (pasted) stored 5,000,000 | `p1-r1-13-finance-capital-en.jpg`, `p3-r1-13-finance-capital-zh-CN.jpg` |
| 14–15 | Finance › Tax Structure | *Regional Hub Structure* card clicked → `POST …/context/tax-structure/` 200, current becomes `regional_hub` (in run 1 the auditor also switched team 1 through the API to prove the route; noted) | `p1-r1-15-finance-tax-switched-en.jpg` |
| 20–23 | R&D Investment | *Invest next level* refused by the server (W-CE-03); Create New R&D Platform modal filled, blocked *Over Budget $3.6M* (W-CE-19) | `p1-r1-21a-rd-upgrade-clicked-en.jpg`, `p1-r1-22-rd-create-platform-modal-en.jpg` |
| 30–34 | Product Portfolio | *Nova Aurora R1* created (mainstream, North America) → `product_creates`; last product's edit modal → *Retire at end of round* → `product_retires` | `p1-r1-31-…`, `p1-r1-33-products-edit-modal-en.jpg` |
| 40–44 | Marketing Mix | Nexus One: price 450 (band 315–585), 5,000 units, source market, focus tag, Mass Retail, promo 200,000 → stored; then **1,755** → red *Outside the allowed range… saved; adjusted at close*, stored 1755; Nexus Lite: price cleared → *No price set… priced at $154*, stored `null`. Run 2 exposed W-CE-04 | `p1-r1-41-…`, `p1-r1-42-marketing-out-of-band-en.jpg`, `p1-r1-43-marketing-blank-price-en.jpg` |
| 50–53 | Market Strategy | entry card clicked on a not-entered market → `market_entries` (`entry_mode 1`, $500,000); home market *Build Plant* → `plant_decisions`; *+ partnership* → `partnerships` ($2.0M/round); compliance investment not offered in round 1 (no foreign market entered yet) — driven in round 2 | `p1-r1-51-market-entry-en.jpg`, `p1-r1-52-market-home-en.jpg` |
| 60–66 | Corporate Strategy | Talent: R&D headcount 60, training 100,000 → context `draft`; Staff Allocation collapse → NA 5 / HQ 55 → `talent_allocations`; M&A: targets shown but every one *Available from Round 2/3* (no Acquire button in round 1); ESG 500,000 / 250,000 + *Board diversity* → `esg`; Organization: *Switch — $2.0M* modal → confirmed → `transitioning: true` | `p1-r1-61-…`, `p1-r1-62-corporate-ma-en.jpg`, `p1-r1-63-…`, `p1-r1-65-corporate-org-modal-en.jpg` |
| 70 | Stakeholder Communications | **no assignment in round 1** (`GET …/communications/assignments/` → `[]`); driven in round 2 | `p1-r1-70-communications-en.jpg` |
| 80–84 | Market Research | *Buy report — $50,000* → delivered (`research_expense 50,000` on the statement later); Ask the Analyst → refused visibly (*The research analyst is not part of this game… nothing was charged*), 5 refusals, quota untouched — in English on the zh screen (W-CE-15) | `p1-r1-81-…`, `p1-r1-83-research-analyst-asked-en.jpg`, `p1-r1-84-…` |
| 90–91 | Finance while an operator holds the game lock | Strategy budget edited → `409 lifecycle_in_progress` ×3 → banner *Your last change was not saved … will be sent again* with *Retry now*; lock released → retried → stored 1,750,000, banner gone | `p1-r1-90-autosave-refused-en.jpg`, `p1-r1-91-autosave-retried-en.jpg` |
| 95–97 | Decision Summary & Submit | notes typed; *Lock & Submit Decisions for Round 1* → *Confirm Submission* → status `locked`; team 2 and team 3 (zh: 确认提交 … 锁定决策) likewise | `p1-r1-96-lock-confirm-en.jpg`, `p3-r1-96-lock-confirm-zh-CN.jpg`, `p3-r1-97-locked-zh-CN.jpg` |

### Part 3 — round 1 resolved from the console, results checked (`records/instructor-round1-console-en.json`, `check-round1.json`, `student-tour-t1-after-r1-en.json`, `student-tour-t3-after-r1-zh-CN.json`)

| # | screen | what happened | evidence |
|---|---|---|---|
| r1-00–02 | Game Control › Round Control | 3 of 8 teams locked; *Close round now* popconfirm names the game → closed (5 teams deadline-locked, `teams_locked 8`) | `r1-01-close-confirm-en.jpg`, `r1-02-closed-en.jpg` |
| r1-03 | Reopen round modal | opened, wording on record, cancelled | `r1-03-reopen-modal-en.jpg` |
| r1-04 | Run post-round processing | processed in 3.7 s, `RESULTS_AVAILABLE`, `narrative_error ''` (template fallback, no model) | `r1-04-processed-en.jpg` |
| r1-05–09 | Team Overview, drill-down, Briefings, Research Monitor, AI Coach | rendered after processing | `r1-05-…`…`r1-09-…` |
| r1-10–12 | Advance to round 2 | popconfirm names the game → round 2 open; Operator Log lists close/process/advance | `r1-10-advance-confirm-en.jpg`, `r1-12-operator-log-en.jpg` |
| check | API cross-check (3 teams) | leaderboard ordered by index, ranks 1..8; results index == leaderboard index for each team; statement revenue == results revenue; *Research* and *Compliance investment* rows present (50,000 / 0) | `records/check-round1.json` |
| check | decided vs shown | 1,755 → **585 with the notice** *…adjusted to $585 when the round closed*; blank → **154 with the notice**; product performance rows show 585 / 154; retirement recorded | `s-after-r1-11-results-round1-en.jpg` (notice block) |
| s-after-r1 | every student screen again, EN and zh-CN, results tabs ×5 | **999966.5 %** shareholder return (W-CE-14); Financial Reports income statement R0/R1 with Research $50K, Compliance investment $0 | `s-after-r1-10-financial-reports-en.jpg`, `s-after-r1-12-results-tab*-en.jpg`, `…-zh-CN.jpg` |

### Part 4 — rounds 2–4

_Being filled as the rounds complete._

---

## (c) Defects

Severity: **P0** data loss / cannot proceed / wrong number shown to a player · **P1** wrong or missing behaviour · **P2** wording/cosmetic.

| id | screen | role | lang | what the user sees | what they should see | sev | repro | evidence |
|---|---|---|---|---|---|---|---|---|
| W-CE-01 | Instructor › Game Control | instructor | EN, zh | After *Activate Game*, *Save deadline*, *Extend Deadline*, *Run post-round processing* (anything that reloads the dashboard) the console **drops back to the Courses & Sections tab**; the instructor has to find Game Control again every time | stay on the tab the action was taken from | P1 | Game Control → Activate Game → OK | `i12-game-activated-en.jpg` (active tab is Courses), `records/instructor-setup-en.json` `observed.tab_after_activate`, `tab_after_set_deadline`, `tab_after_extend` |
| W-CE-02 | Finance › Capital Management | student | EN, zh | Typing `5000000` into **Loan Amount** key by key stores **$5** (slow cadence) or **$0** (fast); only a pasted value stores 5,000,000. The impact preview then shows *New total debt $5.0M* as if nothing was borrowed. Same control pattern on Repayment, Amount to Raise, Dividend | the number typed | **P0** | Finance → Capital Management → click Loan Amount → type 5000000 → Tab | `records/probe-loan-input-t1-en.json`, `probe-loan-typed-slowly-en.jpg` (`$ 6`), `p1-r1-13-finance-capital-en.jpg` (`$ 5`, stored `new_debt: 5.00`) |
| W-CE-03 | R&D Investment › Platform Upgrade | student | EN, zh | Five *Invest next level* buttons are offered (and the page's own guidance says *Upgrade an existing feature when a new platform is over budget*); **every click is refused**: *Feature-level R&D investment is no longer available…*, plus toast *R&D investment could not be saved.* With a $4.0M R&D budget and a $7.6M cheapest platform, a team has **no R&D action it can take** in round 1 | either a working upgrade or no button and no guidance pointing at it | P1 | R&D Investment → Invest next level | `p1-r1-21a-rd-upgrade-clicked-en.jpg`, `records/student-play-t1-r1-en.json` refused `PATCH …/rd/ 400` |
| W-CE-04 | Marketing Mix | student | EN, zh | One product-market row failing validation (no campaign focus) makes the **whole page's save fail**, and the notice *Choose one to three campaign focus features* does **not say which product**; it appears on the tab of a product whose focus IS set. The same notice is shown **twice** (global banner + page banner) | name the product/market; save the other rows | P1 | two products; clear the focus tags on one; edit the other | `p1-r1-43-marketing-blank-price-en.jpg` |
| W-CE-05 | Courses & Sections › Bulk Upload (CSV) | instructor | EN, zh | After choosing a CSV, **nothing is announced** (no toast, no modal); the roster table silently grows | a confirmation with counts (created/updated/errors) | P1 | upload `harness/roster.csv` | `i06-roster-uploaded-en.jpg`, `records/instructor-setup-en.json` `observed.roster_upload_*` |
| W-CE-06 | Student top bar news ticker | student | EN, zh | `…launched an aggressively priced Gen 2 product in {market}.` — an unfilled placeholder, after an operator event injected with no target market | the market name, or wording that needs none | P2 | Event Manager → Inject Event with *All markets* | `s-pre-10-dashboard-en.jpg` (ticker) |
| W-CE-07 | Instructor › Operator Log | instructor | EN, zh | *Before → after* column is raw JSON (`{"status":"open","round_number":1} → {"round_number":1,"target_market":null,…}`) | plain words | P2 | Operator Log tab | `i22-operator-log-en.jpg` |
| W-CE-08 | Instructor › Team Overview › View Decisions | instructor | EN, zh | status tag shows the raw value `no_submission` beside the translated *No submission* | one translated status | P2 | Team Overview → View Decisions (before a team saves) | `i26-team-decisions-drill-en.jpg` |
| W-CE-09 | Student › Team Activity | student | EN, zh | page calls `GET …/changes/?round_number=1` which answers **403 "This area is open to instructors only"**; the console logs the error on every visit | a student page must not call an instructor-only route (or the route must serve students) | P1 | Team Activity in the sidebar | `records/student-tour-t1-pre-en.json` refused |
| W-CE-10 | Student top bar | student | EN, zh | the bell icon is a **decorative button with no behaviour**; there is no notifications screen a student can reach | notifications, or no bell | P1 | click the bell | `s-pre-10-dashboard-en.jpg`; `components/design-system/TopBar.jsx` |
| W-CE-11 | Student shell | student | zh | there is **no language switch inside the game**; a student can only change language on the login page (`LanguageSwitcher` is rendered by `LoginPage` only) | a switch in the top bar | P2 | log in, look for EN/中文 | `TopBar.jsx` |
| W-CE-12 | Grading & Export | instructor | EN, zh | the grading **override** (`POST /grades/override/`, `api/instructor.js: overrideGrade`) has **no control on the console** | an override control per team/category | P1 | Grading & Export tab | no screen exists |
| W-CE-13 | Decision Summary & Submit | student | EN | Sourcing / Logistics / Trade Finance / Inventory are listed with *Fix in …* and *Open Sourcing to complete this requirement* although they are **not required to lock** (only budget, products, marketing, strategy are) | mark them optional | P2 | Review & Submit before any decision | `s-pre-10-d-summary-en.jpg` |

| W-CE-14 | Round Results › Performance Overview | student | EN, zh | **SHAREHOLDER RETURN 999966.5%** after round 1 (API `shareholder_return_cumulative: 9999.665`), for a team whose share price and dividend are ordinary ($45, $0.50/share) | a return in the tens of percent at most, or blank with a reason | **P0** | play round 1, resolve, open Round Results | `s-after-r1-11-results-round1-en.jpg`, `records/check-round1.json` (`teams.Aurora Devices.financials`) |
| W-CE-15 | Market Research › Ask the Analyst | student | zh | the refusal *The research analyst is not part of this game, so your question was not asked and nothing was charged.* is shown **in English** on the Chinese screen (server `error` string, not localised) | the same sentence in Chinese | P1 | zh-CN, Ask the Analyst → Ask | `p3-r1-83-research-analyst-asked-zh-CN.jpg`, `records/student-play-t3-r1-zh-CN.json` refused |
| W-CE-16 | Student screens in zh-CN | student | zh | English copy on Chinese screens (28 distinct strings on the round-1 screens, `harness/leak_summary.py`): the whole R&D guidance box (*Choose one R&D action for this round… Upgrade an existing feature when a new platform is over budget*), *Invest next level* ×5, *previous round net profit / base allocation*, Finance *Budget saved / Financing saved / Enter dollar amounts directly / budget remaining*, *Cost exceeds R&D budget*, M&A *Available from Round N / Requires presence in …*, research *Slow growth / Moderate growth*, Summary *This requirement has draft work saved / Complete / Not started / Fix in … / Open Sourcing to complete this requirement / Sourcing / Logistics / Trade Finance / Inventory*, tax cards *Setup: $2.0M / Granite / GreenHorizon / Regulators*, the **news ticker event text** and every headline on Industry News (*Holiday season approaching*, *Import costs rising for US-based firms*…; the scenario's news and the injected event's narrative are English only), the dashboard's *Strategic Signals* and *NEXT REQUIRED ACTION* copy, and the login page's *Built for Real Work / Just Coursework* | Chinese | P1 | any zh-CN student session | `p3-r1-*-zh-CN.jpg`, `s-after-r1-10-news-zh-CN.jpg`, `records/student-play-t3-r1-zh-CN.json` and `student-tour-t3-after-r1-zh-CN.json` `leaks` |
| W-CE-17 | Instructor console in zh-CN | instructor | zh | English on the Chinese console: tab **Students & Logins**; Game Control statistic titles **Decision round / Round status / Game status** and their values (*Open for student decisions*, *active*); the *Monitoring … Decision round 1 of 10 is open…* banner; Extend modal unit *hours*; the whole Supply Chain panel; drill-down *Submission audit evidence* table; roster *CSV format: …* hint, *student(s)*, *teams · students assigned*; rubric editor placeholders; exported CSV headers | Chinese | P1 | zh-CN instructor session, Game Control | `zh-r2-i10-game-control-zh-CN.jpg`, `records/instructor-tour-zh-r2-zh-CN.json` `leaks` |
| W-CE-18 | Finance › Budget / Summary › Budget Summary | student | EN, zh | the **Strategy** bar shows spend against budget (*$3.3M / $1.5M* in purple) but no message says the team is over budget, and the round closed with `strategy_expense` **$9.55M** charged — the bar during the round and the statement afterwards do not agree | one consistent figure, and an over-budget warning where one exists for R&D/Marketing | P1 | Corporate/Market Strategy spending, then Review & Submit, then the income statement after close | `p3-r1-95-summary-zh-CN.jpg` (bar), `records/check-round1.json` (`strategy_expense`) |
| W-CE-20 | Instructor › Team Overview › View Decisions | instructor | EN, zh | the drill-down opens on a *Submission audit evidence* table whose rows are ~270 px tall and whose columns (Request ID, Payload SHA-256, raw JSON Payload) overflow the 800 px modal; the team's actual decisions (budget, R&D, marketing, financing, ESG, talent) are below the fold after dozens of audit rows | the decisions first; the audit trail collapsed or on a tab | P2 | Team Overview → View Decisions on a team that saved many times | `r1-06-decision-drill-en.jpg`, `records/instructor-round1-console-en.json` `observed.drill_modal` |
| W-CE-19 | R&D Investment › Create New R&D Platform | student | EN, zh | with the scenario's round-1 R&D budget ($4.0M) the cheapest platform costs $7.6M; the modal shows *Over Budget: $3.6M* and *Required: Cost exceeds R&D budget* and cannot be submitted; together with W-CE-03 no team can make any R&D decision in round 1 and the checklist keeps *R&D Investment: Not started* | either an affordable action or guidance that says R&D starts later | P1 (calibration-adjacent, recorded per R48 as a behaviour a player feels) | R&D Investment → Create New R&D Platform | `p1-r1-22-rd-create-platform-modal-en.jpg` |

---

## (d) What could not be driven, and why

| item | why |
|---|---|
| **Grading override** (calculate ✓, override ✗) | there is no override control on the console; the API (`POST /grades/override/`) exists and `api/instructor.js` exports `overrideGrade`, but no page calls it — W-CE-12. Not driven through the API either: the walkthrough is of what a user can reach. |
| **Notifications** (student) | the top-bar bell is a button with no handler and there is no notifications route — W-CE-10. Nothing to open. |
| **Marking a competition heat from the console** | nothing in the frontend writes `SimulationInstance.settings['is_competition']`; the heat was marked with `harness/mark_competition.py` (a direct row update, disclosed) so that the delete refusal for a competition heat could be driven. Before that, delete was driven on the same game and refused for the other reason (it has a record). |
| **Phase 2 narratives from a model** | by design of this stack: every LLM URL points at an unreachable port, so the round narrative and the memo evaluation use the template/heuristic fallback (*Automated evaluation unavailable. Score based on submission completeness*). The fallback path is what is on record; the model path is not. |
| **Ask the Analyst — an answer** | the scenario as loaded has no analyst (`The research analyst is not part of this game…`); only the refusal path could be driven (and it was, five times, quota untouched). |
| **Compliance investment in round 1** | the control lives on a foreign market's Market Operations card and only after entry is processed; driven in round 2 (250,000 stored) instead. |
| **Acquisition in round 1** | every target is *Available from Round 2/3*; queued in round 2 (target 2, $18.0M). |
| **Stakeholder communication in round 1** | the scenario issues its first assignment in round 2 (*Board Memo: International Expansion Strategy*, 300 words); the over-limit and submit paths were driven there. |
| **Tax structure switch in zh-CN** | driven and proven in English (`direct → regional_hub` from the card, plus an API probe); in the zh-CN run the driver could not match the card by the English structure names the API returns and did not click — a harness limitation, recorded as not verified in zh-CN rather than as a defect. |
| **Chinese glyphs** | no CJK font in the sandbox and no network to fetch one; every zh-CN claim is about the rendered DOM text, not the pixels. |
| **8 teams actively playing** | three teams (1–2 EN, 3 zh-CN) played every round; teams 4–8 were deadline-locked with no decisions each round, which is itself a path worth having on record (*Never submitted*, index drifting down). |
| **Round 5–10** | four rounds were played end to end (the brief's minimum); the remaining six were not. |
| **Supply-chain decision pages** (Sourcing, Logistics, Trade Finance, Inventory) | opened and photographed in both languages, not edited: they are outside this scenario's decision checklist for locking and outside the brief's list; the Summary page's claim that they are required is W-CE-13. |

---

## (e) Verdict

_Pending._
