# GSP-CRV2-06 Phase 1 — the legal decision space, discovered

Built before any optimizer, from the DRF serializer registry that the write
endpoints actually use and from the routed decision types in
`core.views.decisions._TYPE_MAP`. No dimension list was typed out by hand, and
no bound was taken from reading a `validate_` method: every bound below was
established by offering a value to the real serializer and recording what came
back.

Harness: `evidence/adversarial-balance/harness/`. It runs against a database it
creates and drops, seeded through the project's own `setup_test_game`.

## 1. Shape of the space

| | |
|---|---:|
| Decision types reachable by the per-type PATCH endpoint | 14 |
| Dimensions across them | 67 |
| Types not probed | 0 |
| Numeric dimensions that accepted a negative value | 20 (12 cleanly, 8 where another field blocked the payload first) |

Full data: `evidence/adversarial-balance/dimension-inventory.json`, which records
every probe value and the serializer's verdict for each.

## 2. Thirteen dimensions accepted a negative investment

Cleanly accepted — the field itself raised no error:

| Decision type | Field |
|---|---|
| `esg` | `environmental_investment`, `social_investment` |
| `market-entry` | `initial_investment` |
| `partnerships` | `annual_investment` |
| `plants` | `capacity_units`, `contract_mfg_volume` |
| `platforms` | `committed_cost` |
| `talent` | `rd_headcount`, `commercial_headcount`, `operations_headcount`, and the three matching `*_training_budget` fields |

Seven more accepted a negative value but were masked in the first probe because
another field in the same payload failed first — five on `marketing`
(`channel_digital_pct`, `channel_traditional_pct`, `channel_trade_pct`,
`distribution_investment`, `sales_team_count`) and two on `rd`
(`calculated_cost`, `target_level`). A guard that depends on a neighbouring
field failing is not a guard, so they are covered too, along with
`SourcingAllocation.volume_commitment_units`: **21 fields in total**.

The money fields most people would think of first — `rd_budget`,
`marketing_budget`, `strategy_budget`, `retail_price`, `promotion_budget`,
`production_volume`, `demand_estimate`, `new_debt` — all have explicit
`validate_<field>` guards and refuse negatives. The twelve above are the ones
nobody wrote a guard for.

`core/engine/costs.py` adds several of them straight into `strategy_expense`:

```python
strategy_expense += esg.environmental_investment + esg.social_investment
strategy_expense += p.annual_investment
```

A negative value there is not a smaller cost; it is income. Whether the engine
actually pays it out is a question for the engine, not for the source — see the
value-loop probe result in the completion report.

## 3. Two defences, and what each one covers

V2-018 is closed by two separate mechanisms, because they cover different
things and neither covers both.

### API prevention — the value cannot enter

`core/serializers/decision_limits.py` holds one table of the fields that cannot
be negative. A mixin attaches the rule at field level, so each field reports its
own refusal and a payload with two bad fields names both. Both write surfaces
use the same serializer classes, so both enforce it; **21 fields** are covered
(13 that accepted a negative cleanly, 7 that were masked in the first probe by
another field failing first, and 1 supply-chain field).

A test fails if the table names a field a serializer does not have, or if a
named field has no guard attached. The contract tests fail against the
pre-repair serializers.

### Engine fail-closed defence — the value cannot be scored

Validation covers the supported APIs. It says nothing about a row already in
the database: a data migration, an import, the admin, `manage.py shell` or a
restore can write one, and the engine scores rows rather than payloads.

`_run_phase_1` now applies the same table to the persisted decisions before any
competitive mutation, and raises `InvalidPersistedDecisionError` naming the
model, row id, submission and field. It **refuses; it does not clamp**. A
clamped value is a team's submitted decision quietly replaced with a different
one and scored as though it were theirs — wrong, and invisible. The refusal
happens before `processing_status` is set, so no result rows, no partial
scoring, and no round left mid-flight.

`InvalidPersistedDecisionError` subclasses `RoundNotReadyError`, so existing
callers keep reporting it as an actionable 400: like an unlocked team, it is
something an operator corrects and retries.

Five focused tests cover it, and all five fail with the precondition removed.

### One check found a bug in itself

The scanner reports a model it cannot scope rather than skipping it, on the
grounds that an unscannable table is an unchecked table and silence would read
as "no violations". The first version passed the filter dictionary positionally
instead of as keyword arguments, so *every* model was unscannable — and that
choice turned a silent no-op into a loud, obviously wrong refusal that named
nine models at once. Had it skipped quietly, the precondition would have
scanned nothing and passed.

## 3b. The two write surfaces cover different decision sets

API uniformity only means anything for fields both endpoints accept.

| Reachable only per-type (PATCH) | Reachable only whole-submission (PUT) |
|---|---|
| `talent` | `compliance_investments`, `research_allocations`, `talent_allocations`, `team_notes` |

`talent` is not a field of `DecisionSubmissionSerializer`, so a `talent` key in
that payload is ignored rather than validated. A test asserts it is ignored and
not stored — silent acceptance would be the dangerous outcome.

## 3c. The duplicate R&D divergence was filed in error

Recorded because the mistake is instructive. The check compared
`DecisionSubmissionSerializer` with `DecisionRDInvestmentSerializer` and
reported the result as "the API accepts". It never made a request, so it could
not see that `DecisionPartialUpdateView` calls the cross-row rule itself — it
has since `86c2ad4`. Both endpoints always refused the duplicate, and
API-level tests confirm it by passing unchanged against the pre-repair code.

Before it reached even that state it reported "no divergence" twice, for two
different wrong reasons: an unavailable platform/feature pair, then missing
`team` and `round` fields that stopped DRF calling `validate()` at all.

What was real is narrower and is not an exploit: the rule lived in two places,
so a third caller using `DecisionRDInvestmentSerializer(many=True)` directly
would have missed it. It now lives in `DecisionRDInvestmentListSerializer` and
runs wherever the rows arrive together. The API-level regression and control
tests are kept.

## 4. What the scoring function rewards

Read from `core/engine/performance.py` to aim the optimizer, and to be tested
rather than asserted.

`PI_WEIGHTS`: market `0.30`, capability `0.25`, financial `0.15`,
stakeholder `0.15`, resilience `0.15` — **70% of the index is non-financial.**

`_strategic_capability_component` (0.25 of the index) is:

```python
rd_score = rd_spend / rd_budget          # a ratio of your spend to your own budget
product_score = 1 if any product action else 0.45
strategy_score = 1 if any market entry/plant/partnership/acquisition/ESG else 0.45
```

`rd_score` is self-referential and clamped to 1. A team declaring a $1 R&D
budget and spending $1 scores exactly what a team spending $10M against a $12M
budget scores — 1.0 versus 0.83, in the small team's favour. `strategy_score`
counts `hasattr(submission, 'esg')`: the presence of an ESG row, whatever it
says.

Two anti-exploit guards already exist — `_is_voluntarily_commercially_inactive`
(caps the composite at 0.25) and `_enforce_zero_revenue_invariant` (keeps a
zero-revenue firm below the lowest revenue-positive firm). Both are written
against **zero** revenue. Selling a single unit is outside both.

These are hypotheses with a mechanism, not findings. They are what the optimizer
is pointed at.
