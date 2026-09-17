# The three open interface defects — completion

**Branch:** `crv2-13-open-interface-defects`, cut detached from
`crv2-release-integration` at `be413f9`.
**Repair commit:** `280a762`.
**Date:** 2026-09-17.

**No gate is claimed closed.** Closure is the auditor's. V2-064 in particular
should be re-driven: the repair changed where the fix lives, not only what it
says, and the reasoning for that is below.

---

## The headline

Of the three findings the read-through verified open today, **only one was
open.** And the one that was open was *worse* than the register records it,
because the file the finding names is on a code path no student can reach.

| ID | State found at `be413f9` | What was done |
|---|---|---|
| **V2-064** | **Open, and understated.** The client half was missing, and the file it lives in is unreachable. | Built, at the point every save actually passes through. |
| **V2-105** | **Half open.** The game-naming half was already done at `1855b25`. The hardcoded pause toast was real, and reproduced in Chinese. | Pause strings catalogued; a silently-swallowed Extend failure surfaced. |
| **V2-080** | **Not open.** Zero hardcoded fallbacks in the whole frontend. | Nothing to repair. The comment that caused the false reading was reworded. |

---

## 1. V2-064 — a student's edit was still lost silently

### What was actually wrong

R17 ruled the refusal must be shown and the edit retried. The backend half was
in. The client half was not: `DecisionContext.js` still ended its autosave in
`catch (err) { console.error('Auto-save failed:', err); }`.

**But repairing that file would have fixed nothing a student can see.**
`updateDraft` is exported by `DecisionContext` and **called by no page in the
product**. So `isDirty` never becomes true, the 30-second autosave never arms,
and `saveDraft` never runs. Every decision a team actually saves goes through
its own page's `patchDecision(...)`, and eight of those pages end in
`catch { /* ignore */ }` (StrategyPage, FinancePage, RDPage, ProductsPage,
MarketStrategyPage, CorporateStrategyPage, SummaryPage, CommunicationsPage).
`MarketingPage` is the sole exception, from V2-107.

This is finding **F3's shape again** — the half that exists is not the half
that renders — and it is why the repair is not confined to the named file.

### The repair

- **`src/api/saveFailures.js`** (new) — a tiny import-free publisher. The axios
  response interceptor announces every refused *decision write*, identified by
  route and method, and keeps the refused request so a retry re-sends the
  actual edit rather than a rebuilt one.
- **`src/api/client.js`** — publishes success and failure from the one point
  all ten pages already pass through. The rejection is still re-thrown, so
  `MarketingPage`'s own V2-107 handling keeps working.
- **`src/contexts/DecisionContext.js`** — owns `saveError` and `retrySave`, and
  no longer lets `lastSaved` report a save that did not happen.
- **`src/components/DecisionSaveAlert.js`** (new) — the surface, mounted beside
  `BudgetAlert` inside the student shell so it survives navigation between
  decision screens.

**Why not `GameStatusBar`.** That component owns the Saving/Saved indicator and
would have been the obvious home. **It is exported and imported by nothing** —
it renders to nobody. It was still corrected (it must not state something
false), but it is dead code, and that is recorded below as a separate finding.

### Lifecycle conflict vs validation failure

Told apart by the **response `code`, never by the sentence** — the sentence is
participant copy and R17 ruled it must change, while the code is the contract.

| | Test | Retry | Wording |
|---|---|---|---|
| **lifecycle** | `409` **and** `code === 'lifecycle_in_progress'` | automatic, 2s/5s/10s, then a manual control | names the operator action |
| **validation** | any other refused response | **manual only** | shows the server's own sentences |
| **network** | no response at all | automatic, as lifecycle | names the connection |

Retrying a lifecycle conflict cannot double-write: the boundary refuses
*before* any handler runs — `test_competition_locks` asserts the handler's call
count is zero — so the first attempt wrote nothing. A validation refusal is not
retried on a timer because a timer will never fix an edit the server objected
to; the team must change something.

