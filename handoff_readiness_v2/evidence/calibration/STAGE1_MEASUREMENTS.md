# GSP-CRV2-11 Stage 1 — measurements

**No dial moved.** Everything here is measurement or code inspection, as the
stage requires.

Scenario: `backend/scenarios/consumer_electronics_2026.yaml`
Tool: `independent_bass.py` — reads the scenario YAML, imports no engine code,
writes the Bass arithmetic out longhand. A simulator sharing a helper with the
engine would agree with it about a shared mistake.

Status: **items 1, 3, 4 and 5 are measured; item 2 has its parameter-level
trajectory but not its competent-baseline field trajectory.** The replay below
is an accounting and engine-fidelity run, not an archetype-balance
certification: a constant production plan is deliberately capacity-constrained
and therefore cannot establish that the four starting positions have equal
expected value.

---

## Item 3 — B2 confirmed. The economy contracts. (largest defect)

Before this handoff, `events.py` computed, every round:

```python
base_pop = float(segment.population_size)      # the static authored value
growth   = base_pop * state.effective_growth_rate
seg_state.effective_population = (base_pop + growth) * state.demand_multiplier
```

Growth was applied **once, to the authored constant, every round**. It never
accumulated. Market conditions made the one-period value vary, but could not
carry population from a prior round. The independent replay now follows the
actual engine input path — `markets[].base_growth_rate` plus each
`market_conditions` growth modifier — rather than the informational,
engine-unused per-segment `growth_rates` YAML field. Measured across the whole
economy:

| | round 1 | round 5 | round 10 |
|---|---|---|---|
| M pre-fix (one-period) | 57,953,500 | 61,499,100 | 57,953,500 |
| M compounding (shipped) | 57,953,500 | 80,561,643 | 107,504,457 |

**The scheduled market condition can vary the one-period size, but no growth
carries across rounds.** Meanwhile `N` accumulates, so `M − N` drains:

| round | adoption pool (flat) | compounding | ratio |
|---:|---:|---:|---:|
| 1 | 1,629,470 | 1,629,470 | 1.00x |
| 5 | 4,234,041 | 5,040,030 | 1.19x |
| 8 | **6,145,081** | 8,901,190 | 1.45x |
| 9 | 5,565,161 | 9,451,719 | 1.70x |
| 10 | 5,200,428 | 10,339,572 | 1.99x |

**The pre-fix pool peaks in round 8 and falls for two rounds.** Penetration
reaches **71%** economy-wide. Per segment-market it is worse than the aggregate
hides:

- **Tech Enthusiasts peak in round 5** — half the game is played in decline.
- **Premium Consumers reach 93% penetration**; their round-10 pool is **34%
  below** round 9.
- **20 of 25 segment-markets are already contracting by round 10**; 5 are past
  90% penetration.

By round 10 the late game was **about half** the size the authored growth path
describes. A team's late-round decisions competed over a shrinking pool, which
inverted the intended arc of a ten-round course. CRV2-11 now compounds each
historical market rate, including finite event windows, into the effective
population.

The pre-fix calculation did not accumulate any authored growth path. That is
the defect in one sentence: the economy could be shocked in a round, but it
could not grow across the game.

## Item 5 — round-0 parity holds; the ladder beneath it does not

**Index parity: confirmed.** Every team is written
`index_value = scenario.performance_index_base` at round 0
(`bootstrap.py:300-307`), with `satisfaction_score` 0.5000 for all.

**The tie-break makes a ladder anyway.** `bootstrap.py:369` sorts:

```python
leaderboard_data.sort(key=lambda x: (-float(x['index']), -float(x['revenue'])))
```

Indexes are equal, so rank is decided entirely by `starting_revenue`, which is
authored per archetype:

| rank at round 0 | archetype starting revenue |
|---|---|
| 1 | $35,000,000 |
| 2 | $30,000,000 |
| 3 | $28,000,000 |
| 4 | $25,000,000 |

**A fixed 1-2-3-4 ladder before anyone has decided anything**, determined by
which archetype a team was handed. The score says equal; the board says ranked.

**The `* 10` factor is undocumented.** `bootstrap.py:175`:

```python
new_adopters = bass_p * pop * avg_share * 10  # Scale for meaningful numbers
```

The comment is the entire justification. It scales every team's round-0
adoption and therefore the revenue the ladder above is sorted on.

**All four archetypes share `home_market: NA`** — Stage 2 item 4 asks whether
that is intended. It is the authored state.

## Item 2 — trajectory recorded

Full per-round, per-segment, per-market figures for all three regimes (flat,
compounding, static) in `trajectory.json`: `M`, `N`, adoption pool, remaining
pool, penetration and industry revenue. Flat is the **pre-CRV2-11 historical
comparison**; compounding is the **current shipped runtime**.

## Items 1 and 4 — resolved runtime replay

`stage1_runtime_replay.py` created a fresh disposable PostgreSQL database,
loaded Consumer Electronics, held the documented marketing/talent baseline
constant for four teams, and resolved rounds 1–10. It exports every customer
segment-market result to `stage1_runtime_replay.json`. The database was dropped
after the run. No production game or calibration setting was changed.

`independent_bass.py --runtime-input ...` then replayed Bass from the exported
effective population and the preceding **human** cumulative adoption, using
only YAML `p`/`q` values and no engine import. Across 250 observations, the
largest difference between the independently calculated and persisted pool was
**0.005 units** (maximum relative divergence **0.000054290%**): the difference
is the result table's two-decimal rounding. This confirms the delivered engine
implements the authored Bass arithmetic under the exact same `M` and `N`.

The replay also quantifies the existing Fix-A rule. AI competitors received
between **87.80% and 89.60%** of each round's adoption pool; human teams sold
only 52,000–72,000 units per round under the held-constant production plan.
The residual is explicitly recorded as unserved demand, not silently lost.

| round | pool | human adopters | AI take | unserved | AI share |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,629,470 | 72,000 | 1,443,186 | 114,284 | 88.57% |
| 2 | 1,827,841 | 72,000 | 1,613,907 | 141,934 | 88.30% |
| 3 | 1,863,866 | 72,000 | 1,638,200 | 153,666 | 87.89% |
| 4 | 2,139,495 | 72,000 | 1,878,494 | 189,000 | 87.80% |
| 5 | 2,369,004 | 72,000 | 2,098,506 | 198,498 | 88.58% |
| 6 | 2,325,569 | 52,000 | 2,047,622 | 225,948 | 88.05% |
| 7 | 2,685,381 | 72,000 | 2,383,676 | 229,705 | 88.76% |
| 8 | 3,017,743 | 52,000 | 2,703,961 | 261,782 | 89.60% |
| 9 | 2,970,839 | 72,000 | 2,646,707 | 252,132 | 89.09% |
| 10 | 3,175,218 | 72,000 | 2,835,150 | 268,068 | 89.29% |

This is the requested evidence for Fix B, rather than a reason to enable it:
the current model enters human adoption only into `N`. Adding the 88–90% AI
take would make imitation rise much faster early and deplete the pool sooner;
the ten-round side-by-side design decision is still outstanding.

---

## What Stage 1 does not claim

- No further tuning is proposed here. The compounding repair is already
  shipped; Stage 3 still decides whether its authored trajectory needs a
  future calibration adjustment.
- This replay does not certify the held-constant field as competent play or
  balance the starter archetypes. It only certifies the engine arithmetic and
  makes the AI/served/unserved split observable; those are prerequisites for
  the Stage 2 and Fix-B measurements.
