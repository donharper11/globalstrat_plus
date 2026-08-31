# Rules, calibration and player-experience assessment — pre-CRV2-09

**Prepared 2026-08-30 against `crv2-06-adversarial-balance` / `d768038`.**
**Method: source reading only. Nothing was executed, no database was touched, no
file outside this directory was changed.**

That method statement is the load-bearing sentence in this document. Every item
below is read from code and is marked **READ** — a defect a reader believes is
there. Under the standing rule that a gate is not closed from code inspection
alone, the converse also binds: a finding is not *raised* from code inspection
alone either. Stage 1 of GSP-CRV2-10 confirms or withdraws each one by probe
before any repair is designed. Two of the items below may turn out to be
unreachable through the product UI; they are listed because they are reachable
through the supported API, which is the surface a motivated team will use.

## Why this exists

The v2 programme has been asking "does the platform hold up?" — determinism,
concurrency, audit, load, disputes. It has not yet asked **"are the rules of
play right, and do they hold?"** GSP-CRV2-06 came closest: its Stage-1
legal-space gate inventoried 21 decision fields for type, range and nullability,
and closed V2-018. But it asked whether a field's value was *in range*. It did
not ask whether a field that names a **price** agrees with the price the
scenario authored. That is the gap most of Part A sits in.

## Reference: what BECSR already settled

`~/projects/BECSR` has litigated most of these rules to a ruling, in code, with
the reasoning preserved in the module docstrings. It is the closest available
prior art and its conclusions should be read before re-deriving them:

| Question | BECSR's answer | Where |
|---|---|---|
| Price movement limits | ±30% band off last round's *effective* price; round-1 anchor is the authored starting price, so round 1 is not a special case | `services/pricing.py` |
| Blank/absent price | Cannot be refused (nothing to hand back) — takes the most conservative legal value, the bottom of the band, and says so on the response | `pricing.resolve_blank_price` |
| Budget | `floor + pct x max(prior net profit, 0)`, capped. Additive, not `max(share, floor)` — the `max` form flattened the reward gradient across most of the field | `services/budget.calculate_csr_budget` |
| Overspend | Allowed, never refused; financed as a loan at a published rate, amortised to the final round, interest expensed and never capitalised | `budget.process_loans`, `services/cash.py` |
| R&D lead time | Platform is `developing` for `base + complexity + economy` rounds, capped; cannot be built on until `ready`; base cost charged **at creation**, not at readiness | `r-and-d-mechanic.md` |
| Re-basing a product | Free switch to another *activated* platform; unsold stock on the platform being left is written off at a markdown and the on-hand zeroed | `services/platform_switch.py` |
| Performance index | Relative and ratio measures only (share / margin / health). Absolute revenue bands peg at 1.0 by mid-game and stop discriminating | `services/performance_index.py` |
| ESG pillars | Pillars are **alignment** (how well you matched a stakeholder), not mean feature level (how high you built). The level form made max-everything optimal and was blind to targeting | same |
| One calculator | The cost a team is *shown* and the cost it is *charged* must be the same function, not two functions kept in step by hand | `budget.get_total_program_cost` (RW-50) |
| Market scale | Bass is homogeneous of degree 1 in `(M, N)` — so price and market size must be recalibrated together; and `N` must count units **sold**, not units allocated | `handoffs_v1/reports/reprice_calibration.md`, `demand_diagnostic.md` |

globalstrat+ already has the last one right: `bass_engine.py` applies the
production cap before accumulating `cumulative_adopters`, so `N` counts sold
units. The rest are open.

---

# Part A — Rules and legal space (owner: GSP-CRV2-10)

## A1. The price of R&D is set by the client — **suspected P0** (READ)

`DecisionPlatformDevelopment.committed_cost` and `DecisionRDInvestment.amount` /
`calculated_cost` are **team-supplied numbers**. The scenario authors the real
prices — `PlatformGenerationDefinition.development_cost` / `license_cost`
(`core/models/scenario.py:115`; $5M/$15M/$25M and $8M/$35M/$55M in
`consumer_electronics_2026.yaml:864-988`) and a per-level incremental cost table
— and nothing compares the two.

