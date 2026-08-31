# GSP-CRV2-10 Stage 1 — confirm or withdraw

**Final position.** Part A was written from source reading and none of it had
been executed. Every item was submitted as a real payload against an isolated
stack, advanced through the supported round controls where the claim is about
engine behaviour, and read back from the rows.

**Tally: eight confirmed findings, one withdrawn theory.**

Stage 1 ran in two passes. The first pass, at `c20ebbb`, made three claims that
were **false and are corrected here, not appended to**: that every probe used
both submission APIs, that nothing was withdrawn, and that
`development_rounds: 0` could not be measured. Where the chronology matters it
is marked *first pass, superseded*. Nothing below states a first-pass
conclusion as current.

Nothing here changes runtime code. Baseline `e5cb8f4`, database
`gsp_crv210_probe`, ports claimed at run time, stack refused to start until a
fixture identity authenticated through the app origin.

Raw records, immutable: `stage1-probe-record.json` (first pass, 8 probes),
`stage1-a1b-reprobe.json`, `stage1-rework-probes.json`.

## Dispositions

| Item | Disposition | Severity | Surfaces measured |
|---|---|---|---|
| A1 — R&D price set by the client | **Reproduced** | **P0** (V2-037) | both |
| A1b — level-based R&D grants outright | **Reproduced**, on the lag | **P0** (V2-037) | both |
| A1c — R&D against another team's platform | **Reproduced**, bounded | P1 (V2-044) | both |
| A2 — platform cost escapes both budget checks | **Reproduced**, plus a second defect | P1 (V2-038, V2-039) | both |
| A3 — `development_rounds: 0` ready in creation round | **Reproduced** | P1 (V2-040) | both |
| A3 — authored `development_rounds: 2` behaves as 1 | **Reproduced** | P1 (V2-040) | both |
| A4 — no price band | **Reproduced** (absent) | **P1** (V2-041) | both |
| A6 — cohort caps unenforced | **Reproduced** | P1 (V2-042) | n/a — no decision surface |
| D1 — `end_of_round` retirement | **Reproduced exactly** | P2 (V2-043) | both |
| Free ceiling-level feature initialisation | **Withdrawn — the reading was wrong** | — | measured directly |

Every mandatory probe has a measured disposition. The surface-coverage matrix
below names the endpoint and result for each.

## A1 — a $15M platform for nothing. Reproduced. P0

Gen 2 is authored `development_cost` **$15,000,000** and `license_cost`
**$35,000,000**. Both teams submitted `committed_cost: 0`, one per surface:
`PATCH .../platforms/` **200**, `POST .../round/{n}/` **201**. After close,
process and advance, both own the platform `active`, and `rd_expense` for the
round is **0.00**. The licensed variant behaved identically, so `method`
changed nothing about the price.

## A1b — features to the ceiling for nothing. Reproduced. P0

Gains are lagged through `PendingFeatureGain`, so the first read — one advance
after submitting — showed no change. *First pass, superseded:* that was
recorded as inconclusive. Re-probed across three advances
(`stage1-a1b-reprobe.json`):

| | feature 36 level | pending row | `rd_expense` |
|---|---|---|---|
| before | 11.00 | — | 0.00 |
| after advance 1 | 11.00 | `gain_amount 3.00, applies_round 2, applied false` | 0.00 |
| after advance 2 | **14.00** | `applied true` | **0.00** |
| after advance 3 | 14.00 | applied | 0.00 |

Submitted `target_level: 14, amount: 0, calculated_cost: 0`. The feature reached
its ceiling and nothing was charged in any round. `amount` and
`calculated_cost` are not read on this path.

## A1c — the write accepts a foreign platform; the lock refuses it. Reproduced, bounded. P1

Both write surfaces accept an R&D investment naming another team's
`team_platform`: per-type **200**, whole-submission **201**.

With every other required section filled so the validator is reached, the
complete lock is refused **400**: `R&D investment references a platform not
owned by this team.` **The ownership check is correct and runs at lock.**

The finding is the gap before it: the write persists the foreign row, and a
team that never locks is defaulted at close, so the row reaches the engine
anyway. In the first probe run exactly that happened — duplicate
`PendingFeatureGain` rows against the other team's platform and a round left
unprocessable by a natural-key collision, the same class as V2-029. Same shape
as V2-039: a gate that exists only at lock does not bind a team that never
locks.

