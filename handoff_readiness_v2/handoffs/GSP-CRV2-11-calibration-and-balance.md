# GSP-CRV2-11 — Calibration: the economy, the starting field, and stakeholder response

**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoffs/EXECUTION_PROTOCOL.md`
**Source:** `handoff_readiness_v2/RULES_AND_CALIBRATION_ASSESSMENT.md` Part B
**Owner:** simulation/calibration engineer, independent of the CRV2-10 implementer
**Depends on:** GSP-CRV2-10 frozen. Do not calibrate against rules that are
about to change — a dominant line found under client-priced R&D says nothing
about the game that ships.

## Objective

Establish, by measurement, that the ten-round economy behaves the way the course
needs it to: teams start equal on score and unequal in position, the market has
a deliberate size and trajectory, decisions move outcomes by an amount worth
deciding about, and stakeholder response rewards *matching* a segment rather
than maximising every slider.

This is the intensive one. It is measurement first and tuning second, and its
output is as much a written statement of what the economy is *supposed to do* as
it is a set of changed numbers.

## Prior art — read before deriving anything

`~/projects/BECSR` spent a calibration cycle on this exact problem and the
reasoning is preserved in code and reports. Read, at minimum:

- `handoffs_v1/reports/demand_diagnostic.md` — how to establish whether the
  engine is faithful before touching a dial. Its method (replay the seed's own
  arithmetic in an independent simulator that touches no product code, then
  compare round by round) is the method this handoff should use. Its verdict is
  the one to expect: the engine was faithful to 0.2%, and the problem was the
  seeded market.
- `handoffs_v1/reports/reprice_calibration.md` — Bass is homogeneous of degree 1
  in `(M, N)`. Price and market size must move together; their product is the
  company size being chosen. A price change alone does not shrink the company,
  it deletes it.
- `services/performance_index.py` — why the pillars are alignment and not mean
  feature level, and why the economic axis is share/margin/health and not
  revenue.

## Stage 1 — measure before tuning

No dial moves in this stage.

1. **Is the engine faithful?** Reproduce the Bass and allocation arithmetic in
   an independent script that imports no engine code, run both against the same
   seeded scenario, and compare per round per segment. Report the divergence.
   Everything after this depends on knowing the engine delivers what the
   parameters specify.
2. **The economy's trajectory, rounds 0–10.** Total addressable population,
   adoption pool, units, and industry revenue per round per market per segment,
   at the authored parameters, with a competent baseline field. Plot it. State
   what it is *supposed* to be; the gap is the calibration target.
3. **Confirm B2.** `events.py:388-392` computes `effective_population` from the
   static authored population every round, applying growth once and never
   compounding, so round 10's market equals round 1's while `N` accumulates and
   `M − N` shrinks. Confirm the economy contracts over a ten-round game. If it
   does, this is the single largest calibration defect and it is repaired here.
4. **Confirm B3.** AI competitors dilute every human share
   (`bass_engine.py:151-153`) but write no adoption row and never enter
   cumulative `N` (`:331`). Quantify what fraction of the pool they take and
   what saturation looks like with and without them counted.
5. **Round-0 parity.** Verify all teams open on `performance_index_base`
   (`bootstrap.py:300-307`) — expected to hold — and then measure the
   consequence of the leaderboard tie-break on revenue (`:369`), which produces
   a ranked ladder from an equal field before anyone has decided anything.
   Report the round-0 `* 10` adoption scale factor (`:175`).

## Stage 2 — starting positions: equal score, unequal position

The requirement is that every team opens on the same performance index and the
same rank, while genuinely differing in strengths, market position, price point
and strategic problem — so a team's first task is to read its own situation
rather than to copy a template.

The authored half is already good: four archetypes with distinct platform
strengths, prices, volumes, shares, debt and revenue. What is unmeasured is
whether they are **balanced** — whether one archetype's strengths happen to sit
on the segment preferences with the largest populations and heaviest weights.

1. Hold decisions constant across archetypes and run the field. Any spread in
   round-1..3 outcome is a starting-position advantage, not a decision outcome.
2. Adjust starter profiles and/or segment preferences until no archetype has a
   material unearned edge, **without** flattening the differences. Equal
   expected value, different shape, is the target.
3. Resolve the leaderboard tie-break: either show no rank at round 0, or rank
   every team joint-first. Do not present a revenue ladder as a score ladder.
4. Consider whether all four profiles sharing `home_market: NA` is intended.
   The stated goal includes teams targeting different regions; today they all
   start in the same one.
5. Replace the `* 10` round-0 scale factor with a derived figure, or state in
   the scenario what it represents.

## Stage 3 — market size and trajectory

1. Make population growth compound per round, or state and implement whatever
   trajectory the course wants (linear, S-curved, shocked by events). Growth
   must accumulate across ten rounds.
2. Settle B3 per Ruling 3: AI competitors either consume the pool and saturate
   it, or act as a benchmark that does not consume. Implement one; the current
   hybrid — consume without saturating — is what must not remain.
3. Re-derive segment populations, `bass_p` and `bass_q` against the intended
   industry revenue per round. Remember the homogeneity result: changing price
   without changing `M` changes the company by exactly that factor and nothing
   else.
4. State the intended economy in the scenario as authored values, so a future
   scenario author has a target rather than a set of inherited constants.

## Stage 4 — sensitivity: does each decision matter?

Reuse GSP-CRV2-06's screening method and honour its budget: legal minimum,
documented baseline and legal maximum per numeric dimension; each category once;
one fixed scenario/opponent/seed. Escalate to a denser sweep only on a material
response, cliff or non-monotonicity.

Report, per decision dimension, whether it is **flat** (the decision does not
matter — a design problem), **cliffed** (small changes swing the result — a
fairness problem), or responsive. Price, promotion, distribution, production
volume, R&D level, market entry and headcount are the minimum set.

Pay particular attention to the derived marketing features in
`preference_engine.py:296-370`, all five of which contain hand-chosen constants
(`promotion_benchmark_per_unit`, the `base_reach_map`,
`brand_awareness_halflife`, the `f_max / 2` scalings). BECSR's defect C is the
cautionary case: a `0.5` baseline constant meant a good decision made things
worse — *every* stakeholder emphasis a student allocated lowered that
stakeholder's demand, and the bonus half of the lever had never once fired in
four full replays. A single constant, never measured, inverting a mechanic.

## Stage 5 — stakeholder response: preferences, ideals and weights

The map from a team's feature levels to a segment's ideal preference levels, and
the weights on those preferences, is what drives every fit score and therefore
every adoption outcome. It is currently authored in YAML and validated by
nothing.

1. **Validate the authored preferences.** For every segment × market × feature:
   is the `ideal_value` inside the feature's own `min_value`..`max_value`? Are
   the weights non-degenerate? Is any weight spent on a feature whose ceiling is
   0 on every generation available in that round? BECSR shipped fixes for the
   first (`32ed072`, clamping ideals outside their feature's range) and the
   third (`bfd45c7`, excluding dead preference weight from alignment) within the
   last month. An unreachable ideal spends weight on a term no team can move.
2. Note the known case: `ai_features`, `connectivity` and `iot_integration` have
   ceiling 0 on Gen 1 while Value Seekers in NA carry authored weights on all
   three. Plausibly a deliberate pull toward upgrading; never measured. Decide
   which it is.
3. Add a scenario-load validation that refuses, or loudly reports, an ideal
   outside range and a weight on an unreachable feature. This is a scenario
   contract, not a one-off data fix — the next scenario author needs it too.
4. Review the Gaussian `tolerance` values: a tolerance wide enough that every
   team scores near-identically makes the feature decorative; one narrow enough
   that only an exact match scores makes it a cliff.
5. Review AI competitor fit trajectories and the investor/persona response paths
   for the same class of defect.

## Stage 6 — performance index composition

1. Measure whether market share and the revenue term in the financial component
   double-count scale (`performance.py:20-26`, `_financial_component`). BECSR's
   ruling is that they are the same number and scoring both crowds out
   profitability. Confirm or refute here rather than inheriting the conclusion.
2. Resolve the default fit of `0.5` for segments in unentered markets
   (`performance.py:88-98`) — a team currently earns middling stakeholder credit
   for markets it is absent from. State a rationale or change it.
3. Confirm the composite cannot be won one-dimensionally: dumping price to buy
   share should cost margin; harvesting should cost share. Show the trade-off
   exists.

## Stage 7 — field size and saturation

Answers Ruling 4 with a measurement rather than an opinion.

Run the calibrated economy at 4, 8, 16, 24 and (if the cap allows) 32 teams,
holding decisions competent and constant. Report per-team share, revenue and
the spread between best and worst play at each size. Saturation is the point
where an individual team's decisions stop moving its outcome because the field
has diluted the pool — that is the number that matters, not the point where the
software slows down.

Report the same for team size: at what point do additional members stop having a
decision to own?

Deliver a recommended cap for teams-per-game and players-per-team, with the
measurement behind it. GSP-CRV2-10 Stage 6 enforces whatever this stage lands
on.

## Acceptance

- A written statement of the intended economy — market size, industry revenue
  and adoption per round for rounds 0–10 — with measured output matching it.
- Round 0: identical index, identical rank, materially different positions; no
  archetype holds an unearned edge.
- Population growth accumulates; AI competitor treatment is one coherent rule.
- A sensitivity table for every exposed decision dimension, labelled flat /
  cliffed / responsive, with the flat and cliffed ones dispositioned.
- Authored preferences validated, dead weight identified and dispositioned, and
  a scenario-load check that prevents the next one.
- A recommended field size with the saturation measurement behind it.
- All three shipped scenarios pass the scenario-load validation, not only
  consumer electronics.

## Evidence

`handoff_readiness_v2/evidence/calibration/` — the independent replay script and
its comparison, trajectory tables and plots, per-archetype parity runs, the
sensitivity table, the preference validation report, saturation runs, and every
seed and scenario revision used. Machine-readable results for every dimension;
plots only where screening showed something.

## Verification budget

Cheap development uses one seed, one opponent set and short horizons and
produces no evidence. Release-scale runs come once, from the frozen candidate.
No full backend suite, no load run, no concurrency matrix, no determinism
replay. Where a recalibration changes a value GSP-CRV2-06's tournament searched
against, say so — its strongest-strategy result is evidence for its own
scenario revision and not automatically for the recalibrated one.
