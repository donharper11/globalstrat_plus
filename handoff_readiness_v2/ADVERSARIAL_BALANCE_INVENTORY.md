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

## 2. Twelve dimensions accept a negative investment

Cleanly accepted — the field itself raised no error:

| Decision type | Field |
|---|---|
| `esg` | `environmental_investment`, `social_investment` |
| `market-entry` | `initial_investment` |
| `partnerships` | `annual_investment` |
| `plants` | `capacity_units`, `contract_mfg_volume` |
| `platforms` | `committed_cost` |
| `talent` | `rd_headcount`, `commercial_headcount`, `operations_headcount`, and the three matching `*_training_budget` fields |

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

## 3. The two API paths do not refuse the same payloads

**Confirmed divergence.** Two R&D investments naming the same platform and the
same feature:

| Path | Verdict |
|---|---|
| `PUT /decisions/round/<n>/` (whole submission) | **rejected** — *"Only one R&D investment per platform feature is allowed in a round."* |
| `PATCH /decisions/round/<n>/rd/` (per type) | **accepted** |

The rule lives in `DecisionSubmissionSerializer.validate()`. The PATCH handler
validates each row with `DecisionRDInvestmentSerializer` on its own and never
runs it, because it is a cross-row rule and PATCH never sees the rows together.

That rule is not cosmetic. Its docstring says why it exists: *"Reject ambiguous
R&D payloads whose result could depend on row order"* — the defect class raised
as V2-012, where an unordered iteration changed a published competitive hash.
The partial endpoint lets a team store exactly the state the full endpoint was
changed to forbid.

### This check reported "no divergence" twice before it measured anything

Worth recording, because it is the failure mode this whole handoff is exposed
to:

1. **First version** picked the first platform and feature it found. Both paths
   rejected the payload — because that feature was not available on the team's
   platform generation. Two refusals for an unrelated reason are indistinguishable
   from agreement.
2. **Second version** used a valid pair, and both paths accepted. `team` and
   `round` are required fields of the submission serializer, and DRF only calls
   `validate()` once every field has validated — so the cross-row rule was never
   reached, and its silence read as approval.

The check now carries a control: a *distinct* platform/feature pair that the
full API must accept. If the control is refused, the check declares itself
inconclusive rather than reporting a result. A probe that cannot distinguish
"allowed" from "rejected for some other reason" is not evidence.

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
