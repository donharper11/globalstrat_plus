# R48 delegated calls — items 7, 8, 9, 12 (2026-09-22)

**Branch:** `crv2-13-r48-delegated-calls`, cut from `crv2-release-integration`
at `83a50bb` (the commit that adds `INTEGRATOR_DECISIONS_UNDER_R48.md`; the
file's presence was verified before anything was touched).
**Observes:** `specs/STANDING-DISCIPLINE.md`,
`handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`, owner ruling R48
(`OWNER_RULINGS_2026-09-22.md`) and the integrator decisions under it
(`INTEGRATOR_DECISIONS_UNDER_R48.md`, items 7, 8, 9, 12). The decisions and
their reasons were taken as fixed; nothing below re-decides them.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`,
`LAUNCH_CHECKLIST_V2.md`, every `OWNER_RULINGS` file and
`INTEGRATOR_DECISIONS_UNDER_R48.md` were left untouched; §7 proposes register
text for the auditor to apply or reject.

Commits, oldest first, one per item so an interruption loses at most one:

| Commit | Item | What |
|---|---|---|
| `a3ddab5` | 7 | CJK-aware word count, one rule on each side, shared case table |
| `d86a699` | 8 | The three round-status routes removed with their views, sentences and inventories |
| `1348ca4` | 9 | The product edit control removed; create and retire kept |
| `84f2ac2` | 12 | "Compliance investment" row on the shared budget bar |
| *(next)* | — | This document |
| *(last)* | — | Regenerated string inventory, alone |

---

## 1. Item 7 — a Chinese communication is limited like an English one

**State at head (`83a50bb`).** `views/cc32a_views.py` counted a
communication's words three times as `len(content.split())` (draft save,
submit-without-draft create, submit-with-content), and refused at
`word_count > word_limit * 1.1`. `str.split()` splits on whitespace, and
Chinese is written without it, so a Chinese memo of any length counted as one
word. The student's page (`CommunicationsPage.js:57`) counted the same way
(`text.trim().split(/\s+/)`) for its live "N / limit" and its Submit guard.
The refusal sentence `communication_over_word_limit` was already bilingual.

**Red, mechanically.** The new test module against head: 8 failures, 3
errors of 9 (the errors are the missing service module). The behavioural
evidence in the failures: a 600-letter Chinese memo against a 300-word limit
was **accepted** with `word_count: 1` and went to evaluation; the mixed memo
(20 English words + 30 letters) was accepted at `word_count: 21`. The Jest
module failed to resolve `./communicationWords`.

**Change.** One rule, in one place on each side:

- `backend/core/services/communication_words.py` — `count_words(text)`:
  CJK letters (Han: U+3400–4DBF, U+4E00–9FFF, U+F900–FAFF, U+20000–2FA1F,
  々〆〇; Hiragana U+3040–309F; Katakana U+30A0–30FF, U+31F0–31FF, half-width
  U+FF66–FF9F; Hangul U+1100–11FF, U+3130–318F, U+AC00–D7AF) count at 1.5
  per word, rounded up in integers (`(letters * 2 + 2) // 3`, so one letter is
  one word and never zero); CJK punctuation and full-width symbols
  (U+3000–303F less 々〆〇, and the full-width punctuation ranges, not the
  full-width digits and letters) are separators; the rest is `str.split()`
  as before. `cc32a_views.py` calls it at all three sites.
- `frontend/globalstrat-frontend/src/communicationWords.js` —
  `countWords(text)`, the same ranges (`u`-flag regexes), the same integer
  arithmetic (`Math.floor((letters * 2 + 2) / 3)`); `CommunicationsPage.js`
  calls it for the live count. `draft_word_count` from the server is unchanged
  in shape.
- Tests: `core/tests/test_communication_word_limit.py` (9) and
  `src/communicationWords.test.js` (19) share **one table of sixteen cases,
  row for row**, so a change to either side without the other fails.

**Green.** A 600-letter Chinese memo against a 300-word limit is refused at
`count=400` in both languages; a 300-word English memo is accepted (with
`evaluate_communication` mocked) at `word_count: 300`; 450 letters are 300
words and are accepted, so the limit binds at the same point in both
languages; mixed text (20 words + 30 letters = 40 against a limit of 30) is
refused in both parts' sum; the draft route and the assignments list report
the same count; a submit that carries no body is refused on the draft's
count. `test_student_refusal_language`'s existing over-limit test
(`'word ' * 20`) still passes: English is exactly what `split()` gave.

