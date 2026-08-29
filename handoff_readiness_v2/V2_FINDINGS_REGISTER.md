# GlobalStrat+ competition readiness v2 — findings register

Prepared 2026-08-28 against `competition-rc-2026.08.27.3` / `7452ee7`.
Findings were recorded before repair. P0 blocks; P1 degrades; P2 cosmetic.

| ID | Area | Sev | Description | Reproduction / evidence | Initial status |
|---|---|---:|---|---|---|
| V2-001 | Determinism boundary | P0 | `output_sha256` covered only financials, performance-index rows, and leaderboard rows. It omitted coherence, product/market outcomes, adoption, resilience, share price history, and mutable `Team` state carried into the next round. | Compare original `complete_manifest()` at `7452ee7` with `_run_phase_1()`. | **Closed** — see closure entry below |
| V2-002 | Reconstruction / disputes | P1 | The input manifest stores decision-event IDs and payload hashes, but not the decision payload, scenario parameters, market state, starting team state, or engine configuration. The backup can reconstruct these, but the manifest alone cannot prove the calculation or explain an input. | Inspect `prepare_manifest()`: its fields are game/round IDs, six audit metadata fields, active team IDs, and scenario ID. | **Closed** — see closure entry below |
| V2-003 | Dispute tooling | P1 | Instructor decision drill-down showed the stored snapshot and lock actor/time, but not each accepted save's actor, server timestamp, request ID, endpoint, payload, and hash. | V2 API/UI now exposes ordered audit evidence in the historical decisions modal. | Repaired |
| V2-004 | Concurrent operator actions | P0 | Reopen, deadline change, and advance did not share the row-lock transaction used by close/process. Tracing the routes found the problem was wider: several endpoints read the round's status outside any lock and met the conflict inside the engine, where it surfaced as a 500 or a second resolution. | Compare the pre-repair `RoundProcessView` (unlocked status read, blanket `except Exception` → 500) and `InstructorExtendDeadlineView` (no lock, no transaction, silently reopened a closed round). | **Closed** — see closure entry below |
| V2-005 | Failure visibility | P1 | A Phase-1 exception rolled back `PROCESSING`; `_mark_failed()` then required the rolled-back value, leaving no FAILED indicator. | Injected disk-full exception now leaves `Round.processing_status=FAILED`; focused and full suites pass. | Repaired |
| V2-006 | Backend restart / narrative | P1 | Phase 2 runs only in a daemon thread. A worker restart can silently abandon it; no durable queued job or startup retry exists, and an abrupt process death cannot populate `narrative_error`. Numeric results remain valid, but operator visibility/recovery is incomplete. | Process a round, terminate the worker after Phase 2 dispatch and before completion, restart, then inspect `narrative_generated`, `narrative_error`, and logs. | **Closed** — see closure entry below |
| V2-007 | Audit integrity | P1 | Audit models reject a second `.save()`, but queryset `.update()`/`.delete()` and direct SQL can alter them. The database does not enforce append-only history, so stored data alone cannot prove absence of operator/database tampering. | In an isolated database, call `DecisionAuditEvent.objects.filter(pk=...).update(action='tampered')`; it bypasses model `save()`. | **Closed** in GSP-CRV2-04 — see closure entry below |
| V2-008 | Dry-run failure path | P2 | The `process_round(dry_run=True)` exception handler referenced undefined `sid`, masking the original failure. | Removed invalid rollback; outer atomic block owns rollback. | Repaired |
| V2-009 | Frontend verification environment | P1 | Lockfile selects `react-router-dom` 7.1.1 (Node >=20), but the VM runs Node 18.20.8. Production build completes, while Jest cannot resolve the router and one suite cannot start. | `npm install` reports EBADENGINE; `CI=true npm test -- --watchAll=false` has 1 pass / 1 load failure. | **Closed** in GSP-CRV2-05 — see closure entry below. The stated cause was wrong; the repair is described there. |

## V2-010 and V2-011 — closed at `8ddd983` (option A adopted)

**V2-010.** `sc_engine` and `compliance_engine` now use `_cohort_key(game)` =
`game.section_id or game.id`, the rule `events.py` already applied. Two sections
of one class previously met the same events and different supply-chain and
compliance disruptions.

**V2-011.** Each probabilistic operation draws from its own stream, keyed by
cohort, round, subsystem and the identity of the thing being decided —
`sc_event_trigger:{template}` and
`compliance_enforcement:{regime_id}:{team}:{market_code}`. A single sequential
RNG previously meant draw *n* belonged to whichever combination reached it
*n*-th, so one team's presence moved another team's outcome.

Team is keyed on `id` rather than `name`, deliberately: instructors can rename a
team mid-game, and a rename must not resegment that team's stream — so the
manifest's `(game_id, name)` natural key is the wrong identity here.
`regime.regime_id` and `market.code` are scenario codes and are used directly.
`events.py`'s existing `operation_id` strings are untouched, because changing
them would resegment a stream that prior rounds were replayed against.

12 focused tests. The six required properties are asserted directly; because the
repaired engines no longer contain a shared sequential RNG, three further tests
reproduce that pattern in miniature and demonstrate the order-dependence and
cross-team coupling the keyed scheme does not have.

**RNG-impact gate.** The Stage 2 screen was recorded at `e3654ec`, before this
change. Rather than rerun it because source moved, the gate resolved the same
baseline and six representative probes under the repaired RNG: **baseline
unchanged, 6/6 probe deltas unchanged**, so the 107-probe screen still describes
the system it claims to and is retained. Narrow claim, stated as such — this is
evidence that *this fixture's* outputs did not move, not that the repair is
inconsequential in general. The fixture is a round-1 game where the
supply-chain and compliance subsystems have little to fire.

