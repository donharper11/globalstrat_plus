# CRV2-12 — before and after, and the control that holds it

**Recorded:** 2026-09-12, branch `crv2-12-language-completion`, from
`crv2-release-integration` at `46b4bbe`.

This records what the completion pass changed. The Stage 1 candidate
inventory is `STATIC_STRING_INVENTORY.md`; the standard applied is
`AUTHORING_STANDARD.md`; the prevention control is
`backend/scripts/check-participant-strings`.

---

## 1. The four V2-069 defects

### (1) `round_not_accepting` interpolated the raw English status

`Round.STATUS_CHOICES` stores `pending|open|closed|processed`. The zh-CN
template embedded that token directly.

| | |
|---|---|
| before (zh-CN) | 第 3 回合状态为“closed”，不能再提交决策。 |
| after (zh-CN) | 第 3 回合状态为“已关闭”，不能再提交决策。 |
| after (en) | Round 3 is closed and no longer accepts decisions. *(unchanged)* |

`ROUND_STATUS_LABELS` in `core/utils/participant_messages.py` labels all four
authored statuses. Assertion **A5** fails the build if `STATUS_CHOICES` gains a
value that is not labelled, so the helper's English fallback cannot quietly
become the normal path.

### (2) `IsTeamMember` named the wrong action on seven read-only routes

Eleven view classes are guarded by `IsTeamMember`; seven expose only `get`:
`DecisionSummaryView`, `RDContextView`, `ProductContextView`,
`MarketingContextView`, `StrategyContextView`, `FinanceContextView`,
`TalentContextView`.

| | |
|---|---|
| before, any method | You do not have permission to change this team’s decisions. |
| after, safe methods | You do not have permission to view this team’s decisions. |
| after, write methods | You do not have permission to change this team’s decisions. |
| after, safe, zh-CN | 您无权查看该团队的决策。 |

The count is pinned by a test: if a write handler is added to one of those
classes, `test_the_seven_read_only_routes_are_still_seven` fails and the
wording decision is revisited rather than silently wrong.

### (3) The Summary view returned storage names and English-only advice

`SummaryPage.js` renders `lock_blockers` and each category's warnings
verbatim — there is no `t()` around them — so these strings reach the
participant exactly as the backend emits them.

| before | after (en) | after (zh-CN) |
|---|---|---|
| `rd_budget is 0.` | R&D budget is set to zero. Review this before locking. | 研发预算 已设为零。锁定前请确认。 |
| `Budget allocation required.` | Set the budget allocation before locking. | 锁定前，请先设置预算分配。 |
| `No submission created yet.` | No decisions have been started for this round. Open any decision area to begin. | 本回合尚未开始任何决策。请打开任一决策页面开始填写。 |
| `No R&D investment this round.` | No R&D investment is planned this round. Open R&D Investment to add one. | 本回合尚未安排研发投入。请打开“研发投入”页面添加。 |
| `3 product-market(s) not configured.` | 3 product-market combination(s) still need a marketing mix. Open Marketing Mix to complete them. | 还有 3 个产品—市场组合尚未设置营销组合。请打开“营销组合”页面完成设置。 |
| `You're operating in X but have no products assigned there. Go to Product Portfolio to add a target market.` | Your team is active in X but has no products assigned there. Open Product Portfolio and add X as a target market. | 您的团队已在 X 开展业务，但尚未在该市场投放产品。… |
| `You have products in X but no marketing decisions configured. …` | Your team has products in X but no marketing mix set there. Open Marketing Mix to set unit price, production volume and promotion. | 您的团队在 X 已有产品，但尚未设置营销组合。… |
| `Projected ending cash is negative ($-1,250,000). Increase revenue or raise financing.` | Projected ending cash is $-1,250,000.00. Reduce spending or raise financing before locking. | 预计期末现金为 $-1,250,000.00。锁定前请减少支出或增加融资。 |
| `No financing changes this round.` | No financing changes this round. No action is required. | 本回合没有融资变动，无需操作。 |
| `Product Portfolio is required before locking.` | Set the product portfolio before locking. | 锁定前，请先设置产品组合。 |
| `Marketing Mix is required before locking.` | Set the marketing mix for every active product-market combination before locking. | 锁定前，请为每个活跃的产品—市场组合设置营销组合。 |
| `Strategy Mix is required before locking.` | Set at least one strategy decision before locking. | 锁定前，请至少设置一项战略决策。 |

The last four reuse the keys the **lock refusal** already used, rather than
new sentences. Before this pass the Summary and the lock described the
projected-cash rule with two different sentences *and* two different money
formats (`$-1,250,000` against `$-1,250,000.00`); they now share one key and
one rendering.

### (4) `get_user_language` queried `Enrollment` on every permission check

