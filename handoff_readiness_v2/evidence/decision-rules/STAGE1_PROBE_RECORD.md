# GSP-CRV2-10 Stage 1 — probe record

**Purpose.** Part A of `handoff_readiness_v2/RULES_AND_CALIBRATION_ASSESSMENT.md`
was written from source reading only and says so: *"Nothing was executed, no
database was touched."* Stage 1 confirms or withdraws each of its seven claims by
probe against a running isolated stack, through **both** supported submission
surfaces, and records the payload, the response and the resulting database rows.

**Boundary.** No runtime code was written, changed or repaired. Nothing under
`backend/core/` or `frontend/` was touched. The only files added are this record,
the captured evidence and the harness that produced it. Repair is Stage 2 and is
gated on GSP-CRV2-08 clearing its audit.

---

## Verdicts

| # | Part A item | Verdict | Proposed severity |
|---|---|---|---|
| A1 | Platform price is client-set | **Reproduced** — both surfaces, both methods, all three generations | **P0** |
| A1b | Feature price is client-set | **Reproduced** — both surfaces, both methods | **P0** |
| A2 | Platform cost escapes the budget checks | **Reproduced**, with a positive control | **P1** |
| A3 | A platform can be ready in the round it was created | **Reproduced, and worse than read** | **P1** |
| A4 | There is no price band | **Reproduced** (confirmed absent) | **P1** |
| A6 | Cohort caps are not enforced | **Reproduced** — 17 teams against `max_teams` 8, 8 members against `team_size_max` 5 | **P1** |
| D1 | `end_of_round` retirement leaves the market links active | **Reproduced**, and inert today | **P2** |

Nothing was withdrawn. Seven of seven reproduced. Two reproduced *differently*
from the reading, both in the direction of being worse (A3, and A1's blast
radius); each is written up under its own heading below.