## New observation raised by GSP-CRV2-06 Stage 2 characterisation

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-023 | Balance / price response | **P2 pending confirmation** | GSP-CRV2-06 (raised) | In the joint price × volume characterisation, **units sold are identical across a 40× price range**: 2112.32 units at retail prices of 50, 420 and 2000, and 2143.616 units at every price when production rises to 60,000. Revenue is therefore `price x constant`, so raising price from 420 to 2000 multiplies revenue **4.76×** with no volume penalty. The index effect within the round is small (+0.12), because the composite is dominated by non-financial components; the cash effect is not, and cash compounds into later rounds. | `characterisation.json` → `joint["retail price x production volume"]`. Same-team counterfactual from one checkpoint; the baseline resolved twice with zero delta. | Open — mechanism unconfirmed |

**Mechanism hypothesis, not established.** `preference_engine` scores price
purely relatively: `ratio = team_price / market_avg_price`, where the average is
taken over *other* teams sharing the product's positioning in that market and
the team's own price is then appended. Where no rival shares that positioning,
`prices == [team_price]`, the ratio is 1.0 at any price, and price stops
affecting demand. A fixture diagnostic confirmed that positioning groups in this
scenario do vary in size — two teams share `eu/mainstream` and `eu/premium`,
while `na/mainstream` and `na/premium` hold one team each — but **the diagnostic
output was truncated before it recorded which group the measured team was in**,
so the explanation is not confirmed and is offered as a hypothesis only.

Severity is provisional at P2 for that reason. If the mechanism is confirmed it
is materially worse than P2: a team can choose a positioning nobody else
occupies and then price without demand consequence, which is a strategy choice
rather than luck. Confirming it needs one focused probe — vary price for a team
known to share its positioning, and for one known to be alone — which belongs
with the Stage 3 search that is currently out of scope.

## New findings raised by GSP-CRV2-06 Stage 2 rule probes

Both measured by same-game transactional counterfactual at `b43c132`: one team,
one frozen checkpoint, one decision changed, everything rolled back. The
baseline was resolved twice and the delta was exactly zero on every metric, so
these differences are the rule and not noise. Evidence:
`evidence/adversarial-balance/rule-probes.json`.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-021 | Scoring / strategic capability | **P1** | Rules owner (raised by GSP-CRV2-06) | `_strategic_capability_component` scores R&D as `rd_spend / rd_budget`, clamped to 1, and capability carries 0.25 of the performance index. The denominator is the team's *own declared budget*, so the ratio measures self-consistency rather than investment. Declaring **$1** and spending **$1** scores 1.00 where a $100,000 programme against a $2,000,000 budget scores 0.05. Measured: index **56.54 → 58.45 (+1.91)**, composite **0.5772 → 0.6724 (+0.0952)**, while spending **$99,999 less** — cheaper *and* higher-scoring, and independent of what any opponent does. | `rule-probes.json` → `capability_ratio`. Single round; the multi-round trade-off is unmeasured — see the uncertainty note below. | **Closed** at `827a2e1` under an adopted disposition — see below |
| V2-022 | Scoring / anti-exploit guard | **P1** | Rules owner (raised by GSP-CRV2-06) | `_is_voluntarily_commercially_inactive` caps the composite at 0.25 only when *every* marketing row has production, promotion, distribution and sales staffing at or below zero. It tests the **decisions**, not the outcome. Setting `production_volume = 1` on one row defeats it: composite **0.2500 → 0.4123 (+0.1623)**, index **50.00 → 53.25 (+3.25)** — for **$181.86**. Critically, **`total_revenue` is `0.00` in both cases**: the team sold nothing. The guard is escaped by declaring an intention to produce, not by competing. | `rule-probes.json` → `one_unit_bypass`. The hypothesis was "sell one unit"; the measurement shows no sale is needed. | **Closed** at `827a2e1` under an adopted disposition — see below |

### Adopted dispositions and closure — V2-021 and V2-022

**V2-021 adopted rule**

```
rd_score = clamp01(rd_spend / scenario_rd_spend_target)
```

`rd_spend_target` is a scenario configuration value the team cannot choose,
initialised at **$2,000,000** — the figure `load_demo` scripts as competent
R&D, so a team playing the documented baseline scores what it always did. A
missing, zero or negative target raises `InvalidScenarioConfiguration` and the
round is not scored; a silent default would change what the competition rewards
without anyone deciding to, which is the failure V2-021 was. Cohort-maximum
normalisation was explicitly **not** adopted: it would hand $1 full credit
whenever $1 was the largest spend in the room.

Seeded in scenario YAML for fresh loads and by migration `0073` for scenarios
already in a database. `scenario_config` is already a manifest input section,
so the value is in the deterministic digest.

**V2-022 adopted rule**

```
material_revenue_floor = max($1, 0.01 x highest positive team revenue this round)
```

A team whose realised revenue is below that floor is commercially inactive.
The composite cap and the ranking guard now consume this one classification, so
the two controls cannot disagree about who competed. Declarations of
production, promotion, staffing or distribution do not exempt a team.

**The original exploit probes, re-run against the repaired rules at `827a2e1`:**

| Probe | Before | After |
|---|---|---|
| `$1` budget / `$1` spend | index **+1.91**, composite **+0.0952** | index **−0.09**, composite **−0.0048** |
| One unit of production | composite **0.2500 → 0.4123** (+0.1623) | composite **0.2500 → 0.2500** (0.0000) |

Both exploits fail. The `$1/$1` strategy is now marginally *worse* than the
baseline rather than better: it still keeps the $99,999 it declined to spend,
which is ordinary thrift, but it no longer buys a higher capability score.
The token-production team is capped exactly as the silent team is.

