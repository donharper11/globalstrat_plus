# GSP-CRV2-07 — service thresholds and environment capacity

Written **before** any load run, as the handoff requires. Nothing here is
tuned to a result.

## Environment capacity, measured

| resource | value | how it binds |
|---|---|---|
| Application workers | **gunicorn, 3 sync workers** (`backend/gunicorn.conf.py`) | a sync worker serves one request at a time, so three requests are in flight at once and everything else queues. This is the governing constraint, not CPU |
| Worker timeout | 120 s, graceful 30 s | a request still running at 120 s is killed |
| `max_requests` | 1000 with 50 jitter | workers recycle during a long run; expected, not an error |
| Host CPU | 8 cores | not the binding constraint at 3 workers |
| Host memory | 35 GB total, ~28 GB available | ample |
| Host disk | 102 GB free on `/` | ample; disk-full is injected deliberately, not reached by load |
| PostgreSQL | `max_connections` 100, `shared_buffers` 2 GB, remote at 192.168.50.38 | Django opens a connection per request (`CONN_MAX_AGE` unset, so 0), so app connections are bounded by workers; headroom is for the disposable databases and any operator session |

The database is remote, so every query carries network latency that a
single-host deployment would not. Recorded because it inflates latency
relative to a co-located production stack rather than deflating it.

## Load profiles, fixed by the handoff

- **Field:** 24 teams x 4 members = **96 authenticated sessions**.
- **Margin:** 3x field = **288 authenticated sessions**.
- Separate identities per session. Traffic mixes refresh, save, lock and
  instructor resolution, and includes final-minute writes.

## Acceptance thresholds, defined in advance

**Interactive requests** — decision reads, decision saves, lock, summary:

| metric | threshold | reason |
|---|---|---|
| p95 latency | **≤ 2000 ms** | a save that takes longer than two seconds reads as broken to a student under deadline |
| max latency | **≤ 10000 ms** | anything slower is a stall, not a slow response |
| error rate | **≤ 0.5%** of requests, counting 5xx and transport failures | 4xx from business rules (round closed, submission locked) are correct behaviour and are reported separately, never counted as errors |

**Instructor resolution** is a different class and is not held to the
interactive bar. Phase 1 is a whole-cohort computation measured in seconds by
design. Threshold: **completes without error, and no interactive p95 breach
occurs while it runs**.

**Database:**

| metric | threshold |
|---|---|
| peak connections | **≤ 80** (80% of `max_connections`) |
| lock waits | no wait longer than **5 s** |
| deadlocks | **0** |

**Write reconciliation — the gate that matters most:**

| metric | threshold |
|---|---|
| acknowledged writes lost | **0** |
| acknowledged writes duplicated | **0** |
| unexplained final rows | **0** |

Every write the API acknowledged with a 2xx must be present in the final
database exactly once, and every row in the final database must trace to an
acknowledged write. A write refused with 4xx must leave no row.

**Reported, not gated:** throughput, p50, status distribution, CPU, memory,
disk, worker recycles. p99 is reported only where the sample makes it
meaningful; a percentile computed from a handful of requests is decoration.

## What would make a run inadmissible

A load run is refused, not reported, if: sessions fail to authenticate so the
profile never reached its stated concurrency; the driver cannot distinguish a
business 4xx from a transport failure; or write reconciliation cannot be
computed because attempted writes were not recorded with their outcomes. A
profile that did not reach its concurrency measures the driver, not the
product.
