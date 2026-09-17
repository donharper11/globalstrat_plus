# R35 — the demoted team is told on its own results screen

**Ruling:** R35, competition owner, 2026-09-17. **Finding:** V2-119, the
sub-question R34's completion report left explicitly open and unimplemented.

**Implemented on** `crv2-11-demotion-team-notice`, branched from
`crv2-release-integration` at `1e990cf` (which already carries R32 at `0ab1864`
and R34 at `a275010`).

**One thing the integrator needs to know.** While this was being built,
`crv2-release-integration` advanced to `209ccf9`, *"Record owner ruling R35: the
demoted team is told on its own screen"* — the commit that writes R35 into
`OWNER_RULINGS_2026-09-17.md`. **This branch does not contain it**, because it
was cut from `1e990cf` as instructed, so the copy of the rulings file here still
ends at R34. I built from the ruling as stated in the build instruction and then
checked my work against the recorded text at `209ccf9`: it matches point for
point — surface the demotion alongside the price-band adjustments, state the
rule and what it means, EN and zh-CN, no column, code or internal identifier,
the static participant-string gate passing, and ranking, payload and the v6
envelope all unmoved. Merging this branch will need that commit alongside it;
I did not edit any `OWNER_RULINGS_*` file.

> **Development-grade focused evidence from a moving branch. NOT release
> certification.** One environment, one round, one scenario, four firms. **No
> gate is closed by this document** — the owner audits behind it. GSP-CRV2-09
> owns the full suite and the four-environment matrix; neither was run.

---

## 1. What the ruling asked for, and what was built

R32 moved the commercial-inactivity rule onto the standings: a firm that sold
nothing is placed below every firm that competed, whatever its score, so a team
can hold a **higher** performance index than the team above it and still finish
below it. R34 made that firing visible in stored data as a `DecisionAuditEvent`
and CRV2-08's instructor drill-down already surfaces it.

**The team itself was not told.** `core/views/results_api.py`'s
`RoundResultsView` filtered audit events with an explicit `action__in` over the
three price-band actions, so a demoted team read its own standing with no
explanation. R35: **the demoted team is told on its own results screen.**

### The three pieces

| Where | What |
|---|---|
| `core/utils/participant_messages.py` | Two new catalogue keys, EN + zh-CN |
| `core/engine/leaderboard.py::demotion_notice` | Chooses the key and renders it **from the stored payload** |
| `core/views/results_api.py::RoundResultsView` | New `inactivity_notices` key beside `price_adjustments` |
| `components/InactivityDemotionNotice.js` | Renders the server's sentence on `ResultsPage` and `GameDashboard` |

**No model change, no migration, no engine behaviour change.** The ranking
decision, the classification and the audit payload are all exactly as R32 and
R34 merged them; this surfaces a record that already existed.

---

## 2. The wording, and why it meets the standard

Rendered **from the stored audit payload**, exactly as
`core/services/price_band.py::adjustment_notice` is, and deliberately placed in
the same module as `demotion_audit_payload` so the record and its rendering are
read, reviewed and changed together. The sentence the team reads and the row an
instructor produces in a dispute are therefore **the same fact**, not two
computations that can drift.

### `inactivity_demotion_outscored` — the firm lost places

> **EN:** Your firm sold nothing in round {round}, so it did not compete this
> round. A firm that does not compete is placed below every firm that did,
> whatever its score — so your firm was ranked {rank} in this round's standings
> with a performance index of {index}, below firms whose index was lower than
> yours. The index itself was not reduced; only the placing. Sell in at least
> one market next round to be ranked on your score again.

> **zh-CN:** 第 {round} 回合贵公司没有任何销售，因此本回合未参与竞争。未参与竞争的
> 公司无论得分高低，都会排在所有参与竞争的公司之后——因此贵公司本回合排名第 {rank}
> 位，绩效指数为 {index}，低于绩效指数不及贵公司的其他公司。绩效指数本身并未被扣减，
> 受影响的只是排名。下一回合请至少在一个市场实现销售，即可重新按得分排名。

### `inactivity_demotion` — the firm would have finished last anyway

> **EN:** Your firm sold nothing in round {round}, so it did not compete this
> round. A firm that does not compete is placed below every firm that did,
> whatever its score — so your firm was ranked {rank} in this round's standings,
> carrying a performance index of {index}. The index itself was not reduced;
> only the placing. Sell in at least one market next round to be ranked on your
> score again.