Controls: 13 focused tests for the two rules, 108 passing across the affected
set (`test_scoring_dispositions`, `test_cc18_compliance`, `test_equity_issuance`,
`test_decision_limits`, `test_engine`).

### V2-022 supplementary disposition — compliance-frozen teams (adopted)

A compliance-frozen team whose realised revenue is below the material revenue
floor **receives the commercial-inactivity composite cap.** Production intent
does not exempt it.

The two controls address different consequences and are meant to stack:

* the **compliance freeze** is the consequence of a compliance failure;
* the **inactivity cap** stops a team without material realised sales from
  keeping a competitively misleading composite score.

This reverses the previous behaviour, where a team with real production and
promotion but no revenue was explicitly not classified as inactive. Two tests in
`test_cc18_compliance` asserted that older rule; they are preserved and reversed
rather than deleted, and one now asserts the compliance-frozen, below-floor case
directly.

### Superseded — the disposition request as originally filed

### Disposition requested — V2-021

The ratio needs a denominator the team does not choose. Three candidates, in
the order I would rank them:

1. **Normalise against the cohort, as the other components already do.**
   `_market_component` and `_financial_component` both score with
   `_ratio(value, max_across_teams)`. Scoring R&D spend the same way makes
   capability comparable between firms and removes the incentive to shrink the
   denominator. Smallest conceptual change; consistent with the surrounding code.
2. **Normalise against a scenario-configured target R&D spend.** Stable across
   cohorts and explainable to students, but adds a parameter per scenario.
3. **Normalise against the team's own revenue or asset base.** Defensible as an
   intensity measure, but couples capability to size in a way the current model
   does not.

### Disposition requested — V2-022

The guard should test what happened, not what was declared. Concrete options:

1. **Cap on outcome, not intent** — apply the composite cap when revenue is
   below a configured floor rather than when the decisions are all zero. This
   also closes the variant found here, where revenue was zero and the cap still
   did not apply.
2. **Require materiality** — treat production below a threshold relative to
   demand or capacity as inactivity, so a token unit does not qualify as
   competing.

Option 1 is the smaller change and matches the guard's stated purpose. Note that
`_enforce_zero_revenue_invariant` is a *separate* control keyed on zero revenue;
whichever option is chosen, the two guards should be brought onto the same
definition rather than left with different tests for the same idea.

### Uncertainty on both

These are **single-round** measurements. A team declaring a $1 R&D budget also
funds no real R&D, so its feature levels should fall behind over a full game;
whether the index gain survives multiple rounds is unmeasured. Establishing that
is Stage 3's multi-round search, which is blocked on V2-010/V2-011. Neither
finding is claimed as a proven whole-game dominant strategy — each is a
demonstrated, repeatable, opponent-independent advantage within a round.

## New finding raised by GSP-CRV2-06 Stage 2

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-020 | Engine / equity issuance | **P0** | GSP-CRV2-06 (raised) | `generate_financial_statements` prices newly issued shares with `share_price_est = total_equity / shares_outstanding` at `financials.py:212`, but `total_equity` is not assigned until line 262 — fifty lines later, inside the same per-team loop. For the **first** team in the loop that raises equity this is `UnboundLocalError`, and because the call sits inside `_run_phase_1`, **the whole round fails to resolve for every team**. For any **later** team it silently holds the *previous team's* closing equity, so one company's shares are priced off another company's balance sheet and the dilution written to the leaderboard is wrong. Raising equity is an ordinary legal decision exposed by `DecisionFinancing.new_equity`. | Found by Stage 2 screening: setting `financing.new_equity` to its funded maximum crashed resolution. Nothing in the repository exercises `new_equity > 0` — every test and seed command sets it to `0`, which is why it survived. Inherited from the baseline snapshot `2509518`, so it predates globalstrat+. | **Closed** at `c781c8f` under an adopted rules disposition — see the closure entry below |

### V2-020 rules disposition — adopted

**Adopted formula:**

```
issuance_price = opening_total_equity / opening_shares_outstanding
```

Book equity per share, measured before the raise. Adopted because it preserves
the apparent intent of the defective expression, is available before the raise,
is specific to the issuing team, is deterministic, avoids pricing a raise with
the equity that raise creates, and is the smallest change from what was there.

**Considered and not adopted:** the latest price from `SharePriceHistory`. That
would move the model from book-value issuance to market-price issuance and
needs policy for missing and stale prices — a larger rules change than the
defect required.

**Verification at `c781c8f`** (`core/tests/test_equity_issuance.py`, 7 tests):

| Requirement | Test |
|---|---|
| First team raising equity resolves | `test_the_first_team_raising_equity_does_not_fail_the_round` — every team is still scored |
| Teams price from their own opening equity, never another's | `test_shares_are_priced_off_the_issuing_team_s_own_equity` |
| Equal equity-per-share ratios price identically | `test_equal_book_value_per_share_gives_equal_issuance_price` — $1m/1,000 shares and $10m/10,000 shares issue the same count |
| Different ratios give the counts the rule requires | `test_different_ratios_give_the_share_counts_the_rule_requires` — exact counts derived from the formula, and a fiftieth of the price buys fifty times the shares |
| No-raise behaviour unchanged | `test_a_team_that_raises_nothing_is_unchanged` |
| Replay inputs carry every opening value used | `test_the_manifest_captures_every_opening_value_the_price_uses` — `total_equity` and `shares_outstanding` are both in the input manifest's `team` section |
| The defect's shape cannot return | `test_equity_is_not_priced_from_a_figure_computed_later` |

Three of these fail against the unrepaired engine; the no-raise control passes
either way, which is what makes it a control.

