# GSP-CRV2-10 Stage 3A fourth re-audit — FAIL / CANDIDATE INVENTORY REWORK 4

Audited runtime revision: `f39b853`
Audited checkpoint revision: `c20bd8b`

## Binary decision

**FAIL / REWORK. Do not begin Stage 4.**

The V2-045 aggregate-funding repair passes its stated case. The checkpoint
artifacts verify, runtime under `backend/` matches `f39b853`, and an independent
run of `AggregateFundingTests` passed 4/4 against the separately named
`test_gsp_crv210_stage3a_audit4` database under the host runner lock. Two
$1,000,000 generations against $1,500,000 now select and book one platform in
both accounting modes, and the remaining carried draft can fund later.

The refactor introduced a different candidate-inventory regression: two
development rows for the **same generation** are both collected before either
creates a `TeamPlatform`. Both can therefore be funded, created and charged.

## Blocking defect — duplicate requests now create duplicate platforms

Before `f39b853`, `_process_platform_development()` created each platform
inside the decision loop. The next row re-ran the existing-platform query,
observed the platform just created for that generation and skipped the row.

At `f39b853`, `new_requests` is fully collected first. Its existing-platform
query sees the same pre-loop database state for every row. Two rows naming one
generation are both appended, both passed to `allocate_platform_funding`, and
both created afterwards. Neither `DecisionPlatformDevelopment` nor
`TeamPlatform` has a uniqueness constraint for this invariant.

This is reachable through a supported write surface, not only through an ORM
bypass. An independent per-type `PATCH` submitted two rows with the same
`platform_generation` and different names. The response was **200** and both
rows persisted:

```text
status 200
persisted [('Duplicate A', Decimal('1000000.00')),
           ('Duplicate B', Decimal('1000000.00'))]
```

Processing the equivalent stored pair with $3,000,000 opening cash produced:

```text
same_generation_decisions 2
same_generation_platforms [('Duplicate A', 'in_development', 1),
                           ('Duplicate B', 'in_development', 1)]
booked_rd_expense 2000000.00
```

The API sample used `test_gsp_crv210_stage3a_audit_dupapi2`; the lifecycle and
accounting sample used `test_gsp_crv210_stage3a_audit_dup`. Both ran under
`/tmp/globalstrat-backend-test.lock` and were removed by their test runners. No
full suite or release-scale harness was run.

The cash allocator is internally consistent in this case—it reserves and
books both $1,000,000 prices—but it is allocating over the wrong candidate
inventory. This creates two live copies of a generation where the engine's
existing rule and the refactor's own comment say a team already holding that
generation makes a later request ineligible. It also charges the team twice
for a state the previous runtime created once.

## Required rework

1. Make one platform-generation request per team/submission an explicit
   cross-row rule, enforced identically on the per-type and whole-submission
   write surfaces. A refusal writes none of the replacement payload.
2. Add the same fail-closed check at the Phase-1 persisted-decision boundary.
   An ORM-inserted duplicate pair must refuse before any `TeamPlatform`, result
   or accounting mutation. Do not silently discard one row: the stored
   decision and the resolved decision would then disagree.
3. Reconcile the allocator's candidate inventory independently of API
   validation, so a generation appears at most once among new candidates and
   cannot appear as both a carried draft and a new request. Keep the documented
   carried-draft-first, generation/name/id ordering for otherwise distinct
   candidates.
4. Add positive controls proving two distinct generations still allocate as
   V2-045 specifies and that a later request for a genuinely retired generation
   retains the intended existing behavior.
5. Keep the actual accounting assertion: a refused duplicate pair books zero;
   a corrected single request creates one platform and books its one
   authoritative price.
6. Register this regression as V2-046. Keep V2-039, V2-040, V2-044 and V2-045
   implemented-pending-closure; Stage 3 remains open.

## Verification budget

- Focused duplicate-generation API/precondition tests, aggregate funding tests,
  and directly affected platform lifecycle/accounting tests only.
- One independent duplicate-generation negative sample at preflight.
- `makemigrations --check --dry-run`, `git diff --check`, clean-tree and
  checkpoint checksum verification.
- No full suite, browser, determinism, concurrency, load, tournament, or Stage
  4 work.

## Acceptance for re-audit

Stage 3A passes when duplicate-generation rows are refused on both supported
writes and at the real Phase-1 boundary before mutation; the allocator cannot
create two live platforms for one team/generation even when rows bypass the
API; distinct-generation aggregate funding still obeys V2-045 in expense and
capitalisation modes; and the frozen checkpoint evidence matches those claims.
