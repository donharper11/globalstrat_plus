# The lock a team can always reach, and the money that went missing

**Branch:** `walk-ce3-lock-and-money`, cut from `crv2-release-integration` at
`f53fdb8` ("Decide the lock a team can never reach, under R48"). Base verified
before anything ran: `f53fdb8` is HEAD of `crv2-release-integration`, and
`completion/WALKTHROUGH_CE_3_2026-09-23.md` and
`INTEGRATOR_DECISIONS_UNDER_R48.md` are both present on it.
**Date:** 2026-09-23.
**Specification:** integrator decisions **13, 14 and 15** under R48. They are
decided; nothing below re-opens them.
**Evidence root:** `handoff_readiness_v2/evidence/walk-ce3-lock-and-money/`.

Four ids: W-CE3-02 with the W-CE-23 remainder (P0), W-CE2-03's residue (P1),
W-CE3-01 (P0), W-CE3-03 and W-CE3-04 (P1). One more was repaired inside the
first because it is the same dead end and decision 13 forbids it: W-CE3-16.

**No gate is closed by this report.** The next gate is a clean walkthrough
(R48), and nothing here has been driven in a browser.

> Sections: (1) method · (2) commits · (3) W-CE3-02 · (4) W-CE2-03's residue ·
> (5) W-CE3-01 · (6) W-CE3-03 / W-CE3-04 · (7) the whole-game proof ·
> (8) stored and hashed values that change · (9) zh-CN · (10) commands and
> results · (11) proposed register text · (12) distrust list.

---

## 1. Method

Every defect was reproduced first, through the real routes, with the figures
recorded — then repaired, then measured again. The red for each id is quoted
below with the command that produced it:

* **W-CE3-02** — a whole six-round game driven through the product's own HTTP
  routes with a signed-in team member's bearer token, because this is the
  defect unit tests missed. `evidence/.../whole-game-red.json`.
* **W-CE2-03's residue** — the 16 new tests run with the one new call in
  `close_round` disabled; 9 fail.
* **W-CE3-01** — the three defect lines restored in `engine/costs.py`; 8 of 19
  new tests fail, `cash_opening` reading `-$1,000,000` against the $1,000,000
  the round opened with.
* **W-CE3-03 / W-CE3-04** — measured on the served payload and on the page's
  own line list, against the round results the six-round game produced:
  `evidence/.../statement-red.json`, re-taken with the repair reverted so the
  red and green figures are a matched pair.