## New findings raised by GSP-CRV2-06

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-018 | Decision validation / value loop | **P0** | GSP-CRV2-06 | **Thirteen** investment and headcount fields accepted a negative value, and `costs.py` adds several straight into `strategy_expense`, so a negative investment was income. Measured on resolved rounds: `environmental_investment = -5,000,000` turned a $1,130,000 loss into a $3,990,000 profit with zero revenue; a negative **headcount**, multiplied by a salary band, was worth **$50,002,530,000**. Seven further fields accepted negatives but were masked in the first probe by another field failing first, plus one supply-chain field — 21 in all. No lower bound existed anywhere, and the fields were reachable through the ordinary decision API. | `evidence/adversarial-balance/value-loop.json` and `negative-sweep.json`: identical teams differing in one field's sign, resolved through `_run_phase_1`; `strategy_expense_delta` equals the injected amount. | **Closed** by two defences. **API prevention:** one table in `core/serializers/decision_limits.py`, applied at field level to 21 fields across both write surfaces. **Engine fail-closed:** `_run_phase_1` applies the same table to the *persisted* rows before any competitive mutation and raises `InvalidPersistedDecisionError` naming model, row, submission and field — it refuses, it does not clamp, because a clamped value is a team's decision quietly replaced with a different one and scored as theirs. Needed because rows can also arrive from a migration, import, admin, shell or restore, and the engine scores rows. 17 focused tests; the API tests fail against the pre-repair serializers and the five engine tests fail with the precondition removed. |
| V2-019 | API uniformity / determinism | ~~P1~~ **Withdrawn — filed in error** | GSP-CRV2-06 | Filed as "the per-type R&D endpoint accepts a duplicate platform+feature payload the whole-submission endpoint rejects". **That was measured on the serializers, not the endpoints, and described as endpoint behaviour.** `DecisionPartialUpdateView` has called `validate_rd_investment_targets` on the assembled list since `86c2ad4`, so both endpoints always refused the duplicate. Contract tests written against the real API pass unchanged on the pre-repair code. What was real is narrower and not an exploit: the rule lived in two places — the submission serializer and the view — so any third caller using `DecisionRDInvestmentSerializer(many=True)` directly would have missed it. | `core/tests/test_decision_limits.DuplicateRdRowApiTests`: both paths refuse for the intended reason, the distinct-feature control is accepted, and neither writes a row. These pass before and after the repair. | **Withdrawn.** The duplication is repaired anyway: the rule now lives in `DecisionRDInvestmentListSerializer` and runs wherever the rows arrive together |

V2-018 was found in Phase 1, from the serializer registry and a controlled
engine probe, before any optimizer was built.

V2-019 is left in the register as a withdrawn entry rather than deleted,
because how it was filed matters more than that it was wrong. The check
compared `DecisionSubmissionSerializer` with `DecisionRDInvestmentSerializer`
and reported the result as "the API accepts". It never made a request, so it
could not see that the view supplies the rule the serializer lacks. Before it
reached even that state it reported "no divergence" twice for two different
wrong reasons — an unavailable platform/feature pair, then missing `team` and
`round` fields that stopped DRF calling `validate()` at all. A probe that
cannot tell "allowed" from "refused for an unrelated reason" is not evidence,
and neither is one that measures a layer and names a different one.

## New finding raised by GSP-CRV2-04

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-017 | Operator boundary / route inventory | **P1** | GSP-CRV2-02 boundary (raised by GSP-CRV2-04) | The route inventory that certified "0 unguarded mutating routes" can only inspect routes whose callback exposes a view class. Django's admin add/change/delete views are function-based, so **216 admin write routes are skipped entirely** — including `Game`, `Round`, `Team`, `DecisionSubmission`, `ActiveModifier` and `SCEventInstance`. A staff user can move round state through `/admin/` with no lifecycle lock and no `OperatorAuditEvent`. The `<path:object_id>/` routes that *do* appear resolve to `RedirectView` and are reported `lifecycle_mutating: false`, which is how a whole write surface came to be counted as harmless. | `_walk(get_resolver())` yields 778 routes; 371 have no view class and are skipped by `mutating_routes()`, 216 of them admin add/change/delete. `core/services/route_inventory.json` lists `admin/core/round/<path:object_id>/` as `RedirectView`, `lifecycle_mutating: false`, and lists no `.../change/` route at all. | Open — logged, not repaired here |

Reach is limited to Django `is_staff` accounts, not the JWT instructor role, so
this is P1 rather than P0. It is logged rather than repaired because the fix
belongs to V2-004's boundary, and changing that boundary here would invalidate
the concurrency certification GSP-CRV2-02 produced. GSP-CRV2-04 repaired only
the part inside its own scope: the five audit-record admins it registered are
read-only, and the database triggers refuse the writes regardless.

## New findings raised by GSP-CRV2-01

