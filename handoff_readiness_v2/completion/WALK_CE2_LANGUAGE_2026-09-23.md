# WALK-CE2 language repairs — W-CE2-04, 05, 06, 07, 08, 09, and the sweep

**Branch:** `walk-ce2-language`, cut from `crv2-release-integration` at `48a8a92`
(contains the second walkthrough merge `6a25436` and
`handoff_readiness_v2/completion/WALKTHROUGH_CE_2_2026-09-22.md`; both verified
before any edit).
**Date:** 2026-09-23. **Builder:** repair builder, language and figure defects of
the second Consumer Electronics walkthrough.
**Rules observed:** R48 — bugs first, no new rules; R43 — the team's language
governs what a student is told; R44 — the operator audit trail stays English.

> Sections: (a) method · (b) per id: source, repair, red-then-green ·
> (c) every new or changed zh-CN sentence, least-trusted first ·
> (d) the remaining-literals list, including what needs authored scenario
> content · (e) tests and commands · (f) proposed register status text ·
> (g) the owner question from W-CE2-05 · (h) distrust list and notes for the
> integrator.

**No gate is claimed closed.** Everything below is a repair with a test beside
it; the walkthrough that would prove the screens read correctly in a browser
has not been re-run.

---

## (a) Method

Every defect was reproduced before it was repaired — a Jest render or source
scan with `t` stubbed to print its key, or a Django request with the relevant
language set — and the red run is quoted per id. Backend tests ran only through
`cd backend && TEST_POSTGRES_READY_SECONDS=1500 flock -w 3600
/tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>` (disposable
Postgres; never the production database at 192.168.50.38, never
`/etc/globalstrat-plus.env`). Frontend: focused Jest per id, then the full Jest
run, `python3 backend/scripts/check-participant-strings` with its selftest, and
the production build with the ESLint ratchet.

One commit per defect, oldest first:

| commit | id | what |
|---|---|---|
| `e3e5fc5` | W-CE2-05 | the student who asked is answered in their own language |
| `d4a3e21` | W-CE2-08 | the AI Coach follows the console's language |
| `61c6546` | W-CE2-06 | the market's name in the reader's language |
| `d2a5fa9` | W-CE2-07 | the Strategic Scorecard in the reader's language |
| `370568f` | W-CE2-04 | the Operator Log reads a sentence, not a Python string |
| `982ffad` | W-CE2-09 | one total, formatted |

Guards extended so a fixed screen cannot regress:

| guard | what it holds |
|---|---|
| `backend/core/tests/test_walk_ce2_language.py` (new, 10 classes, 41 tests) | every backend behaviour below, by request where a route exists |
| `backend/core/tests/test_manifest_determinism.py` | `RESOLUTION_SERVICES` gains `coherence_feedback.py`: the engine now calls it, and its own guard is what caught the omission |
| `frontend/.../src/pages/walkCe2MoneyFormat.test.js` (new) | no page, component, design-system or instructor source decides a money unit from an unsigned comparison; the ten repaired files still carry the guarded shape |
| `frontend/.../src/components/BudgetBar.test.js` | the negative figure, the one authoritative total, the older-payload fallback, and both budget sentences in both catalogues |
| `frontend/.../src/components/instructor/OperatorEventsPanel.test.js` | an engine fault reads as the server's sentence, with the technical cause inside it and no `engine_failure` token |

---

## (b) Per id

### W-CE2-05 — a team's language was its first enrolment's (P1) — fixed, `e3e5fc5`

**Source.** `participant_messages.language_for_team` answers "the language of
the team's first active enrolment that states one". R43 ruled that the team's
language governs what the analyst route says to a student; it did not settle
*whose* language the team's is when members differ. The consequence a player
feels: a Chinese-reading student whose team-mate enrolled first is answered in
English however often they choose 中文, and the setting is unreachable for every
member but the first. `language_for_team` has exactly one caller —
`ResearchQueryView` in `core/rag/views.py` — so the blast radius is one route.

**Repair — the least change that removes what the player feels.**
`language_for_participant(team, request)` reads the **asking student's own
active enrolment on this team** and falls back to `language_for_team` wherever
the request identifies no student, the student has no enrolment on the team, or
they state no supported language. When a team's members agree it is the same
answer as before. The request's *header* still does not govern — R43 rejected
that explicitly — what is read is the enrolment that the in-game switch and the
sign-in record through `PUT /api/user/preferences/` (W-CE-11). The safe
fallback is kept: the lookup is inside its own savepoint and any failure or
unsupported value falls through to the team rule, which itself falls through to
the request.

**Which sentences moved to the individual rule.** Every sentence of the analyst
route (`ResearchQueryView.post`), all of which answer the one student who
pressed Ask:

