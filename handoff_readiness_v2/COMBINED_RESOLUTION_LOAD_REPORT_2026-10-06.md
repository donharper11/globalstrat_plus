# Gate 3 — combined deadline, refresh and Phase-1 resolution under load

**Candidate:** `f3ebfd4f` on `crv2-release-integration`, clean working tree.
Both profiles record their own `code_revision` and `working_tree_clean`.

**Evidence:** `evidence/load-failure/combined-resolution-2026-10-06/`,
`SHA256SUMS` covers every file. The traffic inventory this discharges is
`evidence/load-failure/COMBINED_RESOLUTION_INVENTORY.md`.

This is the checklist line that CRV2-07 explicitly did **not** cover: its
load report measured refresh/save/lock traffic at field and 3x but never
drove instructor resolution under load. Here the owning instructor's real
`POST /round-control/process/` route — `force=true` with an audited reason,
which closes the round and runs synchronous Phase 1 — executes while the
cohort is still refreshing, saving and locking.

## Result

| | field (96 sessions) | margin (288 sessions, 3x) |
|---|---|---|
| verdict | **PASS** | **INADMISSIBLE for latency** |
| interactive requests | 18,964 | 19,533 |
| client p50 / p95 / max | 476.6 / **901.4** / 2270.5 ms | 2591.8 / 3267.1 / 5778.2 ms |
| **server** p50 / p95 / p99 / max | 325.4 / **669.2** / 742.6 / 1087.4 ms | 338.6 / **646.9** / 715.2 / 1036.1 ms |
| client/server p95 ratio | 1.35 (admissible) | **5.05 (generator-saturated)** |
| 5xx / transport failures | **0 / 0** | **0 / 0** |
| business 4xx (correct refusals) | 984 | 1,321 |
| Phase-1 route under load | **200**, 26.2 s | **200**, 23.7 s |
| round end state | `processed` / `RESULTS_AVAILABLE` | `processed` / `RESULTS_AVAILABLE` |
| peak DB connections | **33** of 100 (897 samples / 225.9 s) | 32 of 100 (958 samples / 241.5 s) |
| deadlocks / lock waits | **0 / 0** | **0 / 0** |
| acknowledged writes reconciled | **7,227, all clean** | 7,590, all clean |
| lost / duplicated / unexplained | **0 / 0 / 0** | 0 / 0 / 0 |
| refusals wrongly recorded | **0** of 960 | 0 of 1,297 |

**Field passes every threshold fixed in advance** and is the pinned
competition size (24 teams x 4 members). Client p95 of 901.4 ms sits against
a 2000 ms threshold; the server itself spent 669.2 ms at p95. Resolution
completed while the cohort was still writing, the round ended `processed`,
and every acknowledged write left exactly one audit row.

**Margin is recorded as inadmissible, not as a pass and not as a product
failure.** At 288 sessions the client observed p95 3267.1 ms while the server
spent 646.9 ms per request at p95 — a ratio of 5.05. The load generator, the
32 gunicorn workers and PostgreSQL share eight cores on this host, and total
throughput was the same at 288 sessions as at 96 (~19,000 requests), which is
the signature of a host already CPU-saturated: the extra 192 sessions bought
client-side queueing, not offered load. The profile therefore measured its own
generator. **3x combined load stays uncertified** until it can be driven from
a generator host separate from the stack.

What the margin run does establish, as supporting rather than certifying
evidence: at triple the pinned concurrency the server's per-request latency
was unchanged (p95 646.9 ms against 669.2 ms at field), with no 5xx, no
transport failure, no deadlock, no lock wait, a successful synchronous
Phase-1 resolution, and 7,590 acknowledged writes reconciling exactly.

## Two harness defects this exercise found and repaired

**The database-connection ceiling was unmeasured in the one condition it
exists to measure** (`9646faf9`). The sampler forked `psql` per reading. That
worked at smoke size — 63 samples — and collapsed at field size, where every
fork+exec after the first exceeded its 10-second timeout and
`except Exception: pass` hid all of them. The first field run of 2026-10-06
reported a connection **peak of 1 from a single pre-load sample**, and the
gate accepted it, because the gate only asked whether the sample list was
non-empty and whether its maximum exceeded 80. Both are true of one sample of
value 1. The sampler now holds one long-lived connection and records
attempted/failed counts, and the profile tests admissibility before threshold:
at least half the ticks the sampling window implies, never fewer than 20. The
runs above carry 897 and 958 samples with zero sampler failures. Deadlock and
lock-wait figures were never affected — those come from cumulative
`pg_stat_database` counters read after the run.

**A latency breach was attributed to the product without being measured
there** (`f3ebfd4f`). The profile gated on client-observed latency alone, so
the margin breach read as a product limit. `gunicorn.conf.py` already ends its
`access_log_format` with `%(D)s`, the server's own service time, and it was
simply never read. The profile now parses it, publishes it as
`server_side_latency`, and adjudicates: a client p95 more than 2.5x the server
p95 makes the run inadmissible for latency, naming the ratio and the remedy;
otherwise the client thresholds apply unchanged; and a server-side p95 over
threshold is always a breach. **An inadmissible run is not a pass** — the
margin result was deliberately not rewritten into one on the server's kinder
numbers. Verified at smoke, where the two measurements agree to 0.1%: client
p95 715.4 ms against server p95 714.7 ms.

Neither repair touches product code. `backend/` and `frontend/` tree objects
are byte-identical across `e55b6193`, `9646faf9` and `f3ebfd4f`, so the
candidate's backend suite result stands unchanged.

## What this does not discharge

* 3x combined load, per above — it needs a separate generator host.
* The CRV2-07 sign-in storm remains open and untouched here: PBKDF2 at
  Django's default work factor pins all cores during a simultaneous cohort
  sign-in, and worker count does not help. Owner: deployment.
* The remaining Gate 3 drills — backend restart, gateway interruption,
  narrative-provider failure, failed backup, restore and replay — and alert
  delivery are separate items.