Severity legend, restated because the first triage of V2-010/V2-011 used it
wrongly: **P0 blocks; P1 degrades; P2 cosmetic.** A behaviour that can change a
published result is never P2.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-010 | RNG cohort key | **P1** | GSP-CRV2-06 | Two different cohort keys are in use. `core/engine/rng.py` seeds on `game.section_id or game.id`; `sc_engine._seed()` and `compliance_engine` seed on `game.id`. Two sections of one class running the same scenario therefore receive the same event stream but different supply-chain and compliance streams. Escalates to **P0** if parallel sections are ever scored against one another, because the disruption exposure they face would differ by construction. | Compare `core/engine/rng.py` with `core/engine/sc_engine.py:_seed` and `core/engine/compliance_engine.py`. | **Closed** at `8ddd983` — option A adopted, see below |
| V2-011 | Shared RNG stream | **P1** | Competition-rules owner (via GSP-CRV2-09) | The supply-chain and compliance passes consume a single `random.Random` across all teams, so draw *n* belongs to whichever (team, regime, market) triple reaches the roll *n*-th. Iteration order is now explicit and replay is exact, but adding or withdrawing a team shifts every later team's draw — one team's presence changes another team's outcome. | `core/engine/compliance_engine.py:enforce_compliance`; `core/engine/sc_engine.py:run_sc_state`. | **Closed** at `8ddd983` — option A adopted, see below |
| V2-012 | Iteration order | **P0** | GSP-CRV2-01 (closed) | The first ordering sweep inspected only inline loop iterators, so `rows = X.objects.filter(...)` followed by `for row in rows` was never checked. `_score_entry_mode_risk` iterated an unordered `TeamMarketPresence` scan; a restored database returned two markets in the opposite order, changing `RoundResultCoherence.breakdown` and the competitive hash. A published round did not reproduce. | Cross-environment replay of game 34 round 1: three same-host replays agreed with each other and disagreed with the original resolution; the section diff named `coherence` and the reordered `entry_mode_risk` list. | **Repaired** — 75 further sites ordered; the AST guard now resolves a loop over a local name back to its assignment. |
| V2-013 | Manifest envelope | **P1** | GSP-CRV2-01 (closed) | The output snapshot held only the competitive sections, so foreign keys pointing at configuration it did not contain (`Team.firm_starter_profile`, `Game.scenario`, `Team.home_market`) fell back to `core.Scenario#surrogate:7`. The competitive hash carried raw sequence values, defeating the surrogate-independence requirement. Never broke a replay, because a restored database reproduces the ids. | Inspect any pre-repair `output_manifest` for `#surrogate:`. | **Repaired** — both envelopes now pull in whatever identity requires; a test forbids `#surrogate:` in either. |
| V2-014 | Narrative envelope | **P1** | GSP-CRV2-01 (closed) | A narrative section's prose is separated into `narrative_rows` by the snapshot, and the narrative envelope was built from `rows` alone. `narrative_sha256` hashed briefing ids and round numbers, not a word of text — so a replay against a deliberately different model produced an identical narrative hash and the "prose differs, result does not" claim was unverifiable. | Two runs of game 36 round 1 under different endpoints reported the same `narrative_sha256`. | **Repaired** — the envelope carries `prose` and `prose_digests`; tests require that changing a briefing changes the narrative hash and leaves the competitive hash alone. |

| V2-015 | Narrative / manifest reconciliation | **P1** | GSP-CRV2-03 | Phase 2 writes into rows and fields that `output_sha256` covers, after that hash has been taken: `RoundResultCoherence.rag_score/blended_score/breakdown`, `SCEventInstance.resolution_data['narrative']`, and newly created `InstructorAlert` coaching rows. The hash never moves — it is computed inside the Phase-1 transaction — so every replay matches; what diverges is the *stored database* from the manifest that certified it, which no replay compares. | Resolve a round with an API key configured, wait for Phase 2, then rebuild the output manifest and compare with the stored `output_sha256`. | **Repaired in GSP-CRV2-03** — see closure entry. |
| V2-016 | LLM reaches a graded number | **P1** | GSP-CRV2-03 (closed) | `RoundResultCoherence.blended_score` is read by `core/services/grading.py`. With an LLM reachable, coherence was `0.6·formula + 0.4·RAG`; without one, the formula score stood. Two identical competitions therefore graded differently depending on an external service's availability. Rank was unaffected: neither `performance.py` nor `leaderboard.py` reads coherence. | `grep blended_score core/services/grading.py`; compare a round resolved with and without `DASHSCOPE_API_KEY`. | **Closed** at `49d6514` — see closure entry below |

### Disposition required for V2-010 and V2-011

Neither is implemented inside GSP-CRV2-01: changing a seed or a draw order
changes published results, which is a rules decision, not a hardening one. The
choice the competition-rules owner has to make is stated here so it cannot stay
ambiguous.

* **V2-010.** Either (a) cohort identity is meant to give every section of one
  class the same scenario stream, in which case `sc_engine` and
  `compliance_engine` must move to `game.section_id or game.id` and a test must
  pin all three call sites to one key; or (b) supply-chain exposure is meant to
  be per-game, in which case that is a published rule and the event stream
  should arguably move to `game.id` for the same reason. Silence is not a third
  option: today the two halves of the engine disagree.
* **V2-011.** Either (a) per-team independence is required — each roll keys on
  `(team, regime, market)` through `get_rng`, as the rest of the engine already
  does — or (b) a shared stream is accepted and the rules state that a
  withdrawal changes later teams' draws, with the withdrawal procedure written
  to match. Option (a) is the smaller change and matches `core/engine/rng.py`'s
  documented convention.

### V2-016 — LLM reaches a graded number (P1) — closed at `49d6514`

**Adopted rule: published coherence and the grades derived from it are the
deterministic formula score. Retrieval is instructor commentary and nothing
else.**

The first GSP-CRV2-03 submission made the blend configurable and defaulted it
off. The audit rejected that: a setting a supported deployment can flip is not
a safe competition configuration, and default-off left the defect one
environment variable away. The rework removed the Phase-2 write path outright.

At `49d6514`:

* `update_coherence_with_rag()` writes no competitive field in any
  configuration. It records the evaluation as an `InstructorAlert` with
  `source='narrative'`, which the manifest keeps outside the competitive
  section.
* `COMPETITION_RAG_AFFECTS_COHERENCE` is retired. The name survives only so a
  stack still setting it fails loudly:
  `require_safe_rag_configuration()` runs before the resolution transaction
  opens, so a misconfigured stack stops without taking a backup or a lock.
  Silently ignoring the flag would be worse than either behaviour — an operator
  who set it deliberately would believe retrieval was being graded when it is
  not.
