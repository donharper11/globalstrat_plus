# V2-104 (assignment refusal) and V2-094 (analyst price)

**Branch:** `crv2-13-assignment-refusal-and-analyst-price`, cut from
`crv2-release-integration` at `79db2bf`.
**Commits:** `f4fcc68` (V2-094), `40ea30d` (V2-104), `140d811` (string
inventory re-cut), plus the commit that adds this report.

> **Development-grade focused evidence from a moving branch. NOT release
> certification.** **No gate is closed by this document** and the register and
> launch checklist were not edited; the proposed register text is in §8.
> No full suite was run, by instruction.

---

## 1. What was found at head, before anything was touched

### V2-104 — mostly already repaired, and not where the register says it is open

The register row and the 2026-09-17 read-through both describe
`InstructorDashboard.js:1955` showing ``message.success(`${userIds.length}
student(s) assigned`)`` with no inspection of `errors`. **That is not the code
at head.** Commit `1855b25` (2026-09-15, "CRV2-13: frontend defect repairs
F1-F7", item F4) already made the two add-to-team call sites read
`res.data.errors`, raise a `Modal.warning` with the server's wording, and
added `instructor.assign_partial` / `assign_none` / `assign_failed` in both
languages. `git merge-base --is-ancestor 1855b25 HEAD` is true. The register
row was never updated, which is the process finding the read-through itself
records.

The repair was inline in a 2,265-line component and **had no test**. Three
things were still wrong inside the finding's scope:

1. **The third caller still discarded the response.** `assignStudents()` has
   three call sites, all in `InstructorDashboard.js`. The one that *removes* a
   student from a team (`team_id: null`) ignored the body, and announced a
   transport failure as the hard-coded English `'Failed to unassign'`.
2. **The success toast could still overstate.** `count: done || userIds.length`
   fell back to the number *requested* when the server confirmed none.
3. **Three of the four per-item refusals were English-only and named storage
   fields** — `Missing user_id.`, `No active enrollment for user_id=41.`,
   `Team 7 not found.` Only the cap refusal was written for an instructor.
   The middle one is reachable in a two-operator heat (a student removed while
   another operator's roster is open), and it lands in the same list the cap
   refusal does.

### V2-094 — open, exactly as registered

`AskAnalystTab` in `pages/MarketResearchPage.js` fetched
`research/queries/`, whose payload carried no price, and rendered an unpriced
"Ask" button. `MAX_QUERIES = 5` was hard-coded. One thing the register does not
say: the sentence `market_research.price_per_query` was authored in **both**
languages at `c87395c` and never wired to anything.

### Callers of `PUT /api/team-management/` (the status-code decision)

Built from `core/urls.py:263` outward, then a tree-wide search for the path.

| Caller | Reads `errors`? |
|---|---|
| `InstructorDashboard.js` multi-select add | yes (since `1855b25`) |
| `InstructorDashboard.js` single add (→ team button) | yes (since `1855b25`) |
| `InstructorDashboard.js` remove from team | **no — repaired here** |
| `api/instructor.js` `renameTeam` | different action; 400/404 on failure already |
| `core/tests/test_cohort_caps.py` | reads the body, never asserted the status |
| `evidence/.../harness/instructor_walkthrough.py` | reads the body text of the 200 |
| `evidence/decision-rules/harness/{stage1_probes,probe_run}.py` | record status + body |

**Decision: the status stays 200 and the client reads `errors`.** The endpoint
is a batch, and a batch can be partly refused; no single status describes
"two seated, one refused", so every caller has to read the list whatever the
status is. Returning 4xx only for the wholly-refused case would give callers
two shapes to handle instead of one, would route the cap's wording through
axios's rejection path (where the dashboard's `catch` shows a generic
sentence), and would change what the archived walkthrough harnesses recorded.
The residual risk of a 200 — a future caller that forgets `errors` — is what
the source guard in §3 is for. **A reviewer who prefers 409 for the
wholly-refused case is not wrong**; it is a judgment, and it is one line in
`_handle_assign` plus one branch in `assignmentOutcome.js`.

---

## 2. V2-094 — what changed

No route was added. **The route inventory and the sensitive-read inventory are
unchanged, and their counts were not touched**; both freshness guards were run
and pass (§5). `ResearchQueriesListView` names no decision or audit model in
its source, so it stays outside the sensitive-read set.

- `core/services/research_catalogue.py` — `max_analyst_queries(scenario)` and
  `analyst_offer(scenario, queries_used)`. The price is `price_for()`, the one
  calculator the charge, the funding rule and the engine already read.
- `core/views/cc15_views.py` — `research/queries/` gains
  `analyst_query: {price, max_queries_per_round, queries_remaining}`. The quota
  counts the **current** round's questions whichever round is being viewed,
  because that is the count the charge refuses on.
- `core/rag/views.py` — the charge reads the quota through
  `max_analyst_queries()` instead of its own inline `get_config(..., 5, int)`,
  so the quota shown and the quota enforced are one expression.
- `pages/MarketResearchPage.js` — the tab shows
  `market_research.price_per_query` with the server's figure, puts the figure
  on the button (the `ReportPaywall` pattern), reads the quota from the server,
  and calls `refreshBudgets()` after a charged question as the paywall does.
  **If the server did not name a price the tab does not sell**: the input and
  button are disabled and `market_research.price_unavailable` is shown. An
  unpriced Ask button after a failed fetch would be the same defect again.
  `AskAnalystTab` became a named export so it can be tested.
- Locales — one new key, `market_research.price_unavailable`, EN and zh-CN.

## 3. V2-104 — what changed

- `pages/assignmentOutcome.js` (new) — `assignmentOutcome(data)` classifies a
  response as `assigned` / `partial` / `refused` / `unconfirmed` from what the
  **server wrote**, and `announceAssignment()` tells the instructor. The
  refusal sentences are the server's, verbatim, in the language the server
  resolved.
- `pages/InstructorDashboard.js` — all three call sites go through it. The
  remove path uses `mode: 'unassign'`; `'Failed to unassign'` is gone.
- `pages/assignmentCallSites.test.js` — a source guard: the number of
  `await assignStudents(` must equal the number passed through
  `announceAssignment(assignmentOutcome(...))`. A fourth call site that
  discards the response fails the build.
- `core/utils/cohort_messages.py` + `core/views/course.py` — the three
  remaining refusals are catalogue entries in both languages and name no
  storage field. `cohort_messages.py` is inside `check-participant-strings`'
  catalogue scope, so A1–A3 now hold for them.
- Locales — `instructor.assign_unconfirmed`, `unassign_none`,
  `unassign_failed`, EN and zh-CN.
- The cap (`team_capacity_error`, V2-042) was not touched; the existing cap
  tests pass unchanged.

---

## 4. Red, then green

| # | Test | Red (before the change) | Green |
|---|---|---|---|
| 1 | `core.tests.test_paid_research.AnalystQueryPriceTests` (3) | `FAILED (errors=3)` — `KeyError: 'analyst_query'` ×3, 17.8 s wall | `Ran 3 tests … OK`, 11.1 s |
| 2 | `src/pages/MarketResearchPage.analyst.test.js` (5) | `Tests: 5 failed, 5 total` — e.g. `Unable to find an element with the text: /market_research\.price_per_query.*\$12,345/`, 8 s. Run with **only** `export` added to the component, so the failures are about behaviour, not a missing import. | `Tests: 5 passed`, 3 s |
| 3 | `test_cohort_caps…test_every_other_refusal_is_localised_and_names_no_storage_field` | `FAILED (failures=5)` of 6 sub-tests — `'user_id' unexpectedly found in 'No active enrollment for user_id=987654321.'`, `False != True : Team 987654321 not found.`, 11 s | OK (in the 80-test run below) |
| 4 | `src/pages/assignmentCallSites.test.js` (2) | `Expected: 3 / Received: 0`; `Expected pattern: not /Failed to unassign/` | passed |
| 5 | `src/pages/assignmentOutcome.test.js` (9) | `Cannot find module './assignmentOutcome'` | passed |

**Distrust row 5's red.** It is red only because the module did not exist; it
pins the classification but proves nothing about head. Row 4 is the test that
is red on head's actual behaviour. **Three of the new backend tests were never
red** and are labelled as contract pins in the source:
`test_a_wholly_refused_batch_says_nothing_was_written`,
`test_a_partly_refused_batch_reports_both_halves`,
`test_the_cap_refusal_is_localised_for_a_zh_instructor`. They pass at head
because the server was already correct; they exist because the client's
reading now depends on exactly those shapes.

## 5. Commands, results, durations

Backend, all via
`cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`
(disposable `postgres:16-alpine`; the production database and
`/etc/globalstrat-plus.env` were never read):

| Labels | Result | Wall |
|---|---|---|
| `core.tests.test_cohort_caps core.tests.test_paid_research core.tests.test_player_language_guard core.tests.test_crv2_12_language core.tests.test_audit_integrity.SensitiveReadInventoryTests core.tests.test_operator_concurrency.RouteCoverageTests` | `Ran 80 tests in 19.2s — OK` | 30 s |
| `core.tests.test_engine.TestRAGInfrastructure core.tests.test_engine.TestArticleIngestion` (`rag/views.py` was edited) | `Ran 16 tests — OK` | 12 s |

Frontend, in `frontend/globalstrat-frontend` (`npm ci`, 6 s, node 22.17.1):

| Command | Result |
|---|---|
| `CI=true npx react-scripts test --watchAll=false` | 13 suites, 69 tests, all passed, 6 s |
| `python3 backend/scripts/check-participant-strings` | `PASS 4579 unit(s) examined, 0 reviewed suppression(s)`; 27 computed keys not resolved (its standing blind spot) |
| `python3 backend/scripts/check-participant-strings-selftest` | `34 ok, 0 failed` |
| `react-scripts build` (to a scratch `BUILD_PATH`) + `node eslint-warning-count.js` | build exit 0, 34 s; `eslint warnings: 55 (baseline 57)` |
| `generate_inventory.py --check` | stale after the change → re-cut at `140d811` (2,234 → 2,260 rows, every changed row in a file these commits touched) → `--check` clean |

The ESLint baseline file says 57 and the build reports 55. I did not lower it:
I did not measure head, so I cannot say the two are mine, and it is a shared
file.

## 6. New defects found — recorded, NOT repaired

**N1 (P1 candidate). The analyst query cannot be bought from the interface at
all.** `MarketResearchPage.js` posts `{ query_text: … }`;
`ResearchQueryView.post` reads `request.data.get('query')`. A throwaway probe
against the disposable database (not committed) sent the frontend's exact body
with `rag_enabled` on: **`400 {'error': 'Query text is required.'}`, zero
purchase rows.** So at head a student pressing Ask is refused before any
charge, in English, with a sentence that is false (they typed a question). No
backend test posts to this route, which is how it survived. This changes how
V2-094 should be read: the charge-without-price was real **through the API**
(where the register's author drove it) and unreachable through the UI.
I did **not** repair it: it is outside both findings, and the one-line fix
turns on a per-question charge in the student interface that has never
actually been live — that is an owner decision, not a builder's. The price
disclosure in this branch is correct either way, and must land **before or
with** any fix to N1, never after. My backend test posts `query`, the key the
server reads; my Jest test deliberately does not assert the request body.

**N2 (P2 candidate). `under_minimum` is computed and never shown.**
`_handle_assign` returns it and its comment says "The console shows it"; no
frontend source reads `under_minimum`. R12's 3-member minimum is therefore
advisory with nobody advised. V2-042 territory, not repaired.

**N3 (observation). The rest of `InstructorDashboard.js` still announces in
hard-coded English** — `'Failed to create game'`, `'Game activated — Round 1
is open'`, `'Round schedule saved'`, and more: a grep counts 42 `message.*` calls opening on an English literal. A9
does not see them because they are not `t()` calls at all. Out of scope;
related to the owner's ruling that operator tooling is bilingual.

**N4 (observation). Two analyst refusals are English-only**: `Query limit
reached (5 per round).` (429) and `Research system unavailable: <exception
text>` (503, which also leaks an exception string to a student). Not repaired.

## 7. Not verified

- **Nothing was observed in a browser.** The V2-104 register row's own caveat —
  the toast was read from source, never seen — is still true of the repair.
  Jest renders `AskAnalystTab` for real; the dashboard's three call sites are
  covered by unit tests of the shared function plus a source guard, **not** by
  rendering `InstructorDashboard`.
- The zh-CN sentences I authored (four frontend keys, three backend messages)
  were written by me and not reviewed by a native reader.
- With N1 open, "student sees the price, then is charged that price" cannot be
  walked end to end in the UI. It is proven at the API
  (`test_the_price_shown_is_the_price_charged`) and at the component.
- No full backend suite, by instruction. Not run: load, walkthrough, replay.
- Auditor preflight, applicable items: inventory started from `urls.py` (yes);
  alternate entry point — `POST /api/users/<id>/assign-team/` also writes
  membership and is capped (`test_the_user_route_respects_the_same_cap`), it
  answers with a real 4xx and no frontend source calls it;
  negative tests prove no write (the refused student's `team_id` is asserted
  `None`, and reading the price is asserted to create no purchase row).

## 8. Proposed register text (for the auditor to apply or reject)

**V2-104** — append to the status cell, and make it the first sentence:

> **Repaired, pending closure — and the row above was stale when written
> down as open.** The success-toast defect was repaired at `1855b25`
> (2026-09-15, F4) for both add-to-team call sites; the read-through of
> 2026-09-17 still listed it as not started. `40ea30d` finishes it: the third
> `assignStudents()` caller (remove from team) no longer discards the
> response or fails in hard-coded English; the toast counts what the server
> wrote, never what was requested; the three non-cap refusals are bilingual
> `cohort_messages` entries naming no storage field; one shared reading
> (`assignmentOutcome.js`) with a source guard against a call site discarding
> the response again. **Status stays 200 by decision** — a batch can be partly
> refused — with the contract pinned in `test_cohort_caps`. V2-042 untouched.
> **Still unobserved on screen.** New, separate: `under_minimum` is returned
> and never displayed. Evidence:
> `completion/ASSIGNMENT_REFUSAL_AND_ANALYST_PRICE_2026-09-21.md`.

**V2-094** — append, first sentence:

> **Repaired, pending closure.** `f4fcc68`: `research/queries/` publishes
> `analyst_query {price, max_queries_per_round, queries_remaining}` from
> `price_for()`; the tab shows the price in a sentence and on the button, reads
> the quota from the server (the `MAX_QUERIES = 5` note above is closed by the
> same change), and does not sell when no price was published. No route added;
> both inventories unchanged. **Read with the new finding below: the UI could
> never reach the charge** — the tab posts `query_text`, the view reads
> `query`, and every question from the interface is refused 400 before any
> purchase row is written. The undisclosed charge was reachable through the
> API only.

**New row proposed (N1)** — P1 candidate, "Paid research / participant
interface": *the analyst query cannot be asked from the interface; request-key
mismatch `query_text` vs `query`; refused 400 in English with a false
sentence; no charge occurs. Fix is one line but switches on a per-question
charge that has never been live in the UI — needs an owner ruling, and must
not land before `f4fcc68`.*
