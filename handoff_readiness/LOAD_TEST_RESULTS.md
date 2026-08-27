# Phase 2 load and concurrency results

## Live authenticated baseline

The local production backend was probed on 2026-08-27 using the student decision retrieval path. This safe read baseline does not substitute for the final multi-user write rehearsal.

| Profile | Requests | Concurrency | Throughput | p50 | p95 | p99 | Statuses |
|---|---:|---:|---:|---:|---:|---:|---|
| Expected baseline | 96 | 24 | 33.0 rps | 494 ms | 1,285 ms | 1,713 ms | 96×200 |
| 3× / throttle probe | 288 | 72 | 63.8 rps | 1,157 ms | 1,323 ms | 1,333 ms | 242×200, 46×429 |

The 3× probe reused one identity, deliberately confirming the new 120/min per-user throttle. Real competition traffic is distributed across identities, so these 429s are expected for this abuse-shaped probe. The expected-profile p95 exceeds the aspirational 1-second gate and should be watched during rehearsal.

## Concurrency controls verified

- Decision list replacement executes in one transaction.
- Close and resolution acquire database row locks.
- The engine pipeline is one atomic transaction: failure rolls back mutations.
- Exactly one processed transition is possible; a waiting second invocation observes the processed state and stops.
- Every accepted write is hashed into the append-only audit ledger.

## Final multi-user write rehearsal — passed 2026-08-27

The production-shaped API rehearsal used 24 separate student identities and the
real Gunicorn/PostgreSQL path. Deadline-close contention uncovered and corrected
an upsert race, lock-order deadlock, stale permission window, and a resolution
snapshot race before the final passing runs.

| Profile | Requests | Accepted/audited | In flight at close | Uniform 403 | Locked | p50 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Expected | 96 | 86/86 | 10/10 | Yes | 24/24 | 643 ms | 913 ms | 1,608 ms |
| 3× | 288 | 259/259 | 29/29 | Yes | 24/24 | 2,127 ms | 2,452 ms | 2,473 ms |

Evidence: `evidence/deadline-96.json` and `evidence/deadline-288.json`.

Two concurrent resolution triggers were then issued against the preserved
24-team evidence game. Exactly one completed and one stopped with `Round 1 has
already been processed.` The pre-resolution dump was restored into an isolated
database and replayed using the same code. Both manifests matched byte-for-byte:

- input SHA-256: `7f276cd53a5ea60178f37c4cd92fb145152d2f9e010568d9f010fefda6a700a1`
- output SHA-256: `eec610617e280d24289014eb0da82299878a1b67bf5ff227e4f280ca594665e4`

All required dry-run invariants are satisfied: zero lost payloads, uniform late
rejection, one resolution winner, and byte-identical isolated restore/replay.