**Boundary, stated.** Python's `str.split()` and JS `\s+` differ on a few
control characters (U+001C–001F) that no memo contains; the shared table does
not include them and the two helpers are not asserted equal over them.

## 2. Item 8 — the three round-status routes that answered 500

**State at head.** `urls.py:265-267` registered
`rounds/<int:round_id>/decision-status/` and `rounds/<int:round_id>/send-reminder/`
(`DecisionStatusView`, `SendReminderView`, `views/course.py:997-1176`) and a
third, `rounds/current/my-status/`, on the same `DecisionStatusView` in
"student mode". All three did `Round.objects.get(round_id=...)`; `Round` has
`round_id` only as a `@property` (`models/core.py:176`), so the query raises
`FieldError` and every call answers 500. The student route additionally read
`SimulationState.current_round_id`, the v1 state model. **No caller:**
`src/api` and `src/pages` contain none of `decision-status`, `send-reminder`
or `my-status` (the only `decisionStatus` in the frontend is a local
function in `GameDashboard.js` over the summary payload). No test drove the
routes; `test_operator_refusal_language` held their literals by source scan
only and said so.

**Red.** Four new tests in `test_legacy_control_removal.DeadRoundStatusRoutesAreGone`
failed at head: the three names reversed, the three paths resolved, both
views existed on `core.views` and `core.views.course`, and the sentences were
in the catalogues.

**Change.** Removed: the three `path()`s and the `urls.py` import; the
export in `views/__init__.py`; both classes in `course.py` (185 lines) with
the imports only they used (`SimulationState`, `participant_message`,
`participant_refusal`); the participant sentences only they spoke
(`round_not_found` and the eight legacy checklist labels `status_item_*`,
`status_detail_*`); the operator sentence `reminder_game_required` and its
line in the console's allowlist (`bilingualServerReason.js`, which a test
holds equal to `bilingual_codes()`); the two names in the source scan's
`CONVERTED` list and its note. **Kept:** the operator `round_not_found`
(`results_api.py:1162` speaks it). `rounds/current/my-status/` is removed
too, and this is said explicitly: it was as dead as the other two (no
frontend caller, same failing lookup, plus a dependency on the v1 state
model). A docstring in `read_inventory.py` that named `DecisionStatusView`
as the example of a substring false positive now says the view was since
removed.

**Inventories.** Regenerated with the repo's own tooling, against a dummy
unreachable database (`DB_HOST=127.0.0.1 DB_PORT=1`, never the production
host): `manage.py dump_route_inventory` — 217 → **216 mutating routes**
(`send-reminder|post` gone; `decision-status` and `my-status` were GET and
never in the mutating inventory), 38 lifecycle-mutating, 22 guarded, 16
exempt, 0 unguarded; `manage.py dump_read_inventory` —
`url_conf_route_count` 797 → **794**, 34 sensitive reads / 33 logged
unchanged (none of the three was a logged read). Both `--check` clean.
**No test pinned the route count deliberately**; the only pins are the two
checked-in JSON files, and `test_audit_integrity`'s `33` logged reads is
unchanged.

**Green.** 278 OK across the nine focused modules (§5).

## 3. Item 9 — the product edit control

**State at head.** `ProductsPage.js` rendered a pencil button
(`products_page.edit_product`) on every active product, made every active
row clickable ("Click any active product row to edit or retire it."), and
opened a modal with an editable form whose save (`handleEditSave`) sent
`product_creates: [..., {..., existing_product_id: editProduct.id}]`. The
serializer has no such field (`grep existing_product_id backend/` finds
nothing), so the server took the edit for a new product and refused it; the
page showed the refusal. A control that could never succeed.

**Red.** `ProductsPage.test.js` at head: 3 of 4 failed (the hint and the
edit path present; no retire control on the row; `existing_product_id` in
the source). The fourth — a retired product has no control — passed at head
and must.

**Change.** Removed: the pencil and its tooltip, the row `onClick` and
pointer cursor, the edit form, `editForm`, `handleEditSave` and the payload
that carried `existing_product_id`, the `faEdit`/`FontAwesomeIcon` and
`Checkbox` imports, and the four catalogue keys only they used
(`edit_product`, `click_to_edit`, `save_changes`, `base_platform`; no other
file referenced them). Kept: create (unchanged) and retire (unchanged
payload, `product-retires`). Added: a "Retire product" link on each active,
unlocked row opening the same modal, now read-only (platform, unit cost,
active markets, features) with Cancel and the two retirements; the hint
`fixed_once_created` under the table. The serializer and every rule are
untouched, as the decision requires. A first cut showed positioning in the
modal through `t(positionLabelKeys[...])`, a computed key; dropped (the row
already shows it), so the computed-key count stays at 28.

