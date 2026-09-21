# Console and analyst leftovers (N2, N3, N4 of the 2026-09-21 assignment report)

**Branch:** `crv2-12-console-and-analyst-leftovers`, cut from
`crv2-release-integration` at `d433a94`.
**Commits:** `05967b2` (analyst refusals), `b244e73` (`under_minimum`),
`4856d89` (console toasts), `05428a3` (string inventory re-cut, generated
output only, its own commit), plus the commit that adds this report.

> **Development-grade focused evidence from a moving branch. NOT release
> certification. No gate is closed by this document.** The register and the
> launch checklist were not edited; proposed register text is in §8. No full
> backend suite was run, by instruction.

Source: `completion/ASSIGNMENT_REFUSAL_AND_ANALYST_PRICE_2026-09-21.md` §6,
items N2, N3 and N4. N1 of that report (the tab posted `query_text`, the view
read `query`) **was already repaired at head** by `aeba182`; the tab posts
`query` and a Jest test asserts the body. It matters here because it means the
two refusals below are now reachable from the interface.

---

## 1. State at head, verified before anything was touched

### Item 1 — console toasts (N3)

`grep -nE "message\.(success|error|warning|info)\("` on
`InstructorDashboard.js` finds **57 calls**. 11 were already `t()` calls. The
other **46 spoke a hard-coded English literal**: 31 open on one, and 15 open on
`err.response?.data?.error ||` and fall back to one (both counted by grep at
`d433a94`). The earlier report's "42" matches neither count; I could not
reproduce it and did not need to. The scanner written for
this item (§2) lists all 46 with line numbers; that list is the red evidence.

One component, one `useTranslation()`; `t` is shadowed only inside
`.map(t => …)` callbacks that contain no `message` call, so `t()` is in scope
at all 46.

**Catch blocks that discard the server's reason — 8 sites.** The instruction
was: surface the server's message if it is already bilingual, otherwise keep
the catalogue string. The backend side was inventoried from `core/urls.py`
outward:

| Site | Route | Server's refusals | Decision |
|---|---|---|---|
| Save schedule; Generate & save (2) | `POST games/<id>/round-schedule/` | English-only f-strings naming `round_id`/`game_id` (`course.py:764-803`), **except** the lifecycle boundary's `competition_course_unowned`, which is `cohort_message` + `language_for_request` | surface **only** that coded refusal; otherwise catalogue |
| Save rubric | `grading-categories/` (DRF `ModelViewSet`) | DRF field errors, English, keyed by field | catalogue |
| Seed rubric | `POST grades/seed-rubric/` | `'course_id is required.'` | catalogue |
| Export team / student grades (2) | `GET grades/export/*` (blob) | `'instance_id is required.'`; body arrives as a Blob | catalogue |
| Create course / section (2) | DRF `ModelViewSet` | DRF field errors, English | catalogue |
| Update student | `PUT roster/` `action=update` | `'enrollment_id is required.'`, `'Enrollment not found.'` | catalogue |

The 15 sites that already showed `err.response?.data?.error || '<English>'`
keep the server's reason first and now fall back to the catalogue. **Those
server reasons are still mostly English** (see D3); I did not suppress them,
because replacing "Cannot change home markets after Round 1 decisions have
been submitted" with "保存团队配置失败" trades a language defect for an
information defect, and the instruction covered discarding catch blocks only.

### Item 2 — `under_minimum` (N2)

Open as recorded. `_handle_assign` (`core/views/course.py:672-675`) returns
`under_minimum: [{team_id, team_name, member_count, minimum, detail}]`, `detail`
rendered by `cohort_message('team_under_minimum', language=…)` — already
bilingual. `grep -rn under_minimum frontend/…/src` found one hit, a test
fixture. Nothing displayed it.

### Item 3 — analyst refusals (N4)

Open as recorded. `core/rag/views.py`: the 429 was
`f'Query limit reached ({max_queries} per round).'`; the 503 was
`f'Research system unavailable: {str(e)}'`. The purchase **is** deleted on
failure. **The assignment said that deletion has an existing test; at head it
did not** — no test in the tree drives the 503 path (`grep` for the route, the
view and the sentence: only `test_paid_research`'s happy path and an import in
`test_engine`). One is added here as a contract pin.

The frontend **already showed** `err.response.data.error`, in a toast. So the
"generic failure" half of N4 was not true at head; what was wrong is that a
sentence telling a student whether they were charged lived for three seconds.

---

