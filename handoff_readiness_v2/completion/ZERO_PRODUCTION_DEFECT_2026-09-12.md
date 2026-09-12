# Zero production while solvent — the mechanism, the repair, and the rule question

**Investigating:** GSP-CRV2-11 finding 2 — "a team can lose an entire round to
zero production, with cash in hand", offered as a **P0 candidate**.
**Branch:** `crv2-11-zero-production-defect`, cut detached from
`crv2-release-integration` at `fb08db4`, in an isolated worktree.
**Date:** 2026-09-12.

**No gate is claimed closed.** Everything below is development-grade
measurement offered for audit. I did not edit `V2_FINDINGS_REGISTER.md` or
`LAUNCH_CHECKLIST_V2.md`; the findings are handed over in the register's format
in the last section.

---

## Summary

It is a defect, and it is **not** a production, capacity, funding, plant or
pricing failure. The team never got to produce anything because it was removed
from its only market by a **CC-18 compliance market-access freeze**, fired by
the `customs_documentation` regime for not filing a document that
**progressive disclosure forbade it to file**.

The engine punished a team for the absence of a decision the write path,
the disclosure registry and the participant UI all refuse to let it make.

One narrow repair is made in `compliance_engine._trigger_applies`. It removed
**every** zero-production round in rounds 1–4 of the 8-team replay, cut the
index spread from **42.15 to 32.92**, and — as a side effect worth stating —
reduced the worst remaining single-round penalty from **−17.81 to −5.00**,
because the catastrophic ranking-guard hits were themselves a product of the
spread that earlier collapses created.

It does **not** fix everything. Four collapses remain, in rounds 5–8, where the
document *is* filable and the fixed-policy baseline simply never files it.
Those are a different problem and I say so plainly below.

---

## Question 1 — why a solvent, competently-playing team produces nothing

### The trace, end to end

The reported symptom is `units_produced = units_sold = revenue = 0`. The first
thing to establish is what that zero actually is. In
`stage1_runtime_replay.py:207` it is

```python
'units_produced': str(sum((row.units_produced for row in product_rows), 0)),
```

— a sum over `RoundResultProductMarket` rows. In the lost rounds that queryset
is **empty**. The team did not produce zero units; **no product row was written
at all**. Confirmed against the pre-existing 4-team replay, which persisted the
full grain:

| team | round | `product_rounds` | `product_demand_rounds` |
|---|---:|---:|---:|
| Prism Tech (Workhorse) | 5 | 2 | present |
| Prism Tech (Workhorse) | **6** | **0** | **0** |
| Prism Tech (Workhorse) | 7 | 2 | present |
| Eclipse Gadgets (Green Pioneer) | 7 | 2 | present |
| Eclipse Gadgets (Green Pioneer) | **8** | **0** | **0** |
| Eclipse Gadgets (Green Pioneer) | 9 | 2 | present |

The products are present, active and identically named on both sides of the
lost round, producing the same 20,000 + 25,000 units. So nothing was retired,
deactivated or rebased, and `DecisionMarketing` rows existed — which excludes
the "no marketing row" hypothesis the original finding offered as consistent.

That the **demand** rows are also absent is what identifies the mechanism.
Only one path in the engine suppresses both the demand grain and the revenue
grain for one team, in one market, for exactly one round:

1. `revenue.py:111-118` — on a compliance freeze the loop `continue`s
   **before** `context.revenue[rev_key]` is assigned.
2. `bass_engine.py:113-115` — a frozen team-market has its product fit forced
   to 0 and is `continue`d out of the offer map, so no
   `RoundResultProductDemand` row is written.
3. `financials.py:396-424` writes `RoundResultProductMarket` by iterating
   `context.revenue`. Empty in, nothing out.
4. `costs.py:52` (`calculate_cogs`) also iterates `context.revenue`, so no COGS
   is charged either.

Net income is therefore the declared budgets, admin overhead, interest and the
$120,000 reclassification penalty against no revenue at all — the ≈ −8,000,000
reported — while cash stays healthy because nothing was manufactured. **R14's
spend refusal is correctly excluded: no team ran out of money.**

### What fires the freeze

`compliance_engine.enforce_compliance` (`advance_round.py:777`, before revenue)
evaluates every regime against every team and market. In Consumer Electronics
2026 only one regime has a live, evaluable trigger for a team playing the
documented baseline:

