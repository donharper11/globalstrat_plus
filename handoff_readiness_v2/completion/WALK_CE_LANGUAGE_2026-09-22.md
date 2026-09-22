# WALK-CE language repairs — W-CE-06, 08, 11, 13, 15, 16, 17, 20, 22, and the sweep

**Branch:** `walk-ce-language`, cut from `crv2-release-integration` at `b955c41` (contains `4b152f8` and `WALKTHROUGH_CE_2026-09-22.md`).
**Date:** 2026-09-22. **Builder:** repair builder, language defects of the Consumer Electronics walkthrough.
**Rule observed:** R48 — bugs first, no new rules; R43 — the team's language governs what a student is told; R44 — the operator audit trail stays English.

> Sections: (a) method · (b) per id: source, repair, red-then-green · (c) every new or changed zh-CN sentence, least-trusted first · (d) the remaining-literals list · (e) tests and commands · (f) register status text · (g) distrust list and observations.

---

## (a) Method

Every defect was reproduced before it was repaired: a Jest render or source scan with `t` stubbed to print its key, or a Django request with `Accept-Language`/the team's enrolment language set. The red run was taken against the base with the fix reverted (`git checkout -- <runtime files>` with the new tests in place), the green run after re-applying it; both are quoted per id below. Backend tests ran only through `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>` (disposable Postgres; never the production database, never `/etc/globalstrat-plus.env`). Frontend: focused Jest per id, then the full Jest run, `backend/scripts/check-participant-strings` (+ selftest) and the production build with the ESLint ratchet.

Guards extended so a fixed screen cannot regress:

| guard | what it holds |
|---|---|
| `backend/core/tests/test_walk_ce_language.py` (new, 10 classes) | every backend behaviour below, by request |
| `backend/core/tests/test_zh_terminology.py` | now also reads `operator_messages.SUBMISSION_ORIGIN_LABELS` and the Phase-2 fallback tables in `narratives.py`, `instructor_alerts.py`, `communication_eval.py` (one term per concept) |
| `backend/scripts/participant-strings.config.json` | `SUBMISSION_ORIGIN_LABELS` held to A1–A3 |
| `frontend/.../src/englishLiteralScan.js` (new) | the console-panel scan factored out, shared by the student and console guards |
| `src/pages/walkCeStudentLanguage.test.js` (new) | SummaryPage whole-scan clean; LoginPage, GameDashboard, RDPage, FinancePage, ProductsPage, CorporateStrategyPage, MarketingPage, TeamActivityBanner held to the literals removed, and to their keys existing in both catalogues |
| `src/pages/walkCeConsoleLanguage.test.js` (new) | W-CE-08, -11, -17, -20 on the console source; AuditEvidenceTable and InstructorSCPanel: no computed key, every key in both catalogues |
| `src/components/consolePanelsLanguage.test.js` | InstructorSCPanel promoted from “announcements only” to the whole scan |
| `src/pages/SummaryPage.test.js`, `SummaryPage.language.test.js`, `marketStrategyLabels.test.js`, `marketResearchColours.test.js`, `components/LanguageSwitcher.test.js`, `AuthContext.test.js`, `instructor/AuditEvidenceTable.test.js`, `instructor/AuditRoundSelect.test.js` | render tests, by key |

Commits (one per defect, oldest first): `d29e857` W-CE-06 · `d985122` W-CE-08 · `e1745f1` W-CE-20 · `fdb0a2d` W-CE-22 · `863e7b0` W-CE-13 · `f5f757f` W-CE-16 (a) · `56d8985` W-CE-11 · `3de618a` W-CE-17 · `be4aad1` W-CE-16 (c) · `dd7a81c` sweep · then W-CE-15 + W-CE-16 (b)(d) backend (see (e)) · then the string inventory, alone.

---

## (b) Per id

### W-CE-06 — `{market}` in the ticker (P2) — fixed, `d29e857`

**Source.** `InstructorInjectEventView` (`backend/core/views/results_api.py`) stored `narrative=template.description_template` — the raw authored template, placeholders unfilled. The engine's own path (`core/engine/events.py`, `fire_events`) renders through `generate_event_narrative`, which replaces `{market}` with the market name or “global markets”; the inject route never called it. Every reader (ticker `cc31h_views.py`, industry news `cc15_views.py`, round results `results_api.py`, communications context `cc32a_views.py`) showed `ev.narrative` verbatim.

