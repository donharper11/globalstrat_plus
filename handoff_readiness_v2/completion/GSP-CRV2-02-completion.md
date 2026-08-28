# GSP-CRV2-02 completion report — fail-closed operator concurrency

**Finding closed:** V2-004 (P0)
**Date:** 2026-08-28
**Branch:** `crv2-02-operator-concurrency`, on the GSP-CRV2-01 baseline `bb1cbe2`

## What the inventory found

V2-004 was written up as "reopen, deadline change and advance did not share the
row-lock transaction used by close/process". Tracing every route — the handoff
explicitly warned not to assume the existing locks covered child decision
writes or legacy paths — showed the shape was wider. Each lifecycle endpoint
decided for itself what to lock and, more importantly, *when to check*. Five
took no lock at all.

Two that were live before this work:

* `RoundProcessView` read the round's status outside any lock, then called
  `process_round`. Two operators both saw `closed` and both proceeded; the
  loser hit `ValueError('already been processed')` inside the engine, which a
  blanket `except Exception` turned into a **500**.
* `InstructorExtendDeadlineView` reopened a closed round as a side effect,
  unlocking every submission, with no lock, no transaction, no processed check
  and no audit record.

## What was built

**One boundary, one order** (`core/services/competition_locks.py`): an
exclusive advisory lock per game, taken before any row lock, then the `Game`
row, the `Round` row, the per-team advisory lock, then team rows. Student
writes take level 1 *shared*; operator actions take it *exclusive*, so they
exclude both student writes and each other. No path acquires in reverse.

**`core/services/lifecycle.py`** makes the pattern hard to get wrong.
`operator_action()` yields the game row under the lock and a `round` property
that re-reads on every access, so a view cannot validate against a stale copy.
`@lifecycle_view` turns a refusal into its documented response instead of a
500.

**Twelve entry points** brought onto it — the five round-control routes, three
legacy instructor routes, both event-injection routes, the correction unlock,
team participation, the deadline scheduler and the recovery command. Full
inventory in `OPERATOR_CONCURRENCY_MATRIX.md`.

**Refusals are audited.** `OperatorAuditEvent` gained `outcome` and `conflict`.
A rejection is written *after* the transaction it refused has rolled back, in
its own transaction — the first attempt at this wrote it inside, and the
rollback took the evidence with it, which the audit-completeness test caught.
`after` stays empty so the row cannot imply the round moved. An engine *fault*
is recorded differently again: inside the transaction, because the engine's
`processing_status=FAILED` marker is written there and re-raising would roll
both back (that is V2-005, and it must not regress).

**A caller can prove it was not racing.** `expected_round_number` and
`expected_status` are compared under the lock; a mismatch is a 409
`state_moved` naming what changed. Without it the loser of a race gets whatever
message fits the *new* state — "close it first" — which reads as the operator's
mistake. The console now sends what it rendered.

**Phase-2 dispatch moved to `transaction.on_commit`.** Once a view can wrap
`process_round` in its own transaction, the old direct thread start would let
the narrative thread read a round the database had not yet accepted.

## Status codes

A stable promise, written down in `lifecycle.py` and the matrix document:
**409** means refresh and look again (already done, or terminal for this
action); **400** means do something else first or fix the request. Two existing
tests changed: reopening a processed round is now 409 (results exist; nothing
the operator types helps), while advancing before processing stays 400 (they
can process and retry).

## Force flags

No `force` bypasses an integrity check without a written reason of at least ten
characters, recorded on the audit row: process-force, advance-force, the legacy
advance's all-teams-locked override, extend-deadline's implicit reopen, the
correction unlock, and team withdrawal (which also keeps its exact confirmation
token).

## Tests and evidence

```bash
cd backend
python3 manage.py test core --noinput                        # 338 passed
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput
```

7 pairs × 100 races × both arrival orders = **700 races**, real threads against
real PostgreSQL with a barrier, no mocks. **0 deadlocks, 0 5xx.**

The status-code tallies show both orders genuinely won — process+process 47/53,
process+correct 58/42, close+reopen 52/48 — and each pair's JSON records
advisory-lock rows sampled mid-race with a waiter present, so the boundary was
contended rather than the races quietly missing each other.

The invariants are asserted on the data, not only the codes: no round in the
database ever resolved while one of its submissions was a draft; every resolved
round has exactly one manifest and one full result set; a round's status and
its submissions' lock state always agree; and the roster a round *scored*
equals the roster its input manifest *recorded*.

## Unresolved risks

1. **The scheduler wins only 8 of 100 races.** A management command has more
   startup cost than an API request, so the operator usually arrives first.
   Eight scheduler wins is real coverage of that direction but thin; a slower
   machine would shift the ratio. Worth re-running under load in GSP-CRV2-07.
2. **Operator actions now hold the boundary for the whole of Phase 1.** Student
   writes block behind a resolution rather than racing it — which is the point
   — but on a slow resolution that is a visible stall for anyone still saving.
   The round is closed by then, so those writes would be rejected anyway; the
   latency, not the outcome, is the risk. GSP-CRV2-07's load work should
   measure it.
3. **Phase 2 is stubbed in the concurrency tests.** It runs after the boundary
   is released and is outside the competitive envelope; its durability is
   GSP-CRV2-03's subject.
4. **`InstructorAdvanceRoundView` still exists.** It is now on the boundary and
   returns the same codes as the modern route, but two consoles driving the
   same lifecycle is a maintenance hazard. Retiring it is a product decision.
5. **The fixture is a minimal two-team scenario.** Coordination does not depend
   on scoring richness, but a full-field race has not been run; that belongs
   with the load work.
