# Repairing the standing red tests — V2-071 / V2-074 — 2026-09-12

**Branch:** `crv2-repair-standing-red-tests`, cut detached from
`crv2-release-integration` at `e1b744c`
**Scope:** the seven pre-existing failures V2-074 registered and did not repair
**Worktree:** isolated; the main checkout, other worktrees and every other
builder's file were untouched. Nothing was pushed.

## Lead: none of the seven is a product defect

Every one of the seven is a test that outlived the rule or the shape it was
written against. The product is right in all seven cases, and that is asserted
from evidence rather than from the fact that the repairs went in easily:

- **The four R10 failures.** `_strategic_capability_component` does exactly what
  R10 requires — it reads no `DecisionRDInvestment.amount`, and the comment
  block where the term used to be says so. The number the four tests tripped on,
  `0.450`, is the *correct* earned score for a fixture that takes no scored
  action: `(0.45*0.30 + 0.45*0.30) / 0.60`. The tests asserted `0.6700`, which
  is that same score with the retired R&D term still contributing.
- **The two reference-price errors.** The engine refused those rounds because
  the fixture had built a state the game forbids — one team holding five
  non-retired platforms of a single generation. The refusal is the
  one-platform-per-generation rule working, and it fired *before* any
  competitive write, which is the very property those tests exist to assert.
- **The narrative error.** The 403 is correct and the test's status assertion
  passed; it failed one line later, on the response *class*. This was the one
  with a genuinely dangerous alternative reading — a 403 that still carried the
  narrative payload would have been a disclosure defect — so it was checked
  rather than assumed. `GameScopeGuardMiddleware` returns
  `{'error', 'request_id'}` and nothing else, and the repaired test now proves
  that against the real body.

No finding is opened for the product. Two are opened for the record: see
**Findings to register**.

## The seven

| # | Test | Classification | What it asserted before | What it asserts now |
|---|---|---|---|---|
| 1 | `test_scoring_dispositions.RdSpendTargetTests.test_a_dollar_against_a_dollar_no_longer_earns_full_credit` | **Stale expectation (R10)** | The V2-021 exploit is closed *by degree*: $1-against-$1 scores strictly **less** than a $2,000,000 programme (`assertLess(exploit, honest)`). | The exploit is closed *outright*: the amount is never read, so $1-against-$1 scores **equal** to the honest programme and **equal** to spending nothing. Same exploit, same fixture, the stronger rule. |
| 2 | `test_scoring_dispositions.RdSpendTargetTests.test_zero_spend_earns_zero_for_the_rd_term` → renamed `test_no_amount_of_spend_earns_capability` | **Stale expectation (R10)** | Zero spend scores strictly less than spend at target — i.e. the R&D term exists and rewards the amount. | No amount earns capability: `0`, `1`, `500,000`, `50,000,000` and no row at all all score identically. The name changed because the old one named the retired term. |
| 3 | `test_staffing_adequacy.TheRule.test_staffing_at_each_optimum_preserves_capability` | **Stale expectation (R10), amount only** | A staffing factor of exactly 1 passes the earned score through: `capability == 0.6700`. | The identical claim at the correct earned score: `capability == 0.450`. The V2-025 rule under test is untouched — only the score the factor multiplies moved, and the derivation is written into the test. |
| 4 | `test_staffing_adequacy.RDStillMatters.test_actual_rd_spend_still_moves_capability` → class renamed `SpendNoLongerMovesCapability`, test renamed `test_rd_spend_no_longer_moves_capability` | **Stale expectation (R10)** | Two claims at once: R&D spend still moves capability, **and** the staffing factor scales the score rather than flattening it. | The first inverted (none, half and full spend are now equal), the second **kept and strengthened** in a new sibling test — see *Coverage* below. |
| 5 | `test_reference_price.ConfigurationFailsClosed.test_resolution_refuses_before_any_competitive_write` | **Fixture defect** (not a rule change, not a product defect) | Phase 1 refuses a missing reference price before any competitive write. | Unchanged — the test now *reaches* that refusal. The fixture gave every platform the same generation, so `alone` held five non-retired platforms of one generation and the engine refused the round on that stored state first. Each platform now gets its own generation. |
| 6 | `test_reference_price.ElasticityConfiguration.test_resolution_refuses_before_any_competitive_write` | **Fixture defect** | Phase 1 refuses an out-of-range elasticity before any competitive write. | Unchanged; same fixture repair, same shared `ReferencePriceFixture`. |
| 7 | `test_durable_narratives.NarrativeStatusEndpointTests.test_an_unrelated_instructor_is_refused` | **Stale expectation about response shape** | A non-owning instructor is refused 403 and the response body carries no `narratives` key — read via DRF's `response.data`. | The same two claims, read from the body the caller actually receives (`response.json()` and `response.content`). Authorization moved ahead of the view into `GameScopeGuardMiddleware` (the V2-034 repair), and a middleware refusal is a plain `JsonResponse` with no `.data`. |

