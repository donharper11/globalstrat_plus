# GSP-CRV2-10 Stage 1 — confirm or withdraw

Part A was written from source reading and none of it had been executed. Each
item below was submitted as a real payload through **both** supported
submission APIs against an isolated stack, advanced through the supported round
controls where the claim is about engine behaviour, and read back from the rows.

**Nothing here changes runtime code.** Baseline `e5cb8f4`, database
`gsp_crv210_probe`, ports claimed at run time, stack refused to start until a
fixture identity authenticated through the app origin.

Raw records: `stage1-probe-record.json` (8 probes), `stage1-a1b-reprobe.json`.

## Dispositions

| Item | Disposition | Severity |
|---|---|---|
| A1 — R&D price set by the client | **Reproduced** | **P0** |
| A1b — level-based R&D grants outright | **Reproduced** (on the lag) | **P0** |
| A1c — R&D against another team's platform | **New, not in Part A** | P1 |
| A2 — platform cost escapes both budget checks | **Reproduced**, plus a second defect | P1 |
| A3 — platform ready in its creation round | **Reproduced differently** | P1 |
| A4 — no price band | **Reproduced** (confirmed absent) | gap, Stage 5 owns |
| A6 — cohort caps unenforced | **Reproduced** | P1 |
| D1 — `end_of_round` retirement | **Reproduced exactly** | P2 |

Nothing was withdrawn. One item, A3's `development_rounds: 0` case, could not be
tested through the supported path; the reason is recorded below rather than
counted as a pass.

## A1 — a $15M platform for nothing. Reproduced. P0

Gen 2 is authored at `development_cost` **$15,000,000** and `license_cost`
**$35,000,000**. Both teams submitted `committed_cost: 0`, one per surface:

- `PATCH .../decisions/round/2/platforms/` → **200**
- `POST .../decisions/round/2/` → **201**

After close, process and advance, both teams own the platform with
`status: 'active'`, and `rd_expense` for the round is **0.00**. The licensed
variant behaved identically, so `method` changed nothing about the price.

## A1b — features to the ceiling for nothing. Reproduced. P0

The first attempt read the level one round after submitting and found it
unchanged. That settled nothing, because gains are lagged. Re-probed across
three advances (`stage1-a1b-reprobe.json`):

| | feature 36 level | pending row | `rd_expense` |
|---|---|---|---|
| before | 11.00 | — | 0.00 |
| after advance 1 | 11.00 | `gain_amount 3.00, applies_round 2, applied false` | 0.00 |
| after advance 2 | **14.00** | `applied true` | **0.00** |
| after advance 3 | 14.00 | applied | 0.00 |

Submitted `target_level: 14, amount: 0, calculated_cost: 0`. The feature was
raised to its ceiling and nothing was charged in any round. `amount` and
`calculated_cost` are not read on this path.

Separately, a newly created platform had five features initialised from nothing
to 14.00, 14.00, 14.00, 12.00 and 12.00 in one round — the mass-initialisation
at `rd_processing.py:119-131`, which gives a new platform ceiling-level features
without a decision naming them. Recorded here because it is the same "free
capability" shape and Stage 3 will have to answer it.

## A1c — R&D against another team's platform. New. P1

Not in Part A. Found because the first probe run mistakenly sent one team's
`team_platform` id to both teams; the API accepted it. Probed deliberately
afterwards.

Team B, owning platform 2, submitted an R&D investment naming **platform 1**
(team A's). `PATCH .../rd/` returned **200**. In the first run this reached the
engine and wrote duplicate `PendingFeatureGain` rows against the victim's
platform, which then made the round unprocessable with a natural-key collision
— the same failure class as V2-029.

`_full_validate` does own an ownership check, but the lock refusal named only
`Budget allocation is required before locking`: the validator returns early on
the missing budget, so the ownership check never ran. **Not yet established:**
whether an otherwise-complete locked submission is refused. That is a bounded
follow-up, not a claim made here.

## A2 — cost escapes both checks, and the unlock gate too. Reproduced. P1

`committed_cost: 999,999,999` against **$47,980,000** cash and an `rd_budget`
of **$1,000**:

- both surfaces **200 / 201**
- lock refused **400**, naming the unlock round, the missing product portfolio,
  the missing marketing mix and the missing strategy mix — and **never the cost
  or the cash**. Verified against the response body, not inferred.
- the engine charged it: `rd_expense` for the round is **999,999,999.00**

**Second defect, same probe.** The platform targeted was Gen 3, which unlocks at
round 5, and it was submitted in round 3. Because the team never locked, close
defaulted the submission and the engine built it anyway: the platform exists
with `status: 'active'` two rounds before its unlock round. The unlock gate is
enforced at lock time only — not at save, and not in the engine.

## A3 — authored timing means something else. Reproduced differently. P1

Gen 2 is authored `development_rounds: 2`. Submitted in round 5; after a single
close/process/advance it is `status: 'active'` with
`development_rounds_remaining: 0`. An authored two-round build is ready after
one round.

**The `development_rounds: 0` case could not be tested through the supported
path.** Gen 1 is the starting platform, every team already owns one, and
`_process_platform_development` skips creation when a non-retired platform of
that generation exists (defect D3). The probe recorded
`team_already_owned_this_generation: true` and no platform was created — the
skip, not the timing. D3 obstructs its own diagnosis, and Stage 3 will need a
fixture where a team owns no Gen 1 platform to answer it.

## A4 — no price band. Reproduced. Gap, owned by Stage 5

In one open round, for the same product: `retail_price: 99999` accepted
(200/201), then `retail_price: 1` accepted (200/200). Stored price after both:
**1.00**. No band, no anchor, no alert, no refusal, no adjustment.

Three earlier attempts returned 400 on missing required marketing fields. Those
were harness defects, not a band: recording the response body is what kept them
distinguishable, and a bare status code would have read as a refusal.

## A6 — cohort caps unenforced. Reproduced. P1

Section: `max_teams 8`, `team_size_min 3`, `team_size_max 5`.

- Eight students added through `POST /api/roster/ {action: add}` — all **201**
- Eight assigned to one team through
  `PUT /api/team-management/ {action: assign}` — **200**, body
  `{'updated': 8, 'errors': []}`
- Result: **11 active members on one team** against a `team_size_max` of 5

Neither the enrolment surface nor the assignment surface consults the caps.

## D1 — retirement leaves the product on sale. Reproduced exactly. P2

`{timing: 'end_of_round'}` accepted (200). After the round, `TeamProduct.status`
is `retired` and its `TeamProductMarket` row is still `is_active: true`. The
`immediate` branch deactivates those rows; the `end_of_round` branch does not.

## What Stage 1 does not claim

- Whether a **complete** locked submission is refused for A1c's cross-team
  reference. Only the write and one masked lock refusal were observed.
- The `development_rounds: 0` timing case, for the reason above.
- Anything about severity ordering between P1s; that is the owner's call.

---

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