```yaml
- id: customs_documentation
  enforcing_market: all
  trigger_condition: incomplete_or_misclassified_customs_documentation
  baseline_enforcement_probability_per_round: 0.12
  detention_consequence:
    shipment_hold_rounds: 1
    reclassification_penalty_usd: 120000
```

- `uflpa` needs Xinjiang sourcing exposure; the baseline writes no
  `SourcingAllocation`, so exposure is 0% and it never applies.
- `us_bis_entity_list` and `product_safety_certification` return `None` from
  `_trigger_applies` — the module's documented "skip, don't fake" convention.
- `cbam` carries no `trigger_condition`.

So `_trigger_applies` returns `(True, False, 'no customs classification for
this market')`, the draw is
`get_rng(cohort, round, f'compliance_enforcement:customs_documentation:{team.id}:{market.code}').random() < 0.12`,
and `_freeze_rounds` reads `shipment_hold_rounds: 1` giving
`freeze_until = round_number` — frozen for exactly that round.

**Why one draw costs the whole firm.** `initialize_game.py:190-200` creates
exactly **one** `TeamMarketPresence` per team, its home market. Every
consumer-electronics starter profile is on NA. A freeze is scoped to one
team-market, but for a one-market firm that is total commercial blackout.

Per team per round the exposure is 12%. Over a 10-round game that is a
**72.1%** chance that any given team loses an entire round. That is the
lottery the finding detected.

### Why this is a defect and not legitimate risk

`logistics.customs_classification` is progressive-disclosure gated to
**round 5**, and all three layers enforce it:

| layer | evidence |
|---|---|
| registry | `core/utils/disclosure.py` — `'logistics.customs_classification': 5` |
| API | `CustomsClassificationDecisionWriteSerializer.validate` → `_reject_locked_fields` raises `ValidationError` below the unlock round |
| UI | `LogisticsPage.js:21` `customs_classification: 5`; `:190` disables the control; `:104` strips customs rows from the payload when `round < 5` |

In rounds 1–4 a team **cannot file the document at all**, yet the regime fires
on its absence at 12% per round. There is no counter-decision, no mitigation
reachable (the `customs_broker_program` investment is never consulted for this
trigger — `mitigated` is set by document presence alone), and no warning.

`compliance_engine`'s own module docstring already rules this case:

> Other regimes whose triggers have no determinable signal … are **skipped, not
> faked** — we do not invent enforcement we cannot ground.

A team forbidden to file presents no signal. Firing on it is invented
enforcement.

### The repair

`backend/core/engine/compliance_engine.py`, inside the customs branch of
`_trigger_applies` — 5 functional lines:

```python
from core.utils.disclosure import get_effective_unlock_round
unlock_round = get_effective_unlock_round(
    team.game, 'logistics.customs_classification')
if rnd.round_number < unlock_round:
    return None
```

Deliberately narrow:

- It reads the **effective** unlock round, so an instructor who unlocks the
  field early via `ClassProgressiveDisclosureOverride` re-arms the regime early
  too.
- From the unlock round on, the regime is **byte-identical** to before.
- It does not touch the V2-021/V2-022 inactivity classification, the composite
  cap, the ranking guard, the freeze consequence, or any other regime.
- It consumes no RNG draw, and `get_rng` is keyed per
  `(cohort, round, team, regime, market)` rather than drawn from a shared
  sequence (V2-011), so **skipping rounds 1–4 does not resegment the rounds 5+
  streams**.

### The focused test, and proof it fails without the repair

New module `backend/core/tests/test_zero_production_compliance_freeze.py`,
8 tests. It pins the enforcement probability at 1.0 so a green result cannot be
a lucky roll.

**Before the repair** (`core.tests.test_zero_production_compliance_freeze`):

```
FAIL: test_customs_trigger_is_not_evaluable_before_the_field_unlocks
  AssertionError: (True, False, 'no customs classification for this market') is not None
FAIL: test_round_one_enforcement_cannot_freeze_a_single_market_firm
  AssertionError: (1, 1) unexpectedly found in {(1, 2), (1, 5), (1, 1), (1, 4), (1, 3)}
FAIL: test_every_locked_round_is_covered_not_just_round_one (round_number=1..4)  [4 subtests]
Ran 8 tests in 1.571s
FAILED (failures=6)
```

**After the repair:** `Ran 130 tests in 11.490s — OK` (see below).

