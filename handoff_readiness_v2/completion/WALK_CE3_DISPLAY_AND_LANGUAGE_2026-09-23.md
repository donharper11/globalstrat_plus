# WALK-CE3 display and language repairs — W-CE3-05..20 (less 01–04)

**Branch:** `walk-ce3-display-and-language`, cut from `crv2-release-integration`
at `f2e7cbd` (contains `f53fdb8` "Decide the lock a team can never reach, under
R48" and `handoff_readiness_v2/completion/WALKTHROUGH_CE_3_2026-09-23.md`; both
verified before any edit).
**Date:** 2026-09-23. **Builder:** repair builder, display and language defects
of the third Consumer Electronics walkthrough.
**Rules observed:** R48 — bugs first, calibration deferred, no new rules;
R43 — the team's language governs what a student is told; R44 — the operator
audit trail stays English; R32/R34/R35 — the inactivity rank guard, its record
and what the demoted team is told.

**Ids in scope:** W-CE3-05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18,
19, 20, and the named residues of W-CE2-06, 07, 08, 09. W-CE3-01 to 04 belong
to another builder and are untouched.

> Sections: (a) method and commands · (b) per id: source, repair,
> red-then-green · (c) every new or changed zh-CN sentence, least-trusted first
> · (d) findings raised, not closed · (e) what still needs authored content ·
> (f) tests, guards and the certification run · (g) proposed register status
> text · (h) distrust list.

**No gate is claimed closed.** Everything below is a repair with a test beside
it. The walkthrough that would prove these screens read correctly in a browser
has not been re-run, and no claim here rests on pixels.

---

## (a) Method, and the exact commands

Every defect was reproduced before it was repaired. The red run was taken
against the base with the repair reverted (`git checkout -- <runtime files>`
with the new tests already in place) and the green run after re-applying it;
both are quoted per id.

Backend tests ran only through

```bash
cd backend && TEST_POSTGRES_READY_SECONDS=1500 \
  flock -w 3600 /tmp/globalstrat-backend-test.lock \
  scripts/test-postgres <labels>
```

— a disposable PostgreSQL container per run, never the production database at
192.168.50.38, never `/etc/globalstrat-plus.env`. Another builder was running
concurrently on the same host, which is what the `flock` is for.

Frontend: focused Jest per id, then the full Jest run,
`python3 backend/scripts/check-participant-strings` with its selftest, and the
production build with the ESLint ratchet.

One commit per defect or small group, oldest first:

| commit | ids | what |
|---|---|---|
| `f0dbafb` | W-CE3-15 | the leaderboard says why the top score is fourth |
| `bc94e26` | W-CE3-16 | a dividend of $0.00 is not a distribution |
| `88db6f9` | W-CE3-05, 13 | the product is named; an overrun is not "not yet committed" |
| `0fa9e38` | W-CE3-14 | the third generation is listed with the requirement it fails |
| `0cc102c` | W-CE3-19, 20 | the export names its round, and marks what was set by hand |
| `49cc15f` | W-CE3-06, 07 | the Strategic Scorecard's last two English leaks |
| `4262529` | W-CE3-09, 10 | the market and platform names W-CE2-06 did not reach |
| `bc7c735` | W-CE3-12, 17, 18 | a tab label, five storage keys, a code run onto a sentence |
| `de462a4` | W-CE3-08 + W-CE2-08's residue | the distress alert, and a stored alert that can be said again |
| `c79c68e` | W-CE3-11 | the Strategic Briefing, and where its English really came from |

---

## (b) Per id

### W-CE3-15 — the top score shown in fourth place (P1) — fixed, `f0dbafb`

**Is it the R32 guard?** **Yes**, and the guard is working exactly as ruled.
Round 6 read *1 Nova Circuit 54.59 · 2 Aurora Devices 52.86 · 3 Solaris
Consumer 52.83 · 4 Meridian Tech 60.34*; Meridian Tech had $0 of revenue, so
`leaderboard.published_key` leads with `D('0')` for a commercially inactive
firm and it cannot finish level with, let alone above, a firm that competed.

**The defect is that the firing was invisible on that screen.** R34 records it
as a `DecisionAuditEvent`, R35 tells the demoted team on its own results
screen, and CRV2-08's drill-down surfaces it for an instructor — but the
leaderboard payload had no field for it (`rank, team_name, team_id,
performance_index, index_change, total_revenue, net_income,
shareholder_return, market_share, share_price, investor_confidence`) and
`pages/LeaderboardPage.js` contained no mention of inactivity or demotion. On
the one screen a competition is read from, the standings contradicted the
numbers beside them with nothing to explain it.

**Repair — R35's pattern, on R35's own record.**

- `leaderboard.demoted_team_ids(game, round_number)` reads R34's receipts
  rather than recomputing the classification, so a screen cannot disagree with
  the record about who was demoted. A round with no receipts — the round-zero
  bootstrap, or a game resolved before R34 — marks nobody and renders as
  before.
- `leaderboard.rank_marker()` and `rank_rule_note()` are the third-person half
  of R35's two sentences: a marker on the row and the rule under the table,
  both bilingual, both chosen in `engine/leaderboard.py` beside the payload
  that decides it, so no surface can describe the rule differently by picking a
  different sentence.
- `LeaderboardView` serves `commercially_inactive` on every row (true on the
  demoted ones), `rank_marker` on the demoted rows, and `rank_rule_note` once
  under the table, only when the table carries a marker.
- `LeaderboardPage.js` renders the marker beside the team name and the rule
  below the table. Neither sentence is written in the page.

**What it does not publish.** R35's standard is that the audit row names the
firm that was outscored so a dispute can be answered, and the team's own screen
does not republish another firm's score. The marker says no more than the table
already prints: the row's own revenue is on the same line. A test asserts the
rival's name and index are not in the marker.

**Red → green.** `core.tests.test_walk_ce3_display` with the repair reverted:
`Ran 8 tests … FAILED (errors=9)` — `KeyError: 'rank_rule_note'`,
`AttributeError: module 'core.engine.leaderboard' has no attribute
'demoted_team_ids'`, `KeyError: 'inactivity_rank_marker'`. Green with
`test_demotion_team_notice`, `test_inactivity_rank_guard`,
`test_scoring_dispositions`, `test_zh_terminology`,
`test_player_language_guard`, `test_crv2_12_language`: `Ran 83 tests … OK`.
Jest `walkCe3Screens`: `3 passed`.

### W-CE3-16 — a dividend of $0.00 reported as exceeding equity (P1) — fixed, `bc94e26`

**Source.** `lock_blockers_for` (`views/decisions.py`) compared
`total_dividends > projected_equity` with no floor, so `0 > -5,000,000` is
true. Every team whose projected equity was negative was told *Total dividends
of $0.00 exceed projected equity. Reduce the dividend.* — and in Chinese,
*股利总额 $0.00 超过预计股东权益。请降低每股股利。* The blocker cannot be
cleared: there is nothing below zero to reduce a zero dividend to. It sat in
the same list as the cash blocker, so a team that had stripped every reachable
decision back to nothing still could not lock.

**Repair.** The blocker now requires a distribution to exist before it can
exceed anything: `total_dividends > 0 and total_dividends > projected_equity`.
A team paying nothing out is not paying out more than its equity. No rule,
threshold or figure changes — a real dividend above projected equity is refused
exactly as before, which a test drives.

The edit is one line inside the file another builder is changing this week; it
is local to the financing block and touches nothing they are working in.

**Red → green.** `AssertionError: Lists differ: ['Total dividends of $0.00
exceed projected equity. Reduce the dividend.'] != []`, and the same in
Chinese — `Ran 4 tests … FAILED (failures=2)`. Green with
`test_deadline_lock_affordability`, `test_plant_collision`,
`test_committed_spend_one_calculator`: `Ran 45 tests … OK`.

