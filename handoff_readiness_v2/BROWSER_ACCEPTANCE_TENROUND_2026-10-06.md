# Gate 1 browser acceptance on the candidate — ten rounds, 2026-10-06/07

**Supersedes `BROWSER_WALKTHROUGH_CANDIDATE_2026-10-06.md`** (rounds 1–3),
whose rounds 2 and 3 measured a fixture defect rather than the product. That
report's own instruction — *set each round's deadline relative to the open,
through the console's own controls* — is what this run does, in every round.

**Candidate:** `a0631e5d` on `crv2-release-integration`, clean tree apart from
the untracked evidence directory.
**Stack:** disposable PostgreSQL in Docker (`globalstrat_walk_10r`, loopback,
ephemeral port), the candidate worktree's own built frontend —
`main.81b42bcc.js`, the asset hash the 2026-10-05 Gate 1 build log records —
gunicorn with `GLOBALSTRAT_ENV=production` and `GIT_REVISION=a0631e5d…`, every
LLM URL pointed at an unreachable port so Phase 2 and the memo evaluation take
their fallbacks. **Production was not touched:** it served `:8002` from the
pinned `f0cf` worktree throughout, and this run's database is a container.

**Evidence:** `evidence/gate1-browser-2026-10-06-tenround/` with `SHA256SUMS`.
Screenshots are off by the W-CE4 budget ruling; every screen is still visited,
named, leak-scanned, and its API calls recorded.

## The verdict

**A full ten-round game was played and finished from the console with no
operator reopening a round and no database edit.** Nine rounds resolved on the
**first attempt** of the path chosen for them — six through the round console,
one through *Close & process now*, one through the lifecycle card's *Advance
Round* — and round 10 was ended with *Finish game*. There were **zero**
processing refusals and **zero** reopens.

That is the W-CE4 auditor's verdict reversed. Theirs was: *"No — a full game
cannot be played start to finish with no intervention. Four of ten rounds
refused to score until an operator reopened them and edited a team's
financing, and one needed a database change."*

| round | resolved | console language | playing teams that locked themselves | instructor steps failed |
|---:|---|---|---:|---:|
| 1 | console | en | 4 of 4 | 0 |
| 2 | console | **zh-CN** | 3 of 4 | 0 |
| 3 | console | en | 3 of 4 | 0 |
| 4 | **force** | **zh-CN** | 2 of 4 | 0 |
| 5 | console | **zh-CN** | 4 of 4 | 0 |
| 6 | console | en | 4 of 4 | 0 |
| 7 | **lifecycle** | **zh-CN** | 4 of 4 | 0 |
| 8 | console | **zh-CN** | 3 of 4 | 0 |
| 9 | console | en | 4 of 4 | 0 |
| 10 | **finish game** | en | **4 of 4** | 0 |

**Round 10 ended the game from the console.** The card offered *Finish game*
in place of *Advance* once the open round was the scenario's last — 0 advance
buttons, 1 finish button — the control walkthrough 3 could never reach. The
game reports itself `completed`, and afterwards round 1's results, the last
round's results, the leaderboard and the financial reports are **all still
readable**. Round 10 processed `FULLY_COMPLETE` with its narrative generated,
and all four playing teams had locked themselves before the close.

The final standings read as the game was played: the four teams that played
every screen on top (68.23, 59.03, 55.86, 50.15), the two that only ever
submitted from the Decision Summary beneath them, and the two that never
submitted last, each marked *"Did not compete"*.

**84 of 84 cross-checks pass in every round.** Opening cash equals the previous
round's closing cash; opening + OCF + ICF + FCF equals closing; gross profit
equals revenue − COGS; the printed income statement adds up with $0.00 in no
served field; net income equals operating income − interest − tax; the
performance index on a team's results equals the leaderboard's. Across the
whole game the worst residual on any identity, for any team, in any round, is
**$0.00**.