The other five tests pass on both sides deliberately, because they are what
stops the repair going too far:

- `test_a_team_cannot_file_the_customs_document_before_round_five` — the
  serializer refuses at round 1 and accepts at round 5. The repair is only
  correct *because* of this.
- `test_the_regime_still_fires_once_the_field_is_unlocked` — round 5, no
  document, fires; cost $120,000; `freeze_until_round = 5`.
- `test_filing_the_document_prevents_the_freeze_once_unlocked` — the
  counter-decision works.
- `test_an_instructor_override_rearms_the_regime_early` — override to round 1,
  regime fires at round 1.
- `test_a_single_market_freeze_costs_the_entire_round` — documents the blast
  radius: `ctx.revenue == {}` for a frozen one-market firm, and the firm is
  then commercially inactive against a cohort floor set by teams that were not
  frozen.

### What evidence the repair invalidates

**Two existing tests asserted the old behaviour and had to be reversed.** I
preserved and moved them rather than deleting them, following the precedent
V2-022 set for exactly this situation:

| test | was | now |
|---|---|---|
| `test_cc18_compliance.test_customs_fires_when_docs_missing` | round 1, `freeze_until_round == 1` | round 5, `freeze_until_round == 5` — same assertions, first round where the omission is a real choice |
| `test_cc18_compliance.test_customs_not_fired_when_docs_present` | round 1 | round 5 |
| *(added)* `test_customs_is_unevaluable_while_the_document_is_still_locked` | — | pins the reversal in the CC-18 module too |

**Replay and determinism evidence invalidated.** This is an engine change
inside the CRV2-01 determinism boundary. `compliance_enforcement` is a
competitive manifest section (`manifest_sections.py:419`), so any stored
`output_sha256` / `input_sha256` for a game whose rounds 1–4 contained a customs
enforcement event no longer reproduces. Specifically superseded:

- `evidence/calibration/starter-profiles/r28_eight_profile_balance.json` — the
  8-team R28 balance measurement (re-measured below; **I did not overwrite it**).
- `evidence/calibration/stage2_archetype_parity_replay.json` and the other
  stage-2 parity replays, to the extent any round 1–4 freeze occurs in them.
  Note the two collapses *reported* from that file (Workhorse r6, Green Pioneer
  r8) are **outside** the gate and are unaffected.
- `evidence/calibration/fixed_policy_measurements.json` — the single-lever
  sensitivity figures (`production_plus_25` +12.40 etc.) were measured on runs
  that contained these freezes.
- Any v5/v6 envelope replay fixture whose captured game has a rounds 1–4 customs
  event. I did **not** re-run GSP-CRV2-01's envelope regression; that belongs to
  its owner and I am not claiming it clean.

### Test runs

All under `flock -w 1800 /tmp/globalstrat-backend-test.lock`, each starting its
own disposable PostgreSQL 16 container with a generated credential. The
production database at 192.168.50.38 was never contacted and no systemd
environment file was read.

| command | result |
|---|---|
| `test-postgres core.tests.test_cc18_compliance` (baseline, before any change) | **Ran 14 — OK** |
| `test-postgres core.tests.test_zero_production_compliance_freeze` (before repair) | **Ran 8 — FAILED (failures=6)** |
| `test-postgres` × 8 modules (after repair, before reconciling CC-18) | Ran 129 — FAILED (1 failure, 1 error) — the two tests above |
| `test-postgres` × 8 modules (after repair, CC-18 reconciled) | **Ran 130 — OK** in 11.490s |

The 8 modules: `test_zero_production_compliance_freeze`, `test_cc18_compliance`,
`test_calibration`, `test_scoring_dispositions`, `test_leaderboard_tiebreak`,
`test_cc19_sc_engine`, `test_rd_scoring_retired`, `test_engine`. No full backend
suite — GSP-CRV2-09 owns it.

### Measured consequence on the 8-team replay

`run-calibration-postgres --field-sizes 8 --rounds 10 --name-seed 20260912
--baseline-only`, the same command and seed as the R28 measurement, written to
a scratch path so the committed evidence file was not overwritten.

**Zero-production rounds, before → after:**