Four findings that Part A did not anticipate are in
[Not anticipated by Part A](#not-anticipated-by-part-a). One of them —
**the lock validator is not a gate** — changes what Stage 2 has to build, so it
is stated before the item-by-item detail.

### Say this out loud: the free platform will not keep

A team can own **any unlocked platform generation, at any generation's authored
price, for $0**, through either supported API, using either `method`, and the
platform is **active in the round it was committed**. Measured, not reasoned:
Gen 3 carries an authored `development_cost` of **$25,000,000** and a
`license_cost` of **$55,000,000`**; two teams took it for `committed_cost: 0` and
were charged `rd_expense = 0.00`. Feature levels behave the same way: one team
took **$15,610,000** of authored level-cost to three Gen-1 ceilings for
`amount: 0, calculated_cost: 0`.

This is not a value a competition can absorb. It is available to any participant
who opens the network tab, it needs no timing, no race and no operator error, and
nothing in the product records that it happened — the P&L simply shows $0,
because $0 is what the team declared. **A GO issued against this rule set is a GO
that has to be withdrawn.** The programme owner's decision about interrupting
CRV2-08 should be made against that sentence, not against the table above.

### And this one, because it changes Stage 2's shape

`_full_validate` — the lock validator — is the only place in the product that
holds the unlock-round rule, the duplicate-platform rule, the cash rule, the
`rd_budget` rule, the portfolio-completeness rule, the marketing-coverage rule,
the debt-ratio rule and the negative-projected-cash rule. **It runs only when a
team presses Lock.** Closing a round calls `_lock_all_submissions`
(`core/engine/advance_round.py:146-175`), which locks every draft exactly as it
stands and validates nothing, and the engine then resolves it.

Proven here, in one team, in one round: a Gen 3 platform (`unlock_round: 5`) was
submitted in **round 1**, the lock validator refused it in as many words —
`Platform "Gen 3 — AI-Native Sustainable Platform" not unlocked yet (unlocks
round 5).` — the team did not lock, the operator closed the round, and the team
finished round 1 owning an **active Gen 3 platform, `activated_round: 1`**.

So a Stage-2 repair that only strengthens `_full_validate` repairs nothing for a
team that never presses the button. The engine precondition the handoff already
specifies — the V2-018 shape at `advance_round.py:396-411` — is not
belt-and-braces here. It is the only layer that runs on every path.

---

## Environment and provenance

| | |
|---|---|
| Revision under probe | `5a777bad5ac425e3483315006acc992c52e9ad2b` (`crv2-10-13-rules-and-calibration-specs`) |
| Worktree | `.claude/worktrees/agent-aa23a70e43fabef2c`, isolated; main checkout untouched |
| Working tree at run time | dirty — **only** `handoff_readiness_v2/evidence/decision-rules/` (this record, the evidence, the harness). `git status --porcelain` showed no other path. No runtime source changed. |
| Database | `gsp_crv210_stage1_20260831030546` on `192.168.50.38:5432`, created for this run and dropped after it |
| Production database | `globalstrat_plus` — **not touched**. `stack.py` names it in a constant and refuses to `migrate`, create, drop or probe it. |
| Backend | gunicorn, `GLOBALSTRAT_ENV=production`, `globalstrat.wsgi:application`, pid 4052235 |
| Port | **57085, claimed at run time** from the kernel. No constant appears anywhere in the harness. |
| Run window | 2026-08-31T03:05:46 → 03:09:11 UTC, 6 game rounds |
| Evidence | `stage1-probes.json` (payloads, responses, and a full row snapshot after every round), `stage1-summary.txt` |
| Harness | `harness/stack.py`, `harness/fixture_bodies.py`, `harness/probe_run.py`, `harness/summarise.py` |

### Why the port matters, and what was asserted before the first probe

Port **8002 on this host carries a gunicorn serving the live `globalstrat_plus`
database** (`ss -ltnp` at the time of the run: `0.0.0.0:8002 users:(("gunicorn",
pid=1140145,…))`). GSP-CRV2-08 configured a stack on that fixed port, failed to
bind, died, and its requests fell through to production while it believed it was
talking to its own fixture — caught only by a login failure.

`stack.assert_identity` therefore refuses to return before the first probe unless
**both** of these hold, because either one alone has already failed on this host:

1. a fixture identity authenticates through this stack's own origin —
   `POST http://127.0.0.1:57085/api/auth/login/` as `crv210_student_1` returned
   **200** with an access token; and
2. the database name reported by a Django process started with this run's
   settings equals the database this run created —
   `database_reported: "gsp_crv210_stage1_20260831030546"`.

Both are recorded in `stage1-probes.json → identity_check`.

Isolation from the concurrent CRV2-08 work: a uniquely named database per run, a
run-time port, and no writes to `gsp_crv208_disputes` or to the main working
tree. No shared test database was used, so no host runner lock was required; the
harness never runs the Django suite.

### One thing the run did reach outside itself

Phase 2 narrative generation called the configured DashScope endpoint
(`https://dashscope-intl.aliyuncs.com/...`) during round processing, because the
API key is present in the environment. That is the product's ordinary behaviour
and it writes only into this run's own database. Noted so the record is complete,
not as a finding.

---

## The fixture

`harness/fixture_bodies.seed()`:

- `load_all_scenarios`, then `initialize_game --scenario <Consumer Electronics
  2026> --teams 8`. Game id 1, section id 1, round 1 open, round 0 bootstrapped.
- Eight teams, ids 1–8, each with $50,000,000 cash, an **active Gen 1 platform**
  and two starter products in NA (market id 6). Starter profiles cycle through
  the four authored ones.
- `crv210_instructor` owns the course behind the section, so instructor-scoped
  routes answer for the right reason.
- Section caps restated to the model defaults under test:
  `max_teams=8, team_size_min=3, team_size_max=5`.
- Platform generations as authored: Gen 1 id 4 (`unlock_round 0`,
  `development_cost 5,000,000`, `license_cost 8,000,000`,
  `development_rounds 0`); Gen 2 id 5 (`unlock 2`, `15,000,000` / `35,000,000`,
  `rounds 2`); Gen 3 id 6 (`unlock 5`, `25,000,000` / `55,000,000`, `rounds 2`).

**One declared piece of ORM setup, which is not a probe result.** Team 8's
starter Gen 1 platform (id 8) was set to `status='retired'` before play. Every
team is initialised owning the starting generation and
`_process_platform_development` skips a generation the team already holds, so a
`development_rounds: 0` generation is otherwise unreachable through the API on a
fresh team and A3's first half could not be asked at all. Everything else in the
run — every decision, every lock, every lifecycle action — went through the HTTP
API.

Team assignment, one probe per team so a round's engine consequences can be read
per item:

| Team | id | Carries |
|---|---|---|
| T1 | 1 | A1, whole-submission surface, `in_house` |
| T2 | 2 | A1, per-type surface, `license` |
| T3 | 3 | A1b, whole-submission surface, `in_house` |
| T4 | 4 | A1b, per-type surface, `license` |
| T5 | 5 | A2, and the deadline-bypass probe |
| T6 | 6 | A4 |
| T7 | 7 | D1 |
| T8 | 8 | A3 |

---

## A1 — the platform price is set by the client. **Reproduced. Proposed P0.**

### Payloads and responses

Whole-submission surface, T1, round 2:

```
POST /api/games/1/teams/1/decisions/round/2/
{"platform_developments": [{"platform_generation": 5, "method": "in_house",
                            "committed_cost": "0", "platform_name": "T1 free Gen2",
                            "feature_levels": {}}]}
→ 200
```

Per-type surface, T2, round 2:

```
PATCH /api/games/1/teams/2/decisions/round/2/platforms/
[{"platform_generation": 5, "method": "license", "committed_cost": "0",
  "platform_name": "T2 free Gen2", "feature_levels": {}}]
→ 200
```

Repeated in round 5 against **Gen 3, the most expensive unlocked generation**, on
both surfaces: `platform_generation: 6`, `committed_cost: "0"`, `in_house` on T1
and `license` on T2 — both **200**.

### Resulting rows

`team_platform`, final snapshot:

| Team | Generation | `status` | `activated_round` | Authored `development_cost` | Authored `license_cost` | `capitalized_cost` |
|---|---|---|---|---|---|---|
| T1 | Gen 2, `in_house` | active | 2 | $15,000,000 | $35,000,000 | $0 |
| T1 | Gen 3, `in_house` | active | 5 | $25,000,000 | $55,000,000 | $0 |
| T2 | Gen 2, `license` | active | 2 | $15,000,000 | $35,000,000 | $0 |
| T2 | Gen 3, `license` | active | 5 | $25,000,000 | $55,000,000 | $0 |

`round_result_financials.rd_expense`, T1 and T2, every round 0–6: **0.00**.
`platform_amortization`: 0.00 (`capitalize_platform_development` is `false` in
this scenario, so the cost would have gone to `rd_expense`; there was no cost).
T2's closing cash after six rounds is **$97,952,547.83**, having acquired
$90,000,000 of authored platform for nothing.

### What the server itself says the price is

The same server, asked in the same round through the supported read endpoint
(`GET /api/games/1/teams/1/context/rd/`), publishes the authored prices and the
whole per-level cost schedule:

```
available_generations[0] = {"id": 4, "name": "Gen 1 — Standard Electronics",
  "development_cost": 5000000.0, "development_rounds": 0,
  "license_cost": 8000000.0, "team_already_owns": true, ...
  "features": [{"feature_id": 36, "code": "processing_power", "ceiling": 14,
    "cost_schedule": [{"level": 1, "incremental_cost": 150000.0, ...}, ...]}]}
```

So the authoritative figure exists, is computed server-side, and is sent to the
browser for display — and then the browser sends a number back and the server
charges that one. `frontend/globalstrat-frontend/src/pages/RDPage.js:66-69`
computes `baseCost` from `license_cost` or `development_cost`, `:69` adds the
feature cost, and `:94` posts it as `committed_cost`. Part A's file:line claims
here are accurate.

Two details worth carrying into Stage 2, both of which the probe surfaced:

- The `method` multiplier (`license` 2.5, `partnership` 1.6) and the
  `overBudget` check exist **only in the browser** (`RDPage.js:62-63, :70`). Server
  side, `method` changes neither the price charged nor the lead time — T1
  (`in_house`) and T2 (`license`) received identical treatment in every respect
  except the string stored on the row.
- `TeamPlatform.development_method` stores `"license"`, which is not one of that
  model's declared choices (`'in_house' | 'licensed' | 'partnership'`,
  `core/models/team_state.py:19-22`). `DecisionPlatformDevelopment.METHOD_CHOICES`
  spells it `'license'` and `rd_processing.py:99` copies it straight across.
  Cosmetic today; listed under [N4](#n4).

### Severity

**P0.** Reachable through both supported APIs by an ordinary participant, with no
timing, no race and no operator involvement; it changes the competitive outcome
directly; and it leaves no trace, because the P&L faithfully reports the $0 the
team declared.

---

## A1b — the feature price is set by the client. **Reproduced. Proposed P0.**

### Payloads and responses

Whole-submission surface, T3, round 2, `in_house`:

```
POST /api/games/1/teams/3/decisions/round/2/
{"rd_investments": [
  {"team_platform": 3, "feature": 39, "method": "in_house", "amount": "0",
   "target_level": 10, "calculated_cost": "0"},
  {"team_platform": 3, "feature": 37, "method": "in_house", "amount": "0",
   "target_level": 12, "calculated_cost": "0"},
  {"team_platform": 3, "feature": 38, "method": "in_house", "amount": "0",
   "target_level": 14, "calculated_cost": "0"}]}
→ 200
```

Per-type surface, T4, round 2, `license`:

```
PATCH /api/games/1/teams/4/decisions/round/2/rd/
[{"team_platform": 4, "feature": 37, "method": "license", "amount": "0",
  "target_level": 12, "calculated_cost": "0"},
 {"team_platform": 4, "feature": 38, "method": "license", "amount": "0",
  "target_level": 14, "calculated_cost": "0"},
 {"team_platform": 4, "feature": 36, "method": "license", "amount": "0",
  "target_level": 14, "calculated_cost": "0"}]
→ 200
```

Every `target_level` is the Gen-1 ceiling for that feature.

### Resulting rows

T4 (`license`, immediate effect), `team_platform_feature_level`:

| Feature | Level after round 1 | Level after round 2 | Gen-1 ceiling | Authored cost of those levels | Charged |
|---|---|---|---|---|---|
| `battery_life` | 8 | **12** | 12 | $2,760,000 | $0 |
| `durability` | 6 | **14** | 14 | $4,600,000 | $0 |
| `processing_power` | 3 | **14** | 14 | $8,250,000 | $0 |
| | | | | **$15,610,000** | **$0.00** |

T3 (`in_house`, `time_lag_rounds: 1`) took the delayed path. After round 2,
`pending_feature_gain` held `app_ecosystem +8.0`, `battery_life +3.0`,
`durability +2.0`, all `applies_round: 3`, all `applied: false`. After round 3 all
three are `applied: true` and the levels read `app_ecosystem 10`,
`battery_life 12`, `durability 14` — the ceilings. Authored cost of those levels:
$3,900,000 + $2,160,000 + $1,450,000 = **$7,510,000**. `rd_expense` for T3 in
every round: **0.00**.

The authored figures above are computed from `feature_level_cost`, the same table
`RDContextView._build_cost_schedule` (`core/views/decisions.py:1136-1155`) reads
for display; `harness/summarise.py` shows the arithmetic.

Part A's reading of `core/engine/rd_processing.py:192-215` is exactly right: the
level-based branch reads `target_level` and neither `amount` nor
`calculated_cost`. Both `method` values take that branch. The dollar-based
fallback at `:217+` is the only code that converts money into level gain, and no
payload a current client sends reaches it.

One thing the reading did not say, and the run shows: the R&D **read** endpoint
echoes the team's own number back as the cost. `RDContextView` builds
`current_investments[].cost` as `inv.calculated_cost if inv.calculated_cost else
inv.amount` (`core/views/decisions.py:1389`), so a team that submits 0 also *sees*
0 on its own R&D page. There is no screen in the product on which this looks
wrong.

### Severity

**P0**, same reasoning as A1. It is arguably the more valuable of the two,
because feature levels are what the demand engine actually scores.

---

## A2 — platform cost escapes both budget checks. **Reproduced, with a positive control. Proposed P1.**

### Payloads and responses

T5, round 3. Cash on hand at the start of the round: **$49,712,336.85**.
`rd_budget` declared: $2,000,000.

```
POST  /api/games/1/teams/5/decisions/round/3/
{"platform_developments": [{"platform_generation": 5, "method": "in_house",
  "committed_cost": "999999999999.00",
  "platform_name": "T5 trillion dollar Gen2", "feature_levels": {}}]}
→ 200

PATCH /api/games/1/teams/5/decisions/round/3/platforms/
[ …the same row… ]
→ 200

POST  /api/games/1/teams/5/decisions/round/3/lock/   {}
→ 200   locked_at 2026-08-31T03:07:47.097779Z, locked_by 6
```

The submission was completed first (portfolio, marketing for both active
product-markets, ESG) so that `_full_validate` ran its whole list rather than
stopping early. It reached the end and passed. Round 3 was chosen because rounds
2, 4, 6 and 8 each carry a mandatory communication assignment, and the validator
refuses on that before it reaches anything this probe is asking about.

### The positive control

The same team, the same round, the same submission, one field moved. An
instructor unlock, then the identical figure placed in `rd_budget` — a field the
checks *do* read — and a second lock:

```
PATCH /api/games/1/teams/5/decisions/round/3/budget/
{"rd_budget": "999999999999.00", "marketing_budget": "0", "strategy_budget": "0"}
→ 200

POST  /api/games/1/teams/5/decisions/round/3/lock/   {}
→ 400
{"detail": "Validation failed.", "errors": [
  "Total budget ($999,999,999,999.00) exceeds available cash ($49,712,336.85).",
  "Marketing spend ($1,200,000.00) exceeds marketing budget ($0.00).",
  "Projected ending cash is negative ($-999,950,287,662.15). Increase revenue or raise financing."]}
```

So the checks at `core/views/decisions.py:548-552` and `:555-561` work. They are
blind to `committed_cost`, not broken. That distinction is the point of the
control and it is what makes this a P1 rather than a note.

The budget was then restored to baseline and the submission re-locked, so the
round resolved from the trillion-dollar commitment.

### Resulting rows

`round_result_financials`, T5, round 3: `rd_expense = 999,999,999,999.00`.
T5's `cash_on_hand` after six rounds: **−$999,955,263,272.15**.

Nothing refused it at any point: not the serializer (V2-018's guard is `>= 0`,
and this is positive), not the lock validator, not the engine precondition
(`persisted_violations` scans for negatives only), not the funding rule
(`funding_need.assess_submission` runs on the equity path and this submission
carried no financing row). A team can commit an arbitrary figure and the engine
will book it.

Part A's third observation holds too: the budget-vs-cash rule is written three
times (`:548`, `:888`, `:1015`) and only `:1015` includes `research_budget`. That
is D2 and belongs to GSP-CRV2-13; Stage 2 of this handoff reconciles them.

### Severity

**P1.** It is not the free-platform P0 — a team gains nothing by overcommitting —
but it is the same missing join seen from the other side, and it puts the ledger
into a state no rule prevents and no screen explains.

---

## A3 — a platform can be ready in the round it was created. **Reproduced, and worse than the reading. Proposed P1.**

### The `development_rounds: 0` half — exactly as read

T8, round 1, at the **authored** price (this probe is about timing, not price):

```
POST  /api/games/1/teams/8/decisions/round/1/
{"platform_developments": [{"platform_generation": 4, "method": "in_house",
  "committed_cost": "5000000.0", "platform_name": "T8 Gen1 rebuild",
  "feature_levels": {}}]}
→ 200
PATCH /api/games/1/teams/8/decisions/round/1/platforms/   [ …same row… ]  → 200
```

Resulting `team_platform` row: `status='active'`,
`development_started_round=1`, `development_rounds_remaining=-1`,
`activated_round=1`. `rd_expense` for T8 in round 1: **$5,000,000.00** — the
authored cost, because that is what was submitted.

`-1` is the create-then-decrement Part A described: the platform is created with
`development_rounds_remaining = 0` and the advance loop in the *same function
call* decrements it below zero and flips it to `active`
(`core/engine/rd_processing.py:96-110`).

### The `development_rounds: 2` half — reproduced differently

Part A predicted "the authored 2 behaves as 1: an off-by-one." Measured, **the
authored 2 behaves as 0**. Every `development_rounds: 2` platform in this run
became active in the round it was committed:

| Team | Generation | Authored `development_rounds` | Started | Remaining | `activated_round` |
|---|---|---|---|---|---|
| T1 | Gen 2 | 2 | 2 | 0 | **2** |
| T2 | Gen 2 | 2 | 2 | 0 | **2** |
| T1 | Gen 3 | 2 | 5 | 0 | **5** |
| T2 | Gen 3 | 2 | 5 | 0 | **5** |
| T5 | Gen 2 | 2 | 3 | 0 | **3** |
| T5 | Gen 3 | 2 | 1 | 0 | **1** |

The round that should have been waited is removed by the
organisational-structure speed modifier at
`rd_processing.py:83-95`, which the reading noted only as a swallowed exception
(D4). Every team is initialised on the **Centralized** structure
(`initialize_game.py:226-235`), whose authored `decision_speed_modifier` is
**1.10**. So `dev_rounds = max(1, floor(2 / 1.10)) = 1`, and the same call then
decrements that 1 to 0 and activates the platform. The modifier is not silently
failing here — it is applying, and its arithmetic plus the create-then-decrement
removes the wait entirely.

The consequence for Stage 3 is concrete: **no platform in this scenario, at any
generation, on the default organisational structure, ever waits a round.** The
`development_rounds` numbers in all three scenario files currently mean nothing
at all.

### Severity

**P1.** It is a rules defect rather than an exploit — a team must still commit
the decision — but it removes the entire R&D lead-time mechanic, which is one of
the things the simulation is for. Stage 3 already owns the repair; this record
adds that the fix must handle the speed modifier, not only the decrement, and
that a floor of 1 round has to survive `floor(dev_rounds / speed)`.

---

## A4 — there is no price band. **Reproduced (confirmed absent). Proposed P1.**

T6's two starter products opened at the authored round-0 prices: Aura Pro
$750.00, Aura SE $380.00.

### Round 1 — 10x

```
POST  /api/games/1/teams/6/decisions/round/1/
{"marketing_decisions": [ …retail_price "7500.0" for Aura Pro,
                          retail_price "3800.0" for Aura SE… ]}
→ 200
PATCH /api/games/1/teams/6/decisions/round/1/marketing/  [ …same rows… ] → 200
```

No warning of any kind. The `warnings` field the marketing serializer returns is
populated only by the production-capacity check
(`core/serializers/decisions.py:350-385`); it has nothing to say about price. The
response carried `"warnings": []`.

### Round 2 — 0.1x

```
POST  /api/games/1/teams/6/decisions/round/2/   retail_price "75.0" / "38.0"  → 200
PATCH /api/games/1/teams/6/decisions/round/2/marketing/                        → 200
```

### What the engine used

`round_result_product_market`, T6:

| Round | Product | `retail_price` | `units_produced` | `units_sold` | `local_revenue` |
|---|---|---|---|---|---|
| 0 | Aura Pro | 750.00 | 15,000 | 15,000 | $11,250,000 |
| 0 | Aura SE | 380.00 | 30,000 | 30,000 | $11,400,000 |
| 2 | Aura Pro | **75.00** | 20,000 | 0 | $0 |
| 2 | Aura SE | **38.00** | 20,000 | 20,000 | $532,000 |

The engine used the submitted price verbatim. There is no anchor, no band, no
alert, no adjustment and no rule for a blank price — exactly as read.

**Round 1 has no rows at all.** At $7,500 and $3,800 the demand side allocated
nothing, so `context.revenue` had no key for either product and
`financials.py:388-395` wrote no `round_result_product_market` row. T6's round-1
`total_revenue` is **$0.00**. This is worth carrying into Stage 5: a team that
prices itself out of the market gets *no line on its results screen for that
product*, so the price the engine used is not visible anywhere afterwards.
Whatever Stage 5 builds for the audited adjustment has to survive the case where
the product produced no result row.

One thing the reading did not mention and Stage 5's designer will want:
positioning-level **reference prices already exist** as scenario config, added by
V2-023's repair — `reference_price_budget 250`, `mainstream 420`, `premium 700`,
`ultra_premium 1000`, with `high_price_elasticity 1.5`. They anchor the demand
response. They are not a legality band and nothing validates against them, but a
band anchored on last round's effective price will interact with them and the two
should be specified together.

### Severity

**P1.** It is not an exploit in the V2-023 sense any more — that repair made
revenue peak at the reference price and fall monotonically above it — but the
absence of any band, alert or blank-price rule is a rules gap the handoff already
plans to close, and the missing round-1 result row is a dispute-2 hazard.

---

## A6 — cohort caps are not enforced. **Reproduced. Proposed P1.**

Section 1: `max_teams=8`, `team_size_min=3`, `team_size_max=5`. The game began
with 8 teams and 8 enrolments.

| Probe | Request | Result |
|---|---|---|
| A 9th team | `POST /api/teams/` | **201** |
| Teams 10–17 | `POST /api/teams/` ×8 | **201** each |
| 7 more enrolments | `POST /api/roster/` `{"action":"add",…}` ×7 | **201** each |
| All 7 onto one team | `PUT /api/team-management/` `{"action":"assign", …}` | **200**, `{"updated": 7, "errors": []}` |
| The same, per user | `POST /api/users/<id>/assign-team/` ×7 | **200** each |

Final state, read from the database: **17 teams in the game** whose section
allows 8, and **8 active enrolments on team 1** whose section allows 5. Neither
cap was consulted on any path. `team_size_min` has no enforcement point at all —
seven of the eight teams finished with one member against a minimum of three.

Two further observations:

- `POST /api/games/create/` **cannot be used to probe this**, because it returns
  **500** for every authenticated instructor. See [N2](#n2) — that is a separate
  finding and a serious one.
- The unrelated cap at `views/scenario_views.py:237` *is* enforced: `num_teams:
  17` was refused **400** `{"error": "num_teams must be between 2 and 16."}`. So
  the two caps Part A said disagree do disagree, and the one that binds is the
  one with no relationship to the section. `POST /api/teams/` then walks straight
  past it — the game finished with 17 teams.

### Severity

**P1.** In a competition run as concurrent heats of 6–8 firms on one deployment,
"the field size is whatever anyone typed" is a fairness problem before it is a
correctness one. It is also cheap to fix, which is Stage 6's own conclusion.

---

## D1 — `end_of_round` retirement leaves the market links active. **Reproduced. Proposed P2.**

T7, round 1, both timings in one payload so the comparison is within one team and
one round:

```
POST  /api/games/1/teams/7/decisions/round/1/
{"product_retires": [{"team_product": 13, "timing": "end_of_round"},
                     {"team_product": 14, "timing": "immediate"}]}
→ 200
PATCH /api/games/1/teams/7/decisions/round/1/product-retires/  [ …same rows… ] → 200
```

`team_product` / `team_product_market` afterwards:

| Product | `timing` | `status` | `retired_round` | `team_product_market.is_active` |
|---|---|---|---|---|
| IronClad X (13) | `end_of_round` | retired | 1 | **true** |
| IronClad Field (14) | `immediate` | retired | 1 | false |

Exactly the asymmetry Part A read at `core/engine/rd_processing.py:323-338`.

**Why P2 rather than P1.** Every reader of `team_product_market` in the engine
and the views that I could find also filters `team_product__status='active'` —
`preference_engine.py:422-436`, `readiness_engine.py:23-31`,
`views/decisions.py:666`, `:926`, `:974`, `MarketingContextView` at `:1643`. So
the stale row is inconsistent persisted state rather than a live behavioural
difference today. It stops being harmless the moment a reader keys on `is_active`
alone — and Stage 4's re-basing history, which has to resolve a product's markets
*as of a round*, is precisely such a reader. Repair it before Stage 4, not after.

---

## Not anticipated by Part A

### N1 — the lock validator is not a gate. **Proposed P0.**

Stated in full at the top of this record. The evidence:

```
POST  /api/games/1/teams/5/decisions/round/1/
{"platform_developments": [{"platform_generation": 6, "method": "in_house",
  "committed_cost": "0", "platform_name": "T5 round-1 Gen3", "feature_levels": {}}]}
→ 200                      (Gen 3 has unlock_round 5; this is round 1)

PATCH /api/games/1/teams/5/decisions/round/1/platforms/   [ …same row… ]  → 200

POST  /api/games/1/teams/5/decisions/round/1/lock/  {}
→ 400
{"detail": "Validation failed.", "errors": [
  "Platform \"Gen 3 — AI-Native Sustainable Platform\" not unlocked yet (unlocks round 5).",
  "Product Portfolio is required before locking."]}
```

The team then did nothing. The operator closed round 1 —
`Round 1 closed. 8 submission(s) locked.` — and after processing T5 holds:

```
team_platform: generation_order 3, name "T5 round-1 Gen3", status "active",
               development_started_round 1, development_rounds_remaining 0,
               activated_round 1, capitalized_cost 0.00
round_result_financials: T5 round 1 rd_expense 0.00
```

A Gen 3 platform, in round 1, for nothing, on a submission the product had
already told the team was invalid.

The mechanism is `_lock_all_submissions` (`core/engine/advance_round.py:146-175`):
it sets `status='locked'` on every draft and creates an empty locked submission
for teams that never saved. It calls no validator. The engine's own precondition
(`advance_round.py:380-411`) then checks only that every team is locked, and
`persisted_violations` scans only for negative values.

This is not a new rule to invent — it is a statement about where the existing
rules have to live. **Every rule Stage 2 writes must exist as an engine
precondition on persisted rows, not only as a serializer or lock-time check**,
or a team defeats it by not pressing a button.

### N2 — `POST /api/games/create/` returns 500 for every authenticated instructor. **Proposed P1, arguably P0 for Stage 6.**

```
POST /api/games/create/
{"scenario_id": 2, "num_teams": 16, "name": "…", "section_id": 1}
→ 500  (Server Error, HTML)
```

From the stack's log:

```
File ".../core/views/scenario_views.py", line 301, in post
    game = Game.objects.create(
ValueError: Cannot assign "<core.authentication.JWTUser object …>":
            "Game.created_by" must be a "User" instance.
```

`Game.created_by` is a FK to `settings.AUTH_USER_MODEL`
(`core/models/core.py:31-34`), and `AUTH_USER_MODEL` is not overridden, so it
resolves to `django.contrib.auth.User`. The project's only
authentication class is `core.authentication.JWTAuthentication`
(`globalstrat/settings.py:312-314`), so `request.user` is always a `JWTUser`, and
`scenario_views.py:246-251` assigns it whenever the caller is authenticated —
which `IsInstructor` guarantees. The fallback to a superuser at `:252-258` is
unreachable for exactly the caller the endpoint is for.

This is not a corner: `frontend/globalstrat-frontend/src/api/instructor.js:121`
is `createGame`, called from `InstructorDashboard.js:243` — the dashboard's
create-game control. **An instructor cannot create a game through the product.**
No other harness in `handoff_readiness_v2/` calls this route — a grep for
`games/create` across that directory returns only this stage's files — because
every earlier fixture built its game with `manage.py initialize_game` or
`setup_test_game`. That is why no earlier handoff met it.

Stage 6 of this handoff plans a competition as several concurrent heats set up on
one deployment. That plan currently has no working setup path. Raising it here
rather than repairing it; it is not this stage's to fix, and it may not even be
this handoff's.

### N3 — `migrate` on an empty database fails. **Proposed P1.**

At this revision a fresh database cannot be migrated:

```
python manage.py migrate --noinput
…
  Applying core.0070_audit_guards...
django.db.utils.ProgrammingError:
  relation "competition_authorization_refusal_event" does not exist
```

`0070_audit_guards`, `0071_audit_truncate_guards` and
`0072_truncate_guard_authorization` each call
`core.services.audit_guards.install_sql()`, which is evaluated **at import time**
against today's `PROTECTED_TABLES` tuple (`audit_guards.py:27-33`). That tuple
names `competition_authorization_refusal_event`, whose table is created eight
migrations later by `0078_authorization_refusal_event`. Three historical
migrations therefore try to install a trigger on a table that does not exist yet.

Every existing deployment migrated incrementally and never met it. A new
deployment, a disaster-recovery rebuild, or a restore-then-migrate cannot get
past it — which touches the RD-01/02/03 recovery runbook. The harness works
around it by faking 0070–0072 and then running `manage.py install_audit_guards`,
so the stack under probe carries the same schema *and* the same triggers a
deployment carries; see `harness/stack.py:create_database`.

### N4 — small ones, recorded so they are not re-found

- **N4a.** `TeamPlatform.development_method` is written with `'license'`, which
  is not among its declared choices (`'licensed'`). Observed on T2's Gen 2 and
  Gen 3 rows. Cosmetic; a filter on `'licensed'` would silently miss them. **P2.**
- **N4b.** Generation prerequisites are display-only.
  `_check_generation_prerequisites` (`views/decisions.py:1158`) is called at
  `:1327` and `:1442`, both inside `RDContextView`. No write path consults it, so
  `prerequisites_met: false` blocks nothing but a button in the browser
  (`RDPage.js:79`). A sibling of N1. **P2.**
- **N4c.** A product that sells nothing gets no `round_result_product_market`
  row at all, so its price for that round exists only in the decision row. Stage
  5's audited adjustment and any dispute-2 answer have to account for that. **P2.**
- **N4d.** Part D's **D3** — *"`_process_platform_development` skips creation
  when any non-retired platform of that generation exists, so a team can never
  rebuild after retiring one"* — did **not** reproduce. T8's starter Gen 1 was
  retired and T8 rebuilt Gen 1 in round 1 through the ordinary API; both the
  engine filter (`rd_processing.py:69-75`) and the lock validator
  (`views/decisions.py:598-602`) exclude `status='retired'`. Noted for
  GSP-CRV2-13, which owns Part D; not withdrawn here, because Part D is not this
  handoff's to dispose of.

---

## What Stage 2 should take from this

Not a design — the design is in the handoff. Three constraints the probes
establish that the handoff was written before knowing:

1. **The engine precondition is load-bearing, not defence in depth** (N1). Any
   rule that lives only in a serializer or in `_full_validate` is optional for a
   team that never locks. `advance_round.py:396-411` already has the right shape;
   the cost-agreement check belongs beside `persisted_violations`, refusing and
   naming the row, never clamping.
2. **The authoritative values already exist and are already served.**
   `PlatformGenerationDefinition.development_cost` / `license_cost` and
   `feature_level_cost` are what `RDContextView` publishes. Stage 2's "one
   function, two callers" is a lift-and-share of code that is already correct,
   not new arithmetic. The read path's `current_investments[].cost`
   (`views/decisions.py:1389`) must move onto the same function, or the R&D page
   will keep showing the team its own number.
3. **A3's repair has to go through the speed modifier.** Fixing only the
   create-then-decrement leaves `floor(2 / 1.10) = 1` and the authored 2 still
   behaves as 1. A minimum of one round must survive both the modifier and the
   decrement.

---

## Reproducing this

From the repository root, on this revision:

```bash
python3 handoff_readiness_v2/evidence/decision-rules/harness/probe_run.py --rounds 6
python3 handoff_readiness_v2/evidence/decision-rules/harness/summarise.py
```

`probe_run.py` creates its own database with a timestamped name, claims a port
from the kernel, asserts the fixture identity and the database identity before
the first probe, plays six rounds through the HTTP API, snapshots every row after
every round, writes `stage1-probes.json`, and drops the database. `--keep-database`
keeps it. `summarise.py` reads the JSON and needs no stack, so any number in this
record can be checked without replaying the game.

Team *names* are drawn from a scenario list and differ between runs; team
*indices and ids* (T1 = id 1 … T8 = id 8) are stable, and this record cites
indices and ids.

---

## Status

Stage 1 closes here. Seven of seven Part A items reproduced; none withdrawn; four
findings raised that Part A did not anticipate. Proposed register entries —
**V2-036** (A1 + A1b, P0), **V2-037** (N1, P0), **V2-038** (A2, P1),
**V2-039** (A3, P1), **V2-040** (A4, P1), **V2-041** (A6, P1),
**V2-042** (N2, P1), **V2-043** (N3, P1), **V2-044** (D1 + N4a–c, P2) — are
proposed, not written: `V2_FINDINGS_REGISTER.md` is a shared record and another
builder is working in the main checkout, so the register update should be one
reviewed act rather than a concurrent edit from a worktree.

No repair was written. Stage 2 remains gated on GSP-CRV2-08 clearing its audit.