The leaderboard is checked against the rule it actually follows, which took a
correction: the first version asserted a flat ordering by performance index and
reported round 8 as a failure, because Titan Micro was ranked sixth on an index
of **47.66**, above two teams on 26.77 and 19.83. The product was right. R32
ranks a commercially inactive firm below every firm that competed, and
W-CE3-15's repair prints the reason on the row — *"Did not compete"*. The check
now asserts the three things that must hold: firms that competed are ordered by
index, every inactive firm ranks below every firm that competed, and each one
carries its reason. Rounds 1–8 were re-judged under the corrected rule and all
pass; the as-run records are kept beside them in
`records/as-run-before-leaderboard-recheck/`.

## Round 9 is the one worth reading twice

Round 9 is where the previous walkthrough's worst defect would have appeared,
and the repair held in the open.

The equity pre-flight — the check the console does not have — found Eclipse
Gadgets holding an equity raise of **$11,466,246.71** against a funding
shortfall of **$11,366,246.71**: $100,000 too much, which is the W-CE4-02
shape that used to make a round every team had locked refuse to score with
**nothing shown on the console**. This time the team could not lock in the
first place, and its own Decision Summary said why, with both figures:

> Eclipse Gadgets: equity raise of $11,466,246.71 exceeds the funding shortfall
> of $11,366,246.71 (eligible uses $7,400,000.00 less available funding …)

The raise was resized from the Finance page to the shortfall it finances, the
team locked, and the round processed on the first attempt. One team action,
prompted by the product's own sentence — not an operator intervention and not
a database edit.

## The Simplified-Chinese path

One team played **every decision screen of every round entirely in Simplified
Chinese**, and the instructor console was driven in Chinese for five of the ten
rounds. Across ten rounds that player passed **206 steps and failed 18**, over
**346 screens**, and every one of the 18 is accounted for in the next section.

Refusals reach that player in Chinese. Three examples read off its own screens:

> 现金不足。此次切换会使承诺支出达到 $16,000,000，而可用现金为 $-13,820,117。
>
> 购买细分市场报告需 $50,000.00，将使承诺支出达到 $16,050,000.00，而可用现金为
> $-13,820,116.91。购买前请减少承诺支出或增加融资。
>
> 本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。

**What the Chinese path did not pass is the content behind those screens**, and
that is this pass's largest finding: 155 player-facing strings in the
competition scenario had no Chinese at all, and three views served authored
content out of JSON blobs unlocalised while localising every field beside
them. See V2-145 and V2-146 in `V2_FINDINGS_REGISTER.md`; both are repaired on
`fix/bilingual-coverage`.

## 145 failed steps, every one accounted for

Not one of them is an unexplained product defect, and five of them *are* the
two product findings.

| n | step | what it is |
|---:|---|---|
| 33 | `summary: lock offered after the required decisions` | `student_play` drives the edge cases and deliberately leaves rows incomplete; the later drivers finish them the way a student would. |
| 29 | `research: report bought and delivered` | the product **correctly refuses** a $50,000 report to an over-committed team, naming both figures and the remedy, in the reader's language. |
| 27 | `lock offered after the required decisions` | two per round are teams 5 and 6, which never open a decision screen: the lock validator refuses them and names both missing requirements. The rest are a repair creating the next blocker — see the harness section. |
| 24 | `dashboard tab N opens` | the new every-tab sweep could not open the eight dashboard tabs, in either language, in any of the three tours. **Not a modal** — the dismissal guard runs first and the bound is 4 s. A tour-level selector problem on one page, and the only page it affects; 75 screens per tour were still captured and leak-scanned, including the eight Financial Reports tabs the sweep was added for. |
| 12 | `products: retire at end of round saved` | the driver targeted the **last** product row; `ProductsPage.js:231` renders the retire control only for an `active` product, so from round 7 that row rightly had none. Fixed; round 10 passes it with 5 rows offering the control. |
| 6 | `following the Decision Summary's own instructions makes the lock available` | the equity-box convergence bug described below, plus the debt-to-equity ceiling (**W-CE4-10, open**). |
| 6 | the closed-round `Extend Deadline` probe, and three request-id steps | **the two product findings**: V2-142 and V2-141. |
| 2 | `the game is active with round 1 open`, `the console offers Close round now` | the probe's idempotent second run, on a round its first run had already closed. |
| 2 | the bulk-password and memo-submit steps | reads taken before a 10.57 s and a 15.20 s route had finished; both outcomes proven complete afterwards. |
| 1 | `reset offered` | on a **completed** game the console does not render *Reset to Setup* at all. The step expected a button to press and be refused; withholding it is the stronger behaviour, and the W-CE-26 assertion beside it passes. |
| 1 | `a plant build in the market of the completed acquisition is accepted` | the acquisition was still **queued**, and the product refused the duplicate plant precisely: *"The acquisition of TechSul Eletrônicos already brings a plant in South America, so a plant build there cannot be queued as well. Withdraw one of the two."* The step's expectation was wrong, not the answer. |
| 1 | `a product-market row with no decision yet is available` | a precondition the probe needed and the game no longer had. |

