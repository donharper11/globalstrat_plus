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

`events.py` computes, every round:

```python
base_pop = float(segment.population_size)      # the static authored value
growth   = base_pop * state.effective_growth_rate
seg_state.effective_population = (base_pop + growth) * state.demand_multiplier
```

Growth is applied **once, to the authored constant, every round**. It never
accumulates. Measured across the whole economy:

| | round 1 | round 5 | round 10 |
|---|---|---|---|
| M today (flat) | 58,590,000 | 58,590,000 | 58,590,000 |
| M compounding | 58,590,000 | 78,210,778 | 115,692,118 |

**The market is the same size in round 10 as in round 1.** Meanwhile `N`
accumulates, so `M − N` drains:

| round | adoption pool (flat) | compounding | ratio |
|---:|---:|---:|---:|
| 1 | 1,655,745 | 1,655,745 | 1.00x |
| 5 | 4,129,757 | 5,053,306 | 1.22x |
| 8 | 5,691,569 | 8,821,544 | 1.55x |
| 9 | **5,697,567** | 10,050,246 | 1.76x |
| 10 | **5,364,072** | 11,176,920 | 2.08x |

**The pool peaks in round 9 and falls in round 10.** Penetration reaches
**70%** economy-wide. Per segment-market it is worse than the aggregate hides:

- **Tech Enthusiasts peak in round 5** — half the game is played in decline.
- **Premium Consumers reach 92% penetration**; their round-10 pool is **32%
  below** round 9.
- **15 of 25 segment-markets are already contracting by round 10**; 5 are past
  90% penetration.

By round 10 the late game is **less than half** the size the authored growth
rates describe. A team's late-round decisions compete over a shrinking pool,
which inverts the intended arc of a ten-round course.

Penetration is identical across markets for a given segment, because in the
flat regime `N/M` depends only on `p` and `q` — the authored per-market growth
rates (NA 0.02 … AFR 0.12) change absolute size and **nothing about the shape**.
That is the defect in one sentence: authored growth currently cannot alter the
trajectory.

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
