# GSP-CRV2-11 Stage 2 — every firm in a heat starts from a distinct position

**Ruling implemented:** **R28**, competition owner, 2026-09-12
(`OWNER_RULINGS_2026-09-12.md`).
**Binding and not relaxed:** **R22** — round-zero equality of performance index
and rank is the only starter-parity requirement. Equal score, unequal position.
**Branch:** `crv2-11-distinct-starter-profiles`, cut from
`crv2-release-integration` at `46b4bbe`, in an isolated worktree.
**Observes:** `handoffs/EXECUTION_PROTOCOL.md`, `specs/STANDING-DISCIPLINE.md`.

**No gate is claimed closed.** Everything below is development-grade
measurement under the protocol's Phase 2/3 budget, offered for audit.

| commit | content |
|---|---|
| `d475b66` | the inventory, committed **before** any authoring |
| `fb28191` | four new profiles per scenario, the round-zero tests, evidence tooling |
| `9e3593d` | persist per-round team detail in the balance report |

---

## Part A — the inventory, and the defect

Full inventory:
`evidence/calibration/starter-profiles/PROFILE_ASSIGNMENT_INVENTORY.md`.

**How a profile is defined.** Each scenario carries a top-level
`starter_profiles:` list. `load_scenario.py:1014-1057` maps one entry onto
three models: `FirmStarterProfile` (home market, cash, debt, revenue),
`FirmStarterPlatformConfig` (one row per platform label × feature, all attached
to generation 1) and `FirmStarterProduct` (positioning, base price, market,
unit volume, market share, platform label).

**How a profile is assigned.** Two registered entry points, both selecting with
the same expression:

| entry point | line | expression |
|---|---:|---|
| `management/commands/initialize_game.py` (CLI) | 112 | `profiles[i % len(profiles)]` |
| `views/scenario_views.py` (instructor API) | 325 | `profiles[i % len(profiles)]` |

`profiles` is built by `FirmStarterProfile.objects.filter(scenario=scenario)`
with **no `.order_by()`**, so the team-index → profile mapping rests on
unordered database return order.

**The repeat behaviour, precisely.** Nothing checks whether teams outnumber
profiles; no warning, log line or error is produced when the list wraps. Each
scenario authored **four** profiles against the R12 cap of **eight firms**, so
every heat produced four duplicate pairs — teams 5–8 pointing at the *same*
`FirmStarterProfile` rows as teams 1–4. A pair therefore shared home market,
cash, debt, revenue, every platform feature level, both product names,
positionings, prices, volumes and shares, and consequently identical round-0
revenue, COGS, net income, share and segment adoption. **The only differences
were the team's display name — drawn by an unseeded `random.shuffle` — and its
primary key.** Two teams did not merely begin similarly; they began identically
and differed only in what they were called.

Round-zero parity was never what was broken: `bootstrap.py:449` writes the
scenario base index for every team and `:531` gives every team rank 1. R22
requires equal score and *unequal position*; a duplicate pair had equal score
and **equal** position.

---

## Part B — what was authored

Four new profiles per scenario, in English and Chinese, taking each to eight.

**The rule that governed the numbers, and a discarded first draft.** Each new
profile carries the **same authored platform capability budget** as the shipped
ones — consumer electronics alpha 30 (shipped 29–30), clean energy 17 (15–18),
media 16–17 (16–17). Profiles differ in the **distribution** of capability,
never in the amount. This mattered: a first draft ignored it and gave the new
profiles 3–6 more authored levels each, which lifted their preference fit above
every shipped profile in nearly every segment — an unearned edge baked straight
into the data. That draft was measured, rejected and rewritten. No new profile
leads on a feature a shipped profile already leads on, with one deliberate
exception noted below. Every authored level is at or below its Gen-1 ceiling.

### Consumer Electronics 2026 (all eight on NA — see Part E)

* **The Volume Champion** — a contract manufacturer gone own-brand: competent
  everywhere and exceptional nowhere, winning on shelf space and price with the
  largest unit volume in the field and no premium customer to fall back on.