Measured, not asserted — `test_language_is_resolved_once_per_request` counts
the statements that read `"enrollment"."language"` on a GET of the Decision
Summary sent with no `Accept-Language` header:

| | language-resolution queries |
|---|---:|
| before (helper as it read pre-CRV2-12) | **2** |
| after (memoised on the request) | **1** |

Two is what this one endpoint costs: the permission check and the view body
each resolved the caller's language. `views/decisions.py` calls the resolver
from twenty-four places, so a request crossing more of them paid more. The
repair is a per-request memo on the request object, the same shape
`auth_context` already uses for the decoded JWT; the resolved value cannot
change within a request, so it changes no answer.

Counting every statement whose text contains "enrollment" gives 4 → 3 and
measures nothing: `IsTeamMember`'s own membership check reads the same table,
and the supply-chain categories touch `sc_sinosure_enrollment`.

---

## 2. Beyond the four — what the sweep found

### Scenario-authored names were interpolated raw (new finding, repaired)

`MarketDefinition`, `PlatformGenerationDefinition` and `FeatureDefinition`
each carry a `name_zh`, and `get_localized_field` reads it with an English
fallback. Fourteen call sites passed `.name` instead, so a Chinese refusal
carried an English market, platform or feature name:

> before (zh-CN) — 您的团队已在 **Home** 开展业务，但尚未在该市场投放产品。
> after (zh-CN) — 您的团队已在 **本土市场** 开展业务，但尚未在该市场投放产品。

One Summary response could even name the same market two ways: the
active-presence branch used `presence.market.name` while the entering-market
branch two blocks below already used `get_localized_field`.

`TeamProduct.name` is deliberately still raw — a team names its own product
during play and there is no translated counterpart to read. That distinction
is about who authored the name, which the syntax cannot supply, so it is
declared in the check's `localised_name_arguments` rather than inferred.

### The same sentence in two places (repaired)

`IsTeamMember.message`, `IsRoundOpen.message` and `IsInstructor.message` each
restated a sentence the catalogue already held. They now import it. DRF only
falls back to the class attribute when `has_permission` returns without
setting one, but a second copy is a second place to drift.

`IsInstructor` additionally said "Instructor or Admin access required" — the
platform's role vocabulary, English-only. It is now "This area is open to
instructors only." / 「此区域仅向教师开放。」

### The R&D prerequisite rows were copy wearing structured-data clothing

`RDPage.js:176` renders `{p.requirement} — {p.detail}` with no `t()`. Six
strings built as dict values therefore reached Chinese teams in English:

| before | after (en) | after (zh-CN) |
|---|---|---|
| `Round 5 or later` | Round 5 or later | 第 5 回合或之后 |
| `Current round: 3` | Current round: 3 | 当前回合：3 |
| `Gen 2 must be active` | Generation 2 must be active | 第 2 代平台必须处于活跃状态 |
| `Active` / `Not yet developed` | Active / Not yet developed | 已激活 / 尚未开发 |
| `At least 4 features at level 6+` | At least 4 features at level 6 or higher | 至少 4 项功能达到 6 级或以上 |
| `2 of 4 features qualify` | 2 of 4 features qualify | 4 项中已有 2 项符合 |

"Gen" became "Generation": the abbreviation is the schema's, not the
business's.

### `funding_need.describe` was English-only

It is reached from the Decision Summary (a participant) *and* from
`advance_round` (an engine record with no request to read a language from).
It now takes `language`, defaulting to English, and the English rendering is
**byte-identical** to the sentence it built before — pinned by
`test_english_is_byte_identical_to_the_pre_crv2_12_sentence`, so the refusal
an instructor can reproduce from an engine record did not move.

---

## 3. Bilingual parity, demonstrated

Catalogue state after the pass:

| catalogue | entries | language gaps | placeholder mismatches |
|---|---:|---:|---:|
| `participant_messages.MESSAGES` | 99 | 0 | 0 |
| `participant_messages.FIELD_LABELS` | 35 | 0 | — |
| `participant_messages.ROUND_STATUS_LABELS` | 4 | 0 | — |
| `cohort_messages.MESSAGES` | 6 | 0 | 0 |
| `locales/en.json` ↔ `zh-CN.json` | 2000 keys each | 0 | 0 |

The two locale values that are identical across languages are `login.title`
and `instructor.brand`, both `GLOBALSTRAT` — a brand name, correctly not
translated.

Interpolating messages rendered in both languages (the cases where
translated strings usually break):

