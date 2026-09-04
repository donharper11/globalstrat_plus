# GSP-CRV2-11 Stage 1 — measurements

**No dial moved.** Everything here is measurement or code inspection, as the
stage requires.

Scenario: `backend/scenarios/consumer_electronics_2026.yaml`
Tool: `independent_bass.py` — reads the scenario YAML, imports no engine code,
writes the Bass arithmetic out longhand. A simulator sharing a helper with the
engine would agree with it about a shared mistake.

Status: **items 2, 3 and 5 complete; items 1 and 4 need an engine run.**

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
pool, penetration and industry revenue. The flat column is what ships today.

## Items 1 and 4 — outstanding

- **Item 1, engine fidelity.** The independent simulator exists and produces
  the specified trajectory. Comparing it against delivered output needs a
  resolved ten-round game with a competent baseline field, which is the next
  build.
- **Item 4, AI competitor take.** Confirmed structurally: `bass_engine.py:151-153`
  adds `ai_attract` into `total_attractiveness`, so every human share is
  diluted; `_get_total_cumulative` (`:336-349`) sums only `RoundResultAdoption`
  rows, which are written per *team*, so AI adoption never enters `N`.
  Quantifying the fraction taken needs the same engine run.

---

## What Stage 1 does not claim

- No tuning is proposed here. The compounding column is a **reference**, not a
  recommendation; Stage 3 decides the trajectory the course wants.
- Engine fidelity is **unmeasured** so far. Everything above about the engine is
  read from source or computed from authored parameters; the handoff is right
  that fidelity must be established before any dial moves, and it has not been.
