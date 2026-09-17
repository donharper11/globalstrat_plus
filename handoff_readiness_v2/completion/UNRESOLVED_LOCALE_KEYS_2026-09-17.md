# `results_page.of_teams`, and the gap in the check that hid it

**Follows:** R35 (merged at `f8c4b47`) and the defect its completion report
raised but did not fix. **Branch:** `crv2-13-unresolved-locale-keys`, cut from
`crv2-release-integration` at `f8c4b47`.

> **Development-grade focused evidence from a moving branch. NOT release
> certification.** **No gate is closed by this document** — the owner audits
> behind it.

Two pieces of work: the string, and the reason the gate did not catch it. The
second is the larger half.

---

## 1. The count, before anything beyond `of_teams` was touched

The new assertion found **18** `t()` keys the catalogues cannot answer. One is
`of_teams`, which I fixed. **17 are pre-existing and I did not fix them** — the
owner asked for the number first, and this is the number.

They are not one defect. They split into two classes that fail differently:

**Class A — the raw key reaches a user (4, of which 1 is fixed here).**
No fallback, so i18next renders the key itself, in every language.

| Key | Call site | State |
|---|---|---|
| `results_page.of_teams` | `ResultsPage.js:134` | **fixed** — part 1 |
| `topbar.over` | `TopBar.jsx:102` | **fixed** — part 2 |
| `communications_page.max_words` | `CommunicationsPage.js:293` | **fixed** — part 2 |
| `strategy_tools.swot_placeholder` | `StrategyToolsPage.js:807` | **fixed** — part 2 |

`topbar.over` is the sharpest of the three: it renders in the **over-budget**
chip, in red, at the moment a team has overspent. The catalogue holds
`topbar.of` but not `topbar.over`.

**Class B — a hard-coded English fallback (14, all pre-existing).**
Every one is `instructor.*` in CRV2-08's operator-events work:
`OperatorEventsPanel.js` (12) and `InstructorDashboard.js` (2), written as
`t('instructor.actor', 'Actor')`. English renders correctly, so nothing looks
broken — and **a Chinese instructor reads English**. The catalogue has been
bypassed, which is the defect A4 forbids on the backend; this is its frontend
twin. Labels like "Actor", "Action", "Outcome", "Reason", "Request ID",
"Time (server)", "Operator Log", "Supply Chain".

**Class A's remaining three were subsequently authorised and are fixed in part
2 below.** Class B's 14 are untouched: the wording belongs to CRV2-08's owner
and is with them as a scope decision.

The suppression list is therefore now **14**, all `instructor.*`. Every entry
carries a per-key reason, is pinned to the exact key, and the checker **reports
any entry that stops matching**, so the list cannot quietly outlive its defect —
it has already shrunk from 17 to 14 by exactly the three keys part 2 fixed.
That keeps the gate meaningful today — it fails on the **next** unresolved key —
without silently absorbing a backlog it did not cause.

---

## 2. The string

`ResultsPage.js:134` calls `t("results_page.of_teams", { count: rankings.length })`.
The key was in neither catalogue, so the Leaderboard Position tile read
**`#3 results_page.of_teams`** in English *and* Chinese.

Authored the way i18next expects for a counted value. i18next is **25.10.5**,
which selects by CLDR category:

| Catalogue | Keys |
|---|---|
| `en.json` | `of_teams_one` = "of {{count}} team", `of_teams_other` = "of {{count}} teams" |
| `zh-CN.json` | `of_teams_other` = "共 {{count}} 支队伍" |

**Chinese supplies `_other` alone, and that is complete, not short.**
`Intl.PluralRules('zh-CN').resolvedOptions().pluralCategories` is `["other"]`;
English is `["one","other"]`. This is exactly the trap the coordinator's
counter-hypothesis probed from the other side, and it had a second edge: the
**existing** A6 compares raw keys between catalogues, so authoring `_one` in
English alone would have made a correct Chinese catalogue look like it was
missing a key. A6 had to be taught plurals before this string could be fixed
properly — see §3.

### Proved on screen, both languages