| round | profile | before | after |
|---:|---|:--:|:--:|
| 1 | The Turnaround | ✗ lost | **gone** |
| 2 | The Ecosystem Player | ✗ lost | **gone** |
| 2 | The Volume Champion | ✗ lost | **gone** |
| 4 | The Ecosystem Player | ✗ lost | **gone** |
| 5 | The Ecosystem Player | ✗ lost | ✗ still lost |
| 6 | The Workhorse | ✗ lost | ✗ still lost |
| 7 | The Turnaround | ✗ lost | ✗ still lost |
| 8 | The Green Pioneer | ✗ lost | ✗ still lost |

Every collapse inside the disclosure gate is gone; every one outside it remains.

**Finishing order:**

| profile | before | after | Δ index |
|---|---|---|---:|
| The Heritage Manufacturer | #1 98.12 | #1 98.82 | +0.70 |
| The Brand Builder | #2 92.28 | #2 90.43 | −1.85 |
| The Ecosystem Player | #5 59.49 | **#3 76.64** | **+17.15** |
| The Volume Champion | #4 75.01 | #4 76.12 | +1.11 |
| The Innovator | #3 77.64 | **#5 73.77** | −3.87 |
| The Workhorse | #6 57.45 | #6 67.61 | +10.16 |
| The Turnaround | #7 56.28 | #7 66.29 | +10.01 |
| The Green Pioneer | #8 55.97 | #8 65.90 | +9.93 |

**Index spread 42.15 → 32.92.**

Two things in that table matter more than the ranks.

First, **the R28 report's headline observation does not survive the repair.**
It recorded that "the three profiles that never lost a round finished 1st, 2nd
and 3rd". After the repair The Ecosystem Player finishes **3rd while still
losing round 5**, and The Innovator — which never lost a round — falls to 5th.
Finishing order was even more defect-driven than the report could see.

Second, and unexpectedly, **the repair defused the catastrophic penalty even in
the rounds it did not remove.** The remaining four collapses now cost the
composite cap's flat 5.00, not the ranking guard's 13–18:

| profile | round | before | after |
|---|---:|---|---|
| The Green Pioneer | 8 | 70.43 → 52.62 (**−17.81**, ranking guard) | 67.6 → 62.6 (**−5.00**, composite cap) |
| The Workhorse | 6 | 66.17 → 48.86 (**−17.31**, guard) | 64.0 → 59.0 (**−5.00**, cap) |
| The Turnaround | 7 | 64.52 → 50.92 (**−13.60**, guard) | 66.0 → 61.0 (**−5.00**, cap) |

The ranking guard fires only when the inactive firm's index is at or above
`min(active_indexes)`. Once the field is no longer torn apart by earlier
freezes, a firm that loses one round is not sitting above the whole pack, so
the guard does not engage. **The 17.81-point events were a second-order
consequence of the first-order defect.** That is the strongest single argument
that the priority ordering in the handoff — question 1 first — was right.

### What the repair does **not** fix, stated plainly

Four collapses remain, all in rounds 5–8, and they are **not** the same defect.
From round 5 the document is filable through both the API and the UI, costs
nothing, and completely prevents the trigger
(`test_filing_the_document_prevents_the_freeze_once_unlocked`). A team that
does not file it has made an omission it was free to avoid.

So the residue is a **measurement** problem, not an engine one: the documented
"competent baseline" in `handoff_readiness_v2/evidence/adversarial-balance/harness/baseline.py`
never writes a `CustomsClassificationDecision`, and therefore is not competent
in this dimension from round 5. Every remaining collapse in the R28 replay is
the baseline policy's omission, not the starting profile's fault. Any re-run of
the R28 balance measurement should either file the document as part of competent
play or state that it deliberately does not.

That still leaves a live rules question I am not qualified to settle: whether a
one-click, zero-cost form omission should cost a team its **entire round of
trading** plus an inactivity penalty. Residual exposure for a team that never
files is 12% per round across rounds 5–10 — a **53.6%** chance of losing a whole
round somewhere in a 10-round game. See the recommendation below.

---

## Question 2 — is the inactivity classification right?

**This is a rules-owner decision. I have not changed it and I am not
recommending that a builder change it.**

### What the classification actually tests

```python
def material_revenue_floor(revenues):
    return max(D('1'), highest_positive_revenue * D('0.01'))

def is_commercially_inactive(revenue, floor):
    return D(str(revenue or 0)) < floor
```