A `409` **without** the code is treated as a validation refusal, and that is
pinned by a test, so a future conflict of another kind is not retried as though
an instructor caused it.

### Wording

New `decision_save.*` block, both catalogues, no placeholders (so A2/A6 parity
is trivially satisfied):

| key | EN | zh-CN |
|---|---|---|
| `not_saved_title` | Your last change was not saved | 您的最近一次修改未能保存 |
| `lifecycle_conflict` | An instructor is changing this round right now, so nothing was saved. Your edit is still on screen and will be sent again in a moment. | 教师正在调整本回合，因此未保存任何内容。您的修改仍在屏幕上，稍后将自动重新提交。 |
| `refused` | The change was refused and nothing was saved. Correct the entries below, then try again. | 此次修改被拒绝，未保存任何内容。请更正以下条目后重试。 |
| `network_failed` | The server could not be reached, so nothing was saved. Your edit is still on screen and will be sent again in a moment. | 无法连接服务器，未保存任何内容。您的修改仍在屏幕上，稍后将自动重新提交。 |
| `retrying` | Retrying... | 正在重试... |
| `retry_now` | Retry now | 立即重试 |
| `game_status.not_saved` | Not saved | 未保存 |

Against the GSP-CRV2-12 standard: **§5** — a refusal says nothing was saved,
and these say so first, in the title; **§3** — each says what happened and what
happens next; **§1/§2** — no field name, no id, no status token; **§6** — the
server's sentences are shown, never restated, so one rule is not worded twice.

---

## 2. V2-105 — the part that was real

The game-naming half was **already done** at `1855b25`:
`instructor.extend_deadline_title` = `Extend round deadline — {{game}}` /
`延长回合截止时间 — {{game}}` existed in both catalogues and was already in use.
Confirmed on screen in the before-image, both languages.

What was real:

- **The pause toast was hardcoded English** at two sites. Reproduced: in the
  before-image the Chinese judge's toast read **`Game paused`** where the
  catalogue says **`游戏已暂停`**. Now `instructor.game_paused`, with
  `instructor.failed_pause` for the failure.
- **A refused Extend Deadline said nothing at all** — `catch { /* empty */ }`.
  The modal stayed open, `loadData()` never ran, and a judge could not tell a
  rejected change from a slow one. Now surfaced like its sibling
  `handleAdvance`, via `instructor.failed_extend_deadline`.

### A claim of mine that did not survive its own test

I initially read `createGameName || dashboard?.game_name` as naming the *wrong*
heat, and reordered it to prefer `dashboard.game_name`. **I could not reproduce
that, and on the evidence it is not reachable:** `InstructorDashboard.js:1411`
does `setCreateGameName(game.game_name)` when a section's game auto-loads, and
the create-a-game form only renders when `!gameId`. So the two values are kept
in sync, and the field a judge could type into is not on screen while a game is
selected. The reordering is **defensive hardening with no reproduced defect
behind it**; the probe written to demonstrate it was deleted rather than left
to imply evidence that does not exist.

---

## 3. V2-080 — nothing to repair

`OperatorEventsPanel.js` has **13** real `t()` calls and **zero** hardcoded
fallbacks. All 13 keys resolve in both catalogues. The whole `src` tree,
comments stripped, contains **no** `t('key', 'English')` call.

The "one remaining fallback" was **a prose comment** at line 18 that quoted the
old pattern as an example. Two review passes matched on it. The string gate
never flagged it, because the key it quotes is now catalogued and A9 only fires
on keys no catalogue answers.

Reworded to describe the shape instead of spelling out the call. **This is not
a defect repair**, and the panel was confirmed correct on screen in both
languages in the before-image, i.e. before any change of mine.

The same trap then caught me: my first draft of the new test file quoted a
translation call with a made-up key in its docstring, and the gate failed the
build on it. That is recorded in the file.

---

## 4. Evidence