* **The Turnaround** — a famous name that lost a decade, still holding the best
  design-and-software heritage in the field and the heaviest debt, which must
  fund a comeback while servicing the last failed strategy.
* **The Heritage Manufacturer** — builds a few thousand devices a year and
  expects them to last ten, sells at the market's highest prices to a small
  loyal clientele, carries no debt at all, and is the smallest firm by units and
  revenue.
* **The Ecosystem Player** — a software and services company that happens to
  ship hardware, whose richest-in-market app ecosystem retains customers its
  ordinary devices could not, and which cannot charge a hardware premium for
  software strength.

**The deliberate exception.** The Volume Champion leads Value Seekers (round-0
fit 0.3890). Value Seekers was the one NA segment **no shipped profile
claimed** — the shipped maximum was 0.3512, held by a profile whose identity is
sustainability. It is claimed at a *lower* peak than the existing Enterprise
specialist (Workhorse, 0.4243) and Sustainability specialist (Green Pioneer,
0.4040). Filling an orphan segment at a lower peak than existing specialists
improves the field rather than tilting it.

### Clean Energy Technology 2026

* **The Fast-Charge Specialist** (na) — chemistry and thermal engineers who
  solved charging time and nothing else: the fastest-charging cell in the market
  and, deliberately, the worst cycle life in the field.
* **The Cost Leader** (ea) — builds the cheapest cell anyone will buy, in
  enormous quantities, on mature chemistry nobody else bothers with; ships more
  cells than any rival and earns the least on each.
* **The Industrial Integrator** (eu) — sells installed and maintained storage
  systems rather than cells; balanced, best-in-class at nothing, and the only
  firm the utilities will let on site.
* **The Residential Brand** (na) — the only firm selling to households rather
  than engineers, running a consumer retail brand on margins set by a commodity
  cell market.

### Media & Entertainment 2026

* **The Compliance Broadcaster** (na) — a public-service broadcaster's
  successor with the safest catalogue in the market: trusted by institutions and
  invisible to consumers.
* **The Rights Holder** (eu) — owns rather than makes; the deepest rights
  library in the market on a merely adequate platform, carrying the heaviest
  debt because those rights are leased and renew.
* **The Arthouse Curator** (eu) — a small European house with impeccable taste
  and beautiful subtitling: the smallest firm by subscribers and revenue, almost
  debt-free, beloved and sub-scale.
* **The Value Bundler** (ea) — sells access to everyone else's catalogue at a
  price nobody can match; the cheapest subscription and the largest subscriber
  count, owning nothing its subscribers cannot get elsewhere.

### A constraint worth recording

In clean energy and media the Gen-1 reachable feature space is small — six
features with ceilings of 4–7 — and the four shipped profiles already occupy
density, endurance, safety and recyclability (clean energy) and quality,
technology, localisation and engagement (media). Eight genuinely distinct
*platform signatures* are not available there. Distinctness for the new four
therefore leans on portfolio, price point, home market, balance sheet and
customer type, with only moderate feature differences. This is stated rather
than hidden: it is a property of the authored ceilings, not of the profiles.

---

## Part C — the parity proof

Extended `core/tests/test_round_zero_adoption.py` rather than writing a parallel
set, as instructed. New class `EightFirmDistinctStarterTests`, two tests, run
against **all three shipped scenarios** at **8 teams** through the real
`load_scenario` and `initialize_game`:

1. **R28 distinctness** — the scenario authors at least 8 profiles; all 8 teams
   hold distinct `FirmStarterProfile` rows; and all 8 hold distinct *position
   signatures*. The signature is built from observable starting state — home
   market code, cash, debt, starting revenue, every platform feature level, and
   every product's name, positioning, price, volume and share — deliberately
   **not** from the profile's primary key, because two teams pointed at
   different rows that happened to be authored identically would still be the
   defect.
2. **R22 parity** — every round-0 `RoundResultPerformanceIndex.index_value`
   equals `scenario.performance_index_base`, and every round-0
   `LeaderboardEntry.rank` is 1. Asserted as set equality, so a single
   divergent team fails it.
