# GSP-CRV2-10 Stage 3A fifth re-audit — FAIL / HELD-STATE REWORK 5

Audited runtime revision: `9987688`
Audited checkpoint revision: `f878ab6`

## Binary decision

**FAIL / REWORK. Do not begin Stage 4.**

The new V2-046 checks work for duplicate decision rows in the current
submission. The checkpoint artifacts verify, runtime under `backend/` matches
`9987688`, and an independent run of `DuplicateGenerationTests` passed 8/8
against `test_gsp_crv210_stage3a_audit5` under the host runner lock. Both
writes refuse a same-submission pair, Phase 1 refuses an ORM-inserted pair, and
the allocator defensively selects only one of those new requests.

The claimed one-platform-per-generation invariant is still incomplete in two
adjacent states: a carried duplicate draft is never reconciled against another
platform the team already holds, and a supported write accepts a new request
for an already-held generation which the engine later discards silently.

## Blocking defect 1 — an upgrade residue is promoted into a second live platform

`_process_platform_development()` adds **all** carried `unfunded_draft` rows to
the candidate list before it builds `held`. The `held`/`claimed` sets filter
only `new_requests`; they never reconcile one draft with another non-retired
platform of the same generation.

This is not a hypothetical corrupt state. Runtime `f39b853`, the immediately
preceding V2-045 implementation, could create it from the supported duplicate
rows V2-046 documented: with enough cash for only one price it created one
`in_development` platform and one `unfunded_draft` for the same generation.
Checkpoint `f878ab6` supplies no upgrade scan, migration or precondition for
those rows.

Independently reproduced with one active platform and one legacy draft for the
same team/generation, then $1,500,000 cash against a $1,000,000 price:

```text
before [('Already Live', 'active', 0), ('Legacy Draft', 'unfunded_draft', None)]
after [('Already Live', 'active', 0), ('Legacy Draft', 'in_development', 2)]
nonretired_same_generation 2
booked_rd_expense 1000000.00
```

The repair therefore prevents a duplicate pair of *new request rows* from
creating two platforms, but the allocator can still create two live platforms
for one generation by promoting a carried draft beside one already held. That
does not meet rework 4's acceptance.

## Blocking defect 2 — a request for an already-held generation is accepted and ignored

The cross-row serializer rule compares rows only with other rows in the
incoming payload. It does not compare them with the team's non-retired
platforms. The persisted Phase-1 rule likewise finds only duplicate rows in
one submission.

An independent per-type `PATCH` requested a generation for which the team
already had an active platform. The supported write returned **200** and
persisted the authoritative $1,000,000 request. The lifecycle then skipped it
through `held`, created nothing and booked zero:

```text
status 200
persisted_request ('Second Live', 1, Decimal('1000000.00'))
nonretired_platforms [('Already Live', 'active')]
booked_rd_expense 0
```

The allocator preserves state here, but only by silently replacing the stored
decision with no decision at all. That is the failure shape the handoff's
fail-closed rules explicitly reject. This existing write/engine gap is
registered as V2-047.

The carried-state sample used `test_gsp_crv210_stage3a_audit_legacydup`; the
supported-write sample used `test_gsp_crv210_stage3a_audit_heldapi`. Both ran
under `/tmp/globalstrat-backend-test.lock` and were removed by the custom test
runner. No full suite or release-scale harness was run.

## Required rework

1. Inventory duplicate non-retired `TeamPlatform` rows by team and generation
   before designing the upgrade behavior. Include the candidate database or an
   isolated production-shaped clone; do not infer absence from model code,
   because no database constraint prevents the state.
2. Make Phase 1 fail closed when existing non-retired platform state contains
   more than one row for a team/generation. Name every conflicting row and do
   not silently delete, retire or merge competition state.
3. Reconcile carried drafts against the other non-retired platforms before
   allocation. A duplicate draft must not start, acquire a funding/start round,
   or be booked. The Phase-1 refusal is the supported recovery signal; the
   allocator guard remains a defence, not a silent repair.
4. Refuse a new development request for a generation the submitting team
   already holds as active, in development or unfunded draft, on both write
   surfaces. Validate before replacement so the previously accepted payload is
   unchanged on refusal. Preserve the explicit retired-generation exception.
5. Add the same held-generation check to the persisted Phase-1 boundary. A
   single ORM-inserted request against an existing non-retired platform must be
   refused before platform, result or accounting mutation rather than silently
   ignored.
6. Cover at minimum active-plus-draft and two-draft upgrade residues, both
   supported writes against an already-held generation, the stored-row bypass,
   unchanged replacement data, zero accounting on refusal, and the retired
   positive control. Keep the existing V2-045 and V2-046 controls.
7. Record V2-046 as incomplete at `9987688` until the carried-state acceptance
   passes. Register V2-047 before repair. V2-039, V2-040, V2-044 and V2-045
   remain implemented-pending-integrated-closure; Stage 3 remains open.

## Verification budget

- Focused held/duplicate-generation API, Phase-1, allocator, lifecycle and
  accounting tests only, plus the existing V2-045/V2-046 controls.
- One independent production-shaped duplicate-state/held-request sample at
  preflight.
- `makemigrations --check --dry-run`, `git diff --check`, clean-tree and
  checkpoint checksum verification.
- No full suite, browser, determinism, concurrency, load, tournament, or Stage
  4 work.

## Acceptance for re-audit

Stage 3A passes when an upgrade from the faulty predecessor cannot promote a
duplicate draft; invalid existing platform state and stored held-generation
requests refuse before mutation; both write surfaces reject already-held and
same-payload duplicate generations atomically; retired generations remain
re-buildable; V2-045's aggregate allocation still holds in both accounting
modes; and the frozen checkpoint evidence matches those claims.