### W-CE3-05 — the Marketing page never named the product (P1) — fixed, `88db6f9`

**Source.** `MarketingPage.js` printed `d.product_name` only inside the inner
product tab label, and that inner `Tabs` is rendered only when
`items.length > 1`; with one product the card was rendered directly. A team
with one product in each of two markets saw two tabs named only *Africa (1)*
and *North America (1)*, and set a price, a production volume, a campaign focus
and a channel split without being told which product it was deciding for.

**Repair.** The product name and its positioning tag are on the card itself,
so they are there whatever the market holds. The market is already the outer
tab's label and is not repeated.

**Red → green.** Jest `MarketingPage.productName`: `Unable to find an element
with the text: Nexus One` — `3 failed, 14 passed`. Green with
`MarketingPage.refusal`, `marketingPricingRules`, `SummaryPage`,
`walkCe2MoneyFormat`: `35 passed, 7 suites`.

### W-CE3-13 — an overrun called "not yet committed" (P1) — fixed, `88db6f9`

**Source.** `BudgetBar.js` rendered one sentence for both states:
*Committed this round: $49.3M of $19.3M cash — $-30.0M not yet committed*. The
label contradicts its own figure, and W-CE2-09's formatter repair left the sign
written into the amount rather than into the sentence.

**Repair.** Over-commitment is its own state and gets its own sentence,
`budget.committed_over_cash` — *over-committed by $30.0M* /
*超出可用现金 $30.0M* — with the shortfall stated as a magnitude. No figure
changes: both sentences read the same `committed_total`, `total_available` and
`unallocated` from `rd_costs.budget_assessment`.

**The two W-CE2-09 tests that pinned `$-12.6M` beside `budget.committed_of_cash`
are re-specified, not deleted.** The sign guard moves to the older-payload
`budget.unallocated` line, which is where a negative figure is still printed,
and the over-committed case gets its own assertions.

**Red → green.** `Expected substring: "budget.committed_over_cash" / Received:
… budget.committed_of_cash {"unallocated":"$-30.0M"}`. Green as above.

### W-CE3-14 — the third platform generation, absent with no reason (P1) — fixed, `0fa9e38`

**Source.** `RDContextView` `continue`d past generation 3 unless the team
already held an **active** generation 2 platform, so at round 5 — the
generation's own `unlock_round` — it was not listed and no reason was given.
Every other locked offer on the platform names itself: the M&A card says
*available from round 3*, the platform round check says *available from round
N*. A team could not tell an offer it had not yet earned from one that does not
exist.

**Repair — the server's own rule, already worded.**
`_check_generation_prerequisites` already computes that requirement, in the
reader's language: *Generation 2 must be active — Not yet developed* /
*第 2 代平台必须处于活跃状态 — 尚未开发*. Removing the `continue` lists the
generation like every other locked offer, with `prerequisites_met` false and
the rows stating why; `RDPage.js` already disables a generation whose
prerequisites are unmet (`const disabled = g.generation_order > 1 &&
!g.prerequisites_met`) and renders each row beneath it. **No unlock rule and no
price changes** — a test asserts the round requirement is met at round 5 and
the development cost is untouched.

**A finding, not closed here** — see (d): that `continue` was the only place
the "generation 2 must be active" requirement was applied at all.

**Red → green.** `AssertionError: unexpectedly None : the third generation is
not listed at all`, and four `TypeError: 'NoneType' object is not
subscriptable` — `Ran 6 tests … FAILED (failures=1, errors=4)`. Green with
`test_platform_lifecycle`, `test_rd_costs`, `test_product_rebase`:
`Ran 140 tests … OK`.

### W-CE3-19 — "No decisions saved" for every team (P1) — fixed, `0cc102c`

**Source.** The Status column of the team summary CSV reads each team's
submission state for the **currently open** round. Taken at the end of a game —
after the advance past round 6 had opened round 7 — that is the round nobody
has decided in yet, so the file stated the opposite of what happened for four
teams that played all six rounds. The same file's Cash column was right, which
is what makes the Status column misleading rather than merely empty.

**Repair.** The column heading names the round it describes:
`instructor.export_status_round` — *Status (round 7)* / *状态（第 7 回合）*. What
the column reports is unchanged; a reader can no longer take it for the game's
outcome.

**Red → green.** Jest: `expect(exportBlock).not.toMatch(/t\('instructor\.status'\)/)`
— `2 failed, 4 passed`. Green with the instructorDashboard suites:
`21 passed, 5 suites`.

### W-CE3-20 — a hand-set score exported with nothing saying so (P2) — fixed, `0cc102c`

**Source.** The grades CSV carried 88.0 for a team beside a real performance
index of 52.86 — a score overridden from the console before a single round was
played — and had no column marking it, though the console's own Team Grades
table tags the row *Overridden* and shows the computed score it replaced.

**Repair.** `TeamGrade.override_score` is non-null exactly when a score was set
by hand, which is the same fact the screen reads. The file gains one trailing
`Overridden Categories` column naming each such category and the computed score
it replaced (`Performance Index (computed 52.9)`), empty when nothing on that
row was touched. One trailing column rather than a companion per category, so
the score columns stay numeric and a spreadsheet still sums them. The header
follows the file's existing English column names (R44).

**Red → green.** `AssertionError: 'Overridden Categories' not found in ['Team
ID', 'Team Name', 'Performance Index', 'Overall']` — `Ran 4 tests … FAILED
(failures=1, errors=2)`. Green with
`test_r40_model_component_not_in_competition`, `test_cohort_caps`:
`Ran 57 tests … OK`.

### W-CE3-06 — the governance/tax sentence still English (P2) — fixed, `49cc15f`

**Source — a name, not a rule.** `coherence_feedback.GOVERNANCE_TAX` was
written as `governance_tax_consistency`, after the scoring function
`_score_governance_tax_consistency`, while `engine/coherence.py:209` stores the
entry under `breakdown['governance_tax']`. `_key_and_values` therefore never
matched that criterion and every Chinese read fell through to "keep the stored
sentence" — the module's own safe fallback, working exactly as designed, on a
key that could never match. Its two siblings matched and were translated, which
is why one sentence of three stayed English.

**Repair.** `GOVERNANCE_TAX = 'governance_tax'`, with
`GOVERNANCE_TAX_NAMES` accepting both spellings so a row written under either
is placed.

### W-CE3-07 — English market names in the scorecard detail tables (P2) — fixed, `49cc15f`

**Source.** `entry_mode_risk.details[].market`, `positioning_price` and
`distribution_positioning` each store `MarketDefinition.name`, so a Chinese
read carried *Africa*, *North America*, *East Asia* while the same market read
非洲 / 北美 everywhere else in the same response.

**The constraint.** `RoundResultCoherence.breakdown` is a hashed field of the
competitive `coherence` section, so what is stored cannot follow the reader —
W-CE2-07's constraint, unchanged — and the row carries **no market id**, so the
English name it does carry is the lookup key.

**Repair.** `coherence_feedback.localised_breakdown` takes a `market_names`
mapping, built by the view because the view holds the scenario, and renders a
copy of the detail rows. A name the mapping does not hold keeps its stored
value, so a market renamed or removed since resolution loses nothing. The
product name is left alone: it is the team's own, as `platform_display_name`
already treats a platform the team named. The stored row is written by neither
repair, which a test drives.

**Red → green (06 and 07 together).** `AssertionError: 'No governance-tax
conflict detected.' != '未发现治理与税务之间的冲突。'` and five `TypeError:
localised_breakdown() got an unexpected keyword argument 'market_names'` —
`Ran 8 tests … FAILED (failures=1, errors=5)`. Green with
`test_walk_ce2_language`, `test_manifest_determinism`,
`test_coherence_price_ranges`: `Ran 146 tests … OK`.