3. **R11 reconciliation, for every new profile** — round-0 adopters equal
   round-0 units sold, which equal the authored `unit_volume` sum, to the cent,
   for all 8 teams in all 3 scenarios.

A second test pins that the field differs on the axes R28 names — price point
and debt unique per firm, at least three portfolio shapes — rather than only
somewhere.

**One assertion was wrong and was corrected, not the data.** The first version
also demanded a unique total starting volume and share per firm. That failed
`6 != 8`, and the collisions are in the **shipped** profiles: The Innovator and
The Workhorse both open on 65,000 units, The Brand Builder and The Green
Pioneer both on 45,000. R28 requires that no two firms begin from the same
*position* — the composite — not that every axis is injective. The assertion was
relaxed to the measured spread with the shipped collisions named in a comment.

```
backend/scripts/test-postgres core.tests.test_round_zero_adoption \
    core.tests.test_leaderboard_tiebreak core.tests.test_calibration
Ran 24 tests in 13.749s — OK
```

`test_calibration.ScenarioPreferenceValidationTests` is included deliberately:
it runs `validate_scenario_yaml` over all three shipped scenarios, so the
scenario contract is proved against the authored data (Part F).

---

## Part D — balance, and what the measurement actually found

**Method.** One fixed-policy replay, **8 teams, 10 rounds**, Consumer
Electronics 2026, every team playing the identical documented competent
baseline policy with 10% adaptive production, all teams on NA, name seed
**20260912** pinned. Because every team plays the same policy, a difference in
outcome is attributable to the authored starting position and to nothing else.
Run from the frozen commit `fb28191`; re-run at `9e3593d` reproduced every
figure **to the cent**.

### Per-profile round-10 outcome

| rank | starter profile | units | revenue | net income | index |
|---:|---|---:|---:|---:|---:|
| 1 | The Heritage Manufacturer *(new)* | 47,174 | 30,945,760 | 15,026,883 | **98.12** |
| 2 | The Brand Builder | 64,234 | 27,923,168 | 11,884,807 | 92.28 |
| 3 | The Innovator | 68,301 | 18,306,640 | 4,378,214 | 77.64 |
| 4 | The Volume Champion *(new)* | 81,312 | 21,563,680 | 6,184,780 | 75.01 |
| 5 | The Ecosystem Player *(new)* | 46,858 | 19,680,640 | 6,236,212 | 59.49 |
| 6 | The Workhorse | 59,900 | 15,600,592 | 2,861,237 | 57.45 |
| 7 | The Turnaround *(new)* | 54,453 | 14,181,936 | 1,543,652 | 56.28 |
| 8 | The Green Pioneer | 49,501 | 12,892,200 | 1,204,036 | 55.97 |

**Index spread 42.15 points.** A profile I authored finishes first.

### The spread is mostly a defect, not a starting advantage

Two hypotheses were tested and **both were falsified** before reporting.

*Positioning mix does not explain it.* Correlation between the positioning
reference-price blend and the final index is only **0.699**, and the five
profiles sharing the **identical** `budget+mainstream` mix finish 77.64, 75.01,
57.45, 56.28 and 55.97 — a 21-point spread inside one mix.

*What actually happens is a cliff.* Three profiles climb monotonically and never
fall: Heritage Manufacturer, Brand Builder, Innovator. **They finish 1st, 2nd
and 3rd.** Every other profile takes a sudden single-round collapse:

| profile | round | index before → after | delta | mechanism |
|---|---:|---|---:|---|
| Green Pioneer | 8 | 70.43 → 52.62 | **−17.81** | ranking guard (min active 52.63 − 0.01) |
| Workhorse | 6 | 66.17 → 48.86 | **−17.31** | ranking guard (min active 48.87 − 0.01) |
| Turnaround | 7 | 64.52 → 50.92 | **−13.60** | ranking guard (min active 50.93 − 0.01) |
| Ecosystem Player | 2 | 58.29 → 52.91 | −5.38 | ranking guard (min active 52.92 − 0.01) |
| Volume Champion | 2 | 57.15 → 52.15 | −5.00 | composite cap 0.25, exactly `(0.25−0.5)×20` |
| Ecosystem Player | 4 | 56.33 → 51.33 | −5.00 | composite cap |
| Ecosystem Player | 5 | 51.33 → 46.33 | −5.00 | composite cap |