```
round_not_accepting     en     Round 3 is closed and no longer accepts decisions.
round_not_accepting     zh-CN  第 3 回合状态为“已关闭”，不能再提交决策。

rd_budget_exceeded      en     R&D investments of $4,200,000.00 exceed the R&D budget
                               of $3,000,000.00. Reduce investments or increase the budget.
rd_budget_exceeded      zh-CN  研发投入 $4,200,000.00 超过研发预算 $3,000,000.00。请减少投入或增加预算。

price_band_alert        en     The price of $900 for Atlas in Germany is outside this
                               round’s allowed range of $400 to $800. …
price_band_alert        zh-CN  Germany 中 Atlas 的价格 $900 超出本回合允许的价格区间 $400 至 $800。…

zero_budget_warning     en     R&D budget is set to zero. Review this before locking.
zero_budget_warning     zh-CN  研发预算 已设为零。锁定前请确认。

cash_negative           en     Projected ending cash is $-1,250,000.00. Reduce spending
                               or raise financing before locking.
cash_negative           zh-CN  预计期末现金为 $-1,250,000.00。锁定前请减少支出或增加融资。

rd_prereq_features      en     At least 4 features at level 6 or higher
rd_prereq_features      zh-CN  至少 4 项功能达到 6 级或以上

rd_prereq_features_detail  en     2 of 4 features qualify
rd_prereq_features_detail  zh-CN  4 项中已有 2 项符合
```

Note `rd_prereq_features_detail`: the Chinese reorders the two counts
(「4 项中已有 2 项符合」 — "of 4, already 2 qualify"). That reordering is
exactly why parity is asserted on the *placeholder set* and verified by
rendering, not by comparing string shape.

`test_every_message_renders_in_both_languages_with_its_values` renders all 99
messages in both languages with a sentinel per placeholder and asserts every
sentinel survives, so a value dropped by a translator fails the suite rather
than raising `KeyError` at the moment a team is already being refused.

---

## 4. The prevention control, with its failing and passing cases

`backend/scripts/check-participant-strings` — standard library only, reads
the tracked source tree, never a database or a model response. Seven
assertions: **A1** both languages present, **A2** identical placeholder sets,
**A3** no storage/model field name in a message, **A4** no participant-facing
literal bypassing the catalogue, **A5** every round status labelled, **A6**
locale key and placeholder parity, **A7** no raw scenario name interpolated.

Exit codes follow `checks/README.md`: `0` clean, `1` findings, `2` could not
run. Zero findings over zero examined units is exit 2, never a pass.

**It is not the Stage 1 `--check`.** `generate_inventory.py --check` asserts
the checked-in inventory still describes the tree — it passes happily on a
brand-new English-only refusal as long as the inventory lists it. This
asserts the property instead.

### Passing case, and the failing case, on the real tree

```
$ backend/scripts/check-participant-strings --repo .
aide-checks: check-result name=participant-string-hygiene units=2154 findings=0 suppressions=0
participant-string-hygiene: PASS 2154 unit(s) examined, 0 reviewed suppression(s)
exit=0

# plant an untranslated message that also names a storage field
$ backend/scripts/check-participant-strings --repo .
aide-checks: check-result name=participant-string-hygiene units=2155 findings=1 suppressions=0
participant-string-hygiene: FAIL 1 finding(s)
  A1 backend/core/utils/participant_messages.py:MESSAGES['crv212_plant_do_not_ship']
     has no zh-CN wording. A participant reading that language would get English or nothing.
exit=1

# remove the plant
$ backend/scripts/check-participant-strings --repo .
participant-string-hygiene: PASS 2154 unit(s) examined, 0 reviewed suppression(s)
exit=0
```

The file was restored byte-identical (`diff -q`) after the plant.

### Every assertion proved able to fail

`backend/scripts/check-participant-strings-selftest` builds a disposable tree
per case, asserts it passes, plants a violation of one assertion, asserts a
non-zero exit, and tears the tree down — the pattern `checks/selftest/run`
uses, for the reason AP-R10 gives: *a check counts only when the packet proves
it can fail.*

```
selftest: 22 ok, 0 failed
```

covering A1, A2, A3, A4, A5, A6 (missing key), A6 (placeholder skew), A7, a
stale suppression, and two could-not-run cases (a suppression with no stated
reason; a scope entry naming a file that no longer exists).

### Where it runs

- `backend/core/tests/test_player_language_guard.py` — so `manage.py test core`
  fails on it, which is the gate GSP-CRV2-09 runs.
- `.github/workflows/player-language.yml` — runs the selftest first, then the
  check.

It is deliberately **not** a vendored `aide-checks` check:
`checks/config/schema.json` sets `additionalProperties: false` on its check
set and `checks/.aide-checks-rev` pins the package, so adding one there means
forking a package whose whole design is that it is never forked.

### The check's own first run found a bug in itself

Its first run over the real tree produced 20 findings, of which **6 were
false positives in A3**: it matched placeholder *names* (`{unlock_round}`,
`{max_teams}`, `{team_size_max}`) which are substituted before anyone reads
the sentence. A3 now masks placeholders first. Four more were speculative
`allow_literals` entries in the first draft of the config — and the staleness
assertion rejected every one of them, which is why the shipped allowlist is
empty.