### W-CE3-09 — English market names on the supply-chain screens (P2) — fixed, `4262529`

**Source.** `ScenarioMarketsView` (`views/sc_views.py:365`) served
`{'id', 'code', 'name': m.name, 'currency_code'}` — the stored English name
with no `get_localized_field` — so *North America*, *East Asia*, *Western
Europe*, *Africa* and *South America* were the names in the routes table, the
terms-by-market table and the customs table on Logistics and Trade Finance
whatever the reader's language. It is the one read W-CE2-06's repair did not
cover.

**Repair.** The name follows the reader, from the scenario's authored
`name_zh`; no content is needed. **The `code` stays a code.** `NA`, `APAC`,
`EU` are stable identifiers, rendered in a tag beside the name
(`<Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag>`) and used as the option
value on the returns-hub selector; a code reads the same in both languages, and
translating it would break the selector's labels. A Chinese screen now reads
*北美 NA*.

### W-CE3-10 — the generated platform name's English suffix (P2) — fixed, `4262529`

**Source.** W-CE2-06 added `platform_display_name`, which renders
*<Team> Base Platform* — the name `game_creation` writes, not a name the team
chose — in the reader's language. Four reads beside the one it covered still
read `tp.name` raw:

| where | what a Chinese reader saw |
|---|---|
| `ProductContextView.active_platforms` (`views/decisions.py:2034`) | the Create Product modal's platform selector |
| `views/scorecard.py:177` | the dashboard's Balanced Scorecard — **and** the hard-coded English literal `'None'` for a team with no platform |
| `views/onboarding.py:59` | the post-login modal, the first screen after signing in |
| `views/research_reports.py:451` | the product report |

**Repair.** All four go through `platform_display_name`; the `'None'` literal
becomes the catalogue sentence `platform_none_held` (无). Nothing stored
changes, so no game needs migrating, and a name the team chose is never
translated — a test drives both.

`engine/strategy_advisory.py:271` reads the same field and is **left**: that
whole module is English prose outside these ids, and half-translating it would
produce a Chinese platform name inside an English paragraph. It is in (e).

**Red → green (09 and 10 together).** `AssertionError: Lists differ: ['North
America'] != ['北美']`; `'Base Platform' unexpectedly found in …
"platform_generation": "Team 0 Base Platform"` — `Ran 7 tests … FAILED
(failures=4)`. Green with `test_walk_ce2_language`, `test_zh_terminology`,
`test_player_language_guard`, `test_crv2_12_language`, `test_cc09_sc_api`,
`test_game_creation_paths`: `Ran 124 tests … OK`.

### W-CE3-12 — `Trade Finance & FX`, a hard-coded literal (P2) — fixed, `bc7c735`

One tab of nine on Financial Reports carried a bare string where every sibling
used `t(...)`. It now comes from the catalogue (贸易融资与外汇). A Jest guard
fails the moment **any** tab label in that file is written as a literal again,
so the class is closed rather than the instance.

### W-CE3-17 — five storage keys on the evaluation screen (P2) — fixed, `bc7c735`

**Source.** `CommunicationsPage.js:179` printed
`key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())` — *Framework
Grounding*, *Risk Acknowledgment*, *Stakeholder Awareness*, *Strategic
Consistency*, *Clarity And Persuasion* — and `:149` a hard-coded English
`(weight: N%)` beside each, on a screen whose feedback prose is otherwise
correctly Chinese.

**Label table, not authored content.** The tokens are authored by the scenario,
but they are the same five in every scenario this repository ships, so this is
`COMMUNICATION_CRITERION_LABELS` in the participant catalogue, served as
`criterion_label` beside the token the evaluation is keyed by. A token the
table has not been taught keeps the prettified fallback, so a scenario that
authors a new criterion renders a readable row rather than an empty one — and a
backend test reads the criteria **out of the scenario files**, so a new one
fails there instead of reaching a screen as a storage key.

Two things in the same view, of the same class, noted by the previous pass as
belonging with this work: the memo prompt interpolated `{active_markets}` from
the stored English `market__name`, and the literal `N/A` for a team with no
active market. Both now follow the reader.

### W-CE3-18 — the refusal code run onto the sentence (P2) — fixed, `bc7c735`

*Refused: …requires a written reason of at least 10 characters.*
**reason_required** — only a CSS margin stood between them, and the row's own
text has no margins. The code is now a labelled line of its own beneath the
sentence: *Refusal code* / *拒绝代码*, which is the walkthrough's "in its own
column" without adding a column to a table that is already wide.

**Red → green (12, 17 and 18 together).** `ImportError: cannot import name
'COMMUNICATION_CRITERION_LABELS'` — `Ran 4 tests … FAILED (errors=4)`; Jest
`walkCe3Screens` `7 failed, 6 passed`. Green: backend with
`test_zh_terminology`, `test_player_language_guard`, `test_crv2_12_language`,
`test_communication_word_limit`, `test_walk_ce2_language`:
`Ran 116 tests … OK`; Jest with `OperatorEventsPanel`: `20 passed, 2 suites`.

### W-CE3-08 — the distress alert, English in every round (P2) — fixed, `de462a4`

**Source.** *X has entered financial distress · Cash closing: … Net income: …*
was three f-strings inside `engine/financials.py:494-510`, so it never passed
through the alert catalogue and was English whatever the console's language,
while the other 32 alerts of the same round were Chinese. It is the alert that
matters most and the one an instructor could not read.

**Repair.** The three templates join `instructor_alerts._ALERT_TEXT` in both
languages and are chosen, worded and rendered exactly like their siblings; the
English is byte-identical to what shipped. The edit in `financials.py` is a
dozen lines in the distress block, far from the statement assembly another
builder is changing.

### W-CE2-08's named residue — an alert written before the switch stays English for ever

**The question asked:** can a stored alert be re-rendered at read time, the way
`coherence_feedback` re-renders a scorecard sentence? **Answer: yes, but not by
the same mechanism, and the difference is the point.**

A coherence breakdown stores the *numbers* its sentence was derived from, so a
reader can re-derive the key from what is already stored and nothing new has to
be written down. An alert stores only the finished sentence. So the rendering
inputs are stored: `InstructorAlert.render_context` =
`{key, language, values}` (migration `0091_instructor_alert_render_context`),
and `InstructorAlertsView` says the sentence again in the reader's language.

**Why this does not move the manifest.** `render_context` is excluded from both
sections that claim the model (`instructor_alert`, `narrative_alert`) with a
stated reason: it is a rendering input, not a computed outcome. The regenerated
inventory's only change is three `dropped` entries — every `hashed` and
`narrative` field list is byte-identical — so no round's hash moves. Schema v7
is still `PENDING`, so its provenance record is updated in place and says so.

**Known limit, recorded rather than hidden.** Two alert types interpolate a
name resolved at write time: `market_entry` (market and entry mode) and
`overproduction` (market and product). On a re-render those names stay in the
language they were written in. Every other alert interpolates only numbers and
the team's own name, which are language-neutral.

`test_walk_ce2_language.test_the_alerts_a_view_serves_are_the_stored_ones` is
**re-specified, not deleted**: it pinned W-CE2-08's deliberate choice ("read
time changes nothing"), which the third walkthrough recorded as the defect
above. It is replaced by three tests — the reader's language, an alert written
in the other language, and that reading never writes.

