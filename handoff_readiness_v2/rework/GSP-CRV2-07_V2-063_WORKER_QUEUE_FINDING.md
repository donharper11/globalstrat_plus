# V2-063 — queued decision writes starve refreshes during synchronous Phase 1 (P1)

**Recorded:** 2026-09-11, before repair.  **Scope:** CRV2-07 development
combined deadline/resolution smoke only; this is not field-scale evidence.

## Distinct root cause

V2-062 correctly identified that the combined load condition had not been
measured and recorded the initial above-threshold result while Phase 1 held the
lifecycle boundary.  The focused disposable reproduction identifies the
mechanism of that latency: a decision write takes the shared game advisory lock
*before* dispatching its round-open permission check.  During synchronous
Phase 1 the instructor holds the exclusive form of that lock.  Final-minute
writes therefore wait inside Gunicorn's three synchronous workers; lock-free
summary refresh requests then queue behind those blocked workers.

This is not database saturation or a lost-write failure.  The reproduction
completed Phase 1 in 6.76 s, had zero 5xx/transport failures and reconciled all
acknowledged writes, but measured an 8.71 s max and 8.62 s interactive p95 in
the deadline/resolution phases (above the 2 s p95 threshold).

## Required repair and invariants

On conflict with a lifecycle action, a student mutation must fail quickly with
an explained 4xx rather than wait for the long-running exclusive lock.  It must
not write, and a request that does obtain the shared lock must retain the
existing lock order, transaction, permissions, per-team lock, round recheck and
decision audit path.  The 10-second maximum and all CRV2-07 thresholds remain
unchanged.

The focused regression must demonstrate both: (1) a contended mutation returns
without waiting for a held exclusive boundary and does not execute its handler;
and (2) normal mutations still acquire the shared boundary and execute exactly
once.

## Repair verification — development only

`try_lock_game_for_decision_write` now takes the same PostgreSQL shared
advisory boundary without waiting.  A conflict returns a finalized, permission
checked `409 lifecycle_in_progress`; a successful acquisition follows the
existing shared-lock, team-lock and handler path unchanged.

The focused `core.tests.test_competition_locks` PostgreSQL test passed against
a generated container.  It held the exclusive game boundary from another
connection and proved the mutation returned in under 0.5 seconds without
executing its handler; after release the same mutation executed exactly once.

The final disposable eight-session combined smoke passed with no threshold
breaches: Phase 1 was **6.93 s**, instructor response **8.43 s**, interactive
p50/p95/max **37.8/659.3/749.0 ms**, zero transport failures and zero 5xx,
and **31** acknowledged writes reconciled with zero lost, duplicated or
unexplained rows.  It returned **32** expected busy `409` responses and three
other expected business `400` refusals.  The run is harness/regression proof
only; CRV2-07 field and margin certification remain pending a clean frozen
candidate.