Driven in a real browser, both languages, against a disposable PostgreSQL
container and the built frontend on one origin. The lifecycle lock is held by
`lock_game_for_lifecycle` from a separate process — the same call every
exclusive operator action takes — so the 409 the student receives is the
product's own refusal.

`evidence/open-interface-defects/{before,after}/browser-{en,zh-CN}.json`,
screenshots alongside, harness in `.../harness/`.

| | before | after |
|---|---|---|
| **en** | 16 passed, **4 failed** | **20 passed, 0 failed** |
| **zh-CN** | 15 passed, **5 failed** | **20 passed, 0 failed** |

The before-image is the pristine `be413f9` source; the served bundle was
checked to contain no `lifecycle_in_progress` and none of the new zh-CN
wording.

**What the before run proves.** The student's refused edit produced **one
refusal and zero retries — the edit was dropped**, nothing named the operator
action, no retry control existed, and the only thing on screen was the
backend's `This round is being processed. Refresh shortly to see the results.`
The Chinese run additionally caught the `Game paused` toast.

**Two steps in this harness are not evidence, and should not be read as such.**
`the status indicator does not claim a save` and `the edit is retried and the
notice clears` both **passed in the before-image too**, vacuously: the first
because `GameStatusBar` renders nowhere, the second because it asserts the
absence of a notice that the before-image never shows. They are retained for
the after-image, where they discriminate, but they carry no weight before.

**No visual claim is made about Chinese glyphs.** This sandbox has no CJK font,
so the zh-CN screenshots show missing-glyph boxes. Every Chinese assertion is
exact string equality against `textContent` — not `innerText`, which reflects
the design system's `text-transform` and has produced a false failure on this
programme before. Both harness records carry that disclaimer. Every expected
string was additionally diffed against the catalogues programmatically.

---

## 5. Gates

Exit codes read directly, not inferred.

| gate | result |
|---|---|
| `npm run build` | **exit 0** — "Compiled with warnings", build folder ready |
| jest | **exit 0** — 10 suites, 53 tests, all passed (7 new, from 36) |
| `check-participant-strings` | **exit 0** — 4567 units, **0 findings, 0 suppressions** |
| `check-participant-strings-selftest` | **exit 0** — 34 ok, 0 failed |
| `allow_unresolved_keys` | **still `{}`** — config untouched |

**A correction to my own verification.** I first ran the build as
`CI=true npx react-scripts build`, which turns roughly fifty *pre-existing*
ESLint warnings into errors. That fails **on the pristine `be413f9` tree too**,
so it is not this branch's doing — but I also backgrounded those runs with a
trailing `echo`, so the "exit 0" I saw was the echo's status and not the
build's. I reported a passing build twice on that basis before catching it. The
project's own gate is `npm run build` with no `CI`, and that is what the table
above records, read in the foreground.

---

## 6. Open, and handed over rather than decided

1. **R17's first consequence is still unmet.** It ruled the message *"must stop
   claiming the round is being processed"*. `participant_messages.py:211` still
   reads `This round is being processed. Refresh shortly to see the results.` /
   `本回合正在处理。请稍后刷新查看结果。`, and it is pinned by
   `test_competition_locks.py:69`. The student now reads an accurate sentence
   from the frontend catalogue instead, so the screen is correct — but the
   backend sentence is unchanged, still inaccurate for a deadline change, and
   **still reaches the screen through FinancePage's own error line** (visible in
   `after/screenshots/11-finance-refusal-shown-en.png`). Changing a pinned
   participant string is a wording decision; wording is yours.
2. **`GameStatusBar.js` is dead code.** Exported, imported nowhere. It owns the
   Saving/Saved indicator that V2-064 and the register both describe. Either it
   should be mounted or it should go; either way the register's description of
   the status bar is describing something no student sees.