**Red → green.** `KeyError: 'distress'`; `ImportError: cannot import name
'render_context'`; `AssertionError: None is not true` for both section
exclusions — `Ran 12 tests … FAILED (failures=4, errors=8)`. Green with
`test_manifest_determinism`, `test_walk_ce2_language`, `test_zh_terminology`,
`test_durable_narratives`, `test_crv2_12_language`,
`test_player_language_guard`: `Ran 215 tests … OK`; and with
`test_walk_ce_language`: `Ran 65 tests … OK`.

### W-CE3-11 — the Strategic Briefing (P1, the big one) — fixed, `c79c68e`

**The record names the wrong module, and the difference decides the repair.**

W-CE3-11 attributes the English briefing to `core/engine/briefing.py` — 21
`parts.append(f"…")` calls and about 90 English literals, which is a true
description of that file. But **that module has no caller anywhere in the
tree**, and it would raise if it had one: `_compile_briefing` returns an
`agent_narratives` key that `StrategicBriefing` has no field for, so
`generate_strategic_briefings` fails for every team and writes nothing
(`Invalid field name(s) for model StrategicBriefing: 'agent_narratives'`). It
is not what the student read.

**What the student read is in the walkthrough's own evidence**,
`records/student-tour-t3-after-r1-zh-CN.json`, `observed.post_login_modal`:

> 第1回合战略简报您的团队绩效摘要和战略展望**Quarter 1 Results** Revenue
> declined 89.9% to $2,100,000. Net income: $-11,445,050. Cash position:
> $23,054,950.继续到仪表板完整简报可在「战略简报」标签中查看

Chinese page chrome around English prose. That prose is
`narratives._build_briefing_fields` rendered through `_fallback_text` — whose
zh-CN table is complete and was never reached — in the language
`get_team_language(team)` returned **at processing time**. The harness set the
student's language in `localStorage` only, so nothing had written `zh-CN` to
that team's enrolment when round 1 resolved, and every later round inherited
the same stored English.

**So the briefing has the same shape of defect as the coach alerts:** stored
Phase-2 prose frozen in the language of the moment it was written.

**Which envelope rule applies — asked and answered.** `StrategicBriefing` is a
**narrative** section: `in_output=False`, every field a `narrative_field`,
hashed on its own as `narrative_sha256` and declared "never part of the
competitive hash … visible but not disqualifying". So nothing here is inside
the competitive envelope, and the `coherence_feedback` constraint ("what is
stored cannot depend on who reads it") does not bind. What it offers instead is
a *technique*, and that technique fits exactly:

**Repaired at read time, with no new storage.** Every template sentence in a
briefing is derived from figures the reader can read back, so
`narratives.briefing_for_reader` runs the same builder again for the reader and
uses the result **only** where the stored text is recognisably that builder's
own output in one of the shipped languages. Model-written prose is never
replaced — a test drives that — an older or unplaceable row keeps exactly what
it has, and the stored row is never written. `_build_briefing_fields` gains a
`language_override` the writer never passes; the reader is the only caller.

**`briefing.py` is repaired anyway, and recorded as dead.** Its ~90
participant-facing English literals are now catalogue entries rendered in the
team's language (110 `briefing_*` keys, both languages, identical
placeholders), and the module is inside `check-participant-strings`'s declared
scope, so a literal cannot be written back into it. Along the way its market,
segment, entry-mode and acquisition names follow the reader; its RAG framework
sentence is asked for in the team's language; and the universal-gap check finds
a segment **by id** rather than by the name it had just localised — a bug that
would have fired the moment the module was translated. A test asserts nothing
calls it, so the fact is on record rather than rediscovered by the next reader.

**Red → green.** `AssertionError: '收入下降' not found in '**Quarter 1
Results**\n\nRevenue declined 89.5% to $2,100,000. Net income: $-11,445,050.
Cash position: $500,000.'` and `'Reduce operating costs' unexpectedly found in
…` — `Ran 12 tests … FAILED (failures=9)`. Green with
`test_durable_narratives`, `test_walk_ce_language`, `test_walk_ce2_language`,
`test_zh_terminology`, `test_player_language_guard`, `test_crv2_12_language`,
`test_manifest_determinism`: `Ran 257 tests … OK`.

---

## (c) Every new or changed zh-CN sentence — for a native reviewer, least-trusted first

**125 sentences, all of them new; none of the existing zh-CN entries was
changed.** 119 in `core/utils/participant_messages.py` (110 of them the
Strategic Briefing), 5 in the frontend catalogue, 1 in
`engine/instructor_alerts._ALERT_TEXT`.

Terminology follows `test_zh_terminology`: 游戏 for a game, 回合 for a round,
团队 for a team, 教师 for an instructor; 比赛, 队伍, 小组 and 轮 are not used,
and 竞赛 appears nowhere new.