It tests **realised revenue and nothing else**. Not whether the team submitted
decisions, not whether it produced, promoted, staffed or held stock, not
whether it was solvent, and not why its revenue was zero. That was deliberate:
V2-022 found the previous intent-based test was defeated by setting
`production_volume = 1` for $181.86, buying +0.1623 composite and +3.25 index
while selling nothing. "Declaring an intention to produce is not competing."

**Can a playing team be caught by it? Yes — trivially, and not only by a
freeze.** Any team whose revenue falls below 1% of the round leader's is
classified inactive. A total blackout guarantees it. This is demonstrated, not
argued: `test_a_single_market_freeze_costs_the_entire_round`.

The two controls that consume the classification are very different animals:

| control | cost | bounded? | writes to |
|---|---|---|---|
| composite cap (`COMMERCIAL_INACTIVITY_COMPOSITE_CAP = 0.25`) | `(0.25 − composite) × 20`, at most **5.00** | **yes** | that round's score |
| `_enforce_inactive_revenue_invariant` | `min(active_indexes) − 0.01` | **no** | `team.performance_index` — **carried forward** |

### The case for leaving it alone

It exists for a real reason and it works. The V2-022 probes fail against it:
the `$1/$1` strategy went from +1.91 index to −0.09, and the one-unit bypass
from +0.1623 composite to 0.0000. The owner has already ruled once on this
exact interaction — the V2-022 supplementary disposition holds that a
compliance-frozen team below the floor **takes the cap as well as the freeze**,
because "the two controls answer different questions … they are meant to
stack." Nothing in my finding contradicts the reasoning behind that ruling.

### The case for revisiting it

The supplementary disposition was adopted when the freeze was understood as
**the consequence of a compliance failure**. For rounds 1–4 that premise was
factually wrong: there was no failure, because there was no permitted action.
The ruling was sound reasoning applied to a mis-stated fact. My repair removes
the mis-stated fact, which is the honest way to answer this — but it does not
answer whether the stacking is right when the freeze *is* earned.

Two structural observations the owner may not have had in front of them:

1. **The ranking guard punishes in proportion to prior success.** It drops the
   firm to just below the *worst* active firm. A leader frozen in round 8 loses
   more than a straggler frozen in round 8 — measured at −17.81 versus the
   −5.00 the same event costs a mid-pack firm. The penalty is indexed to how
   well the team was doing, which is the opposite of proportionate.
2. **It writes to carried state.** `performance.py:374` sets
   `team.performance_index = new_index`. The composite cap costs a round; the
   ranking guard costs the *game*, because the reset position is the base every
   later round accumulates from. The trajectories show it: Green Pioneer never
   recovers its pre-round-8 index in the remaining two rounds.

There is also a **triple count** for one event: the frozen firm loses its
revenue (the natural financial loss, ≈ −8M), that loss then depresses the
market and financial components of its composite in the same round, and then
the cap and guard are applied on top of the already-depressed composite.

### The options, with measured consequences

| option | measured consequence | reopens V2-022? |
|---|---|---|
| **(a) Leave it** | The repaired 8-team run: 4 collapses remain, each costing 5.00; spread 32.92; order Heritage/Brand Builder/Ecosystem. The guard did not fire at all in the repaired run — but it will whenever a leader is frozen while the field is spread, at up to ≈ −17.8. | no |
| **(b) Exempt a team that submitted decisions** | Reopens the V2-022 exploit exactly. Measured at adoption: +0.1623 composite, +3.25 index, for $181.86. **Do not do this.** | **yes — fatally** |
| **(c) Exempt a team whose revenue was blocked by an engine-imposed market-access freeze** | Cause-based, not intent-based, so a voluntarily silent team is unaffected (it has no freeze) and the exploit stays closed. Would have removed all 8 collapse penalties; the 4 post-repair ones would cost only the natural −8M. Directly reverses the V2-022 supplementary disposition. | no |
| **(d) Keep the classification; enforce "must not outrank" on rank, not by rewriting the carried index** | Satisfies the guard's stated purpose exactly — an inactive firm is ordered below every active firm on the leaderboard — while removing the unbounded, permanent destruction of accumulated standing. The frozen firm still loses the round's revenue and still takes the bounded 5.00 cap. | no |

### My recommendation

**(d), with (a) as the safe fallback, and explicitly not (b).**