Both mechanisms are the **commercial-inactivity** controls in
`performance.py` — the composite cap (`COMMERCIAL_INACTIVITY_COMPOSITE_CAP`,
0.25) and `_enforce_inactive_revenue_invariant`, which forces an inactive firm's
index to `min(active_indexes) − 0.01`. A firm is classified inactive when its
revenue falls below `material_revenue_floor` — 1% of the largest revenue that
round.

Note the arithmetic that forced this diagnosis: every PI component is
`_clamp01`-ed and `PI_WEIGHTS` sum to 1.00, so the composite is bounded to
[0,1] and `index_change = (composite − 0.5) × 20` cannot exceed ±10. **A −17.31
move is impossible from scoring alone**, which is what identified the ranking
guard as the real mechanism.

### Why revenue collapses — and it is not cash

At each collapse the team shows `units_produced = 0, units_sold = 0,
revenue = 0`, net income ≈ −8,000,000 (fixed costs and declared budgets against
no revenue), **while closing cash stays between 27,000,000 and 50,000,000.** No
team ran out of money, so this is not R14's spend-refusal. Production is drawn
solely from that round's `DecisionMarketing.production_volume` rows
(`bass_engine._init_production_remaining`), and the round after a collapse
resumes at the baseline default of 45,000 units rather than at 1.1× prior sales
— consistent with no `RoundResultProductMarket` row having existed for the lost
round. The team simply had no marketing rows that round.

### Attribution — this pre-dates the new profiles

The pre-existing 4-team replay `stage2_archetype_parity_replay.json`, run
against the **shipped profiles only, before this work**, contains the same
zero-production rounds with **byte-identical figures**: The Green Pioneer at
round 8 (net −8,250,000) and The Workhorse at round 6 (net −7,890,000). The
defect is not caused by the new profiles; an 8-firm field exposes more instances
of it.

### The verdict, plainly

**No profile is shown to carry an advantage that play cannot overcome, because
this measurement cannot answer that question while the zero-production defect is
live.** Finishing order in this run is determined by whether a firm lost a round
at all, and among those that did, by how late — an early loss (Volume Champion
r2, Ecosystem Player r2/r4/r5) is recovered from, a late one (Green Pioneer r8)
is not. That is a defect ordering the field, not a starting position.

What survives the caveat, and should be re-measured once the defect is fixed:
**The Heritage Manufacturer realises $656 per unit against $260 for the
`budget+mainstream` group, and it never lost a round.** It is the only
`ultra_premium` profile in any shipped scenario. I consider it the most likely
genuine outlier in the field and I am flagging it as such rather than waiting
for a team playing for a prize to find it. The Brand Builder was already the
strongest shipped profile before this work (98.24 against 81–89 in the prior
4-team run), by the same mechanism.

For scale, the single-lever sensitivity already measured at 8 teams:
`production_plus_25` moves the index **+12.40**, `price_plus_10` −1.76,
`sales_team_plus_50` −0.78, `promotion_plus_50` +0.13. One decision lever is
worth around 12 points against a 42-point spread, so the spread as measured is
**not** recoverable by a single competent decision — but most of it is the
defect, not the field.

---

## Part E — `home_market`: reported, not decided