**Repair.** The inject route renders the narrative the way the engine does. `generate_event_narrative` takes a `language` (the authored `description_template_zh` and the market's `name_zh` for zh-CN; “全球市场” for an all-markets event). A new `event_narrative_for_reader(event, language)` is what the four readers call: the authored Chinese template for a Chinese reader, the stored English text otherwise, and a stored row that still carries a placeholder (a game injected before this fix) is rendered again rather than shown with `{market}`.

**Red → green.** `core.tests.test_walk_ce_language.TickerPlaceholderTests` + `EventNarrativeLanguageTests`: red `Ran 8 tests … FAILED (failures=7)` (`'{market}' unexpectedly found in 'Major Competitor Product Launch — An AI competitor has launched an aggressively priced Gen 2 product in {market}. '`); green with `test_engine.TestEventNarrativeGeneration`, `test_operator_refusal_language`, `test_player_language_guard`: `Ran 65 tests … OK`.

### W-CE-08 — raw `no_submission` tag (P2) — fixed, `d985122`

**Source.** The drill-down rendered `<Tag>{drillData.status}</Tag>` (the stored token) beside `submission_origin_label` (“No submission”), and the team overview rendered `decision_status` (`locked`/`draft`/`empty`) raw. The origin labels themselves were an English-only dict in the view.

**Repair.** `submissionStatusLabel()` in the console maps each status to `instructor.submission_status_locked/draft/empty` (one literal key per value) and the status tag is omitted when the origin label already says there is no submission. The origin labels moved to `operator_messages.SUBMISSION_ORIGIN_LABELS` (bilingual, rendered in the instructor's language via `submission_origin_label(origin, language)`); the string check and the terminology test read the new table; a test asserts every origin `classify_submission_origin` can return has both labels.

**Red → green.** Jest `walkCeConsoleLanguage.test.js` red `Tests: 4 failed, 4 total`; backend `DrillDownStatusLabelTests` red `Ran 3 … FAILED (failures=2, errors=1)`. Green: backend with `test_zh_terminology`, `test_operator_refusal_language`, `test_player_language_guard`, `test_competition_hardening`: `Ran 76 tests … OK`; Jest with `instructorDashboardMessages`, `consolePanelsLanguage`: `Tests: 25 passed`.

### W-CE-20 — the drill-down led with the audit table (P2) — fixed, `e1745f1`

**Source.** `AuditEvidenceTable` was rendered first in the View Decisions modal, before budget/R&D/marketing/financing/ESG/talent.

**Repair.** `AuditEvidenceTable` takes `collapsed`: the same table — every row, column, hash and payload — inside a closed antd `Collapse` panel. The modal renders it after the last decision block. No data removed.

**Red → green.** Jest (`AuditEvidenceTable.test.js` new collapsed block + console guard): red `Tests: 2 failed, 17 passed`; green `Tests: 29 passed` (with `instructorDashboardMessages`).

### W-CE-22 — “Build Plant — $0”, “+ $0/round”, `VERY_HIGH` (P2) — fixed, `fdb0a2d`

**Source.** Three sources. (1) The strategy context (`StrategyContextView`) never sent `plant_build_cost`, `plant_build_rounds` or `plant_capacity_units`, so `fmt(m.plant_build_cost)` was `$0` for **every** market and the page invented “2 rounds, 50000 units” as defaults; in the CE scenario one market (line 1079 of the YAML) also authors no cost at all. (2) The partnership button read `${capital_cost_base} + ${recurring_cost_per_round}/round`; the server never sends `recurring_cost_per_round`, and the stored decision is `annual_investment = capital_cost_base`, charged every active round by `engine/costs.py`. (3) The cultural-distance level (`VERY_HIGH`) and the plant status token (`operational`) were rendered raw.

**Repair.** The server sends the three authored figures per market (`null` when the scenario authors no cost — never a number). `src/pages/marketStrategyLabels.js` (new): `plantBuildLabel` shows the authored cost or “cost not set in this scenario”, the authored build rounds and capacity (no invented default); `perRoundCharge` states the one charge as it is levied (`$2.0M/round`); `distanceLabel` and `plantStatusLabel` map every enum to a bilingual label, one literal key per value.

**Red → green.** Jest `marketStrategyLabels.test.js` red `Cannot find module './marketStrategyLabels'` (suite failed); backend `PlantCostContextTests` red `KeyError: 'plant_build_cost' … FAILED (failures=1, errors=1)`. Green: Jest `Tests: 15 passed`; backend with `test_player_language_guard`: `Ran 15 tests … OK`.

### W-CE-13 — Sourcing/Logistics/Trade Finance/Inventory shown as lock requirements (P2) — fixed, `863e7b0`

**Source.** `DecisionSummaryView._sc_cfg` returned `{'status', 'warnings': []}` with no `optional` flag; the lock's real preconditions are `required_lock_categories = {products, marketing, strategy}` plus the budget. The page's `guidanceFor` then said “Open Sourcing to complete this requirement” and showed a “Fix in Sourcing” button for any non-optional, non-configured category.

**Repair.** The server marks the four categories `optional: True` and carries the sentence `summary_section_optional` (“Optional this round. Locking your decisions does not require it.” / 本回合为可选项，锁定决策时无需完成。) in the reader's language; the page shows that sentence, an “Optional” tag, and no Fix button for an optional section. A test reads `required_lock_categories` from the view and asserts the optional set is exactly disjoint from it. **Overlap noted:** the page's own `requiredForLock = ['budget','products','marketing','strategy']` and `hasIncompleteRequired` are untouched — the W-CE-25 builder is deriving the blocker list from the server; my change stays on the supply-chain items.

**Red → green.** Jest `SummaryPage.test.js` red `Tests: 2 failed, 1 passed`; backend `SummaryOptionalSectionTests` red `FAILED (failures=3, errors=1)`. Green: Jest `Tests: 3 passed`; backend with `test_crv2_12_language`, `test_player_language_guard`, `test_zh_terminology`: `Ran 41 tests … OK`.

### W-CE-11 — no in-game language switch (P2) — fixed, `56d8985`

**How a student's language is set today.** Interface: `localStorage.gs_language` (written by `LanguageSwitcher` and by the i18next browser detector), sent as `Accept-Language` on every request by `api/client.js`; most routes resolve `get_user_language` = header first, then the enrolment. Team: `Enrollment.language` (default `'en'`), read by `language_for_team` (R43: first active enrolment that states one) and by `get_team_language` for Phase 2. Preference store: **`PUT /api/user/preferences/`** (`LanguagePreferenceView`, existing) writes the caller's enrolment language. The switch existed only on the login page, where there is no token, so the preference route was never reached and the enrolment kept `'en'`.

**Repair.** No route, no model. `LanguageSwitcher` is rendered in the student top bar (`design-system/TopBar.jsx`) and the console header, and records the choice through `api/auth.setLanguagePreference` (the existing route, via the API client rather than a raw `fetch`). `AuthContext.login` calls `syncLanguagePreference(userData)`: the login-page choice is sent once at sign-in when it differs from what the server holds, so it becomes the team's stated language (the client half of W-CE-15).

**Red → green.** Jest (`LanguageSwitcher.test.js`, `AuthContext.test.js`, console guard): red `Tests: 5 failed, 5 passed` (`syncLanguagePreference is not a function`) and, for the switch alone, `✕ records the choice through the preference route when signed in`, `✕ the student top bar renders the switch`. Green (with `MarketResearchPage.analyst`, `marketResearchColours`): `Tests: 26 passed`.

### W-CE-15 — the analyst refusal in English on the zh-CN screen (P1) — fixed (client half `56d8985`, server proof in the backend commit)

**Source.** Not a missing catalogue key: `analyst_not_enabled` has both languages. The route follows R43 — `language_for_team(team, request)` — and the team's first enrolment said `'en'` because nothing had ever recorded the login-page choice (see W-CE-11). The screen was zh-CN from the header, the refusal `en` from the enrolment.

**Repair.** The sign-in and the in-game switch now record the choice through the existing preference route (W-CE-11), so the enrolment states what the student chose and the team's language is Chinese. `AnalystRefusalLanguageTests` pins the three states: the walkthrough as it was (header zh-CN, enrolment default → English), the sign-in choice recorded through `PUT /api/user/preferences/` → the refusal is Chinese with no Latin word, and the team's language governing over the header (R43).

**Red → green.** The red is the client's: `AuthContext.test.js` `✕ a choice that differs from the stored preference is sent at sign-in` (`syncLanguagePreference is not a function`). The backend tests are the server half of the flow and pass on the base as well as after; they are recorded as the proof that the route the client now calls has the effect claimed. See (g) for the R43 caveat.

### W-CE-16 — English on zh-CN student screens (P1) — fixed in four commits

**(a) `f5f757f` Summary checklist, dashboard next-action card, login taglines.** Source: literals in `SummaryPage.js` (section names, status tags, every guidance sentence, “Fix in …”, the “Finish the blocked items” notice), `GameDashboard.js` (NEXT REQUIRED ACTION, its two sentences, the checklist statuses) and `LoginPage.js` (both taglines). Repair: t() keys in both catalogues (`summary_page.*`, `dashboard.*`, `login.tagline`, `login.brand_line`); the Summary's R&D guidance no longer tells a team to upgrade a feature (the server refuses that — W-CE-03, another builder's). Red `Tests: 10 failed, 7 passed` → green `Tests: 20 passed` (render test with `t` stubbed: no run of three English words left on the page).

**(b) backend sentences a view wrote as f-strings** (commit with the backend batch). Source: `scorecard.py` Strategic Signals (5 f-strings), `decisions.py` M&A `locked_reasons` (3) and the R&D `budget_source` sentence, `research_reports.py` rating words (importance / fit / growth / price sensitivity / channel fit / channel names / opportunity signals / “All Markets” / “Global” / “N/A”). Repair: participant-catalogue keys (`signal_*`, `ma_*`, `rd_budget_source`, `research_*`) rendered in the request's language; the research view now reasons in codes (`_fit_code` …) and renders the word at the edge, sending both the word and a `*_code` so `MarketResearchPage` colours by the code — the opportunity rules used to compare English words and would have switched off silently under translation. Red: Jest `marketResearchColours.test.js` `Tests: 2 failed`; backend `ViewSentenceLanguageTests` — see (e).

**(c) `be4aad1` R&D guidance box, finance save states, hints, tax-card tags.** String replacements only, kept local because other builders edit both pages: `rd.guidance_title/desc` (the sentence pointing at the refused feature upgrade dropped), `rd.invest_next_level`, `rd.cost_exceeds_budget`, `rd.saving`, `rd.current_draft` + the draft table columns; `finance.unsaved_budget … financing_save_failed` (8), `finance.round_budget_remaining`, `finance.amount_entry_hint`, `finance.setup_cost`, `finance.regulators_modifier`. Red `Tests: 21 failed, 15 passed` → green `Tests: 40 passed`.

**(d) Phase-2 template fallbacks in Chinese, selected by the team's language** (commit with the backend batch). Source: `_build_briefing_fields` (executive summary, recommendations, risk alerts), `_compliance_fallback`, `_sc_event_fallback` in `engine/narratives.py`; `_fallback_evaluation` in `rag/communication_eval.py` (“Automated evaluation unavailable…”); the ten coach alerts in `engine/instructor_alerts.py` — all English f-strings, and the walkthrough's stack had no model, so every narrative a Chinese team read was one of these. Repair: a `_FALLBACK_TEXT` / `_ALERT_TEXT` table per module in both languages, English byte-identical to what shipped; the briefing and the compliance notice follow `get_team_language(team)`, the supply-chain event `get_instructor_language(game)` (stored once per event, the same choice the model path makes), the memo evaluation the team, the coach alerts the instructor (with the market and entry-mode names localised). The terminology test now reads these tables. Tests: `NarrativeFallbackLanguageTests` — see (e).

**News and ticker narratives:** the injected/fired event narrative now follows the reader (W-CE-06). The Industry News **headlines** (“Slight uptick in consumer confidence. Holiday season approaching.”) are `MarketConditionByRound.market_outlook_narrative`, scenario-authored with **no Chinese field on the model** — listed in (d) below, not fixed (a field is a model change).

### W-CE-17 — English on the zh-CN console (P1) — fixed, `3de618a` (+ the coach alerts in the backend batch)

**Source.** Literals in `InstructorDashboard.js` (tab “Students & Logins”; statistics titles “Decision round / Round status / Game status” and their values, the stored game status token in three places; the Monitoring banner; the Extend modal's “hours”; the roster CSV hint and “student(s)” counts; the rubric placeholders; the team-summary CSV headers), the whole `InstructorSCPanel.js` (English by construction: ~45 strings) and `AuditEvidenceTable.js` (title, columns, notices); the AI Coach alerts came from the backend f-strings (16 d).

**Repair.** 80 `instructor.*` keys; `gameStatusLabel()`, `severityLabel()`, `weightLabel()` with one literal key per value; the CSV export's column names follow the console's language and its status column is the label. `InstructorSCPanel` joins the whole-scan console guard; the audit table's render test asserts by key.

**Red → green.** Jest (console guard, `AuditEvidenceTable.test`, `consolePanelsLanguage`): red `Tests: 29 failed, 22 passed` → green (with `instructorDashboardMessages`) `Tests: 63 passed`.

### The sweep — `dd7a81c` (what fit) and (d) below (what did not)

The CRV2-12 scan (`englishLiteralScan.js`: JSX text, bare lines, spoken props, spoken fallbacks, computed keys, missing keys) over the 46 student and console sources the walkthrough visited: 209 raw findings, of which after removing CSS/antd tokens 33 were English a person reads. Fixed here: the finance over-allocation banner and the tax-card “net positive / net negative if audited”, the product-name placeholder, the corporate page's two revocation notices and “HQ: n”, the marketing page's raw positioning token, the activity banner's “a decision”, the round selector's default “Round”, the console's grading tooltips and two placeholders. Red `Tests: 14 failed, 66 passed` → green `Tests: 86 passed`.

---

## (c) Every new or changed zh-CN sentence — for a native reviewer, least-trusted first

**Tier 1 — prose written from scratch, no precedent in the catalogues (review first).**

| where | key | en | zh-CN |
|---|---|---|---|
| narratives.py | briefing_heading | **Quarter {round} Results** | **第 {round} 回合业绩** |
| narratives.py | briefing_revenue_grew | Revenue grew {pct}% to ${revenue}. | 收入增长 {pct}%，达到 ${revenue}。 |
| narratives.py | briefing_revenue_declined | Revenue declined {pct}% to ${revenue}. | 收入下降 {pct}%，降至 ${revenue}。 |
| narratives.py | briefing_revenue_flat | Revenue: ${revenue}. | 收入：${revenue}。 |
| narratives.py | briefing_summary | {heading} / {revenue_line} Net income: … Cash position: … | {heading} / {revenue_line}净利润：${net_income}。现金状况：${cash}。 |
| narratives.py | briefing_cash_distress | Cash position below $1M — financial distress risk. | 现金低于 100 万美元——存在财务困境风险。 |
| narratives.py | rec_profitability | Reduce operating costs or increase revenue to restore profitability. | 削减运营成本或提高收入，以恢复盈利。 |
| narratives.py | rec_cash | Shore up cash reserves — consider reducing dividends or raising capital. | 充实现金储备——考虑减少股利或筹集资本。 |
| narratives.py | rec_margin | Gross margins are thin — review pricing or COGS structure. | 毛利率偏低——请检查定价或销售成本结构。 |
| narratives.py | rec_maintain | Maintain current trajectory and explore growth opportunities. | 保持当前发展轨迹，并探索增长机会。 |
| narratives.py | risk_cash | Cash below $1M — financial distress imminent. | 现金低于 100 万美元——财务困境迫在眉睫。 |
| narratives.py | risk_margin | Net margin at {pct}% — losses unsustainable. | 净利润率为 {pct}%——亏损不可持续。 |
| narratives.py | risk_no_revenue | No revenue generated — all spending is a loss. | 没有产生任何收入——所有支出均为亏损。 |
| narratives.py | risk_leverage | Debt exceeds equity — leverage risk elevated. | 负债超过权益——杠杆风险上升。 |
| narratives.py | sc_event_generic | A {severity} supply-chain event ({name}) disrupted sourcing this round. | 一起{severity}级供应链事件（{name}）扰乱了本回合的采购。 |
| narratives.py | compliance_all_markets / enforcement / cost / frozen | all markets / {regime} enforcement in {market}: {trigger}. / Remediation/penalty cost ${cost}. / Market access is frozen through round {round}. | 所有市场 / {regime}在{market}的执法：{trigger}。 / 整改/处罚成本 ${cost}。 / 市场准入冻结至第 {round} 回合。 |
| instructor_alerts.py | cash_crisis (title/detail/note) | {team} has only ${cash} cash remaining / At current burn rate… / This is a teaching moment… | {team} 的现金仅剩 ${cash} / 按当前消耗速度，该团队可能在 1-2 个回合内耗尽现金。负债：…，净利润：…。警惕困境螺旋——陷入财务困境的团队常会做出孤注一掷的决策。 / 这是讲解现金管理与财务规划的教学时机。可以问该团队："你们的现金预测是多少？是否计入了所有成本？" |
| instructor_alerts.py | leverage | {team} debt-to-equity ratio at {ratio} / Total debt… / Discuss the trade-offs… Modigliani-Miller | {team} 的资产负债率达到 {ratio} / 总负债：…，权益：…。利息支出：每回合 …。这一杠杆水平会限制未来的借款能力并增加风险。 / 讨论债务融资与股权融资的权衡。参考：莫迪利安尼-米勒定理及现实中的资本结构决策。 |
| instructor_alerts.py | revenue_decline | {team} revenue declined {pct}% this round / Revenue: … / Revenue decline in a growing market… | {team} 本回合收入下降 {pct}% / 收入：…（上回合为 …）。请检查原因是定价、生产、市场份额流失还是汇率影响。 / 在增长的市场中收入下降，说明存在竞争压力。可以问："你们的竞争地位发生了什么变化？是竞争对手进步了，还是你们停滞不前？" |
| instructor_alerts.py | no_rd | {team} has not invested in R&D for {rounds} consecutive rounds / Their technology capability… / Classic short-term thinking trap… Innovator's Dilemma | {team} 已连续 {rounds} 个回合未投入研发 / 其技术能力停滞不前，而竞争对手可能正在进步。这将削弱其在技术敏感型细分市场中的契合度得分。 / 典型的短视思维陷阱：团队为了短期利润牺牲长期能力。参考：《创新者的窘境》——成熟企业在创新上投入不足。 |
| instructor_alerts.py | single_market | {team} still operates in only {count} market (Round {round}) / Remaining in one market… / Discuss market entry timing… Uppsala | {team} 仍只在 {count} 个市场运营（第 {round} 回合） / 停留在单一市场会限制收入增长潜力，并增加集中度风险。 / 讨论市场进入时机。参考：乌普萨拉国际化模型——企业常因不确定性而推迟进入海外市场，但推迟也有代价。 |
| instructor_alerts.py | coherence_high | {team} achieved a coherence score of {score}/100 / Their strategy is internally consistent… / Highlight this in debrief… | {team} 的战略一致性得分达到 {score}/100 / 其战略内部一致：定价与定位相符，分销与细分市场匹配，进入模式与风险特征相称。 / 在复盘中将此作为战略协同的范例加以强调。是哪些具体选择造就了这种一致性？ |
| instructor_alerts.py | index_drop | {team} performance index dropped {drop} points / Index: … / A sharp index drop… | {team} 的绩效指数下降了 {drop} 点 / 指数：{index}（此前为 {previous}）。满意度得分：{satisfaction}。 / 指数骤降表明多个利益相关者群体同时感到不满。该团队可能摊子铺得太开，或做出了相互矛盾的决策。 |
| instructor_alerts.py | acquisition | {team} acquired {target} / Cost: … / Good opportunity to discuss M&A strategy… | {team} 收购了 {target} / 成本：${cost}。整合需要 {rounds} 个回合。 / 这是讨论并购战略的好机会：此次收购是否创造了价值？团队预期哪些协同效应？整合成本将如何影响近期业绩？ |
| instructor_alerts.py | market_entry | {team} entered {market} via {mode} / Investment: … / Discuss entry mode choice… Dunning's OLI | {team} 通过{mode}进入了{market} / 投资：${investment}。该市场增长率为 {growth}%，关税率为 {tariff}%。 / 讨论进入模式的选择：它是否与该市场的风险特征相匹配？参考：邓宁的 OLI 框架（进入模式选择）。 |
| instructor_alerts.py | overproduction | {team} producing 2x+ last round sales for {product} in {market} / Production: … | {team} 在{market}的 {product} 产量超过上回合销量的两倍 / 生产：{volume} 台。上回合销量：{sold} 台。这可能导致大量库存积压。 |
| instructor_alerts.py | unknown_mode | unknown mode | 未知模式 |
| communication_eval.py | criterion / strength / gap / overall | Automated evaluation unavailable. Score based on submission completeness. / Communication submitted within word limit / LLM evaluation unavailable — detailed feedback not generated / This communication was evaluated using a fallback heuristic… | 自动评估不可用。得分基于提交内容的完整性。 / 沟通稿在字数限制内提交 / 模型评估不可用——未生成详细反馈 / 由于评估模型不可用，本沟通稿采用备用规则进行评估。得分仅反映提交内容的完整性。 |

**Tier 2 — catalogue sentences and labels (participant_messages / operator_messages / events.py).**

| where | key | en | zh-CN |
|---|---|---|---|
| participant_messages | signal_rd_low | R&D investment is {pct}% of revenue. Competitors may be outpacing your innovation. | 研发投入仅占收入的 {pct}%。竞争对手的创新可能正在超越您。 |
| participant_messages | signal_tech_low | Technology capability at {pct}%. A next-generation platform is available for development. | 技术能力为 {pct}%。新一代平台已可开发。 |
| participant_messages | signal_satisfaction_low | Customer satisfaction is below average. Review Market Research to identify underperforming segments. | 客户满意度低于平均水平。请查看市场研究，找出表现不佳的细分市场。 |
| participant_messages | signal_single_market | Operating in {entered} of {total} markets. International expansion could unlock growth. | 目前仅在 {total} 个市场中的 {entered} 个开展业务。国际扩张可能带来增长。 |
| participant_messages | signal_leverage | Debt-to-equity ratio at {ratio}. Conservative investors may be concerned. | 资产负债率为 {ratio}。保守型投资者可能会感到担忧。 |
| participant_messages | ma_available_from_round / ma_requires_presence / ma_already_acquired | Available from Round {round} / Requires presence in {market} / Already acquired by {team} | 第 {round} 回合起可用 / 需要先进入{market} / 已被{team}收购 |
| participant_messages | rd_budget_source | 20% of previous round net profit ({profit}) + base allocation ({base}) | 上一回合净利润的 20%（{profit}）+ 基础拨款（{base}） |
| participant_messages | summary_section_optional | Optional this round. Locking your decisions does not require it. | 本回合为可选项，锁定决策时无需完成。 |
| participant_messages | research_importance_* | Critical / High / Moderate / Low | 关键 / 高 / 中等 / 低 |
| participant_messages | research_fit_* | Strong / Moderate / Weak / Very Weak | 强 / 中等 / 弱 / 很弱 |
| participant_messages | research_growth_* | Fastest / Fast / Moderate growth / Slow growth / Moderate / Slow | 最快 / 快速 / 温和增长 / 缓慢增长 / 温和 / 缓慢 |
| participant_messages | research_price_* | Very High / High / Moderate / Low | 很高 / 高 / 中等 / 低 |
| participant_messages | research_channel_fit_* | Excellent / Good / Moderate / Poor | 极佳 / 良好 / 中等 / 较差 |
| participant_messages | research_channel_* | Mass Retail / Selective Retail / Exclusive Retail / Direct Online / Hybrid | 大众零售 / 精选零售 / 独家零售 / 直销在线 / 混合渠道 |
| participant_messages | research_all_markets / research_global / research_no_competitor | All Markets / Global / None | 所有市场 / 全球 / 无 |
| participant_messages | research_opportunity_growing_uncaptured | Growing segment you're not capturing. Investigate fit gaps. | 该细分市场正在增长，但您尚未获取份额。请排查契合度差距。 |
| participant_messages | research_opportunity_lead_eroding | Your lead may be eroding. Check competitor moves. | 您的领先地位可能正在削弱。请关注竞争对手动向。 |
| participant_messages | research_opportunity_underserved | Large underserved segment. First-mover advantage available. | 大型且服务不足的细分市场，具备先发优势。 |
| participant_messages | research_opportunity_high_margin_mismatch | High-margin segment. Your capabilities may not match their expectations. | 高利润细分市场，但您的能力可能不符合其期望。 |
| participant_messages | research_opportunity_price_competition | Dominated by price competition. Margins thin. | 价格竞争激烈，利润率微薄。 |
| participant_messages | research_opportunity_protect_expand | Growing segment where you have strong fit. Protect and expand. | 您在该增长细分市场契合度高。请巩固并扩大。 |
| operator_messages | SUBMISSION_ORIGIN_LABELS | No submission / Draft (not locked) / Locked by team / Auto-locked at deadline / Never submitted — defaulted at close | 未提交 / 草稿（未锁定） / 团队已锁定 / 截止时自动锁定 / 从未提交——回合关闭时按默认处理 |
| events.py | _NARRATIVE_WORDS | global markets / significant | 全球市场 / 显著 |

**Tier 3 — frontend catalogue keys (144), in the order they were added.**

| id | key | en | zh-CN |
|---|---|---|---|
| W-CE-08 | `instructor.submission_status_locked` | Locked | 已锁定 |
| W-CE-08 | `instructor.submission_status_draft` | Draft (not locked) | 草稿（未锁定） |
| W-CE-08 | `instructor.submission_status_empty` | No decisions saved | 尚未保存任何决策 |
| W-CE-22 | `market_strategy.distance_home` | Home market | 本土市场 |
| W-CE-22 | `market_strategy.distance_low` | Low | 低 |
| W-CE-22 | `market_strategy.distance_medium` | Medium | 中等 |
| W-CE-22 | `market_strategy.distance_high` | High | 高 |
| W-CE-22 | `market_strategy.distance_very_high` | Very high | 极高 |
| W-CE-22 | `market_strategy.distance_unknown` | Not rated | 未评级 |
| W-CE-22 | `market_strategy.plant_operational` | Operational | 运营中 |
| W-CE-22 | `market_strategy.plant_decommissioned` | Decommissioned | 已停用 |
| W-CE-22 | `market_strategy.per_round_charge` | {{amount}}/round | 每回合 {{amount}} |
| W-CE-22 | `market_strategy.plant_cost_not_available` | cost not set in this scenario | 本情景未设定建设费用 |
| W-CE-13 | `summary_page.optional` | Optional | 可选 |
| W-CE-16 (a) | `summary_page.status_complete` | Complete | 已完成 |
| W-CE-16 (a) | `summary_page.status_needs_review` | Needs review | 需要复核 |
| W-CE-16 (a) | `summary_page.status_blocked` | Blocked | 受阻 |
| W-CE-16 (a) | `summary_page.status_not_started` | Not started | 未开始 |
| W-CE-16 (a) | `summary_page.guidance_draft_saved` | This requirement has draft work saved. | 此项已保存草稿。 |
| W-CE-16 (a) | `summary_page.guidance_rd` | Open R&D Investment and choose this round's R&D action. | 请打开“研发投资”页面，选择本回合的研发行动。 |
| W-CE-16 (a) | `summary_page.guidance_budget` | Open Finance and allocate R&D, Marketing, and Strategy budgets. | 请打开“财务管理”页面，分配研发、营销和战略预算。 |
| W-CE-16 (a) | `summary_page.guidance_open_section` | Open {{section}} to complete this requirement. | 请打开“{{section}}”完成此项要求。 |
| W-CE-16 (a) | `summary_page.fix_in` | Fix in {{section}} | 前往{{section}}修正 |
| W-CE-16 (a) | `summary_page.finish_blocked_title` | Finish the blocked items above before locking this round. | 请先完成上方受阻的事项，再锁定本回合。 |
| W-CE-16 (a) | `summary_page.finish_blocked_desc` | Use each Fix button to jump to the page where that decision is completed. | 点击各“修正”按钮可跳转到完成该决策的页面。 |
| W-CE-16 (a) | `login.brand_line` | Clarity. Capability. Camdani. | 清晰。能力。Camdani。 |
| W-CE-16 (a) | `login.tagline` | Built for Real Work, Not Just Coursework | 为真实工作而建，不止于课程作业 |
| W-CE-16 (a) | `dashboard.next_required_action` | NEXT REQUIRED ACTION | 下一步必做事项 |
| W-CE-16 (a) | `dashboard.continue_here_first` | Continue here first. The checklist below updates as each draft decision is saved. | 请先从这里继续。下方清单会随每项草稿决策的保存而更新。 |
| W-CE-16 (a) | `dashboard.continue_to` | Continue to {{page}} | 继续：{{page}} |
| W-CE-16 (a) | `dashboard.open_review` | Open Review & Submit to check the round. | 请打开“审核并提交”检查本回合。 |
| W-CE-17 | `instructor.students_logins` | Students & Logins | 学生与登录 |
| W-CE-17 | `instructor.stat_decision_round` | Decision round | 决策回合 |
| W-CE-17 | `instructor.stat_round_status` | Round status | 回合状态 |
| W-CE-17 | `instructor.stat_game_status` | Game status | 游戏状态 |
| W-CE-17 | `instructor.round_state_open` | Open for student decisions | 开放供学生决策 |
| W-CE-17 | `instructor.round_state_closed` | Closed; awaiting processing | 已关闭；等待结算 |
| W-CE-17 | `instructor.round_state_processed` | Processed; results available | 已结算；结果可查看 |
| W-CE-17 | `instructor.round_state_pending` | Not open yet | 尚未开放 |
| W-CE-17 | `instructor.game_status_setup` | setup | 设置中 |
| W-CE-17 | `instructor.game_status_active` | active | 进行中 |
| W-CE-17 | `instructor.game_status_paused` | paused | 已暂停 |
| W-CE-17 | `instructor.game_status_completed` | completed | 已结束 |
| W-CE-17 | `instructor.game_status_archived` | archived | 已归档 |
| W-CE-17 | `instructor.monitoring_title` | Monitoring {{game}} | 正在监控 {{game}} |
| W-CE-17 | `instructor.monitoring_desc` | Decision round {{round}} of {{total}} is {{state}}. Game status: {{status}}. Latest processed results round: {{processed}}. | 第 {{round}} 回合（共 {{total}} 回合）当前{{state}}。游戏状态：{{status}}。最近已结算的结果回合：第 {{processed}} 回合。 |
| W-CE-17 | `instructor.hours_unit` | hours | 小时 |
| W-CE-17 | `instructor.csv_format_hint` | CSV format: {{columns}} (header row required) | CSV 格式：{{columns}}（需要标题行） |
| W-CE-17 | `instructor.students_count` | {{count}} student(s) | {{count}} 名学生 |
| W-CE-17 | `instructor.teams_students_assigned` | {{teams}} teams · {{assigned}}/{{total}} students assigned | {{teams}} 个团队 · 已分配 {{assigned}}/{{total}} 名学生 |
| W-CE-17 | `instructor.teams_count_status` | {{teams}} teams · Status: | {{teams}} 个团队 · 状态： |
| W-CE-17 | `instructor.category_name_placeholder` | Category name (e.g. Strategic Coherence) | 类别名称（例如：战略一致性） |
| W-CE-17 | `instructor.csv_headers_note` | Exported column names follow the console's language. | 导出的列名与控制台语言一致。 |
| W-CE-17 | `instructor.audit_evidence_title` | Submission audit evidence | 提交审计记录 |
| W-CE-17 | `instructor.audit_load_failed` | Audit evidence could not be loaded | 无法加载审计记录 |
| W-CE-17 | `instructor.audit_not_empty_note` | This is not the same as an empty audit trail. Retry before concluding anything about what this team submitted. | 这不等同于审计记录为空。在对该团队提交内容下结论之前，请先重试。 |
| W-CE-17 | `instructor.audit_no_saves` | No recorded saves for this round | 本回合没有记录到任何保存操作 |
| W-CE-17 | `instructor.endpoint` | Endpoint | 接口 |
| W-CE-17 | `instructor.payload_sha256` | Payload SHA-256 | 载荷 SHA-256 |
| W-CE-17 | `instructor.payload` | Payload | 载荷 |
| W-CE-17 | `instructor.retry` | Retry | 重试 |
| W-CE-17 | `instructor.severity_low` | low | 低 |
| W-CE-17 | `instructor.severity_medium` | medium | 中 |
| W-CE-17 | `instructor.severity_high` | high | 高 |
| W-CE-17 | `instructor.severity_critical` | critical | 严重 |
| W-CE-17 | `instructor.sc_inject_title` | Inject supply-chain event | 注入供应链事件 |
| W-CE-17 | `instructor.sc_pick_disruption` | Pick a supply-chain disruption to inject | 选择要注入的供应链中断事件 |
| W-CE-17 | `instructor.sc_inject_tooltip` | Queues the event onto the current open round; it fires (real supplier/lane disruption) when you advance the round. | 将事件排入当前开放回合；推进回合时触发（真实的供应商/运输线路中断）。 |
| W-CE-17 | `instructor.sc_inject` | Inject | 注入 |
| W-CE-17 | `instructor.sc_injects_onto_round` | Injects onto round {{round}} (fires on next advance). | 将注入第 {{round}} 回合（下次推进时触发）。 |
| W-CE-17 | `instructor.sc_injections_queued` | {{count}} injection(s) queued — fire on next round advance | 已排队 {{count}} 个注入事件 — 下次推进回合时触发 |
| W-CE-17 | `instructor.sc_injection_row` | {{event}} ({{severity}}) — fires when round {{round}} is advanced | {{event}}（{{severity}}）— 推进第 {{round}} 回合时触发 |
| W-CE-17 | `instructor.sc_disruptions_active` | {{count}} disruption(s) active this round | 本回合有 {{count}} 个中断事件生效中 |
| W-CE-17 | `instructor.sc_supplier_disruption` | Supplier {{name}} ({{country}}) — capacity {{pct}}%, {{rounds}} recovery round(s) left | 供应商 {{name}}（{{country}}）— 产能 {{pct}}%，剩余 {{rounds}} 个恢复回合 |
| W-CE-17 | `instructor.sc_lane_disruption` | Lane {{name}} — {{disruption}} (freight ×{{rate}}) | 线路 {{name}} — {{disruption}}（运费 ×{{rate}}） |
| W-CE-17 | `instructor.sc_audit_title` | Per-team supply-chain audit | 各团队供应链审计 |
| W-CE-17 | `instructor.sc_round_tag` | round {{round}} | 第 {{round}} 回合 |
| W-CE-17 | `instructor.sc_no_teams` | No teams / no SC data yet. | 暂无团队或供应链数据。 |
| W-CE-17 | `instructor.sc_overrides_title` | Class resilience-weight overrides | 班级韧性权重覆盖 |
| W-CE-17 | `instructor.sc_weights_sum_hint` | the 6 weights must sum to 1.0 | 6 项权重之和必须为 1.0 |
| W-CE-17 | `instructor.sc_weight_now` | {{label}} (now {{value}}) | {{label}}（当前 {{value}}） |
| W-CE-17 | `instructor.sc_value` | value | 数值 |
| W-CE-17 | `instructor.sc_save_override` | Save override | 保存覆盖 |
| W-CE-17 | `instructor.sc_resilience` | Resilience | 韧性 |
| W-CE-17 | `instructor.sc_not_scored` | not scored | 未评分 |
| W-CE-17 | `instructor.sc_sourcing_strategy` | Sourcing strategy | 采购策略 |
| W-CE-17 | `instructor.sc_single_source_risk` | Single-source risk | 单一来源风险 |
| W-CE-17 | `instructor.sc_none` | none | 无 |
| W-CE-17 | `instructor.sc_buffer_days` | Buffer (days) | 缓冲（天） |
| W-CE-17 | `instructor.sc_contingency` | Contingency | 应急预案 |
| W-CE-17 | `instructor.sc_ready` | ready | 已就绪 |
| W-CE-17 | `instructor.sc_compliance` | Compliance | 合规 |
| W-CE-17 | `instructor.sc_frozen_through` | {{regime}}{{market}} — frozen thru R{{round}} | {{regime}}{{market}} — 冻结至第 {{round}} 回合 |
| W-CE-17 | `instructor.sc_clear` | clear | 无 |
| W-CE-17 | `instructor.sc_disruption_impact` | Disruption impact | 中断影响 |
| W-CE-17 | `instructor.sc_capacity_pct` | capacity {{pct}}% | 产能 {{pct}}% |
| W-CE-17 | `instructor.sc_lost_revenue` | lost {{amount}} | 损失 {{amount}} |
| W-CE-17 | `instructor.sc_components_title` | Resilience components (weighted) | 韧性构成（加权） |
| W-CE-17 | `instructor.sc_weight_multi_sourcing` | Multi-sourcing | 多元采购 |
| W-CE-17 | `instructor.sc_weight_geographic_diversity` | Geographic diversity | 地域多样性 |
| W-CE-17 | `instructor.sc_weight_buffer_inventory` | Buffer inventory | 缓冲库存 |
| W-CE-17 | `instructor.sc_weight_modal_flexibility` | Modal flexibility | 运输方式灵活性 |
| W-CE-17 | `instructor.sc_weight_tier2_visibility` | Tier-2 visibility | 二级供应商可见性 |
| W-CE-17 | `instructor.sc_weight_supplier_financial_health` | Supplier fin. health | 供应商财务健康 |
| W-CE-17 | `instructor.sc_no_allocations` | No sourcing allocations this round. | 本回合没有采购分配。 |
| W-CE-17 | `instructor.sc_input` | Input | 投入品 |
| W-CE-17 | `instructor.sc_supplier` | Supplier | 供应商 |
| W-CE-17 | `instructor.sc_country` | Country | 国家 |
| W-CE-17 | `instructor.sc_allocation_pct` | Allocation % | 分配比例 % |
| W-CE-17 | `instructor.sc_disrupted` | disrupted | 已中断 |
| W-CE-17 | `instructor.sc_ok` | ok | 正常 |
| W-CE-16 (c) | `rd.guidance_title` | Choose one R&D action for this round | 为本回合选择一项研发行动 |
| W-CE-16 (c) | `rd.guidance_desc` | You have {{remaining}} of R&D budget remaining and {{open}} of {{max}} investment slots open. | 您剩余 {{remaining}} 的研发预算，投资槽位还有 {{open}}/{{max}} 个可用。 |
| W-CE-16 (c) | `rd.invest_next_level` | Invest next level | 投资下一级 |
| W-CE-16 (c) | `rd.cost_exceeds_budget` | Cost exceeds R&D budget | 成本超出研发预算 |
| W-CE-16 (c) | `rd.saving` | Saving... | 保存中... |
| W-CE-16 (c) | `rd.current_draft` | CURRENT R&D DRAFT | 当前研发草稿 |
| W-CE-16 (c) | `finance.unsaved_budget` | Unsaved budget changes | 预算更改尚未保存 |
| W-CE-16 (c) | `finance.saving_budget` | Saving budget... | 正在保存预算... |
| W-CE-16 (c) | `finance.budget_saved` | Budget saved | 预算已保存 |
| W-CE-16 (c) | `finance.budget_save_failed` | Budget save failed | 预算保存失败 |
| W-CE-16 (c) | `finance.unsaved_financing` | Unsaved financing changes | 融资更改尚未保存 |
| W-CE-16 (c) | `finance.saving_financing` | Saving financing... | 正在保存融资... |
| W-CE-16 (c) | `finance.financing_saved` | Financing saved | 融资已保存 |
| W-CE-16 (c) | `finance.financing_save_failed` | Financing save failed | 融资保存失败 |
| W-CE-16 (c) | `finance.round_budget_remaining` | Round {{round}} budget remaining | 第 {{round}} 回合剩余预算 |
| W-CE-16 (c) | `finance.amount_entry_hint` | Enter dollar amounts directly. Examples: 2500000, $2,500,000, or 2.5M. | 请直接输入美元金额。例如：2500000、$2,500,000 或 2.5M。 |
| W-CE-16 (c) | `finance.setup_cost` | Setup: {{cost}} | 设置费用：{{cost}} |
| W-CE-16 (c) | `finance.regulators_modifier` | Regulators: {{value}} | 监管机构：{{value}} |
| sweep | `dashboard.supply_chain_tab` | Supply Chain | 供应链 |
| sweep | `finance.over_allocated` | Allocated budget {{allocated}} exceeds the Round {{round}} operating budget {{available}}. | 已分配预算 {{allocated}} 超出第 {{round}} 回合的运营预算 {{available}}。 |
| sweep | `products_page.name_placeholder` | e.g. Nexus Pro | 例如：Nexus Pro |
| sweep | `corporate_strategy.revoke_penalty_warning` | Revoking triggers a {{rounds}}-round investor confidence penalty ({{drop}}). | 撤销将触发持续 {{rounds}} 回合的投资者信心惩罚（{{drop}}）。 |
| sweep | `corporate_strategy.revocation_penalty_active` | Revocation penalty active: {{rounds}} round(s) remaining | 撤销惩罚生效中：剩余 {{rounds}} 回合 |
| sweep | `corporate_strategy.hq_count` | HQ: {{count}} | 总部：{{count}} |
| sweep | `marketing.positioning_budget` | Budget | 经济型 |
| sweep | `marketing.positioning_mainstream` | Mainstream | 主流型 |
| sweep | `marketing.positioning_premium` | Premium | 高端型 |
| sweep | `marketing.positioning_ultra_premium` | Ultra premium | 超高端型 |
| sweep | `common.a_decision` | a decision | 一项决策 |
| sweep | `instructor.select_section_first` | Select a section first | 请先选择班级 |
| sweep | `instructor.no_simulation_linked` | No simulation linked to this section | 该班级尚未关联模拟游戏 |
| sweep | `instructor.game_name_placeholder` | e.g. Spring 2026 Simulation | 例如：2026 春季模拟 |
| sweep | `instructor.csv_example_placeholder` | student_id,display_name,email 12345,John Doe,john@university.edu | student_id,display_name,email 12345,张三,zhangsan@university.edu |

---

## (d) Remaining English a zh-CN user can still see on the walkthrough's screens — not fixed here, precisely

Found by the same scan, or by reading the server. Each names the file and why it is outside this pass.

| # | screen | source | what | why not here |
|---|---|---|---|---|
| 1 | Industry News headlines (“Slight uptick in consumer confidence. Holiday season approaching.”, “Euro weakening slightly…”) | `MarketConditionByRound.market_outlook_narrative`, scenario YAML lines 5823, 5921 | scenario-authored, English only; **no `_zh` field on the model** | a model field + migration + scenario authoring; W-CE-16 named it; needs the owner/scenario author |
| 2 | Financial Reports › Trade Finance & FX section | `pages/FinancialReportsPage.js` lines 786–820 and the FX/instrument tables (≈20 literals: “Open FX hedge positions”, “Pair / Notional / Locked rate / Mark-to-market / Realized P&L”, “Buyer payment instruments”, “Export-credit (Sinosure) coverage”, credit-rating words `BBB+ / VERY LOW … DISTRESS`) | hard-coded | a whole section outside the named defects; the credit-rating words are also colour keys |
| 3 | Trade Finance page instrument names (“Open Account”, “Letter of Credit”, “Cash in Advance”, “Sinosure Export Credit Insurance”) and Sourcing component names (“Camera Module”, “Final Assembly”, “Power Management”) | scenario-authored supply-chain data (`display_name`, supplier/component `name`); the CE scenario authors no Chinese counterpart | scenario authoring | not a code literal; needs the scenario author |
| 4 | Communications › audience tags (“Board of Directors”, “Investor Community”) | `TeamCommunication.assignment.get_audience_display()` in `cc32a_views.py` lines 101, 242, 272 — Django choice labels | English choice labels served as `audience_display` | fixable in a follow-up with a bilingual label table in the participant catalogue; found in the sweep after the backend batch was frozen |
| 5 | Communications › criterion names (“Framework Grounding”, “Risk Acknowledgment”, “Strategic Consistency”…) | scenario YAML `evaluation_criteria[].criterion` rendered by title-casing the token in `CommunicationsPage.js` | scenario-authored tokens | scenario authoring or a criterion label table |
| 6 | Logistics › “Incoterms” | `pages/LogisticsPage.js` title | a proper term (国际贸易术语) | judgment call; left |
| 7 | Onboarding image `alt` texts (“Your Global Challenge” …) | `components/OnboardingModal.js` lines 14–18 | accessibility text on images; not visible | out of scope |
| 8 | Keys reached through label maps (`t(variable)`): CompetitiveIntel 1, StrategyTools 7, Products 1, MarketStrategy 1, Sourcing 2, Logistics 2, TradeFinance 1, Inventory 4, Login 1 (demo buttons), InstructorDashboard 1 (`origin_${o}`), DecisionSaveAlert 1, StatusBadge 1 | the pattern inventoried in `handoff_readiness_v2/evidence/unresolved-locale-keys/keys-hidden-behind-label-maps.txt`, with the owner | invisible to the static scan; not new |
| 9 | Grading & Export › default rubric category names and descriptions (“Performance Index”, “Cumulative simulation score based on market performance…”) | server-created default rubric (`grading.py`), stored English text | stored data, not a literal on the screen | needs a decision on whether stored rubric text is authored per language |
| 10 | Operator Log › “Before → after” raw JSON with storage names | W-CE-07 | another builder's item | — |
| 11 | Product names (“Nova Nova”) and positioning shown as “Xmainstream” in the leak scan | team-authored product name + the positioning token | the token is fixed here (`marketing.positioning_*`); the name is the team's | — |

---

## (e) Tests and commands

**Backend** (every run `cd backend && flock -w … /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`, disposable Postgres; the host's disk was saturated by another builder's full suite for part of the afternoon, so two runs waited on the lock for over an hour — no budget was exceeded, the full run happened once).

| run | labels | result |
|---|---|---|
| W-CE-06 red / green | `test_walk_ce_language` (+ `test_engine.TestEventNarrativeGeneration`, `test_operator_refusal_language`, `test_player_language_guard`) | `Ran 8 … FAILED (failures=7)` → `Ran 65 tests … OK` |
| W-CE-08 red / green | `DrillDownStatusLabelTests` (+ `test_zh_terminology`, `test_operator_refusal_language`, `test_player_language_guard`, `test_competition_hardening`) | `FAILED (failures=2, errors=1)` → `Ran 76 tests … OK` |
| W-CE-22 red / green | `PlantCostContextTests` (+ `test_player_language_guard`) | `KeyError: 'plant_build_cost' … FAILED (failures=1, errors=1)` → `Ran 15 tests … OK` |
| W-CE-13 red / green | `SummaryOptionalSectionTests` (+ `test_crv2_12_language`, `test_player_language_guard`, `test_zh_terminology`) | `FAILED (failures=3, errors=1)` → `Ran 41 tests … OK` |
| W-CE-15 / 16 (b)(d) / 17 coach red | `ViewSentenceLanguageTests`, `NarrativeFallbackLanguageTests`, `AnalystRefusalLanguageTests` against the reverted runtime files | `Ran 14 tests … FAILED (failures=5, errors=8)` — the three `AnalystRefusalLanguageTests` pass by design (server half) |
| same, green | `test_walk_ce_language`, `test_player_language_guard`, `test_crv2_12_language`, `test_zh_terminology`, `test_operator_refusal_language`, `test_durable_narratives`, `test_narrative_llm_routing`, `test_cc17_narratives`, `test_paid_research`, `test_engine.TestEventNarrativeGeneration`, `test_competition_hardening` | first pass `Ran 219 … FAILED (failures=1, errors=1)` (a fixture missing `market_share_gained`; a doubled space in the English briefing fallback — both corrected before the freeze), then `Ran 219 tests in 29.7s … OK` |
| **the one full run**, from the frozen commit `573e256` | `scripts/test-postgres core --parallel 8` | started 20:46:07, `Ran 1549 tests in 203.974s … OK`, exit 0 at 20:50:12; no runtime code changed after it |

`test_walk_ce_language.py`: 10 classes, 30 tests.

**Frontend.**
- Focused Jest per id: quoted in (b).
- Full Jest: `CI=true npx react-scripts test --watchAll=false` → `Test Suites: 38 passed, 38 total · Tests: 448 passed, 448 total` (exit 0), run on the final working tree before the backend commit.
- `python3 backend/scripts/check-participant-strings`: `participant-string-hygiene: PASS 5536 unit(s) examined, 0 reviewed suppression(s)` (after the sweep); selftest: `selftest: 34 ok, 0 failed`.
- Production build with the ESLint ratchet (`CI=false GENERATE_SOURCEMAP=false npx react-scripts build`, `node eslint-warning-count.js`): on the frozen commit `573e256`: build exit 0; `eslint warnings: 55 (baseline 57)` — no new warning, two fewer (the two finance `useCallback` arrays that now call `t` list it); the baseline is lowered to 55 in the final commit, as the ratchet asks.
- String inventory regenerated last, from the repository root, in its own commit: `python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py` → `wrote 2584 candidate rows`; `--check` exit 0. Committed alone, after the full run, as the last commit on the branch.

---

## (f) Proposed register status text

| id | proposed status |
|---|---|
| W-CE-06 | Fixed `d29e857` — inject route renders the narrative; four readers render in the reader's language; legacy rows re-rendered. Guard: `TickerPlaceholderTests`, `EventNarrativeLanguageTests`. |
| W-CE-08 | Fixed `d985122` — status label by key; origin labels bilingual in `operator_messages`. Guard: `DrillDownStatusLabelTests`, console source guard. |
| W-CE-11 | Fixed `56d8985` — switch in the game top bar and console header; preference recorded through the existing `PUT /api/user/preferences/`; login-page choice sent at sign-in. No route, no model. |
| W-CE-13 | Fixed `863e7b0` — the four supply-chain sections marked optional by the server with a bilingual sentence; no Fix button. Overlap with W-CE-25 recorded (page-side required list untouched). |
| W-CE-15 | Fixed (client `56d8985`, server proof in the backend commit) — the enrolment now states the student's choice, so R43's team language is Chinese. Caveat for the owner in (g). |
| W-CE-16 | Fixed in four commits (a)(b)(c)(d) + sweep; remaining scenario-authored English listed in (d). |
| W-CE-17 | Fixed `3de618a` + coach alerts in the backend commit; console guard extended. Remaining: rubric text stored in English (d 9), operator log (W-CE-07). |
| W-CE-20 | Fixed `e1745f1` — decisions first, audit table collapsed after them, nothing removed. |
| W-CE-22 | Fixed `fdb0a2d` — authored plant figures served (null when unauthored, shown as “not set”), one per-round partnership charge, distance and plant status labelled. The $0 plant that the scenario authors no cost for is calibration (R48), left. |

---

## (g) Distrust list and observations

**Needs the owner.**
1. **R43's first-enrolment rule.** `language_for_team` takes the first active enrolment (by pk) that states a language. Every enrolment states one (`Enrollment.language` defaults to `'en'`), so “stated” cannot be told from “default”. After this pass each student's sign-in records their own choice, which fixes the walkthrough (both team-3 members signed in with zh-CN). It does not fix a team whose first member reads English and second reads Chinese: the second is refused in English on the analyst route while the rest of the screen is Chinese, by R43 as ruled. Whether the team's language should be the reader's enrolment, a majority, or the first member's is the owner's call; no rule was changed here.
2. **The scenario's English-only content** (d 1, 3, 5) — a model field for `market_outlook_narrative_zh` and Chinese authoring of the CE supply-chain data.

**Needs a native speaker.** Every row of (c), tier 1 first. Terminology follows the survey (游戏 / 回合 / 团队 / 教师; 资产负债率 for debt-to-equity as the existing lock refusal uses it); the terminology test passes on all of it.

**Needs a browser.** No visual claim is made about Chinese glyphs (the walkthrough's sandbox had no CJK font); the render tests assert DOM text by key.

**Observations for other builders.**
- W-CE-03 (R&D): the Summary's and the R&D page's guidance no longer tells a team to upgrade a feature; if the “Invest next level” control is removed, `rd.invest_next_level` becomes unused and can go.
- W-CE-25: `SummaryPage.js` still hard-codes `requiredForLock`; the server's `optional` flag now exists on every non-required category (`financing`, the four supply-chain sections), which the blocker derivation can read.
- `_generate_fallback_briefing` in `narratives.py` is unreferenced (dead, English); left untouched.
- Two `useCallback` dependency arrays on the finance page gained `t` (the callbacks now call `t`), keeping the lint count at the baseline (57).