**There is no product console error in the entire pass.** All **198** console
errors are the browser logging a refusal the driver provoked, and they match
the **198** refused API calls exactly. No JavaScript exception, no raw i18n
key, no `undefined` / `NaN` / `[object Object]` on any screen in either
language. One storage field name *was* found, on a Chinese console, by the new
tab sweep — `coherence_ext` prettified onto a chart axis as *"coherence ext"* —
and it is repaired on `fix/bilingual-coverage`.

**Totals.** 1,509 steps passed, 145 failed, 311 observed, across **2,261
screens**, **16,058 API calls** and 212 record files.

## The wrap-up: what a reader is served after the game is over

Everything below ran against the finished game, in both languages.

* **A student reads results and the leaderboard after resolution, in Chinese.**
  The item the previous report left open. Two tours — round 5's results and
  round 10's — each walking **75 screens**, because the tours now open every
  tab on every page and not just the one each page opens on. The contrast is
  the headline bilingual measurement of this pass: on the English reader's 75
  screens the scanner flags **4**; on the Chinese reader's 75 it flags **74**.
  V2-145, V2-146 and V2-148 are what is behind that number.
* **A dispute answered from the console, in both languages.** 14 of 15 steps
  pass in English and 14 of 15 in Chinese, the one failure being V2-141. The
  drill-down was set to the disputed round on the screen (`回合 3` in the
  Chinese run), and it carried **39 audit events, 35 saves and the lock** for
  that team-round, each save with its actor, server timestamp, endpoint,
  payload and SHA-256 readable on screen. **CRV2-08's "unanswerable" dispute is
  closed:** *"the operator changed something"* is answered from **49 operator
  rows read back inside the product**, with actor, server time, action,
  outcome, round, reason, before → after **in words** and request id, refusals
  included and filterable.
* **The console in Chinese, every tab.** The instructor tour named nine tabs
  and swept **twelve**, which is how the Reasoning Analysis panel was seen on a
  Chinese console for the first time — reading *"Reasoning Analysis / Export
  CSV / Team Scores / Comparison / Competition Summary"* and
  *"RANK TEAM AVG SCORE ROUNDS DOMINANT PATTERN CONSISTENCY TREND"* in English
  beside Chinese chrome. Repaired on `fix/bilingual-coverage`.
* **The destructive flows refuse, and say why.** Delete is refused on a game
  with a record — *"CE 2026 Heat A already has a record of instructor actions
  or team decisions. That record is permanent, so the game cannot be deleted.
  Archive the game instead…"* — and refused again, differently, once the heat is
  marked a competition: *"…its results and records have to stay available after
  the event."* Reset is not merely refused on a completed game: **the control is
  not rendered at all**. Archive succeeds and says what it means: *"Game
  archived. You can now create a new game for this section."*
* Grades calculated on the played rounds, and three CSV exports written.

## Findings

Full entries, with causes and repairs, are in `V2_FINDINGS_REGISTER.md`.

* **V2-141, P1** — *the decision audit trail has never carried a request id.*
  Every `DecisionAuditEvent` a real user creates is written with
  `request_id = ''`, across every action type, so the column the dispute
  procedure asks for reads `—` in the instructor's own evidence panel.
  `record_decision_event` took the caller's `X-Request-ID` header or nothing;
  `record_operator_event` has always minted one. The only caller in the tree
  that sends the header is `run_deadline_rehearsal`, so the synthetic rehearsal
  produced ids no browser would. CRV2-08's own evidence shows `request_id: ""`
  beside a conclusion that says the saves carry them. Repaired on
  `fix/decision-audit-request-id`; proven outside the determinism boundary.