The defect was found by reading a rendered screen, so the fix is proved the
same way — same harness as R35, against a seeded stack in real Chromium.

| Assertion | EN | zh-CN |
|---|---|---|
| Raw key `results_page.of_teams` gone from the page | **pass** | **pass** |
| Tile reads the authored sentence | **pass** — `of 4 teams` | **pass** — `共 4 支队伍` |
| R35's demotion notice still renders beside it | **pass** | **pass** |
| Tile quoted from the DOM | `LEADERBOARD POSITION #3 of 4 teams` | `排行榜位置 #3 共 4 支队伍` |
| Steps passed / failed | **5 / 0** | **5 / 0** |
| Network errors ≥400 | 0 | 0 |

Screenshots: `evidence/unresolved-locale-keys/screenshots/50-results-of-teams-{en,zh-CN}.png`.
I opened the English capture rather than trusting the DOM string: `innerText`
concatenates the AntD `Statistic` value and suffix without whitespace, so the
quoted text reads `#3of 4 teams` while the screen shows **`#3 of 4 teams`**.
That is markup, not a spacing defect — stated because the quoted string alone
would look wrong.

> **Correction, and it applies to every zh-CN capture in this document and in
> the R35 completion report.** This sandbox has **no CJK font installed**
> (`fc-list`: 32 families, none CJK), so Chinese renders in the screenshots as
> missing-glyph boxes. **The English screens are visually confirmed; the
> Chinese ones are not.** The Chinese evidence is exact string equality against
> the *rendered DOM* — `inner_text('body')`, and for the SWOT case the textarea
> `placeholder` attribute compared verbatim to the authored sentence with its
> interpolation resolved. That is strong evidence the right string reached the
> page, and it is **not** evidence about glyphs. I earlier said I had opened
> the Chinese screenshot and seen it render correctly; that over-claimed the
> pixels and is corrected here.

The third assertion is deliberate: a fix that quietly breaks the neighbouring
feature is not a fix, so each run re-proves R35's notice on the same screen.

---

## 3. The gap that hid it — the larger half

**A6 could not have caught this, by construction.** It compares the two
catalogues *against each other*. A key missing from **both** is symmetric, so
A6 stayed green while the key rendered on screen in both languages. That is not
a bug in A6; it is a question A6 does not ask.

Three changes to `backend/scripts/check-participant-strings`:

**A8 — every `t()` key the frontend calls exists in the catalogues.** A key
called with no fallback, or with an options object and no fallback, renders as
itself. Reported with the file, the line and the key.

**A9 — no `t()` call carries a hard-coded fallback string instead.** The A4
defect, on the frontend: the wording lives in the component, English looks
fine, every other language renders that same English.

**A6 taught plurals.** Plural forms are collapsed onto their base key before
the catalogues are compared, so `of_teams_one`/`of_teams_other` is one logical
key; and each language is then asked, separately, for exactly the CLDR
categories *it* needs. Without this, the correct fix in §2 would have failed
the check.

### It knows what it cannot see, and says so

A key computed at run time — `t(variable)` or a template literal — cannot be
resolved by reading the source. The checker counts them and **prints the count
on every run** (`note 26 computed t() key(s) are decided at run time and were
not resolved`) rather than guessing or dropping them silently. 26 of 2242
references, in 97 files.

### Proved it can fail — twice, two different ways

**On a fixture**, by extending the selftest, which grew from 22 to **32 ok, 0
failed**. Five new plants: A8, A9, a plural missing its `one` form, an
unreasoned suppression (exit 2), and a stale suppression. Two false-positive
guards are asserted by the `clean tree passes` half of *every* case, which is
the stronger form — if either were flagged, no case in the file could reach its
plant:

- `t('summary.teams', { count: 3 })` resolving through `_one`/`_other` with
  **zh-CN holding only `_other`**;
- `t(labelKey)`, a computed key, not guessed at.

**On the real repository**, which is the assertion that matters: put
`results_page.of_teams` back exactly as it shipped and the check must fail
naming it.