## 2. What changed

**Item 3 (`05967b2`).**
`participant_messages.py`: `analyst_query_limit_reached`, `analyst_unavailable`
(both languages; the file is inside `check-participant-strings`' catalogue
scope). `rag/views.py`: both refusals come from the catalogue via
`language_for_request(request)` — the safe resolver, not the raw
`get_user_language()` the neighbouring refusals use (D5); the `except` no longer
binds the exception into the response and calls `logger.exception(...)` with
the purchase id, game, team and round. The delete-on-failure line is untouched.
`MarketResearchPage.js`: the refusal is kept on the tab in a closable error
`Alert` until the next question (server's text verbatim; `query_failed` only
when the server sent none); the typed question is kept; on a 429 the tab
re-reads `research/queries/`, because a 429 the client did not predict means a
teammate used the quota from another screen and this tab's count is stale.

**Item 2 (`b244e73`).** `assignmentOutcome()` carries `underMinimum` (the
server's `detail` sentences, verbatim). `announceAssignment()` hands them to an
`onUnderMinimum` callback on every response the server actually gave, including
an empty list, which withdraws the notice; an `unconfirmed` response leaves the
standing notice alone. `UnderMinimumNotice` is a standing warning `Alert` above
the roster's assignment panel. **Not a toast and not a modal, deliberately:** a
team is short for the whole time it is being filled, so an interruption per
click would be noise. It never changes `kind`; the success toast still fires.
All three `assignStudents()` call sites pass it; the notice is cleared when the
section changes. Two locale keys. The backend comment "The console shows it" is
now true and was left alone.

**Item 1 (`4856d89`).** 46 literals → 39 `instructor.msg_*` keys (duplicates
share a key: both "Game activated" variants, both resume/reset/upload-failed
pairs), EN and zh-CN, one `t()` call per key, **no computed keys**.
`bilingualServerReason.js`: returns the server's `error` only when `code` is one
of three codes that are `cohort_messages` refusals
(`competition_course_unowned`, `team_count_refused`, `section_full`); used by
the two schedule saves. `instructorDashboardMessages.test.js`: cuts every
`message.*(` call out of the source with its balanced argument list, sets the
`t()` keys aside, and fails on any remaining string or template literal that
contains a letter — so it catches a call that opens on a literal **and** one
that falls back to a literal after `||` — and fails on a `t(` whose first
argument is not a quoted key. It asserts it found ≥ 50 calls, so it cannot pass
by finding nothing, and it tests its own scanner on seven snippets.

English wording was lightly normalised while moving ("Failed to activate" →
"Failed to activate the game"; the two "Game activated" variants became one
sentence). No meaning changed.

---

## 3. Red, then green

| # | Test | Red | Green |
|---|---|---|---|
| 1 | `core.tests.test_paid_research.AnalystRefusalTests` (3) | `FAILED (failures=6)`, 15.0 s wall. `'Query limit reached (3 per round).' != '您的团队本回合的 3 次…'` (zh and en sub-tests); `no logs of level ERROR or higher triggered on core.rag.views`. Run with the two catalogue entries **already added**, so the red is the view's behaviour, not a `KeyError`. | `Ran 3 tests … OK`, 10.6 s |
| 2 | `MarketResearchPage.analyst.test.js` (3 new of 8) | `3 failed, 5 passed` — `Unable to find an element by: [data-testid="analyst-refusal"]` ×3 | `8 passed` |
| 3 | `assignmentOutcome.test.js` + `assignmentCallSites.test.js` | `9 failed, 10 passed`: 7 new tests, the call-site guard, and the two existing `toEqual` shape pins that I changed to include `underMinimum` | `19 passed` |
| 4 | `instructorDashboardMessages.test.js` | `1 failed, 9 passed`: the offender list, 46 lines, e.g. `line 263: 'Failed to create game'`, `line 1790: \`Created ${…} students from ${file.name}\`` | passed (in the 94) |
| 5 | `bilingualServerReason.test.js` source check | `1 failed, 3 passed`, run before the dashboard edit. **The failing assertion in that run was my own miscount** (`Expected: 2 / Received: 3` `updateRoundSchedule` call sites; the third is a silent save-on-blur, D6c); the surfaced-sites assertion behind it was never separately observed red, though the source had zero matches at the time. | passed |

**Distrust these reds.**
- Row 1's third test, `test_an_unanswered_question_is_not_charged`, was red in
  the first run **only because I had wrapped it in `assertLogs`**. I removed
  that; it is a contract pin, green at head, and is labelled so in its
  docstring. The no-charge behaviour was already correct.
- Row 2 is red on a `data-testid` that did not exist. It proves the refusal is
  now persistent; it does **not** prove head hid the server's text — head
  showed it, in a toast.
- Row 3's render test and row 5's unit tests are red-by-absence of a new
  export. The behavioural reds in row 3 are the `announceAssignment` tests and
  the call-site guard.
- `test_the_short_team_report_is_localised_for_a_zh_instructor` (backend) was
  **never red**: the server was already correct. It pins the shape the console
  now prints verbatim.

## 4. Commands, results, durations

Backend, all through
`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`
(disposable Postgres; the production database and `/etc/globalstrat-plus.env`
were never read):

| Labels | Result | Wall |
|---|---|---|
| `core.tests.test_paid_research.AnalystRefusalTests` (red) | `FAILED (failures=6)` | 15.0 s |
| same (green) | `Ran 3 tests — OK` | 10.6 s |
| `core.tests.test_cohort_caps` | `Ran 30 tests — OK` | ~12 s |
| `core.tests.test_paid_research core.tests.test_cohort_caps core.tests.test_player_language_guard core.tests.test_crv2_12_language core.tests.test_engine.TestRAGInfrastructure core.tests.test_engine.TestArticleIngestion` (final, at `05428a3`) | `Ran 91 tests in 2.4s — OK` | 14.0 s |

Frontend, in `frontend/globalstrat-frontend` (`npm ci`, 21 s):

| Command | Result |
|---|---|
| `CI=true npx react-scripts test --watchAll=false` | 15 suites, 94 tests, all passed, 3.4 s (head: 13 suites, 69 tests) |
| `python3 backend/scripts/check-participant-strings` | `PASS 4679 unit(s) examined, 0 reviewed suppression(s)`; 27 computed keys not resolved — unchanged from head. My scanner test briefly raised that to 29 (a `'t(KEY'` string and a comment quoting a ternary); reworded, back to 27. |
| `python3 backend/scripts/check-participant-strings-selftest` | `34 ok, 0 failed` |
| `CI=false BUILD_PATH=<scratch> npx react-scripts build` + `node eslint-warning-count.js build.log` (the CI recipe in `.github/workflows/frontend.yml`) | build exit 0, 22 s; `eslint warnings: 55 (baseline 57)` — the same 55 the previous report measured, so none added. Baseline file not lowered: shared file, not my warnings. |
| `generate_inventory.py --check` | stale → regenerated at `05428a3` (2,260 → 2,278 rows) → `--check` exit 0 |

## 5. zh-CN sentences authored here — for one native review

Terms were taken from `zh-CN.json` where they exist: 游戏 (game), 回合, 日程,
评分标准 (rubric), 归档, 激活, 班级 (section), 课程, 总部市场 (home market),
分析师, 查询, and the button labels "保存日程" / "保存配置" quoted exactly.
Note `cohort_messages.py` says 比赛 for a game and the frontend catalogue says
游戏; I followed whichever file I was in, so the two still differ (D4).

Backend, `participant_messages.py`:

| Key | zh-CN |
|---|---|
| `analyst_query_limit_reached` | 您的团队本回合的 {maximum} 次分析师查询机会已用完，因此本次问题未提交，也未产生费用。下一回合可继续提问。 |
| `analyst_unavailable` | 分析师服务暂时不可用，因此您的问题未得到回答，也未产生费用。请几分钟后重试；如问题持续出现，请告知教师。 |

Frontend, `zh-CN.json`, all under `instructor.`:

| Key | zh-CN |
|---|---|
| `teams_under_minimum` | 有 {{count}} 个团队的人数低于下限 |
| `teams_under_minimum_note` | 此提示不会阻止任何操作，分配结果已保存。请在比赛开始前为这些团队补充成员。 |
| `msg_game_created` | 游戏"{{name}}"已创建，共 {{teams}} 个团队。 |
| `msg_create_game_failed` | 创建游戏失败 |
| `msg_event_injected` | 事件已注入 |
| `msg_inject_event_failed` | 注入事件失败 |
| `msg_schedule_saved` | 回合日程已保存 |
| `msg_schedule_save_failed` | 保存回合日程失败 |
| `msg_schedule_generated_saved` | 已保存 {{count}} 个回合的日程。 |
| `msg_schedule_generated_not_saved` | 日程已生成，但未能保存。请点击"保存日程"重试。 |
| `msg_game_activated` | 游戏已激活，第1回合现已开放。 |
| `msg_activate_failed` | 激活游戏失败 |
| `msg_game_resumed` | 游戏已恢复 |
| `msg_resume_failed` | 恢复游戏失败 |
| `msg_game_reset` | 游戏已重置为初始设置 |
| `msg_reset_failed` | 重置游戏失败 |
| `msg_game_archived` | 游戏已归档。现在可以为本班级创建新游戏。 |
| `msg_archive_failed` | 归档游戏失败 |
| `msg_game_deleted` | 游戏已删除。现在可以创建新游戏。 |
| `msg_delete_failed` | 删除游戏失败 |
| `msg_team_config_save_failed` | 保存团队配置失败 |
| `msg_random_previewed` | 已预览随机分配结果。请点击"保存配置"使其生效。 |
| `msg_randomize_failed` | 随机分配总部市场失败 |
| `msg_weights_must_total` | 权重合计必须为 100%（当前为 {{total}}%） |
| `msg_rubric_updated` | 评分标准已更新 |
| `msg_rubric_save_failed` | 保存评分标准失败 |
| `msg_default_rubric_created` | 默认评分标准已创建 |
| `msg_seed_rubric_failed` | 创建默认评分标准失败 |
| `msg_no_team_grades_to_export` | 暂无可导出的成绩，请先计算成绩。 |
| `msg_no_student_grades_to_export` | 暂无可导出的学生成绩 |
| `msg_course_created` | 课程已创建 |
| `msg_create_course_failed` | 创建课程失败 |
| `msg_section_created` | 班级已创建 |
| `msg_create_section_failed` | 创建班级失败 |
| `msg_student_added` | 学生已添加 |
| `msg_add_student_failed` | 添加学生失败 |
| `msg_roster_uploaded_from_file` | 已从 {{file}} 创建 {{count}} 名学生 |
| `msg_roster_uploaded` | 已创建 {{count}} 名学生 |
| `msg_upload_failed` | 上传失败 |
| `msg_student_updated` | 学生信息已更新 |
| `msg_update_student_failed` | 更新学生信息失败 |

One inconsistency a reviewer should rule on: `teams_under_minimum_note` says
比赛开始前 because the server sentence printed directly above it
(`team_under_minimum`) says 比赛开始前; every other key here says 游戏.

## 6. New defects found — recorded, NOT repaired (none is inside the three items)

**D1 (P2 candidate). A failed analyst query leaves a purchase audit event with
no purchase.** `ResearchQueryView` writes
`record_decision_event(…, 'purchase_research_report', …)` inside the charge
transaction, which commits; on the 503 path the purchase row is then deleted
and nothing compensating is written. The audit trail shows a purchase the
ledger does not. The `DecisionSubmission` the view may have created also
stays. Team is not charged (pinned). Audit semantics — not mine to change.

**D2 (P2 candidate). Four more English-only sentences on the analyst route**,
all student-facing: `Game or team not found.` (404),
`Market research AI is not enabled for this scenario.` (400),
`Query text is required.` (400), and — the important one — the **charged**
200 answer `No relevant research found for this query. Try broadening…`, which
is returned in English to a zh-CN team and costs the full price. The assignment
named two refusals; these are recorded, not repaired.

**D3 (observation, large). Operator routes refuse almost entirely in English.**
Of the routes behind the dashboard's toasts, only three refusals are bilingual
(`competition_course_unowned`, `team_count_refused`, `section_full`). Everything
else — activate/pause/resume/reset/archive, team-config, inject-event,
round-schedule, roster update, grading, courses/sections (DRF defaults) — is an
English literal, several naming storage fields (`enrollment_id is required.`,
`Round 7 not found in game 3.`). After this branch the 17 toasts that show the
server's reason first will therefore still show English to a Chinese-language
instructor whenever the server gives one. The repair is backend catalogue work
per route, plus widening `BILINGUAL_REFUSAL_CODES`.

**D3a (P2 candidates, from the same inventory; not verified by execution).**
`{'error': str(e)}` returns raw exception text on roster add
(`course.py:422`) and per CSV row (`:357`). `PUT roster/` has no ownership
check and carries no `game_id`, so the game-scope guard never fires: any
instructor can rename any student. `GameDeleteView` is not on the lifecycle
boundary (no audit row, no reason, no competition-ownership check). `Section`
accepts `max_teams: 9999` / `team_size_max: 0`, which `cohort_caps` then reads
as the authored cap. Several routes 500 on a non-numeric id. **These came from
a read-only source sweep by a sub-agent; I did not drive any of them.**

**D4 (observation).** 比赛 (backend `cohort_messages`) vs 游戏 (frontend
catalogue) for "game".

**D5 (P3 candidate).** `ResearchQueryView` resolves the language for its older
refusals with raw `get_user_language()`, which returns whatever
`Enrollment.language` holds; `participant_message()` raises `KeyError` on a
language it has no entry for (unlike `cohort_message`, which falls back to
English). An enrollment with any value other than `en`/`zh-CN` would turn a
refusal into a 500. My two new refusals use `language_for_request()`.

**D6 (observations, `InstructorDashboard.js`, outside `message.*`).**
(a) CSV upload reports `Created N students` and **never reads the per-row
`errors`** the server returns with its 201 — the same shape of defect as
V2-104, on the roster: rows refused by the section cap vanish silently.
(b) Both export catch blocks assert a cause ("No grades to export") for *any*
failure, including a 403 or 500. (c) The deadline field's save-on-blur swallows
every failure silently. (d) English JSX remains: `{n} student(s)`,
`{n} teams · x/y students assigned`, the whole `marketTooltip`
(`Growth: … | Tariff: …`, `volatile/moderate/stable`), the CSV placeholder.
The new guard polices `message.*` calls only and says so.

## 7. Not verified

- **Nothing was observed in a browser.** `AskAnalystTab` and
  `UnderMinimumNotice` are rendered for real by Jest; **`InstructorDashboard`
  itself is never rendered by any test.** The 46 toast changes, the notice's
  placement, its clearing on section change, and the three `onUnderMinimum`
  wirings are proven by source scans plus unit tests of the shared functions.
  A typo'd key cannot slip through (`check-participant-strings` A8 resolves
  every literal key), but a wrong-but-existing key could.
