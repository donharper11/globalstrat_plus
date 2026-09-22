# Walkthrough CE 2026-09-22 — instructor console repairs

**Branch:** `walk-ce-console`, cut from `crv2-release-integration` at `4756ffc`
(contains `4b152f8` and `WALKTHROUGH_CE_2026-09-22.md`; verified).
**Date:** 2026-09-22. **Under:** R48 (bugs first; calibration deferred; no new
rules), `EXECUTION_PROTOCOL.md`, `STANDING-DISCIPLINE.md`.
**Scope:** W-CE-01, 05, 07, 12, 24, 26 (instructor console), W-CE-09, 10
(student shell). Every defect was reproduced first through the real route or
the real component (red), then repaired, then shown green. No rule a player
can feel was changed. No route was added, removed or re-guarded (`dump_route_inventory --check`
and `dump_read_inventory --check`: current).

> Sections: 1 commits · 2 per defect · 3 zh-CN sentences · 4 commands and results ·
> 5 proposed register text · 6 what still needs someone else · 7 preflight answers.

---

## 1. Commits

| commit | defect | what |
|---|---|---|
| `263afb8` | W-CE-26 | Reset to Setup refused on a competition heat and once a round is processed |
| `49d0447` | W-CE-24 | Lifecycle "Advance Round" asks for a written reason when teams are pending |
| `457bfd6` | W-CE-01 | The console stays on its tab when a Game Control action reloads the dashboard |
| `93ede85` | W-CE-05 | A roster CSV upload's outcome stays on the roster panel until dismissed |
| `125bc9a` | W-CE-07 | Operator Log before/after as labelled fields, not JSON |
| `417bf93` | W-CE-12 | Grading override control on the Team Grades table |
| `4926081` | W-CE-09 | Student Team Activity page, route and sidebar entry removed |
| `9bde205` | W-CE-10 | Student top-bar bell removed; remaining buttons named |
| `94f1bd9` | W-CE-24 | Test-floor adjustment: the advance refusal reading moved with its control |
| *(last)* | — | Regenerated string inventory, alone |

No push, no merge. `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md`, the
`OWNER_RULINGS` and `INTEGRATOR_DECISIONS` files were not edited.

---

## 2. Per defect

### W-CE-26 (P1) — Reset to Setup accepted on a competition heat with four processed rounds

**Reproduction (red), through the route.** `GameResetBoundaryTests` in
`backend/core/tests/test_operator_route_ownership.py` builds a game with round 1
`processed` and round 2 `open`, marks it a heat the way the walkthrough did
(`SimulationInstance.settings['is_competition']`), and posts
`/api/games/<id>/reset/` with a written reason. At `4756ffc`:

```
200 {'game_id': 1, 'status': 'setup', 'current_round': 0, 'rounds_reset': 1, 'request_id': 'srv-…'}
  -> left {'status': 'setup', 'current_round': 0, 'rounds': [(1, 'processed'), (2, 'pending')]}
```

— the same state the walkthrough recorded (`records/instructor-endgame-en.json`,
`observed.game_after_reset`): the game believes it has not started while round 1
is still processed and its results are still served. The same 200 for an
ordinary (non-heat) course game with a processed round. 5 of 7 tests red.

**Cause.** `GameResetView` (`backend/core/views/scenario_views.py`) checked only
the reason. What it undoes is narrow — `open` rounds back to `pending`, the game
to round 0 — and it cannot undo a processed round: the results, the leaderboard
rows and the audit record are permanent (PROTECT keys, append-only tables). No
consistent reset exists to wire: `reset_simulation` is a whole-database
management command withheld from competition stacks, not a per-game reset.

**Repair (refusing option, as instructed).** Inside the lifecycle boundary,
before the reason is read, mirroring `GameDeleteView`:

* a competition heat → 409 `competition_game_not_resettable`
  (`cohort_messages`, bilingual, guidance `archive_instead`);
* any game with a processed round → 409 `reset_round_processed`
  (`operator_messages`, bilingual, names the game and the first processed
  round, guidance: archive and create a new game).