```
1. the tree as it stands, with the fix     -> exit 0
     PASS 4432 unit(s) examined, 17 reviewed suppression(s)
2. with the shipped defect put back        -> exit 1
     A8 frontend/globalstrat-frontend/src/pages/ResultsPage.js:134 calls
     t('results_page.of_teams'), which is in no catalogue. i18next renders
     the key itself, so a user reads 'results_page.of_teams' on screen in
     every language.
```

Transcript: `evidence/unresolved-locale-keys/a8-catches-the-shipped-defect.txt`.
It runs against a temporary **copy** of the tree via `--repo`, so the working
tree is never mutated — restoring by `git checkout` would have been wrong here,
because the fix is not committed at that point.

---

## 3a. Part 2 — the remaining three Class A strings

Authorised after the count in §1 was reported. Fixed on the same branch so the
whole thing lands as one reviewed change.

### The two questions asked directly

**Does the suppression list go 17 → 14?** **Yes.** Exactly the three fixed keys
were removed; the remaining 14 are all `instructor.*` Class B. The list shrank
rather than becoming a parking lot, and `allow_unresolved_keys_source` now
records the shrink history so a future reader can see it must keep shrinking.

**Was any of the three a wrong-key call site rather than a missing string?**
**No — all three are genuinely missing strings.** This was checked rather than
assumed, and `topbar.over` is the one that looked most like a rename:

> `topbar.of` **is already in use, correctly**, at `TopBar.jsx:86` —
> `R{currentRound} {t('topbar.of')} {totalRounds}`, rendering "R2 of 4" in
> English and "R2 / 4" in Chinese. It is the round counter, not the budget
> chip. Line 102 appends a *different* marker after
> `Budget $spent/$available` when `over_budget` is true. Renaming the call to
> `topbar.of` would have rendered "Budget $60.0M/$5.0M of" — so a rename would
> indeed have been the wrong fix, and the intent was a new string.

### The wording

| Key | EN | zh-CN |
|---|---|---|
| `topbar.over` | `over budget` | `超出预算` |
| `communications_page.max_words` | `_one` "Maximum {{count}} word", `_other` "Maximum {{count}} words" | `_other` `最多 {{count}} 字` |
| `strategy_tools.swot_placeholder` | `List your {{quadrant}} here, one per line.` | `在此列出贵公司的{{quadrant}}，每行一项。` |
| `strategy_tools.swot_strengths` … `_threats` | Strengths / Weaknesses / Opportunities / Threats | 优势 / 劣势 / 机会 / 威胁 |

`max_words` is authored as real CLDR plural forms, not a padded catalogue:
English supplies `one` and `other`, Simplified Chinese supplies `other` alone,
which is complete for a language that does not inflect. A6's plural handling
passes it on that basis.

### Why the SWOT fix is five keys, not one

**The placeholder interpolates the quadrant label**, and those four labels were
missing too, so fixing `swot_placeholder` alone would have rendered
*"List your strategy_tools.swot_strengths here, one per line."* — trading one
raw key for another. The four labels are `SWOT_LABEL_KEYS[key]` resolved
through `t(SWOT_LABEL_KEYS[key])`, a **computed key**, which is precisely the
blind spot §3 records: **A8 cannot see them, and never could.** They were found
by going to drive the screen, not by the checker. That is the honest reading of
this fix — the assertion caught three of these four defects, and the fourth was
caught by the browser.

### Driven on screen — all three, both languages

One fixture serves all three screens: round 2 open (the communication
assignment is a `ROUND_MILESTONE` at round 2), a round-2 submission spending
$60.0M against a $5.0M formula budget (the chip renders only when
`budget_status.over_budget` is true), and SWOT reachable at any round. Every
precondition is asserted by the seed, so a screen that silently failed to show
the thing under test could not photograph a pass.

