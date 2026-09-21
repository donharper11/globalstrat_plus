# The remaining English refusals, converted

**Date:** 2026-09-21
**Branch:** `crv2-12-remaining-english-refusals`, cut from `crv2-release-integration` at `87c92dc` (verified an ancestor before anything was touched)
**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`
**Input:** §6 of `ANALYST_AUDIT_AND_ROSTER_UPLOAD_2026-09-21.md` — "62 English-only refusal literals left unconverted (14 instructor-side, 48 student-facing)", the round-control success messages, and the English fallbacks in `RoundControlCard.js` and `StudentAccountsPanel.js`.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md` and the `OWNER_RULINGS` files were not edited; §9 proposes register text for the auditor to apply or reject.

Commits (oldest first):

| Commit | What |
|---|---|
| `299259f` | Backend: every literal in the re-derived inventory; the confirmations; the two scope guards; the two services; the governance notices; the widened source scans |
| `be1fa41` | Frontend: `RoundControlCard`, `StudentAccountsPanel`, the supply-chain panel's announcements, antd's own locale |
| `30e7864` | Frontend: a refused login no longer reloads the page (**the one non-wording change; separate so it can be dropped**) |
| `94fea43` | Backend: `core/permissions.py` messages |
| `a81136b` | Frontend: the login request carries no left-over token (follow-up to `30e7864`) |
| `5b4ce4d` | Frontend: R&D page announcements, student sidebar, a dozen one-word fallbacks; tree-wide guard |
| `6e73974` | Backend: `str(exception)` handed to the instructor (game creation, event engine) |
| `a02ae01` | Backend: **the pause guard middleware**; the set-password refusal |
| `f3308bf` | Backend: the legacy programme cap |
| `2834ab4` | Line endings only (see §4, "a defect of my own") |
| *(next)* | This document |
| *(last)* | Regenerated string inventory, in its own commit |

---

## 1. The inventory, re-derived at head

The line numbers in the input had moved (the ownership merge), so nothing was taken from them. The list below is what the **final** guard scanner (`english_refusal_literals` in `core/tests/test_operator_refusal_language.py`) finds when run over the tree **as it was at `87c92dc`** — every view module, the scope middleware, `services/lifecycle.py` and the two services whose refusals a view passes straight on. 102 sites.

Reconciliation with the input's 62:

* Restricted to what the previous scan looked at (`core/views/*.py`, `core/rag/views.py`, `services/lifecycle.py`; keys `error` / `detail`; `Lifecycle*(<literal>)`), and counted the way it counted, the figure at `87c92dc` is **61**: the 62, less `scenario_views.py:97`, which `4fff45c` converted after that report was written.
* The split the input gave (14 / 48) is, at head, **15 instructor-side / 46 student-facing**: the 13 instructor-side sites that remained after `4fff45c`, plus `events.py`'s two, which the input counted as student-facing but which sit behind `IsInstructor`.
* The other 41 of the 102 are sites the previous scan could not see, found by widening the scanner rather than by reading: the `message` / `warning` / `reason` keys (22 — the six round-control confirmations the task names, and sixteen more like them); two conditionals (`'Modified' if … else 'No changes'`), and a **name bound to a literal** (`msg = f'…'` … `{'message': msg}` — this is how the advance, deadline and extend-deadline confirmations were written, and a key-only scan passes them); the two scope-guard middleware answers; twelve refusals in `services/persona_engine.py` and `services/r_and_d.py` that a view returns untouched; and three `{'error': str(exc)}`.