* **V2-142, P2** — *`Extend Deadline` on a closed round is a dead end.* Driven
  on real screens: the control is offered, the modal holds an hours spinner and
  **no reason box**, the server answers `reason_required`, and the operator is
  shown *"requires a written reason of at least 10 characters"* with no way to
  give one and no mention of *Reopen round*, which does the job. The refused
  extension left the round exactly as it was. **An asymmetry found on the way:**
  `RoundReopenView` requires **no** written reason at all, while the extend path
  demands one on the stated grounds of *"same bar as an explicit reopen"* — and
  reopen does strictly more, unlocking every locked submission. The additive
  half is repaired on `fix/extend-deadline-reason`; whether reopen should also
  ask is a judgement about the bar itself and is recorded, not decided.
* **V2-143 and V2-144** — four harness defects that were passing or failing
  gates on measurements that never happened. Repaired.
* **V2-145, P1 and V2-146, P2** — bilingual coverage: **GSP-CRV2-12 Stage 4's
  player half was performed in this pass and did not pass.** 155 player-facing
  scenario strings with no Chinese, three views serving JSON blobs raw, and
  nine rendered strings that reached no catalogue — including an entire
  FX-hedge/export-credit panel and a Reasoning Analysis panel of 27 English
  strings with a tab called *"Competition Summary"*. Both repaired on
  `fix/bilingual-coverage`, with the coverage test that stops it recurring.
* **V2-148, P1** — *engine-generated prose a Chinese student reads in English.*
  Found by the new tab sweep on the Government Relations tab of Financial
  Reports: *"Government tightening standards due to poor foreign firm
  compliance"*, which exists in exactly one place —
  `agents/governments.py:449` — composed at resolution and **stored** with the
  action. A different class from V2-145/146: not catalogue coverage and not
  authored content, but prose that is data by the time a reader sees it, which
  is why switching language cannot touch it. The repair follows the pattern the
  repository already uses for briefings — rebuild the sentence at read time from
  the facts the row carries, leaving the stored English as the historical record,
  so nothing hashed moves. Not yet repaired.
* **V2-147** — a Chinese student read English memo feedback. Corrected in the
  register from a heap-order bug to what it is: the open question of what
  language a team-wide artefact uses when a team's members differ. The half
  that costs nothing — template text re-rendered for the reader — is repaired.

## Measured on the way, from gunicorn's own `%(D)s`

Service times under a real browser workload, and the pessimistic case for
anything that calls a model: every LLM URL in this stack is unreachable.

| route | n | p95 | max |
|---|---:|---:|---:|
| `POST …/communications/<id>/submit/` | 4 | 15.20 s | 15.20 s |
| `POST /api/instructor/student-accounts/bulk-reset/` | 1 | 10.57 s | 10.57 s |
| `POST …/round-control/process/` | 1 | 5.90 s | 5.90 s |
| `POST /api/auth/login/` | 80 | 0.44 s | 0.98 s |
| everything else | 2,900+ | < 0.7 s | 0.76 s |

* **A memo submit evaluates inside the request.** With no model reachable it
  waits out the LLM call and the RAG lookup before falling back: 3.2, 3.3, 7.6
  and 15.2 s for the four teams of round 2. If the gateway is down mid-heat,
  each memo submission holds a worker that long.
* **Bulk password issue is one request per roster.** 10.57 s for 27 accounts —
  PBKDF2 at Django's default work factor, measured at **0.378 s per hash** on
  this host. At the pinned field of 24 teams × 4 members that button is ≈ 36 s
  with no progress shown. It completes; axios sets no timeout.
* **Sign-in cost, for the CRV2-07 item.** 0.378 s of CPU per authentication, so
  96 students signing in at once is ≈ 36 s of CPU and ≈ 5 s of wall time on
  eight cores if nothing else runs. Derived from the per-hash measurement, not
  measured as a storm — CRV2-07's own harness owns that.

## What this run changed about how the deadline is set