The composite cap is proportionate and bounded and should stay exactly as it
is: it is a scoring answer to a scoring problem, it costs at most 5.00, and it
is what closes the V2-022 exploit. The part that is disproportionate is
`_enforce_inactive_revenue_invariant` rewriting a **carried-forward** index to a
positional floor. Its stated purpose — "a firm that did not compete must not
outrank one that did" — is a statement about *rank*, and it can be enforced on
rank directly without destroying a game's worth of accumulated index.

I recommend **(d)** because it is the only option that keeps every anti-free-rider
property the owner has already ruled on while removing the one effect that is
demonstrably able to decide a competition on a single round. I did not implement
it: changing the guard is a scoring-rule change and belongs to the rules owner.

If the owner prefers minimal change before the competition, **(a)** is defensible
now that question 1 is repaired — the guard did not fire once in the repaired
8-team run. I would not ship **(b)** under any framing.

**A separate question the owner should rule on at the same time:** whether a
free, always-available form omission should cost an entire round of trading at
all. Options are to lower `baseline_enforcement_probability_per_round` from
0.12, to reduce the consequence from a full market freeze to the $120,000
penalty alone, or to require the document only once rather than per round.
I have not changed the scenario data.

---

## Findings — handed over, register not edited

| ID | Area | Severity | Owner | Finding | Evidence | Status |
|---|---|---|---|---|---|---|
| *(new)* | Engine / compliance | **P0** | engine (this report) | `compliance_engine._trigger_applies` fired the `customs_documentation` regime on the absence of a `CustomsClassificationDecision` in rounds 1–4, where `logistics.customs_classification` is progressive-disclosure gated to round 5 and the serializer and UI both refuse it. With `enforcing_market: all`, `shipment_hold_rounds: 1` and one `TeamMarketPresence` per starter profile, a single 0.12 draw removed a solvent firm from its only market for a whole round: no demand rows, no revenue rows, no `RoundResultProductMarket` row, revenue 0.00, net ≈ −8,000,000, cash 27–50M. 72.1% chance per team over 10 rounds. | `test_zero_production_compliance_freeze` (6 failures before, OK after); 8-team replay before/after | **Repaired here** |
| *(new)* | Calibration harness | **P1** | GSP-CRV2-11 | The documented competent baseline (`harness/baseline.py`) never writes a `CustomsClassificationDecision`, so from round 5 it is not competent in a dimension that costs an entire round at 12%/round. All four surviving collapses in the repaired R28 replay are this omission, not the starting profile. The R28 balance measurement should be re-run with it filed, or state that it deliberately is not. | repaired replay: collapses only at rounds 5, 6, 7, 8 | Open — not mine to repair |
| *(new)* | Scoring / anti-exploit guard | **P1** | **Rules owner** | `_enforce_inactive_revenue_invariant` rewrites `team.performance_index` — carried state — to `min(active) − 0.01`. The cost is unbounded and scales with how well the team was doing (−17.81 for a leader vs −5.00 for a mid-pack firm on the identical event), and it is permanent rather than costing one round. The composite cap, by contrast, is bounded at 5.00 and proportionate. Options and a recommendation are in "Question 2" above; recommendation is **(d)**. | `performance.py:261-279`, `:374`; before/after trajectories | Open — rules decision, deliberately not taken |
| *(new)* | Engine / compliance ↔ R26 | **P2** | engine | On a compliance freeze `revenue.py:111-118` `continue`s **before** writing `context.revenue`, so `calculate_cogs` charges nothing and no inventory is carried: the team ordered production and got it free. This contradicts R26 (2026-09-12) — "a product that cannot be sold is still paid for … the factory ran and the money went out" — and the deliberate comment at `revenue.py:74-80` that implements R26 for the not-for-sale path by processing the row rather than skipping it. Not repaired: it changes competitive outcomes (it currently *favours* the frozen team) and the R26 read-across is arguably a rules call. | `revenue.py:111-118`; `costs.py:52` | Open — reported, not repaired |
| *(new)* | API / progressive disclosure | **P3** | decision-path | `_reject_locked_fields` skips any field whose submitted value is falsy, and `CustomsClassificationDecision.classification` has model default `general_trade`. So `POST …/logistics/ {"customs":[{"destination_market": N}]}` creates a valid row in a locked round, bypassing both the disclosure gate and (pre-repair) the regime. Not reachable from the UI, which filters on a truthy classification. Largely moot post-repair, but the gate is still bypassable. | `sc_serializers.py:29-46`, `:396-414`; `sc_decisions.py:110-135` | Open — reported, not repaired |
| *(new)* | Engine / compliance | **P3** | engine | `uflpa`'s mitigation `tier_2_3_visibility_investment` is itself gated to round 5, so a team that sources from a Xinjiang-adjacent supplier in rounds 1–4 can trigger the regime but cannot buy the mitigation. Lesser than the customs case — the trigger is an action the team chose, so it is avoidable — and therefore not repaired. | `compliance_engine.py:53-60`; `disclosure.py` | Open — reported, not repaired |