| # | File:line (at `87c92dc`) | Class | Kind | Text (start) |
|---|---|---|---|---|
| 1 | `core/views/auth.py:215` | `LoginView` | error literal | Invalid username or password. |
| 2 | `core/views/auth.py:190` | `LoginView` | error literal | Username is required. |
| 3 | `core/views/auth.py:196` | `LoginView` | error literal | Password is required. |
| 4 | `core/views/auth.py:229` | `LoginView` | error literal | No password is set for this account.  |
| 5 | `core/views/auth.py:329` | `CurrentUserView` | error literal | User not found. |
| 6 | `core/views/auth.py:355` | `LanguagePreferenceView` | error literal | Unsupported language |
| 7 | `core/views/auth.py:247` | `LoginView` | error literal | Your account has not been assigned to a team yet. Please contact your instructor. |
| 8 | `core/views/briefing.py:73` | `BriefingReadView` | error literal | user_id required |
| 9 | `core/views/cc15_views.py:248` | `FrameworkAnalysisView` | message literal | Analysis saved. |
| 10 | `core/views/cc15_views.py:609` | `ForecastScenarioView` | message literal | Scenario saved. |
| 11 | `core/views/cc15_views.py:219` | `FrameworkAnalysisView` | error literal | framework_type is required |
| 12 | `core/views/cc15_views.py:465` | `ForecastView` | message literal | No round found. |
| 13 | `core/views/cc15_views.py:472` | `ForecastView` | message literal | No draft decisions yet. |
| 14 | `core/views/cc31j_views.py:102` | `-` | message literal | Your {", ".join(below_market_pools)} salary is Below Market. Pay transparency is exposing  |
| 15 | `core/views/cc31j_views.py:114` | `-` | message literal | You have JV partnerships in {", ".join(jv_markets)}. Anti-corruption monitoring adds $100K |
| 16 | `core/views/cc31j_views.py:126` | `-` | message literal | You use contract manufacturing in {", ".join(contract_mfg_markets)}. Audit may expose labo |
| 17 | `core/views/cc31j_views.py:141` | `-` | message literal | Total ESG investment is only ${cumulative:,.0f}. Reporting without substance is seen as gr |
| 18 | `core/views/cc32a_views.py:123` | `CommunicationDraftView` | detail literal | No active round. |
| 19 | `core/views/cc32a_views.py:159` | `CommunicationSubmitView` | detail literal | No active round. |
| 20 | `core/views/cc32a_views.py:177` | `CommunicationSubmitView` | detail literal | Already submitted. Cannot resubmit. |
| 21 | `core/views/cc32a_views.py:187` | `CommunicationSubmitView` | detail literal | Cannot submit empty communication. |
| 22 | `core/views/cc32a_views.py:190` | `CommunicationSubmitView` | detail literal | Exceeds word limit. Maximum {ca.word_limit} words, you have {tc.word_count}. |
| 23 | `core/views/cc32b_views.py:127` | `OrgStructureContextView` | error literal | structure_id required |
| 24 | `core/views/cc32b_views.py:146` | `OrgStructureContextView` | error literal | Already using this structure |
| 25 | `core/views/cc32b_views.py:151` | `OrgStructureContextView` | error literal | Cannot switch during an active transition |
| 26 | `core/views/cc32b_views.py:183` | `OrgStructureContextView` | error literal | No current round for this game. |
| 27 | `core/views/cc32b_views.py:45` | `OrgStructureContextView` | error literal | Game or team not found |
| 28 | `core/views/cc32b_views.py:123` | `OrgStructureContextView` | error literal | Game or team not found |
| 29 | `core/views/cc32b_views.py:134` | `OrgStructureContextView` | error literal | Structure not found |
| 30 | `core/views/cc32b_views.py:213` | `OrgStructureContextView` | error literal | Insufficient cash. This switch would take committed  |
| 31 | `core/views/cc32c_views.py:119` | `TaxStructureContextView` | error literal | structure_code required |
| 32 | `core/views/cc32h_views.py:19` | `RoundStatusView` | error literal | No rounds found |
| 33 | `core/views/core.py:147` | `UserViewSet` | error literal | No CSV data provided. |
| 34 | `core/views/core.py:306` | `DashboardViewSet` | error literal | team_id is required |
| 35 | `core/views/core.py:168` | `UserViewSet` | error literal | Missing username |
| 36 | `core/views/core.py:311` | `DashboardViewSet` | error literal | team_id must be an integer |
| 37 | `core/views/core.py:323` | `DashboardViewSet` | error literal | Team not found |
| 38 | `core/views/core.py:235` | `UserViewSet` | error literal | Team not found. |
| 39 | `core/views/core.py:185` | `UserViewSet` | error literal | Invalid team_id: {team_id} |
| 40 | `core/views/course.py:342` | `RosterViewSet` | detail literal | Enrollment removed. |
| 41 | `core/views/course.py:1053` | `DecisionStatusView` | detail literal | 'Modified' if … else 'No changes' |
| 42 | `core/views/course.py:1060` | `DecisionStatusView` | detail literal | {challenges_submitted}/{challenges_available} submitted |
| 43 | `core/views/course.py:1069` | `DecisionStatusView` | detail literal | 'Submitted' if … else 'Pending' |
| 44 | `core/views/course.py:1104` | `SendReminderView` | error literal | instance_id is required. |
| 45 | `core/views/course.py:991` | `DecisionStatusView` | error literal | No active round. |
| 46 | `core/views/course.py:997` | `DecisionStatusView` | error literal | Round not found. |
| 47 | `core/views/course.py:1100` | `SendReminderView` | error literal | Round not found. |
| 48 | `core/views/decisions.py:1069` | `DecisionUnlockView` | LifecycleConflict literal | Round {round_number} has already been processed;  |
| 49 | `core/views/decisions.py:1077` | `DecisionUnlockView` | LifecycleConflict literal | Submission is not locked. |
| 50 | `core/views/events.py:43` | `FireEventsViewSet` | error literal | round_number and game_id are required |
| 51 | `core/views/events.py:52` | `FireEventsViewSet` | error literal | round_number and game_id must be integers |
| 52 | `core/views/events.py:62` | `FireEventsViewSet` | error str() | `str(e)` — the event engine's exception text |
| 53 | `core/views/gamification.py:78` | `QicoinView` | error literal | team_id is required |
| 54 | `core/views/gamification.py:82` | `QicoinView` | error literal | team_id must be an integer |
| 55 | `core/views/grading.py:144` | `CalculateGradesView` | error str() | `str(exc)` — `ModelDerivedComponentInCompetition` |
| 56 | `core/views/instructor_accounts.py:172` | `StudentPasswordResetView` | message literal | Password updated for {user.username}. |
| 57 | `core/views/instructor_accounts.py:222` | `BulkPasswordResetView` | message literal | Reset {len(updated)} password(s) to the student ID default. |
| 58 | `core/views/instructor_accounts.py:212` | `BulkPasswordResetView` | reason literal | no student_id or username |
| 59 | `core/views/instructor_sc.py:237` | `InstructorInjectSCEventView` | LifecycleConflict literal | Round {rnd.round_number} is "{rnd.status}"; an event  |
| 60 | `core/views/instructor_sc.py:250` | `InstructorInjectSCEventView` | message literal | "{template.name}" queued — fires when round  |
| 61 | `core/views/mixins.py:43` | `DecisionLockedMixin` | error literal | Decisions are locked for this round. |
| 62 | `core/views/onboarding.py:24` | `OnboardingDataView` | error literal | game_id and team_id required |
| 63 | `core/views/onboarding.py:91` | `OnboardingCompleteView` | error literal | user_id required |
| 64 | `core/views/onboarding.py:100` | `OnboardingCompleteView` | error literal | No active enrollment found |
| 65 | `core/views/onboarding.py:30` | `OnboardingDataView` | error literal | Game not found |
| 66 | `core/views/onboarding.py:35` | `OnboardingDataView` | error literal | Team not found |
| 67 | `core/views/persona_engine.py:33` | `PersonaReplyView` | error literal | team_id, message_id, and reply_text are required |
| 68 | `core/views/persona_engine.py:65` | `PersonaConsultView` | error literal | team_id, persona_key, and question are required |
| 69 | `core/views/persona_engine.py:117` | `ConsultationUsageView` | error literal | team_id is required |
| 70 | `core/views/programs.py:104` | `ProgramViewSet` | error literal | Platform has no team_id. |
| 71 | `core/views/programs.py:123` | `ProgramViewSet` | error literal | team_id is required |
| 72 | `core/views/programs.py:151` | `ProgramPortfolioViewSet` | error literal | Platform "{platform.program_name}" is still in  |
| 73 | `core/views/research_reports.py:137` | `ResearchReportsView` | error literal | Unknown report type: {report_type} |
| 74 | `core/views/resources.py:63` | `ResourceSearchView` | error literal | query is required |
| 75 | `core/views/results_api.py:824` | `InstructorAdvanceRoundView` | message literal | {game.name}: round advanced to  |
| 76 | `core/views/results_api.py:886` | `InstructorInjectEventView` | message literal | Event "{template.name}" injected. |
| 77 | `core/views/results_api.py:963` | `InstructorExtendDeadlineView` | message literal | {game.name}: deadline extended by {hours} hour(s). [+ The round was closed, so it has been reopened …] (a name bound to a literal) |
| 78 | `core/views/round_control.py:197` | `RoundCloseView` | message literal | {game}: round {n} closed. {m} submission(s) locked. |
| 79 | `core/views/round_control.py:269` | `RoundReopenView` | message literal | {game.name}: round {round_obj.round_number}  |
| 80 | `core/views/round_control.py:350` | `RoundProcessView` | message literal | {game.name}: round {result["processed_round"]}  |
| 81 | `core/views/round_control.py:419` | `RoundAdvanceView` | message literal | {game}: round {n} was the last round. Game complete. / {game}: advanced to round {n}. (a name bound to a literal) |
| 82 | `core/views/round_control.py:490` | `RoundDeadlineView` | message literal | {game}: deadline updated. / {game}: deadline cleared. |
| 83 | `core/views/round_control.py:490` | `RoundDeadlineView` | warning literal | That deadline is in the past — the round will close within a minute. |
| 84 | `core/views/scenario_views.py:483` | `GameArchiveView` | message literal | Game archived. Section is now free for a new game. |
| 85 | `core/views/scenario_views.py:261` | `GameCreateView` | error str() | `str(exc)` — `GameCreationError` |
| 86 | `core/views/strategic_impact.py:35` | `StrategicImpactView` | error literal | Game or team not found |
| 87 | `core/rag/views.py:57` | `ActiveEventsView` | error literal | Game not found. |
| 88 | `core/rag/views.py:135` | `EventHistoryView` | error literal | Game not found. |
| 89 | `core/middleware.py:256` | `TeamScopeGuardMiddleware` | detail literal | You do not have access to this team. |
| 90 | `core/middleware.py:356` | `GameScopeGuardMiddleware` | error literal | This game belongs to another instructor. |
| 91 | `core/services/persona_engine.py:1055` | `-` | error literal | Message not found |
| 92 | `core/services/persona_engine.py:1058` | `-` | error literal | Message does not belong to this team |
| 93 | `core/services/persona_engine.py:1066` | `-` | error literal | Maximum {MAX_REPLIES_PER_THREAD} replies per conversation reached |
| 94 | `core/services/persona_engine.py:1072` | `-` | error literal | Consultation limit reached ({MAX_CONSULTATIONS_PER_ROUND} per round) |
| 95 | `core/services/persona_engine.py:1078` | `-` | error literal | Cannot determine persona for this thread |
| 96 | `core/services/persona_engine.py:1098` | `-` | error literal | Advisor is temporarily unavailable |
| 97 | `core/services/persona_engine.py:1143` | `-` | error literal | Invalid persona. Valid: {list(PERSONAS.keys())} |
| 98 | `core/services/persona_engine.py:1150` | `-` | error literal | Consultation limit reached ({MAX_CONSULTATIONS_PER_ROUND} per round) |
| 99 | `core/services/persona_engine.py:1218` | `-` | error literal | Advisor is temporarily unavailable |
| 100 | `core/services/r_and_d.py:139` | `-` | error literal | Platform is not in development. |
| 101 | `core/services/r_and_d.py:141` | `-` | error literal | Platform is already ready. |
| 102 | `core/services/r_and_d.py:153` | `-` | error literal | Insufficient budget. Need ${cost:,.0f},  |

**Outside any dict literal, so found by reading and by driving the routes, not by the scan** — all converted, each with its own test or source guard:

