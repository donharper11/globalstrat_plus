# Analyst audit, analyst language, roster upload, zh-CN terminology, operator refusals

**Branch:** `crv2-12-analyst-audit-and-roster-upload`, cut from
`crv2-release-integration` at `f46d173` (verified an ancestor of the branch).
**Commits:** `43b9181` (analyst audit + language: D1, D2, D5), `1942add`
(operator catalogue + roster upload: D3, D6), `54b8f95` (terminology: D4),
`2cf0281` (operator catalogue, second batch), then the commit that adds this
document, then the string-inventory re-cut in its own commit, last.

> **Development-grade evidence from a moving branch. NOT release certification.
> No gate is closed by this document.** The register, the launch checklist and
> the owner-rulings files were not edited; proposed register text is in §9.

Source: `completion/CONSOLE_AND_ANALYST_LEFTOVERS_2026-09-21.md` §6 — defects
D1, D2, D3, D4, D5 and D6(a), all recorded open there and not repaired.

---

## 1. State at head (`f46d173`), verified before anything was touched

| Item | Verified how | Result |
|---|---|---|
| D1 | New test drives the 503 path and counts `purchase_research_report` events | **Open.** 1 event, 0 purchase rows. One detail the earlier report had wrong: it says the charge transaction "commits" before the failure. It does not — `CompetitionDecisionWriteMixin.dispatch` wraps the whole handler in one `transaction.atomic()`, so the inner block is a savepoint. The orphan event still commits, because a 503 is a normal return. This matters for the choice of repair (§2.1). |
| D2 | New tests, zh-CN and en, on the 404, both 400s and the no-results 200 | **Open.** All four English-only. |
| D5 | Enrolment with `language='fr'`, no `Accept-Language`, closed round | **Open.** `KeyError: 'fr'` → 500. |
| D6(a) | Read of both call sites; new source-scan guard | **Open.** Both read `res.data?.created` only. |
| D4 | Term survey over every catalogue (counts in §2.4) | **Open**, and wider than recorded: 比赛 8× in the backend catalogues for "game", plus 轮 16×, 队伍 4× and 小组 1× for round/team, which the earlier report had not noticed. |
| D3 | AST scan of `core/views`, `core/rag/views.py`, `core/services/lifecycle.py` for `{'error'/'detail': <literal>}` and `Lifecycle*(<literal>)` | **Open.** Three bilingual codes existed; everything else English. |

Nothing was found already fixed.

## 2. What changed, and why

### 2.1 D1 — the purchase audit is written only with a delivered answer

**Chosen repair: write the `purchase_research_report` event once the answer
exists, in one savepoint with the `ResearchQueryLog` row. Not a compensating
event.** Reasons, from reading `competition_audit.py`, `audit_chain.py`, the
database guards and the integrity tests:

1. *Audit rows cannot be withdrawn.* `DecisionAuditEvent.save()` refuses a
   re-save, database triggers refuse UPDATE/DELETE/TRUNCATE, and every row is
   sealed into a hash chain on commit. So the only two honest options are "do
   not write it until it is true" or "write a second row that negates it".
   Neither deletes or mutates anything; both keep the chain valid.
2. *At no committed moment was there ever a charge.* The whole request is one
   transaction (§1), so the purchase row and its deletion commit together: no
   reader, budget calculation or resolution manifest ever saw the purchase. A
   `purchase` + `void` pair would describe, permanently, a charge that never
   existed in any committed state. The truthful record of "nothing happened" is
   no decision event — already this system's rule:
   `test_a_refused_purchase_writes_no_audit_event` pins that an unaffordable
   purchase leaves none, and the 429 leaves none.
3. *The decision-event table feeds the resolution manifest*
   (`manifest_sections`, `decision_audit_event`). A compensating pair adds two
   rows to a round's hashed input for something with no competitive effect, and
   anything that ever reconciles events against `decision_research_purchase`
   would have to learn to net them.
4. *No crash window is opened.* The usual argument for auditing with the charge
   is a crash in between leaving an unaudited charge. Here a crash rolls back
   the single transaction, charge and all.
5. *Fail-closed is preserved.* If the audit write fails after the answer exists,
   the savepoint rolls back the question log too, the `except` undoes the
   charge, and the student gets the 503: no answer, no charge, no quota used, no
   event. Tested by injection.

The failed attempt is still recorded where operational failures belong: the
`logger.exception` line now says `no audit event written` and carries the
`X-Request-ID`, purchase id, game, team and round.

Every outcome of the route now leaves the purchase row, the question log and the
audit event **all present or all absent**. Not changed: the empty draft
`DecisionSubmission` that `get_or_create` may leave behind on a failure. It
carries no money, every other refused decision write on this path leaves the
same (the unaffordable refusal does), and deleting it would race a teammate's
concurrent save.

### 2.2 D2 / D5 — the rest of the analyst route is bilingual

Four `participant_messages` entries (§5b). The route resolves its language once,
through the guarded `language_for_request()`, and uses it for every sentence,
including the two older refusals that used raw `get_user_language()` (D5).
`query` is read as `str(... or '')`, so a non-string body is a 400, not a 500.

The no-results answer now **says it was charged and counted**, because it is,
and a student should not discover that on the budget screen. If the owner
changes the rule (Q1), that sentence changes with it.

### 2.3 D6 — CSV roster upload

`pages/rosterUploadOutcome.js`, the `assignmentOutcome.js` pattern.
`rosterUploadOutcome(data)` reads `{created, updated, errors}` into
`{kind, created, existing, accepted, refusals: [{row, text}]}`, `kind` one of
`uploaded | partial | refused | unconfirmed`. Counts are what the SERVER
reported. Rows already on the roster count as accepted, so re-uploading a roster
is a success rather than `unconfirmed`. `announceRosterUpload()` shows a toast
for a clean upload and a **modal** for anything refused: both counts in the
heading, the accepted split, every refused row as `Row N: <server's sentence>`,
and a note that row 1 is the header and the accepted rows are saved. The pasted
text is kept unless the upload was clean, so refused rows can be corrected and
resent. Ten locale keys in both languages, literal `t()` keys only; the two old
`msg_roster_uploaded*` keys are removed.