The schedule `instructor_setup.py` generates starts at a fixed 2026-09-22, so
**every round after the first opens with a deadline that has already passed**,
and the product refuses every write with the correct sentence. That is what
rounds 2 and 3 of the previous run measured: 93 and 87 failed steps against
round 1's zero. Round 2 of this run failed **2**.

1. **Each round is given a deliberate deadline before the teams play, from the
   console's own controls.** `set_round_deadline.py` types an absolute time into
   *Set deadline*. On round 6, named in `hooks/extend-deadline-r6`, the expired
   deadline was first driven through ***Extend Deadline***: the round opened
   **54.37 hours expired** and the control moved it to exactly now + 24.0 h,
   with the round still open and no submission unlocked — the route branch that
   gives the full extension from `now` rather than from a spent window, which is
   what the previous report asked to see exercised.
2. **A deadline step that fails now stops the round** instead of being logged
   and ignored.
3. **Every driver blocks requests that leave this host.** Two drivers never
   called `Recorder.instrument`, where the font-CDN aborts lived. That was
   harmless while the sandbox's resolver refused `fonts.googleapis.com`; once it
   began *answering* with an address this host cannot reach, the stylesheet
   stalled, `DOMContentLoaded` never fired, and `page.goto` timed out after 30 s
   against a stack answering curl in 0.6 ms. The first attempt at this run
   aborted all nine rounds in three minutes as *"no playable deadline"*.

## Harness defects repaired in this run, stated as such

Each had been reporting something other than what it claimed.

| what it claimed | what was happening |
|---|---|
| *"no playable deadline"* on all nine rounds | two drivers never blocked the font CDN; a stalled stylesheet held `DOMContentLoaded` past the navigation timeout |
| *"7 of 27 accounts still without a password"* | the roster was read 2 s into a 10.57 s route that saves each account as it goes |
| *"memo submitted and an evaluation shown"* failed | a fixed 15 s wait raced a 15.20 s submit; the memo was in the database with its evaluation, like the other three teams' |
| the dispute drill-down's endpoint and hash columns read as missing | the drill-down opens on the **current** round, not the round under dispute, so round-1 rows were compared against a round-3 screen |
| *"following the Decision Summary's own instructions makes the lock available"* failed | **the equity box holds a total, not a top-up.** Typing the residual shortfall replaced the equity already decided, so a team oscillated in a perfect two-cycle — type $1.8M → stored $2M → short $0.8M → type $1M → stored $1M → short $1.8M — for five attempts and went to the close as a draft. The driver also cleared the team's financing unconditionally, turning a **$100,000** shortfall into $2.8M on a team whose debt the product *was* counting. Both fixed; in the round after, every playing team locked itself |
| a leaderboard ordering failure in round 8 | the check asserted a flat ordering and did not know R32's rule; the product had printed *"Did not compete"* on the row |
| *"retire at end of round saved"* failed from round 7 | the driver targeted the last product row, which the page rightly offers no retire control for |
| the tours screened one tab per page | only the results page had its tabs walked, so **every other page was screened and leak-scanned on its default tab alone** — which is how an entirely English FX-hedge panel survived three bilingual walkthroughs unseen. Both tours now open every tab, and the console sweep reaches tabs the tour was never told about |

## What this run does not claim

* **It is not Gate 4.** Gate 4 is the rehearsal on the serving deployment with
  its own instructor account (the V2-140 checklist line). This is an isolated
  stack that happens to share the host.
* **Teams 5 and 6 never lock themselves,** in any round. They do not open a
  decision screen, so the lock validator correctly refuses them — *"Set the
  product portfolio before locking."*, *"Set at least one strategy decision
  before locking."* — and the close locks them with the two absentees.
  `run_round.sh`'s comment that they *"complete and lock from the Decision
  Summary"* overstates what `lock_round.py` does. The previous report's *"six
  teams locked"* in round 1 should read **four**: the four that played.
* The leak scan's `team_product` / `retail_price` hits on the dispute
  drill-down's audit panel are the **stored record shown verbatim**, which is
  what that column is for.
* The three repair branches are **not merged into the commit this pass
  certifies.** `a0631e5d` is what was driven; the repairs land on top and the
  automated half of Gate 1 is re-run on the merged tip.