> **zh-CN:** 第 {round} 回合贵公司没有任何销售，因此本回合未参与竞争。未参与竞争的
> 公司无论得分高低，都会排在所有参与竞争的公司之后——因此贵公司本回合排名第 {rank}
> 位，绩效指数为 {index}。绩效指数本身并未被扣减，受影响的只是排名。下一回合请至少
> 在一个市场实现销售，即可重新按得分排名。

### Why two keys rather than one

R34's payload is deliberately honest about what the guard cost:
`outscored_a_firm_ranked_above` is **false** when the firm would have finished
last regardless. A single sentence claiming "below firms whose index was lower
than yours" would then assert an inversion that did not happen — the record
would say one thing and the screen another. The second key states the rule and
the firing **without** claiming a lost place. Which key applies is decided in
`demotion_notice`, beside the payload that decides it, so no surface can
describe the rule differently by picking a different sentence.

### Against GSP-CRV2-12's standard

- **Names the business object, never the column.** "performance index", not
  `performance_index`; "standings", not `LeaderboardEntry`.
- **No internal id, no action code, no rule identifier.** Asserted, not
  asserted-by-eye: `test_it_names_no_action_code_column_or_internal_id` checks
  both languages against `inactivity_rank_demotion`,
  `inactivity.ranked_below_every_active_firm`, `commercially_inactive`,
  `performance_index`, `team_id`, `lowest_active_performance_index`,
  `DecisionAuditEvent` and `LeaderboardEntry`.
- **States the rule AND what to do next** — "Sell in at least one market next
  round to be ranked on your score again."
- **Says the index itself was not reduced.** This is R32's whole point: the
  standing moved, the carried score did not. A team told only "you were placed
  last" would reasonably read it as a scoring penalty, which is precisely the
  control R32 removed.
- **Worded in one place and imported**, never restated on the client: the
  React component passes the server's sentence straight through.
- **A rival firm is not named.** The payload carries
  `lowest_active_team_name` so a dispute can be answered; the team's own screen
  does not republish another firm's score.

`./backend/scripts/check-participant-strings` — **PASS, 2189 units, 0 findings,
0 suppressions.** `backend/core/engine/leaderboard.py` was added to the check's
declared scope with a stated reason, because a participant-facing renderer now
lives there; widening the scope is a deliberate, reviewable edit in that config,
which is how the file says it must be done.

---

## 3. Where it is rendered, and the proof it reaches the screen

The history mattered here: **F3** recorded that the price-adjustment notice had
no screen a student could reach, and the repairs merged 2026-09-15. That is a
defect class where the API is right and nothing renders it, so this was
**driven, not assumed**.

Rendered by `InactivityDemotionNotice` on **both** surfaces the price-band
notice uses — `ResultsPage` (the routed results screen) and `GameDashboard`
(the landing screen a team actually arrives on after a round resolves).

### The round had to be constructed

The guard has **never fired in stored play** (448 index rows, worst
`index_change` −5.82), so a browser pass over any recorded round would
photograph the *absence* of the notice and call it a pass.
`evidence/r35-demotion-team-notice/harness/seed_r35.py` constructs the firing
and **asserts** it — it exits non-zero naming what was missing rather than
resolving a round that proves nothing, the discipline
`r34_inactivity_fixture.py` established. It did exactly that on its first run:
it refused a round because my own assertion compared the held-out firm's rank
against *all* other firms rather than against the firms that **competed**. The
fixture was wrong, the product was right, and the assertion was corrected.

**The resolved round (game 1, round 1, `R35 Demotion Heat`):**

| Rank | Team | Index | Revenue | Demoted |
|---:|---|---:|---:|---|
| 1 | Zenith Hardware | 53.24 | 1,440,000.00 | |
| 2 | Helix Digital | 52.05 | 908,320.00 | |
| **3** | **Lumen Devices** | **89.96** | **0.00** | **yes — outscored both firms above it** |
| 4 | Vertex Electronics | 48.69 | 0.00 | yes — outscored nobody |

The round exercises **both wording variants**: Lumen outscored every firm ranked
above it by ~37 index points and still finished third; Vertex sold nothing and
would have finished last regardless.

### What the browser actually showed