* The submit validator checks the generation's scenario, unlock round and
  duplication (`core/views/decisions.py:588-601`). It never mentions
  `committed_cost`.
* The only constraint on the field is `>= 0`
  (`core/serializers/decision_limits.py:41-43`) — V2-018's guard, which makes
  `0` legal.
* The engine charges what was declared:
  `rd_expense += dev.committed_cost` (`core/engine/costs.py:413-436`).
* The cost is computed **in the browser** and posted:
  `frontend/globalstrat-frontend/src/pages/RDPage.js:65-68, 94` (platform) and
  `:379-381, 404-409` (features).
* An authoritative server-side table already exists and is used only for
  *display*: `_build_cost_schedule` at `core/views/decisions.py:1136-1155`.

Read consequence: `POST` a platform development with `committed_cost: 0` and a
team gets a Gen-3 platform for nothing.

**A1b, same shape, separate path.** The level-based R&D branch
(`core/engine/rd_processing.py:192-215`) grants `target_level` outright — it
reads neither `amount` nor `calculated_cost`. Only the *legacy dollar-based*
fallback (`:217+`) converts money into level gain. So a payload of
`{target_level: 20, amount: 0, calculated_cost: 0}` reads as free maxed features.

This is the RW-50 invariant BECSR states explicitly: one calculator, or two
numbers drift. Here they have not drifted — they were never joined.

## A2. Platform development cost escapes both budget checks — **suspected P1** (READ)

`total_budget` is `rd_budget + marketing_budget + strategy_budget` checked
against cash (`core/views/decisions.py:548-552`), and `rd_total` sums
`rd_investments.amount` against `rd_budget` (`:555-561`). Neither includes
`platform_developments.committed_cost`. A platform is therefore outside the
cash constraint as well as outside the price constraint.

The same rule is written three times and the three do not agree: `:548`, `:888`
and `:1015` — and only `:1015` includes `research_budget`.

## A3. A platform can be ready in the round it was created — **suspected P1** (READ)

`_process_platform_development` creates the platform with
`development_rounds_remaining = gen.development_rounds` (`rd_processing.py:78`,
`:96-103`) and then, in the same function call for the same round, runs the
"advance in-development platforms" loop that decrements it (`:104-110`).

* `development_rounds: 0` (Gen 1, all three scenarios) → `-1` → `status='active'`
  in the creation round. Directly against the stated rule that no platform is
  ready in the round it is created.
* `development_rounds: 2` (Gen 2 and Gen 3) → decrements to 1 → ready one round
  later. The authored 2 behaves as 1: an off-by-one, and the scenario numbers
  mean something other than what they say.

Product creation is separately gated on an *active* platform at submit time
(`views/decisions.py:606-608`), which limits the blast radius but does not fix
the timing rule.

`method` (`in_house` vs `license`) changes neither the lead time nor the price
charged — `dev_rounds` comes from the generation regardless (`:78`). Licensing
is presently a label.

## A4. There is no price band — **confirmed absent** (READ)

`retail_price` is validated `> 0` and nothing else
(`core/serializers/decisions.py:301-304`; restated at
`core/views/decisions.py:637-639`). A team may move a product from $450 to
$5,000 or to $1 between consecutive rounds. There is no anchor, no band, no
warning, no auto-adjustment, and no rule for a blank price.

