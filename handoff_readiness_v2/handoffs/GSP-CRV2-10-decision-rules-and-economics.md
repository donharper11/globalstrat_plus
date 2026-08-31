# GSP-CRV2-10 — Decision rules and the economic legal space

**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoffs/EXECUTION_PROTOCOL.md`
**Source:** `handoff_readiness_v2/RULES_AND_CALIBRATION_ASSESSMENT.md` Part A
**Owner:** backend rules/economics engineer
**Blocks:** GSP-CRV2-11 (do not calibrate rules known to be broken), GSP-CRV2-09
**Entry condition:** GSP-CRV2-08 through its audit gate. See below — this is a
hard gate on Stage 2 onward, not a preference.

## Entry condition — why this waits for CRV2-08

Stage 1 may run concurrently with CRV2-08. **Stage 2 onward may not**, for three
reasons, in descending order of how expensive it is to get wrong.

1. **The protocol's own invalidation rule decides it.** EXECUTION_PROTOCOL:
   *"Any runtime code change after evidence starts invalidates that evidence."*
   CRV2-08 is generating browser-walkthrough evidence against the integrated
   candidate and, as of `45eb83c`, repairing product code inside it — a new
   operator-events endpoint, `results_api.py`, `urls.py`, an instructor panel and
   `LanguageSwitcher.js`. Stage 2 mutates that same candidate. Run concurrently,
   CRV2-08's walkthrough is evidence for a build that no longer exists.

2. **This programme reworks after audit as a matter of course.** Fifteen rework
   documents across handoffs 01, 02, 03, 04, 06 and 07 — 02 twice, 03 twice, 06
   five times, 07 four times. Not one certified handoff cleared its audit on the
   first pass. Planning on CRV2-08 being the first is not supported by anything
   in this directory, and CRV2-08 rework colliding with Stage 2 repairs in the
   same files is the expensive version of this mistake.

3. **Stage 5 hands CRV2-08 a case it cannot have covered.** The price band
   introduces a *system-initiated adjustment*: at the deadline the stored price
   legitimately differs from the number the team typed. That is a new instance
   of **dispute 2 — "our decision was recorded differently from what we
   entered"** — arriving after CRV2-08 has frozen its dispute inventory and
   proved the six cases. It does not invalidate CRV2-08's evidence; it adds a
   case that evidence says nothing about, which is worse, because nothing flags
   it.

   **Obligation on this handoff:** Stage 5 delivers a written delta to the
   CRV2-08 owner naming the new dispute-2 case, and that case is re-verified
   through the supported operator path before this handoff certifies. Do not
   rebuild CRV2-08's completed game and do not replay its five passing disputes.

If Stage 1's probes confirm the suspected P0 at a severity that will not keep,
raise it as a finding and let the programme owner decide whether to interrupt
CRV2-08 — that is an explicit decision with a stated cost, not a scheduling
convenience taken quietly.

## Running Stage 1 alongside CRV2-08

Stage 1 writes no runtime code and commits nothing to the candidate. It is
therefore safe to run in parallel, under EXECUTION_PROTOCOL Phase 0 and one
addition CRV2-08 paid for the hard way:

- Separately named database and isolated stack. Record database name, PID,
  branch and revision at start.
- **Claim ports at run time; never bind a fixed one.** CRV2-08's stack was
  configured on 8002, which already carries a gunicorn serving the live
  `globalstrat_plus` database. Its backend failed to bind, died, and its requests
  fell through to production — exposed only by a login failure. Had a fixture
  username collided with a live one, it would have read production while
  reporting on the fixture.
- Refuse to start unless a fixture identity authenticates through the app origin.

## Objective

Make the price, the timing and the limits of every decision **authoritative on
the server**, enforced identically on both write surfaces and again as a
fail-closed engine precondition, and make the rules of play match the rules as
stated rather than as the code happens to behave.

GSP-CRV2-06's Stage 1 asked whether a decision field's value was in range. This
handoff asks the question it did not: **does a field that names a price agree
with the price the scenario authored?** Everything else here follows from that
question being asked of each rule in turn.

## Stage 1 — confirm or withdraw, before designing any repair

Part A is source reading. Nothing in it has been executed. Confirm each item
against a running isolated stack through **both** supported submission APIs
before proposing a repair, and withdraw what does not reproduce — GSP-CRV2-06
withdrew V2-019 for exactly this reason and the withdrawal was the right call.

Produce a checked-in probe record covering, at minimum:

1. `POST` a platform development with `committed_cost: 0` for the most expensive
   unlocked generation. Advance the round. Record what the team was charged and
   whether it owns the platform. (A1)
2. `POST` an R&D investment with `target_level` at the generation ceiling and
   `amount: 0`, `calculated_cost: 0`. Advance. Record the resulting feature
   level and the P&L charge. (A1b)
3. Submit `committed_cost` above the team's cash and above `rd_budget`. Record
   whether either check fires. (A2)
4. Develop a `development_rounds: 0` generation and a `development_rounds: 2`
   generation. Record the round each becomes `active`. (A3)
5. Price a product at 10x and at 0.1x its previous round's price. Record the
   response and the price the engine used. (A4)
6. Enrol past `CourseSection.max_teams` and past `team_size_max`. Record whether
   either is refused. (A6)
7. Retire a product with `timing='end_of_round'`. Record `TeamProductMarket`
   afterwards. (D1)

State for each: reproduced / did not reproduce / reproduced differently, with
the payload, the response and the resulting rows. A finding that does not
reproduce is withdrawn in writing, with the reason the reading was wrong.

**Stage 1 closes on a committed probe record and a severity for each confirmed
finding. No repair is written before it closes.**

## Stage 2 — one authoritative price, one calculator

The rule, stated once: **the cost a team is shown is the cost the server
computes, and the cost the server computes is the cost it charges.** Not two
functions kept in step by hand — one function with two callers. BECSR's RW-50
is the precedent: `budget.get_total_program_cost` and the charge path both call
`services.program_costs.platform_costs`, and the invariant holds by
construction.

- Derive platform cost server-side from `PlatformGenerationDefinition`, keyed on
  `method`: `development_cost` for `in_house`, `license_cost` for `license`.
- Derive feature R&D cost server-side from the same level-cost table
  `_build_cost_schedule` already reads (`core/views/decisions.py:1136-1155`).
  Lift it out of the view into a service both the read and the charge use.
- Client-supplied cost fields become **advisory or removed**. If they are
  retained for display round-tripping, the server overwrites them; a submitted
  value that disagrees is refused with the authoritative figure named, and is
  never silently corrected.
- The engine gets a fail-closed precondition on persisted rows, in the shape
  V2-018's already takes: a stored row whose cost disagrees with the authored
  cost **refuses the round before any competitive mutation** and names the
  offending row and field. Do not clamp and do not reinterpret — a decision
  quietly replaced with a different one looks ordinary afterwards.
- Include platform development cost in the cash and budget checks, and
  reconcile the three divergent copies of the budget-vs-cash rule
  (`views/decisions.py:548`, `:888`, `:1015`) into one.

## Stage 3 — the R&D lifecycle

**Timing.** A platform is never ready in the round it is created. Fix the
same-call create-then-decrement (`rd_processing.py:96-110`) so the authored
`development_rounds` is the number of rounds actually waited, and so that a
generation authored at 0 still takes the minimum. Minimum 1 round, maximum 2,
by generation; make the maximum a scenario value rather than a constant.
`method` must affect lead time, price or both, or be removed — it currently
affects neither.

**Paid before ready.** A platform completes only if its cost was actually
charged. A team that starts one and cannot fund it keeps it as an unfunded
draft it may fund in a later round; the round the funding lands is the round the
clock starts. Draft state is student-visible, and so is "approved / in
development / ready" and the round it becomes available.

**Immutability after ready — SEE RULING 1 BEFORE IMPLEMENTING.** As stated, a
ready platform is frozen: no features added, no levels changed. That retires
`_process_feature_investments` on active platforms, and with it per-generation
ceilings, licensing, time lags and `PendingFeatureGain`. Do not begin this
sub-stage until the ruling lands. If the narrower reading is chosen (no *new*
features after ready, existing levels may still rise), the change is small and
local; if the full reading is chosen, it is the largest item in this handoff and
it invalidates the strategy space GSP-CRV2-06's tournament searched.

**Feature count.** Confirm the per-platform cap (currently
`max_platform_features`, default 5) is enforced on both write surfaces and at
activation. `rd_processing.py:119-131` initialises **every** entry in
`feature_levels` when a decision exists and only applies the cap on the fallback
path. Confirm the intended maximum is 5 or 6 and state it in one place.

## Stage 4 — re-basing a product, and the write-off

New capability. A team may switch a product's base platform to another of its
own **ready** platforms. The old platform may then be left unassigned,
deactivated, or reactivated and re-used later.

- Unsold inventory built on the platform being left is written off: a
  scenario-configured percentage of unit cost times units on hand at the moment
  of the switch, charged to the team and shown as its own line, on the stated
  rationale that this is a new model launching and the old one discontinuing.
- Write a round-versioned history row so past rounds remain reconstructable.
- **Read `~/projects/BECSR/backend/csr_sim/services/platform_switch.py` first**,
  and read defect B in `BECSR/handoffs_v1/reports/demand_diagnostic.md` before
  writing a line. That defect is the trap this feature opens: the demand side
  resolved platforms *as of the round* while the supply side resolved them *as
  of now*, so demand allocated to the historical platform reconciled to nothing
  — silently, because the conservation check summed only rows that existed. It
  measured 0 units only because no cohort had used the feature yet. Add the
  round dimension to both sides in the same change, and add a conservation
  assertion that fails on a *missing* row rather than summing what is present.

## Stage 5 — the price band

Per Ruling 2. The band is ±30% of the price the product was selling at last
round (a scenario parameter, not a constant). Round 1 anchors to the authored
starting price from the firm starter profile, so round 1 is not a special case.

Three behaviours, and the distinction between them is the whole rule:

| Team's input | While the round is open | At the deadline |
|---|---|---|
| Out-of-band price | **Alert**, naming the legal range. The submission is accepted and the team's number is kept | Auto-adjusted to the nearer band edge |
| No price entered / blank | Alert: this will be priced at the floor | Set to previous round −30% |
| In-band price | Nothing | Used as entered |

Every auto-adjustment writes an **audit event with actor `system`** recording
the submitted value, the applied value and the rule, and surfaces on the team's
results screen as an adjustment they can see. This is not optional garnish: an
unaudited substitution makes dispute 2 ("our decision was recorded differently
from what we entered") unanswerable, which is precisely the gate GSP-CRV2-08
exists to prove. BECSR refuses out-of-band prices rather than substituting, on
the argument that storing 130 against a `201` lies to a student who typed 140 —
the audit event and the visible adjustment are what answer that objection here.

## Stage 6 — cohort caps

Enforce `CourseSection.max_teams`, `team_size_min` and `team_size_max` at
enrolment and team assignment, with a refusal that names the cap. Reconcile
them with the unrelated `num_teams must be between 2 and 16` at
`views/scenario_views.py:237` — two caps that disagree is one cap that does not
exist. The *value* of the cap is CRV2-11's to determine (Ruling 4); this stage
makes whatever value it lands on actually bind.

## Stage 7 — events and challenges

Bounded. Do not build a challenge engine here.

1. Inventory every authored event and response across all three scenarios: what
   fires it, what it shifts, what responses exist, what each costs, whether a
   response is required, and what happens on silence.
2. Replace the hardcoded no-response penalty (`events.py:737-752`, a flat `-1.0`
   to `regulatory_govt` in the affected market regardless of the event) with an
   authored, per-event consequence. A penalty aimed at a feature that no segment
   in that market weighs is a penalty in name only.
3. Report — do not build — what response *quality* scoring and unresolved-event
   carry-over would require. BECSR's `challenge_engine.py` is the reference for
   what that would look like.

## Acceptance

- Every Stage-1 finding is confirmed-and-closed or withdrawn-with-reason.
- No cost, price or level a team can influence is taken from the client. A
  deliberately falsified payload on either surface is refused at the API, and a
  row inserted behind the API refuses the round before any competitive write.
- Both submission APIs enforce the identical rule set; where a field is exposed
  on only one surface it still obeys the central policy and the engine
  precondition.
- Platform timing, funding, feature cap and (per ruling) immutability behave as
  specified, with the authored `development_rounds` meaning what it says.
- Re-basing works, the write-off is charged, and demand/supply reconcile across
  a switch with a conservation check that fails on absence.
- The price band alerts, auto-adjusts at the deadline, audits every adjustment
  with actor `system`, and the adjustment is visible to the team.
- Cohort caps bind.
- New/changed student-facing strings are handed to GSP-CRV2-12 as a list rather
  than written twice.

## Evidence

`handoff_readiness_v2/evidence/decision-rules/` — Stage-1 probe record with
payloads and responses; the legal-space inventory extended with an
authoritative-value column per cost field; focused API and engine tests;
migration SQL; audit transcripts for band adjustments; the re-base conservation
proof. Findings opened and closed go to `V2_FINDINGS_REGISTER.md`.

## Verification budget

Focused API, serializer and engine tests throughout; one seeded multi-round game
for the lifecycle and re-base paths. **No full backend suite, no load run, no
concurrency matrix, no determinism replay** — CRV2-09 owns the single integrated
regression. Where a repair touches a boundary CRV2-01 through 06 certified,
state which, and run that boundary's focused regression only.