**Green.** 4 of 4; the page-adjacent suites (`sectionPayloads`,
`decisionInputLimits`) unchanged.

## 4. Item 12 — the committed compliance row

**State at head.** `budget_summary` (Summary), `budget_status` (Finance
context, and through `GameContext.refreshBudgets` the dashboard) carry
`compliance_committed` beside `platform_development_committed`, inside
`committed_total`, from which `unallocated` is computed
(`rd_costs.budget_assessment`). The three pages render the same
`components/BudgetBar.js`, which draws four allocated/spent bars (R&D,
marketing, strategy, research) and the unallocated line, and read neither
committed figure.

**Red.** `BudgetBar.test.js` at head: 4 of 6 failed (no row, no label in
either catalogue); the two negatives (no row without the figure; unallocated
untouched) passed and must.

**Change.** A `committed` list in `BudgetBar.js` — one entry,
`compliance_committed`, label `budget.compliance_committed` — rendered as a
label/amount row after the four bars and before the unallocated line, only
when the payload carries the figure (an older server draws nothing), at $0
when it is zero. **Nothing is summed on the client**: the bar has no total of
its own, `committed_total` and `unallocated` come from the server and
already include the figure, so the row is a line shown, not a figure added.
The backend side is not re-proven here: `test_compliance_investment_charge
.test_the_summary_and_finance_context_agree_with_the_refusal` already asserts
`committed_total`, `compliance_committed` and `unallocated` on both payloads
(re-run focused in §5). Label: "Compliance investment" / 合规投入, held by
the test equal to the income statement's `financial_reports.compliance_label`
so the same money is named the same way before and after lock.

**Not done, recorded.** `platform_development_committed` is on the same
payloads and is equally unrendered. The decision names the compliance row
only; a platform-development row is the same defect and the same one-line
change, proposed as a finding in §7 rather than added here.

**Green.** 6 of 6.

## 5. Commands, results, durations

All backend runs through `scripts/test-postgres` (disposable Postgres in
Docker) under `flock -w 1800 /tmp/globalstrat-backend-test.lock`; another
agent ran concurrently and the lock was always taken. The production host
(192.168.50.38) and `/etc/globalstrat-plus.env` were never read.

| # | Command | Result | Wall |
|---|---|---|---|
| 1 | Jest `src/communicationWords.test.js` at head | module not found (red) | 1 s |
| 2 | `test-postgres core.tests.test_communication_word_limit` at head | 8 F, 3 E of 9 (red) | 15 s |
| 3 | Jest `src/communicationWords.test.js` | 19 OK | 1 s |
| 4 | `test-postgres` item-7 module + `test_student_refusal_language` + the six standing labels | **209 OK**, 171 s | 3 min 1 s |
| 5 | `check-participant-strings` / selftest | PASS 5220 units / 34 ok | 2 s |
| 6 | Jest `CommunicationsPage`, `decisionSaveCatchScan` | 44 OK | 1 s |
| 7 | `test-postgres …DeadRoundStatusRoutesAreGone` at head | 4 F of 4 (red) | 4 s |
| 8 | `dump_route_inventory`, `dump_read_inventory`, both `--check` | 216 mutating; 794 routes; current | <10 s |
| 9 | `test-postgres` `test_legacy_control_removal` + `test_operator_route_ownership` + `test_student_refusal_language` + the six standing labels | **278 OK**, 171 s | 3 min 2 s |
| 10 | Jest `bilingualServerReason`, `consolePanelsLanguage` | 34 OK | 1 s |
| 11 | Jest `ProductsPage.test.js` at head | 3 F of 4 (red) | 10 s |
| 12 | Jest `ProductsPage.test.js` + `sectionPayloads` + `decisionInputLimits` | 61 OK | 2 s |
| 13 | Jest `BudgetBar.test.js` at head | 4 F of 6 (red) | 1 s |
| 14 | Jest `BudgetBar.test.js` | 6 OK | 1 s |
| 15 | `CI=true npx react-scripts test --watchAll=false` (full) | **30 suites / 325 tests OK** | 7 s |
| 16 | `CI=false BUILD_PATH=<scratch> npx react-scripts build`; `node eslint-warning-count.js` | Compiled with warnings; **55 (baseline 57)**, none in a file this branch adds; exit 0 | 35 s |
| 17 | `test-postgres test_zh_terminology test_crv2_12_language test_player_language_guard test_compliance_investment_charge` (after the last zh-CN sentence) | 42 OK | 15 s |
| 18 | **`test-postgres core --parallel 8`, once, at `84f2ac2`** | **`Ran 1519 tests in 114.033s` — OK**, exit 0 (log records branch, revision and PID) | 2 min 11 s |

