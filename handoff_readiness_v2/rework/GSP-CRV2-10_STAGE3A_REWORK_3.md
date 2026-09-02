# GSP-CRV2-10 Stage 3A third re-audit — FAIL / FUNDING ALLOCATION REWORK 3

Audited runtime revision: `a713349`
Audited checkpoint revision: `f81426c`

## Binary decision

**FAIL / REWORK. Do not begin Stage 4.**

The focused-proof requirements from rework 2 now pass. The revised tests read
`rd_expense` and `platform_capex` from the real
`calculate_operating_expenses` output, the report no longer claims a cash
observation, the submitted evidence hashes reconcile, and the transcript
records a clean runtime tree at both ends. An independent run of
`FundingAccountingTests` passed 4/4 against the separately named
`test_gsp_crv210_stage3a_audit` database under the host runner lock.

The independent adversarial sample exposed a different blocker: funding is
decided one platform at a time against the same, unreserved cash balance. The
checkpoint therefore proves that a selected platform is booked in its
`funded_round`; it does not prove that all platforms labelled funded in that
round could be funded together.

## Blocking defect — two drafts spend the same cash

`rd_costs.can_fund_platform()` compares one platform's authored price with
`team.cash_on_hand`. Both loops in `_process_platform_development()` call that
boolean independently. Neither loop reserves the price accepted for an
earlier platform or reduces the balance available to the next candidate.

Reproduced at `f81426c` with the production lifecycle and accounting functions:

- create two in-house platforms authored at $1,000,000 each while the team has
  $100; both correctly remain `unfunded_draft` in round 1;
- set round-2 opening cash to $1,500,000 and process the two drafts in the
  existing deterministic name order;
- both become `in_development`, both receive `funded_round=2`, and both clocks
  start;
- run `calculate_operating_expenses` for round 2; its actual `context.opex`
  output books `rd_expense=2,000,000` against opening cash of $1,500,000.

Observed output:

```text
round1 [('Audit P20', 'unfunded_draft', None), ('Audit P21', 'unfunded_draft', None)]
round2 [('Audit P20', 'in_development', 2), ('Audit P21', 'in_development', 2)]
opening_cash 1500000.00 booked_rd_expense 2000000.00 affordable False
```

The sample used database `test_gsp_crv210_stage3a_audit_multi` under
`/tmp/globalstrat-backend-test.lock`; the disposable test database was removed
by the test runner. No full suite or release-scale harness was run.

This violates the Stage-3 rule that a platform the team cannot fund remains an
unfunded draft. It also reopens the cash side of V2-038 inside the new
auto-funding path: the API's aggregate submission check cannot protect carried
drafts, and persisted rows must not be able to make the lifecycle spend the
same opening cash more than once.

## Required rework

1. Replace the per-row affordability decisions with one deterministic,
   per-team/per-round allocation over every new platform and carried draft
   considered for funding. An accepted platform's authoritative cost must be
   reserved before the next candidate is considered.
2. State the priority between new requests and carried drafts. Whichever rule
   is adopted must be deterministic; candidates that do not fit the remaining
   funding stay `unfunded_draft` with no funded/start round and no running
   clock.
3. Keep lifecycle selection and accounting on one authoritative set of funded
   platforms. Do not add a second approximate cost calculation or silently
   lower a price.
4. Add a focused two-draft test at the real lifecycle/accounting boundary:
   with two $1,000,000 drafts and $1,500,000 opening cash, no more than one may
   start or be booked. After enough funding arrives in a later round, the
   remaining draft may start and must be booked exactly once in that later
   round. Assert both platform state and actual `context.opex` values.
5. Add the corresponding same-round multi-request control, including a row
   inserted outside the supported API, so aggregate safety does not depend on
   the serializer having run. Cover expense and capitalisation modes without
   duplicating the whole lifecycle matrix.
6. Correct the stale `FundingAccountingTests` class docstring: it still says
   the test records cash, although the checkpoint correctly says it does not.
7. Keep V2-039, V2-040 and V2-044 implemented-pending-closure. Register this
   defect as V2-045 and leave Stage 3 open.

## Verification budget

- Focused platform funding/lifecycle/accounting tests and the directly affected
  authoritative-budget tests only.
- One independent aggregate-funding adversarial sample at preflight.
- `makemigrations --check --dry-run`, `git diff --check`, clean-tree and
  checkpoint checksum verification.
- No full suite, browser, determinism, concurrency, load, tournament, or Stage
  4 work.

## Acceptance for re-audit

Stage 3A passes when no set of platform transitions can book more authoritative
platform cost than the funding available to that set; unfunded candidates keep
null funding/clock fields; each later-funded candidate is booked once in the
round its own clock starts; both accounting modes observe the same selection;
and the checkpoint report, tests and evidence describe only what they prove.