**None obsolete, none deleted.** Every one of the seven had a subject that still
exists, so no deletion was justified and none was made.

### Why 3 of 7 were errors rather than failures

As the handoff anticipated, an error is not automatically either category.
Diagnosed: #5 and #6 are a **fixture** problem (the test's own setup builds an
illegal game state), and #7 is a **shape** problem (the assertion uses an API
the response no longer has). Neither is an environment problem, and neither is a
product defect. Only #7 needed the product checked to rule a defect out.

## Coverage: what changed besides the seven

Repairing #4 would have silently destroyed a real claim, so it did not.
`RDStillMatters` asserted two things, and only one of them died with R10: that
the staffing factor **scales** the earned score instead of flattening it. Under
R10 that claim is not merely still true, it is load-bearing — a factor
multiplying a constant is indistinguishable from a working rule, and every
equality in the repaired class would pass against a `_strategic_capability_component`
that returned a constant. Two controls were added to prevent exactly that
vacuity, mirroring the pattern `test_rd_scoring_retired` already established
for the same reason:

- `test_staffing_adequacy.SpendNoLongerMovesCapability.test_the_factor_still_scales_a_score_that_can_move`
  — a scored action (platform development, which is what R10 left standing
  where spend used to be) must still move the component, and zeroing the pools
  must still take the larger score to zero.
- `test_scoring_dispositions.RdSpendTargetTests.test_the_component_can_still_move`
  — the same control for the equalities in that class.

This is why the focused count rose from 92 to 94. No coverage was lost.

## Commands

All runs used `backend/scripts/test-postgres <labels>` under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`, each in its own disposable
PostgreSQL 16 container. The production database was never contacted and no
systemd environment file was read. The full backend suite was **not** run —
GSP-CRV2-09 owns it.

| # | What | Result | Suite time | Wall |
|---|---|---|---|---|
| 1 | `checks/bin/run-checks --fast` (hook probe) | `rc=0`, 2 checks ran, 0 blocking failures | — | ~2 s |
| 2 | Baseline, 4 affected modules | `Ran 92 tests`, **FAILED (failures=4, errors=3)**, `rc=1` | 21.966 s | 34 s |
| 3 | Same 4 modules, after an incomplete edit | `Ran 94 tests`, **FAILED (errors=22)**, `rc=1` | 21.541 s | 34 s |
| 4 | Same 4 modules, after the fix | `Ran 94 tests`, **OK**, `rc=0` | 22.341 s | 36 s |
| 5 | Final pass, 9 modules | **`rc=0`** — summary line not captured | — | 205 s |
| 6 | Final pass, 9 modules, output captured | `Ran 132 tests`, **OK**, `rc=0` | 25.988 s | 38 s |

Run 2 reproduces V2-074's exact seven on this branch — the same four failures
and three errors, same names, same values — so the repairs were made against a
reproduction rather than against the register's description of one.

**Run 3 was my own error and is recorded rather than hidden.** A `replace_all`
edit missed two `platform_generation=generation` references whose line shape
differed, and 22 tests failed on the resulting `NameError` in `setUp`. Fixed and
re-run as run 4.

**Runs 5 and 6 are the same command twice, and that is a deviation.** The
handoff allows one final pass. Run 5 passed (`rc=0`), but `test-postgres` emits
scenario-loading output after the unittest summary, so the count and duration
scrolled out of the captured tail. Run 6 repeated it with output redirected to a
file. It was re-run to obtain a number I could evidence, not to see whether a
failure would flake — no failure had occurred. The log is at
`scratchpad/final_pass.log`.

Final pass modules: the four repaired, plus `test_rd_scoring_retired` (the
canonical R10 suite), `test_rd_ordering` (the precedent repair at `6ea59a7`),
`test_cc17_narratives`, `test_game_scope_boundary` (the guard behind #7) and
`test_refusal_audit`.

## Change surface

```
backend/core/tests/test_durable_narratives.py   | 12 ++-
backend/core/tests/test_reference_price.py      | 26 +++++--
backend/core/tests/test_scoring_dispositions.py | 97 ++++++++++++++++++++-----
backend/core/tests/test_staffing_adequacy.py    | 84 ++++++++++++++++++---
4 files changed, 185 insertions(+), 34 deletions(-)
```

**Test files only. No runtime code was changed** — which is the expected shape
when all seven are stale tests, and would have been the wrong shape if any had
been a defect. None of the files other builders hold (`core/views/decisions.py`,
the serializers, `core/views/course.py`, `core/views/core.py`,
`core/engine/bootstrap.py`, `core/services/route_inventory.py`) was opened for
writing.

## Commit verification — `--no-verify`, for a different reason than stated

The handoff sanctioned `--no-verify` because `checks/.aide-checks-rev` is
absent, leaving `run-checks` no vendored revision to compare. **The conclusion
holds but the premise does not.** The file is present (8 bytes, revision
`e710f26`), and the hook fails on the opposite problem — a vendored revision
that *mismatches the runner*:

```
run-checks: ERROR revision mismatch — could not run.
run-checks: runner built from : e1b744c
run-checks: repo vendored at  : e710f26
run-checks: a stale runner reports PASS for checks it does not carry. That is a false
            pass, not a pass, so this is exit 2 in every mode including --report-only.