`git diff --check` clean at every commit; `file` confirms every touched file
kept its line endings (LF throughout). No runtime code changed after #18
began.

**Not in the budget table because they are not release-scale:** no
concurrency matrix, replay, load, soak or browser archive was run; none of
the four items touches a hashed section, the lifecycle boundary or the
engine (`communication_words` is a view-time count stored on
`TeamCommunication.word_count`, which is not in the envelope).

## 6. zh-CN — new sentences

Backend: none added; ten removed with the dead routes (§2), all of them
unreachable at head.

Frontend, both catalogues, no computed key:

| Key | en | zh-CN |
|---|---|---|
| `budget.compliance_committed` | Compliance investment | 合规投入 (the income statement's existing term) |
| `products_page.retire_product` | Retire product | 退役产品 (the page's existing term for retire) |
| `products_page.fixed_once_created` | Products are fixed once created. Retire an active product to remove it from the portfolio. | 产品创建后不可更改。如需将活跃产品移出产品组合，请将其退役。 |

`test_zh_terminology` passes over them (no retired term). The
`fixed_once_created` sentence is new wording and has not been read by a
native speaker.

## 7. Proposed register text (for the auditor to apply or reject)

**Row "Word limit never binds for Chinese"** (status cell):
> **Repaired, pending closure** at `a3ddab5` under R48 item 7. One rule on
> each side (`services/communication_words.count_words`,
> `src/communicationWords.countWords`): CJK letters at 1.5 per word, rounded
> up in integers, added to the space-split count; both tests share one table
> of cases. A 600-letter memo against a 300-word limit is refused at 400 in
> both languages; English counts exactly as before. Not observed in a browser.

**Row "`rounds/<id>/decision-status/` and `rounds/<id>/send-reminder/` answer 500"**:
> **Removed** at `d86a699` under R48 item 8, with `rounds/current/my-status/`
> (same view, same failing lookup, no caller), their views, the ten sentences
> only they spoke, and one console allowlist entry. Route inventory 217 → 216
> mutating; read inventory 797 → 794 routes, 33 logged reads unchanged.

**Row "Editing an existing product"**:
> **Repaired, pending closure** at `1348ca4` under R48 item 9: products are
> fixed once created. The edit control, the row click, the form and the dead
> `existing_product_id` client code are gone; a "Retire product" link opens
> the retire modal; create and retire payloads unchanged; serializer and rules
> untouched. Jest: an existing product renders without an edit control. Not
> observed in a browser.

**Row "Summary/Finance rows for committed compliance spend"**:
> **Repaired, pending closure** at `84f2ac2` under R48 item 12. A
> "Compliance investment" / 合规投入 row on the shared `BudgetBar` (Summary,
> Finance, dashboard), read from `compliance_committed`, drawn only when the
> payload carries it; nothing summed on the client, `committed_total` and
> `unallocated` already include it. Not observed in a browser.

**New finding, proposed:**
> | Platform development committed before lock has no row | **Open, P2.** `platform_development_committed` is on the same three payloads as `compliance_committed` and is rendered nowhere; the same defect item 12 repaired for compliance, and the same one-entry change in `BudgetBar.js`'s `committed` list. Not added under item 12, whose decision names the compliance row only. |

## 8. What a reviewer should distrust

Only what genuinely needs the owner, the production host, a browser, or a
native speaker:

1. **No browser.** Four screens changed (communications count, products row
   and modal, budget bar on three pages); each is asserted through Jest
   against the real components with i18n stubbed to keys, not clicked. The
   next gate under R48 is the walkthrough, which is where they get clicked.
2. **`products_page.fixed_once_created`** (zh-CN) is new wording; the other
   two zh-CN labels reuse terms already in the catalogues. Native-speaker
   read pending.
3. **The 1.5-letters-per-word constant and the letter ranges** are the
   integrator's call and are implemented as stated; whether 1.5 is the right
   ratio for the assignments' authored limits is calibration, deferred by R48
   §2, and not decided here.