Real Chromium via Python `playwright`, against the built bundle served on one
origin with `/api` proxied (CRV2-08's `serve_app.py`), backend under
`GLOBALSTRAT_ENV=production`.

| Check | EN | zh-CN |
|---|---|---|
| The demoted team signs in | pass | pass |
| Results API carries the notice | pass (1 notice) | pass (1 notice) |
| `/games/1/teams/4/results` renders heading **and** server sentence | **pass** | **pass** |
| `/games/1/teams/4/results/1` renders heading **and** server sentence | **pass** | **pass** |
| Landing dashboard renders it too | **pass** | **pass** |
| Sentence quoted back out of the live DOM | **pass** | **pass** |
| Steps passed / failed | **6 / 0** | **6 / 0** |
| Network errors ≥400 | **0** | **0** |

Screenshots: `evidence/r35-demotion-team-notice/screenshots/` — `40-results…`
(both routes, both languages) and `41-dashboard…`. I opened the captures rather
than only parsing the DOM: the notice renders as an Ant Design warning alert
above the tabs, and the leaderboard immediately beneath it shows the inversion
it explains — Lumen Devices, index 89.96, at rank 3, beneath 53.24 and 52.05.

**Console errors: 12 per run, all `net::ERR_FAILED` on `fonts.googleapis.com` /
`fonts.gstatic.com`, and all mine** — the harness aborts those requests
deliberately because they are unreachable from this sandbox and a pending font
request stops the page settling. No product console error, and zero network
errors at or above 400 in either language.

---

## 4. The leakage test

This change widens what `RoundResultsView` reads out of the audit table, so the
Stage 5 blast-radius property was re-asserted rather than assumed.
`RoundResultsView` declares no permission class of its own; what refuses a rival
is `TeamScopeGuardMiddleware`.

`DemotionNoticesDoNotLeakAcrossTeams` puts **both** teams under the guard so
there is genuinely something to leak, then asserts:

- a team sees exactly one notice, its own, and the rival's name appears nowhere
  in the response body;
- a rival's student gets **403** — the status code asserted explicitly, because
  a bare "the rival did not see it" would also pass on a 500 and prove nothing
  about the guard;
- the owning team's student gets **200** through the same guard, so the 403 is
  about team scope and the test is not vacuous.

**Confirmed again at production grain** against the running stack, over HTTP
(`evidence/r35-demotion-team-notice/cross-team-refusal.txt`):

| Request | Result |
|---|---|
| Rival student → demoted team's results | **403** `{"detail": "You do not have access to this team."}` |
| Demoted team's own student → its own results | 200, **1** notice |
| Rival reading **its own** results (it competed) | 200, key **present**, **0** notices |
| The other demoted firm reading its own | 200, 1 notice, `outscored=false`, **2 price adjustments alongside it**, and the sentence claims no lost place |

That last row also proves **coexistence at production grain**: one team
carrying both a price-band receipt and a demotion receipt returns both, neither
filter catching the other's rows.

---

## 5. What must not change, and did not

| | |
|---|---|
| `MANIFEST_SCHEMA_VERSION` | **6** — file untouched by this diff |
| `dump_manifest_schema --check` | **"Manifest schema inventory is current."** (exit 0) |
| Manifest on the resolved firing round | `schema_version` **6** |
| Migrations added | **none** — no model changed |
| `core/tests/test_inactivity_rank_guard.py` (R32) | **14 tests pass, file unmodified** |
| `core/tests/test_inactivity_demotion_audit.py` (R34) | **18 tests pass, file unmodified** |
| Ranking behaviour (R32) | untouched — no edit to the sort key, the shared-rank comparison or the classification |
| Audit payload (R34) | untouched — `demotion_audit_payload` is read, never rewritten |
| `git diff --check` | clean |

Neither protected test module appears in `git diff --name-only`. The envelope
did not need to move for the reason R34 records: audit events sit outside the
hashed output, so rendering one to a screen costs no envelope bump.

---

## 6. Commands, counts, durations

Focused tests via `backend/scripts/test-postgres`, each in its **own disposable
`postgres:16-alpine` container**, under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`. The browser stack used a
**separate** disposable container (`gsp-r35-pg`, PostgreSQL 16, credential from
`openssl rand -hex 32`, written only to a scratchpad file at mode 600, bound to
`127.0.0.1` on an ephemeral port, removed afterwards). The production database
at `192.168.50.38` was **never contacted** and **no systemd environment file was
read** — no harness script contains that host at all.

| # | Command | Result | Duration |
|---|---|---|---|
| 1 | `test-postgres rank_guard + demotion_audit + price_band --parallel 8` — **pre-change baseline** | **77 tests, OK** | 32.3s |
| 2 | `check-participant-strings` — baseline | PASS, 2185 units, 0 findings | 0.12s |
| 3 | jest `react-scripts test --watchAll=false` — baseline | 7 suites, **33 tests**, OK | 5.8s |
| 4 | `test-postgres core.tests.test_demotion_team_notice --parallel 8` — **against the unmodified tree** | 22 tests, **14 failures + 3 errors** (intended red) | 21s |
| 5 | `test-postgres` × 4 labels `--parallel 8` — after the change | **99 tests, OK** | 32s |
| 6 | `check-participant-strings` — after | **PASS, 2189 units, 0 findings, 0 suppressions** | 0.12s |
| 7 | jest — after | 8 suites, **36 tests**, OK | 3.0s |
| 8 | `npm run build` (Node 22.17.1) | **exit 0**, compiled with warnings | ~90s |
| 9 | disposable PG + `migrate` + `load_scenario` | OK, scenario id 1 | 24s |
| 10 | `dump_manifest_schema --check` | **"inventory is current."** (exit 0) | <1s |
| 11 | `seed_r35.py` (seed, close, resolve, assert the firing) | **guard fired**, inversion real, `schema_version` 6 | ~20s |
| 12 | `start_stack_r35.py` (gunicorn + one-origin app server) | fixture identity confirmed | ~10s |
| 13 | `browser_r35.py en` | **6 passed / 0 failed**, 0 network errors | 28s |
| 14 | `browser_r35.py zh-CN` | **6 passed / 0 failed**, 0 network errors | 26s |
| 15 | `leak_probe.py` (production-grain refusal) | rival **403**, owner 200 | <1s |
| 16 | `git diff --check` | clean | — |
| 17 | `test-postgres` × 4 labels `--parallel 8` — **after the commit, clean tree** | **99 tests, OK** | 32s |
| 18 | `check-participant-strings` and jest — after the commit | PASS 2189 units; 8 suites, 36 tests | 3s |

Baselines (1, 2, 3) were taken **before** any edit and the red run (4) before
the implementation existed, so every later result is attributable. Runs 17 and
18 were taken **after** the commit against a clean working tree, so the green
result anchors to the frozen commit rather than to an uncommitted tree.

The pre-commit hook ran and passed at commit `7b134a0`: `aide-checks` revision
**`77b8ced`**, matching `checks/.aide-checks-rev`; 2 checks ran
(`no-agent-worktrees-tracked`, `no-committed-secrets`), **0 blocking failures**,
0 could-not-run. **No `--no-verify` was used and none was needed.**

Host: Ubuntu 22.04.5 LTS, Python 3.10.12, PostgreSQL 16 in Docker, Node 22.17.1,
Chromium 151.0.7922.34. `node_modules` was **symlinked read-only** from the main
checkout; nothing was installed and the main checkout was not modified.

---

## 7. A defect I found and did **not** fix

**`results_page.of_teams` reaches a participant as a raw translation key.**
Visible in every screenshot above: the Leaderboard Position tile reads
**"#3 results_page.of_teams"** in English *and* in Chinese.

`ResultsPage.js:134` calls `t("results_page.of_teams", { count: rankings.length })`
and the key exists in **neither** locale catalogue, so i18next renders the key
itself. It is **pre-existing and not mine** — the reference dates to the baseline
snapshot `111d541`, and my diff to `ResultsPage.js` is three lines that add the
demotion notice. `check-participant-strings` A6 passes because it compares the
two catalogues against *each other*, and a key missing from **both** is
symmetric; that is a real gap in the check, not a false negative it should have
caught.

Untouched because it is outside this ruling. Rated as a wording defect on a
participant screen — the CRV2-12 class — for the register owner to file.

---

## 8. What I could NOT verify

- **One environment, one round, one scenario, four firms, round 1.** Same host,
  OS, Python, timezone and locale. No cross-environment reproduction.
  **GSP-CRV2-09 owns the four-environment matrix; this is not a substitute.**
- **No full backend suite** — GSP-CRV2-09 owns it. Four focused labels only.
- **The constructed firing is not a natural one.** The held-out firm's carried
  index was set by the fixture to force the inversion. The mechanism, the
  payload and the rendered sentence are real; the specific numbers are
  engineered. (Vertex Electronics' demotion, by contrast, arose on its own.)
- **The two notices were never photographed on one screen.** Lumen had its
  marketing rows stripped, so it has no price-band receipt, and the screenshots
  show the demotion notice alone. Coexistence is proven by
  `ThePriceBandNoticesAreUnchanged` and by the production-grain probe of Vertex
  (2 price adjustments + 1 demotion notice on one response), **not** by a
  capture.
- **The non-inversion wording was never photographed either** — it is proven by
  focused test and by the production-grain read of Vertex's own results, not on
  screen.
- **No instructor-side re-verification.** R34 proved the drill-down surfaces the
  event; I did not re-drive it, and this change touches no instructor surface.
- **The zh-CN rendering depends on the header the client sends.** The page's own
  fetch sent `Accept-Language: zh-CN` and the screen is wholly Chinese apart
  from the pre-existing key leak above and team names, which are authored by
  teams and have no translated counterpart.
- **No replay/determinism re-run.** None is owed: no hashed section changed and
  `MANIFEST_SCHEMA_VERSION` did not move. R34's replay evidence stands for the
  audit row itself.
- **No load, concurrency or accessibility testing**, and no mobile widths.

---

## 9. Proposed register wording for V2-119 — **not applied**

I did not edit `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md` or any
`OWNER_RULINGS_*` file.

> **R35 (2026-09-17) ruled and implemented — V2-119's user-facing remainder.**
> R32 and R34 answered the finding's two recorded questions; this is the
> remainder the owner named, and on the ruling's own disposition **V2-119
> becomes closable by the auditor once this lands. I claim no closure.**
> R34's completion report recorded that the *team-facing*
> `RoundResultsView` filtered audit events to the three price-band actions, so a
> demoted team read its own standing with no explanation, and left whether the
> team should be told as a rules-owner question. R35 answered it: **the demoted
> team is told on its own results screen.** `RoundResultsView` now returns an
> `inactivity_notices` list beside `price_adjustments`, rendered **from the
> stored R34 audit payload** by `leaderboard.py::demotion_notice` — placed
> beside `demotion_audit_payload` so the sentence a team reads and the row an
> instructor produces in a dispute are the same fact rather than two
> computations that can drift. Wording is bilingual (EN + zh-CN) in
> `participant_messages.py`, names no column, action code or internal id
> (asserted in both languages), states the rule, states that **the index itself
> was not reduced — only the placing**, and says what to do next. **Two keys, on
> R34's own honesty field:** a firm whose `outscored_a_firm_ranked_above` is
> false is told the rule and the firing but is **not** told it lost a place it
> never held. **Rendered on screen, driven not assumed** — the F3 defect class
> was "the API is right and nothing renders it", so a round in which the guard
> actually fires was constructed (it has never fired in 448 stored rounds) and
> driven in real Chromium: the notice appears on both results routes **and** the
> landing dashboard, in **both languages**, quoted back out of the live DOM,
> 6/6 steps and 0 network errors per language, with screenshots. **Cross-team
> leakage re-asserted** because this widens what the endpoint reads from the
> audit table: a rival's student gets **403** from `TeamScopeGuardMiddleware`
> (status asserted explicitly), the owning student 200 through the same guard,
> and a team that competed gets the key **present and empty** rather than
> missing — confirmed again at production grain over HTTP. **Nothing else
> moved:** ranking behaviour (R32) and the audit payload (R34) are untouched, no
> model changed, no migration, `MANIFEST_SCHEMA_VERSION` is still **6** and
> `dump_manifest_schema --check` is clean, and R32's 14 tests and R34's 18 tests
> pass **unmodified**. Tests: `core/tests/test_demotion_team_notice.py`, 22
> tests, red against the unmodified tree (14 failures + 3 errors); merged
> regression 99 tests OK; `check-participant-strings` PASS 2189 units.
> Evidence: `completion/R35_DEMOTION_TEAM_NOTICE_2026-09-17.md`,
> `evidence/r35-demotion-team-notice/`. **Separate pre-existing defect found and
> not fixed:** `results_page.of_teams` reaches participants as a raw translation
> key on the results screen in both languages (`ResultsPage.js:134`; the key is
> absent from both catalogues, which is why the A6 parity check does not catch
> it). **Development-grade, single-environment evidence. No gate closed.**