Server side (`course.py`, text sources only): all three per-row reasons come
from catalogues and each row carries a `code` — `roster_row_needs_identity`,
`section_full`, `roster_row_failed`. The last replaces `str(e)`: what the
database raised is logged, not shown. That closes the roster-add and CSV-row
halves of the earlier report's D3a ("raw exception text").

Guard: `rosterUploadCallSites.test.js` walks every non-test file under `src/`
and fails unless each `uploadRoster(` call is
`announceRosterUpload(rosterUploadOutcome((await uploadRoster(…)).data), …)`. It
asserts it found exactly the two known call sites and tests its own regex on a
good and a bad snippet.

### 2.4 D4 — terminology

Counts at `f46d173` (frontend catalogue / `participant_messages` /
`cohort_messages` / other backend):

| Concept | Established | Rivals found | Applied |
|---|---|---|---|
| game | 游戏 48/0/0/0 | 比赛 1/4/3/0 | 游戏 |
| round | 回合 130/44/0/1 | 轮 16/0/0/0 | 回合 |
| team | 团队 62/26/10/0 | 队伍 3/0/0/1, 小组 1/0/0/0 | 团队 |
| instructor | 教师 9/6/2/0 | none (讲师 0, 老师 0) | unchanged |
| competition | 竞赛 3/0/0/0 | 比赛场次 0/0/1/0 | 竞赛, only where a competition is meant |

比赛 is therefore retired altogether. `core.tests.test_zh_terminology` reads all
five sources as text, fails on a retired term, and pins the exact set of keys
allowed to say 竞赛. All 30 changed sentences are in §5d.

### 2.5 D3 — operator refusals

New catalogue `core/utils/operator_messages.py` — 101 sentences including
guidance lines, three status-label tables, **72 codes** — in the
`cohort_messages` pattern, and a separate module so this work and the concurrent
`course.py` ownership work do not share a catalogue file. Registered with
`check-participant-strings` (A1 both languages, A2 same placeholders, A3 no
storage names).

* `operator_refusal(request, key, **values)` → `{'error', 'code'}`.
* `lifecycle_refusal(ErrorClass, key, **values)` for the lifecycle boundary.
  **The operator audit row and the server log keep the English sentence; only
  the response is localised** (`LifecycleError.localise`, applied in
  `lifecycle_view`). Before this, the one bilingual lifecycle refusal
  (`competition_course_unowned`) wrote Chinese into `OperatorAuditEvent.conflict`
  for a Chinese-language operator; it now records English like the rest. Tested.
* Status tokens (`closed`, `paused`, `withdrawn`) go through per-language label
  tables, so no Chinese sentence frames an English storage token.
* Existing codes are unchanged (`state_moved`, `reason_required`,
  `round_already_processed`, …). Refusals that had no code used to answer with
  the exception class name (`LifecyclePrecondition`); they now have real codes.
  Nothing in the tree, the harnesses or the frontend matched on a class-name
  code (grep over `handoff_readiness_v2`, `core/management`, `scripts`, `src`).

**Converted — every refusal in:** `services/lifecycle.py`; `round_control.py`;
`results_api.py` advance, inject, extend, session-readiness, operator-events,
team-decisions; `scenario_views.py` create, teams, activate, pause, resume,
reset, archive, delete; `course.py` `RosterViewSet`, `TeamManagementView`,
`GameRoundScheduleView`; `grading.py`; `team_config.py`; `team_control.py`;
`instructor_accounts.py`. `OperatorRefusalSourceScanTests` (AST, self-tested)
fails if any of them regrows an `{'error': <literal>}` or a
`Lifecycle*(<literal>)`.

`course.py` was edited at message-text sources only (the argument of
`Response(...)` / `errors.append(...)`, one import block, a module `logger`). No
control flow, ownership check or structure was touched.

**Frontend.** `BILINGUAL_REFUSAL_CODES` is those 72 codes, and a backend test
fails unless the list is *exactly* `operator_messages.bilingual_codes()`, in both
directions. `bilingualServerReason()` appends the server's localised `guidance`
line. New `serverReason(err)`: the bilingual sentence if there is one, else the
server's text — kept deliberately, since English-but-informative beats
Chinese-but-generic on routes not yet converted. All 19 dashboard sites that
read `err.response?.data?.error` directly go through it, and five catch blocks
that discarded the reason on now-converted routes (seed rubric, update student,
three assignment failures) surface it.

**Engine-originated detail stays English inside a bilingual frame**, on purpose:
`round_not_ready`, `advance_refused`, `processing_failed`, `advance_failed`
carry the engine's own exception sentence as `{detail}`, and the zh-CN frame says
so (`系统给出的原因（英文）：…`). Translating those means giving every engine
exception a key, which is engine work; listed in §6.

## 3. Red, then green

| # | Test | Red (at the state named) | Green |
|---|---|---|---|
| 1 | `test_paid_research.AnalystAuditTruthTests` (4) | At `f46d173` + tests: `1 != 0 : the audit trail records an analyst purchase the ledger does not`; `2 != 1` (failure-then-success); `RuntimeError: audit table unavailable` escaping as a 500. | OK |
| 2 | `test_paid_research.AnalystRouteLanguageTests` (5) | Same run, catalogue entries **already added** so the red is the view, not a `KeyError`: 8 sub-test failures of the form `'Query text is required.' != '请先输入…'`, plus `KeyError: 'fr'` (D5). Run total: `Ran 9 — FAILED (failures=10, errors=2)`, 12.3 s. | `Ran 98 — OK` with `test_audit_integrity` |
| 3 | `test_operator_refusal_language` (27 at the time) | Views unconverted, `lifecycle.py` **reverted to head for the run**, catalogue present: `FAILED (failures=42, errors=2)`, 48 s wall (mostly lock wait). All 7 source-scan sub-tests, the allowlist test, the audit-language test, and every behavioural test red in zh-CN (several also in en, where the old sentence named a storage field or had no code). | `Ran 33 — OK` (after batch 2) |
| 4 | `rosterUploadOutcome.test.js` + `rosterUploadCallSites.test.js` | Module written, dashboard and locales untouched: `12 failed, 12 passed` — the 10 locale-key tests and both call-site guards. | passed |
| 5 | `bilingualServerReason.test.js` (+ call sites) | New tests, `bilingualServerReason.js` and `InstructorDashboard.js` **restored to head for the run**: `21 failed, 6 passed`. | passed |
| 6 | `test_zh_terminology` (3) | Before the edits: `FAILED (failures=2)` — 29 offending sentences listed, and `cohort_messages:competition_course_unowned` not yet saying 竞赛. | OK |