- **All 43 zh-CN sentences were written by me and not reviewed by a native
  reader.**
- The 503 test injects a `RuntimeError` at `get_embedding`. Failures raised
  elsewhere in the `try` (Qdrant search, synthesis, the `ResearchQueryLog`
  insert) take the same `except`, by reading, not by test.
- `logger.exception` was asserted with `assertLogs`; where `core.rag.views`
  logs go in the deployed logging config was not checked.
- The re-read on 429 assumes `research/queries/` returns the current round's
  rows to a team member; shown by the existing price tests, not re-proved for
  a second teammate.
- Auditor preflight, applicable items: inventory started from `urls.py`
  (yes, for every discarding catch site); alternate entry point for the
  analyst charge — none found, `research/query/` is the only writer of an
  `ANALYST_QUERY` purchase; negative tests prove no write (no purchase row and
  no `ResearchQueryLog` row after a 429 or a 503, quota still 3).
- No full backend suite, load, walkthrough or replay, by instruction.

## 8. Proposed register text (for the auditor to apply or reject)

**New row — instructor console toasts (was N3):**
> **Repaired, pending closure.** `4856d89`: the 46 hard-coded English
> `message.*` announcements in `InstructorDashboard.js` read 39
> `instructor.msg_*` catalogue keys in both languages; a source-scan Jest guard
> fails on a literal or a computed key. **Residual, separate:** the server
> reasons those toasts show first are still English-only on nearly every
> operator route (D3), and non-toast English remains in the component (D6d).
> Unobserved on screen; zh-CN unreviewed.

**New row — `under_minimum` (was N2), V2-042 territory:**
> **Repaired, pending closure.** `b244e73`: the assign response's
> `under_minimum` is shown as a standing, non-blocking warning above the roster
> in the server's own bilingual wording; all three call sites wired, source
> guard added. Unobserved on screen. Teams with zero members are not reported
> by the server (`under_minimum_teams` walks enrolled members), unchanged.

**New row — analyst refusals (was N4), append to V2-094's neighbourhood:**
> **Repaired, pending closure.** `05967b2`: the 429 and 503 of
> `research/query/` are `participant_messages` entries in the request's
> language; the 503 no longer carries exception text (logged server-side); the
> tab keeps the refusal on screen and re-reads the quota on a 429. No-charge on
> failure now has a test (it had none). **Still open, separate:** the charged
> "No relevant research found" answer and three other refusals on the route
> are English-only (D2); a failed query leaves a purchase audit event with no
> purchase (D1).