| sentence | key |
|---|---|
| the analyst is not part of this game | `analyst_not_enabled` |
| a question is required | `analyst_question_required` |
| the round's query limit is reached | `analyst_query_limit_reached` |
| the round is not open | `round_not_open` |
| the purchase exceeds available cash | `research_purchase_exceeds_cash` (and the report name in it) |
| nothing relevant was found, nothing charged | `analyst_no_relevant_research` |
| the research system is unavailable | `analyst_unavailable` |
| the game or team was not found | `analyst_game_or_team_not_found` (already the request's language) |
| the synthesised brief itself | `synthesize_research_brief(..., language=…)` |

plus one thing that is not a sentence: whether that student's own typed
question is translated for the English-only embedding model
(`translate_query_if_needed`). It followed a team-mate's language, which would
silently degrade retrieval for the asker.

**Which sentences kept the team rule.** Everything written once for the whole
team, all of it still `get_team_language`:

| sentence | where |
|---|---|
| the round briefing: executive summary, recommendations, risk alerts | `engine/narratives.py` `_build_briefing_fields` |
| the compliance notice and the supply-chain event narrative | `engine/narratives.py` `_compliance_fallback`, `_sc_event_fallback` |
| the memo evaluation | `rag/communication_eval.py` |
| the persona messages in a team thread (three call sites) | `services/persona_engine.py` |
| the LLM language instruction for coherence prose | `engine/coherence.py` |
| the ticker's reader language | `views/cc31h_views.py` (already header-then-team) |

A test class, `TeamWideProseKeepsTheTeamRuleTests`, pins that split so a later
builder cannot move it silently.

**Red → green.** `core.tests.test_walk_ce2_language` on `48a8a92`:
`Ran 10 tests … FAILED (failures=2, errors=3)` —
`AssertionError: False is not true : {'error': 'The research analyst is not part
of this game, so your question was not asked and nothing was charged.'}` for the
second member, and `ImportError: cannot import name 'language_for_participant'`.
Green with `test_walk_ce_language`, `test_player_language_guard`,
`test_crv2_12_language`, `test_zh_terminology`,
`test_operator_refusal_language`, `test_durable_narratives`,
`test_student_refusal_language`, `test_numeric_refusal_language`:
`Ran 200 tests … OK`. The R43 guard
`test_the_teams_language_governs_over_the_header` is inside that run and still
passes.

**The owner question this raises is in (g).**

### W-CE2-08 — the AI Coach alerts were always English (P1) — fixed, `d4a3e21`

**Source.** Two causes, both found by reading the server, and the walkthrough
named only the second.

1. `GameCreateView` (`views/scenario_views.py`) records `Game.created_by` as
   **the first superuser** whenever the caller is a `JWTUser` — which is every
   instructor signing in to the console, because `Game.created_by` points at
   Django's auth user and the platform authenticates against its own
   `core.User`. So `get_instructor_language(game)`, which read
   `game.created_by_id`, was reading a superuser, not the instructor.
2. An instructor created from the console has no `Enrollment` at all, so
   `PUT /api/user/preferences/` — the route the console header's language
   switch calls — found nothing to write to and silently stored nothing. The
   switch changed the browser and nothing on the server.

**Where the instructor's language is known elsewhere.** The operator catalogue
resolves it per request with `operator_messages.language_for_request`, which is
`Accept-Language` then the caller's own enrolment. That works for a *response*.
It cannot work here: the coach alerts are **stored prose generated in Phase 2
with no request in scope** — `generate_post_round_alerts` writes `title` and
`detail` into `instructor_alert`, and `title` is a hashed field of the
manifest's `instructor_alert` section — so they cannot be re-rendered for
whoever later opens the panel without changing what is hashed. **So they follow
the stored preference of the instructor who owns the game, resolved when the
alert is written, and this report says so.**

**Repair.**

- `core/models/preferences.py` — `UserLanguagePreference` (migration
  `0090_user_language_preference`): one row per user id, holding the language
  they last chose. A preference store only: no engine reads it, it is in no
  manifest section, and it alters no existing table. `user_id` is a plain
  integer rather than a foreign key because the two user tables this platform
  authenticates against do not share a key space.
- `LanguagePreferenceView.put` writes that row for every caller and still
  writes the enrolment when there is one, so the two stores cannot disagree;
  `get` reads the enrolment first, then the row.
- `get_instructor_language(game)` asks the **course instructor**, reached
  through the game's section (`Section → Course.instructor_id`), and then
  `created_by` exactly as before; for each candidate it reads the preference
  row then the enrolment. A language the catalogue has no entry for now reads
  as English instead of being returned verbatim.

**Red → green.** `Ran 20 tests … FAILED (failures=4, errors=3)` —
`ModuleNotFoundError: No module named 'core.models.preferences'`,
`AssertionError: 'en' != 'zh-CN'`, and the alert itself
`Team 0 has not invested in R&D for 2 consecutive rounds`. Green with
`test_walk_ce_language`, `test_player_language_guard`, `test_crv2_12_language`,
`test_zh_terminology`, `test_operator_refusal_language`,
`test_durable_narratives`, `test_manifest_determinism`: `Ran 217 tests … OK`;
and `test_game_deletion_audit`, `test_refusal_audit_integrity`:
`Ran 38 tests … OK` (the admin/audit-model guards, checked because a new model
was added).

### W-CE2-06 — English market names on Chinese screens (P2) — fixed, `61c6546`

**Does the scenario have the Chinese names?** **Yes.** The CE scenario authors
`name_zh` for every market — `Western Europe` / `西欧` at
`backend/scenarios/consumer_electronics_2026.yaml:1061`, and the same for North
America, East Asia, South America and West Africa. A test asserts no market in
the scenario lacks `name_zh`. **Nothing in this defect needs authored content**;
these were four reads that skipped `get_localized_field`.

**Source and repair.**

| where | was | now |
|---|---|---|
| `ProductContextView` (`views/decisions.py`), the Products table's Active Markets | `.values('market_id', 'market__name', 'is_active')` — the stored English name | the same rows built through `get_localized_field`, as `MarketingContextView` already did |
| `price_band.adjustment_notice` | the audit payload's English `market_name` interpolated into a Chinese sentence — *Western Europe 中的 IronClad Field：未输入价格…* | `market_name_for_reader` looks the market up by the `market_id` the payload has always carried; a payload without one, or a market since removed, keeps the stored name rather than losing the fact. **The audit row itself is untouched (R44).** |
| the price-adjustment table's own `market` column (`results_api.py`) | the same stored English name | the same helper |
| `results_api.py` ×2, an event with no target market | the literal `'Global'`, in both languages | `participant_messages.market_label(market, language)`, reusing the existing `research_global` entry (`Global` / `全球`) |
| Products and R&D, the platform column | `… Base Platform`, the English name `game_creation` generates and stores for a starting platform | `platform_display_name` renders that generated default in the reader's language and leaves a name the team chose alone. Nothing stored changes, so no game needs migrating; the suffix now lives in `participant_messages.BASE_PLATFORM_SUFFIX_EN` and `game_creation` imports it, so writer and reader cannot drift. |

**Red → green.** `Ran 7 tests … FAILED (failures=1, errors=4)` —
`AssertionError: '西欧' not found in 'Western Europe 中的 IronClad Field：未输入价
格，回合截止时已按本回合允许的最低价 $100 定价（本回合允许区间为 $90 至 $110）。'`
Green: `Ran 27 tests … OK`; with `test_walk_ce_language`,
`test_player_language_guard`, `test_crv2_12_language`, `test_zh_terminology`,
`test_operator_refusal_language`, `test_durable_narratives`,
`test_price_band`, `test_reference_price`: `Ran 216 … OK`; and
`test_game_creation_paths`, `test_platform_lifecycle`, `test_product_rebase`:
`Ran 128 … OK`.

**Checked, because a localised name could have broken a lookup:** nothing in the
frontend keys logic on the English market name. `components/MarketImage.js`
holds a map with English aliases (`'Western Europe': …`), but it is imported by
no file — dead code; noted in (d).

### W-CE2-07 — English Strategic Scorecard sentences (P2) — fixed, `d2a5fa9`

**Source.** Twelve sentences written as English f-strings in
`core/engine/coherence.py` with no catalogue entry: three for leverage, six for
budget discipline, three for the governance/tax check.

**The constraint that shapes the repair.** `RoundResultCoherence.breakdown` is a
hashed field of the `coherence` manifest section — a scoring artefact inside the
competitive hash. What the engine stores therefore **cannot** depend on who
reads it, and adding a code to the stored JSON would change the hashed value and
invalidate replay evidence for every round.

**Repair.** The stored sentence stays English, byte-identical to what shipped,
and the reader re-derives the same key from the same stored numbers — through
the same function, so there is one rule, not two.
`core/services/coherence_feedback.py` holds the key selection: leverage by
`debt_to_equity`, budget by `over_pct` and `operating_budget`, governance/tax by
its score (that branch stores no other number). The engine picks the key with
those functions and stores their English rendering; `results_api` calls the same
functions on the numbers the engine stored beside the sentence and renders a
**copy** for the response. An entry the module cannot place — an older row, a
criterion with no rule — keeps the sentence it already has, so a screen never
loses one. Tests assert both the byte-identical English and that a Chinese read
leaves the stored row alone.

`coherence_feedback.py` is registered in `RESOLUTION_SERVICES` in
`test_manifest_determinism.py`: the engine now calls it, and that guard is what
caught the omission.

**Red → green.** `Ran 8 tests … FAILED (failures=1, errors=6)` —
`ImportError: cannot import name 'coherence_feedback' from 'core.services'` and
`AssertionError: False is not true : Conservative leverage. Strong financial
position.` Green: `Ran 35 tests … OK`; with `test_manifest_determinism`,
`test_coherence_price_ranges`, `test_walk_ce_language`,
`test_player_language_guard`, `test_crv2_12_language`, `test_zh_terminology`,
`test_operator_refusal_language`, `test_durable_narratives`:
`Ran 248 tests … OK`.

### W-CE2-04 — a raw `SnapshotError` in the Operator Log (P2) — fixed, `370568f`

**Source.** `OperatorAction.record_fault` stored
`f'Post-round processing failed: {e}'` — the raw exception — and
`OperatorEventsPanel` printed `conflict.detail` verbatim, so an instructor read
storage names, a Python argument and an instruction addressed to a developer,
with `engine_failure` beside it.

**Repair.** `record_fault(cause, *, message_key)` stores the same catalogue
sentence the failing route already returns — `processing_failed`,
`advance_failed`, `legacy_advance_failed`, all three already bilingual and
already carrying `{detail}`, whose Chinese template labels the quoted cause as
English (*系统给出的原因（英文）：*). The technical cause is kept beside it as
`cause`. The stored sentence is English (R44: one record, one language, whatever
the operator works in) and `operator_messages.localise_conflict` renders it in
the reader's language when the Operator Log is read. The code on the row becomes
the route's own code rather than the generic `engine_failure`, so the log and
the response the operator saw now agree. A conflict with no `message_key` —
every lifecycle refusal, whose values are not stored — is served exactly as
stored.

**So the row is "a labelled bilingual sentence with the detail kept for the
operator":** the sentence is the label, in the operator's language; the cause is
inside it, marked as English, and also carried as its own field for a dispute.

**Red → green.** `Ran 6 tests … FAILED (errors=5)` —
`TypeError: OperatorAction.record_fault() got an unexpected keyword argument
'message_key'`, `ImportError: cannot import name 'localise_conflict'`. Green:
`Ran 41 tests … OK`; with `test_operator_refusal_language`,
`test_refusal_audit`, `test_refusal_audit_integrity`, `test_walk_ce_language`,
`test_crv2_12_language`, `test_zh_terminology`, `test_operator_concurrency`:
`Ran 153 … OK`; `test_operator_events_view`, `test_operator_route_ownership`,
`test_auth_rounds`: `Ran 138 … OK`. Jest `OperatorEventsPanel`:
`Tests: 7 passed`.

### W-CE2-09, with W-CE-18b's remainder — two totals, one unformatted (P2) — fixed, `982ffad`

**The unformatted figure.** Eight copies of the same short money formatter
tested `n >= 1e6` and `n >= 1e3`, so every **negative** amount fell past both
branches into `toFixed(0)`: `Unallocated: $-12553689` beside figures written
`$28.5M`. Magnitude now decides the unit and the sign is carried — the shape
`BudgetAlert` and `DSBudgetBar` already had. Repaired in `BudgetBar`,
`GameStatusBar` (a team at negative cash, W-CE-23), `RDPage`, `MarketingPage`,
`StrategyPage`, `MarketStrategyPage`, `CorporateStrategyPage`,
`CommunicationsPage`. The new source-scan guard fails the moment a ninth copy is
written the old way.

**Two round totals.** The banner said *total spending $28.5M exceeds available
budget $5.0M* while the blocker below said *Committed spend of $38,000,000.00
exceeds available cash*. Both already come from the one assessment the
committed-spend work made authoritative (`rd_costs.budget_assessment`,
`WALK_CE_STUDENT_NUMBERS_2026-09-22.md` §3): the banner's figure is the sum of
its three declared lines, the blocker's is its `committed_total`. The screen
presented a subset and the total as if both answered "what does this round
cost".

- The panel now states the authoritative total — *Committed this round: $38.0M
  of $25.4M cash — $-12.6M not yet committed* — so the figure the blocker quotes
  is on the bar, and "unallocated" can no longer read as headroom while the same
  panel refuses the lock. An older payload without `committed_total` keeps the
  plain line.
- The banner stops calling its subset the round's total spending and names its
  own concept: *R&D, marketing and strategy spending totals $28.5M, which is
  $23.5M over the operating budget of $5.0M.* **No figure, threshold or charge
  changes** — only which words describe the comparison already being made.
- `budget_status` (Finance, dashboard) gains `total_available`, the cash key the
  summary endpoint already published, so the shared bar can say that sentence
  everywhere.

**Red → green.** Jest `BudgetBar`: `Tests: 5 failed, 8 passed, 13 total`
(`$-12553689` present; `budget.committed_of_cash` undefined). Green:
`Tests: 13 passed`; with `walkCe2MoneyFormat`, `SummaryPage`, `GameDashboard`,
`FinancePage`: `Tests: 25 passed, 5 suites`. Backend
`test_committed_spend_one_calculator`, `test_rd_costs`,
`test_compliance_investment_charge`, `test_walk_ce2_language`:
`Ran 82 … OK`.

---

## (c) Every new or changed zh-CN sentence — for a native reviewer, least-trusted first

**Tier 1 — prose written from scratch for this pass, no precedent in the
catalogues. Review these first.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 1 | Round Results › Strategic Scorecard | `coherence_governance_tax_conflict` | Anti-corruption commitment conflicts with aggressive tax optimization. Stakeholders view this as hypocritical — coherence heavily penalized. | 反腐败承诺与激进的税务筹划相互冲突。利益相关者视之为言行不一，战略协同性因此被大幅扣分。 |
| 2 | Round Results › Strategic Scorecard | `coherence_governance_tax_aggressive` | Aggressive tax optimization without governance commitments — raises moderate stakeholder concerns. | 激进的税务筹划缺乏相应的治理承诺——引发利益相关者的中度关切。 |
| 3 | Round Results › Strategic Scorecard | `coherence_budget_significantly_over` | Significantly over budget ({over}). Reckless spending erodes stakeholder confidence. | 显著超出预算（{over}）。无节制的支出会削弱利益相关者的信心。 |
| 4 | Round Results › Strategic Scorecard | `coherence_leverage_moderate` | Moderate leverage. Manageable but watch debt growth. | 杠杆水平适中。尚在可控范围，但需关注债务增长。 |
| 5 | Decision Summary › Budget Summary | `budget.committed_of_cash` | Committed this round: {{committed}} of {{cash}} cash — {{unallocated}} not yet committed | 本回合已承诺支出：{{committed}}，现金共 {{cash}}；尚未承诺 {{unallocated}} |

**Tier 2 — a sentence whose English was reworded in this pass, so the Chinese is
new prose for an existing screen.**

| # | where | key | en (new) | zh-CN (new) |
|---|---|---|---|---|
| 6 | the over-budget banner, every decision page | `budget.over_budget` | R&D, marketing and strategy spending totals {{spent}}, which is {{overage}} over the operating budget of {{available}} | 研发、营销与战略支出合计 {{spent}}，比经营预算 {{available}} 高出 {{overage}} |

The English it replaces was *Over budget by {{overage}} — total spending
{{spent}} exceeds available budget {{available}}*; the Chinese it replaces was
*超出预算 {{overage}} — 总支出 {{spent}} 超过可用预算 {{available}}*. The change is
the point of the repair: **总支出 / "total spending" is what made it read as a
second total of the round's cost.**

**Tier 3 — short sentences with close precedent in the catalogue; lower risk.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 7 | Scorecard | `coherence_leverage_conservative` | Conservative leverage. Strong financial position. | 杠杆水平保守。财务状况稳健。 |
| 8 | Scorecard | `coherence_leverage_high` | High leverage. Risk of financial distress. | 杠杆水平过高。存在财务困境风险。 |
| 9 | Scorecard | `coherence_budget_within` | Spending within operating budget. Good fiscal discipline. | 支出未超出经营预算。财务纪律良好。 |
| 10 | Scorecard | `coherence_budget_slightly_over` | Slightly over budget ({over}). Minor overspend. | 略微超出预算（{over}）。属小幅超支。 |
| 11 | Scorecard | `coherence_budget_over` | Over budget by {over}. Spending discipline is weak. | 超出预算 {over}。支出纪律薄弱。 |
| 12 | Scorecard | `coherence_budget_massively_over` | Massively over budget ({over}). No spending discipline. | 大幅超出预算（{over}）。毫无支出纪律。 |
| 13 | Scorecard | `coherence_budget_no_baseline` | No operating budget baseline (first round). | 尚无经营预算基准（首个回合）。 |
| 14 | Scorecard | `coherence_governance_tax_clear` | No governance-tax conflict detected. | 未发现治理与税务之间的冲突。 |

**Tier 4 — a name, not a sentence.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 15 | Products, R&D — the starting platform | `platform_base_name` | {team} Base Platform | {team}基础平台 |

`{team}` is the team's own name and is never translated. A platform the team
renamed keeps its own name in both languages.

**No new Chinese was written for W-CE2-04, W-CE2-05 or W-CE2-08.** W-CE2-04
reuses `processing_failed` / `advance_failed` / `legacy_advance_failed`, all
already reviewed; W-CE2-06's market names are the scenario's authored `name_zh`
and the existing `research_global`; W-CE2-05 and W-CE2-08 change only which
language is resolved.

---

## (d) Remaining English a zh-CN user can still see — precisely

The sweep the previous builder used (`src/englishLiteralScan.js`: JSX text, bare
lines, spoken props, spoken fallbacks, computed keys, missing keys) was re-run
over every page, component, instructor panel and design-system source — the
screens the second walkthrough visited and their neighbours. **220 raw spoken
findings, 25 computed keys, 0 missing keys.** After removing CSS, antd and font
tokens (`1px solid #f0f0f0`, `0 auto`, `rgba(...)`, `calc(...)`,
`Inter, sans-serif` and the like), what is left that a person reads is below.
Nothing on this list is new; items 1, 2, 3, 5, 6, 7 and 9 carry over from
`WALK_CE_LANGUAGE_2026-09-22.md` §(d).

| # | screen | source | what | why not here / what it needs |
|---|---|---|---|---|
| 1 | Industry News headlines | `MarketConditionByRound.market_outlook_narrative`, scenario YAML lines 5823, 5921 | scenario-authored, English only; **no `_zh` field on the model** | **Needs authored content and a model change**: a `market_outlook_narrative_zh` column + migration, then a Chinese line per round in the CE scenario (the YAML has ~10 per market-round block). Not a code fix. |
| 2 | Financial Reports › Trade Finance & FX | `pages/FinancialReportsPage.js` | ≈20 literals: *Trade Finance & FX*, *Open FX hedge positions*, *Payment & export-credit posture*, *Buyer payment instruments*, *Export-credit (Sinosure) coverage*, the table columns *Pair / Notional / Locked rate / Mark-to-market / Realized P&L / Status*, *None set.*, *No export-credit insurance set.*, the hedge explanation sentence, the empty-state sentence, and the rating words *AAA / BBB+ / BBB / CCC*, *VERY LOW / LOW / MODERATE / ELEVATED / HIGH / VERY HIGH / DISTRESS* | a whole section outside the six named defects; the rating words are also colour keys, so they need a code-and-label split like W-CE-16(b)'s `_fit_code`. Code only — no authored content needed. |
| 3 | Trade Finance instrument names; Sourcing component and supplier names | scenario supply-chain data (`display_name`, component/supplier `name`) | *Open Account*, *Letter of Credit*, *Cash in Advance*, *Sinosure Export Credit Insurance*, *Camera Module*, *Final Assembly*, *Power Management* | **Needs authored content**: the CE scenario authors no Chinese counterpart for these fields. A `_zh` value per row in the YAML (the model fields exist for some of these; confirm per table before authoring). |
| 4 | Communications › audience tags | `cc32a_views.py` — Django choice labels served as `audience_display`; and `'N/A'` for a team with no active market | *Board of Directors*, *Investor Community*, *N/A* | code only: a bilingual label table in the participant catalogue. Also `cc32a_views.py:90` builds `{active_markets}` from `market__name` (English) — the same defect as W-CE2-06 but inside prompt text sent to the model, so it belongs with the communications work rather than here. |
| 5 | Communications › criterion names | scenario YAML `evaluation_criteria[].criterion`, title-cased in `CommunicationsPage.js` | *Framework Grounding*, *Risk Acknowledgment*, *Strategic Consistency* … | **Needs authored content or a label table**: the tokens are scenario-authored. |
| 6 | Logistics › *Incoterms* | `pages/LogisticsPage.js` | a proper term (国际贸易术语) | judgment call; left, as before |
| 7 | Onboarding image `alt` texts | `components/OnboardingModal.js` | *Your Global Challenge*, *What You Must Navigate*, *How to Build Your Global Strategy*, *How You're Scored*, *Your Starting Position*, and a `TBD` | accessibility text on images; not visible on screen |
| 8 | Instructor › Grading & Export | `pages/InstructorDashboard.js` | the CSV column hint *student_id, display_name, email* | storage names in a hint an instructor reads; small, and the accounts panel is another builder's file this week |
| 9 | Keys reached through label maps (`t(variable)`) | 25 computed keys across CompetitiveIntel, CorporateStrategy, Inventory, Login, Logistics, MarketStrategy, Products, Sourcing, StrategyTools, TradeFinance, DecisionSaveAlert, StatusBadge, InstructorDashboard, incomeStatementRows | invisible to the static scan | the pattern inventoried in `handoff_readiness_v2/evidence/unresolved-locale-keys/keys-hidden-behind-label-maps.txt`, with the owner; not new. `check-participant-strings` reports the same 30 unresolved keys and passes. |
| 10 | Investor popover | `components/InvestorProfilePopover.jsx` | *▲ BUY*, *▼ SELL*, *— HOLD* | three verdict tokens; one literal key per value would fix it, same shape as `distanceLabel` |
| 11 | Round labels and currency codes | `R${round_number}` across Results, Leaderboard, FinancialReports, incomeStatementRows; `USD` on Industry News; `ESG`, `CSV` on the dashboard | short codes, arguably not translatable | left; listed so a reviewer can rule |
| 12 | Market name aliases | `components/MarketImage.js` | *North America*, *East Asia*, *Western Europe*, *South America*, *West Africa* as `alt` text and map keys | **dead code**: no file imports `MarketImage`. Worth deleting, but deletion is not a language repair and I left it. |
| 13 | Results CSV export | `pages/ResultsPage.js:636–637` | `${m.market_name} Revenue` / `${m.market_name} Share` — English words appended to a localised name | a CSV export, not a screen; one literal key each would fix it |

**Nothing on the six repaired ids remains.** The market names, the scorecard
sentences, the coach alerts, the analyst sentences, the operator fault row and
the Summary figures are all clean in the sweep.

---

## (e) Tests and commands

All backend commands ran as
`cd backend && TEST_POSTGRES_READY_SECONDS=1500 flock -w 3600
/tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`.

| # | command | result |
|---|---|---|
| 1 | `core.tests.test_walk_ce2_language` (W-CE2-05 red, at `48a8a92`) | `Ran 10 … FAILED (failures=2, errors=3)` |
| 2 | …+ `test_walk_ce_language test_player_language_guard test_crv2_12_language test_zh_terminology test_operator_refusal_language test_durable_narratives test_student_refusal_language test_numeric_refusal_language` (green) | `Ran 200 … OK` |
| 3 | `core.tests.test_walk_ce2_language` (W-CE2-08 red) | `Ran 20 … FAILED (failures=4, errors=3)` |
| 4 | …+ the guards + `test_manifest_determinism` (green) | `Ran 217 … OK` |
| 5 | `test_game_deletion_audit test_refusal_audit_integrity` | `Ran 38 … OK` |
| 6 | `…MarketNameOnChineseScreensTests` (W-CE2-06 red) | `Ran 7 … FAILED (failures=1, errors=4)` |
| 7 | `test_walk_ce2_language` (green) | `Ran 27 … OK` |
| 8 | + `test_price_band test_reference_price` and the guards | `Ran 216 … OK` |
| 9 | `test_game_creation_paths test_platform_lifecycle test_product_rebase test_crv2_12_language` | `Ran 128 … OK` |
| 10 | `…ScorecardSentenceTests` (W-CE2-07 red) | `Ran 8 … FAILED (failures=1, errors=6)` |
| 11 | `test_manifest_determinism test_coherence_price_ranges` + the guards (green) | `Ran 248 … OK` |
| 12 | `…OperatorLogFaultSentenceTests` (W-CE2-04 red) | `Ran 6 … FAILED (errors=5)` |
| 13 | `test_operator_refusal_language test_refusal_audit test_refusal_audit_integrity` + the guards | `Ran 153 … OK` |
| 14 | `test_operator_events_view test_operator_route_ownership test_auth_rounds` | `Ran 138 … OK` |
| 15 | `test_committed_spend_one_calculator test_rd_costs test_compliance_investment_charge test_walk_ce2_language` | `Ran 82 … OK` |
| 16 | **the single full run:** `scripts/test-postgres core --parallel 8` | `Ran 1625 tests in 117.181s … OK` |

Frontend:

| command | result |
|---|---|
| Jest `OperatorEventsPanel` | `Tests: 7 passed` |
| Jest `BudgetBar` (red) | `Tests: 5 failed, 8 passed, 13 total` |
| Jest `walkCe2MoneyFormat BudgetBar SummaryPage GameDashboard FinancePage` | `Tests: 25 passed, 5 suites` |
| **full Jest** `CI=true npx react-scripts test --watchAll=false` | `Test Suites: 49 passed, 49 total · Tests: 486 passed, 486 total` |
| `python3 backend/scripts/check-participant-strings` | `participant-string-hygiene: PASS 5733 unit(s) examined, 0 reviewed suppression(s)`; note: 30 computed `t()` keys unresolved (item 9 in (d)) |
| `python3 backend/scripts/check-participant-strings-selftest` | `selftest: 34 ok, 0 failed` |
| `CI=false GENERATE_SOURCEMAP=false npx react-scripts build` | exit 0 |
| `node eslint-warning-count.js <build log>` | `eslint warnings: 54 (baseline 55)` |

The full backend suite ran **once**, from the frozen commit `982ffad`, after
every runtime change and before the record and the inventory. No runtime code
changed after it; the two commits that follow it are this document with the
lint baseline, and the regenerated string inventory alone.

**On the ESLint baseline.** The same build on the current
`crv2-release-integration` head also reports **54**, so this pass adds no
warning and the drop from 55 arrived with work merged before it. The ratchet
asks for the baseline to be lowered when the count falls, so
`.eslint-warning-baseline` is set to 54 in the final commit.

---

## (f) Proposed register status text

Offered as wording only. **I did not edit `V2_FINDINGS_REGISTER.md`,
`LAUNCH_CHECKLIST_V2.md`, any `OWNER_RULINGS` file or
`INTEGRATOR_DECISIONS_UNDER_R48.md`.**

| id | proposed status | proposed note |
|---|---|---|
| W-CE2-04 | **REPAIRED, needs a browser** | `370568f`. A failed action's Operator Log row now carries the catalogue sentence the route returns, rendered in the operator's language, with the technical cause inside it and kept as its own field; the stored row stays English (R44). Needs one console reading to confirm the panel. |
| W-CE2-05 | **REPAIRED, one question for the owner** | `e3e5fc5`. A sentence addressed to one student follows that student's own stated language; prose written once for the whole team keeps the team rule. R43's gap — whose language a *team-wide document* uses when members differ — is open; see (g). |
| W-CE2-06 | **REPAIRED** | `61c6546`. Four reads that skipped `get_localized_field`; the CE scenario already authors `name_zh` for every market, so no content was needed. The generated `… Base Platform` name is rendered, not re-stored. |
| W-CE2-07 | **REPAIRED** | `d2a5fa9`. The stored breakdown stays English and byte-identical — it is inside the competitive hash — and the reader re-derives the sentence from the stored numbers through the same function the engine used. |
| W-CE2-08 | **REPAIRED, needs a browser** | `d4a3e21`. Two causes: a console-created game is recorded against the first superuser, and a console-created instructor has no enrolment to store a language in. New `UserLanguagePreference` (migration 0090) and an owner chain through the game's section. Alerts are Phase-2 prose, so the language is fixed when the alert is written. |
| W-CE2-09 | **REPAIRED** | `982ffad`. Eight copies of a money formatter ignored the sign; the panel now states the one authoritative committed total against cash, and the banner names its own comparison instead of calling a subset the round's total spending. |
| W-CE-16 / W-CE-17 residue | **partially cleared** | The market names (W-CE2-06), the scorecard (W-CE2-07) and the coach alerts (W-CE2-08) are gone from the zh leak list. The scenario-authored news headlines and supply-chain names remain and need authored content — (d) items 1, 3, 5. |

---

## (g) The owner question W-CE2-05 raises, in plain language

**What a team-wide document should say when the team's members read different
languages.**

Right now, when the platform speaks to one student — refusing their click,
answering their question — it uses that student's own language. That is what
this repair changed, and it is the part a player feels.

But some things are written **once for the whole team** and then read by
everyone on it: the round briefing, the compliance notice, the coach's memo
evaluation, the messages the AI advisors post into the team's thread. Those are
still written in "the team's language", and the team's language is whichever
member enrolled first. If one member reads English and another reads Chinese,
one of them will read a briefing in a language they did not choose.

The three ways out, with no recommendation:

1. **Leave it.** One document, one language, chosen by whoever set up the team
   first. Simple, and wrong for somebody on every mixed team.
2. **Let the team choose.** Add one setting — a team language the members or the
   instructor set — so the choice is deliberate rather than an accident of who
   signed in first. Costs a setting and a screen.
3. **Write it twice.** Generate each team-wide document in both languages and
   show each member theirs. Costs twice the model work for every briefing, and
   the two versions will not say exactly the same thing.

There is also a smaller version of the same question inside the analyst route:
the answer the analyst gives is addressed to the student who asked, and this
repair renders it in that student's language — but it is **stored** and appears
in the team's question history, so a team-mate may later read an answer in a
language they did not choose. If the owner's answer to the main question is
(1) or (2), that stored answer should probably follow the same rule, and this
builder did not assume it.

**Nothing has been decided here.** The code does what the finding asked for and
no more.

---

## (h) Distrust list, and notes for the integrator

Only items that need the owner, the production host, a browser or a native
speaker.

| # | what | why it is here |
|---|---|---|
| 1 | **Every Chinese sentence in (c)** | Needs a native speaker. Fifteen strings, ordered least-trusted first. #1–#5 are prose written from scratch; #6 replaces a sentence that was already reviewed, so its Chinese is new for an existing screen. |
| 2 | **The AI Coach panel read in Chinese** | Needs a browser and a processed round on a zh-CN console. The walkthrough could not produce a Chinese reading of that panel at all; the tests prove the alert rows are written in Chinese, not that the panel renders them well. |
| 3 | **The Operator Log's fault row** | Needs a browser: one processing failure on a zh-CN console, to confirm the sentence reads as an operator sentence and the cause is legible inside it. |
| 4 | **The Summary's budget panel at a negative balance** | Needs a browser: the new one-total sentence with a negative figure, at phone width as well, where three money figures now sit on one line. |
| 5 | **The owner question in (g)** | Needs the owner. |
| 6 | **The remaining-literals items that need authored content** | (d) items 1, 3 and 5 need the scenario author: Chinese news headlines (and a model field for them), Chinese supply-chain names, and Chinese criterion names. |
| 7 | **Whether `MarketImage.js` should be deleted** | (d) item 12: dead code carrying English market names. A deletion, not a language repair. |

**For the integrator.**

- **Migration number.** This branch adds `backend/core/migrations/0090_user_language_preference.py`, depending on `0089_r47_compliance_expense_line`. The concurrent builder's merged work adds no 0090 as of `c40d5be`, but if another branch does, the two are conflicting leaf nodes and the merge needs a `makemigrations --merge`. The new table is a preference store: no engine reads it, it is in no manifest section, and it alters no existing table.
- **Determinism.** No stored engine output changes. W-CE2-07 deliberately keeps `RoundResultCoherence.breakdown` byte-identical; W-CE2-08 changes which user's stored language an alert is written in, which was already a per-game input to that Phase-2 text, not a new dependency.
- **`coherence_feedback.py`** is registered in `RESOLUTION_SERVICES` in `core/tests/test_manifest_determinism.py`. That is the only edit to a guard another handoff owns, and the guard itself demanded it.
- **`crv2-release-integration` moved during this work** (now `c40d5be`, the round-blockers merge). This branch is still cut from `48a8a92` and was not rebased. No push, no merge was performed.
- **Files another builder is also editing** were kept to minimal, local edits: `core/engine/coherence.py` (an import and twelve literal assignments replaced by calls), `core/views/decisions.py` (three payload lines), `core/views/results_api.py` (four payload lines and two imports), `core/views/round_control.py` (two call sites), `core/services/game_creation.py` (one line and an import).