Honest notes on these reds:
- Row 1's `test_an_answered_question_is_audited_exactly_once` was **green at
  head**; it is a contract pin for the happy path and is not evidence of a
  defect.
- Row 4's module tests (`rosterUploadOutcome`, `announceRosterUpload`) were never
  red: they were written with the module. The behavioural red is the call-site
  guard, which fails on the head dashboard.
- Row 3 was captured before batch 2; the six tests batch 2 added
  (`scenario_required`, `participation_action_invalid`, `account_not_visible`)
  were not separately observed red. Their routes returned code-less English at
  `1942add`, which the same assertions reject, but that is by reading.

## 4. Commands, results, durations

Backend, all through
`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`
(disposable Postgres container per run; the production database and
`/etc/globalstrat-plus.env` were never read):

| Labels | Result | Wall |
|---|---|---|
| `…AnalystAuditTruthTests …AnalystRouteLanguageTests` (red) | `Ran 9 — FAILED (failures=10, errors=2)` | 12.3 s |
| `test_paid_research test_audit_integrity test_engine.TestRAGInfrastructure` | `Ran 98 — OK` | 32.3 s |
| `test_operator_refusal_language` (red) | `Ran 27 — FAILED (failures=42, errors=2)` | 48.3 s |
| `test_operator_refusal_language test_paid_research test_audit_integrity test_cohort_caps test_player_language_guard test_crv2_12_language test_console_defects test_auth_rounds test_game_scope_boundary test_competition_hardening test_refusal_audit test_refusal_audit_integrity test_r40_model_component_not_in_competition` | `Ran 289 — OK` | 1 m 44 s |
| `test_zh_terminology` (red, then with `test_cohort_caps test_crv2_12_language test_player_language_guard`) | `FAILED (failures=2)` → `Ran 55 — OK` | ~12 s each |
| `test_operator_refusal_language test_zh_terminology` (after batch 2) | `Ran 33 — OK` | 11.6 s |
| **`core --parallel 8`, once, at `2cf0281`** | **`Ran 1255 tests in 96.5s — OK`, exit 0** | **1 m 54 s** |

No runtime code changed after the full run; the two later commits are this
document and generated inventory output.

Frontend, in `frontend/globalstrat-frontend` (`npm ci` first):

| Command | Result |
|---|---|
| `CI=true npx react-scripts test --watchAll=false` | 17 suites, 137 tests, all passed, 3.4 s (head: 15 suites, 94 tests) |
| `python3 backend/scripts/check-participant-strings` | `PASS 4811 unit(s) examined, 0 reviewed suppression(s)`; 27 computed keys unresolved — unchanged from head. It failed once on the way (A8: a scanner snippet in `instructorDashboardMessages.test.js` quoted the removed `msg_roster_uploaded` key); the snippet now quotes a live key. |
| `python3 backend/scripts/check-participant-strings-selftest` | `34 ok, 0 failed` |
| `CI=false BUILD_PATH=<scratch> npx react-scripts build`, then `node eslint-warning-count.js build.log` (the CI recipe) | build exit 0; `eslint warnings: 55 (baseline 57)` — the same 55 as the previous report, none added. Baseline file not lowered: shared file, not my warnings. |
| `generate_inventory.py`, then `--check` | see the last commit |

## 5. zh-CN — the complete list for one native review