**Current state, stated precisely.** The handoff's premise — "all existing
profiles start in NA" — is true of **consumer electronics only**. Clean energy
already spreads na/ea/eu/eu and media na/na/eu/ea. I therefore kept all eight
consumer-electronics profiles on NA (changing it is a calibration decision, not
a builder's) and placed the new clean-energy and media profiles only in markets
those scenarios already used. After this work: consumer electronics NA×8; clean
energy na×3, ea×2, eu×3; media na×3, eu×3, ea×2.

**What spreading would do, with the measurement I have.** From
`STAGE2_PARITY_MEASUREMENTS.md`, the same field assigned `NA, APAC, EU, LATAM`
instead of all-NA produced round 1–3 index spreads of **3.77, 8.52, 10.61**
against **1.02, 1.85, 2.63** for all-NA — roughly a fourfold widening, before
anyone has made a distinguishing decision. The mechanism is that home market is
not a neutral label:

* `base_manufacturing_cost` runs NA 1.20, APAC 0.65, EU 1.40, AFR 0.55, LATAM
  0.80 — a **2.5× COGS spread** on identical units;
* `tax_rate` runs 0.21 to 0.34;
* `origin_trust` multiplies fit, 1.00 at home against 0.72–0.95 abroad;
* segment populations differ per market, so the addressable pool differs.

Round-zero parity is unaffected either way — the index is the authored base and
rank is joint-first regardless — but from round one a spread field is materially
less equal than an all-NA field, and the inequality is authored rather than
earned.

**The question for the owner.** Should consumer electronics spread its eight
home markets, accepting a four-fold wider early-round index spread and a 2.5×
COGS asymmetry that no team chose, in exchange for the stated design goal of
teams targeting different regions? Or should a heat stay in one market so the
contest is decided by decisions rather than by which market a team was dealt?
A third option exists and is cheap: spread home markets but equalise the cost
and trust terms across them, so region changes *who you sell to* without
changing *what it costs you*. I have not chosen, and no scenario data was
changed either way.

---

## Part F — the scenario contract

`validate_scenario_yaml` (`load_scenario.py:146-243`) passes with **zero
errors** on all three scenarios after the authoring, proved by
`ScenarioPreferenceValidationTests.test_all_shipped_scenarios_pass_the_preference_contract`
in the 24-test run. The authored preference/feature validation reported nothing
against the new profiles, so no validator was touched — as instructed, the
data would have been fixed, not the validator.

An additional offline structural check was run over the authored data: 8
profiles per scenario, no duplicate names, both language fields present, ≤5
features per platform label, every feature code real, **every starting level at
or below its Gen-1 ceiling**, valid market codes, legal positionings, products
in the profile's own home market, and 8/8 distinct position signatures. Result:
**PASS** for all three.

---

## Commands, counts and durations

Every test run used `backend/scripts/test-postgres` and every replay
`backend/scripts/run-calibration-postgres`; each starts its own disposable
PostgreSQL 16 container with a generated credential and drops it on exit. All
runs were serialised under `flock -w 1800
/tmp/globalstrat-backend-test.lock`. The production database at 192.168.50.38
was never contacted and no systemd environment file was read.

| command | result | duration |
|---|---|---|
| offline structural + distinctness validation, 3 scenarios | **PASS**, 8/8 distinct signatures each | <1s |
| round-0 fit pre-screen, shipped vs candidate (2 rounds) | rejected the first draft, retuned | <1s |
| `test-postgres` × 3 modules (first) | Ran 24 — **FAILED** (1, my assertion) | 13.811s |
| `test-postgres` × 3 modules (after correction) | **Ran 24 — OK** | 13.749s |
| `run-calibration-postgres --field-sizes 8 --rounds 10 --name-seed 20260912 --baseline-only` | 8 profiles, 8 teams, reconciled | 1m26.3s |
| same, re-run at `9e3593d` to capture per-round detail | **identical to the cent** | 1m50.7s |

Two replays, not one, because the first report persisted only round-10 rows and
could not explain a 17-point single-round fall. No full backend suite, no load
run, no concurrency matrix and no determinism matrix — those belong to
GSP-CRV2-09. The seven pre-existing full-suite failures (V2-071 / V2-074) were
not touched and are not in any module run here.

**Commit policy.** All commits used `--no-verify`. The pre-commit hook
(`.husky/pre-commit`) runs `checks/bin/run-checks`, which exits 2 on an
aide-checks **revision mismatch** — runner built from `46b4bbe`, repo vendors
`e710f26` — on the stated grounds that "a stale runner reports PASS for checks
it does not carry". The hook's own header sanctions the bypass: *"Bypassable
with --no-verify; the deploy gate is the layer that is not."*

---

## Findings — handed over, register not edited

1. **A heat of 8 firms drew on 4 profiles, so two teams began identical.**
   P1, **fixed here** for all three scenarios. Both game-creation paths use
   `profiles[i % len(profiles)]` with no warning when the list wraps. A
   duplicate pair shared every authored value and differed only in team name and
   primary key.

2. **A team can lose an entire round to zero production, with cash in hand.**
   **P0 candidate, not mine to repair, and the most important thing in this
   report.** `units_produced = units_sold = revenue = 0` for exactly one round,
   net income ≈ −8,000,000, closing cash 27–50M. The commercial-inactivity
   controls then fire: the composite cap costs exactly 5.00 index points, and
   `_enforce_inactive_revenue_invariant` forces the firm to
   `min(active_indexes) − 0.01`, costing up to **17.81 points in one round**.
   Reproduces byte-identically in the pre-existing 4-team shipped-profile replay
   (Green Pioneer r8, Workhorse r6), so it pre-dates this work. In this 8-firm
   run it determined the finishing order. In a competition with a prize, a team
   losing a round and 17 index points with a full bank account is not
   defensible. Owner: the engine/decision-path handoff.

3. **Starter-profile assignment reads an unordered queryset.**
   P2. `FirmStarterProfile.objects.filter(scenario=scenario)` has no
   `.order_by()`, so which team gets which profile rests on database return
   order. Inside the CRV2-01 determinism boundary in spirit.

4. **The two game-creation paths build different starting states from the same
   data.** P2. `initialize_game` reads only the `alpha` platform config and
   creates one platform, attaching both products to it; `scenario_views` creates
   one platform per label and honours `FirmStarterProduct.platform_label`. Every
   shipped profile authors a `beta` block, so on the CLI path authored data is
   read and never used.

5. **`verify_scenario_schema` expects a unique key the model no longer has.**
   P3. It declares `firm_starter_platform_config` unique on
   `(firm_starter_profile_id, feature_id)`; the model declares
   `(firm_starter_profile, platform_label, feature)`. Predates the dual-platform
   format.

6. **Positioning reference prices are shared across all three scenarios and fit
   only one of them.** P2. All three author `reference_price_*` of
   250/420/700/1000, while clean energy's authored starter prices run
   $900–$12,000 and media's $55–$340. Price competitiveness is scored against
   those references, so in clean energy a premium product clamps to zero
   competitiveness and in media effectively everything clamps to maximum. Not
   touched here; it is Stage 3/4 territory and changing it would invalidate
   existing evidence.

7. **Two shipped profiles spend their signature strength on a gated segment.**
   P3. The Innovator's `processing_power` and The Disruptor's
   `audience_engagement` are the heaviest-weighted features of Tech Enthusiasts
   and Gen Z Digital Natives respectively, both of which carry
   `min_generation_required: 2`. At Gen 1 those signatures earn nothing, which
   is why both profiles are easy for a new profile to dominate on fit.

---

## EXECUTION_PROTOCOL preflight answers

* **Did inventory start from registered routes/models, not only code using the
  new abstraction?** Yes. It was built from the scenario YAML sections, the
  Django model registry (`FirmStarterProfile`, `FirmStarterPlatformConfig`,
  `FirmStarterProduct`) and both registered game-creation entry points, and it
  was committed before any authoring.
* **Is there an active legacy or alternate entry point?** Yes, and it is
  recorded: `initialize_game.py:112` and `scenario_views.py:325` both assign
  profiles, and they build *different* starting states from the same data
  (finding 4). Both are covered by the authoring, since both now have 8
  profiles to draw on; the divergence itself is reported, not repaired.
* **Does a failure/refusal audit survive rollback?** Not applicable — this
  change adds scenario data and tests and performs no mutation, refusal or
  audited action.
* **Is each correlation ID generated once?** Not applicable — no request, audit
  or log identifier is created on this path.
* **Is background/external work delayed until the outer transaction commits?**
  Not applicable — no background or external work.
* **Do claimed environment values describe the executing process?** Yes. Every
  figure came from a disposable PostgreSQL 16 container created by the named
  script in this worktree and dropped on exit; the replay creates and
  force-drops its own uniquely named database.
* **Does provenance identify runtime bytes, including required untracked
  files?** Yes, with one exactness worth stating rather than glossing. The
  balance report records `code_revision` (`9e3593d`), `runtime_replay_sha256`
  and `scenario_sha256`. `stage1_runtime_replay.py` — the script the hash
  covers, and the one that actually resolves the rounds — was **not** modified
  after the measurement, so that hash describes the code that ran. No
  measurement was taken while an evidence script was being edited, precisely
  because the report stamps its own hashes.
  **However:** the `--home-markets` passthrough was added to
  `fixed_policy_measurements.py` *after* the final replay, so the committed
  `r28_eight_profile_balance.json` was produced by an earlier revision of that
  runner than the one now on the branch. The option defaults to `NA`, which is
  exactly what the measurement used, so no reported figure is affected — but
  **the option is unexercised by any evidence here** and nothing in this report
  rests on it. It exists so the home-market question in Part E can be measured
  without further tooling work. Re-running the command in the table against the
  current branch would reproduce the same numbers and stamp the current
  revision.
* **Do README commands run exactly as written against stored artifacts?** Yes;
  the commands in the table above are the ones that were run, verbatim.
* **Do P0/P1/P2 labels match their definitions?** Finding 2 is offered as a
  **P0 candidate** because it can cost a team 17 index points in a live
  competition round with no warning and no team error; the severity call belongs
  to the rules owner, not to me. Finding 1 is P1 and is fixed. The rest are P2/P3
  and change no competitive outcome.
* **Does each negative test prove mutation/engine execution did not occur?**
  The distinctness and parity assertions are set-equality checks over persisted
  round-0 rows, so a single divergent team fails them; the pre-existing
  `test_starter_units_with_no_reachable_customer_segment_raises` continues to
  prove the bootstrap aborts before writing adoption rows.

---

## Files changed

| file | change |
|---|---|
| `backend/scenarios/consumer_electronics_2026.yaml` | **data** — 4 new profiles (4 → 8) |
| `backend/scenarios/clean_energy_tech_2026.yaml` | **data** — 4 new profiles (4 → 8) |
| `backend/scenarios/media_entertainment_2026.yaml` | **data** — 4 new profiles (4 → 8) |
| `backend/core/tests/test_round_zero_adoption.py` | new `EightFirmDistinctStarterTests`, 2 tests |
| `evidence/calibration/stage1_runtime_replay.py` | `--name-seed` (default off, behaviour unchanged) |
| `evidence/calibration/fixed_policy_measurements.py` | `--name-seed`, `--baseline-only`, `--home-markets`, per-profile final table and per-round detail |
| `evidence/calibration/starter-profiles/PROFILE_ASSIGNMENT_INVENTORY.md` | new — the inventory |
| `evidence/calibration/starter-profiles/r28_eight_profile_balance.json` | new — the 8-team measurement |
| `completion/GSP-CRV2-11-distinct-starter-profiles.md` | this report |

**No engine or scoring code changed.** The only non-scenario, non-test changes
are to evidence tooling under `handoff_readiness_v2/evidence/calibration/`, and
`--name-seed` defaults to off so existing behaviour is unchanged.
`V2_FINDINGS_REGISTER.md` was not edited; the findings above are handed over.

I did not touch `core/views/decisions.py`, the serializers, `core/views/`,
`core/engine/`, `core/services/`, or any existing test module other than
appending to `test_round_zero_adoption.py` — all named as other builders'
territory or outside this task's remit.
