# Walkthrough CE 2 — the round blockers (2026-09-23)

**Branch:** `walk-ce2-round-blockers`, cut from `crv2-release-integration` at
`48a8a92` (contains `6a25436`, the merge of the second walkthrough, and
`completion/WALKTHROUGH_CE_2_2026-09-22.md`; both verified before anything
was touched).
**Observes:** `handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`,
`specs/STANDING-DISCIPLINE.md`, `handoff_readiness_v2/DETERMINISM_BOUNDARY.md`,
owner ruling **R48** (bugs first, calibration deferred, no new rules).
**Defects:** W-CE2-01 (P0), W-CE2-02 (P1), W-CE2-03 with W-CE-23's remainder
(P1), W-CE2-10 (P1), W-CE-24's remainder (P1), from
`completion/WALKTHROUGH_CE_2_2026-09-22.md`.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`,
`LAUNCH_CHECKLIST_V2.md`, every `OWNER_RULINGS` file and
`INTEGRATOR_DECISIONS_UNDER_R48.md` were left untouched; §8 proposes register
text for the auditor to apply or reject.

Method throughout: reproduce first — a test that fails on the tree as it was,
with the exception and the state recorded — then repair, then run the same
test green. One commit per defect.

| Commit | Defect | What |
|---|---|---|
| `4693777` | W-CE2-01 | Two plants in one market are one plant, and cannot be queued |
| `8d9fda0` | W-CE2-02 | A queued commitment can be withdrawn; what cannot be funded is not offered |
| `273daec` | W-CE2-03 | The deadline no longer executes an acquisition the lock refused |
| `5182912` | W-CE2-10 | The round control card re-reads when the game is activated |
| `7efd126` | W-CE-24 | A reasoned Advance Round actually advances the round |
| *(next)* | — | This document |
| *(last)* | — | Regenerated static string inventory, alone |

---

## 1. W-CE2-01 (P0) — a round that cannot be processed at all

### Reproduction (red)

`backend/core/tests/test_plant_collision.py`. A two-team game whose home
market allows manufacturing, one team with a `decision_plant` build in that
market **and** a locked `decision_acquisition` for *AfriConnect Mobile*, an
`includes_plant` target in the same market; the round is closed and
`process_round` is called — the real path behind *Run post-round processing*
and *Close & process now*.

On the tree as it was: **4 errors of 7**, the exact exception the walkthrough
recorded, raised from `resolution_manifest.complete_manifest` →
`manifest_snapshot.build_snapshot`:

```
core.services.manifest_snapshot.SnapshotError: Natural key
('team_id', 'market_id', 'construction_started_round') is not unique in
section "team_plant": team_plant(team(game("pc-…")|"Team 0")|
market_definition(scenario("Concurrency pc-…")|"HM")|"1") appears twice.
```

**The state it leaves.** Phase 1's transaction rolls back, so no plant row,
no financials and no results survive; `advance_round._mark_failed` then
writes, outside that transaction, `round.processing_status = 'FAILED'` while
`round.status` stays `closed`. The game sits on that round. Every console
control — *Run post-round processing*, *Close & process now*, the lifecycle
*Advance Round* — reaches the same 500, and no student or instructor screen
can withdraw either decision on a closed round. That is the state
`harness/unstick_plant_collision.py` was written for.

**A second game-stopper found in the same reproduction, not in the record.**
Two `decision_plant` build rows for one market — which the Market Strategy
screen offered, because the Build Plant button stayed on the card after the
first click (§2) — break the **input** snapshot instead:

```
SnapshotError: Natural key ('submission_id', 'market_id', 'action') is not
unique in section "decision_plant": … appears twice.
```

`prepare_manifest` runs before Phase 1, so this one stops the round before a
single value is computed and **no engine repair can reach it**. It needs the
operator path in §1.4.

### Cause

* `core/engine/strategy_effects.py:280` (`_process_plants`, engine step 4)
  created a `TeamPlant` for the build.
* `core/engine/acquisitions.py:66` (`process_acquisitions`, step 4.6) created
  a second one for the target's included plant.
* Both used `(team, market, construction_started_round = this round)`, which
  `core/services/manifest_sections.py:464` declares the natural key of the
  hashed `team_plant` section.
* `core/models/team_state.py:135` carries no database constraint, so nothing
  refused the second row; the snapshot did, at the end of the round.

The invariant is the manifest's: **one plant row per team, market and
construction start**. Every read side already assumes it — `views/decisions.py:2179`
and `serializers/decisions.py:540` sum `capacity_units` per market as the
team's capacity there, and `engine/costs.py:111,120` ask only whether *a*
plant exists in the source market and read one row's learning curve.

### Repair

**a. The engine reconciles rather than crashes.** New
`backend/core/engine/plants.py` — `record_plant(team, market, …)`. Both engine
steps go through it. A second plant started by one team, in one market, in
one round merges into the row already there: capacities add, the earlier
`completion_round` wins, and a plant that is operational stays operational.
It is deterministic — the row is chosen by the natural key itself, so the
result does not depend on which engine step ran first.

*What the reconciled row means for the team.* It has the acquired plant's
capacity plus the built plant's, operational from this round. That is a
choice, because before this repair the round produced nothing at all: there
was no behaviour to preserve. It favours the team that paid for both. The
alternative — hold the combined capacity under construction until the build
would have finished, delaying the acquired plant the team bought outright —
is recorded for the owner in §7.2. **This path is reachable only for a game
that already carries the collision**, because of (b).

**b. The decision boundary refuses it.** `plants.plant_collisions(submission,
language)` returns finished sentences for both collisions, judged on the rows
actually stored, and is applied at:

* the per-type save (`views/decisions.py`, `DecisionPartialUpdateView`) for
  `plants` **and** `acquisitions`, so either order of the two pages is
  refused, inside the view's atomic block — a refused save leaves the team's
  decisions exactly as they were;
* the whole-submission save (`DecisionSubmissionView._upsert`), in the
  position V2-024's funding check already occupies;
* `lock_blockers_for`, so a draft assembled before this rule existed — or by
  an import, the admin or a shell — cannot be locked into a round that would
  then refuse to process. The Decision Summary publishes that list (W-CE-25),
  so the student sees it before the click.

A target another team already owns does not block a build: `process_acquisitions`
skips it, so it cannot collide.

**c. The operator path for a round already stuck.**
`manage.py reconcile_plant_rows --game-id N [--round R] [--apply]`. Reports by
default; `--apply` removes only the *repetition* — the first row for each
(submission, market, action) is kept, so the team's decision survives — and
writes a `DecisionAuditEvent` (`duplicate_plant_decision_removed`,
`endpoint='manage.py:reconcile_plant_rows'`) for each removal. It is the
supported replacement for the database edit the walkthrough had to make.

### Recovery for a round that is already `closed / FAILED`

**For the acquisition-plus-build collision (the one the record names): the
engine fix alone un-sticks it.** `prepare_manifest` uses `update_or_create`,
so a second attempt overwrites the failed manifest; `process_round` accepts a
round whose status is `closed`; and the merge means the output snapshot now
succeeds. The operator presses *Run post-round processing* again and the
round completes.
`StuckRoundRecoveryTests.test_a_failed_round_processes_on_the_next_attempt`
sets exactly `status='closed', processing_status='FAILED'` and asserts it.

**For the duplicate-decision collision: the command, then the same button.**
`ReconcileCommandTests` drives it end to end — the SnapshotError, the report,
`--apply`, the audit row, and the round processing afterwards.

### Green

`test_plant_collision` **18 OK of 18** (4 errors before the repair). Focused
batch with it: **259 OK** across `test_engine`,
`test_manifest_determinism`, `test_silent_section_saves`,
`test_committed_spend_one_calculator`, `test_summary_blockers_match_lock`,
`test_console_defects`, `test_audit_integrity`.

### Stored or hashed values

No hashed value moves for any round that does not carry the collision: the
merge only runs when a second row would be created, and the decision refusals
change no stored value. A round that *does* carry it could not be hashed at
all before, so there is no earlier hash to compare with.
`MANIFEST_SCHEMA_VERSION` is unchanged at **7**; no section changes shape and
no migration is added.

---

## 2. W-CE2-02 (P1) — a commitment that could be made but never withdrawn

### Reproduction (red)

Two Jest suites driving the real pages:

* `frontend/.../src/pages/CorporateStrategyPage.withdraw.test.js` — a queued
  acquisition and the walkthrough's own figures ($23.4M of unallocated cash
  against a $25.0M target). On the page as it was (`git show 48a8a92:…` swapped
  in for one run): **2 failed of 3** — no control with an accessible name of
  "withdraw" exists at all, and the Acquire button is offered and enabled for
  a target the team cannot fund.
* `frontend/.../src/pages/MarketStrategyPage.withdraw.test.js` — a queued
  plant build and a queued partnership. On the page as it was: **4 failed of
  4** — the queued build is not rendered (so the Build Plant button is still
  offered and a second click stores the duplicate row of §1), the queued
  partnership is not rendered at all, and nothing can be withdrawn.

### Cause

* `MarketStrategyPage.js` read `context.plants` (plants the team **owns**) and
  `context.partnerships` (**active** partnerships) — neither contains this
  round's draft. The draft was in component state (`plantDecisions`,
  `partnerships`) and was never rendered.
* `CorporateStrategyPage.js` rendered a queued acquisition only as a disabled
  button label.
* Nothing on either page read an affordability figure; the strategy context
  published none.

The write contract was already right: `_TYPE_MAP` in `views/decisions.py:490`
makes `plants`, `partnerships` and `acquisitions` whole-section replaces
(`delete()` then `bulk_create()`), which is how market entry's own *Exit
market* control already works. Withdrawing is that same save with the row left
out.

### Repair

* Each queued commitment is shown where it was made, with a withdraw control
  that removes the row and autosaves the remaining list. The plant card shows
  *Plant build queued* in place of the Build button, which also closes the
  duplicate-row path in §1.
* `StrategyContextView` publishes `affordability` — `cash_on_hand`,
  `committed_total`, `unallocated` — read straight from
  `rd_costs.budget_assessment(submission, team)`, the calculator the lock
  refuses on. An offer costing more than `unallocated` is disabled with the
  figures beside it. A server that does not send `affordability` offers
  everything, as before.
* `plantCostLabel` is factored out of `plantBuildLabel` so the new sentence
  keeps W-CE-22's floor: a cost the scenario does not author is named, never
  rendered as `$0`. (`marketStrategyLabels.test.js` enforces that floor and
  caught the first attempt.)

### Green

`CorporateStrategyPage.withdraw.test.js` **3 OK**,
`MarketStrategyPage.withdraw.test.js` **4 OK**; full Jest **485 of 485** at
that commit. Backend **95 OK** across `test_audit_integrity`,
`test_zh_terminology`, `test_plant_collision`,
`test_committed_spend_one_calculator`, `test_summary_blockers_match_lock`.

### Stored or hashed values

None. The context endpoint gains a read-only block; no engine charge, no
scenario number and no decision default changes.

---

## 3. W-CE2-03 and W-CE-23's remainder (P1) — the deadline executed the refused spend

### Reproduction (red)

`backend/core/tests/test_deadline_lock_affordability.py`: a team with $1.0M of
cash and a queued $1.5M acquisition, left as a **draft**; `close_round` then
`process_round` — the deadline path exactly. On the tree as it was: **3 failed
of 7**.

* `lock_blockers_for` on that draft returns *Committed spend of $1,500,000.00
  exceeds available cash of $1,000,000.00* — the lock refuses it (the control
  assertion, green before and after).
* `_lock_all_submissions` locks it anyway as `deadline_lock`;
  `process_acquisitions` fulfils the acquisition; `costs` charges it in full.
* Recorded state: `TeamAcquisition` exists, `strategy_expense` is $1.5M above
  the control team's, `cash_closing` is **−$1,000,000.00**, and the team is
  told nothing — `TeamNotification` for the team is `[]`.

That is the walkthrough's −$12.4M in miniature.

### What the rules say, and what was implemented

There is **no ruling on auto-lock at the deadline** — `OWNER_RULINGS_2026-09-11
/12/16/17/21/22` and `OWNER_DECISIONS_PENDING_2026-09-16` contain none, and
R48 delegates nothing that covers it. Applying the whole lock validator at the
deadline would be wrong on its own terms: most of `lock_blockers_for`'s
blockers are *this section is empty* (`product_portfolio_required`,
`marketing_mix_required`, `strategy_mix_required`), and a team that did nothing
must still be resolved — refusing to auto-lock it would stall the round, which
is the W-CE2-01 failure again.

So what is implemented is the one rule the refusal itself names, in the one
place the engine **already** withholds a commitment for a team's financial
condition:

> `engine/acquisitions.py` already refuses an acquisition to a team in
> financial distress, and to a team whose target another team took, in both
> cases with a notification ending *"No cost has been charged"* — and
> `engine/costs.py:515` charges the base acquisition cost **only for an
> acquisition that was actually fulfilled**.

That gate now also reads the lock's own affordability answer,
`rd_costs.budget_assessment(submission, team)['within_cash']` — the exact
check whose sentence the team was shown. **If a submission would be refused
for affordability, none of its acquisitions are fulfilled**: all-or-nothing,
so no ordering is invented, no decision row is deleted (the row is the team's
record, as the price-band ruling requires), and nothing is charged.

It is uniform rather than a deadline special case, which is why no new rule is
needed: a team that locked its own submission passed that check *at the lock*,
so the gate can only ever fire on a draft the lock would have refused.

### Repair

`backend/core/engine/acquisitions.py` — `affordable` computed once per team
alongside `distressed`, a `_notify_unaffordable` worded like its two siblings.

### Green

**7 OK of 7.** Focused batch with it: **266 OK**. The withheld acquisition is
not charged (`strategy_expense` equals the control team's), cash closes at or
above zero, the decision row survives, and the team is told. An affordable
acquisition is unaffected, on a deadline-locked draft and on a
team-locked submission alike.

### What this does **not** cover — for the owner, §7.1

A draft made unaffordable by outlays **other than** an acquisition — a plant
build, marketing, a market entry — still resolves and can still end a team in
the red. Those are charged from the decision row rather than from a fulfilment
the engine can withhold, and V2-024's parity assertion holds
`funding_need.decision_outlays` and `costs.calculate_operating_expenses` to
the same rows, so withholding one of them is a change to the charging
contract, not a change to a gate. It is a rules question, put plainly in §7.1.

W-CE-23's own remainder — *a team whose cash is negative cannot lock anything,
because the affordability check compares spend to cash on hand and ignores the
financing the team has decided, while the sentence beside it says to raise
financing* — is unchanged and unchangeable without a ruling. It was already
put to the owner as §8.1 of `WALK_CE_STUDENT_NUMBERS_2026-09-22.md`; it is
restated in §7.3 so it is not lost. What this branch does change is how a team
*reaches* negative cash: the acquisition that caused it is now withheld, and
the commitments that caused it can now be withdrawn before the lock (§2).

### Stored or hashed values

Yes, for a round in which a team's committed spend exceeds its cash **and** it
has a queued acquisition. In such a round `team_acquisition`, `financials`
(`strategy_expense`, `cash_closing` and everything derived from them) and the
rest of the competitive envelope now differ from what the same state would
have produced before this commit. Every other round is byte-identical. No
section changes shape; `MANIFEST_SCHEMA_VERSION` stays **7**. Replay evidence
for a round carrying such a team predates this branch's engine.

---

## 4. W-CE2-10 (P1) — the first action after Activate was always refused

### Reproduction (red)

`frontend/.../src/pages/instructorDashboardActivate.test.js` drives the real
`InstructorDashboard` through the real Activate Game popconfirm, against a
server that answers `/round-control/` with round 0 `pending` while the game is
in setup and round 1 `open` once it is active. On the tree as it was: **2
failed of 2** — `/round-control/` is fetched exactly once, the card still
shows `rc_status_pending`, and the first round-control action carries
`expected_round_number: 0`, which is precisely the 409 the walkthrough
recorded (*The game has moved to round 1; this request was for round 0.
Refresh the console…*).

### Cause

`components/RoundControlCard.js` — `load` is `useCallback(…, [gameId, t])` and
the effect that calls it depends on `load` alone. Activating a game moves it
from round 0 to round 1 without changing `gameId`, and since the W-CE-01
repair the console deliberately no longer unmounts on a reload, so the card
kept the round it had first read and sent it as `expected_round_number` —
the optimistic check in `services/lifecycle.py:133` that exists to tell an
operator the state moved under them.

### Repair

The card takes a `reloadKey` prop and its load effect depends on it; the
dashboard passes what the card cannot see change,
`` `${displayGameStatus}:${dashboard?.current_round ?? ''}` ``. No guard is
weakened: the expected-round check still fires when the state genuinely moves
under an operator; the card now simply knows when the operator's own action
moved it.

### Green

**2 OK**; full Jest **487 of 487** across 51 suites.

### Stored or hashed values

None — a console read.

---

## 5. W-CE-24's remainder (P1) — Advance Round still could not advance

### Reproduction (red)

`backend/core/tests/test_legacy_advance_with_pending_teams.py`: one team
locked, one still a draft, `POST /api/games/N/instructor/advance-round/` with
`{force: true, reason: …}` through the real instructor client. On the tree as
it was: **3 failed of 7**, with exactly the recorded body —

```
400 {'error': 'Team "Team 1" has not locked decisions for round 1. Re-lock the
team (or close the round) before processing.', 'code': 'round_not_ready',
'guidance': 'Re-lock the team, or close the round, then process again.'}
```

and the round left `open`, the pending submission left `draft`.

### Cause

`views/results_api.py`, `InstructorAdvanceRoundView`: `force` skipped **this
view's** all-teams-locked precondition and then called `advance_round` →
`process_round` → `_run_phase_1`, which checks the same thing again at
`engine/advance_round.py:508` — deliberately, as its comment says, so the
engine entry point never silently creates or locks a submission. The override
reached the engine and the engine refused it. The one control on the card
that says "advance" could not advance a round with pending teams at all.

### Repair — the step the operator expects, with no guard weakened

With `force` and a written reason on an **open** round, `close_round` runs
first. That is the deadline path: it locks each team's draft as it stands,
writes a `deadline_lock` `DecisionAuditEvent` per team, and applies the
deadline price rule. It is exactly what `RoundProcessView` already does with
`force`. The engine's precondition is then **satisfied**, not bypassed.

Everything else is unchanged and is now covered by a test that would catch a
regression: without a reason the override is still refused `reason_required`
and the round stays open; without `force` a pending team still refuses
`team_not_locked`; an already-processed round still refuses
`round_already_processed`; the all-teams-locked plain path is unchanged; the
reason is still on the `advance_round_legacy` operator audit row.

The modal's own sentence went with it. It promised *"Their previous round's
decisions will carry forward"*, which is not what happens — the pending team
is locked with the decisions it has entered *this* round. Corrected in both
languages (§6).

### Green

**7 OK of 7**; **213 OK** with `test_operator_refusal_language`,
`test_operator_concurrency`, `test_console_defects`, `test_audit_integrity`,
`test_engine`.

### Stored or hashed values

No hashed value changes. A round advanced this way now carries `deadline_lock`
audit events and price-band audit events it previously could not carry,
because the action previously could not complete at all.

---

## 6. zh-CN — new and changed sentences

New, additive, inserted line by line rather than by re-serialising the
catalogues, because another builder is editing them concurrently.

| Where | Key | English | 中文 |
|---|---|---|---|
| `participant_messages.py` | `plant_already_queued` | Your company has already queued a plant in {market}. One plant per market in a round. | 贵公司本回合已在{market}安排建设工厂。每个市场每回合只能建设一座工厂。 |
| `participant_messages.py` | `plant_and_acquired_plant` | The acquisition of {target} already brings a plant in {market}, so a plant build there cannot be queued as well. Withdraw one of the two. | 收购{target}已在{market}带来一座工厂，因此不能同时安排在该市场建设工厂。请撤回其中一项。 |
| `locales/*.json` | `market_strategy.plant_queued` | Plant build queued | 已排入工厂建设 |
| `locales/*.json` | `market_strategy.withdraw` | Withdraw | 撤回 |
| `locales/*.json` | `market_strategy.queued` | Queued | 已排入 |
| `locales/*.json` | `market_strategy.not_affordable` | Needs {{cost}}; {{available}} unallocated | 需要 {{cost}}；未分配资金 {{available}} |
| `locales/*.json` | `corporate_strategy.withdraw` | Withdraw | 撤回 |
| `locales/*.json` | `corporate_strategy.not_affordable` | Needs {{cost}}; {{available}} unallocated | 需要 {{cost}}；未分配资金 {{available}} |

Changed, because the old sentence described something the action does not do:

| Where | Key | Was | Now (EN) | Now (中文) |
|---|---|---|---|---|
| `locales/*.json` | `instructor.advance_pending` | {{count}} team(s) have not locked decisions. Their previous round's decisions will carry forward. Proceed? | {{count}} team(s) have not locked decisions. Advancing closes the round: each of them is locked with the decisions it has entered so far. Proceed? | {{count}} 个团队尚未锁定决策。推进将结束本回合：这些团队将以目前已填写的决策被锁定。是否继续？ |

`test_zh_terminology` passes (回合 for round; no retired term).
`check-participant-strings` PASS, 5740 units, 0 findings, and its selftest
34 ok. Whether the short labels read naturally is for a native speaker (§9).

**One sentence is English only, and was before this branch.** The new
`_notify_unaffordable` team notification (§3) is an English f-string, exactly
like its two siblings `_notify_distress_blocked` and `_notify_rejected_bid`
and like `financials._notify_debt_refused`. `TeamNotification` stores finished
text with no language column, so making these bilingual is a change to how
notifications are stored, not a wording change; it is listed in §9 as
untouched work rather than introduced silently here.

---

## 7. Questions for the owner, in plain language

### 7.1 A team that overspends on something other than an acquisition

*What happens now:* if a team commits more than it has and part of it is an
acquisition, the acquisition is not completed, the team is told, and it is not
charged — the same treatment a team in financial distress already gets. If the
overspend is a plant, marketing or a market entry instead, the money still
leaves and the team can finish the round with negative cash.

*Why the difference:* an acquisition is the only one of these the engine
already decides to complete or not; the others are charged straight from the
team's decision line, and two separate parts of the engine are checked against
each other to make sure they charge the identical figure. Withholding one of
them would mean changing what the engine charges, not just whether it
completes something.

*The question:* should a team be able to spend past its cash at all, once the
deadline locks it in? Three answers are possible — (a) leave it as it is, and
a team that mismanages its cash ends the round in the red and lives with it;
(b) the deadline trims whatever the team cannot pay for, in some stated order;
(c) the deadline refuses to lock that team and an instructor sorts it out.
(c) stalls the round for everyone, which is what the P0 above was about, so it
is not recommended. Nothing here is urgent: with this branch a team can now
see the figures before it commits, and take a commitment back.

### 7.2 Two plants in one market in one round

*What happens now:* it cannot be created any more — the screens and the lock
refuse it. For a game that already has it, the engine treats the two as one
plant with both capacities, running from this round.

*The alternative:* treat them as one plant that is still being built, so the
combined capacity only comes on line when the construction would have
finished. That is harsher on the team, which bought a working factory as part
of the acquisition.

*Why it barely matters:* the situation is now unreachable in a new game. It
is written down because it is a rule a player could feel, and R48 asks for
every such rule to be traceable.

### 7.3 Restated, not new: a team with negative cash cannot press Lock

Already put to the owner as §8.1 of `WALK_CE_STUDENT_NUMBERS_2026-09-22.md`
and still open. A team whose cash is negative is told *"Committed spend of $X
exceeds available cash of $−Y"* no matter what it cuts, and beside it
*"Projected ending cash is … raise financing before locking"* — but raising
financing does not clear the first line, because that check compares spend to
cash on hand and ignores the debt or equity the team has decided to raise. The
team can still play (its draft is locked for it at the deadline) but can never
press Lock. Should "available cash" count the financing the team has decided,
as the projected-cash check and the funding rule already do?

---

## 8. Proposed register text

* **W-CE2-01** — *Repaired at `4693777`.* Two engine steps created a
  `team_plant` row with the same declared natural key, so the output snapshot
  refused the round and it stuck at `closed / FAILED` with nothing on any
  screen able to undo either decision. Both steps now go through
  `engine/plants.record_plant`, which merges rather than collides, so a stuck
  round is un-stuck by running post-round processing again; the collision is
  refused at both saves, at the whole-submission save and at the lock,
  bilingually and naming the market. A second collision found in the
  reproduction — two build rows in one market, which breaks the *input*
  snapshot before Phase 1 — is refused at the save and cleared for an existing
  game by the new `manage.py reconcile_plant_rows`. `test_plant_collision`,
  18 tests. No hashed value moves for a round without the collision; schema
  version 7 kept.
* **W-CE2-02** — *Repaired at `8d9fda0`.* Queued acquisitions, plant builds
  and partnerships are shown where they were made and can be withdrawn until
  the lock (the sections are whole-section replaces, as market entry already
  used). `StrategyContextView` publishes `affordability` from
  `rd_costs.budget_assessment`, so an offer the lock would refuse is not
  enabled. `CorporateStrategyPage.withdraw.test.js`,
  `MarketStrategyPage.withdraw.test.js`.
* **W-CE2-03** — *Repaired at `273daec`; one rules question remains.* The
  engine's existing acquisition gate — which already withholds an acquisition
  from a distressed team, uncharged — now also reads the lock's own
  affordability answer, so a draft the lock would have refused does not have
  its acquisitions fulfilled at the deadline. Uniform, not a deadline special
  case. `test_deadline_lock_affordability`. An overspend made of other outlays
  still resolves: §7.1. **Changes a hashed value** for a round carrying such a
  team.
* **W-CE-23** — *First half repaired earlier (`e0cd389`); the negative-cash
  lock-out is still a rules question,* §7.3. This branch changes how a team
  reaches negative cash, not the check itself.
* **W-CE2-10** — *Repaired at `5182912`.* `RoundControlCard` read
  `/round-control/` once per `gameId` and sent the round it was showing as
  `expected_round_number`; activating a game moved the round without changing
  `gameId` and, since W-CE-01, without remounting the console. The dashboard
  now passes the game's status and round as `reloadKey`.
  `instructorDashboardActivate.test.js`. No guard weakened.
* **W-CE-24** — *Repaired at `49d0447`, `94f1bd9` and now `7efd126`.* With
  `force` and a written reason on an open round, the legacy advance closes the
  round first — the deadline path, which is what `RoundProcessView` already
  does with `force` — so the engine's all-teams-locked precondition is
  satisfied rather than bypassed and the action completes. The modal's claim
  that previous-round decisions carry forward is corrected in both languages.
  `test_legacy_advance_with_pending_teams`, including a test for each guard
  that must not move.

---

## 9. Commands and results

Every backend run through `backend/scripts/test-postgres` (disposable
`postgres:16-alpine`) under `flock -w 3600
/tmp/globalstrat-backend-test.lock`, with `TEST_POSTGRES_READY_SECONDS=1500`.
Never the production database (192.168.50.38), never
`/etc/globalstrat-plus.env`.

| # | Command | Result |
|---|---|---|
| 1 | `test-postgres core.tests.test_plant_collision` at `48a8a92` | **4 E of 7 (red)**, both SnapshotErrors |
| 2 | `test-postgres core.tests.test_plant_collision` | 18 OK |
| 3 | `test-postgres` focused batch (plant collision + the 7 standing labels) | **259 OK**, 52.1 s |
| 4 | Jest `CorporateStrategyPage.withdraw` against `48a8a92`'s page | **2 F of 3 (red)** |
| 5 | Jest `CorporateStrategyPage.withdraw` | 3 OK |
| 6 | Jest `MarketStrategyPage.withdraw` against `48a8a92`'s page | **4 F of 4 (red)** |
| 7 | Jest `MarketStrategyPage.withdraw` | 4 OK |
| 8 | `test-postgres test_audit_integrity test_zh_terminology test_plant_collision test_committed_spend_one_calculator test_summary_blockers_match_lock` | 95 OK |
| 9 | `test-postgres core.tests.test_deadline_lock_affordability` at `8d9fda0` | **3 F of 7 (red)**, cash closing −$1,000,000.00 |
| 10 | `test-postgres core.tests.test_deadline_lock_affordability` | 7 OK |
| 11 | `test-postgres` focused batch after W-CE2-03 | **266 OK**, 55.3 s |
| 12 | Jest `instructorDashboardActivate` against `48a8a92`'s console | **2 F of 2 (red)** |
| 13 | Jest `instructorDashboardActivate` | 2 OK |
| 14 | `test-postgres core.tests.test_legacy_advance_with_pending_teams` at `5182912` | **3 F of 7 (red)**, 400 `round_not_ready` |
| 15 | `test-postgres core.tests.test_legacy_advance_with_pending_teams` | 7 OK |
| 16 | `test-postgres` + `test_operator_refusal_language`, `test_operator_concurrency`, `test_console_defects`, `test_audit_integrity`, `test_engine` | **213 OK**, 163.4 s |
| 17 | `CI=true npx react-scripts test --watchAll=false` (full) | **51 suites / 487 tests OK** |
| 18 | `check-participant-strings` / selftest | **PASS 5740 units, 0 findings** / **34 ok** |
| 19 | `CI=false BUILD_PATH=<scratch> npx react-scripts build`; `node eslint-warning-count.js` | Compiled with warnings; **54 (baseline 55)**, none in a file this branch adds; exit 0 |
| 20 | **`test-postgres core --parallel 8` at `7efd126`** | `Ran 1616 tests in 130.013s`, **OK**, exit 0 |

**On the ESLint count.** It is 54 against a baseline of 55, so the ratchet
passes. I did not lower the baseline: no declaration is removed by any file
this branch touches, so the one-warning drop is not attributable to it, and
another builder is editing the same tree concurrently — lowering the baseline
would fail their build for a warning they did not add.

No runtime code changed after #20 began. `git diff --check` clean at every
commit; every touched file kept LF line endings; the locale catalogues were
edited line by line so the diff is 6 added lines and 1 changed line per file.

Not run, because not release-scale and not touched by this branch: the
concurrency matrix at release iterations, the four-environment replay, load,
soak, browser archive. §3 changes a hashed value for one class of round, so
replay evidence for a round in which a team's committed spend exceeded its
cash *and* it had a queued acquisition predates this branch's engine.

---

## 10. Distrust

Only what needs the owner, the production host, a browser or a native speaker.

* **The owner:** §7.1 (should a deadline-locked team be able to spend past its
  cash at all), §7.2 (which of the two reconciliations for a plant collision a
  game already carrying one should get), §7.3 (restated, still open).
* **A browser:** every frontend repair here is driven through the real
  components under jsdom, which is not Chromium. The walkthrough drivers
  (`student_play.py`, `instructor_round.py`,
  `verify_post_activate_deadline.py`) have not been re-run against this
  branch. In particular the W-CE2-10 repair should be confirmed by actually
  activating a game and setting a deadline without reloading.
* **The production host:** `manage.py reconcile_plant_rows` is tested against
  the disposable database only. It has been run nowhere else, and there is no
  evidence that any live game carries the duplicate rows it clears.
* **A native speaker:** the eight zh-CN strings in §6, and in particular the
  corrected `instructor.advance_pending` sentence, which is longer than the
  one it replaces.
* **Untouched, not fixed:** team notifications from the engine are stored as
  finished English text with no language column
  (`_notify_unaffordable` joins three siblings that were already like that).
  A Chinese-speaking team reads them in English. Making them bilingual is a
  storage change, not a wording change, and belongs with the language work
  another builder is doing.