Terms follow §2.4. Additional choices a reviewer should rule on:
**已结算** for a processed round (taken from `ROUND_STATUS_LABELS`, so 结算 is also
the verb for "process a round" throughout 5a); **操作者** for "operator";
**停用 / 重新启用** for deactivating/reactivating a team; **情景** for "scenario";
**控制台** for "console"; **强制选项** for the force option; **越权操作** for an
override in `reason_required_guidance` (possibly too strong — "override of a
check", not "exceeding authority", is what is meant).

#### 5a. `backend/core/utils/operator_messages.py` — all new

| Key | en | zh-CN |
|---|---|---|
| `game_not_found` | That game could not be found. Reload the console and choose the game again. | 未找到该游戏。请刷新控制台后重新选择游戏。 |
| `round_missing` | Game "{game}" has no round {round}. | 游戏“{game}”没有第 {round} 回合。 |
| `round_missing_guidance` | The game may not be initialised. Check the game setup. | 该游戏可能尚未完成初始化。请检查游戏设置。 |
| `expected_round_not_a_number` | The round number the console sent with this request was not a number. Reload the console and try again. | 控制台随本次请求发送的回合编号不是数字。请刷新控制台后重试。 |
| `state_moved_round` | The game has moved to round {current}; this request was for round {expected}. | 游戏已进入第 {current} 回合；本次请求针对的是第 {expected} 回合。 |
| `state_moved_status` | Round {round} is now {status}, not {expected} as the console showed. | 第 {round} 回合当前{status}，而不是控制台显示的{expected}。 |
| `state_moved_guidance` | Refresh the console and repeat the action if it is still what you want. | 请刷新控制台；如仍需执行该操作，请再次操作。 |
| `reason_required` | This action overrides an integrity check, so it requires a written reason of at least {minimum} characters. | 此操作会绕过一项完整性检查，因此需要填写至少 {minimum} 个字符的书面理由。 |
| `reason_required_guidance` | Repeat the action with a written reason explaining why this override is correct. | 请填写书面理由，说明为何需要此次越权操作，然后重新执行。 |
| `competition_course_unowned_guidance` | Assign an instructor to the course behind this game, then repeat the action. | 请先为该游戏所属课程指定教师，然后重新执行该操作。 |
| `game_belongs_to_another_instructor` | This game belongs to another instructor. | 该游戏属于另一位教师。 |
| `round_already_closed` | Round {round} is already {status}. | 第 {round} 回合{status}。 |
| `round_already_closed_guidance` | Refresh the console — the deadline scheduler or another operator closed it first. | 请刷新控制台——截止时间调度程序或另一位操作者已先行关闭该回合。 |
| `reopen_already_processed` | Round {round} has already been processed and cannot be reopened. | 第 {round} 回合已结算，无法重新开放。 |
| `reopen_already_processed_guidance` | Results exist for this round. Recovery is the only route back; see the recovery runbook. | 本回合的结果已经生成。只能通过恢复流程回退；请参阅恢复操作手册。 |
| `round_already_open` | Round {round} is already open. | 第 {round} 回合已处于开放状态。 |
| `round_already_open_guidance` | Refresh the console — another operator reopened it. | 请刷新控制台——另一位操作者已重新开放该回合。 |
| `deadline_unparseable` | The deadline could not be read as a date and time. Pick the deadline again and resend. | 无法将该截止时间识别为日期和时间。请重新选择截止时间后再提交。 |
| `deadline_in_past` | The deadline has already passed. | 截止时间已过。 |
| `deadline_in_past_guidance` | Supply a new deadline when reopening, or the scheduler will close the round again within a minute. | 重新开放时请设置新的截止时间，否则调度程序会在一分钟内再次关闭该回合。 |
| `process_already_processed` | Round {round} has already been processed. | 第 {round} 回合已结算。 |
| `process_already_processed_guidance` | Refresh the console. If results look wrong, use recovery rather than processing again. | 请刷新控制台。如结果有误，请使用恢复流程，而不要再次结算。 |
| `round_still_open` | Round {round} is still open. | 第 {round} 回合仍处于开放状态。 |
| `round_still_open_guidance` | Close it first, or use the force option with a written reason to close and process in one step. | 请先关闭该回合；或使用强制选项并填写书面理由，一步完成关闭和结算。 |
| `round_not_ready` | {detail} | 本回合尚不具备结算条件。系统给出的原因（英文）：{detail} |
| `round_not_ready_guidance` | Re-lock the team, or close the round, then process again. | 请重新锁定该团队的决策，或关闭该回合，然后再次结算。 |
| `processing_failed` | Post-round processing failed: {detail} | 回合结算失败。系统给出的原因（英文）：{detail} |
| `round_not_processed` | Round {round} is {status}, not processed. | 第 {round} 回合{status}，尚未结算。 |
| `round_not_processed_guidance` | Run post-round processing first, or use the force option with a written reason to advance without results. | 请先执行回合结算；或使用强制选项并填写书面理由，在没有结果的情况下进入下一回合。 |
| `advance_refused` | {detail} | 无法进入下一回合。系统给出的原因（英文）：{detail} |
| `advance_refused_guidance` | Refresh the console. | 请刷新控制台。 |
| `advance_failed` | Advance failed: {detail} | 进入下一回合失败。系统给出的原因（英文）：{detail} |
| `round_not_open` | Round {round} is {status}; deadline changes are refused unless the round is open. | 第 {round} 回合{status}；只有开放中的回合才能修改截止时间。 |
| `round_not_open_guidance` | Reopen the round with a new deadline if students still need time. | 如学生仍需时间，请重新开放该回合并设置新的截止时间。 |
| `minutes_not_a_number` | The number of minutes must be a whole number. | 分钟数必须为整数。 |
| `deadline_required` | Provide a deadline, or a number of minutes from now. | 请提供截止时间，或从现在起的分钟数。 |
| `legacy_advance_already_processed` | Round {round} has already been processed. | 第 {round} 回合已结算。 |
| `legacy_advance_already_processed_guidance` | Refresh the console and advance instead. | 请刷新控制台，然后改为进入下一回合。 |
| `team_not_locked` | Team "{team}" has not locked decisions. | 团队“{team}”尚未锁定决策。 |
| `team_not_locked_guidance` | Lock or close the round first, or use the force option with a written reason. | 请先锁定决策或关闭该回合；或使用强制选项并填写书面理由。 |
| `legacy_advance_failed` | Round advance failed: {detail} | 回合推进失败。系统给出的原因（英文）：{detail} |
| `inject_already_processed` | Round {round} has already been processed; an event injected now would not be part of it. | 第 {round} 回合已结算；此时注入的事件不会计入该回合。 |
| `inject_already_processed_guidance` | Advance to the next round and inject there. | 请进入下一回合后再注入事件。 |
| `hours_not_a_number` | The number of hours must be a whole number. | 小时数必须为整数。 |
| `extend_already_processed` | Round {round} has already been processed; its deadline cannot be extended. | 第 {round} 回合已结算；无法延长其截止时间。 |
| `extend_already_processed_guidance` | Advance to the next round and set its deadline there. | 请进入下一回合，并在该回合设置截止时间。 |
| `game_not_in_setup` | This game is already {status}. Only a game in setup can be activated. | 该游戏当前{status}。只有设置中的游戏才能激活。 |
| `game_not_in_setup_guidance` | Refresh — another operator may have activated it. | 请刷新——可能已有另一位操作者激活了该游戏。 |
| `round_one_missing` | This game has no round 1, so it cannot be activated. Check the game setup. | 该游戏没有第 1 回合，因此无法激活。请检查游戏设置。 |
| `game_not_active` | This game is {status}, not active, so it cannot be paused. | 该游戏当前{status}，并非进行中，因此无法暂停。 |
| `game_not_active_guidance` | Refresh — another operator may have paused or completed it. | 请刷新——可能已有另一位操作者暂停或结束了该游戏。 |
| `game_not_paused` | This game is {status}, not paused, so it cannot be resumed. | 该游戏当前{status}，并非已暂停，因此无法恢复。 |
| `game_not_paused_guidance` | Refresh — another operator may have resumed it. | 请刷新——可能已有另一位操作者恢复了该游戏。 |
| `game_already_archived` | This game is already archived. | 该游戏已归档。 |
| `game_already_archived_guidance` | Refresh — another operator archived it. | 请刷新——另一位操作者已将其归档。 |
| `scenario_required` | Choose a scenario before creating the game. | 创建游戏前，请先选择情景。 |
| `scenario_not_found` | That scenario could not be found. Reload the console and choose the scenario again. | 未找到该情景。请刷新控制台后重新选择情景。 |
| `team_count_required` | Enter the number of teams before creating the game. | 创建游戏前，请先输入团队数量。 |
| `team_count_not_a_number` | The number of teams must be a whole number. | 团队数量必须为整数。 |
| `game_creator_missing` | The game could not be recorded against an account, so it was not created. Contact support. | 无法将该游戏记录到任何账户名下，因此未创建。请联系技术支持。 |
| `round_not_found` | That round could not be found. Reload the console. | 未找到该回合。请刷新控制台。 |
| `participation_action_invalid` | Choose whether to deactivate or reactivate the team. | 请选择停用或重新启用该团队。 |
| `confirmation_required` | To confirm, type exactly: {expected} | 如需确认，请准确输入：{expected} |
| `participation_unchanged` | This team is already {status}. | 该团队当前{status}。 |
| `participation_unchanged_guidance` | Refresh — another operator may have changed it. | 请刷新——可能已有另一位操作者更改了该团队的状态。 |
| `account_not_visible` | That student could not be found, or is not in one of your courses. | 未找到该学生，或该学生不在您的任何课程中。 |
| `account_instructor_reset_refused` | Only an administrator can reset an instructor password. | 只有管理员可以重置教师密码。 |
| `account_no_default_password` | This account has neither a student number nor a username to derive a default password from. Set a password explicitly. | 该账户既没有学号也没有用户名，无法生成默认密码。请直接设置一个密码。 |
| `account_bulk_selection_required` | Choose the students to reset, or choose to reset only those with no password. | 请选择要重置的学生，或选择仅重置尚未设置密码的学生。 |
| `round_1_started` | Home markets cannot be changed after round 1 decisions have been submitted. | 第 1 回合的决策提交后，不能再更改总部市场。 |
| `round_1_started_guidance` | Team configuration is fixed once play starts. | 游戏开始后，团队配置即固定。 |
| `team_config_no_teams` | No teams were included in this request, so nothing was saved. Reload the console and try again. | 本次请求未包含任何团队，因此未保存任何内容。请刷新控制台后重试。 |
| `team_config_team_not_in_game` | One of the teams in this request is not part of this game, so nothing was saved. Reload the console and try again. | 本次请求中有团队不属于该游戏，因此未保存任何内容。请刷新控制台后重试。 |
| `team_config_invalid_market` | "{market}" is not a market in this scenario. Available markets: {valid}. | “{market}”不是本情景中的市场。可选市场：{valid}。 |
| `scenario_has_no_markets` | This scenario defines no markets, so home markets cannot be assigned. | 本情景未定义任何市场，因此无法分配总部市场。 |
| `section_required` | Choose a section first. The request did not say which section it was for. | 请先选择班级。本次请求未指明班级。 |
| `section_not_found` | That section could not be found. Reload the console and choose the section again. | 未找到该班级。请刷新控制台后重新选择班级。 |
| `roster_unknown_action` | The console asked the roster for something it cannot do. Reload the console and try again. | 控制台向名单发出了无法执行的请求。请刷新控制台后重试。 |
| `roster_student_required` | The request did not say which student it was for. Reload the roster and try again. | 本次请求未指明学生。请刷新名单后重试。 |
| `roster_student_not_found` | That student is no longer on the roster. Reload the roster. | 该学生已不在名单中。请刷新名单。 |
| `roster_account_not_found` | The account behind this roster entry could not be found, so nothing was changed. Reload the roster. | 未找到该名单条目对应的账户，因此未作任何更改。请刷新名单。 |
| `roster_csv_empty` | No roster data was provided. Choose a file, or paste the roster text, then upload again. | 未提供名单数据。请选择文件或粘贴名单文本，然后重新上传。 |
| `roster_row_needs_identity` | This row has neither a student number nor an email address, so no student was created from it. | 该行既没有学号也没有邮箱，因此未据此创建学生。 |
| `roster_row_failed` | This row could not be saved, so no student was created from it. Check the row and upload it again; if it keeps failing, contact support. | 该行无法保存，因此未据此创建学生。请检查该行后重新上传；如持续失败，请联系技术支持。 |
| `roster_identity_required` | Enter a student number or an email address for the student. | 请输入该学生的学号或邮箱。 |
| `roster_add_failed` | The student could not be added. Check the details and try again; if it keeps failing, contact support. | 无法添加该学生。请检查信息后重试；如持续失败，请联系技术支持。 |
| `team_management_unknown_action` | The console asked team management for something it cannot do. Reload the console and try again. | 控制台向团队管理发出了无法执行的请求。请刷新控制台后重试。 |
| `assignments_required` | No team assignments were included in this request, so nothing was changed. | 本次请求未包含任何团队分配，因此未作任何更改。 |
| `team_rename_incomplete` | Choose a team and enter its new name. | 请选择团队并输入新名称。 |
| `team_not_found` | That team no longer exists. Reload the console. | 该团队已不存在。请刷新控制台。 |
| `schedule_rounds_required` | No rounds were included in this schedule, so nothing was scheduled. | 该日程未包含任何回合，因此未安排任何日程。 |
| `schedule_round_not_in_game` | One of the rounds in this schedule is not part of this game. | 该日程中有回合不属于该游戏。 |
| `schedule_round_frozen` | Round {round} is {status}; its schedule can no longer change. | 第 {round} 回合{status}；其日程不能再更改。 |
| `schedule_invalid_time` | Round {round} has a time that could not be read as a date and time. | 第 {round} 回合有一个时间无法识别为日期和时间。 |
| `schedule_rejected_guidance` | Nothing was scheduled. Fix the listed rounds and resend the whole schedule. | 未安排任何日程。请修正所列回合后重新提交整个日程。 |
| `grading_course_required` | Choose a course first. The request did not say which course it was for. | 请先选择课程。本次请求未指明课程。 |
| `grading_game_and_course_required` | Choose a game and a course first. The request did not say which it was for. | 请先选择游戏和课程。本次请求未指明游戏或课程。 |
| `grading_game_required` | Choose a game first. The request did not say which game it was for. | 请先选择游戏。本次请求未指明游戏。 |
| `grading_override_incomplete` | Choose a game and a team, and enter the score, before overriding a grade. | 修改成绩前，请先选择游戏和团队，并输入分数。 |
| `grading_clear_incomplete` | Choose a game and a team before removing a grade override. | 撤销成绩修改前，请先选择游戏和团队。 |
| `grade_not_found` | There is no grade for that team yet. Calculate grades first. | 该团队尚无成绩。请先计算成绩。 |
| `GAME_STATUS_LABELS.setup` | in setup | 设置中 |
| `GAME_STATUS_LABELS.active` | active | 进行中 |
| `GAME_STATUS_LABELS.paused` | paused | 已暂停 |
| `GAME_STATUS_LABELS.completed` | completed | 已结束 |
| `GAME_STATUS_LABELS.archived` | archived | 已归档 |
| `PARTICIPATION_STATUS_LABELS.active` | active | 处于参与状态 |
| `PARTICIPATION_STATUS_LABELS.withdrawn` | withdrawn | 已停用 |

#### 5b. `backend/core/utils/participant_messages.py` — new analyst sentences

| Key | en | zh-CN |
|---|---|---|
| `analyst_question_required` | Type a question for the analyst before pressing Ask. Nothing was asked and nothing was charged. | 请先输入要向分析师提出的问题，再点击提问。本次未提交问题，也未产生费用。 |
| `analyst_not_enabled` | The research analyst is not part of this game, so your question was not asked and nothing was charged. | 本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。 |
| `analyst_game_or_team_not_found` | This game or team could not be found, so your question was not asked and nothing was charged. Reload the page; if it keeps happening, tell your instructor. | 未找到该游戏或团队，因此您的问题未提交，也未产生费用。请刷新页面；如问题持续出现，请告知教师。 |
| `analyst_no_relevant_research` | The analyst found no relevant research for this question. Try broader terms, or ask about a specific market, entry strategy or competitor. This question counts toward your team's questions for the round and was charged. | 分析师未找到与该问题相关的研究资料。请尝试使用更宽泛的措辞，或就具体市场、进入策略或竞争对手提问。本次提问已计入您团队本回合的提问次数，并已收费。 |

#### 5c. `zh-CN.json`, `instructor.*` — new roster-upload wording

| Key | en | zh-CN |
|---|---|---|
| `roster_upload_added` | Added {{created}} student(s) to the roster. | 已向名单添加 {{created}} 名学生。 |
| `roster_upload_added_existing` | Added {{created}} student(s) to the roster; {{existing}} were already on it. | 已向名单添加 {{created}} 名学生；另有 {{existing}} 名已在名单中。 |
| `roster_upload_partial` | {{accepted}} row(s) accepted, {{refused}} refused | 已接受 {{accepted}} 行，拒绝 {{refused}} 行 |
| `roster_upload_none` | No rows were accepted; {{refused}} refused | 没有任何行被接受；拒绝 {{refused}} 行 |
| `roster_upload_accepted_detail` | Accepted: {{created}} student(s) added, {{existing}} already on the roster. | 已接受：新增 {{created}} 名学生，{{existing}} 名已在名单中。 |
| `roster_upload_unconfirmed` | The server did not confirm the upload. Check the roster before relying on it. | 服务器未确认本次上传。请先核对名单，再以其为准。 |
| `roster_upload_row` | Row {{row}}: {{reason}} | 第 {{row}} 行：{{reason}} |
| `roster_upload_file` | File: {{file}} | 文件：{{file}} |
| `roster_upload_no_reason` | This row was refused and the server gave no reason. | 该行被拒绝，服务器未说明原因。 |
| `roster_upload_fix_note` | Row 1 is the header. The accepted rows are saved; correct the refused rows and upload them again. | 第 1 行为表头。已接受的行已保存；请修正被拒绝的行后重新上传。 |

#### 5d. Terminology — every changed sentence (old → new)

| File | Was | Now |
|---|---|---|
| `cohort_messages.py` | '请在比赛开始前补充成员。' | '请在游戏开始前补充成员。' |
| `cohort_messages.py` | '一场比赛至少需要 {minimum} 个团队 | '一场游戏至少需要 {minimum} 个团队 |
| `cohort_messages.py` | '{game} 是比赛场次，但尚未指定负责教师 | '{game} 是一场竞赛，但尚未指定负责教师 |
| `participant_messages.py` | '该团队已退出比赛，无法提交决策。' | '该团队已退出游戏，无法提交决策。' |
| `participant_messages.py` | '教师已暂停比赛。当前无法进行修改。' | '教师已暂停游戏。当前无法进行修改。' |
| `participant_messages.py` | '该比赛已结束，不能再修改决策。' | '该游戏已结束，不能再修改决策。' |
| `participant_messages.py` | '所选平台不适用于本场比赛。请选择可用平台。' | '所选平台不适用于本游戏。请选择可用平台。' |
| `cc31h_views.py` | {submitted}/{total}队伍已提交' | {submitted}/{total} 个团队已提交' |
| `zh-CN.json` | "no_briefing": "暂无战略简报。简报将在每轮结束后生成。" | "no_briefing": "暂无战略简报。简报将在每回合结束后生成。" |
| `zh-CN.json` |     "rounds": "轮", |     "rounds": "回合", |
| `zh-CN.json` | "no_product_data": "本轮暂无产品数据。" | "no_product_data": "本回合暂无产品数据。" |
| `zh-CN.json` | 建议下一轮增加产量。 | 建议下一回合增加产量。 |
| `zh-CN.json` | "rounds_remaining": "轮剩余" | "rounds_remaining": "回合剩余" |
| `zh-CN.json` | "revoke_warning": "您在第{{round}}轮采纳了{{name}}。 | "revoke_warning": "您在第{{round}}回合采纳了{{name}}。 |
| `zh-CN.json` | "rounds_to_integrate": "轮完成整合" | "rounds_to_integrate": "回合完成整合" |
| `zh-CN.json` | 还剩{{rounds}}轮干扰期（85%效率） | 还剩{{rounds}}回合干扰期（85%效率） |
| `zh-CN.json` | "rounds_disruption": "轮干扰期" | "rounds_disruption": "回合干扰期" |
| `zh-CN.json` | "revoke_savings": "这将节省{{cost}}/轮。" | "revoke_savings": "这将节省{{cost}}/回合。" |
| `zh-CN.json` | "of_teams_other": "共 {{count}} 支队伍" | "of_teams_other": "共 {{count}} 个团队" |
| `zh-CN.json` | 技术特性上限提升：每轮基于研发投资逐步递增。 | 技术特性上限提升：每回合基于研发投资逐步递增。 |
| `zh-CN.json` | 请在比赛开始前为这些团队补充成员。 | 请在游戏开始前为这些团队补充成员。 |
| `zh-CN.json` | "decisions_load_failed": "无法加载该小组的决策" | "decisions_load_failed": "无法加载该团队的决策" |
| `zh-CN.json` | "teams_locked_status": "{{locked}} / {{total}} 支队伍已锁定决策。" | "teams_locked_status": "{{locked}} / {{total}} 个团队已锁定决策。" |
| `zh-CN.json` | "teams_pending_status": "{{count}} 支队伍仍在等待中。" | "teams_pending_status": "{{count}} 个团队仍在等待中。" |
| `zh-CN.json` | "help": "本轮已锁定，无法更改。" | "help": "本回合已锁定，无法更改。" |
| `zh-CN.json` | "help": "本轮当前不开放更改。" | "help": "本回合当前不开放更改。" |
| `zh-CN.json` | "help": "该项会随每轮模拟运行自动更新。" | "help": "该项会随每回合模拟运行自动更新。" |
| `zh-CN.json` | "locked_notice": "本轮您的决策已锁定。" | "locked_notice": "本回合您的决策已锁定。" |
| `zh-CN.json` | "readonly_notice": "本轮不开放更改——您正在查看。" | "readonly_notice": "本回合不开放更改——您正在查看。" |
| `zh-CN.json` | {{submitted}}/{{total}} 支团队已提交 | {{submitted}}/{{total}} 个团队已提交 |

Also changed to match: the two Jest fixtures that quote the server's sentences
(`bilingualServerReason.test.js`, `assignmentOutcome.test.js`).

One English sentence is loose in the same way and was **left alone** because the
item is zh-CN usage: `team_withdrawn` says "withdrawn from the competition" for a
team withdrawn from any game. Its zh-CN now says 游戏.

## 6. D3 — the remainder, precisely

Generated by the same AST scan as the guard, over `core/views/*.py`,
`core/rag/views.py` and `core/services/lifecycle.py`, at `2cf0281`: **62**
English `{'error'/'detail': <literal>}` sites remain, none in a converted file's
converted classes.

**Instructor-console or instructor-only routes still English (14 sites):**

| File:line | View | Text |
|---|---|---|
| `scenario_views.py:97` | `ScenarioDetailView` (console: scenario picker) | `Scenario {id} not found.` — the key `scenario_not_found` exists; one-line change, found after the full run and left so no runtime code changes after it |
| `decisions.py:1069,1077` | `DecisionUnlockView` | `Round N has already been processed; unlocking now would not change its results.`; `Submission is not locked.` |
| `instructor_sc.py:237` | `InstructorInjectSCEventView` | `Round N is "status"; an event staged now would not fire in it.` |
| `course.py:875,881,944` | `DecisionStatusView` | `No active round.`; `Round not found.`; `{n}/{m} submitted` (a label, not a refusal) |
| `course.py:984,988` | `SendReminderView` | `Round not found.`; `instance_id is required.` |
| `course.py:278` | `RosterViewSet.delete` | `Enrollment removed.` — the body of a 204; never displayed |
| `core.py:58–118` | `UserViewSet` CSV import (not called by the console) | `No CSV data provided.`, `Missing username`, `Invalid team_id: N`, `Team not found.` |

**Not literals, so not counted above, and still English:**
- DRF `ModelViewSet` field errors on `courses/`, `sections/`,
  `grading-categories/` (`This field is required.`, keyed by field name). The
  console keeps its catalogue sentence for these.
- `GameCreateView`: `str(GameCreationError)`; `StudentPasswordResetView`:
  `validate_password()`'s sentence; `CalculateGradesView`:
  `str(ModelDerivedComponentInCompetition)` (the console already shows its own
  bilingual sentence for that code).
- The engine sentences carried as `{detail}` (§2.5): `RoundNotReadyError` and its
  subclasses, `advance_to_next_round`'s `ValueError`s, and whatever an engine
  failure raises into `processing_failed` / `advance_failed`.
- Round-control **success** texts: `message` (`"{game}: round N closed. M
  submission(s) locked."` etc., five routes) and the deadline `warning`.
  `RoundControlCard` shows them verbatim. These are confirmations, not refusals,
  and were out of this item's scope.
- `get_object_or_404` answers (`{"detail": "Not found."}`) in inject-event and
  team participation.

**Student-facing routes, outside "operator" (48 sites):** `auth.py` 7 (login
refusals — the most visible of these), `cc32b_views.py` 8 and `cc32a_views.py` 5
(organisation structure, communications), `core.py` `DashboardViewSet` 3,
`onboarding.py` 5, `persona_engine.py` 3, `programs.py` 3, `events.py` 2,
`gamification.py` 2, `rag/views.py` 2 (`ActiveEventsView`, `EventHistoryView`:
`Game not found.`), and one each in `briefing.py`, `cc15_views.py`,
`cc32c_views.py`, `cc32h_views.py`, `mixins.py` (`Decisions are locked for this
round.`), `research_reports.py`, `resources.py`, `strategic_impact.py`. Exact
lines: rerun the scan in `OperatorRefusalSourceScanTests` over those files.

**Frontend, found while wiring and not in any of the five items:**
`RoundControlCard.js` and `StudentAccountsPanel.js` speak hard-coded English in
their own `message.*` fallbacks and confirmations (`'Could not load round
status'`, `'Action failed'`, `'Pick a new deadline, or the round will close again
straight away.'`, `'Could not set the password'`, …). They show the server's
text first, so they now show Chinese when the server refuses; their own
fallbacks remain English. The existing guard polices `InstructorDashboard.js`
only. D6(b), (c), (d) of the earlier report are unchanged.

## 7. Questions for the owner

**Q1. Should a team be charged for "No relevant research found"?** Current
behaviour, unchanged by this branch: **yes, in full.** When the vector search
returns nothing, the route answers 200, keeps the `DecisionResearchPurchase` at
the full analyst price, writes the `ResearchQueryLog` row (so the question also
uses one of the round's quota), and — now — writes the purchase audit event,
because an answer was delivered. Only a *failure* of the research system is free.
Whether "we looked and found nothing" is a delivered answer worth the price is a
rule, not a defect; the new sentence tells the student plainly that it was
charged. If the ruling is "not charged", the change is small and local: treat an
empty result like the 503 path (undo the purchase, write no log row, no event)
and drop the last sentence of `analyst_no_relevant_research`.

**Q2. In which language should an analyst answer be written?** Refusals and the
no-results sentence now follow the *request's* language. Synthesised briefs
follow the *team's* language (`get_team_language`: the first enrolled student's).
On a mixed-language team those differ. Unchanged here; recorded because the two
now sit side by side on one route.

**Q3. Should the operator audit trail be English-only?** This branch makes it so
for lifecycle refusals (§2.5), on the reasoning that an investigator should read
one language. It reverses, for `competition_course_unowned` only, what head did.
If the owner would rather the audit record exactly what the operator read, that
is a one-line change in `lifecycle_refusal`.

## 8. What a reviewer should distrust

Only what could not be resolved here:

1. **Every zh-CN sentence in §5 — 122 new and 30 changed — was written by me and
   has not been read by a native speaker.** The specific choices I am least sure
   of are named at the top of §5.
2. **Nothing was observed in a browser.** `InstructorDashboard` is rendered by no
   test. The roster-upload modal's content is rendered for real by Jest, and the
   wiring is held by source scans, but its appearance, the modal's width and
   scroll on a long refusal list, and a toast that now carries sentence +
   guidance (longer than before) have not been seen on a screen.
3. **Q1–Q3 need the owner.**

Everything else I doubted, I checked: that the savepoint around the log + audit
write really leaves the outer transaction usable (tested by injection, 503 and
clean state); that the chain seals and verifies after a failure then a success
(tested); that no harness or frontend code matched on the old class-name codes
or the changed English sentences (grep, then the full suite); that the locale
files were edited textually, not re-serialised (a re-dump of `en.json` would have
rewritten an existing `’` escape); that the new test files add no computed
`t()` key (27 before and after).

## 9. Proposed register text (for the auditor to apply or reject)

**D1 — analyst purchase audit:**
> **Repaired, pending closure.** `43b9181`: `research/query/` writes its
> `purchase_research_report` event only once the answer exists, in one savepoint
> with the question log; any failure there undoes the charge. No audit row is
> deleted, mutated or compensated. Purchase row, question log and audit event are
> all present or all absent on every path (tests: outage, outage-then-success
> with chain verification, injected audit failure). Open, owner: whether the
> charged "no relevant research" answer should be charged at all (Q1).

**D2 / D5 — analyst route language:**
> **Repaired, pending closure.** `43b9181`: every sentence on the route comes
> from `participant_messages` in the request's language via the guarded resolver;
> an unsupported enrolment language no longer raises. zh-CN unreviewed.

**D6(a) — roster upload, V2-104 shape:**
> **Repaired, pending closure.** `1942add`: both upload controls read the 201
> through `rosterUploadOutcome`; accepted and refused rows are counted from the
> server's response and each refused row is listed with its row number and the
> server's bilingual reason; a source-scan guard covers every `uploadRoster()`
> call under `src/`. Per-row reasons carry codes; raw exception text no longer
> reaches the instructor. Unobserved on screen. D6(b)–(d) unchanged.

**D4 — terminology:**
> **Repaired, pending native review.** `54b8f95`: one zh-CN term per concept
> across all catalogues (游戏, 回合, 团队, 教师; 竞赛 only for a competition; 比赛
> retired); 30 sentences changed; a text-level test prevents regression.

**D3 — operator refusals:**
> **Partly repaired, pending closure.** `1942add`, `2cf0281`: the refusals of the
> routes the instructor console calls (lifecycle boundary, round control,
> deadline, pause/resume/activate/archive, legacy advance/inject/extend, team
> assignment, roster, schedule, grading, team configuration, team participation,
> student accounts, game creation) come from `core/utils/operator_messages.py`
> in the request's language with 72 stable codes; the operator audit row keeps
> English. The console allowlist is test-locked to those codes. **Residual:** 14
> instructor-side literals, DRF field errors, engine exception detail, and
> round-control success messages remain English (completion doc §6); 48
> student-facing literals outside the participant decision path likewise. zh-CN
> unreviewed.