* `core/tests/test_durable_narratives.py::CoherenceIsolationTests` proves all
  three legs: flag unset, flag set with the job run, and resolution attempted
  with the flag set.

Grading retrieval remains a legitimate rules choice. It is now a Phase-1
change — inside the transaction the manifest hashes, certified with the rest of
scoring — and not a flag. Nothing is outstanding for the rules owner.

- Evidence: `evidence/durable-narratives-rework/`.
- Completion: `completion/GSP-CRV2-03-completion.md`, rework addendum.

## Closure entries

### V2-001 — expanded output envelope (P0) — closed

`output_sha256` now covers **72 enumerated sections**: game/round lifecycle,
roster, every accepted decision table (including all ten supply-chain decision
tables), live market/event/modifier state, all eighteen carried per-team state
tables, and all published result tables. The section list, each section's
natural key, and the classification of every model field are recorded in
`backend/core/services/manifest_schema_v2.json`; every excluded field carries a
written justification, and `test_manifest_determinism` fails if a model gains a
field that no rule and no justification covers.

Phase-2 prose is hashed separately as `narrative_sha256` and reported
separately. Measured wall clock is excluded from the competitive hash and kept
in the input envelope, where it is a frozen fact about the starting state.

No surrogate primary key or foreign-key id reaches either envelope: a row is
identified by a natural-key token with foreign keys resolved recursively, and
the snapshot pulls in whatever sections identity requires (V2-013).

- Code: `core/services/manifest_sections.py`, `manifest_snapshot.py`,
  `manifest_schema.py`, `canonical_json.py`, `build_identity.py`,
  `resolution_manifest.py`; migrations `0061`, `0062`.
- Tests: `core/tests/test_manifest_determinism.py` (50), plus the updated
  envelope assertion in `core/tests/test_competition_hardening.py`.
  Backend suite 328.
- Evidence: `evidence/determinism/` — four replays of game 37 round 1 all
  produce `129a374ec6a82f22da9514ad3c263b856381024f46ad31790e5a36e08589b383`,
  including a second container on Debian 12 / Python 3.11 whose *process*
  timezone is `Asia/Kolkata` (`time.tzname == ('IST','IST')`) under
  `LC_ALL=de_DE.UTF-8`, asserted with `--require-env` rather than labelled.
  Four different narrative hashes, with the prose stored beside each.
- Docs: `DETERMINISM_BOUNDARY.md`, `ORDERING_AUDIT.md`,
  `evidence/determinism/README.md`.

### V2-002 — manifest sufficient to explain an input (P1) — closed

`input_sha256` covers canonical snapshots of the accepted decision payloads
themselves (not hashes of them), the full scenario and engine configuration,
per-class configuration overrides, live market/event/modifier state, starting
team and per-team state, the roster, the ordered decision audit trail, the RNG
seed derivation inputs, and the applied migration list. The code revision and a
host fingerprint are recorded alongside — outside the hash, deliberately, so a
cross-environment replay can match.

Surrogate primary keys appear nowhere: every row is identified by a natural-key
token with foreign keys resolved recursively, so a diff names the row a person
can recognise (`team(game("…")|"Nova Circuit")`) rather than an integer.

The envelope is versioned. Version-1 manifests stay readable exactly as stored
and are never reinterpreted as version 2 — `require_schema_version` refuses, so
a v1 hash cannot be compared against a v2 hash and called a match.

The build that resolved a round is identified by content, not only by a commit
hash. `core/services/build_identity.py` digests every runtime source file under
`backend/`; a `-dirty` suffix names the commit but not the modifications on top
of it, and two different patches on one HEAD produce the same string.
Resolution refuses an unidentified build when `COMPETITION_REQUIRE_CLEAN_BUILD`
is on (the default in production), and replay refuses a source mismatch before
it mutates anything.

- Command: `manage.py replay_round` verifies the source tree, asserts its own
  environment fingerprint (`--require-env`), and verifies input integrity
  **before** any mutation (exit 2, engine not run), printing per-section diffs
  on a hash mismatch (exit 3). `manage.py dump_manifest_schema --check` guards
  the inventory. `recover_competition_round` verifies the restored state
  against the recorded manifest before re-running.
- Negative tests: a corrupted decision payload, a corrupted scenario value, a
  corrupted carried-state value and an altered source tree each fail before
  processing — `evidence/determinism/negative/`. The source-tree case is the
  telling one: `git status --untracked-files=no` reported the tree clean and
  the commit hash was unchanged, and the replay still refused.
- Durability: each envelope is also written to a content-addressed file under
  `<COMPETITION_BACKUP_DIR>/manifests/`, so it survives losing the database.
  The digest in the filename is the manifest's own `input_sha256` /
  `output_sha256`.

### V2-004 — fail-closed operator concurrency (P0) — closed (second submission)

The first submission was returned FAIL. Its inventory was built by tracing the
routes its author knew about, so five registered lifecycle endpoints were never
examined, and a server-minted request id was regenerated per call so a refusal
response pointed at an id no audit row carried. Both are repaired below, and
the inventory is now built mechanically from `urls.py` — which found **nine
more** unguarded routes than the audit had listed.

Every action that can change round state, decision state or the roster now
passes through one coordination boundary — an exclusive advisory lock per game,
taken before any row lock — and evaluates its preconditions *after* acquiring
it. Student decision writes take the same lock shared, so they run concurrently
with each other and are excluded by any operator action.

**Twenty** entry points are on it and **zero** registered mutating routes are
unguarded, measured from the URL conf rather than from calls to the boundary
(`core/services/route_inventory.py`, checked in as `route_inventory.json`).
Sixteen routes carry view-keyed reviewed exemptions, each stating what was
checked. `RouteCoverageTests` fails on drift or on a new bypass.