Both are audited as rejected `reset_game` operator events with the request id
the operator was shown. A game that was activated by mistake and has not
resolved a round is still reset, exactly as before (`rounds_reset`, reason
kept). Both codes were added to `COHORT_BILINGUAL_CODES` / the catalogue, to the
console allowlist `bilingualServerReason.js` (so the console shows the sentence
verbatim with its guidance; the reset buttons already use `serverReason`), and
`competition_game_not_resettable` to the zh-terminology allowlist of sentences
that may say 竞赛.

**Green.** 7/7 `GameResetBoundaryTests`; 129/129 across
`test_operator_route_ownership`, `test_operator_refusal_language`,
`test_zh_terminology`, `test_console_defects`; 112/112 `test_operator_concurrency`
+ `test_audit_integrity` + `test_reset_simulation_withheld` +
`test_refusal_audit_integrity`.

**Left as observed, not changed.** A reset of an unprocessed game returns only
`open` rounds to pending; a `closed`-but-unprocessed round and any locked
submissions are left as they are (pre-existing; not in the defect).

### W-CE-24 (P1) — lifecycle "Advance Round" refused `reason_required` whenever teams are pending

**Reproduction (red).** `AdvanceRoundControl.test.js`: the API wrapper
`advanceRound(7, true, 'reason')` posted `{force: true}` and dropped the reason;
the dashboard source had the bare Cancel/OK modal (`advanceModalOpen`,
`await advanceRound(gameId, force)`). 4 of 5 red at head. The server side is
exactly what the walkthrough recorded (`records/advance-round-legacy-refusal.txt`):
`force: true` without a reason is `400 reason_required`.

**Cause.** The legacy one-step route treats `force` as an override and calls
`require_reason()`; the console sent the flag with no box to write a reason in,
so the one button on the card that said "advance" could not advance a round with
pending teams at all.

**Repair.** `components/instructor/AdvanceRoundControl.js`: with teams pending,
the `ReasonedAction` pattern (reason of 10+ characters before the request is
sent, `force: true` + `reason`), named for the game like every other lifecycle
confirmation; with every team locked, a plain confirmation (`force: false`,
the server asks for no reason then). A refusal is shown in the server's own
words with its guidance (`serverReason`), not "Failed to advance round".
`advanceRound(gameId, force, reason)` carries the reason. The old modal, its
state and `handleAdvance` are gone from the dashboard. Keys added:
`instructor.advance_round_named`, `instructor.advance_now`.

**Green.** 5/5 `AdvanceRoundControl.test.js` (wrapper; source; pending → reason
required, request body; refusal shown verbatim in Chinese with guidance; locked →
plain confirm, `{force:false, reason:''}`). The dashboard's `serverReason(err) || t(`
floor in `bilingualServerReason.test.js` went 19 → 18 because the reading moved
with the control (commit `94f1bd9`).

### W-CE-01 (P1) — every Game Control action threw the console back to Courses & Sections

**Reproduction (red), through the real component.**
`instructorDashboardTabs.test.js` renders `InstructorDashboard` with the API
client mocked by URL and the dashboard fetch answered on a later task (a real
server never answers in the click's microtask; React 18 batches everything
before the next task, so an instantly-resolved mock hides the loading render —
the first draft of this harness passed at head for that reason and was
corrected). It opens Game Control, drives the real Activate Game popconfirm,
waits for the reload. At `4756ffc`: `aria-selected="true"` on
`instructor.courses_sections`, and the Game Control pane (Pause Game) is not
in the document — the walkthrough's `tab_after_activate` / `tab_after_set_deadline`
/ `tab_after_extend` = "Courses & Sections".

**Cause.** `loadData()` sets `loading`; the component returned a bare spinner
while loading (`if (loading && gameId) return …`), unmounting the whole
`<Tabs>`; the Tabs were uncontrolled (`defaultActiveKey="courses"`), so the
remount forgot the tab. Not a navigation, not a state reset: an unmount.

**Repair.** The active tab is component state (`activeTab`, controlled
`activeKey` / `onChange`); the full-page spinner is for the first load of a
game only (`loading && gameId && !dashboard`), so a reload keeps the console on
screen and the cards refresh in place; a tab that has gone (game-specific tabs
after a reset or delete) falls back to Courses & Sections rather than to
nothing. The lazy loads on `onTabClick` are unchanged.

**Green.** 1/1; the same harness is reused for W-CE-05.

### W-CE-05 (P1) — roster CSV upload announces nothing