3. **Eight pages still swallow their own save errors.** They are now covered
   globally, but each keeps its local behaviour — and `FinancePage`'s own
   status line is hardcoded English (`'Budget save failed'`, `'Budget saved'`)
   and is **not cleared when a retry succeeds**, so a stale refusal sentence
   can sit under a cleared notice.
4. **One sentence now lives under two keys.** `decision_save.not_saved_title`
   and `marketing.save_failed_title` are both `Your last change was not saved`
   (likewise `retry_now` / `save_failed_retry`). Deliberate, for consistency
   with V2-107 — but authoring standard §6 says a rule is worded in one place
   and imported, so you may want them unified.
5. **A long operator action exhausts the retry budget.** The lock held beyond
   ~17s uses up 2s/5s/10s and leaves the student with the manual Retry. That is
   correct behaviour — they are told, and the control is there — but it is a
   threshold nobody has ruled on.
6. **Not verified:** the eight other decision pages were not each driven in a
   browser; only the Finance screen was. The global mechanism is page-agnostic
   by construction, but that is an argument, not an observation.

---

## Register wording

Offered for you to apply — I did not edit the register.

**V2-064** — *Repaired at `280a762`, pending closure.* R17's client half is
built, and **not where the row said it was**. The row names
`DecisionContext.js:49-61`, but `updateDraft` is called by no page, so that
autosave never runs in the shipped product and a repair confined to it would
have been unreachable — F3's shape. The refusal is now caught at the axios
interceptor every decision write passes through (`api/saveFailures.js`),
surfaced by a mounted `DecisionSaveAlert` beside `BudgetAlert`, and retried by
re-sending the refused request. A lifecycle conflict is told from a validation
refusal by the response `code`, never the sentence: the former retries itself
at 2s/5s/10s (safe — the boundary refuses before any handler runs), the latter
shows the server's own sentences and offers a manual retry only. `lastSaved` no
longer reports a save that did not happen. Wording in both catalogues to
GSP-CRV2-12. Proven before/after in a browser in both languages against a real
held lifecycle lock: before, **one refusal and zero retries — the edit was
dropped**. **Two consequences remain open:** R17's requirement that the backend
message stop claiming the round is being processed is **unmet**
(`participant_messages.py:211`, pinned by `test_competition_locks.py:69`), and
`GameStatusBar.js` — the status bar this row describes — is **imported by
nothing**.

**V2-105** — *Partly stale; the live half repaired at `280a762`.* The
game-identity requirement was **already met** at `1855b25`:
`instructor.extend_deadline_title` carries `{{game}}` in both catalogues and
was confirmed on screen in both languages **before** any change here. What was
genuinely open was narrower: the pause toast was hardcoded English at two sites
— reproduced in the before-image, where a zh-CN judge's toast read `Game
paused` against a catalogue saying `游戏已暂停` — and a refused Extend Deadline
was swallowed by `catch { /* empty */ }`, leaving the modal open with no
explanation. Both repaired and catalogued. **A builder claim withdrawn:** the
`createGameName || dashboard?.game_name` ordering was reported as able to name
the wrong heat; it could not be reproduced, because `:1411` re-syncs
`createGameName` to the loaded game and the create form only renders when no
game is selected. The reordering was kept as hardening, with no defect behind
it.

**V2-080** — *Not a defect; closable with no code change.* `OperatorEventsPanel.js`
has 13 real `t()` calls, **zero** hardcoded fallbacks, and all 13 keys resolve
in both catalogues; the whole `src` tree, comments stripped, contains no
`t('key', 'English')` call. The "one remaining fallback" was **a prose comment
quoting the old pattern as an example**, which two review passes matched on and
the string gate never flagged — A9 only fires on keys no catalogue answers, and
this key is catalogued. The panel was confirmed rendering catalogued wording in
both languages in the **before**-image. The comment has been reworded to
describe the shape rather than spell out the call, so the next reader does not
re-open it. The register's "one remaining hardcoded fallback" should be struck
as a false positive rather than recorded as repaired.