**Six routes were removed rather than repaired.** All came from BECSR; four
queried `Round.objects.get(round_id=...)` — a field this project's `Round` does
not have — and so returned **500 to every caller**, and all six duplicated
close, reopen, deadline or bulk scheduling under a second vocabulary. "Lock"
and "unlock" meant `Round.decisions_locked`, a flag the *student write path*
reads independently of `Round.status`, so legacy unlock could let students
write into a closed round. That flag is now a projection maintained only by
close/reopen, with a test asserting it always equals
`status in ('closed', 'processed')`.

Newly guarded in this submission: `GameRoundScheduleView` (the only bulk
scheduler; now validate-all-then-write), `GameActivateView`, `GamePauseView`,
`GameResumeView`, `GameArchiveView`, `GameResetView` and
`InstructorTeamConfigView`. The five game-status views used bare `game.save()`,
which rewrites every column from its own copy and could rewind
`Game.current_round` past a concurrent advance.

The full inventory, the lock order, the 409/400 rule and the force-flag policy
are in `OPERATOR_CONCURRENCY_MATRIX.md`.

Two behaviours worth calling out:

* **Refusals are audited.** `OperatorAuditEvent` gained `outcome` and
  `conflict`. A rejected attempt is written *after* the transaction it refused
  has rolled back, in its own transaction, with an empty `after` — so a race is
  visible to whoever investigates without the row implying the round moved.
* **Callers can prove they were not racing.** `expected_round_number` and
  `expected_status` are compared under the lock; a mismatch is a 409
  `state_moved` naming what changed, which is what separates losing a race from
  asking too early. The console sends what it rendered.
* **One request id per request.** Resolved once and cached on the request. It
  was previously regenerated on each call, so a server-minted id in a refusal
  response was not the id on that refusal's audit row — the correlation the
  runbook tells an operator to use led nowhere. Tests assert the response id
  matches exactly one audit row, for supplied and generated ids alike and for
  commits, conflicts and preconditions.

- Code: `core/services/lifecycle.py` and `route_inventory.py` (new),
  `competition_locks.py`, `round_control.py`, `results_api.py`,
  `scenario_views.py`, `course.py`, `team_config.py`, `instructor_sc.py`,
  `decisions.py`, `team_control.py`, `advance_round.py`,
  `check_round_deadlines.py`, `recover_competition_round.py`,
  `competition_audit.py`; migration `0063`.
  Phase-2 dispatch moved to `transaction.on_commit`, so a view wrapping
  `process_round` cannot have the narrative thread read a round the database
  has not accepted yet.
- Tests: `core/tests/test_operator_concurrency.py` — 12 pairs × 100 races ×
  both arrival orders, plus route-coverage and request-id correlation tests.
- Evidence: `evidence/operator-concurrency/` — **1200 races, 0 deadlocks, 0
  5xx**, with advisory-lock rows sampled mid-race showing genuine contention
  and status-code tallies showing both orders really won (process+process
  53 / 47; schedule+close 52 / 48).
- Docs: `OPERATOR_CONCURRENCY_MATRIX.md`, operator runbook.

### V2-006 — durable Phase-2 narrative execution (P1) — closed

Resolving a round writes six `NarrativeJob` rows **in the same transaction as
the numbers**: if the results committed, the outstanding work is recorded.
Workers claim with `SELECT … FOR UPDATE SKIP LOCKED` under a lease, so several
run without coordinating and a worker that dies leaves a lease the next one
reclaims — nothing has to notice the death. Attempts are bounded, `failed` is
terminal and visible, and `retry_narrative_jobs` requeues without re-running
scoring.

`Round.processing_status` and `narrative_error` still drive the console, but
they are now a projection of the job rows rather than the only record, which is
what makes an abrupt death survivable.

A job that finishes on template fallbacks is recorded as `degraded` rather than
plainly `succeeded`. The drills found that: with an unreachable provider every
job reported success, because each producer falls back — correct for students,
who still get a briefing, and silent for operators.

- Code: `core/models/narrative_jobs.py`, `core/services/narrative_jobs.py`,
  `core/engine/narratives.py` (per-type runners), `advance_round.py`,
  `coherence.py`, `manifest_sections.py`, `manifest_snapshot.py`,
  `run_narrative_worker`, `retry_narrative_jobs`; migrations `0064`–`0068`.
- Tests: `core/tests/test_durable_narratives.py` — 28 tests covering enqueue,
  claim/lease/reclaim, timeout / 429 / 500 / malformed output / no key,
  idempotency, isolation and secret redaction. Backend suite **387**.
- Evidence: `evidence/durable-narratives/` — a real SIGKILL of a worker holding
  a claimed job, with recovery; three provider conditions including the live
  model. Competitive hash unchanged in every case.
- Docs: `NARRATIVE_WORKER_OPERATIONS.md` (supervision, leases, backlog
  alerting), `NARRATIVE_JOB_INVENTORY.md` (the Phase-1 inventory).

### V2-007 — database-enforced audit integrity and read evidence (P1) — closed in GSP-CRV2-04

**What the finding was.** The audit models raised on a second `.save()`, and
that was the entire defence. `Model.objects.filter(...).update()`,
`.delete()`, raw SQL, `manage.py shell` and the admin all skip `save()`, so
"append-only" described the usual write path rather than the table.
`ResolutionManifest` had no guard at any layer.

**What decided the design.** The application connects to PostgreSQL as the
**owner** of the tables it audits (`donwh`, verified against `pg_tables` and
`has_table_privilege`). Revoking `UPDATE`/`DELETE` from the connecting role
achieves nothing while that role can grant it back, and an owner can drop any
trigger. So the repair separates two claims that are easy to blur:

* **Rejected** — every write the application can make, at any layer. Triggers
  on all five audit tables refuse `UPDATE` and `DELETE` regardless of role.
* **Detected** — a change made by whoever holds the maintenance credentials.
  Nothing can reject that. A forward hash chain over the audit rows, with its
  head exported outside the database, makes it visible afterwards.

The report does not claim the second category is prevented.

**The manifest exception.** `ResolutionManifest` is written twice by design —
`prepare_manifest` before resolution, `complete_manifest` after — so a blanket
no-`UPDATE` rule would have broken round resolution. Its trigger allows updates
while `completed_at IS NULL` and freezes the row the moment it is set, which is
the moment it becomes evidence. `DELETE` is refused at all times.

**Sealing and the lock order.** Chaining runs in `transaction.on_commit`, not
in the audit write. The seal takes a global advisory lock, and taking it
underneath the operator lifecycle locks GSP-CRV2-02 certified would invert a
lock order and could deadlock. One seal is scheduled per transaction, and the
scheduling check reads Django's pending-callback list rather than setting a
flag, so a rolled-back transaction cannot leave a marker that suppresses the
next seal.

**Read evidence.** `competition_sensitive_read_event` records reads of raw team
decisions and audit payloads: actor, subject game/team/round, route, endpoint,
status, outcome, request id, server time. Refusals are recorded alongside
successes, because a denied cross-team read is the more useful row when a team
alleges disclosure. No payload, header or token is stored, and no API route
serves the table — it is reachable only through `manage.py who_accessed`.
Coverage comes from middleware matching `core/services/read_inventory.json`,
generated from the URL conf, so a view registered later is covered by
construction rather than by memory.

**Still open, and deliberately not closed by code.** The application holds the
owning credentials. `install_audit_guards --role-sql` provisions a non-owner
role and the SQL is tested, but pointing the competition stack at it is a
deployment action. Until then the reject layer is triggers alone.

See also V2-017, raised while building this handoff's inventory.

### V2-009 — supported frontend toolchain and green verification (P1) — closed in GSP-CRV2-05

**The finding named the wrong cause.** It attributed the Jest failure to the
Node engine mismatch (`react-router-dom@7` wants `>=20`, the VM's system node is
18). Reproduced on **Node 22.17.1**, which satisfies that range, the failure is
identical: `Cannot find module 'react-router-dom' from 'src/App.js'`.

The cause is packaging. `react-router-dom@7.1.1` declares `main: "./dist/main.js"`
and does not ship that file — `dist/` holds `index.js` and `index.mjs` only. Node
resolves the package through `exports`; react-scripts 5.0.1 pins jest 27, which
predates `exports` support, falls back to `main`, and finds nothing. Checked
against the registry, **every** published 7.x carries the same dead `main`
(7.1.1 → 7.6.3 verified, including a clean install of 7.6.3), so neither a
Node upgrade nor a 7.x upgrade fixes it.

**Repair:** `react-router-dom@6.30.6`, which ships the file its `main` names and
requires only Node `>=14`. All eight router APIs this application imports exist
unchanged in v6, no data-router API is used, and the two v7 defaults that could
have behaved differently are inert — every navigation in the codebase is
absolute, so `v7_relativeSplatPath` has nothing to change.

**Three further defects were found while closing it**, none of which the finding
mentions:

1. **`npm ci` could not install the project at all.** `react-scripts` peers
   `typescript@^3||^4`, `i18next`/`react-i18next` peer `typescript@^5`, no
   version satisfies both, and npm 10 installs optional peers by default. The
   1.6 GB `node_modules` on the VM was produced by some other command than the
   one the acceptance names. `--legacy-peer-deps` was tried and **rejected on
   evidence**: it makes the install succeed and the build fail, because
   `ajv-keywords@5` then cannot find the `ajv@8` it peers on. Settled with
   `overrides: { "typescript": "^5.9.3" }`, which leaves peer resolution strict
   and pins only a package with no source files in this repository.
2. **`axios@1.7.9` fails Jest for the same reason as the router** — ESM at
   `main`, CJS only via `exports`. Babel now transforms it, so the test runs the
   same source the browser bundle does.
3. **A failed drill-down request was displayed as "no submission data"**, the
   same thing shown for a team that submitted nothing. On the screen an
   instructor opens to defend a disputed result, a server error was being
   rendered as evidence about the team. Repaired and covered by test.

**Also closed:** `yarn.lock` removed (yarn is not installed on the host, so it
was a second source of truth nothing validated); runtime pinned in `.nvmrc`,
`engines` and `packageManager`; CI added reading the runtime from `.nvmrc`;
CRA's stock `renders learn react` placeholder replaced with a test that mounts
the app and asserts the router resolves the default route.

## Scope notes

- The Phase-2 LLM path is outside the existing output hash and is dispatched only after the deterministic transaction commits. No LLM value is read by the Phase-1 scoring call graph. This part of the v1 claim is structurally sound, subject to outage/restart verification.
- Wall-clock values are lifecycle/audit metadata or duration fields. They are excluded from the competitive hash by rule (`manifest_sections.MEASURED_TIME_FIELDS`) and kept in the input envelope as frozen facts about the starting state.
- The unordered-query sweep is complete: 168 iterated querysets in `core/engine/` had no explicit ordering — 93 written inline and 75 reached through a local name, the second group found only after a cross-environment replay failed (V2-012). All now declare one except six documented exemptions whose result cannot depend on order. See `ORDERING_AUDIT.md`. An AST test fails the suite on any new unordered loop in either form, and a forward/reverse insertion test re-runs the whole Phase-1 pipeline over reordered rows.