## A2 — cost escapes both checks, and the unlock gate too. Reproduced. P1

`committed_cost: 999,999,999` against **$47,980,000** cash and an `rd_budget`
of **$1,000**: both surfaces **200 / 201**; the lock refusal named the unlock
round and three missing decision sections and **never the cost or the cash**,
verified against the response body; and the engine charged it — `rd_expense`
**999,999,999.00**.

**Second defect, same probe (V2-039).** The generation targeted unlocks at
round 5 and was submitted in round 3. The team never locked, close defaulted
the submission, and the engine built the platform anyway: `active`, two rounds
before its unlock round. The unlock gate is enforced at lock time only.

## A3 — timing, both cases measured. Reproduced. P1

*First pass, superseded:* the `development_rounds: 0` case was recorded as
untestable, because every team owns the starting generation and creation is
skipped when a non-retired platform of it exists — a `200` with unchanged rows
recorded the skip, not the timing. The rework retired both subject teams'
starting platforms first, and measured it.

- **`development_rounds: 0`** — submitted round 1, both surfaces. After the
  first advance, the processing of its own creation round, the platform is
  `active` with `development_rounds_remaining: **-1**`. The negative value is
  the create-then-decrement in one call. Ready in its creation round.
- **`development_rounds: 2`** — submitted round 4, both surfaces. `active` with
  `development_rounds_remaining: 0` after a single advance. An authored
  two-round build is ready after one.

## A4 — no price band. Reproduced. P1

In one open round, for the same product: `retail_price: 99999` accepted
(200/201), then `retail_price: 1` accepted (200/200). Stored price after both:
**1.00**. No band, no anchor, no alert, no refusal, no adjustment.

**P1, and the justification matters because the rule is absent rather than
broken.** The exposure is live now: a competition run today has no band, so a
team can price at 1 or at 99,999 and the consequence lands on every other team.
Stage 5 owns building the rule; this finding is the exposure until it lands.

Three earlier attempts returned 400 on missing required marketing fields. Those
were harness defects, not a band: recording the response body is what kept them
distinguishable, and a bare status code would have read as a refusal.

## A6 — cohort caps unenforced. Reproduced. P1

Section: `max_teams 8`, `team_size_min 3`, `team_size_max 5`. Eight students
added through `POST /api/roster/ {action: add}` — all **201**; eight assigned to
one team through `PUT /api/team-management/ {action: assign}` — **200**,
`{'updated': 8, 'errors': []}`; result **11 active members on a team whose
`team_size_max` is 5**. Neither surface consults the caps.

A6 has no decision surface, so the two-API rule does not apply to it; the two
operator surfaces it does have were both exercised.

## D1 — retirement leaves the product on sale. Reproduced exactly. P2

`{timing: 'end_of_round'}` accepted on both surfaces (200/200). After the
round, both products are `retired` and both `TeamProductMarket` rows remain
`is_active: true`. The `immediate` branch deactivates those rows; the
`end_of_round` branch does not.

## Withdrawn — free ceiling-level feature initialisation

*First pass, superseded and false.* I recorded that a new platform's features
are initialised "to ceiling levels", from seeing 14.00/14.00/14.00/12.00/12.00
on a newly created platform.

Measured against the authored ceilings **for that generation**, they are not: a
platform created with `feature_levels: {}` initialises to **10.00, 10.00,
10.00, 8.00, 8.00** against ceilings of **17, 16, 16, 17, 16**, every level
below its ceiling, and `levels_at_or_above_ceiling` is empty.

The error was mine twice: I compared one generation's observed levels against a
different generation's ceilings, and never read the authored ceilings for the
generation in question. Initialising a new platform to its generation's
baseline capability is ordinary behaviour, not a free capability grant.

**Withdrawn as a finding.** The mechanism — features initialised without a
decision naming them — is recorded so Stage 3 can confirm the baseline levels
are intended. It is not evidence that anything was obtained for free.

## What Stage 1 does not claim