The requested rule (alert on violation, auto-adjust to the cap at the deadline,
blank → previous −30%) differs from BECSR's on purpose, and the difference is
worth stating once: BECSR *refuses* an out-of-band price because a student who
typed 140 and has 130 stored "has been lied to by a success response." The
requested behaviour keeps the student's number in the box, alerts them while the
round is open, and only substitutes at the deadline. That is defensible — but
only if the substitution is **visible and audited**: recorded as a system
adjustment with actor `system`, its own audit event, and shown on the results
screen. A silent clamp is the shape BECSR rejected and would also be
unanswerable under dispute 2 ("our decision was recorded differently from what
we entered"). GSP-CRV2-10 specifies it that way.

## A5. There is no operating budget and no overspend financing — **gap** (READ)

An operating budget exists only as a *coherence score component*
(`core/engine/coherence.py:459-515`): `base + 20% of prior net profit`, used to
grade "budget discipline". It constrains nothing. Overspend is instead handled
by refusal — the hard cash block at `views/decisions.py:548-552` — which is the
rule BECSR removed as wrong on its own terms (it blocks legitimate strategy
while the loan mechanic that exists to permit it sits unused).

There is no round budget allocated to a team, and no automatic conversion of
overspend into an amortised loan. `DecisionFinancing.new_debt` exists as a
manual, voluntary raise; it is not the mechanic described.

## A6. Cohort caps are defined but not enforced, and two of them disagree — **suspected P1** (READ)

* `CourseSection.max_teams=8`, `team_size_min=3`, `team_size_max=5`
  (`core/models/course.py:30-32`). Grepped across `views/` and `services/`:
  referenced only by a serializer field list (`core/serializers/course.py:59`).
  Nothing enforces them at enrolment or team assignment.
* A different, unrelated cap exists at game creation: `num_teams must be between
  2 and 16` (`core/views/scenario_views.py:237`).
* There are four starter profiles (`consumer_electronics_2026.yaml:5563`). At 16
  or 24 teams they repeat 4–6 times, so several teams begin *identical*.
* All four profiles set `home_market: NA`. Every team starts in the same market.

The saturation question — how many teams a market can carry before the game
stops teaching — is a calibration question and belongs to CRV2-11. The
enforcement question belongs here.

## A7. Product re-basing does not exist — **gap** (READ)

Grep for a platform switch / re-base path across `core/` returns nothing. A team
cannot move a product to a newer platform; there is no inventory write-off
because there is no switch. `DecisionProductRetire` retires a product outright.
BECSR's `platform_switch.py` is a working implementation of the requested rule,
including the clearance charge and the round-versioned history that keeps past
rounds reconstructable.

Note for the spec: BECSR's own diagnostic recorded the trap this feature opens
(defect B in `demand_diagnostic.md`) — the demand side resolved a team's
platforms *as of the round* while the supply side resolved them *as of now*, so
demand allocated to the historical platform reconciled to nothing, silently,
because the conservation check only summed rows that existed. Any globalstrat+
implementation must add the round dimension to both sides at once.

## A8. A finalised platform is fully modifiable — **rules decision required**

The requested rule is that a ready platform is frozen: no features added, no
modification at all, and a team that wants something different builds a new
platform and re-bases onto it. The engine currently does the opposite by
design: `_process_feature_investments` exists to raise feature levels on
*active* platforms, with ceilings per generation, licensing, time lags and
pending gains. That is a substantial, working mechanic and the R&D page is built
around it.

These cannot both stand. This is the one item in Part A that is a **product
decision, not a defect**, and GSP-CRV2-10 stops on it rather than guessing —
see the rulings requested at the end.

## A9. Events and challenges — thin, and one rule looks arbitrary (READ)

Events fire, shift segment preference ideals, and can carry authored responses
(`core/engine/events.py`). The failure-to-respond rule is a single hardcoded
line: `-1.0` to the `regulatory_govt` feature in the affected market
(`events.py:737-752`), regardless of the event, its severity, or whether
`regulatory_govt` matters to any segment in that market. There is no scored
response quality, no carry-over of an unresolved event, and no dependency
between events. BECSR's challenge engine scores responses and carries unresolved
challenges forward; globalstrat+ does not.

---

# Part B — Calibration (owner: GSP-CRV2-11)

## B1. Round-0 parity is already correct; the leaderboard then breaks it (READ)

Every team's round-0 performance index is `scenario.performance_index_base` —
one constant, all teams (`core/engine/bootstrap.py:300-307`), with round-0
coherence flat at 50.00. The differentiation half is well authored: four
archetypes with genuinely different platform strengths, prices, volumes, shares,
debt and revenue ($25M–$35M starting revenue on identical $50M cash).

**But** the round-0 leaderboard sorts `(-index, -revenue)`
(`bootstrap.py:369`), so with the index tied for everyone the ranking is
entirely a revenue ranking. On first login a team reads that as a starting
position it did not earn — and The Brand Builder is "1st" before anyone has
decided anything. Equal scores that produce an unequal ladder is worse than not
showing a ladder.

Also at `bootstrap.py:175`: `new_adopters = bass_p * pop * avg_share * 10` with
the comment `# Scale for meaningful numbers`. A magic multiplier in the numbers
students use to form their first read of the market.

## B2. Market size does not grow — **suspected P1, the largest calibration item** (READ)

`core/engine/events.py:388-392`:

```python
base_pop = float(segment.population_size)
growth = base_pop * state.effective_growth_rate
seg_state.effective_population = (base_pop + growth) * state.demand_multiplier
```

`base_pop` is the **static** authored population, re-read every round. Growth is
applied once, off the base, and never compounds. The authored APAC growth of 10%
per round means the market is 1.10× base in round 1 — and 1.10× base in round
10. It does not accumulate.

Meanwhile `N` accumulates correctly, so `M − N` shrinks monotonically. The
economy therefore **contracts** across the ten rounds rather than growing:
adoption pools peak early and decline. That is the opposite of the intended
"market value of the economy from round 1 to round 10" and it interacts with
everything else — pricing, budgets, capacity, whether late-game decisions still
matter.

## B3. AI competitors take share but never deplete the pool (READ)

AI competitors are added to `total_attractiveness` and so reduce every human
team's share (`bass_engine.py:151-153`), but no `RoundResultAdoption` row is
written for them and `_get_total_cumulative` (`:331`) sums only team rows. AI
adoption is therefore taken out of the current round's pool but never enters
cumulative `N`.

Whether that is right is a design question (BECSR deliberately made competitors
a *benchmark* that does not consume the pool — a different, coherent choice).
What is not defensible is the present hybrid: they consume, and their
consumption does not saturate. Pick one and state it.

## B4. Performance index composition (READ)

Weights are market .30 / capability .25 / financial .15 / stakeholder .15 /
resilience .15 (`core/engine/performance.py:20-26`). The financial component
scores revenue as `_ratio(revenue, max_revenue)` — cohort-relative, so it does
not peg the way BECSR's absolute band did. But market share and revenue are
close to the same quantity, and BECSR's ruling is explicit that scoring both
double-weights scale and crowds out profitability. Worth measuring here, not
assuming.

`_segment_score` awards a **default fit of 0.5** for segments in markets a team
has not entered (`performance.py:88-98`). A team gets middling stakeholder
credit for markets it is absent from. That needs a stated rationale or a change.

## B5. Preference weights, ideals and tolerances are unvalidated (READ)

`segment_preferences` in the YAML is a bare `[feature, ideal, weight,
tolerance]` list per segment per market. `_apply_pref_modifiers` clamps the
*event-modified* ideal into the feature's range
(`preference_engine.py:196-200`) — but nothing validates the **authored** ideal
against the feature's own min/max, nothing checks that a segment's weights are
non-degenerate, and nothing catches a preference pointing at a feature whose
ceiling is 0 on every platform generation available in that round.

Both of those are exactly the bugs BECSR shipped fixes for last month: *"Clamp
stakeholder ideals that sat outside their feature's range"* (`32ed072`) and
*"Exclude dead preference weight from alignment"* (`bfd45c7`). An ideal outside
the range is unreachable, so its weight is spent on a term no team can move; a
weight on a zero-ceiling feature is the same defect with a different cause. Note
that `ai_features`, `connectivity` and `iot_integration` have ceiling `0` on
Gen 1 while Value Seekers in NA carry authored weights on all three
(`consumer_electronics_2026.yaml:1511+`). That is dead weight for every team
until Gen 2 unlocks in round 2 — plausibly intentional as a pull toward
upgrading, but it has never been measured.

---

# Part C — Player-facing language (owner: GSP-CRV2-12)

Refusals a student can hit today, verbatim from the source:

* `retail_price must be > 0.`
* `promotion_budget must be >= 0.` · `rd_budget must be >= 0.` (and ~19 more of
  this shape from `decision_limits.non_negative_message`)
* `target_market_ids must be a non-empty list.`
* `target_market_ids must contain only integers.`
* `Product "X" targets market 7 where team has no active presence.` — a raw row id
* `Platform has no team_id.`
* `No SimulationState found for this instance.`
* `instance_id is required.` · `game_id and team_id required`
* `Validation failed.` — on the decision submit path, with no indication of what

These name database columns, model classes and primary keys. They are the
platform's internal vocabulary offered to an executive-education audience, and
under competition conditions they will be screenshotted.

**Second finding, and the sharper one for this audience: backend messages are
not localised at all.** `core/utils/localization.py` resolves `*_zh` fields on
*scenario content* only. Every validation error, instructor alert and system
message is English-only, so a zh-CN team plays a Chinese UI and receives English
refusals at the moment something goes wrong. The frontend catalogue is in good
shape by contrast — `locales/en.json` and `locales/zh-CN.json` are within two
lines of each other — which makes the backend gap more visible, not less.

---

# Part D — Bug sweep (owner: GSP-CRV2-13)

Incidental defects noticed while reading for the items above. None was searched
for; a real sweep will find more.

| # | Defect | Where |
|---|---|---|
| D1 | `end_of_round` product retirement sets `status='retired'` but, unlike the `immediate` branch, never deactivates `TeamProductMarket` rows | `core/engine/rd_processing.py:334-338` |
| D2 | The budget-vs-cash rule is written three times and `:1015` includes `research_budget` while `:548` and `:888` do not | `core/views/decisions.py` |
| D3 | `_process_platform_development` skips creation when *any* non-retired platform of that generation exists, so a team can never rebuild after retiring one | `rd_processing.py:70-76` + `views/decisions.py:596-601` |
| D4 | `except Exception: pass` swallows the org-structure development-speed modifier entirely — the modifier can silently never apply | `rd_processing.py:83-95` |
| D5 | `for market_id, seg_state in context.segments.items()` — `context.segments` is keyed by **segment** id (`engine/utils.py:305`). Cosmetic today; the name invites a real bug | `preference_engine.py:60` |
| D6 | Round-0 adoption uses an unexplained `* 10` scale factor | `bootstrap.py:175` |

---

# Rulings requested

These change what the specs say. GSP-CRV2-10 Stage 1 can run without them;
nothing after Stage 1 can.

1. **A8 — is a ready platform frozen?** Freezing it retires the entire
   feature-upgrade mechanic (R&D investment on active platforms, per-generation
   ceilings, licensing, time lags, pending gains) and makes re-basing the only
   route to a better product. That is a coherent game and it is the one
   described. It is also the largest single change in this document and it
   invalidates part of GSP-CRV2-06's accepted tournament. Confirm, or scope it
   to "no new features added after ready, existing levels may still be raised".
2. **A4 — auto-adjust at the deadline.** Confirmed as specified (alert while
   open, substitute at close, blank → previous −30%), on the condition that the
   substitution is written as an audited system adjustment the team can see.
   Say if the audit requirement is unwanted; it is what keeps dispute 2
   answerable.
3. **B3 — do AI competitors consume the market?** Consume-and-saturate, or
   benchmark-only. Either is defensible; the current hybrid is not.
4. **A6/B-sizing — the competition field.** CRV2-07 certified 24 teams × 4
   members. Confirm 24 as the cap to enforce, or name the number, so the
   saturation study has a target to test rather than a range to explore.
