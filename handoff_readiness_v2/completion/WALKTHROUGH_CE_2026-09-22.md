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

_Pending — being filled._

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

_zh-CN findings and the round-resolution findings are added below as the runs complete._

---

## (d) What could not be driven, and why

_Pending._

---

## (e) Verdict

_Pending._
