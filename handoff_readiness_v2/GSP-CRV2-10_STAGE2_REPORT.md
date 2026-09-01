# GSP-CRV2-10 Stage 2 — one authoritative price, one calculator

**Freeze revision `75503cf`.** Runtime committed before any evidence was
generated; the evidence run refuses a dirty tree and ran against a disposable
database at that revision.

Closes **V2-037** (P0) and **V2-038** (P1).

## The rule

The cost a team is shown is the cost the server computes, and the cost the
server computes is the cost it charges. Not two functions kept in step by hand
— one function with two callers.

`core/services/rd_costs.py` is that function. Platform cost comes from
`PlatformGenerationDefinition` keyed on `method`: `development_cost` for
`in_house`, `license_cost` for `license`. Feature cost sums the same
`FeatureLevelCost` rows the R&D screen already displayed;
`RDContextView._build_cost_schedule` now delegates to the service, so the
display path and the charge path read one table through one code path.

## Demonstrated, not asserted

Evidence: `evidence/decision-rules/stage2-authoritative-cost.json`.

| Behaviour | Per-type `PATCH` | Whole submission `POST` | Result |
|---|---|---|---|
| Cost omitted | 200 | 201 | both stored at **15,000,000.00**, the authored figure |
| Cost matches authored | 200 | 201 | stored unchanged at 15,000,000.00 |
| Cost disagrees | **400** | **400** | refused, authored figure named, **nothing persisted** |

The refusal text, verbatim:

> `committed_cost was submitted as 0.00, but this scenario prices it at
> 15,000,000.00. The server sets the price; correct the submission or leave the
> field out.`

Never silently corrected. A submitted decision quietly replaced with a
different one looks ordinary afterwards, which is exactly what made V2-037
invisible for as long as it existed.

## One service, five callers

Asked for the same platform, five ways, and compared — `all_agree: true`:

| Caller | Figure |
|---|---|
| Scenario's authored `development_cost` | 15000000.00 |
| `rd_costs.platform_development_cost` | 15000000.00 |
| What the engine precondition compares against | 15000000.00 |
| The stored `committed_cost` | 15000000.00 |
| The budget rule's platform-development line | 15000000.00 |
| Display schedule vs service schedule | identical |

If the display path ever drifts from the charge path, `all_agree` goes false;
the flag is computed from the figures rather than written by hand.

## The engine boundary

A stored row was edited behind the API to `committed_cost: 0`, as an admin
edit, a shell or a restore would, then the round was driven through the real
close / process / advance controls.

- `process` → **400**: *Round 2 cannot be scored: 1 stored R&D cost(s) disagree
  with the price this scenario authors. Correct the row(s) and retry.*
- The refusal names the row: `DecisionPlatformDevelopment #3 (Apex Devices):
  committed_cost stored 0.00, authored 15000000.00 — Gen 2 by in_house is
  priced at 15,000,000.00`
- **Financial rows before and after: 0 and 0.** The refusal lands before any
  competitive mutation, not as a rollback afterwards.

Shape borrowed from V2-018's guard deliberately: name the model, row, field,
stored value and authored value, so a refusal says which row to correct.

## V2-038 — the budget rule that platform development escaped

`budget_assessment` is now the single answer to "can this team afford what it
has committed?". It counts platform development, which no previous check did,
and it replaced three copies that disagreed: `views/decisions.py:548` and
`:888` summed three budget lines, `:1015` summed four by including
`research_budget`, and none counted platform development. Three rules that
disagree is one rule that does not exist.

## A defect an existing contract test caught

The first cut asked whether a level was *priced* before asking whether it was
*reachable*. All three shipped scenarios author four ceiling rows at `0.00` —
`ai_features`, `connectivity` and `iot_integration` on Gen 1, `connectivity` on
Gen 2 — with no level prices, because a ceiling of zero means the feature does
not exist on that generation. That is correct authoring.

Shipped as first written, a student targeting one of those features would have
been refused with *"author the missing FeatureLevelCost rows"* — blamed for a
configuration fault that is not one. The ceiling is now checked first, so an
unreachable feature is refused as unreachable, and only a genuinely
unpriced-but-reachable level is reported as a configuration problem.

The contract fixture did also need its prices authored — ceiling 10, no prices,
so it genuinely could not quote one — but that was the smaller half.

## Verification

- `core/tests/test_rd_costs.py` — **15 tests**, new
- Directly affected contract tests — `test_decision_limits`,
  `test_product_name_uniqueness`, `test_auth_rounds`, `test_permissions` —
  **116 passing in total**
- No full suite, no load, concurrency, determinism, browser or drill run

## Changed files

`core/services/rd_costs.py` (new), `core/serializers/decisions.py`,
`core/views/decisions.py`, `core/engine/advance_round.py`,
`core/tests/test_rd_costs.py` (new), `core/tests/test_decision_limits.py`
(fixture authors its level prices).

## Carried forward, not addressed here

- **V2-039** — the unlock gate is enforced at lock only, so a team that never
  locks is defaulted at close and the engine builds a generation before its
  unlock round. Stage 3's territory.
- **V2-040** — authored `development_rounds` off by one, and a zero-round
  generation ready in its creation round. Stage 3.
- **V2-044** — the write path accepts another team's platform; the lock refuses
  it. The same shape as V2-039.
- **V2-041, V2-042, V2-043** — Stages 5, 6 and the retirement fix.

`method` now changes the price. Whether it also changes lead time is Stage 3's
question, per the handoff.
