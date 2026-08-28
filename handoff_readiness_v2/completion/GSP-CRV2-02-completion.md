# GSP-CRV2-02 completion report — fail-closed operator concurrency

**Finding closed:** V2-004 (P0)
**Date:** 2026-08-28
**Branch:** `crv2-02-rework`, on the GSP-CRV2-01 baseline `bb1cbe2`

## Second submission — what the audit sent back

`rework/GSP-CRV2-02-AUDIT-REWORK.md` returned FAIL on two points.

**1. Five registered lifecycle routes bypassed the boundary.** The audit was
right, and understated it. My inventory had been built by *tracing the routes I
knew about* and then checking they used `operator_action()` — which cannot find
a route nobody thought to look at. Rebuilding it mechanically from `urls.py`
found **fourteen** unguarded lifecycle-mutating routes, nine more than the
audit listed: the five it named plus `GameActivateView`, `GamePauseView`,
`GameResumeView`, `GameArchiveView`, `GameResetView`, `GameRoundScheduleView`,
`InstructorTeamConfigView`, `GameCreateView` and `RoundScheduleView`.

The five game-status views were the worst of the additions: each used a bare
`game.save()`, which rewrites every column from its own in-memory copy, so
pausing a game concurrently with an advance could restore `Game.current_round`
to the value it had read beforehand. There is now a race asserting it cannot.

Six routes were **removed** rather than repaired. Four returned 500 to every
caller — they queried `Round.objects.get(round_id=...)`, and this project's
`Round` has no `round_id` — and all six were a second vocabulary for actions
that already had one. "Lock" and "unlock" meant `Round.decisions_locked`, a
flag the student write path reads independently of `Round.status`; legacy
unlock could therefore let students write into a closed round. That flag is now
a projection maintained only by close/reopen, with a test asserting it always
agrees with status. No client referenced any of the six.

`core/services/route_inventory.py` walks the URL conf, reads each view's source
*and its bases'*, and flags a route when it writes lifecycle state — including
a bare `.save()` beside a lifecycle query, because that is a write whether the
author meant it as one. Result: **214 mutating routes, 36 lifecycle-mutating,
20 on the boundary, 16 view-keyed reviewed exemptions, 0 unguarded.**
`RouteCoverageTests` fails on drift, on a new bypass, or on an exemption that
no longer matches a registered view. `manage.py dump_route_inventory --check`
is the CI guard.

**2. A generated refusal id did not match its audit row.** `request_id_for()`
minted a fresh UUID on every call, and it was called once by
`operator_action()` for the audit row and again by `lifecycle_view()` for the
response. The id is now resolved once and cached on the request (and on the
Django request DRF wraps), so every audit row, response body and log line for
one request carries the same value. Tests assert the response id matches
exactly one audit row — supplied and generated ids, commits, 409s and 400s.

**Evidence expanded** from 7 pairs to 12: bulk schedule against close, process
and the deadline scheduler; extend against set-deadline; pause against process.
1200 races, still 0 deadlocks and 0 5xx.

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
python3 manage.py dump_route_inventory --check    # route coverage guard
python3 manage.py test core --noinput                        # 353 passed
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput
```

12 pairs × 100 races × both arrival orders = **1200 races**, real threads
against real PostgreSQL with a barrier, no mocks. **0 deadlocks, 0 5xx.**

The status-code tallies show both orders genuinely won — process+process 53/47,
process+correct 58/42, schedule+close 52/48 — and each pair's JSON records
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
6. **The route detector is a heuristic over source text.** It over-flags by
   design — a lifecycle query beside any `.save()` counts — so the judgement
   lives in the sixteen exemptions, each of which states what was checked. A
   view that mutated lifecycle state through a helper in another module with no
   local query or field assignment would slip past it. The behavioural races,
   not the detector, are what prove a route is safe.
7. **Six routes were deleted.** They returned 500 to every caller and no client
   referenced them, but deletion is irreversible for any unknown integration.
   The commit message and the matrix document name each one and its
   replacement.
