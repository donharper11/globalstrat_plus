# GSP-CRV2-11 Stage 3 — trajectory and AI accounting implementation

## Landed rules

Population now compounds over every completed market-growth period. For round
`r`, the effective population is the authored segment population multiplied by
the product of `1 + effective_growth_rate_t` for `t = 1..r`, then by the
current round's demand multiplier. Scheduled `MarketConditionByRound` growth
modifiers and time-bounded event growth modifiers are replayed in their own
periods; a temporary event is not projected backwards over the whole game.

The resulting Consumer Electronics parameter trajectory, before teams divide
the pool, is:

| round | addressable population | adoption pool | reference industry revenue |
|---:|---:|---:|---:|
| 1 | 57,953,500 | 1,629,470 | $824,772,500 |
| 2 | 64,625,302 | 2,289,383 | $1,142,752,497 |
| 3 | 65,227,255 | 2,938,333 | $1,450,179,758 |
| 4 | 74,046,259 | 3,952,969 | $1,927,266,762 |
| 5 | 80,561,643 | 5,040,030 | $2,398,814,549 |
| 6 | 78,107,302 | 5,913,537 | $2,737,337,304 |
| 7 | 90,904,647 | 7,373,160 | $3,307,899,260 |
| 8 | 102,266,153 | 8,901,190 | $3,864,358,737 |
| 9 | 100,676,020 | 9,451,719 | $3,857,762,617 |
| 10 | 107,504,457 | 10,339,572 | $4,031,734,222 |

Revenue is the scenario's segment `revenue_per_unit` reference, not a forecast
of the prices students will choose. The stated economic intent is therefore a
growing, constrained market: the pool is nearly 6.35 times round 1 in round 10,
not a late-game decline caused by a non-growing `M` and accumulating `N`.

## AI rule: Fix A landed; Fix B remains a design decision

AI competitors still enter the same total-attractiveness denominator, so they
take exactly the same theoretical share as before this change. A resolved pool
now writes:

```
human adoption + AI adoption + unserved adoption = Bass adoption pool
```

to cents for every game, round, segment and market. `RoundResultAIAdoption`
keeps each competitor's fit, attractiveness, share and take;
`RoundResultDemandReconciliation` keeps the aggregate identity. Capacity and
price-constrained human demand is explicit `unserved`, not silently reassigned
to AI.

AI take is deliberately **not** added to cumulative `N` in this pass. That is
Fix B, which changes the Bass curve (higher early imitation and a sooner-empty
late pool) and must be decided only from an all-ten-round side-by-side replay
with this compounding population rule. It has not been smuggled into an
accounting repair.

## Starting-score rule

Round 0 continues to publish the starting revenue and the contrasting company
profiles as briefing evidence, but every equal-base performance index is now
ranked joint first. Revenue cannot be a score tie-break before a team has made
a decision.

## Preference contract

Scenario load now rejects an ideal outside its feature range, a negative weight,
a non-positive tolerance, and weight on a platform feature unavailable in every
generation. It reports, rather than rejects, positive weight on a Gen-1
unavailable feature: Consumer Electronics has deliberate-looking upgrade
pressure on `ai_features`, `connectivity`, and `iot_integration`; the report
makes that author choice visible. All three shipped scenarios pass errors
(Consumer Electronics has four warnings; Clean Energy and Media have three
each).

## Remaining calibration decisions

The field-size, archetype-parity, sensitivity and Fix-B runs still require a
resolved baseline game. They are not inferred from the arithmetic above. The
release environment's database credential currently rejects isolated test
connections, so this change is held before release-scale certification rather
than claiming a run that could not execute.