---

## What I could not determine

- **Whether the pre-existing stage-2 parity replays contain rounds 1–4 customs
  freezes.** The two collapses reported from
  `stage2_archetype_parity_replay.json` are at rounds 6 and 8, both outside the
  gate, so the repair does not change them; but that file does not persist
  compliance events, so I cannot say from the artefact alone whether any
  *other* team took a rounds 1–4 freeze that shortened its round without
  zeroing it. Re-running it would settle it; I did not, as it is CRV2-11's
  artefact.
- **Which stored determinism manifests are actually invalidated.** I established
  that `compliance_enforcement` is a competitive section and that the repair
  changes rows in it, so any affected game's hash moves. I did not enumerate the
  fixtures or re-run GSP-CRV2-01's v5→v6 envelope regression — that is its
  owner's call, and I am not claiming it clean.
- **Whether the 0.12 probability and the full-round freeze are calibrated to
  anything.** They are authored scenario values. I found no measurement
  justifying either, and I did not change them.
- **Whether the other two shipped scenarios behave identically.** The customs
  regime is authored with `enforcing_market: all` in consumer electronics; I did
  not audit clean energy or media for their compliance regimes, and their teams
  are spread across 2–3 home markets, which may change the blast radius of a
  single freeze.
- **Whether a real cohort would file the document from round 5.** The UI
  surfaces it, but there is no deadline alert for a missing customs
  classification the way there is for a missing price. Whether students find it
  is an instructional question I cannot measure here.
- **Why `checks/bin/run-checks` reports a revision match when invoked directly
  and a mismatch when invoked by the pre-commit hook** — see "Commit policy".
  The consequence is that the aide-checks suite did not actually run against
  this commit under either invocation, so I am claiming no check clean.

---

## Commit policy

**The commit used `--no-verify`, as the handoff sanctions.** The pre-commit
hook refused it on the aide-checks revision mismatch the handoff describes:

```
run-checks: ERROR revision mismatch — could not run.
run-checks: runner built from : fb08db4
run-checks: repo vendored at  : e710f26
run-checks: a stale runner reports PASS for checks it does not carry. That is a false
            pass, not a pass, so this is exit 2 in every mode including --report-only.
```

The hook's own header sanctions the bypass: *"Bypassable with --no-verify; the
deploy gate is the layer that is not."*

**One discrepancy I am recording rather than smoothing over.** Invoking the same
runner path directly from this worktree
(`checks/bin/run-checks --fast --repo=<worktree>`) reported the opposite —
`revision e710f26 matches …/checks/.aide-checks-rev`, two checks run, zero
blocking failures. Invoked through the hook, the same binary path reports itself
as built from `fb08db4` and refuses. I did not determine why the runner resolves
its own build revision differently under the two invocations. An earlier draft of
this report asserted, on the strength of the direct run alone, that the hook
passed and no bypass was needed; that was wrong, and the hook's refusal above is
what actually happened. The checks were therefore **not** run against this
commit, by either path.

## Files changed

| file | change |
|---|---|
| `backend/core/engine/compliance_engine.py` | **engine** — gate the customs trigger on the effective unlock round |
| `backend/core/tests/test_zero_production_compliance_freeze.py` | **new** — 8 focused tests; 6 failures before the repair |
| `backend/core/tests/test_cc18_compliance.py` | two tests moved round 1 → 5 and preserved; one test added for the reversal |
| `handoff_readiness_v2/completion/ZERO_PRODUCTION_DEFECT_2026-09-12.md` | this report |

No scoring code, no scenario data, no serializer, no view and no frontend file
was changed. `V2_FINDINGS_REGISTER.md` and `LAUNCH_CHECKLIST_V2.md` were not
edited. The committed R28 evidence file was not overwritten; the post-repair
replay was written to a scratch path.