| Assertion | EN | zh-CN |
|---|---|---|
| `topbar.over` raw key absent / chip reads the sentence | **pass** — `Budget $60.0M/$5.0M over budget` | **pass** — `预算 $60.0M/$5.0M 超出预算` |
| `max_words` raw key absent / tag reads the sentence | **pass** — `Maximum 300 words` | **pass** — `最多 300 字` |
| SWOT: no `strategy_tools.swot*` key on screen | **pass** | **pass** |
| SWOT: all four quadrant labels render | **pass** | **pass** |
| SWOT: placeholder reads the sentence with the quadrant | **pass** — `List your strengths here, one per line.` | **pass** — `在此列出贵公司的优势，每行一项。` |
| Steps passed / failed | **8 / 0** | **8 / 0** |
| Network errors ≥400 | 0 | 0 |

Screenshots `60-topbar-over-budget-*`, `61-communications-word-limit-*`,
`62-swot-placeholder-*`. The English top-bar capture also shows the dashboard
banner *"Over budget by $55.0M — total spending $60.0M exceeds available budget
$5.0M"*, which was already correct and is unrelated to this fix. **The zh-CN
captures render CJK as boxes** — see the correction in §2; the Chinese proof is
DOM string equality, including the placeholder attribute compared verbatim.

### A new finding this turned up — 34 more keys, hidden the same way

Driving the SWOT screen showed the computed-key blind spot is not theoretical.
Enumerating literals that look like keys and sit in a real namespace but never
appear inside a `t('literal')` call finds **34 more missing keys**, none of
which A8 can see:

| Namespace | Count | What it is |
|---|---:|---|
| `strategy_tools` | **18** | the rest of the Strategy Tools page — Porter's five forces (5), PESTLE (6), entry-matrix column labels (7) |
| `common` | **11** | `StatusBadge` labels — developing, retired, distress, mainstream, premium, ultra_premium, open, pending, processed, operational, budget_tier |
| `login` | **5** | the demo team labels on the login page |

`common.*` is the widest: `StatusBadge` is used across many pages. **Not
fixed** — that is another "many, not a handful", and the same scope decision
belongs to the owner. Inventory:
`evidence/unresolved-locale-keys/keys-hidden-behind-label-maps.txt`.

**A8 could be extended to resolve module-level label maps** (`const X = { a:
'ns.key' }` consumed as `t(X[k])`), which would catch all 34. I did not do it
here: it would add 34 findings at once and that is the owner's call, not mine.
Say the word and it is a contained change to the checker plus a reasoned
suppression entry per key.

### Incidental, seen while driving and not fixed

On the Chinese communications screen the audience tag renders **"Board of
Directors"** in English. It is `audience_display`, a Django
`get_..._display()` value from `cc32a_views.py`, so the enum label is
English-only server-side. Same bilingual-parity class as Class B, different
mechanism, outside this change.

---

## 4. Constraints

| | |
|---|---|
| `check-participant-strings` | **PASS**, 4432 units, 0 findings, 17 reviewed suppressions |
| `check-participant-strings-selftest` | **32 ok, 0 failed** (was 22) |
| `test_inactivity_rank_guard.py` (R32) | **passes unmodified** |
| `test_inactivity_demotion_audit.py` (R34) | **passes unmodified** |
| `test_demotion_team_notice.py` (R35) | **passes unmodified** |
| Ranking, payload, envelope | **untouched** — no backend behaviour changed at all |
| `MANIFEST_SCHEMA_VERSION` | **6**, file not in the diff |
| Migrations | none |
| Register / checklist / `OWNER_RULINGS_*` | **not edited** |

The three protected modules ran together: **54 tests, OK**. No backend source
file was modified by this change — only the checker, its config, its selftest,
and the two locale catalogues.

---

## 5. Commands, counts, durations