Backend tests only through
`cd backend && flock -w 3600 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`
with `TEST_POSTGRES_READY_SECONDS=1500` (disposable PostgreSQL in a container
of this pass's own). Never the production database at 192.168.50.38, never
`/etc/globalstrat-plus.env`. The whole-game harness runs against its own
disposable container (`globalstrat-walk-ce3-lockmoney-pg`, database
`globalstrat_walkce3lm`, an ephemeral host port), refuses the production host
by name, and writes pre-resolution dumps only to a disposable directory
(`harness_isolation.require_disposable_backup_dir`, V2-128).

---

## 2. Commits

| Commit | Item |
|---|---|
| `a97f055` | W-CE3-02 + W-CE-23's remainder + W-CE3-16 — decision 13 |
| `57e9e4f` | W-CE2-03's residue — decision 14 |
| `e91ead6` | W-CE3-01 — decision 15 |
| `0bb0d13` | W-CE3-03 and W-CE3-04 |

A fifth commit regenerates the string inventory from the repository root, on
its own, after everything else.

---

## 3. W-CE3-02 — the lock a team can never reach (P0, decision 13)

### 3.1 The reproduction, with the figures

Driven on a six-round game through `/api/auth/login/`,
`…/decisions/round/N/summary/`, `…/financing/` and `…/lock/`
(`harness/whole_game.py --label red`). One team is made to build far more
stock than its market will buy in round 2 — cost of goods is charged at
resolution and is deliberately outside `funding_need.decision_outlays`, so
nothing the lock checks refuses it.

| Round | Team's cash at the round's start | Locked? | Forced by the deadline |
|---|---:|---|---:|
| 1 | $50,000,000.00 | yes | 0 |
| 2 | $38,688,923.44 | yes | 0 |
| 3 | **−$61,306,078.79** | **no** | 1 |
| 4 | −$12,080,892.36 | **no** | 1 |
| 5 | −$12,966,934.29 | **no** | 1 |
| 6 | −$17,466,265.49 | **no** | 1 |

At round 3, with every declared budget, promotion budget and dividend set to
zero through the real save routes, the Summary still refused:

> Committed spend of $200,000.00 exceeds available cash of $-61,306,078.79.
> This includes $0.00 of platform development.
> Total dividends of $0.00 exceed projected equity. Reduce the dividend.

and **raising $61,600,000 of new debt through the real financing route did not
move the available-cash figure by a cent**. That is the walkthrough's finding,
reproduced to the shape and to the sentence.

### 3.2 The cause

`backend/core/services/rd_costs.py:418` (as it stood):

```python
cash = Decimal(getattr(team, 'cash_on_hand', ZERO) or ZERO)
...
'within_cash': committed <= cash,
```

The affordability rule compared committed spend with cash on hand and read the
financing row nowhere. Once cash is negative, no spend is smaller than it.
Beside it, `backend/core/views/decisions.py:1090` computed a *second* projected
cash figure from the financing row — so the lock told a team to raise financing
in one sentence while refusing it on a comparison raising financing could not
clear.

Two more lines made the state terminal rather than merely hard:

* `views/decisions.py:1060` fired `dividends_exceed_equity` on a dividend of
  **$0.00** whenever projected equity was negative — W-CE3-16, nothing below
  zero to reduce to;
* `engine/financials.py:199` refuses new debt outright for a team in financial
  distress, which is every team whose cash closed negative.

### 3.3 The repair

One new calculator, `funding_need.financing_effect`, is the engine's own
financing arithmetic lifted out of `engine/financials.generate_financial_
statements` whole — the distress refusal, the repayment cap, the CC-26 equity
subscription and the dividend cap. The engine now calls it and keeps only its
side effects (the log lines, the refusal notice, the share issue), so there is
one calculator and the lock cannot promise money the round then declines.

`rd_costs.budget_assessment` compares committed spend with **available funds**
— cash on hand plus `financing_effect`'s net figure — and publishes
`projected_cash` (`available_funds - committed_total`) once. The lock, the
Decision Summary and the Finance page all read that one figure; the separate
projected-cash sentence is gone because it described the same comparison.
`unallocated` and `total_available` follow it, so the M&A and plant cards
(W-CE2-02) still offer exactly what the lock will accept.

Two judgements inside that, each with a test that fails if it is reversed:

* **Debt refused in distress is not counted.** The engine will not hand it
  over, so counting it would be the same class of defect as not counting
  financing at all. The team is told, and told to raise equity instead.
* **Equity is counted at the amount decided, not at the subscribed amount.**
  V2-024 caps an equity raise at the round's shortfall itself; netting the
  subscription haircut inside available funds would make that shortfall
  uncloseable by equity — exactly the dead end decision 13 forbids — and
  grossing the cap up instead would widen V2-024. The subscribed figure is
  published beside it so a screen can warn where it must not refuse.

The refusal now names what the team can change. With something left to cut:

> Committed spend of $13,899,999.96 exceeds available funds of
> $-61,270,637.48 — $-61,270,637.48 of cash plus $0.00 of financing decided
> this round. Cut $75,170,637.44: your largest reducible commitment is the
> marketing budget at $10,899,999.96. Raising more debt or equity has the same
> effect.

With nothing left to cut:

> Available funds are $-7,431,324.09 — $-7,431,324.09 of cash plus $0.00 of
> financing decided this round — and this round still commits $200,000.00.
> Nothing committed can be cut any further, so raise at least $7,631,324.09 of
> debt or equity on the Finance page before locking.

`rd_costs.largest_reducible_line` picks that line from the committed figures.
Bought research and a completed structure switch are deliberately absent from
its candidates: the report is delivered and the structure switched, so naming
either would tell a team to change something it cannot change.

W-CE3-16 is repaired in the same commit — `total_dividends > 0` guards the
dividend blocker — because it is the same unreachable state and decision 13
rules it out.

**Not weakened, each with its own test:** V2-024 (`funding_requirement`'s
`available_funding` is still opening cash plus new debt as submitted, so no
team's maximum raise moves), the debt-in-distress refusal, the debt-to-equity
ceiling, and the repayment cap. No price, no cap and no competitive rule
changes.

### 3.4 Red, then green

| | Red | Green |
|---|---|---|
| `core.tests.test_lock_always_reachable` (16 new) | 5 failures, 2 errors on the base rule | 16 pass |
| whole game, rounds 3–6 | refused, force-advanced every round | locks every round |

`file:line`: `backend/core/services/rd_costs.py:418`, `:446`,
`backend/core/views/decisions.py:1060`, `:1090`,
`backend/core/engine/financials.py:199`.

---

## 4. W-CE2-03's residue — the deadline (P1, decision 14)

### 4.1 What was left

W-CE2-03 taught the engine's acquisition gate to read the lock's own
affordability answer, and disclosed in its §7.1 what it could not close: a
draft made unaffordable by a plant build or by marketing still resolved in
full. The walkthrough measured it — teams closed at −$6,468,269.34 and
−$7,431,324.09 on drafts the lock had refused with the figures on the page —
and from there neither could lock again, which is why W-CE2-03 and W-CE3-02
are one story.

### 4.2 What a deadline-closed unaffordable draft now does, precisely

`close_round` calls one new service,
`backend/core/services/deadline_affordability.py`, before submissions are
frozen and after the price band, on **drafts only**: a team that locked its own
submission passed this same check at the lock.

It evaluates `rd_costs.budget_assessment` — the function the lock refuses on,
and nothing else — and while the draft does not fit it withdraws the team's own
discretionary commitments in this fixed order, re-asking after each and
**stopping the moment the draft fits**:

1. plant builds
2. platform development requests (and the unfunded draft platform each left)
3. compliance investments
4. the ESG investment
5. market entries
6. promotion and distribution budgets, and sales-team counts
7. the declared budget lines, reduced to the decisions actually made under them

Every one of those is a row the team could itself have withdrawn from a screen
before the lock — W-CE2-02 gave it the controls — so no rule is introduced
that a player could not have applied themselves. Step 7 can only give back
headroom a team declared and did not use: a declared budget is a floor the
affordability rule counts (V2-057) and the engine never charges on its own.

**Queued acquisitions are not withdrawn.** The engine already declines an
unaffordable bid, uncharged and with a notification, and W-CE2-03 deliberately
keeps the decision row as the team's record. So the question is asked with the
acquisition excluded, because withdrawing a plant to pay for a purchase that
will not happen would be the wrong trade.

**If the draft still does not fit** once everything discretionary is gone — a
team whose available funds are simply negative and which raised nothing — it is
closed with nothing discretionary in it. The lock would have refused; the
deadline cannot refuse without stalling the round for everyone (rejected in
W-CE2-03 §7.1(c)); so it spends nothing. `within_available_funds: false` is
recorded on the audit event in that case.

Each withdrawal writes a `DecisionAuditEvent` with `user=None` — actor
`system` on the instructor drill-down, action
`deadline_withdrew_commitments` — carrying the steps applied, the committed
total and the available funds before and after. The team is told, in its own
language, what was withdrawn and that nothing was charged for it.

### 4.3 Whether any stored or hashed value changes

**Yes, for a team whose draft the lock would have refused.** The service
deletes and rewrites decision rows (`decision_plant`, `decision_platform`,
`compliance_investment`, `decision_esg`, `decision_market_entry`,
`decision_marketing`, `decision_budget_allocation`) *before* the round's input
snapshot is taken, so `input_sha256` and every downstream published figure for
that round move. A round in which every team locked its own submission, or in
which every deadline-closed draft already fitted, is byte-identical.

**No section gains or loses a field**, and `MANIFEST_SCHEMA_VERSION` stays at
**7**. `deadline_affordability.py` joins `RESOLUTION_SERVICES` in
`test_manifest_determinism`, so its iteration order is inside the ordering
scan; every queryset it walks is explicitly ordered.

### 4.4 Red, then green

Red taken by replacing the one call in `close_round` with `trimmed = []`:
**9 of the 16 tests in `core.tests.test_deadline_matches_lock_rule` fail** —
the plant is built and charged, the promotion budget is charged, the team
closes the round in the red, no audit event, no notice in either language.
Green: 16 pass. `core.tests.test_deadline_lock_affordability` (the W-CE2-03
suite, including "the decision row is kept as the team's record") still passes
unchanged in substance.

`file:line`: `backend/core/engine/advance_round.py:139-147`,
`backend/core/services/deadline_affordability.py`.

---

## 5. W-CE3-01 — $2,000,000 vanishes (P0, decision 15)

### 5.1 The reproduction, with the figures

The walkthrough's money reconciliation, on four teams: Aurora Devices closes
round 2 at **$13,523,631.84** and opens round 3 at **$11,523,631.84**;
Meridian Tech $18,296,607.20 → $16,296,607.20; Solaris Consumer
$24,566,940.00 → $22,566,940.00; Nova Circuit the same $2,000,000 between
rounds 3 and 4. The amount is always exactly the tax structure's `setup_cost`
(`regional_hub: 2000000`).

Reproduced here as a test: with the defect lines restored, a team that switches
structure in a round it opens with $1,000,000 produces a statement whose
`cash_opening` reads **−$1,000,000.00**.

### 5.2 The cause

`backend/core/engine/costs.py:1165` (as it stood):

```python
if not tts.setup_cost_paid and structure.setup_cost > 0:
    team.cash_on_hand -= structure.setup_cost
```

`process_tax_structure_costs` runs at `advance_round.py:850`;
`generate_financial_statements` reads `cash_opening = team.cash_on_hand` at
`financials.py:147`, eighteen lines later in the pipeline. So the statement's
own identity (`opening + OCF + ICF + FCF == closing`) closed perfectly on every
team in every round and the money was simply not there any more. No calculator
could see it: not `decision_outlays`, not `rd_costs.budget_assessment`, not the
engine's own opex. The team was never told.

This is R36 / V2-088 in a second place —
`views/cc32b_views.py:166-185` says so in as many words about the
organisational-structure switch — and it is repaired the same way.

### 5.3 The repair

`funding_need.tax_structure_setup_charge(team, current_round)` derives the
charge from the row the team's own decision already writes: `adopted_round` is
this round and `current_structure` is what it switched to
(`views/cc32c_views.py:143-153`). No new field. Four things follow, each with a
test:

* the charge and the decision cannot disagree — there is one row and it is the
  decision;
* a round with no switch costs nothing, and an earlier switch is not charged
  again;
* re-resolving recomputes the same figure rather than a cumulative one, which
  the mutable `setup_cost_paid` flag alone could not promise;
* **no hashed field is added**, so `MANIFEST_SCHEMA_VERSION` stays at 7.

`decision_outlays` totals it as `tax_setup`, computed before its submission
guard because a structure is switched from a Finance screen and writes no
decision row. `costs.calculate_operating_expenses` books the same figure into
strategy expense from the same function, outside its own submission guard for
the same reason, and the `_shared == _engine` assertion is **widened over it**
— `TheParityAssertionCoversItTests` fails if a future edit charges it on one
side only. `rd_costs.committed_outlay` counts it, so the affordability rule,
the equity funding rule and every "spent" figure a student reads see it.

`process_tax_structure_costs` keeps the `setup_cost_paid` flag and its log
line and no longer touches cash.

### 5.4 `annual_maintenance_cost` — checked, and it is not the same defect

Decision 15 asked. The answer, with a test class of its own
(`TheMaintenanceCostIsNotTheSameDefectTests`):

`calculate_tax` puts it on `context.tax_structure_maintenance` and
`financials.py:174-176` subtracts it inside `operating_income`, so it reaches
net income, operating cash flow and the closing cash a student reads. **It does
not vanish between rounds** — the statement identity holds with it in. What it
lacks is a line of its own on the served statement, which is W-CE3-04 and is
repaired in §6.

It is deliberately **not** moved into `decision_outlays` and an opex line.
`calculate_tax` builds its deduction total from `context.opex`
(`costs.py:771-777`), so an opex line for the maintenance cost would newly
enlarge the tax deduction and change a team's published tax. That is
calibration, not a bug, and R48 defers calibration. Recorded for the owner in
§12.

### 5.5 Red, then green

Red taken by restoring the three defect lines in `engine/costs.py`:
**8 of the 19 tests in `core.tests.test_tax_structure_setup_charge` fail**,
including `cash_opening` at −$1,000,000 and `strategy_expense` unchanged
against the control team. Green: 19 pass.

### 5.6 One pre-existing crash fixed on the way

`platform_switch_write_off` was bound only inside `if submission:` in
`calculate_operating_expenses` and read unconditionally on the way out. Any
charge owed in a round a team never submitted in therefore raised
`UnboundLocalError` and failed the whole round for every team. R36's charge
could already reach it; decision 15's second one made it reachable in a test.
Initialised with its siblings.

---

## 6. W-CE3-03 and W-CE3-04 — the statement does not add up (P1)

### 6.1 The reproduction, with the figures

Measured on this pass's own six-round game, through the served payload a
browser receives and through the page's own line list read from
`pages/incomeStatementRows.js` (`harness/statement_gap.py`,
`evidence/.../statement-red.json`):

| | worst gap, four teams × six rounds |
|---|---:|
| `gross profit − the lines the PAGE prints − printed net income` | **$2,862,694.58** |
| `gross profit − every expense field the API SERVES − served operating income` | **$615,289.00** |

The page printed Revenue, COGS, Gross Profit, R&D, Marketing, Strategy,
Research, Compliance, Admin, Net Income and Margin and nothing else — not
interest, not tax, not logistics/tariff, not inventory, all four of which the
same API serves on the same row. That is W-CE3-03.

The served gap is W-CE3-04 and is the harder half: `operating_income` also
subtracts depreciation at 10 % of plant book value, the tax structure's
`annual_maintenance_cost`, product-retirement cost, supply-chain disruption
cost and compliance enforcement cost, **none of which is a field of
`RoundResultFinancials`**. The $615,289.00 above is a product retirement with
no field to carry it. `platform_amortization` and `platform_switch_write_off`
are stored columns that were served by nothing at all.

### 6.2 The repair, and what it needed

Served-field only, which is the preferred answer:

* `platform_amortization` and `platform_switch_write_off` — stored already,
  now published;
* `other_operating_expense` — `gross_profit` less every served expense less
  `operating_income`, so it is exactly the charge with no column;
* `other_non_operating_expense` — `operating_income` less interest less tax
  less `net_income`, the tax audit penalty and the realised FX hedge result.

`views/cc15_views.STORED_OPERATING_EXPENSE_FIELDS` names the columns once so
the residual and the page cannot drift. The page prints every served charge,
with `operating_income` as a printed subtotal, and `INCOME_STATEMENT_SUM`
states the identity its own Jest test measures on a served row rather than
trusting the list.

After: page gap **$0.00**, served gap **$0.00**, below-operating-income gap
**$0.00**, across four teams and six rounds
(`evidence/.../statement-green.json`).

### 6.3 STOPPED, and reported

**Naming those five charges one by one requires five new columns on
`RoundResultFinancials`.** The `financials` section is hashed field-for-field
(`manifest_sections.py:493`, no `exclude` mapping), so a new column changes the
section's shape, moves **`MANIFEST_SCHEMA_VERSION` from 7 to 8**, and makes a
v7 hash and a v8 hash of the same state non-comparable — `replay_round`
refuses the comparison by version before it restores anything. That is the
owner's call, not a side effect of a presentation repair, and it is **not
done**. `MANIFEST_SCHEMA_VERSION` is untouched at 7 and
`TheHashedSectionIsUnchangedTests` fails if it moves or if a column appears.

So a team that builds a plant can now find the depreciation *inside* "Other
operating charges" and see that the statement balances, but cannot yet see it
named. That is the residue, and it is the owner's to rule on.

---

## 7. The whole-game proof

Required because unit tests are what missed W-CE3-02. Six rounds, four teams,
every lock pressed through the product's own HTTP routes with a signed-in team
member's bearer token. A round is closed only after every team has locked
itself, and `close_round` reports how many submissions **it** had to lock —
anything but zero is a force-advance.

```
cd handoff_readiness_v2/evidence/walk-ce3-lock-and-money/harness
bash make_db.sh                                   # this pass's own container
cd ../../../../backend && python3 ../handoff_readiness_v2/evidence/walk-ce3-lock-and-money/harness/seed.py
cd ../handoff_readiness_v2/evidence/walk-ce3-lock-and-money/harness
COMPETITION_BACKUP_DIR=$(cd ../runtime/backups && pwd) \
  LLM_GATEWAY_URL=http://127.0.0.1:9/unreachable \
  COMPETITION_REQUIRE_CLEAN_BUILD=false \
  python3 whole_game.py --label green
```

### 7.1 Per-round outcome

| Round | Locks pressed and accepted | Forced by the deadline | Distressed team's closing cash |
|---|---|---:|---:|
| 1 | 4 of 4 | 0 | $38,688,923.44 |
| 2 | 4 of 4 | 0 | **−$61,270,637.48** |
| 3 | 4 of 4 | 0 | $18,683,401.96 |
| 4 | 4 of 4 | 0 | $5,933,606.41 |
| 5 | 4 of 4 | 0 | $1,314,275.21 |
| 6 | 4 of 4 | 0 | $1,227,269.57 |

`total_forced_by_deadline=0 never_locked=[]`. Before the repair, on the same
harness: `total_forced_by_deadline=4`, the distressed team refused in rounds
3, 4, 5 and 6.

### 7.2 The round after the cash went negative, step by step

Round 3, Eclipse Gadgets, opening cash **−$61,270,637.48**:

1. **As played** — refused, naming the marketing budget at $10,899,999.96 as
   the largest reducible commitment.
2. **Stripped** through the real save routes (budgets, promotion, distribution,
   sales teams, compliance, dividend all zero) — still refused, $200,000.00 of
   ESG left standing, shortfall $61,470,637.48.
3. **$61,470,637.48 of new debt** saved through `…/financing/` — refused, and
   told why: *New debt of $61,470,637.48 is not counted: lenders will not
   extend credit while the company is in financial distress. Raise equity
   instead.*
4. **The same amount as equity**, which is what the page just said to do —
   `lock_blockers: []`, `POST …/lock/ → 200`, submission `locked`.

That is decision 13's property demonstrated on a real game: from a state the
walkthrough said was terminal, a sequence of decisions available to the team
makes the lock succeed, and the team is told at each step which one.

### 7.3 Caveats on the proof

The harness drives decisions through the ORM and locks, saves and financing
through HTTP; it is not a browser. The route to negative cash is an ordinary
operational loss (stock built and not sold), not a deadline-closed
unaffordable draft — that route is closed by decision 14, which is the point.

---

## 8. Every stored or hashed value that changes

`MANIFEST_SCHEMA_VERSION` stays at **7**. No section gains, loses or renames a
field. What moves, and when:

| Change | When it moves a stored or hashed value |
|---|---|
| Decision 14, the deadline withdrawal | **Hashed.** Decision rows are deleted or rewritten before the input snapshot, for a team whose draft the lock would have refused: `decision_plant`, `decision_platform`, `compliance_investment`, `decision_esg`, `decision_market_entry`, `decision_marketing`, `decision_budget_allocation`. `input_sha256`, `output_sha256` and every published figure for that round move. A round in which every deadline-closed draft already fitted is byte-identical. |
| Decision 15, the tax setup cost | **Hashed**, for a team that switched structure in the resolved round: `financials.cash_opening` rises by the setup cost (it is no longer removed before the statement is read), `strategy_expense` rises by it, `calculate_tax`'s deduction total rises with strategy expense, and `operating_income`, `pre_tax_income`, `net_income`, `tax_expense`, `operating_cash_flow` and `cash_closing` follow. A round with no switch is byte-identical. |
| Decision 13, the affordability rule | **Hashed only through `engine/acquisitions`.** That gate reads `budget_assessment(...)['within_cash']`, so a draft that now fits because the team decided financing has its acquisition fulfilled where it previously did not. Everything else decision 13 touches is a blocker, a sentence or a served field. |
| Decision 13, the engine refactor | **No change.** `financing_effect` reproduces `generate_financial_statements`' financing arithmetic exactly; `test_engine`, `test_equity_issuance` and `test_manifest_determinism` pass unchanged. |
| W-CE3-03 / W-CE3-04 | **No change.** Both new fields are computed at serialisation from figures already published. |
| `platform_switch_write_off` initialisation | **No change** for any round that resolved before, because a round that reached the unbound read crashed rather than producing a value. |

Replay evidence for a round carrying either a deadline-withdrawn draft or a
tax-structure switch is invalidated by this branch and must be regenerated
against its commit. There are no live games (R41).

---

## 9. zh-CN — new sentences, in one table

| Where | Key | English | 中文 |
|---|---|---|---|
| `participant_messages.py` | `committed_spend_exceeds_available_funds` | Committed spend of {committed} exceeds available funds of {available} — {cash} of cash plus {financing} of financing decided this round. Cut {shortfall}: your largest reducible commitment is {line} at {amount}. Raising more debt or equity has the same effect. | 承诺支出 {committed} 超过可用资金 {available}——现金 {cash} 加上本回合已决定的融资 {financing}。需要削减 {shortfall}：目前可削减的最大承诺是{line}，金额 {amount}。增加债务或股权融资也可达到同样效果。 |
| `participant_messages.py` | `available_funds_short_with_nothing_to_cut` | Available funds are {available} — {cash} of cash plus {financing} of financing decided this round — and this round still commits {committed}. Nothing committed can be cut any further, so raise at least {shortfall} of debt or equity on the Finance page before locking. | 可用资金为 {available}——现金 {cash} 加上本回合已决定的融资 {financing}——本回合仍承诺支出 {committed}。已承诺的支出无法再削减，请在财务页面至少增加 {shortfall} 的债务或股权融资后再锁定。 |
| `participant_messages.py` | `new_debt_refused_in_distress` | New debt of {requested} is not counted: lenders will not extend credit while the company is in financial distress. Raise equity instead. | 新增债务 {requested} 不计入可用资金：公司处于财务困境期间，贷款方不会继续授信。请改为进行股权融资。 |
| `participant_messages.py` | `budget_rd` | the R&D budget | 研发预算 |
| `participant_messages.py` | `budget_marketing` | the marketing budget | 营销预算 |
| `participant_messages.py` | `budget_strategy` | the strategy budget | 战略预算 |
| `participant_messages.py` | `budget_research` | the market-research budget | 市场调研预算 |
| `participant_messages.py` | `committed_platform_development` | platform development | 平台开发支出 |
| `participant_messages.py` | `committed_plant` | plant construction | 工厂建设支出 |
| `participant_messages.py` | `committed_acquisitions` | the queued acquisition | 已排队的收购 |
| `participant_messages.py` | `committed_compliance` | compliance investment | 合规投入 |
| `participant_messages.py` | `committed_talent` | payroll and talent | 薪酬与人才支出 |
| `participant_messages.py` | `deadline_withdrew_commitments` | The round closed while {committed} was committed against available funds of {available}, which is the same reason the round could not be locked. These commitments were withdrawn and nothing was charged for them: {withdrawn}. Every other decision was resolved as submitted. | 本回合结束时，已承诺支出 {committed}，而可用资金为 {available}，这也是本回合无法锁定的原因。以下承诺已撤回，且未产生任何费用：{withdrawn}。其余决策均按提交内容结算。 |
| `participant_messages.py` | `withdrawn_plant_builds` | plant construction | 工厂建设 |
| `participant_messages.py` | `withdrawn_platform_developments` | platform development requests | 平台开发申请 |
| `participant_messages.py` | `withdrawn_compliance_investments` | compliance investment | 合规投入 |
| `participant_messages.py` | `withdrawn_esg` | environmental and social investment | 环境与社会投入 |
| `participant_messages.py` | `withdrawn_market_entries` | market entries | 市场进入 |
| `participant_messages.py` | `withdrawn_promotion_budgets` | promotion, distribution and sales teams | 促销、渠道与销售团队支出 |
| `participant_messages.py` | `withdrawn_declared_budgets` | the unused part of the declared budgets | 已申报预算中未动用的部分 |
| `locales/*.json` | `financial_reports.logistics_label` | Logistics & tariffs | 物流与关税 |
| `locales/*.json` | `financial_reports.inventory_cost_label` | Inventory holding | 库存持有成本 |
| `locales/*.json` | `financial_reports.platform_amortization_label` | Platform amortization | 平台摊销 |
| `locales/*.json` | `financial_reports.platform_write_off_label` | Platform switch write-off | 平台切换减值 |
| `locales/*.json` | `financial_reports.other_operating_label` | Other operating charges | 其他营业费用 |
| `locales/*.json` | `financial_reports.interest_label` | Interest | 利息费用 |
| `locales/*.json` | `financial_reports.tax_label` | Tax | 所得税 |
| `locales/*.json` | `financial_reports.other_non_operating_label` | Other charges | 其他费用 |

One existing sentence is reworded because the figure it names changed:
`budget.committed_of_cash` now reads "of {{cash}} available funds" /
"可用资金共 {{cash}}", because the bar states available funds, not cash.

`core.tests.test_zh_terminology` passes (回合 for round; no retired term).
Whether the new short labels read naturally to a native speaker is §12.

---

## 10. Commands and results

All backend runs under `flock -w 3600 /tmp/globalstrat-backend-test.lock` with
`TEST_POSTGRES_READY_SECONDS=1500`, from `backend/`.

| Command | Result |
|---|---|
| `scripts/test-postgres core.tests.test_lock_always_reachable` | 16 tests, OK (red: 5 failures, 2 errors) |
| `scripts/test-postgres core.tests.test_deadline_matches_lock_rule` | 16 tests, OK (red: 8 failures, 1 error) |
| `scripts/test-postgres core.tests.test_tax_structure_setup_charge` | 19 tests, OK (red: 8 failures) |
| `scripts/test-postgres core.tests.test_served_income_statement` | 8 tests, OK |
| `scripts/test-postgres` × the 15 focused labels (see below) | 374 tests, OK |
| `scripts/test-postgres core.tests.test_zh_terminology` + served statement | 11 tests, OK |
| `scripts/test-postgres core --parallel 8` | **1718 tests, 117.1 s, OK** |
| `handoff_readiness_v2/evidence/…/harness/whole_game.py --label red` | `total_forced_by_deadline=24 never_locked=[…]` then, with the corrected driver, `=4` with the distressed team refused in rounds 3–6 |
| `handoff_readiness_v2/evidence/…/harness/whole_game.py --label green` | `total_forced_by_deadline=0 never_locked=[]` |
| `handoff_readiness_v2/evidence/…/harness/statement_gap.py … red` | `worst_page_gap=2862694.58 worst_served_gap=615289.0` |
| `handoff_readiness_v2/evidence/…/harness/statement_gap.py … green` | `worst_page_gap=0.00 worst_served_gap=0.00 worst_below_operating_income_gap=0.00` |
| `CI=true npx react-scripts test --watchAll=false` | 52 suites, **499 tests, all pass** |
| `python3 backend/scripts/check-participant-strings` | PASS, 5792 units, 0 findings |
| `python3 backend/scripts/check-participant-strings-selftest` | 34 ok, 0 failed |
| `CI=false GENERATE_SOURCEMAP=false npx react-scripts build` | builds; **54 ESLint warnings against a baseline of 55** — the ratchet holds |

The 15 focused labels: `test_tax_structure_setup_charge`,
`test_deadline_matches_lock_rule`, `test_deadline_lock_affordability`,
`test_lock_always_reachable`, `test_committed_spend_one_calculator`,
`test_summary_blockers_match_lock`, `test_equity_issuance`,
`test_compliance_investment_charge`, `test_participant_messages`,
`test_rd_costs`, `test_org_transition_charge`, `test_engine`,
`test_manifest_determinism`, `test_audit_integrity`,
`test_silent_section_saves`, `test_plant_collision`.

### 10.1 The full suite

```
cd backend && TEST_POSTGRES_READY_SECONDS=1500 \
  flock -w 3600 /tmp/globalstrat-backend-test.lock \
  scripts/test-postgres core --parallel 8
```

`Ran 1718 tests in 117.076s` — **OK**. Run once, after the last runtime edit,
and no runtime code changed afterwards. The only commits after it are this
report and the regenerated string inventory.

### 10.2 Existing tests whose expectation this branch changes

Each is a sentence or a figure a ruling moved, not a rule relaxed:

| Test | What changed, and why |
|---|---|
| `test_committed_spend_one_calculator` (2) | the affordability sentence, reworded by decision 13; the same figures |
| `test_compliance_investment_charge` (3) | the same sentence, built from the new catalogue key |
| `test_rd_costs` (1) | the same sentence |
| `test_deadline_lock_affordability` (1) | the same sentence, in the control that quotes it |
| `test_participant_messages` (1, plus 1 new) | the hand-built assessment gains the keys the sentence reads |
| `test_summary_blockers_match_lock` (1) | the projected-cash sentence merged into the affordability one; the invariant it guards — Summary and lock refuse identically with no financing row — is asserted unchanged |
| `test_equity_issuance` (1, plus 1 new) | the share-pricing guard follows the arithmetic into `funding_need.financing_effect`; a new test asserts the engine keeps no second copy |
| `test_manifest_determinism` (1) | `deadline_affordability.py` added to `RESOLUTION_SERVICES` |

---

## 11. Proposed register text

Not written to the register by this branch, as instructed.

* **W-CE3-02 / W-CE-23's remainder** — *Repaired at `a97f055`, under
  integrator decision 13.* The affordability rule compared committed spend
  with cash on hand, so a team whose cash had gone negative could never lock
  again and raising debt did not move the figure. Available funds are now cash
  plus the financing the team has decided this round, netted the way the engine
  will actually apply it through one new shared calculator
  (`funding_need.financing_effect`, which the engine also calls), and the
  refusal names the funds, the financing counted, the shortfall and the largest
  commitment still open to the team — or, when nothing is left to cut, the
  raise needed. V2-024, the debt-in-distress refusal, the debt ceiling and the
  repayment cap each keep a test that fails if they are weakened.
  `test_lock_always_reachable`, 16 tests, plus a six-round whole-game proof
  through the real routes. **Changes a hashed value** only through
  `engine/acquisitions`, which reads the same answer.
* **W-CE3-16** — *Repaired at `a97f055`.* A dividend of $0.00 no longer
  "exceeds projected equity" for a team whose projected equity is negative.
  The same unreachable state decision 13 rules out.
* **W-CE2-03's residue** — *Repaired at `57e9e4f`, under integrator decision
  14.* The deadline applies the lock's own affordability rule, withdrawing the
  team's discretionary commitments in one stated order until the draft fits and
  stopping there; acquisitions keep W-CE2-03's own treatment. Recorded on the
  audit trail as a system action and notified in the team's language.
  `test_deadline_matches_lock_rule`, 16 tests. **Changes a hashed value** for a
  round carrying such a team; schema version 7 kept.
* **W-CE3-01** — *Repaired at `e91ead6`, under integrator decision 15.* The tax
  structure's setup cost was taken from `team.cash_on_hand` before the
  statement read `cash_opening`, so $2,000,000 left four teams between rounds
  with no line anywhere. It is now booked at resolution through
  `funding_need.tax_structure_setup_charge`, which both the shared calculator
  and the engine read, covered by the widened parity assertion and counted in
  committed spend — R36 / V2-088's pattern, a second time.
  `test_tax_structure_setup_charge`, 19 tests. The recurring
  `annual_maintenance_cost` was checked and does **not** have this defect; it
  is inside operating income. **Changes a hashed value** for a team that
  switched structure in the resolved round; schema version 7 kept.
* **W-CE3-03** — *Repaired at `0bb0d13`.* The income statement on the page now
  prints every charge the API serves, with operating income as a subtotal, and
  the printed lines sum to the printed net income. Measured on a six-round
  game: worst gap $2,862,694.58 → $0.00. `incomeStatementRows.test.js`.
* **W-CE3-04** — *Partly repaired at `0bb0d13`; the rest needs the owner.* The
  served statement is complete and self-consistent: the two stored columns
  nothing published are published, and the charges with no column are served as
  `other_operating_expense` and `other_non_operating_expense`, computed from
  published figures. Worst served gap $615,289.00 → $0.00. **Naming
  depreciation, tax-structure maintenance, product retirement, supply-chain
  disruption and compliance enforcement individually requires five columns on
  the hashed `financials` section and moves MANIFEST_SCHEMA_VERSION from 7 to
  8. Not done; the owner's call.**

---

## 12. What needs someone this builder is not

Only what needs the owner, the production host, a browser, or a native
speaker.

1. **Owner — naming the five charges on the statement.** §6.3. Five columns on
   a hashed section, schema version 7 → 8, and every replay comparison across
   the boundary refused by version. The statement adds up today; it does not
   yet name depreciation.
2. **Owner — the tax structure's `annual_maintenance_cost` in committed
   spend.** §5.4. It is charged and visible inside operating income, but the
   affordability rule does not count it, and moving it into an opex line would
   newly enlarge the tax deduction in `calculate_tax` and change a published
   result. Calibration, deferred by R48.
3. **Owner — the withdrawal order at the deadline.** §4.2. It is a rule a
   player can feel, decided by this builder under decision 14 in the direction
   of least change and stated in one place, as R48 §4 requires. The owner may
   want a different order, or a different terminal state for a team that can
   withdraw nothing more.
4. **A browser.** Nothing in this branch has been driven in a real browser in
   either role or either language. The Financial Reports income statement now
   has 20 columns; whether it reads well at the widths a student uses is a
   question for the walkthrough, not for Jest.
5. **A native speaker.** The 28 new zh-CN strings in §9, particularly the two
   long affordability sentences and the eight short statement labels.
