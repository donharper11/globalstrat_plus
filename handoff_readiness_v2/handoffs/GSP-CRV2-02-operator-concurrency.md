# GSP-CRV2-02 — Fail-closed operator concurrency

**Finding:** V2-004 (P0)  
**Owner:** backend lifecycle/concurrency engineer

## Objective

Every conflicting operator action must serialize on one coordination boundary,
validate fresh state after acquiring it, and either commit one coherent action
or reject without partial state.

## Scope

Inventory close, reopen, extend/set deadline, process, advance, correction,
team deactivate/reactivate, event injection and recovery entry points. Do not
assume the current game/round row locks cover child decision writes or legacy
routes; trace them.

Define an explicit compatibility matrix. At minimum exercise close+extend,
close+reopen, process+correct, process+process, advance+correct,
deactivate+process and scheduler-close+manual-close.

## Requirements

- One documented lock order; no reverse acquisition path.
- Fresh-state preconditions evaluated after locks are held.
- Conflicts return stable 409/400 responses with operator guidance.
- One request ID and immutable operator event per committed action; rejected
  attempts are observable without pretending they changed state.
- No `force` flag may bypass integrity without explicit audit reason and role.
- Deadlock/serialization errors receive bounded safe retry only where idempotent.

## Acceptance

Use PostgreSQL transactional integration tests with barriers, not mocks. Repeat
each pair at least 100 times with both arrival orders. Assert final round state,
decision locks, exactly-once resolution, audit completeness, no partial output
and no unexplained 500. Capture DB lock/deadlock evidence and API responses.

Store results under `handoff_readiness_v2/evidence/operator-concurrency/` and
close V2-004 only after the whole matrix passes.
