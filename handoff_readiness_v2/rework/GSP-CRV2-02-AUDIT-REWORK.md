# GSP-CRV2-02 audit verdict — FAIL / REWORK

**Audited:** 2026-08-28  
**Scope:** GSP-CRV2-02 fail-closed operator concurrency  
**Decision:** **FAIL / REWORK**

**Execution discipline:** Follow
`handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`. Do not regenerate the
700-race evidence while editing. Complete the inventory, coverage guard and
request-ID tests with one race per new pair; use 10 per pair for preflight;
freeze; then generate the complete final matrix once.

Do not mark V2-004 closed. The new boundary works for the routes that use it,
but active registered legacy routes still bypass it, so it is not the single
boundary claimed by the completion report.

## Blocking defect 1 — active lifecycle routes bypass the boundary

`backend/core/urls.py` still registers:

- `POST /api/rounds/<round_id>/lock/` → `RoundLockView`
- `POST /api/rounds/<round_id>/unlock/` → `RoundUnlockView`
- `POST /api/rounds/<round_id>/extend/` → `RoundExtendView`
- `PUT /api/rounds/<round_id>/schedule/` → `RoundScheduleSetView`
- `POST /api/instances/<instance_id>/bulk-schedule/` → `BulkScheduleView`

Their implementations in `backend/core/views/course.py` do not use
`operator_action()` or the lifecycle advisory lock. They read mutable rows
before any lock and then save them. Specific consequences include:

- legacy unlock can race close/process and leave a legacy lock indicator that
  disagrees with submission/round state;
- legacy extend performs an unlocked read-modify-write and can lose a concurrent
  deadline update or change a processed/closed round;
- schedule and bulk schedule can change competition deadlines while close or
  processing is in flight;
- schedule mutation has no operator audit event at all.

This fails the handoff's explicit instruction to trace legacy routes and the
requirement that every conflicting operator action use one coordination
boundary.

### Required repair

1. Build a route inventory from `backend/core/urls.py` and router registrations,
   not from calls to `operator_action()`. Include every endpoint/command that can
   mutate `Game`, `Round`, participation, submission locks/corrections, event
   state or recovery state.
2. For each legacy route, choose exactly one:
   - remove/unregister it after proving no supported client uses it; or
   - route it through the same lifecycle service, lock order, fresh-state
     checks, request ID and audit semantics as the canonical endpoint.
3. Do not keep two endpoints with different meanings for “lock”, “unlock” or
   “extend”. If legacy model fields remain for compatibility, update them only
   as a documented atomic projection of canonical round/submission state.
4. Put single-round and bulk schedule changes under the game lifecycle lock.
   Bulk operations must acquire games in a stable order and must not partially
   schedule an instance on conflict.
5. Add an automated route-coverage guard that fails when a registered operator
   mutation route does not declare/use the lifecycle boundary or an explicit
   reviewed exemption. A grep for existing boundary calls is not sufficient.

## Blocking defect 2 — generated refusal request ID does not match its audit row

`operator_action()` calls `request_id_for(request)` and records that value on
the rejection. After the context manager raises, `lifecycle_view` calls
`request_id_for(request)` again when creating the response. If the caller did
not supply `X-Request-ID`, each call generates a new UUID. The response therefore
points to an ID that is not on the rejection audit event, breaking the stated
operator correlation guarantee.

### Required repair

1. Resolve the request ID exactly once per request and cache it on the request or
   carry the original ID on `LifecycleError`.
2. Use that same value in committed/rejected audit events, API response bodies,
   logs and engine-fault responses.
3. Add tests for both caller-supplied and server-generated IDs. For a refusal,
   assert the response ID equals exactly one audit row's ID. Also test nested
   helpers and repeated calls do not mint another ID.

## Required concurrency evidence

Retain the existing seven-pair matrix, then add PostgreSQL barrier races that
exercise every retained legacy/scheduling path against its conflicts. At
minimum:

- legacy lock/unlock vs close and process;
- legacy extend vs close and set-deadline;
- schedule-set vs scheduler close and process;
- bulk schedule vs close/process on an affected game;
- one refusal in each family with no caller `X-Request-ID`.

Assert final canonical round/submission state, no lost deadline update, exactly
one audit row per committed action, one attributable audit row per refusal, no
partial bulk mutation, no deadlock and no unexplained 5xx.

## Re-audit entry criteria

Return only when all are true:

- The registered mutation-route inventory is checked in and complete.
- Every active lifecycle mutation route uses the common boundary or is removed.
- A test prevents a future registered bypass.
- Generated and supplied request IDs correlate exactly across response/audit/log.
- Expanded race evidence passes in both arrival orders.
- The complete matrix, including original and new pairs, is generated once from
  the final frozen revision at 100 races per pair. Old evidence may remain as
  superseded history but cannot certify the new revision.
- Full backend suite, migration check, schema check, evidence checksums and
  `git diff --check` pass.
- V2-004 remains open until this re-audit passes.

## Checks that passed in this audit

These do not change the fail verdict:

- The canonical routes inspected do acquire the advisory lock before rows.
- Existing evidence inventory checksums verify.
- Existing matrix reports 700 races, zero deadlocks and zero 5xx.
- `process_round` Phase-2 dispatch uses `transaction.on_commit()`.