| # | Command | Result | Duration |
|---|---|---|---|
| 1 | `check-participant-strings` — baseline on this branch | PASS, 2189 units | 0.1s |
| 2 | `check-participant-strings-selftest` — baseline | **22 ok, 0 failed** | 3s |
| 3 | frontend `t()` scan (97 files) | 2242 refs, 1873 distinct keys, **26 computed**, 0 `<Trans>`, 15 defaultValue | <1s |
| 4 | classify the 18 unresolved by call shape | **4 raw-key leaks, 14 defaultValue** | <1s |
| 5 | `Intl.PluralRules` categories | en `["one","other"]`, zh-CN `["other"]` | <1s |
| 6 | `check-participant-strings-selftest` — extended | **32 ok, 0 failed** | 4s |
| 7 | `check-participant-strings` — real tree | **PASS, 4432 units, 17 suppressions**, 26 computed noted | 0.4s |
| 8 | regression proof on a copy of the real tree | exit 0 → **exit 1 naming A8/of_teams** → exit 0 | 2s |
| 9 | `test-postgres` × 3 protected modules `--parallel 8` | **54 tests, OK** | 30s |
| 10 | jest | 8 suites, **36 tests**, OK | 4s |
| 11 | `npm run build` | **exit 0** | ~90s |
| 12 | disposable PG + migrate + load_scenario + seed | guard fired, 4 teams | ~50s |
| 13 | `browser_of_teams.py en` | **5 passed / 0 failed**, 0 network errors | 12s |
| 14 | `browser_of_teams.py zh-CN` | **5 passed / 0 failed**, 0 network errors | 13s |

**Part 2 — the remaining three Class A strings:**

| # | Command | Result | Duration |
|---|---|---|---|
| 15 | inventory of keys hidden behind label maps / template literals | **38 missing**, of which 4 were the SWOT labels this change authored → **34 remain** | <1s |
| 16 | `check-participant-strings` — three fixed, suppressions 17 → 14 | **PASS, 4439 units, 0 findings, 14 suppressions** | 0.4s |
| 17 | `check-participant-strings-selftest` | **32 ok, 0 failed** | 4s |
| 18 | `npm run build` with the seven new strings | **exit 0** | ~90s |
| 19 | disposable PG + migrate + load_scenario + Class A seed (round 2 open, over budget, assignment triggered) | every precondition **asserted** | ~60s |
| 20 | `browser_classA.py en` — all three screens | **8 passed / 0 failed**, 0 network errors | ~20s |
| 21 | `browser_classA.py zh-CN` — all three screens | **8 passed / 0 failed**, 0 network errors | ~20s |
| 22 | `test-postgres` × 3 protected modules `--parallel 8` | **54 tests, OK** | 30s |
| 23 | jest after the locale additions | 8 suites, **36 tests**, OK | 3s |

The seed's first run **failed and refused to continue**: `advance_round` calls
`process_round`, which will not run while any team is unlocked, so the fixture
raised `RoundNotReadyError` rather than producing a half-built round. Fixed by
closing the round before advancing, which is what locks and defaults every
team's submission.

