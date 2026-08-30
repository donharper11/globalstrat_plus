# GSP-CRV2-07 — field load and capacity: interim report

**Scope.** This covers the load half of CRV2-07 only. The recovery walkthrough
and the deploy/restore walkthrough are **not** discharged here and remain
outstanding; a passing load report does not make CRV2-07 complete.

## Revisions

| role | revision |
|---|---|
| Runtime and harness freeze | `8481c25cc42d` — both profiles ran here |
| Evidence | same; each artifact records its own `code_revision` |
| Report-only | this commit; no runtime, harness or evidence change |

Evidence: `handoff_readiness_v2/evidence/load-failure/`, checksums verified.

## Result

**Both profiles pass every threshold fixed in advance.**

| | field (96 sessions) | margin (288 sessions, 3x) |
|---|---|---|
| offered demand | 10.7 rps | 32.0 rps |
| **throughput achieved** | **11.6 rps** | **34.3 rps** |
| client p50 / p95 / max | 65.3 / **90.1** / 179.6 ms | 73.2 / **175.0** / 406.1 ms |
| server p50 / p95 | 64.5 / 95.8 ms | 72.4 / 179.9 ms |
| steady p95 | 86.8 ms | 118.9 ms |
| final-minute p95 | 100.3 ms | 310.4 ms |
| requests over 10 s (server) | **0** | **0** |
| 5xx / transport failures | **0 / 0** | **0 / 0** |
| business 4xx (correct refusals) | 8 | 24 |
| deadlocks / lock waits | 0 / 0 | 0 / 0 |
| peak DB connections | 32 of 100 | 32 of 100 |
| CPU mean / peak | 34.4% / 100% (sign-in) | 50.6% / 100% (sign-in) |
| memory | — | 7.2 GB of 36 GB |
| **acknowledged writes reconciled** | **1185, all clean** | **3514, all clean** |

**Supported ceiling: at least 3x field.** Margin offered triple the field
demand and the system carried it — 34.3 rps against 32 offered — with p95 at
175 ms against a 2000 ms threshold. Capacity beyond 3x is not a launch
requirement and was not pursued.

**Write reconciliation, the gate that matters most, is absolute.** Across every
run at every configuration, no acknowledged write was ever lost, duplicated or
unexplained, and no audit row ever carried a request id the API had refused.
Each accepted save writes one append-only audit row carrying the driver's
`X-Request-ID`, so both questions are answered exactly rather than inferred.

## Configuration repairs this exercise produced

**Workers 3 → 32** (`backend/gunicorn.conf.py`). Three sync workers capped
throughput at three divided by the service time, about 21 rps, and the field
profile queued behind it. 17 (gunicorn's `(2 x cores) + 1`) cleared the steady
state; 32 cleared the final-minute deadline burst, where 288 saves and 24 locks
arrive together and workers block on remote-database I/O rather than CPU.

**`preload_app = True`.** Without it each worker imports Django on its first
request. This was adopted against evidence that later proved to be sign-in
contamination rather than cold start, so its measured benefit here is
unproven — it is retained because importing once in the arbiter is correct on
its own terms, not because this exercise demonstrated a gain.

## Open finding — sign-in storm

| | field (96) | margin (288) |
|---|---|---|
| cohort sign-in window | 26.0 s | **63.7 s** |
| login p50 | 21.0 s | **39.7 s** |
| login max | 26.7 s | **62.7 s** |

Password verification is PBKDF2 at Django's default work factor. A simultaneous
cohort sign-in is a pure CPU burst: it pins all 8 cores at 100% while the rest
of each run averages 34-51%. **More workers do not help**, and the worker
increase that fixed every other number leaves this untouched. A student at the
back of a 288-strong cohort waits over a minute for a password check, and this
is exactly the moment a class starts.

Owner: deployment. The levers are the hasher's iteration count (a security
trade-off, not a builder's call), more cores, or staggering sign-in.

## Thresholds

Fixed before any run in `evidence/load-failure/THRESHOLDS.md` and never
moved: interactive p95 2000 ms, max 10000 ms, error rate 0.5% counting only 5xx
and transport failures, DB connections 80, no lock wait over 5 s, zero
deadlocks, and zero lost, duplicated or unexplained writes. Business 4xx —
a save refused after the deadline or against a locked submission — is the
product working and is reported separately, never as an error.

Also fixed in advance: what makes a run **inadmissible** rather than merely
poor. That gate fired once, refusing a run in which all 8 sessions returned 200
but none authenticated, because the driver truncated the access token. Without
it that run would have reported a clean pass on zero work.

## Measurement failures, and which numbers were invalid

Nine field runs preceded these results. Four followed genuine fixes; the rest
were measuring the harness rather than the product. Every one inflated latency
in the same direction, and none was visible in the aggregates — only in the
per-second timeline.

1. **Warm-up contamination.** Login was recorded from the first run and reported
   in none. Every session was still authenticating until second 22, so the
   "stall" chased through five hypotheses was the first moment interactive
   traffic could begin. Sessions now authenticate, wait on a barrier for the
   whole cohort, and only then open the measured window.
2. **Observer effect.** The `pg_stat_activity` sampler spawned psql
   subprocesses from the driver process and cut throughput from 13778 requests
   to 4690. It is now opt-in.
3. **Lockstep arrivals.** The start barrier released all 96 sessions in one
   instant, putting 35 requests into a single second. First actions are now
   spread across a think-time interval.
4. **An unrealistic traffic model.** Sessions paused 0.05-0.35 s between
   actions — a load-generator default, not a student — offering several hundred
   rps against a ceiling near 35. **No product could have met the p95 threshold
   under that model.** Think time is now 3-15 s and each run reports the demand
   it offers.
5. **Mismatched instrumentation.** Server-side timing parsed the whole access
   log including sign-in, so it described a different population from the
   client and read 35x slower. Field was re-run after the fix so both profiles
   use identical instrumentation; client and server now agree within 6 ms.

Every p95 reported before those corrections was invalid. They are recorded here
because the git history contains nine superseded runs, and an auditor should
not have to discover which were wrong.

## Scope and residual risk

1. **Recovery and deploy/restore are not covered.** Five boundary injections and
   one backup/restore cycle remain outstanding.
2. **Instructor resolution was not driven under load.** The profiles exercise
   refresh, save and lock. Phase 1 resolution is a whole-cohort computation
   held to a different bar and is not measured here.
3. **The database is remote.** Every query carries network latency a co-located
   deployment would not, which biases the measurement against the product.
4. **One host, one run per profile.** No repetition, so run-to-run variance is
   uncharacterised.