**Reproduction (red).** `instructorDashboardRoster.test.js` renders the real
dashboard with the real catalogue (`import '../i18n'`), selects the course and
section, opens Bulk Upload (CSV), uploads a roster and waits for `POST /roster/`.
At `4756ffc` the helper's toast *"Added 27 student(s) to the roster."* IS
emitted — the D6 helper was wired at both call sites (`rosterUploadCallSites.test.js`
was already green) — and there is nothing else: no element carries the outcome.
Red on `roster-upload-outcome`.

**Cause.** A clean upload's only announcement was `message.success`, antd's
three-second toast. The walkthrough's driver looked 4 s after choosing the file
(`instructor_setup.py`: `wait_for_timeout(4000)` then `modal_text`, then
`toast`) — by then the toast was gone and the table had grown silently, which
is what an instructor who looks away for three seconds sees too.

**Repair.** `rosterUploadSummary(outcome, t)` in `rosterUploadOutcome.js` gives
the toast, the refusal modal's title and a standing `<Alert>` on the roster
panel one sentence (type success/warning; file name; for a partial upload the
accepted/refused counts), kept until dismissed and cleared when the section
changes. Both call sites set it; the refusal modal listing rows is unchanged.
No new keys: the existing `roster_upload_*` sentences are reused.

**Green.** 2/2 (clean: the notice is on the panel four seconds later; partial:
"3 row(s) accepted, 1 refused" + "Accepted: 2 student(s) added, 1 already on
the roster."); `rosterUploadCallSites`, `rosterUploadOutcome`,
`instructorDashboardMessages` green (36/36 together). jsdom cannot animate the
toast away, so its removal is not asserted; its three-second life is antd's
documented default.

### W-CE-07 (P2) — raw JSON in the Operator Log

**Reproduction (red).** `OperatorEventsPanel.test.js` renders the panel with
three recorded events (activate, inject, a refused delete). At head the
"Before → after" cell was
`{"status":"open","round_number":1} → {"event_template":"Major Competitor Product Launch","round_number":1,"target_market":null}`
(storage names, `null`, braces) — the walkthrough's `i22-operator-log-en.jpg`.

**Cause.** The column rendered `JSON.stringify(row.before) → JSON.stringify(row.after)`.

**Repair.** `components/instructor/operatorChange.js`: `changedFields` lists the
fields whose value differs (a field only `after` has is a fact the action
added; a null added is nothing; a list — schedule rounds, team table — is
compared entry by entry); `fieldLabel` maps each storage key to a literal
catalogue key (humanised name as the fallback, never a computed key);
`formatValue` renders round/game/processing/participation statuses,
closed-by, dates and booleans in the instructor's language and hides
console-internal values (`seconds_remaining`, `next_action`, ids…). A committed
event reads `Status: in setup → active`, `Current round: 0 → 1`; a refused one
reads `Refused: <the recorded reason>` with its code. The raw record is one
click away, copyable, because the dispute runbook reads it. 32 keys added
(`instructor.oplog_*`), the game-status words copied from the backend's
`GAME_STATUS_LABELS` so the two never disagree.

**Green.** 6/6; `consolePanelsLanguage` 11/11.

### W-CE-12 (P1) — grading override has no console control

**Reproduction (red).** `GradeOverrideControl.test.js`: the dashboard source
carries no `<GradeOverrideControl`; `clearGradeOverride` did not exist. The API
(`POST`/`DELETE /grades/override/`, `OverrideGradeView`) takes `instance_id`,
`team_id`, `category_id`, `override_score`, `comments`; the TeamGrade row keeps
`override_score`, `computed_score`, `instructor_comments`, `graded_by`,
`updated_at` — that row is the audit; there is no separate operator event for
grading (it is outside the lifecycle boundary and was left there).

**Repair.** `components/instructor/GradeOverrideControl.js`, one control per
team row of the Team Grades table: category (preselected to the first),
override score 0–100 (the field clamps; nothing is sent without a score),
the reason kept with the grade (`comments`), Save, and Clear override when the
category is overridden. After either, grades are recalculated
(`calculateGrades` keeps overrides and re-stretches the final grade across
every team; the R40 refusal handling was extracted into `runCalculateGrades`
and reused). An overridden category is tagged *Overridden* with the computed
score and the reason in a tooltip. Refusals show the server's bilingual
sentence (`grading_override_incomplete` is in the catalogue). `clearGradeOverride`
added to `api/instructor.js` (DELETE body via `data`). 13 keys added
(`instructor.grade_override*`, `grade_overridden`, `grade_computed_was`).

**Green.** 5/5.

### W-CE-09 (P1) — student Team Activity page 403 on every visit

**Reproduction (red).** `studentInstructorOnlyRoutes.test.js`: `pages/TeamActivityPage.js`
called `getTeamChanges` → `GET /games/<g>/teams/<t>/changes/`, `IsInstructor`
since V2-035 (`core/views/instructor_alerts.py`), refused 403 "This area is
open to instructors only" — the walkthrough's `student-tour-t1-pre-en.json`
`refused`.

**What it was meant to show.** `DecisionChangeLog` rows: "who on my team
updated which decision page this round" (written by `core/views/decisions.py`
on every decision save). V2-106 had already found the same route polled by
`TeamActivityBanner` and stopped that poll for students ("the guard is working
correctly and nothing leaks"); the page itself stayed in the sidebar. There is
no student route for the change log.

**Repair (remove, not re-guard).** The page, its route in `App.js` and its
sidebar entry (with the `faBell` import) are removed; nothing else referenced
it. The change log is still written on every save and still readable by an
instructor through the instructor-only route. A source scan keeps any student
page from calling the route again and pins `TeamActivityBanner` as the only
caller, asking first whether it may. Opening a student route for a team's own
change log would be a permission change to a hardened route; it is listed in
§6 for a decision rather than made here. Catalogue keys `nav.team_activity` /
`common.team_activity…` are left in place (unused; other builders are editing
the locale files).

**Green.** 3/3; `TeamActivityBanner.test.js`, `App.test.js` green.

### W-CE-10 (P1) — the notifications bell is decorative

**Reproduction (red).** `design-system/TopBar.test.js` renders `DSTopBar` with
the contexts mocked: two buttons with neither title, label nor text — the bell
(no `onClick`, nothing feeds it: no notifications API serves a student, the
instructor alerts are `IsInstructor`) and the menu toggle (a handler, no name).

**Repair (remove, not build).** The bell and its icon import are gone; the
toggle and log-out buttons carry `title`/`aria-label` in both languages
(`topbar.menu` added). No notification subsystem was built.

**Green.** 1/1.

---

## 3. New zh-CN sentences

| where | key | zh-CN | en |
|---|---|---|---|
| `cohort_messages.py` | `competition_game_not_resettable` | {game} 是竞赛场次，因此无法重置为初始设置。其回合、成绩和记录须保持原样。 | {game} is a competition game, so it cannot be reset to setup. Its rounds, results and records have to stay as they were played. |
| `operator_messages.py` | `reset_round_processed` | 游戏“{game}”的第 {round} 回合已结算，因此无法重置为初始设置。该回合的结果和记录为永久保存。 | Round {round} of "{game}" has already been processed, so the game cannot be reset to setup. The results and the record of that round are permanent. |
| `operator_messages.py` | `reset_round_processed_guidance` | 请改为归档该游戏，然后为该班级创建新的游戏。 | Archive the game instead, then create a new game for this section. |
| `zh-CN.json` instructor | `advance_round_named` | 推进回合 — {{game}} | Advance round — {{game}} |
| | `advance_now` | 推进 | Advance |
| | `oplog_current_round` | 当前回合 | Current round |
| | `oplog_target_market` | 目标市场 | Target market |
| | `oplog_rounds_reset` | 退回“尚未开放”的回合数 | Rounds returned to not yet open |
| | `oplog_reopened` | 回合已重新开放 | Round reopened |
| | `oplog_submissions_unlocked` | 已解锁的提交数 | Submissions unlocked |
| | `oplog_opened_at` / `oplog_closed_at` / `oplog_processed_at` | 开放时间 / 关闭时间 / 结算时间 | Opened at / Closed at / Processed at |
| | `oplog_close_reason` | 关闭方式 | Closed by |
| | `oplog_processing_status` | 结算状态 | Processing |
| | `oplog_teams_total` / `oplog_teams_locked` / `oplog_teams_pending` | 游戏中的团队数 / 已锁定的团队数 / 待锁定的团队数 | Teams in the game / Teams locked / Teams pending |
| | `oplog_schedule` | 回合时间表 | Round schedule |
| | `oplog_participation_status` | 参与状态 | Participation |
| | `oplog_withdrawn_at` / `oplog_withdrawal_reason` | 停用时间 / 停用原因 | Withdrawn at / Withdrawal reason |
| | `oplog_locked_at` / `oplog_locked_by` | 锁定时间 / 锁定人 | Locked at / Locked by |
| | `oplog_hours` | 小时数 | Hours |
| | `oplog_round_n` | 第 {{round}} 回合 | Round {{round}} |
| | `oplog_game_status_setup/active/paused/completed/archived` | 设置中 / 进行中 / 已暂停 / 已结束 / 已归档 (= backend `GAME_STATUS_LABELS`) | in setup / active / paused / completed / archived |
| | `oplog_participation_active/withdrawn` | 处于参与状态 / 已停用 (= backend `PARTICIPATION_STATUS_LABELS`) | active / withdrawn |
| | `oplog_no_change` | 没有字段发生变化 | No fields changed |
| | `oplog_refused_because` | 已拒绝： | Refused: |
| | `oplog_copy_record` | 复制原始记录 | Copy the raw record |
| | `grade_override` | 覆盖 | Override |
| | `grade_override_title` | 覆盖类别得分 — {{team}} | Override a category score — {{team}} |
| | `grade_override_hint` | 覆盖分将取代该类别的计算得分，并与成绩及您的理由一同保存。所有团队的最终成绩将重新计算。 | The override replaces the computed score for one category and is kept with the grade, with your reason. The final grades of every team are recalculated. |
| | `grade_override_score` | 覆盖分（0–100） | Override score (0–100) |
| | `grade_override_comments` | 覆盖理由 | Reason for the override |
| | `grade_override_save` / `grade_override_clear` | 保存覆盖分 / 清除覆盖分 | Save override / Clear override |
| | `grade_override_saved` | {{team}}：{{category}} 的得分已覆盖。 | {{team}}: {{category}} score overridden. |
| | `grade_override_cleared` | {{team}}：已清除 {{category}} 的覆盖分。 | {{team}}: override on {{category}} cleared. |
| | `grade_override_failed` | 覆盖分未保存。 | The override was not saved. |
| | `grade_overridden` | 已覆盖 | Overridden |
| | `grade_computed_was` | 计算得分：{{score}} | Computed: {{score}} |
| `zh-CN.json` topbar | `menu` | 菜单 | Menu |

Terminology per `test_zh_terminology` (游戏 / 回合 / 团队 / 教师; 竞赛 only in the
one sentence about a competition, allow-listed). Every added key exists in both
catalogues with identical placeholders (`check-participant-strings` A6/A8: PASS).

---

## 4. Commands and results

All backend runs through `scripts/test-postgres` (disposable Postgres in
Docker) under `flock -w 1800 /tmp/globalstrat-backend-test.lock`; other
builders held the lock at times and the wait was always honoured. The
production host (192.168.50.38) and `/etc/globalstrat-plus.env` were never
read. Frontend runs from `frontend/globalstrat-frontend` with `node_modules`
linked from the main checkout (git-ignored).

| # | command | result | wall |
|---|---|---|---|
| 1 | `test-postgres …GameResetBoundaryTests` at `4756ffc` (red) | 5 F of 7: `200 != 409`, state left `setup / 0 / [(1,'processed'),(2,'pending')]` | 20 s |
| 2 | `test-postgres test_operator_route_ownership test_operator_refusal_language test_zh_terminology test_console_defects` | **129 OK** | 30 s |
| 3 | `test-postgres test_operator_concurrency test_audit_integrity test_reset_simulation_withheld test_refusal_audit_integrity` (background) | **112 OK**, 217.7 s | 4 min |
| 4 | Jest `bilingualServerReason`, `reasonedActions` | 27 OK | 2 s |
| 5 | Jest `AdvanceRoundControl.test.js` at head (red) | 4 F of 5 | 3 s |
| 6 | Jest `AdvanceRoundControl`, `reasonedActions`, `instructorDashboardMessages` | 19 OK | 3 s |
| 7 | Jest `instructorDashboardTabs.test.js` at head, instant mock | 1 OK — harness corrected (see W-CE-01) | 4 s |
| 8 | Jest `instructorDashboardTabs.test.js` at head, next-task mock (red) | 1 F: Courses & Sections selected, Pause Game absent | 3 s |
| 9 | Jest `instructorDashboardTabs.test.js` | 1 OK | 4 s |
| 10 | Jest `instructorDashboardRoster.test.js` at head (red) | 2 F: no `roster-upload-outcome` (the toast text was present) | 3 s |
| 11 | Jest roster harness + `rosterUploadCallSites` + `rosterUploadOutcome` + `instructorDashboardMessages` | 36 OK | 8 s |
| 12 | Jest `OperatorEventsPanel.test.js` with the pure module, panel unchanged (red) | 2 F of 6: cell is the JSON string | 3 s |
| 13 | Jest `OperatorEventsPanel` + `consolePanelsLanguage` | 17 OK | 3 s |
| 14 | Jest `GradeOverrideControl.test.js` at head (red) | 4 F of 5: no control in the dashboard, `clearGradeOverride is not a function` | 3 s |
| 15 | Jest `GradeOverrideControl`, `instructorDashboardMessages`, `consolePanelsLanguage`, `AdvanceRoundControl` | 31 OK | 4 s |
| 16 | Jest `studentInstructorOnlyRoutes`, `design-system/TopBar` at head (red) | 4 F of 4 | 3 s |
| 17 | Jest the two + `TeamActivityBanner` + `App` | 8 OK | 4 s |
| 18 | `CI=true npx react-scripts test --watchAll=false` (full, first) | 36 of 37 suites; 1 F: the `serverReason` floor (19 → 18, the reading moved) | 90 s |
| 19 | `CI=true npx react-scripts test --watchAll=false` (full, after `94f1bd9`) | **37 suites / 346 tests OK**, exit 0 | 90 s |
| 20 | `python3 backend/scripts/check-participant-strings` / `-selftest` | PASS 5348 units, 0 findings / 34 ok | 3 s |
| 21 | `CI=false BUILD_PATH=<scratch> npx react-scripts build`; `node eslint-warning-count.js` | Compiled with warnings; **54 (baseline 57)**, none in a file this branch adds (the dashboard's six are pre-existing unused imports/state); exit 0 | 40 s |
| 22 | `manage.py dump_route_inventory --check`, `dump_read_inventory --check` | current, current (no route changed) | 5 s |
| 23 | `git diff --check 4756ffc HEAD`; `file` on every touched file | clean; 0 CRLF | 1 s |
| 24a | `test-postgres core --parallel 8` at `94f1bd9`, 19:03 | **no test ran**: "Disposable PostgreSQL did not become ready" after the runner's 30 s window (8 min on the flock first) | 9 min |
| 24b | the same, 19:14 | **no test ran**, same failure | 5 min |
| 24c | probe: a bare `postgres:16-alpine` container on this host | `initdb`'s post-bootstrap fsyncs still running after 4 min; `jbd2/dm-0-8` in D state; `/proc/pressure/io` full ≈ 80 % for the whole window; no process moving data (stalls, not throughput); other builders' runner containers stuck in `Created` | 5 min |
| 24 | **`TEST_POSTGRES_READY_SECONDS=1500 test-postgres core --parallel 8`, once, at `94f1bd9`** (branch, revision, PID and timestamps in the log) | **`Ran 1526 tests in 2000.915s` — OK**, exit 0 (database ready at 19:39:56 after ~8 min on the flock and ~4 min of `initdb`; the suite's 33 min against the ~2 min other builders saw the same day is the disk stall of 24c, not the code) | 73 min (19:27 → 20:39) |

No runtime code changed after #24a began. The one file touched after the
freeze is the test runner itself, `backend/scripts/test-postgres`: its
readiness window (a fixed 30 s) is now `TEST_POSTGRES_READY_SECONDS`, default
30, so nothing changes for a run that does not set it; that knob is what made
the host condition in 24c survivable. The string inventory was regenerated
from the repository root after #24, in its own commit.

---

## 5. Proposed register status text

| id | proposed status |
|---|---|
| W-CE-01 | **Repaired (`457bfd6`).** Cause was an unmount: the dashboard returned a bare spinner during every reload and the Tabs were uncontrolled. Active tab is now component state; the spinner is for the first load only. Driven through the real component with a next-task server response. |
| W-CE-05 | **Repaired (`93ede85`).** The D6 helper was wired; a clean upload's only announcement was a 3-second toast. The outcome now also stays on the roster panel until dismissed (counts, file name), for clean and refused uploads alike. |
| W-CE-07 | **Repaired (`125bc9a`).** Before/after rendered as the fields that changed, labelled and valued from the catalogue in both languages; refusals show the recorded reason and code; raw record copyable. |
| W-CE-12 | **Repaired (`417bf93`).** One Override control per team on the Team Grades table: category, score, reason kept with the grade, clear; grades recalculated; overridden categories tagged. Refusals bilingual. |
| W-CE-24 | **Repaired (`49d0447`, `94f1bd9`).** With teams pending the lifecycle Advance Round is a ReasonedAction (reason required, `force: true`); with all locked a plain confirm; server refusals shown verbatim with guidance. |
| W-CE-26 | **Repaired (`263afb8`).** Reset refused for a competition heat (409 `competition_game_not_resettable`) and for any game with a processed round (409 `reset_round_processed`), bilingual, audited as rejections, pointing at archive. Reproduced through the route first; an unplayed game still resets. |
| W-CE-09 | **Repaired (`4926081`) by removal.** No student route serves the change log; the page, route and sidebar entry are gone; a source scan keeps student pages off the instructor-only route. Whether a team should be able to read its own change log is a permission question, listed for the integrator. |
| W-CE-10 | **Repaired (`9bde205`) by removal.** Nothing feeds a student bell; removed, remaining top-bar buttons named in both languages. |

---

## 6. What still needs someone else

| item | who | why |
|---|---|---|
| The eight repairs in a real browser, both languages | a browser (the walkthrough drivers) | Every repair is proven in Jest against the real component or in Django against the real route; the walkthrough's own drivers (`instructor_setup.py`, `instructor_endgame.py`, `instructor_round.py`, `student_tour.py`) are what shows them on screen. The `tab_after_*`, `roster_upload_*`, `end-reset`, `r3-01` and `s-pre-10` observations are the ones to re-read. |
| Chinese wording of the 50 new sentences (§3) | a native speaker | Terminology-checked and consistent with the backend label tables; not reviewed by a native reader. |
| A student route for a team's own decision change log | the integrator (an INTEGRATOR_DECISIONS entry under R48) | W-CE-09 is closed by removal; re-opening `changes/` to a team's own members would reverse part of the V2-035 hardening and needs a decision, not a builder's call. |

| The host's disk during this session (from ~19:00 UTC): journal thread `jbd2/dm-0-8` in D state, I/O pressure "full" ≈ 80 % with no process moving data, a bare Postgres `initdb` taking minutes; every builder's disposable database on this host was failing to come up | the host operator | Observed, not caused, by this branch; §4 rows 24a–24c. Not the production host. |

Nothing here needs the owner or the production host.

---

## 7. Preflight answers (EXECUTION_PROTOCOL)

* **Inventory from registered routes?** No route was added, removed or re-guarded; `dump_route_inventory --check` and `dump_read_inventory --check` are current at `94f1bd9`.
* **Active legacy or alternate entry point?** The legacy one-step advance route is the one W-CE-24 fixes the console for; `RoundControlCard`'s three-step path is unchanged. The reset route has no alternate entry (the management command is a different, withheld operation).
* **Does a refusal audit survive rollback?** Yes: both new reset refusals are raised inside `operator_action` and recorded by `_record_rejection` after the rollback; the tests read the rejected `OperatorAuditEvent` and its `request_id`.
* **Correlation id generated once?** Unchanged mechanism (`request_id_for`); the tests assert the refusal's `request_id` equals the audit row's.
* **Background work after commit?** None added.
* **Environment values / provenance?** The final suite log records branch, revision, PID, start and end.
* **README commands run as written?** The commands in §4 are the ones run.
* **P0/P1/P2 as defined?** Unchanged from the walkthrough's table.
* **Negative tests prove no mutation?** `assertUntouched` reads game status, current round and every round's status after each refused reset.