```

That is a **could-not-run**, not a failing check: `run-checks` refuses to
report a pass it cannot stand behind. Re-vendoring is out of scope, and the
hook's own header sanctions the bypass — *"Bypassable with `--no-verify`; the
deploy gate is the layer that is not."* So the commit was made with
`--no-verify`, and the checks were not executed against it.

**A discrepancy worth someone's attention, which I could not resolve.** Invoked
directly with the same arguments the hook uses, earlier in this session, the
same runner reported `revision e710f26 matches …` and exited `0`. Invoked by
the hook it reports the mismatch above and exits `2`. I did not chase the cause
— it is in the checks tooling, not in this repair — but *a gate that answers
differently depending on how it is called is a gate nobody can read*, which is
the same shape as the finding this whole handoff exists to clean up.

## Findings to register

Not written to `V2_FINDINGS_REGISTER.md` — handed over for the register's owner.

### V2-074 — disposition

> **Repaired** on `crv2-repair-standing-red-tests`. All seven were classified by
> reproduction (`Ran 92 tests, FAILED (failures=4, errors=3)` on this branch,
> V2-074's exact set) and repaired **to the rules now in force**, not to the
> rules they were written against. **None was a product defect**, and that was
> established rather than assumed — most pointedly for the narrative endpoint,
> where the alternative reading was a 403 leaking its payload; the refusal body
> is `{'error', 'request_id'}` and the repaired test asserts it against the real
> response. Four were R10 staleness, two were a fixture that built a state the
> one-platform-per-generation rule forbids, one asserted DRF's `.data` on a
> refusal that V2-034 moved into middleware. Two vacuity controls were added so
> the new equality assertions cannot pass against a constant. Final pass:
> `Ran 132 tests in 25.988s, OK`, over the four repaired modules and five
> siblings. Runtime code unchanged.

### New — proposed

| ID | Area | Severity | Finding | Reproduction | Status |
|---|---|---|---|---|---|
| *(next)* | Verification quality | **P2** | **Two green tests in `RdSpendTargetTests` assert rules R10 retired, and pass vacuously.** `test_spend_at_or_above_the_target_caps_at_one` asserts spend "caps at one" — a cap on a term that no longer exists — and `test_equal_spend_scores_equally_whatever_budget_was_declared` asserts an equality that is now trivially true for every pair of amounts. Both pass, so neither appeared in V2-074's count: *a stale test that happens to stay green is invisible to the process that found the other seven.* They are also now subsumed by `test_no_amount_of_spend_earns_capability`, which asserts the same equality across five amounts deliberately. | Read both at `crv2-repair-standing-red-tests`; every reading they compare returns `0.450`. | **Open, not repaired.** P2 under the register's rule — it cannot change a published result. Deleting or renaming a *green* test is a claim of its own and was outside this handoff's remit, which was the seven red ones. Recommend the scoring owner delete both. |

**Not raised as findings, but noted:** V2-074's own text and
`RELEASE_INTEGRATION_2026-09-12.md` §5 cite `test_staffing_adequacy.RDStillMatters`
and `test_zero_spend_earns_zero_for_the_rd_term` by name, and both names have
changed here. Those are historical records of a measurement that was true when
made, so they are correct as written and were not edited; this document is the
forward pointer.

## What I could not determine

- **Why the hook was expected to fail.** `.aide-checks-rev` is present and
  `run-checks` passes here. I could not reproduce the failure the handoff
  describes, and did not go looking for it in other worktrees.
- **Whether `scenario_rd_spend_target` should survive.** V2-053 left it as an
  orphaned fail-closed guard with no consumer and flagged it as the one item
  worth an owner's decision; that is still true, and two tests in
  `RdSpendTargetTests` still cover the guard itself. Untouched — it is a rules
  decision, not a test repair.
- **The other three V2-071 tests** (`test_rd_ordering` ×2, the route inventory)
  were already repaired on `crv2-release-integration` and are green in the final
  pass. Nothing here changes them.