Own disposable `postgres:16-alpine` container under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`; the production database at
`192.168.50.38` was **never contacted** and no systemd environment file was
read. `node_modules` symlinked read-only from the main checkout; nothing
installed, main checkout not modified.

---

## 6. What I could NOT verify

- **A8 sees only statically-written keys.** 26 computed `t()` calls are outside
  it, by construction. The count is printed on every run so the blind spot is
  visible, but a key broken behind `t(variable)` would still ship.
- **The scan is regex-based, not a JS parse.** A `t(` call split across lines
  with the key on the second line would be missed. Nothing in this tree is
  written that way today, but the check does not prove that it never will be.
- **`<Trans i18nKey>` is not scanned** — there are zero uses today, so the
  assertion would examine nothing and I did not add an unexercised branch.
- **I did not drive the three other Class A screens.** `topbar.over`,
  `communications_page.max_words` and `strategy_tools.swot_placeholder` are
  reported from the source and from the checker, not from a screenshot.
- **Class B's 14 keys were not seen rendered.** That English renders and
  Chinese does not is read from the call shape and i18next's documented
  `t(key, defaultValue)` behaviour, not from the operator panel on screen.
- **One environment, one scenario, one round, four teams.** No full backend
  suite — GSP-CRV2-09 owns it.

---

## 7. Proposed register wording — **not applied**

I judge these **two separate findings**: one is a broken string, the other is a
gate that could not see it. Fixing the first would not have found the rest.

### Finding 1 — unresolved `t()` keys reach users as raw key text

> **Four frontend keys are called but exist in neither locale catalogue, so
> i18next renders the key itself in both languages.** Found 2026-09-17 while
> auditing the R35 results screen, where the Leaderboard Position tile read
> `#3 results_page.of_teams`. `results_page.of_teams` (`ResultsPage.js:134`)
> is **fixed** — authored as i18next plural forms, `_one`/`_other` in English
> and `_other` alone in Simplified Chinese, which CLDR makes complete rather
> than short — and proved on screen in both languages, quoted from the live
> DOM, with screenshots. **The other three are now fixed too**, authorised
> after the count was reported: `topbar.over` (`TopBar.jsx:102`, the
> over-budget chip, which renders in red at the moment a team overspends —
> **not** a wrong-key call site, because `topbar.of` is legitimately in use at
> `TopBar.jsx:86` for the round counter and renaming to it would have rendered
> "Budget $60.0M/$5.0M of"), `communications_page.max_words`
> (`CommunicationsPage.js:293`, authored as CLDR plural forms: English
> `one`/`other`, Simplified Chinese `other` alone) and
> `strategy_tools.swot_placeholder` (`StrategyToolsPage.js:807`) — **which
> required four further keys**, `swot_strengths`/`_weaknesses`/
> `_opportunities`/`_threats`, because the placeholder interpolates the
> quadrant label and those were missing too, so fixing the placeholder alone
> would have traded one raw key for another. All three were **driven on screen
> in both languages** (8/8 assertions each, 0 network errors). The suppression
> list shrank **17 → 14**, exactly the three fixed keys, leaving only Class B.
> **A further 34 missing keys were found while doing this**, hidden behind
> label maps and template literals where A8 cannot see them — 18 more in
> `strategy_tools` (Porter's forces, PESTLE, entry matrix), 11 in `common`
> (`StatusBadge`, used across many pages) and 5 in `login`. **Not fixed**, and
> listed in `evidence/unresolved-locale-keys/keys-hidden-behind-label-maps.txt`.
> Participant- and instructor-facing; rated as a
> wording defect on a live screen, per GSP-CRV2-12's standard. **Separately, 14
> `instructor.*` keys in CRV2-08's `OperatorEventsPanel.js` and
> `InstructorDashboard.js` hard-code their English as a `t()` defaultValue:
> English is correct and a Chinese instructor reads English.** That is the
> bilingual-parity half and belongs to CRV2-08's owner. Evidence:
> `completion/UNRESOLVED_LOCALE_KEYS_2026-09-17.md`,
> `evidence/unresolved-locale-keys/`.

### Finding 2 — the participant-string gate could not see a key missing from both catalogues

> **`check-participant-strings` A6 compared the two locale catalogues against
> each other, so a key absent from BOTH was symmetric and invisible to it.**
> `results_page.of_teams` shipped and rendered as its own name on the results
> screen in both languages with the check green throughout — the gate was not
> bypassed, it was never asked the question. **Closed 2026-09-17** by three
> changes: **A8** fails when a `t()` key the frontend calls is in no catalogue;
> **A9** fails when a call carries a hard-coded fallback string instead (A4's
> frontend twin); and **A6 was taught plurals** — forms are collapsed onto
> their base key before comparison and each language is then asked for exactly
> the CLDR categories it needs, without which the correct fix to finding 1
> would itself have failed the check. Proved two ways: the selftest grew from
> **22 to 32 ok / 0 failed** with plants for A8, A9, a missing plural category
> and both suppression failure modes, plus two false-positive guards asserted
> by every clean-tree run (plural resolution with zh-CN holding only `_other`,
> and a computed `t(variable)` key); and **on the real repository**, where
> restoring the shipped defect makes the check exit 1 naming
> `ResultsPage.js:134` and passing again when restored. The check **states its
> blind spot on every run** — 26 computed keys it cannot resolve. Scope: 2242
> references across 97 files, 4432 units, 17 reviewed suppressions carrying the
> pre-existing backlog, each pinned to an exact key and reported if it stops
> matching. **Development-grade evidence. No gate closed.**