**Tier 1 — prose written from scratch for this pass. Review these first.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 1 | Decision Summary › Budget Summary | `frontend:budget.committed_over_cash` | Committed this round: {{committed}} of {{cash}} cash — over-committed by {{over}} | 本回合已承诺支出：{{committed}}，现金共 {{cash}}；超出可用现金 {{over}} |
| 2 | Instructor › AI Coach | `instructor_alerts:distress` | {team} has entered financial distress · Cash closing: ${cash:,.0f}. Net income: ${net_income:,.0f}. Total debt: ${debt:,.0f}. Consequences, in force from the next round until the company returns to positive cash and profitability: +10% talent turnover, share price floor at 0.7x book value, no new debt, and no acquisitions. (Distress is assessed from this round's closing position, so the restrictions bite from round {next_round}.) · This team is in financial distress. Use this as a teaching moment about cash management, debt sustainability, and the downward spiral that can result from over-leveraging or under-pricing. | {team} 已进入财务困境 · 期末现金：${cash:,.0f}。净利润：${net_income:,.0f}。负债总额：${debt:,.0f}。自下一回合起生效、直至公司恢复正现金与盈利为止的后果：人才流失率上升 10%、股价下限为账面价值的 0.7 倍、不得新增借款、不得进行收购。（财务困境依据本回合期末状况判定，因此各项限制自第 {next_round} 回合起生效。） · 该团队正处于财务困境。可借此讲解现金管理、债务可持续性，以及过度举债或定价过低可能引发的恶性循环。 |
| 3 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_cash_critical` | Cash reserves critically low at {cash}. Immediate action required. | 现金储备严重不足，仅有 {cash}。需立即采取行动。 |
| 4 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_esg_excellent` | Excellent returns. Your ESG leadership is a competitive advantage. | 回报出色。贵公司在 ESG 方面的领先已成为竞争优势。 |
| 5 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_esg_none` | No ESG investment this round. You're missing potential tariff and tax benefits. | 本回合没有 ESG 投入，因而错过了潜在的关税与税收优惠。 |
| 6 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_esg_return` | Your ESG investment of {invested} generated {savings} in economic benefits ({roi}% quarterly return). | 贵公司投入的 {invested} ESG 资金带来了 {savings} 的经济收益（本回合回报率 {roi}%）。 |
| 7 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_bought_esg` | {name} added {shares} shares. Your ESG investments are attracting responsible capital. | {name} 增持 {shares} 股。贵公司的 ESG 投入正在吸引责任投资资本。 |
| 8 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_bought_growth` | {name} added {shares} shares. Your growth trajectory is attracting growth capital. | {name} 增持 {shares} 股。贵公司的增长态势正在吸引成长型资本。 |
| 9 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_bought_value` | {name} added {shares} shares. Your financial discipline appeals to value investors. | {name} 增持 {shares} 股。贵公司的财务纪律受到价值型投资者青睐。 |
| 10 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_sold_esg` | {name} sold {shares} shares. Your ESG profile may not meet their criteria. | {name} 减持 {shares} 股。贵公司的 ESG 表现可能未达到其标准。 |
| 11 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_sold_growth` | {name} sold {shares} shares. They may see insufficient growth momentum. | {name} 减持 {shares} 股。他们可能认为增长动能不足。 |
| 12 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_sold_value` | {name} sold {shares} shares. Rising leverage or declining margins may concern them. | {name} 减持 {shares} 股。上升的杠杆或下滑的利润率可能令其担忧。 |
| 13 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_leverage_elevated` | Leverage elevated at {ratio}x D/E. Conservative investors may be concerned. | 杠杆偏高，债务与股东权益之比为 {ratio} 倍。稳健型投资者可能会感到担忧。 |
| 14 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_net_income_positive` | Net income of {net_income} ({margin}% margin) — a profitable quarter. | 净利润 {net_income}（净利率 {margin}%）——本回合实现盈利。 |
| 15 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_net_loss` | Net loss of {loss}. Monitor cash runway closely. | 净亏损 {loss}。请密切关注现金还能支撑多少回合。 |
| 16 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_partnerships_active` | {count} active partnership(s) generating {value} in value. | {count} 项有效合作，创造价值 {value}。 |
| 17 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_perf_flat` | Flat quarter. Your Performance Index dipped slightly to {index} ({change}, #{rank}). | 本回合表现平淡。绩效指数小幅回落至 {index}（{change}，第 {rank} 位）。 |
| 18 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_perf_steady` | Steady progress. Your Performance Index edged up {change} to {index} (#{rank}). | 稳步前进。绩效指数小幅上升 {change} 至 {index}（第 {rank} 位）。 |
| 19 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_perf_strong` | Strong quarter. Your Performance Index rose {change} points to {index}, placing you #{rank} of {total} teams. | 本回合表现强劲。绩效指数上升 {change} 点至 {index}，在 {total} 家公司中排名第 {rank}。 |
| 20 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_perf_weak` | Challenging quarter. Your Performance Index fell {change} to {index}, dropping you to #{rank}. | 本回合颇为艰难。绩效指数下降 {change} 至 {index}，排名降至第 {rank} 位。 |
| 21 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_plants_operational` | {count} operational plant(s). Local manufacturing eliminates tariffs and reduces logistics costs. | {count} 座工厂已投产。本地生产可免除关税并降低物流成本。 |
| 22 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rank_climbed` | You climbed {places} position(s) to #{rank}. | 贵公司上升 {places} 位，现居第 {rank} 位。 |
| 23 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rank_dropped` | You dropped {places} position(s) to #{rank}. | 贵公司下降 {places} 位，现居第 {rank} 位。 |
| 24 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_deploy_cash_detail` | Holding {cash} in cash — {ratio}x revenue. Consider R&D, market entry, marketing, or dividends. | 持有现金 {cash}，相当于营收的 {ratio} 倍。可考虑用于研发、进入新市场、营销或分红。 |
| 25 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_esg_consider_detail` | ESG generates tariff reductions, tax incentives, and improves regulator satisfaction. | ESG 投入可带来关税减免与税收优惠，并提升监管机构的满意度。 |
| 26 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_esg_critical_detail` | Operating in a highly regulated market without ESG investment. Regulators heavily weight sustainability. | 贵公司在强监管市场经营，却没有 ESG 投入。监管机构对可持续发展的权重很高。 |
| 27 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_expansion_detail` | Operating in one market with {cash} cash. Export entry costs only $500K. | 贵公司只在一个市场经营，却持有现金 {cash}。以出口方式进入新市场仅需 $500K。 |
| 28 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_first_mover_detail` | No competitor currently serves {segment} well — this is an industry-wide gap. Investing in the features this segment values could give you first-mover advantage. Check Market Research to identify which platform capabilities they prioritize. | 目前没有竞争对手能很好地服务{segment}——这是全行业的空白。投入该细分市场看重的功能，有机会取得先发优势。可在市场研究中查看他们最看重哪些平台能力。 |
| 29 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_improve_fit_detail` | Your fit with {segment} in {market} is {fit}, but competitors are doing better. Review Market Research to identify which features this segment values most. | 贵公司在{market}对{segment}的契合度为“{fit}”，而竞争对手表现更好。可在市场研究中查看该细分市场最看重哪些功能。 |
| 30 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_investor_detail` | {name} reduced their position. Check Investor Relations to understand their criteria. | {name} 减持了贵公司股份。可在投资者关系页面了解其评判标准。 |
| 31 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_rd_talent_detail` | R&D team at baseline (3.0). Each level above 3.0 saves 5% on R&D costs. | 研发团队处于基准水平（3.0）。高于 3.0 的每一级可使研发成本下降 5%。 |
| 32 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_reduce_leverage_detail` | Your debt-to-equity ratio is {ratio}. Conservative investors are concerned. Consider using cash flow to repay debt or issuing equity. | 贵公司的债务与股东权益之比为 {ratio}。稳健型投资者对此感到担忧。可考虑用经营现金流偿还债务，或增发股权。 |
| 33 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_revenue_declined` | Revenue declined {pct}% to {revenue} — investigate segment performance. | 营收下降 {pct}%，至 {revenue}——请检视各细分市场的表现。 |
| 34 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_revenue_grew` | Revenue grew {pct}% to {revenue}. | 营收增长 {pct}%，达到 {revenue}。 |
| 35 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_revenue_surged` | Revenue surged {pct}% to {revenue}. | 营收大幅增长 {pct}%，达到 {revenue}。 |
| 36 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_inventory_detail` | {pct}% of production unsold. Reduce production or lower price. | {pct}% 的产量未能售出。请减少产量或下调价格。 |
| 37 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_inventory_title` | {product} inventory buildup in {market} | {product} 在{market}出现库存积压 |
| 38 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_runway_critical_detail` | At current burn of {burn}/round, cash depletes in ~{runway} rounds. | 按当前每回合 {burn} 的消耗速度，现金将在约 {runway} 个回合后耗尽。 |
| 39 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_runway_warning_title` | Cash runway declining: {runway} rounds | 现金可支撑的回合数正在下降：{runway} 个回合 |
| 40 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_share_price_fell` | Your share price fell to {price} ({pct}%). | 贵公司股价下跌至 {price}（{pct}%）。 |
| 41 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_share_price_rose` | Your share price rose to {price} ({pct}%). | 贵公司股价上涨至 {price}（{pct}%）。 |
| 42 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_share_price_steady` | Your share price held steady at {price} ({pct}%). | 贵公司股价保持在 {price}（{pct}%）。 |
| 43 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_stake_declining` | Your {group} are losing confidence. Review what changed. | 贵公司的{group}信心正在下降。请检视是什么发生了变化。 |
| 44 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_strategic_totals` | Total strategic investment: {cost}. Returns: {returns} ({roi}% quarterly). | 战略投入合计：{cost}。回报：{returns}（本回合 {roi}%）。 |
| 45 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_baseline` | Talent at baseline levels. Invest above 3.0 to unlock cost reductions. | 人才水平处于基准线。投入使其高于 3.0 才能带来成本下降。 |
| 46 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_building` | Talent costs {invested} with {savings} in benefits. Building momentum. | 人才成本 {invested}，带来收益 {savings}。势头正在形成。 |
| 47 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_positive` | Talent investment of {invested} generated {savings} in benefits. Net positive ROI. | 人才投入 {invested} 带来了 {savings} 的收益，净回报为正。 |
| 48 | Leaderboard, under the table | `participant_messages:inactivity_rank_rule` | A company that sold nothing in a round did not compete in it, and is placed below every company that did, whatever its score. The performance index itself is not reduced; only the placing. | 某一回合没有任何销售的公司，即为该回合未参与竞争，无论得分高低，都会排在所有参与竞争的公司之后。绩效指数本身并未被扣减，受影响的只是排名。 |

**Tier 2 — short sentences and labels.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 49 | Communications › criteria | `frontend:communications_page.criterion_weight` | (weight: {{weight}}%) | （权重：{{weight}}%） |
| 50 | Instructor › Grading & Export | `frontend:instructor.export_status_round` | Status (round {{round}}) | 状态（第 {{round}} 回合） |
| 51 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_competitor_moves` | {team}: {moves}. | {team}：{moves}。 |
| 52 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_esg_building` | Returns are building — ESG investments compound over time. | 回报正在累积——ESG 投入的效果会随时间叠加。 |
| 53 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_bought` | {name} added {shares} shares. | {name} 增持 {shares} 股。 |
| 54 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_held` | {name} maintained position. No change in confidence. | {name} 维持持仓。信心没有变化。 |
| 55 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investor_sold` | {name} sold {shares} shares. | {name} 减持 {shares} 股。 |
| 56 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investors_increased` | {names} increased positions. | {names} 增加了持仓。 |
| 57 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_investors_reduced` | {names} reduced exposure. | {names} 减少了持仓。 |
| 58 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_metric_debt_to_equity` | Debt-to-Equity | 债务与股东权益之比 |
| 59 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_move_acquired` | Acquired {target} | 收购了 {target} |
| 60 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_move_entered` | Entered {market} via {mode} | 通过{mode}进入{market} |
| 61 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_no_data` | Round data not yet available. | 本回合数据尚未生成。 |
| 62 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_corporate_esg` | Corporate Strategy → ESG | 公司战略 → ESG |
| 63 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_corporate_talent` | Corporate Strategy → Talent | 公司战略 → 人才 |
| 64 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_finance_budget` | Finance → Budget Allocation | 财务管理 → 预算分配 |
| 65 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_finance_capital` | Finance → Capital Management | 财务管理 → 资本管理 |
| 66 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_investor_relations` | Financial Reports → Investor Relations | 财务报告 → 投资者关系 |
| 67 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_market_research_segments` | Market Research → Segments | 市场研究 → 细分市场 |
| 68 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rank_held` | You maintained position #{rank}. | 贵公司保持在第 {rank} 位。 |
| 69 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_esg_consider_title` | Consider ESG Investment | 考虑进行 ESG 投入 |
| 70 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_esg_critical_title` | ESG Investment Critical for Highly Regulated Market | 在强监管市场，ESG 投入至关重要 |
| 71 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_expansion_title` | Consider International Expansion | 考虑开拓国际市场 |
| 72 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_first_mover_title` | First-Mover Opportunity: {segment} | 先发机会：{segment} |
| 73 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_improve_fit_title` | Improve {segment} Appeal | 提升对{segment}的吸引力 |
| 74 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_investor_title` | Address {name} Concerns | 回应 {name} 的关切 |
| 75 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_rd_talent_title` | Invest in R&D Talent | 加大研发人才投入 |
| 76 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_revenue_established` | Revenue of {revenue} established. | 本回合实现营收 {revenue}。 |
| 77 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_revenue_softened` | Revenue softened {pct}% to {revenue}. | 营收下滑 {pct}%，至 {revenue}。 |
| 78 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_concentration_detail` | All revenue from one market. Consider geographic diversification. | 全部营收来自一个市场。可考虑地域多元化。 |
| 79 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_concentration_title` | Single-market concentration risk | 单一市场集中风险 |
| 80 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_interest_detail` | Operating income barely covers interest. Consider debt repayment. | 营业利润勉强覆盖利息支出。可考虑偿还债务。 |
| 81 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_interest_title` | Interest coverage critically low: {coverage}x | 利息保障倍数过低：{coverage} 倍 |
| 82 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_runway_critical_title` | Cash Runway: {runway} rounds remaining | 现金可支撑 {runway} 个回合 |
| 83 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_runway_warning_detail` | Monitor closely. Consider revenue acceleration or cost reduction. | 请密切关注。可考虑加快营收增长或压缩成本。 |
| 84 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_turnover_detail` | High turnover erodes institutional knowledge. | 高流失率会侵蚀组织的知识积累。 |
| 85 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_risk_turnover_title` | {pool} talent turnover at {pct}% | {pool}人才流失率达到 {pct}% |
| 86 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_stake_low` | Your {group} have low confidence in your current strategy. | 贵公司的{group}对当前战略信心不足。 |
| 87 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_stake_moderate` | Your {group} have moderate confidence. | 贵公司的{group}信心一般。 |
| 88 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_stake_satisfied` | Your {group} are satisfied with your current direction. | 贵公司的{group}对当前方向感到满意。 |
| 89 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_stake_warming` | Your {group} are warming to your strategy. | 贵公司的{group}开始认同贵公司的战略。 |
| 90 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_strategic_none` | No significant strategic investments this round. | 本回合没有重要的战略投入。 |
| 91 | Communications › evaluation | `participant_messages:clarity_and_persuasion` | Clarity and persuasion | 表达清晰与说服力 |

**Tier 3 — single words and names; lowest risk.**

| # | where | key | en | zh-CN |
|---|---|---|---|---|
| 92 | Financial Reports, the tab bar | `frontend:financial_reports.trade_finance_fx` | Trade Finance & FX | 贸易融资与外汇 |
| 93 | Instructor › Operator Log | `frontend:instructor.oplog_refusal_code` | Refusal code | 拒绝代码 |
| 94 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_esg_solid` | Solid returns. | 回报稳健。 |
| 95 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_fit_moderate` | Moderate | 中等 |
| 96 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_fit_strong` | Strong | 强 |
| 97 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_fit_very_weak` | Very Weak | 很弱 |
| 98 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_fit_weak` | Weak | 弱 |
| 99 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_group_channel_partners` | channel partners | 渠道伙伴 |
| 100 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_group_investors` | investors | 投资者 |
| 101 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_group_regulators` | regulators | 监管机构 |
| 102 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_metric_cash_position` | Cash Position | 现金状况 |
| 103 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_metric_revenue` | Revenue | 营收 |
| 104 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_page_market_strategy` | Market Strategy | 市场战略 |
| 105 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_partnerships_none` | No active partnerships. | 暂无有效合作。 |
| 106 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_plants_none` | No owned plants. | 尚未拥有工厂。 |
| 107 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_pool_commercial` | Commercial | 商业 |
| 108 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_pool_operations` | Operations | 运营 |
| 109 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_pool_rd` | R&D | 研发 |
| 110 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_deploy_cash_title` | Deploy Excess Cash | 动用闲置现金 |
| 111 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_rec_reduce_leverage_title` | Reduce Leverage | 降低杠杆 |
| 112 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_campaign_uplift` | Marketing effectiveness | 营销效果提升 |
| 113 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_cogs_savings` | Operations efficiency | 运营效率提升 |
| 114 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_talent_rd_savings` | R&D cost reduction | 研发成本下降 |
| 115 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_trend_declined` | declined | 有所下降 |
| 116 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_trend_improved` | improved | 有所改善 |
| 117 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_trend_stable` | stable | 保持稳定 |
| 118 | Strategic Briefing (post-login modal, Dashboard) | `participant_messages:briefing_unknown_mode` | unknown mode | 未知模式 |
| 119 | Stakeholder Communications, the prompt | `participant_messages:communication_no_active_market` | no market yet | 尚无市场 |
| 120 | Communications › evaluation | `participant_messages:framework_grounding` | Framework grounding | 理论框架运用 |
| 121 | Leaderboard, the row | `participant_messages:inactivity_rank_marker` | Did not compete | 未参与竞争 |
| 122 | Dashboard › Balanced Scorecard | `participant_messages:platform_none_held` | None | 无 |
| 123 | Communications › evaluation | `participant_messages:risk_acknowledgment` | Risk acknowledgment | 风险认识 |
| 124 | Communications › evaluation | `participant_messages:stakeholder_awareness` | Stakeholder awareness | 利益相关者意识 |
| 125 | Communications › evaluation | `participant_messages:strategic_consistency` | Strategic consistency | 战略一致性 |

---

## (d) Findings raised, not closed

These are defects this pass found and deliberately did not repair, each with
the reason. None of them is in the four ids assigned to another builder.

| # | what | where | why it is not repaired here |
|---|---|---|---|
| 1 | **The "generation 2 must be active" requirement is not enforced anywhere.** The `continue` removed for W-CE3-14 was the only place it was applied. Neither the decision write (`serializers/decisions.py`, which gates on `unlock_round`) nor the lock validator has ever checked it, so a direct POST could always queue a Generation 3 platform without a Generation 2. Removing the `continue` neither opens nor closes that. | `views/decisions.py`, `serializers/decisions.py` | Enforcing it would be a **new rule**, which R48 forbids without a ruling; and the write path is the concurrently-changing lock/affordability area. For the integrator. |
| 2 | **`engine/briefing.py` cannot run.** `_compile_briefing` returns an `agent_narratives` key `StrategicBriefing` has no field for, so `generate_strategic_briefings` raises for every team, swallows it in a `print`, and returns 0. Nothing calls it. | `core/engine/briefing.py:50-78` | Making it run would revive a module no release path uses and would put a second writer on the same rows. The choice — wire it up, or delete it — belongs to whoever owns CC-27. |
| 3 | **An unsourced price in a recommendation.** *Export entry costs only $500K* is a literal in the code, read from no scenario, and a student reads it as a fact about the game. | `briefing_rec_expansion_detail` | Changing it, or sourcing it from `MarketDefinition.entry_cost_base`, is a calibration question — deferred by R48. The literal is carried through unchanged so nothing a player is told moved. |
| 4 | **The harness never writes a student's language to the server.** `harness/walk.py:sign_in` sets `localStorage` and signs in; nothing PUTs `/api/user/preferences/`. That is why team 3's enrolment stayed English through six rounds, and why every stored Phase-2 artefact for that team was written in English. | walkthrough harness | It is the harness, not the platform — but it means the third walkthrough's zh-CN coverage of *stored* prose is weaker than it reads. The next walkthrough should set the language through the UI switch (or the route) before round 1 is resolved. |
| 5 | **Code words rendered raw on the briefing card.** `GameDashboard.js` prints `r.priority`, `r.category`, `inv.action` and two hard-coded English words (`Generated`, `Go to:`) beside prose that now follows the reader. | `pages/GameDashboard.js` | Outside the named ids, and the natural repair is a label map, which is the computed-`t()`-key pattern already inventoried with the owner. Listed in (e). |

---

## (e) Remaining English a zh-CN user can still see

Nothing on this list is new. Items 1–3 and 6–9 carry over from
`WALK_CE2_LANGUAGE_2026-09-23.md` §(d); items 4 and 5 are what this pass
deliberately left.

| # | screen | source | what | what it needs |
|---|---|---|---|---|
| 1 | Industry News headlines | `MarketConditionByRound.market_outlook_narrative` | scenario-authored, English only; **no `_zh` field on the model** | **Authored content and a model change**: a `market_outlook_narrative_zh` column + migration, then a Chinese line per market-round block. Not a code fix. |
| 2 | Financial Reports › Trade Finance & FX, the section body | `pages/FinancialReportsPage.js` | ≈20 literals: *Open FX hedge positions*, *Payment & export-credit posture*, the table columns, the rating words *AAA / BBB+ …* and *VERY LOW … DISTRESS* | Code only. The tab **label** is fixed (W-CE3-12); the body is a whole section outside the named ids, and the rating words are also colour keys, so they need a code-and-label split like W-CE-16(b)'s `_fit_code`. |
| 3 | Trade Finance instrument names; Sourcing component and supplier names | scenario supply-chain data | *Open Account*, *Letter of Credit*, *Camera Module*, *Final Assembly* | **Authored content**: the CE scenario authors no Chinese counterpart for these fields. |
| 4 | Strategy Tools › the advisory playbooks | `engine/strategy_advisory.py` | every `Strategy(strategy_name=…, description=…, example=…)` and the platform name inside them | Code only, but a large authored surface of its own: ~40 English strings. Half-translating it (the platform name alone) would read worse than leaving it, which is why W-CE3-10 stopped at the four participant reads. |
| 5 | Dashboard › Strategic Briefing card | `pages/GameDashboard.js` | `r.priority`, `r.category`, `inv.action` printed raw; the literals *Generated* and *Go to:* | Code only; the label map is the computed-`t()`-key pattern already inventoried with the owner. |
| 6 | Communications › criterion **descriptions** | scenario YAML `evaluation_criteria[].description` | *Does the memo match the team's actual market entry decisions…* | **Authored content.** The criterion **names** are fixed (W-CE3-17); the one-line description beside each is scenario prose with no `_zh`. |
| 7 | Logistics › *Incoterms*; market **codes** (`NA`, `APAC`, `EU`) | `pages/LogisticsPage.js`, `sc_views` | proper terms and stable identifiers | Judgment calls, left as before. A code is a code in both languages and is used as an option value. |
| 8 | Onboarding image `alt` texts | `components/OnboardingModal.js` | accessibility text on images | Not visible on screen; unchanged. |
| 9 | Keys reached through label maps (`t(variable)`) | 25 computed keys across 14 files | invisible to the static scan | The pattern inventoried in `evidence/unresolved-locale-keys/`, with the owner. `check-participant-strings` reports the same 30 unresolved keys and passes. |

---

## (f) Tests, guards and the certification run

**New and extended guards**

| guard | what it holds |
|---|---|
| `backend/core/tests/test_walk_ce3_display.py` (new, 11 classes, 65 tests) | every backend behaviour in (b), by request where a route exists |
| `frontend/.../src/pages/walkCe3Screens.test.js` (new, 5 groups, 13 tests) | the leaderboard reads the marker and the rule from the payload and writes neither sentence itself; **no** tab label in `FinancialReportsPage.js` is a literal; the evaluation prefers the authored criterion label and keeps one prettifier as a fallback; the operator log's refusal code is labelled and outside the sentence; both catalogues carry each new key with the same placeholders |
| `frontend/.../src/pages/MarketingPage.productName.test.js` (new, 2 tests) | a market holding exactly one product still names it, and a market holding two names the open card |
| `frontend/.../src/components/BudgetBar.test.js` | re-specified for W-CE3-13: the over-committed sentence, the magnitude, and the sign guard moved to the line that still prints a negative |
| `backend/core/tests/test_walk_ce2_language.py` | re-specified for the coach alerts: the reader's language, an alert written in the other language, and that reading never writes |
| `backend/scripts/participant-strings.config.json` | `core/engine/briefing.py` joins the declared participant-facing scope, so A4 fails the build on a new literal there |

**Commands, and what they returned**

| command | result |
|---|---|
| `cd backend && TEST_POSTGRES_READY_SECONDS=1500 flock -w 3600 /tmp/globalstrat-backend-test.lock scripts/test-postgres core --parallel 8` — **once**, at `c79c68e` | `Ran 1724 tests in 120.063s … OK` (real 2m17s) |
| `CI=true npx react-scripts test --watchAll=false` (full Jest) | `Test Suites: 54 passed, 54 total · Tests: 512 passed, 512 total`, 17.3 s |
| `python3 backend/scripts/check-participant-strings --repo .` | `PASS 5879 unit(s) examined, 0 reviewed suppression(s)`; note: 30 computed `t()` keys unresolved, unchanged |
| `python3 backend/scripts/check-participant-strings-selftest` | `selftest: 34 ok, 0 failed` |
| `CI=false GENERATE_SOURCEMAP=false npx react-scripts build` | exit 0 |
| `node eslint-warning-count.js <build log>` | `eslint warnings: 54 (baseline 54)` — no new warning; the baseline is not moved |
| `python3 manage.py dump_manifest_schema` | `manifest_schema_v7.json` rewritten; the only change is three `dropped` entries for `render_context`, every `hashed` and `narrative` list byte-identical |

The full backend suite ran **exactly once**, from `c79c68e`, and no runtime code
changed after it: the two commits that follow are this report and the
regenerated string inventory.

**Auditor preflight, the applicable questions**

- *Did inventory start from registered routes/models, not only code using the
  new abstraction?* Yes — the platform-name sweep started from a grep of every
  read of `TeamPlatform.name` in the tree, not from callers of
  `platform_display_name`; the briefing investigation started from the
  walkthrough's own evidence record, not from the module the record named.
- *Is there an active legacy or alternate entry point?* Yes, and it is finding
  (d)2: `engine/briefing.py` is an alternate writer for `StrategicBriefing`
  that cannot run. Recorded, not revived.
- *Does a failure/refusal audit survive rollback?* Unchanged by this work; no
  audit write is added or removed. The leaderboard marker **reads** R34's
  append-only receipts and writes nothing.
- *Is each correlation ID generated once?* Not touched.
- *Is background/external work delayed until commit?* Not touched.
- *Does provenance identify runtime bytes?* Yes — `manifest_schema_v7.json` and
  its `PROVENANCE.json` entry are regenerated and the change is stated in the
  record while v7 is still `PENDING`.
- *Do README commands run exactly as written?* The commands in (f) are the ones
  that were run, copied from the shell.
- *Do P0/P1/P2 labels match their definitions?* The walkthrough's labels are
  carried unchanged; nothing is re-graded here.
- *Does each negative test prove mutation did not occur?* Yes, for the three
  read-time renderers: `test_the_stored_row_is_never_written`,
  `test_reading_never_writes_the_stored_row` and
  `test_reading_an_alert_never_writes_it`.

---

## (g) Proposed register status text

For `V2_FINDINGS_REGISTER.md` — **proposed, not applied**; this builder does not
edit the register.

| id | proposed status |
|---|---|
| **W-CE3-05** | **Repaired** at `88db6f9`. The product name and positioning tag are on the Marketing card itself, so a market holding exactly one product still names what is being priced. Jest render test, both branches. Not verified in a browser. |
| **W-CE3-06** | **Repaired** at `49cc15f`. `coherence_feedback.GOVERNANCE_TAX` named the scoring function, not the key the engine stores the breakdown entry under, so the sentence could never be placed; both spellings are accepted now. |
| **W-CE3-07** | **Repaired** at `49cc15f`. The scorecard's detail tables name the market for the reader, keyed on the stored English name because the hashed row carries no market id. Stored row untouched. |
| **W-CE3-08** | **Repaired** at `de462a4`. The distress alert is in the alert catalogue in both languages; **and** W-CE2-08's residue is closed — a stored alert carries its rendering inputs (`render_context`, excluded from both manifest sections) and is re-rendered in the reader's language. Residue: two alert types embed a name resolved at write time. |
| **W-CE3-09** | **Repaired** at `4262529`. The supply-chain market list names the market for the reader; the market **code** is deliberately left as a code. |
| **W-CE3-10** | **Repaired** at `4262529`. Four more reads go through `platform_display_name`; the English literal `'None'` becomes a catalogue sentence. `engine/strategy_advisory.py` is deliberately left and listed. |
| **W-CE3-11** | **Repaired** at `c79c68e`, **with the record corrected.** The module the finding names (`engine/briefing.py`) has no caller and cannot run; the English a Chinese student actually read is `narratives._build_briefing_fields`, frozen in the language stored at processing time. Repaired at read time with no new storage; `briefing.py` is translated anyway and brought inside the static check's scope, and two findings are raised (see below). |
| **W-CE3-12** | **Repaired** at `bc7c735`. The tab label is in the catalogue, and a guard fails on any literal tab label in that file. |
| **W-CE3-13** | **Repaired** at `88db6f9`. An over-committed team is told it is over, by how much, as a magnitude. |
| **W-CE3-14** | **Repaired** at `0fa9e38`. The third generation is listed with the requirement it fails, from the server's own already-worded rule. No unlock rule or price changed. **Raises a new finding:** that requirement is enforced nowhere on the write path. |
| **W-CE3-15** | **Repaired** at `f0dbafb`. The cause is the R32 guard firing as ruled; the defect was that the leaderboard said nothing. A marker on the row and the rule under the table, rendered from R34's stored payload by the module that renders R35's team-facing notice. |
| **W-CE3-16** | **Repaired** at `bc94e26`. The dividend blocker requires a distribution to exist. No threshold changed. |
| **W-CE3-17** | **Repaired** at `bc7c735`. The five criteria have authored bilingual names, served beside the token; the weight comes from the catalogue. A test reads the criteria out of the scenario files so a new one cannot reach a screen as a storage key. |
| **W-CE3-18** | **Repaired** at `bc7c735`. The refusal code is a labelled line of its own. |
| **W-CE3-19** | **Repaired** at `0cc102c`. The export's Status column names the round it describes. |
| **W-CE3-20** | **Repaired** at `0cc102c`. The grades export carries an `Overridden Categories` column naming the category and the computed score it replaced. |
| **W-CE2-06 residue** | **Closed** by W-CE3-07, 09 and 10. |
| **W-CE2-07 residue** | **Closed** by W-CE3-06. |
| **W-CE2-08 residue** | **Closed** by W-CE3-08's second half, with one stated limit. |
| **W-CE2-09 residue** | **Closed** by W-CE3-13. |

**New findings to register** — (d)1 the unenforced generation prerequisite,
(d)2 `engine/briefing.py` cannot run, (d)3 the unsourced `$500K` export entry
cost, (d)4 the harness never writes a student's language to the server.

---

## (h) Distrust list

Only what needs the owner, the production host, a browser, or a native speaker.

1. **A native zh-CN reviewer, for the 125 sentences in (c).** The Strategic
   Briefing block alone is 110 of them and is the largest single body of new
   Chinese prose this programme has added at once. Tier 1 is where the risk is.
2. **A browser.** Nothing here is verified in a real browser. The marker and
   footnote on the leaderboard, the product name on the Marketing card, the
   refusal code on its own line and the re-rendered briefing are asserted at
   the payload and the source, not at the pixels — and the sandbox has no CJK
   font, so a Chinese screen cannot be photographed here at all.
3. **The owner or the integrator, for finding (d)1.** Whether the "generation 2
   must be active" requirement should be enforced on the write path is a rule
   question. R48 delegates the pending calls to the integrator; this one is new,
   so it is stated rather than decided.
4. **Whoever owns CC-27, for finding (d)2.** `engine/briefing.py` should be
   wired up or deleted. Leaving a second, broken writer for the same rows is
   the condition that made W-CE3-11 hard to diagnose.
5. **The next walkthrough, for finding (d)4.** Until the harness sets a
   student's language through the product, the zh-CN coverage of *stored*
   Phase-2 prose is weaker than the record reads, and this pass's read-time
   repairs are exactly what such a walkthrough would exercise.
6. **The production host, for the migration.** `0091_instructor_alert_render_context`
   adds one nullable JSON column to `instructor_alert`. It has run only against
   disposable PostgreSQL here.

---

*Written by the repair builder for the third Consumer Electronics walkthrough's
display and language defects, 2026-09-23. No gate is claimed closed; no push,
no merge.*
