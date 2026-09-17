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
| `results_page.of_teams` | `ResultsPage.js:134` | **fixed here** |
| `topbar.over` | `TopBar.jsx:102` | pre-existing |
| `communications_page.max_words` | `CommunicationsPage.js:293` | pre-existing |
| `strategy_tools.swot_placeholder` | `StrategyToolsPage.js:807` | pre-existing |

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

**My recommendation, and it is yours to take or refuse.** Class A is three
short strings and is genuinely cheap — I would fix those next. Class B is 14
instructor-facing labels × 2 languages; the wording belongs to CRV2-08's owner
and I would not author Chinese for a panel I have not driven. Either way,
**say the word and Class A is a ten-minute change.**

All 17 are registered in `allow_unresolved_keys` with a per-key reason, pinned
to the exact key, and the checker **reports any entry that stops matching**, so
the list cannot quietly outlive the defect. That keeps the gate meaningful
today — it fails on the **next** unresolved key — without silently absorbing a
backlog it did not cause.

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
I opened both rather than trusting the DOM string: `innerText` concatenates the
AntD `Statistic` value and suffix without whitespace, so the quoted text reads
`#3of 4 teams` while the screen shows **`#3 of 4 teams`**. That is markup, not
a spacing defect — stated because the quoted string alone would look wrong.

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
> DOM, with screenshots. **Three remain open:** `topbar.over`
> (`TopBar.jsx:102`, the over-budget chip, so it shows in red at the moment a
> team overspends; the catalogue has `topbar.of` but not `topbar.over`),
> `communications_page.max_words` (`CommunicationsPage.js:293`, needs plural
> forms) and `strategy_tools.swot_placeholder` (`StrategyToolsPage.js:807`,
> every SWOT textarea placeholder). All three are registered in
> `allow_unresolved_keys` with per-key reasons and are caught the moment the
> suppression is removed. Participant- and instructor-facing; rated as a
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