- **Severity ordering between the P1s.** That is the owner's call.
- **Anything about Stage 2's repair design.** Stage 1 closes on measured
  dispositions; no repair has been written and Stage 2 remains gated behind
  CRV2-08's audit.

Both limitations recorded in the first pass are now resolved and are no longer
open: `development_rounds: 0` is measured above, and V2-044's lock behaviour is
measured and the finding bounded to the write and default-close path.

# Stage 1 rework — the probes the first pass did not measure

Audit of `c20ebbb` found five gaps. Raw record: `stage1-rework-probes.json`.
No runtime code changed.

## Surface coverage matrix

Replaces the blanket claim that every item used both submission APIs. It did
not, and the artifacts did not support saying so.

| Item | Per-type `PATCH .../<type>/` | Whole submission `POST .../round/{n}/` | Disposition |
|---|---|---|---|
| A1 platform cost | 200, platform active, `rd_expense` 0.00 | 201, platform active | reproduced, both |
| A1b feature grant | 200, level 11→14, charged 0.00 | 200 | reproduced, both |
| A1c foreign platform | 200 (team 2) | 201 (team 3) | reproduced, both — **narrowed, see below** |
| A2 cost vs cash/budget | 200 | 201 | reproduced, both |
| A3 `development_rounds: 0` | 200, active at `-1` | 201, active at `-1` | reproduced, both |
| A3 `development_rounds: 2` | 200, active at `0` after one advance | 201, same | reproduced, both |
| A4 price band | 200 (99999), 200 (1) | 201 (99999), 200 (1) | reproduced, both |
| A6 cohort caps | **not applicable** — no decision surface. Exercised through `POST /api/roster/ {action: add}` (8×201) and `PUT /api/team-management/ {action: assign}` (200) | | reproduced |
| D1 retirement | 200, product retired, market row still active | 200, same | reproduced, both |

## A3 `development_rounds: 0` — now measured. Reproduced

The first pass could not measure this: every team owns the starting generation
and creation is skipped when a non-retired platform of it exists, so a `200`
and unchanged rows recorded the skip. Both subject teams' Gen 1 platforms were
retired in the fixture first.

Submitted in round 1 on both surfaces. After the **first** advance — the
processing of the round it was created in — the platform is `status: 'active'`
with `development_rounds_remaining: **-1**`. The negative value is the
create-then-decrement in one call, exactly as Part A read it. It is ready in
its creation round.

Control, authored `development_rounds: 2`: submitted round 4, `active` with
`development_rounds_remaining: 0` after one advance. An authored two-round
build is ready after one.

## A1c / V2-044 — narrowed to what is proven

Both write surfaces accept an R&D investment naming another team's platform:
per-type **200**, whole-submission **201**.

With every other required section filled so the validator is actually reached,
the complete lock attempt is refused **400**:

> `R&D investment references a platform not owned by this team.`

**So the ownership check works when it runs.** The finding is therefore
narrower than first written: the *write* accepts a foreign platform and only
the *lock* refuses it. That still matters, because a team that never locks is
defaulted at close and the row reaches the engine anyway — which is what
happened in the first probe run, writing duplicate `PendingFeatureGain` rows
against the other team's platform and making the round unprocessable. It is the
same shape as V2-039: a gate that exists only at lock.

## Free ceiling-level initialisation — withdrawn. My reading was wrong

I recorded that a new platform's features are initialised "to ceiling levels",
from seeing 14.00/14.00/14.00/12.00/12.00 appear on a newly created platform.

Measured directly against the authored ceilings for that generation, they are
not. A platform created with `feature_levels: {}` initialises to
**10.00, 10.00, 10.00, 8.00, 8.00** against authored ceilings of
**17, 16, 16, 17, 16** — every level below its ceiling, and
`levels_at_or_above_ceiling` is empty.

The error was mine twice over: I compared one generation's observed levels
against a different generation's ceilings, and I never read the authored
ceilings for the generation in question at all. Initialising a new platform to
its generation's baseline capability is ordinary behaviour, not a free
capability grant.

**Withdrawn as a finding.** The mechanism — features initialised without a
decision naming them — is real and is recorded here so Stage 3 can decide
whether the baseline levels are the intended ones. It is not evidence of
anything being obtained for free.