| Where | What | How a person met it |
|---|---|---|
| `core/middleware.py` `BLOCKING_GAME_STATUSES` | 3 English sentences in a module-level table | **Every write a student makes while the instructor has the game paused** (or it is completed / archived). The middleware answers before the decision routes' own bilingual permission is reached, so CRV2-12's Chinese sentence for a paused game was never the one a student saw. Driven red in both languages before the change. The commonest refusal of a live session. |
| `core/permissions.py` | 4 class-level `message = '…'` | The `detail` of the 403 from `IsInstructor`, `IsInstructorOrReadOnly`, `GameIsNotPaused` (the last is referenced by no view) |
| `core/utils/passwords.py` `validate_password` | 2 English sentences returned to the set-password route | Instructor sets a password under 6 characters |
| `core/services/game_creation.py` | 3 `GameCreationError` messages → `{'error': str(exc)}` | Instructor creates a game from a scenario that lacks something |
| `core/services/budget.py` `validate_program_activation` | 2 English f-strings → `{'errors': errors}` | Legacy programme route (not called by the frontend) |
| `frontend/…/pages/RDPage.js` | 4 literals | **A student page**: "All R&D investment slots are already used this round.", "This upgrade exceeds the remaining R&D budget.", the save confirmation and its failure fallback — English for everyone |
| `frontend/…/components/Sidebar.js` | 4 literals | **The student sidebar** named Sourcing, Logistics, Trade Finance and Inventory in English whenever the interface was Chinese (the scenario's own labels are deliberately dropped for zh-CN, and the fallback was a literal) |
| `App.js` `ConfigProvider` | no `locale` | antd's own words — the OK / Cancel of every Popconfirm and Modal, the date picker, pagination, "No data" — were English for every user, including on the round-control confirmations |
| Twelve more frontend fallbacks | `'Gen 1'`, `` `Level ${n}` ``, `'Export'`, `'Not set'`, `'Unknown'`, `'Rubric'`, `'Game'` ×2, `` `User ${id}` `` ×3, `'The request failed.'`, `'Failed to load the supply-chain panel.'` | Onboarding, corporate strategy, market strategy, instructor dashboard, supply-chain panel |

## 2. What was converted

**Counts.** Of the 102 scanned sites at `87c92dc`: **101 converted, 1 remains** (`grading.py:144`, reason in §6). Of the input's 61: **61 converted, 0 remain.** Of the 14 further backend sentences found outside a dict literal: 14 converted. Frontend: both named components wholly (not only their fallbacks), plus the literals listed above.

**Where the sentences live.** Student-facing text is in `core/utils/participant_messages.py` (62 new keys), instructor-facing in `core/utils/operator_messages.py` (38 new keys: refusals, guidance lines, and 18 confirmations). Both are read by `check-participant-strings` (A1 both languages, A2 same placeholders, A3 no storage names) — it passes.

* `participant_refusal(request, key, *, field='error', **values)` → `{field: sentence, 'code': key}`, the participant-side twin of `operator_refusal`. `field='detail'` keeps the key the communications routes and the team scope guard have always answered under, so no client changes.
* `participant_messages.language_for_request` is now guarded like the cohort one (login and the middleware refuse before any user is known; a refusal must not become a 500 because its language could not be read).
* `service_refusal(key, **values)` / `localise_refusal(request, result)`: a service knows no request. It returns the English sentence plus the key and values; the view re-renders it. Used by `persona_engine` and `r_and_d`; a test asserts every `service_refusal` key exists.
* **No sentence names a storage field.** `team_id is required`, `structure_id required`, `user_id required`, `framework_type is required`, `round_number and game_id must be integers` and their kin became either a sentence about what the *person* left out ("Choose a framework before saving the analysis.") or, where only the page could have left it out, `request_incomplete` ("The page sent an incomplete request, so nothing was done. Reload the page and try again."). The student tests assert a storage-name regex against every refusal they drive.
* English is unchanged to the byte wherever it did not name a storage field; the tests assert it for the confirmations, `Insufficient cash…`, the governance notices and the programme cap, and the login sentences are the old ones verbatim in the catalogue.

**Codes.** Every converted refusal now carries a `code` (additive). `bilingual_codes()` grew from 72 to **90**; `BILINGUAL_REFUSAL_CODES` in `bilingualServerReason.js` was regenerated from it, not typed, and the existing both-directions test holds it. Confirmations use keys prefixed `done_`, which `bilingual_codes()` excludes: a confirmation is not a refusal and never travels as a code (tested).

**What did not change — and how that is held.**

* **No status code.** Every conversion replaced the body expression only. The tests assert the status of each refusal they drive (400 / 401 / 403 / 404 / 409), and the full suite passes.
* **No rule.** Two places needed care. `PersonaReplyView` / `PersonaConsultView` refused one compound condition with one sentence naming three storage fields; the *condition* is untouched and the sentence is now chosen inside it (ids missing → `request_incomplete`; blank text → "Type your reply before sending it."). `validate_password` is now a rendering of `password_problem`, and a test asserts the two cannot disagree.
* **No audit content.** The three lifecycle refusals converted here go through `lifecycle_refusal`, so the operator audit row still records English. Their audit `detail` is asserted **byte-identical** to the pre-conversion f-string, including `Round 1 is "closed"; …` for the supply-chain inject: `stored_round_status()` renders the stored token in English (what the audit row always said) and the label in Chinese (so no Chinese sentence frames `closed`). The game-scope guard's refusal record keeps its English reason; only the response is localised. The convention itself — audit in English — is the previous builder's and is **not decided here** (their Q3 stands).

**The guards, so none of this regrows.**

* `CONVERTED` (the list the task names) gained `DecisionUnlockView`, `instructor_sc.py`, `events.py`, `core.py`'s two viewsets, `course.py`'s `DecisionStatusView` and `SendReminderView`, and `middleware.py`.
* The scanner now reads `message`, `warning`, `detail`, `reason` as well as `error`; follows a conditional and a **name bound to a literal**; and refuses `{'error': str(...)}`. Its self-test covers each shape.
* `WholeTreeRefusalScanTests`: the same scan over **every** view module, the middleware and the two services — not a list of converted files, so a route added tomorrow is covered without being told about it. One reviewed exemption (`grading.py`, §6); the test fails if an exemption stops matching anything.
* `core/permissions.py`: an AST test that no `message` is assigned a literal.
* Frontend: `consolePanelsLanguage.test.js` (the two panels: JSX text, spoken props, literal fallbacks, computed keys, every key present in both catalogues), `announcementsLanguage.test.js` (**every file under `src/`**: a `message.*(` call that opens on words, an `||` / `??` that ends in them), `antdLocale.test.js`, `api/client.test.js`.

## 3. Red, then green

Each backend red below was run through the real routes with the catalogue entries **already present**, so the red is the view, not a `KeyError`.

| # | Tests | Red | Green |
|---|---|---|---|
| 1 | `test_operator_refusal_language` + new `test_student_refusal_language`, views unconverted | `Ran 71 — FAILED (failures=73, errors=9)`, 15.8 s. Representative: login in zh-CN answered `'Invalid username or password.'`; every source-scan sub-test for the newly listed files; the whole-tree scan with 95 offenders; the allowlist test; `test_close_then_reopen` and `test_setting_and_clearing_a_deadline` (the confirmations) | `Ran 255 — OK` with the neighbouring suites, 1 m 09 s |
| 2 | `GovernanceNoticeLanguageTests` + whole-tree scan, `cc31j_views.py` restored to head for the run | `FAILED (failures=4, errors=2)`: `KeyError: 'count'`; `'本土市场、海外市场' not found in 'You have JV partnerships in Home, Away…'` | OK |
| 3 | `PermissionRefusalLanguageTests` | `FAILED (failures=5)`: `'Instructor or Admin access required.' != '此区域仅向教师开放。'`; literal `message` at lines 20, 37, 121, 141 | OK |
| 4 | game creation / event engine / `str()` scan | `FAILED (failures=9)` — but see the note below | OK |
| 5 | **pause guard**, set-password | `FAILED (failures=10, errors=1)`: `'The game is paused by your instructor. No changes can be made right now.' != '教师已暂停游戏。当前无法进行修改。'`, for paused, completed and archived, in both languages | OK |
| 6 | legacy programme cap | `TypeError: … unexpected keyword argument 'language'` | OK |
| 7 | `consolePanelsLanguage.test.js` | `5 failed, 6 passed`; 107 hard-coded strings listed across the two panels and the supply-chain panel's announcements | `11 passed` |
| 8 | `antdLocale.test.js` | `1 failed, 3 passed` (App not yet wired) | passed |
| 9 | `api/client.test.js` | `4 failed` | `5 passed` |
| 10 | `announcementsLanguage.test.js` | 8 offenders; after tightening the scanner to one capitalised word, 5 more | passed |

Honest notes on these reds:

* **Row 1's `errors=9` were not all the defect.** Four were faults in my own new tests (a fixture figure that overflowed a numeric column; an assertion that the audit row carries `guidance`, which it never has; and three sub-test errors from a route that turned out to be dead — §7 F1). They were fixed, or the test dropped, before green, and do not count as evidence. The other errors were the defect (`KeyError: 'code'`).
* **Row 4's two game-creation tests were first red for the wrong reason** — a fixture with no superuser to record the game against, so the route answered 403 before reaching the code under test. After fixing the fixture I re-ran them against the previous view (`scenario_views.py` and `game_creation.py` checked out at `5b4ce4d` for the run, then restored; tree verified clean): `FAILED (failures=4)`, `None != 'game_creation_market_unknown' : {'error': "Market code 'ZZ' not found in scenario …"}`. That is the red that counts.
* Rows 8 and 9: the module tests were written with the module and were never red on their own; the red is the wiring test (8) and the absence of the function (9).
* No behavioural test exists for the legacy routes whose literals were converted but which cannot be reached through a working route (`DecisionStatusView`, `SendReminderView` — F1; `DashboardViewSet`, `DecisionLockedMixin`, `ProgramViewSet` — CSR-era models with no fixture in the suite). They are held by the source scan only. The frontend calls none of them.

## 4. Commands, results, durations

Backend, all through `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>` — a disposable Postgres container per run. The production database and `/etc/globalstrat-plus.env` were never read.

| Labels | Result | Wall |
|---|---|---|
| the two language modules (red, row 1) | `Ran 71 — FAILED (failures=73, errors=9)` | 15.8 s |
| `test_operator_refusal_language test_student_refusal_language test_zh_terminology test_player_language_guard test_crv2_12_language test_org_transition_charge test_refusal_audit test_refusal_audit_integrity test_who_attempted test_game_scope_boundary test_auth_rounds test_console_defects test_paid_research` | `Ran 255 — OK` | 1 m 09 s |
| the language modules + `test_game_creation_paths test_console_defects test_zh_terminology` after batch 4 | `Ran 93 — OK` | 15 s |
| the language modules + `test_auth_rounds test_console_defects test_crv2_12_language test_player_language_guard test_zh_terminology` after the pause guard | `Ran 178 — OK` | 34 s |
| **`core --parallel 8` at `f3308bf`** | **`Ran 1388 tests in 110.4s — OK`, exit 0** | 3 m 59 s |
| **`core --parallel 8` at `2834ab4` (final)** | **`Ran 1388 tests in 103.4s — OK`, exit 0** | 2 m 00 s |

**Two full runs, not one, and why — a defect of my own.** After the first full run I checked the diff against the base and found six legacy files (`budget.py`, `r_and_d.py`, `gamification.py`, `mixins.py`, `persona_engine.py` the view, `resources.py`) showing as whole-file rewrites: they are CRLF in the tree, and my edit scripts had written them back as LF. No content differed, but it buried a few changed lines in 800 lines of noise, so I restored the endings (`2834ab4`) — and since that changes the bytes of runtime files, ran the full suite again rather than argue it was harmless. **No runtime file changed after the second run**: the one later experiment (row 4's re-observed red) checked two files out at an older commit and back, and `git status` was verified clean at `2834ab4` afterwards. `git diff --check` reports "trailing whitespace" on the added lines of those six files; that is the CR of a CRLF file and is true of every line in them.

Frontend, in `frontend/globalstrat-frontend` after `npm ci`, all at `2834ab4`:

| Command | Result |
|---|---|
| `CI=true npx react-scripts test --watchAll=false` | **22 suites, 171 tests, all passed**, 3.6 s (base: 17 suites, 137 tests) |
| `python3 backend/scripts/check-participant-strings` | `PASS 5191 unit(s) examined, 0 reviewed suppression(s)`; 27 computed keys unresolved — **unchanged**, none added |
| `python3 backend/scripts/check-participant-strings-selftest` | `34 ok, 0 failed` |
| `CI=false BUILD_PATH=<scratch> npx react-scripts build`, then `node eslint-warning-count.js build.log` (the CI recipe) | build exit 0; `eslint warnings: 55 (baseline 57)` — the same 55 as the previous report. Baseline file not lowered: shared file, not my warnings |
| `python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py`, then `--check`, from the repository root | see the last commit |

Locale files were edited textually (an insertion after one known line of a section, the file re-parsed and each new key asserted to have landed in the intended section), never re-serialised.

## 5. zh-CN — the complete list for one native review

**224 new sentences, all written by me, none read by a native speaker.** No existing sentence was changed (checked mechanically against the base: zero changed keys in all three catalogues). Terminology follows `test_zh_terminology` (游戏, 回合, 团队, 教师; no 比赛 / 队伍 / 小组 / 轮; no new 竞赛, so `COMPETITION_KEYS` is unchanged) and that test passes. Students are addressed as 您, as the rest of the participant catalogue does.

The choices I am least sure of, for the reviewer to look at first:

* `communication_over_word_limit` — 词 for "words". See F2: the count itself is whitespace-separated, which is a rule question before it is a wording one.
* `persona_*` — 顾问 for the AI advisor personas; there was no established term (the feature is on no screen).
* `governance_notice_greenwashing` — “漂绿”, in quotation marks.
* `governance_notice_*` keep `$100K` and `$1M` as written in English rather than 10 万美元 / 100 万美元, to match how every other money figure on the page is formatted.
* `rc_processing` / `rc_process` — 结算 for "post-round processing", following the existing `instructor.process_round_confirm`.
* `done_game_archived`, 班级 for "section", following `cohort_messages`.
* `enrollment_not_found` / `done_enrollment_removed` — 注册记录 for "enrollment", following `instructor.enrolled` = 已注册.
* `request_incomplete` — deliberately says nothing technical; it is what a student reads for any request the *page* got wrong.
* `status_item_*` / `status_detail_*` — labels of a legacy checklist no screen requests (F1); translated for completeness, lowest priority.
* The `_other` keys are i18next plurals; Chinese has the one form.

#### `backend/core/utils/participant_messages.py`

| Key | English | zh-CN |
|---|---|---|
| `login_username_required` | Username is required. | 请输入用户名。 |
| `login_password_required` | Password is required. | 请输入密码。 |
| `login_invalid` | Invalid username or password. | 用户名或密码不正确。 |
| `login_no_password` | No password is set for this account. Please ask your instructor to reset it. | 该账号尚未设置密码。请联系教师为您重置密码。 |
| `login_no_team` | Your account has not been assigned to a team yet. Please contact your instructor. | 您的账号尚未分配到团队。请联系教师。 |
| `account_not_found` | Your account could not be found. Sign in again. | 未找到您的账号。请重新登录。 |
| `language_unsupported` | That language is not available. Choose English or Chinese. | 不支持该语言。请选择英文或中文。 |
| `request_incomplete` | The page sent an incomplete request, so nothing was done. Reload the page and try again. | 页面发送的请求不完整，因此未执行任何操作。请刷新页面后重试。 |
| `game_not_found` | This game could not be found. Reload the page and try again. | 未找到该游戏。请刷新页面后重试。 |
| `team_not_found` | This team could not be found. Reload the page and try again. | 未找到该团队。请刷新页面后重试。 |
| `game_or_team_not_found` | This game or team could not be found. Reload the page and try again. | 未找到该游戏或团队。请刷新页面后重试。 |
| `instructor_write_required` | Only an instructor can make this change. | 只有教师可以进行此更改。 |
| `team_access_denied` | You do not have access to this team. | 您无权访问该团队。 |
| `no_active_round` | This game has no round in progress yet. | 该游戏目前没有进行中的回合。 |
| `round_not_found` | That round could not be found. Reload the page and try again. | 未找到该回合。请刷新页面后重试。 |
| `decisions_locked` | Decisions are locked for this round. | 本回合的决策已锁定。 |
| `communication_already_submitted` | This communication has already been submitted and cannot be submitted again. | 该沟通已提交，不能再次提交。 |
| `communication_empty` | Write the communication before submitting it. | 请先撰写沟通内容，然后再提交。 |
| `communication_over_word_limit` | This communication is over the word limit. The maximum is {limit} words and yours has {count}. | 该沟通超出字数上限。上限为 {limit} 词，您的内容为 {count} 词。 |
| `org_structure_not_found` | That structure is not available in this game. Reload the page and choose again. | 该架构在本游戏中不可用。请刷新页面后重新选择。 |
| `org_structure_same` | Your team already uses this structure. | 您的团队已在使用该架构。 |
| `org_structure_transition_active` | Your team is still in transition to its current structure, so it cannot switch again yet. | 您的团队仍处于向当前架构过渡的阶段，暂时无法再次切换。 |
| `org_structure_unaffordable` | Insufficient cash. This switch would take committed spend to {committed}, against {cash} of cash. | 现金不足。此次切换会使承诺支出达到 {committed}，而可用现金为 {cash}。 |
| `framework_required` | Choose a framework before saving the analysis. | 请先选择分析框架，然后再保存。 |
| `analysis_saved` | Analysis saved. | 分析已保存。 |
| `forecast_scenario_saved` | Scenario saved. | 情景已保存。 |
| `forecast_no_round` | No round found. | 未找到回合。 |
| `forecast_no_draft` | No draft decisions yet. | 尚无决策草稿。 |
| `enrollment_not_found` | No active enrollment was found for your account. Please contact your instructor. | 未找到您的有效注册记录。请联系教师。 |
| `persona_reply_required` | Type your reply before sending it. | 请先输入回复内容，然后再发送。 |
| `persona_question_required` | Type your question before sending it. | 请先输入问题，然后再发送。 |
| `persona_message_not_found` | That message could not be found. Reload the page and try again. | 未找到该消息。请刷新页面后重试。 |
| `persona_message_wrong_team` | That message does not belong to your team. | 该消息不属于您的团队。 |
| `persona_reply_limit` | This conversation has reached its maximum of {maximum} replies. | 本次对话已达到 {maximum} 条回复的上限。 |
| `persona_consultation_limit` | Your team has used all {maximum} advisor consultations for this round. | 您的团队已用完本回合的 {maximum} 次顾问咨询。 |
| `persona_thread_unknown` | The advisor for this conversation could not be identified, so your reply was not sent. | 无法确定本次对话的顾问，因此您的回复未发送。 |
| `persona_unavailable` | The advisor is temporarily unavailable. Try again shortly. | 顾问暂时无法回复。请稍后重试。 |
| `persona_invalid` | That advisor is not available. Choose an advisor from the list. | 该顾问不可用。请从列表中选择一位顾问。 |
| `platform_without_team` | This platform does not belong to a team, so its development cannot be accelerated. | 该平台不属于任何团队，因此无法加速其开发。 |
| `platform_in_development` | Platform "{platform}" is still in development. {remaining} round(s) remaining. | 平台“{platform}”仍在开发中，还需 {remaining} 个回合。 |
| `platform_not_developing` | Platform is not in development. | 该平台不在开发中。 |
| `platform_already_ready` | Platform is already ready. | 该平台已开发完成。 |
| `acceleration_unaffordable` | Insufficient budget. Need {cost}, have {remaining}. | 预算不足。需要 {cost}，可用 {remaining}。 |
| `program_cap_reached` | Program cap reached ({active}/{maximum}). Deactivate a program before adding another. | 已达到项目数量上限（{active}/{maximum}）。请先停用一个项目，然后再添加。 |
| `program_budget_overage` | This will exceed your Program budget by {overage}. The overage will be financed as a loan at {rate} interest per round. | 这将使项目预算超支 {overage}。超支部分将通过贷款解决，每回合利率为 {rate}。 |
| `resource_query_required` | Type what you are looking for before searching. | 请先输入要查找的内容，然后再搜索。 |
| `governance_notice_pay_transparency` | Your {pools} salary is Below Market. Pay transparency is exposing the gap — turnover increased +5%. Raise salaries to Market Rate or above to resolve. | 您的{pools}薪酬低于市场水平。薪酬透明使这一差距暴露出来——离职率上升 5%。请将薪酬提高到市场水平或以上以解决此问题。 |
| `governance_notice_anti_corruption` | You have JV partnerships in {markets}. Anti-corruption monitoring adds $100K/round per JV market. | 您在{markets}设有合资企业。反腐败监控会使每个合资市场每回合增加 $100K 的成本。 |
| `governance_notice_supply_chain_audit` | You use contract manufacturing in {markets}. Audit may expose labor concerns (15% probability per round). | 您在{markets}使用代工生产。审计可能暴露劳工问题（每回合 15% 的概率）。 |
| `governance_notice_greenwashing` | Total ESG investment is only {total}. Reporting without substance is seen as greenwashing. Increase environmental/social investment above $1M or remove this commitment. | 目前 ESG 总投入仅为 {total}。缺乏实质内容的报告会被视为“漂绿”。请将环境/社会投入提高到 $1M 以上，或取消此项承诺。 |
| `talent_pool_rd` | R&D | 研发 |
| `talent_pool_commercial` | Commercial | 商务 |
| `talent_pool_operations` | Operations | 运营 |
| `list_separator` | ,  | 、 |
| `status_item_programs` | CSR Programs | CSR 项目 |
| `status_item_challenges` | Challenge Responses | 挑战回应 |
| `status_item_dilemma` | Ethical Dilemma | 伦理困境 |
| `status_detail_modified` | Modified | 已修改 |
| `status_detail_no_changes` | No changes | 无更改 |
| `status_detail_submitted_count` | {submitted}/{available} submitted | 已提交 {submitted}/{available} |
| `status_detail_submitted` | Submitted | 已提交 |
| `status_detail_pending` | Pending | 待提交 |

#### `backend/core/utils/operator_messages.py`

| Key | English | zh-CN |
|---|---|---|
| `unlock_already_processed` | Round {round} has already been processed; unlocking now would not change its results. | 第 {round} 回合已结算；此时解锁不会改变其结果。 |
| `unlock_already_processed_guidance` | Use the recovery workflow if a processed round must be corrected. | 如需更正已结算的回合，请使用恢复流程。 |
| `submission_not_locked` | Submission is not locked. | 该提交未处于锁定状态。 |
| `submission_not_locked_guidance` | Refresh — it may already have been unlocked. | 请刷新——它可能已被解锁。 |
| `sc_inject_round_not_open` | Round {round} is "{status}"; an event staged now would not fire in it. | 第 {round} 回合{status}；此时安排的事件不会在该回合触发。 |
| `sc_inject_round_not_open_guidance` | Inject into an open round, or advance first. | 请在已开放的回合中注入事件，或先推进到下一回合。 |
| `no_active_round` | No active round. | 当前没有进行中的回合。 |
| `reminder_game_required` | The request did not say which game session to remind, so no reminder was sent. Reload the console and try again. | 本次请求未指明要提醒哪个游戏场次，因此未发送提醒。请刷新控制台后重试。 |
| `accounts_csv_empty` | No account data was provided. Paste the account list, then upload again. | 未提供账号数据。请粘贴账号列表后重新上传。 |
| `accounts_row_missing_username` | This row has no username, so no account was created from it. | 此行没有用户名，因此未据此创建账号。 |
| `accounts_row_invalid_team` | This row names a team, "{value}", that is not a number, so no account was created from it. | 此行填写的团队“{value}”不是数字，因此未据此创建账号。 |
| `game_creation_market_unknown` | Market code "{code}" is not a market in scenario "{scenario}". | 场景“{scenario}”中没有代码为“{code}”的市场。 |
| `game_creation_no_starter_profiles` | Scenario "{scenario}" has no starter profiles, so no game can be created from it. | 场景“{scenario}”没有初始企业档案，因此无法据此创建游戏。 |
| `game_creation_no_starting_platform` | Scenario "{scenario}" has no starting platform generation, so no game can be created from it. | 场景“{scenario}”没有初始平台代次，因此无法据此创建游戏。 |
| `game_creation_failed` | The game could not be created: {detail} | 无法创建游戏。系统给出的原因（英文）：{detail} |
| `fire_events_failed` | Events could not be fired: {detail} | 无法触发事件。系统给出的原因（英文）：{detail} |
| `password_blank` | Password cannot be blank. | 密码不能为空。 |
| `password_too_short` | Password must be at least {minimum} characters. | 密码至少需要 {minimum} 个字符。 |
| `fire_events_incomplete` | Choose a game and a round before firing events. | 请先选择游戏和回合，然后再触发事件。 |
| `fire_events_not_numbers` | The game and the round must each be given as a whole number. | 游戏和回合都必须以整数表示。 |
| `done_round_closed` | {game}: round {round} closed. {count} submission(s) locked. | {game}：第 {round} 回合已关闭。已锁定 {count} 份提交。 |
| `done_round_reopened` | {game}: round {round} reopened. {count} submission(s) unlocked. | {game}：第 {round} 回合已重新开放。已解锁 {count} 份提交。 |
| `done_round_processed` | {game}: round {round} processed in {seconds}s. Results are available; narratives are generating in the background. | {game}：第 {round} 回合已结算，用时 {seconds} 秒。结果已可查看；叙述内容正在后台生成。 |
| `done_game_complete` | {game}: round {round} was the last round. Game complete. | {game}：第 {round} 回合是最后一个回合。游戏已结束。 |
| `done_advanced` | {game}: advanced to round {round}. | {game}：已进入第 {round} 回合。 |
| `done_deadline_updated` | {game}: deadline updated. | {game}：截止时间已更新。 |
| `done_deadline_cleared` | {game}: deadline cleared. | {game}：截止时间已清除。 |
| `done_deadline_in_past_warning` | That deadline is in the past — the round will close within a minute. | 该截止时间已过——回合将在一分钟内关闭。 |
| `done_deadline_extended` | {game}: deadline extended by {hours} hour(s). | {game}：截止时间已延长 {hours} 小时。 |
| `done_deadline_extended_and_reopened` | {game}: deadline extended by {hours} hour(s). The round was closed, so it has been reopened and {count} submission(s) unlocked. | {game}：截止时间已延长 {hours} 小时。该回合此前已关闭，现已重新开放，并已解锁 {count} 份提交。 |
| `done_legacy_advanced` | {game}: round advanced to {round}. | {game}：已推进到第 {round} 回合。 |
| `done_event_injected` | Event "{event}" injected. | 事件“{event}”已注入。 |
| `done_sc_event_queued` | "{event}" queued — fires when round {round} is advanced. | “{event}”已排入队列——将在第 {round} 回合推进时触发。 |
| `done_game_archived` | Game archived. Section is now free for a new game. | 游戏已归档。该班级现在可以开设新的游戏。 |
| `done_password_updated` | Password updated for {username}. | 已更新 {username} 的密码。 |
| `done_passwords_reset` | Reset {count} password(s) to the student ID default. | 已将 {count} 个密码重置为默认的学号密码。 |
| `done_password_skipped_no_identity` | no student ID or username | 没有学号或用户名 |
| `done_enrollment_removed` | Enrollment removed. | 已移除该注册记录。 |

#### `frontend/globalstrat-frontend/src/locales/zh-CN.json`

| Key | English | zh-CN |
|---|---|---|
| `nav.sourcing` | Sourcing | 采购 |
| `nav.logistics` | Logistics | 物流 |
| `nav.trade_finance` | Trade Finance | 贸易融资 |
| `nav.inventory` | Inventory | 库存 |
| `corporate_strategy.salary_level_n` | Level {{level}} | {{level}} 级 |
| `rd.slots_all_used` | All R&D investment slots are already used this round. | 本回合的研发投资槽位已全部用完。 |
| `rd.upgrade_exceeds_budget` | This upgrade exceeds the remaining R&D budget. | 此次升级超出了剩余的研发预算。 |
| `rd.investment_saved` | Saved R&D investment: {{feature}} to level {{level}} | 研发投资已保存：{{feature}} 升至 {{level}} 级 |
| `rd.investment_save_failed` | R&D investment could not be saved. | 研发投资未能保存。 |
| `onboarding.default_platform` | Gen 1 | 第 1 代 |
| `instructor.user_n` | User {{id}} | 用户 {{id}} |
| `instructor.sc_load_failed` | Failed to load the supply-chain panel. | 无法加载供应链面板。 |
| `instructor.msg_request_failed` | The request failed. | 请求失败。 |
| `instructor.home_market_not_set` | Not set | 未设置 |
| `instructor.unknown_team` | Unknown | 未知团队 |
| `instructor.game_named` | Game: {{game}} | 游戏：{{game}} |
| `instructor.rc_title` | Round Control | 回合控制 |
| `instructor.rc_refresh` | Refresh | 刷新 |
| `instructor.rc_load_failed` | Could not load round status | 无法加载回合状态 |
| `instructor.rc_done` | Done | 操作完成 |
| `instructor.rc_action_failed` | Action failed | 操作失败 |
| `instructor.rc_no_round` | No round yet | 尚无回合 |
| `instructor.rc_no_round_hint` | Activate the game to open Round 1. | 激活游戏后将开放第 1 回合。 |
| `instructor.rc_paused` | Game is paused | 游戏已暂停 |
| `instructor.rc_paused_hint` | Students cannot submit or change anything while the game is paused. The deadline is also on hold — it will not close the round until you resume. | 游戏暂停期间，学生无法提交或更改任何内容。截止时间也同时暂停——在您恢复游戏之前，它不会关闭回合。 |
| `instructor.rc_round_status` | Round status | 回合状态 |
| `instructor.rc_status_open` | open | 已开放 |
| `instructor.rc_status_closed` | closed | 已关闭 |
| `instructor.rc_status_processed` | processed | 已结算 |
| `instructor.rc_status_pending` | not yet open | 尚未开放 |
| `instructor.rc_closed_by_deadline` | closed by deadline | 因截止时间到期而关闭 |
| `instructor.rc_closed_by_instructor` | closed by instructor | 由教师关闭 |
| `instructor.rc_deadline` | Deadline | 截止时间 |
| `instructor.rc_deadline_not_set` | Not set — this round will never close on its own | 未设置——本回合不会自动关闭 |
| `instructor.rc_unit_days` | {{n}}d | {{n}} 天 |
| `instructor.rc_unit_hours` | {{n}}h | {{n}} 小时 |
| `instructor.rc_unit_minutes` | {{n}}m | {{n}} 分钟 |
| `instructor.rc_time_remaining` | {{time}} remaining | 剩余 {{time}} |
| `instructor.rc_time_overdue` | {{time}} overdue | 已超时 {{time}} |
| `instructor.rc_decisions_in` | Decisions in | 已提交决策 |
| `instructor.rc_still_out` | ({{n}} still out) | （还有 {{n}} 个团队未提交） |
| `instructor.rc_processing` | Processing | 结算 |
| `instructor.rc_processing_pending` | Not yet processed | 尚未结算 |
| `instructor.rc_processing_running` | Processing… | 正在结算… |
| `instructor.rc_processing_results` | Results ready — narratives generating | 结果已生成——叙述内容正在生成 |
| `instructor.rc_processing_complete` | Complete | 已完成 |
| `instructor.rc_processing_failed` | Failed | 失败 |
| `instructor.rc_scoring_took` | — scoring took {{seconds}}s | ——计分用时 {{seconds}} 秒 |
| `instructor.rc_narrative_failed` | Narrative generation failed | 叙述内容生成失败 |
| `instructor.rc_narrative_failed_hint` | {{error}} — the numbers are still valid. | {{error}}——各项数字仍然有效。 |
| `instructor.rc_lifecycle_hint` | A round closes at its deadline (or when you close it), then you run post-round processing, then you advance. Processing and advancing are separate so you can check the results before the game moves on. | 回合会在截止时间到期时（或由您手动）关闭，随后由您运行回合结算，然后再推进到下一回合。结算与推进是分开的两步，便于您在游戏继续之前检查结果。 |
| `instructor.rc_change_deadline` | Change deadline | 更改截止时间 |
| `instructor.rc_set_deadline` | Set deadline | 设置截止时间 |
| `instructor.rc_close_hint` | Students will be locked out immediately and all decisions submitted as they stand. | 学生将立即被锁定，所有决策将按当前内容提交。 |
| `instructor.rc_close_now` | Close round now | 立即关闭回合 |
| `instructor.rc_process_hint` | Scores events, R&D, adoption, revenue, costs, financial statements, performance index and the leaderboard. Takes a few seconds. | 将计算事件、研发、采用、收入、成本、财务报表、绩效指数和排行榜。需要几秒钟。 |
| `instructor.rc_process` | Run post-round processing | 运行回合结算 |
| `instructor.rc_reopen` | Reopen round | 重新开放回合 |
| `instructor.rc_advance_hint` | Students will start the next round. | 学生将开始下一回合。 |
| `instructor.rc_finish_game` | Finish game | 结束游戏 |
| `instructor.rc_advance_to` | Advance to round {{round}} | 推进到第 {{round}} 回合 |
| `instructor.rc_close_and_process` | Close & process now | 立即关闭并结算 |
| `instructor.rc_close_and_process_ok` | Close and process | 关闭并结算 |
| `instructor.rc_force_hint` | This closes the round early and resolves it immediately, skipping the review pause. Teams still editing lose whatever they had not saved. The reason below is written to the operator audit record. | 此操作会提前关闭回合并立即结算，跳过检查环节。仍在编辑的团队将丢失尚未保存的内容。下方填写的理由会写入操作审计记录。 |
| `instructor.rc_force_reason_placeholder` | Why is closing early correct here? (at least 10 characters) | 为什么此时提前关闭是正确的？（至少 10 个字符） |
| `instructor.rc_save_deadline` | Save deadline | 保存截止时间 |
| `instructor.rc_deadline_hint` | The round closes automatically at this time and students are locked out. Clear it to let the round run until you close it by hand. | 回合将在该时间自动关闭，学生随即被锁定。清除该时间后，回合将一直开放，直到您手动关闭。 |
| `instructor.rc_timezone_hint` | Times are in your local timezone. Server time is currently {{time}}. | 时间按您的本地时区显示。服务器当前时间为 {{time}}。 |
| `instructor.rc_reopen_needs_deadline` | Pick a new deadline, or the round will close again straight away. | 请选择新的截止时间，否则回合会立即再次关闭。 |
| `instructor.rc_reopen_hint` | This unlocks every team's decisions and lets students edit again. | 此操作会解锁所有团队的决策，学生可以再次编辑。 |
| `instructor.rc_reopen_deadline_hint` | Give the round a new deadline in the future — otherwise the old one is still in the past and the round would close again within a minute. | 请为回合设置一个未来的新截止时间——否则原截止时间仍已过期，回合会在一分钟内再次关闭。 |
| `instructor.sa_load_failed` | Could not load student accounts | 无法加载学生账号 |
| `instructor.sa_set_failed` | Could not set the password | 无法设置密码 |
| `instructor.sa_online` | Logged in now | 当前已登录 |
| `instructor.sa_offline` | Not logged in | 未登录 |
| `instructor.sa_student` | Student | 学生 |
| `instructor.sa_student_id` | Student ID | 学号 |
| `instructor.sa_team` | Team | 团队 |
| `instructor.sa_logged_in_for` | Logged in for | 已登录时长 |
| `instructor.sa_minutes` | {{m}} min | {{m}} 分钟 |
| `instructor.sa_hours` | {{h}}h | {{h}} 小时 |
| `instructor.sa_hours_minutes` | {{h}}h {{m}}m | {{h}} 小时 {{m}} 分钟 |
| `instructor.sa_password` | Password | 密码 |
| `instructor.sa_password_missing` | Not set — cannot log in | 未设置——无法登录 |
| `instructor.sa_password_set` | Set | 已设置 |
| `instructor.sa_actions` | Actions | 操作 |
| `instructor.sa_reset_confirm` | Reset to default? | 重置为默认密码？ |
| `instructor.sa_reset_confirm_hint` | Their password becomes their student ID ({{password}}). | 该学生的密码将变为其学号（{{password}}）。 |
| `instructor.sa_reset_done` | Password reset to the student ID | 密码已重置为学号 |
| `instructor.sa_reset_to_id` | Reset to ID | 重置为学号 |
| `instructor.sa_set_password` | Set password | 设置密码 |
| `instructor.sa_whos_logged_in` | Who's logged in | 当前登录情况 |
| `instructor.sa_active_sessions_other` | {{count}} active session / {{count}} active sessions | {{count}} 个活动会话 |
| `instructor.sa_sessions_hint` | A session is counted when it has activity in the last {{minutes}} minutes. This is not a unique-person count. Auto-refreshes every 30s. | 最近 {{minutes}} 分钟内有活动的会话才会计入。这不是去重后的人数。每 30 秒自动刷新。 |
| `instructor.sa_nobody_online` | Nobody is logged in right now. | 目前没有人登录。 |
| `instructor.sa_last_active` | Last active | 最近活动 |
| `instructor.sa_active_now` | now | 刚刚 |
| `instructor.sa_time_ago` | {{time}} ago | {{time}}前 |
| `instructor.sa_since` | Since | 登录时间 |
| `instructor.sa_accounts_title` | Student accounts & passwords | 学生账号与密码 |
| `instructor.sa_this_game_only` | This game only | 仅限本游戏 |
| `instructor.sa_cannot_log_in_other` | {{count}} student cannot log in / {{count}} students cannot log in | {{count}} 名学生无法登录 |
| `instructor.sa_cannot_log_in_hint` | These accounts have no password set. Give each one their student ID as a password so they can sign in. | 这些账号尚未设置密码。请将每个账号的密码设为其学号，以便学生登录。 |
| `instructor.sa_bulk_confirm_other` | Set {{count}} password? / Set {{count}} passwords? | 设置 {{count}} 个密码？ |
| `instructor.sa_bulk_confirm_hint` | Each student's password becomes their own student ID. Existing passwords are left alone. | 每名学生的密码将变为其本人的学号。已有的密码不受影响。 |
| `instructor.sa_bulk_skipped_other` | {{count}} skipped — no student ID on file. / {{count}} skipped — no student ID on file. | 已跳过 {{count}} 个——没有学号记录。 |
| `instructor.sa_bulk_failed` | Bulk reset failed | 批量重置失败 |
| `instructor.sa_bulk_button` | Set all to student ID | 全部设为学号 |
| `instructor.sa_search_placeholder` | Search by name, username or student ID | 按姓名、用户名或学号搜索 |
| `instructor.sa_set_password_for` | Set password for {{name}} | 为 {{name}} 设置密码 |
| `instructor.sa_password_too_short` | Password must be at least 6 characters. | 密码至少需要 6 个字符。 |
| `instructor.sa_password_updated` | Password updated | 密码已更新 |
| `instructor.sa_set_password_hint` | The student can log in with this immediately. You'll see it once after saving — it isn't recoverable later, only resettable. | 学生可立即使用该密码登录。保存后密码只显示一次——之后无法找回，只能重置。 |
| `instructor.sa_new_password_placeholder` | New password (at least 6 characters) | 新密码（至少 6 个字符） |
| `instructor.sa_password_set_title` | Password set | 密码已设置 |
| `instructor.sa_done` | Done | 完成 |
| `instructor.sa_give_to_student` | Give these to the student: | 请将以下信息交给学生： |
| `instructor.sa_username_label` | Username: | 用户名： |
| `instructor.sa_password_label` | Password: | 密码： |
| `instructor.sa_shown_once` | This is the only time the password is shown. If it's lost, reset it again. | 密码仅在此处显示一次。如果遗失，请重新重置。 |
| `instructor.sc_event_injected` | Event injected. | 事件已注入。 |
| `instructor.sc_injection_failed` | Injection failed. | 事件注入失败。 |
| `instructor.sc_weights_saved` | Resilience weight override saved. | 韧性权重覆盖值已保存。 |
| `instructor.sc_save_failed` | Save failed. | 保存失败。 |

## 6. What remains English, and exactly why

**One scanned site: `core/views/grading.py:144`, `{'error': str(exc), 'code': 'model_derived_component_in_competition'}`.** Not converted because the console never shows it: that code is deliberately absent from the console's allowlist, and the console says its own bilingual catalogue sentence for it (`instructor.grades_refused_model_component`, one of the three sentences allowed to say 竞赛). Converting it would mean adding the code to the allowlist and so *replacing* a reviewed console sentence with a new unreviewed one. It is the guard's one exemption, written down with this reason in `WHOLE_TREE_EXEMPT`.

**Engine exception detail inside a bilingual frame** — unchanged from the previous report, and extended by two frames of the same kind here (`game_creation_failed`, `fire_events_failed`): `round_not_ready`, `advance_refused`, `processing_failed`, `advance_failed` carry the engine's own sentence as `{detail}`, and the zh-CN frame says so (系统给出的原因（英文）：…). Translating those means giving every engine exception a key, which is engine work. The three causes the game builder *names* were given keys here, so game creation only falls back to the frame for a cause nobody has written yet.

**DRF's own sentences.** Out of scope by the task's terms unless a student can plainly meet one; the cases where one can are listed here rather than re-architected. A probe (a temporary test, not committed) drove every writable field of every decision serializer as a zh-CN student with `null`, text, and an over-long number: **113 English answers**, all DRF defaults, none from this codebase. `DecisionSaveAlert` lists the server's messages verbatim, so whatever arrives is what the student reads.

| DRF sentence | Can a student meet it through the normal UI? |
|---|---|
| `Ensure that there are no more than 15 digits in total.` (10 for dividend per share, 5 for the channel percentages) | **Yes, plainly.** Any money `InputNumber` with no `max` accepts a 16-digit number: budget (R&D / marketing / strategy), financing (new debt, new equity, dividend per share), marketing (promotion budget, distribution investment), market entry (initial investment). 21 of the 37 `InputNumber`s on student pages have no `max`. |
| `Ensure this value is less than or equal to 2147483647.` | **Yes**, the same way: production volume, demand estimate, sales team count. |
| `This field may not be null.` | **Mostly no**: the pages normalise a cleared input to 0 (`normalizeMoneyInput`, `v \|\| 0`) or allow blank by design (`retail_price`). I did not audit every page handler; MarketStrategy's compliance input and RD's feature level pass the raw value. |
| `A valid number is required.` / `A valid integer is required.` | No — `InputNumber` cannot send text. |
| `Request was throttled. Expected available in N seconds.` (429, `decision_write` at 120/min per user) | Possible under a fast autosave; not reproduced. |
| `Not found.` (`get_object_or_404`) | Only from a stale page (a team, round or assignment that no longer exists). |
| `Token has expired.` / `Invalid token.` / `User not found.` (`core/authentication.py`) | **Never displayed**: every such 401 redirects to `/login` in the axios interceptor. Left as they are for that reason. |

*A cheap remedy the owner may want, not applied here because it is a platform-wide change:* DRF and Django ship zh-Hans translations of every sentence above. `USE_I18N` is already `True`; what is missing is `LocaleMiddleware` (or an equivalent that activates the request's language). Two caveats: it would also translate things tests may pin in English, and the *field names* DRF keys its errors by would stay storage names (`new_debt`) — `DecisionSaveAlert` decides whether to show them.

**Two instructor-side components are still wholly English in their labels** — not refusals, fallbacks or confirmations, and not the two files this item names, so not converted: `components/instructor/InstructorSCPanel.js` (about 45 strings: column titles, tags, the inject card, the resilience-weight editor; its four announcements and its load failure *were* converted and are guarded) and `components/instructor/AuditEvidenceTable.js` (about 12). They are the same shape as V2-080 and belong with it. `InstructorSCPanel` also shadows `t` with a lambda parameter in two `filter` calls; harmless today, a trap for whoever converts it.

**The legacy checklist's `overall` value** (`'Ready'` / `'Partial'` / `'No Activity'`, `DecisionStatusView`) was left: it reads like a status token a client would branch on, no client exists to ask, and the route is dead (F1).

## 7. New findings (none closed here)

**F1. Two registered instructor routes answer 500 to every call.** `rounds/<id>/decision-status/` (also `rounds/current/my-status/`) and `rounds/<id>/send-reminder/` look the round up with `Round.objects.get(round_id=…)`; `Round` has no such column (`FieldError: Cannot resolve keyword 'round_id'`). Found because a language test for the reminder refusal could not reach it. The frontend calls neither; they are CSR-era leftovers. Their literals are converted and scan-guarded, but the routes should be removed or repaired by whoever owns the route inventory.

**F2. The communication word limit does not work for Chinese text.** `cc32a_views.py` counts words with `len(content.split())`. A memo written in Chinese has no spaces, so it counts as one "word" (or one per whitespace-separated run): the limit never binds for a team writing in Chinese, on a submission that is scored. That is a rule, not wording; nothing was changed. The new zh-CN sentence says 词 and will read oddly until this is ruled on.

**F3. A wrong password was never explained** (repaired in `30e7864` + `a81136b`, separable). Every 401 sent the browser to `/login` — including the 401 that answers a wrong password, so the page reloaded over the refusal, and an instructor who mistyped on `/instructor/login` landed on the student form. Fixing that alone would have introduced a worse fault, which I checked for rather than assumed away: `LoginView` runs the default authentication, so a token left in storage from an earlier session is refused as expired *before the password is read*, and with no reload to clear it the student could never log in. The login request therefore no longer sends a token. Both halves have tests; neither has been seen in a browser.

**F4. The pause guard spoke English to every student** — §1. Reported separately because it means CRV2-12's bilingual paused-game sentence in `decisions.py` was unreachable for students all along: the middleware answers first.

**F5. A bilingual refusal that was discarded.** The supply-chain inject route refuses with `{'error', 'guidance', 'code'}` (it is a lifecycle route); `InstructorSCPanel` read `detail`, so it always showed its own English fallback. It now reads `error` first.

## 8. What a reviewer should distrust

Only what could not be resolved here:

1. **All 224 zh-CN sentences in §5 are mine and unread by a native speaker.** The ones I trust least are named at the top of that section.
2. **Nothing was seen in a browser.** In particular: (a) the two login changes (F3) — the logic is tested, the navigation is not; (b) antd's Chinese locale on the round-control confirmations and the deadline picker — the locale object and the wiring are tested, the rendering is not; (c) `RoundControlCard` and `StudentAccountsPanel` are rendered by no test (the guard reads their source), so a Chinese label too long for its button or column would show up nowhere but on a screen.
3. **For the owner:** whether the operator audit trail should stay English-only (the previous builder's Q3 — untouched, and the conversions here follow their convention so that either answer remains a one-line change); whether `LocaleMiddleware` should be switched on (§6); what a "word" is in a Chinese communication (F2); whether the two dead routes are removed or repaired (F1).

Everything else I doubted, I checked: that no status code moved (asserted per refusal, then the full suite); that the three audit rows are byte-identical (asserted); that English did not drift where it named no storage field (asserted against the old f-strings); that no existing zh-CN sentence changed (mechanical diff against the base: none); that no test, harness or frontend code matched on a sentence I changed (grep before each change; one pin found, `Insufficient cash`, and kept); that keeping a refused login on the page did not strand a stale token (it would have — fixed); that the new tests add no computed `t()` key (27 before and after); that the locale files were inserted into, not re-dumped; that the diff shows only what changed (it did not — six files, fixed, suite re-run).

## 9. Proposed register text (for the auditor to apply or reject)

**D3 — operator refusals (residual):**
> **Repaired, pending native review.** `299259f`, `94fea43`, `6e73974`, `a02ae01`, `f3308bf`: all 61 literals that remained at `87c92dc` (15 instructor-side, 46 student-facing, login first) and 41 further sites found by widening the scan (confirmations, scope-guard middleware, two services, `str(exc)`) come from `participant_messages` / `operator_messages` in the request's language, each with a code and none naming a storage field; 90 codes, console allowlist test-locked. Status codes, rules and audit content unchanged (audit rows asserted byte-identical). A source scan now covers every view module. **Residual:** one exempted site the console never displays (`grading.py`); engine exception detail inside a bilingual frame; DRF's own sentences (completion doc §6 lists the ones a student can meet: over-long numbers in unbounded inputs). zh-CN unreviewed.

**V2-080 — round-control surface untranslated:**
> **Repaired, pending native review and observation.** `be1fa41`: `RoundControlCard` and `StudentAccountsPanel` carry no hard-coded string; the server's confirmations are bilingual (`299259f`); antd's OK / Cancel and date picker follow the interface language. Source-scan guarded. Not seen in a browser. `InstructorSCPanel` and `AuditEvidenceTable` labels remain English (same defect, not converted here).

**New — pause guard language (F4):**
> **Repaired, pending native review.** `a02ae01`: `GamePauseGuardMiddleware` refused every student write to a paused, completed or archived game in English, ahead of the bilingual permission on the decision routes. It now answers from the participant catalogue in the request's language, with a code, and still sends `game_status`. Driven red and green through the decision route in both languages.

**New — student pages announcing in English (R&D page, sidebar):**
> **Repaired, pending native review.** `5b4ce4d`: four R&D-page sentences and the four supply-chain sidebar labels were English for every reader. Catalogue keys now; a tree-wide scan of `src/` holds announcements and literal fallbacks.

**New — refused login not explained (F3):**
> **Repaired, unobserved.** `30e7864`, `a81136b`: a 401 from the login request no longer reloads the page, and the login request carries no stored token. Separable from the language work.

**New — dead instructor routes (F1)** and **communication word count for Chinese text (F2):**
> **Open.** Recorded in the completion doc §7; nothing changed.
