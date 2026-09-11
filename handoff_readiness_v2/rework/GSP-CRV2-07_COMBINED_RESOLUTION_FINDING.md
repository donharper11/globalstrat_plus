# V2-062 — combined resolution load gate had no admissible harness (P1)

**Recorded:** 2026-09-11, before repair.

The existing CRV2-07 field/margin driver measured refresh, decision save and
lock traffic, but it did not invoke the registered instructor `process/`
route.  It therefore could not establish the outstanding combined deadline
burst + refresh + Phase-1-resolution condition.

Two implementation details also made an attempted combined run inadmissible:

1. its in-run PostgreSQL samplers were hard-coded to the old remote connection
   shape instead of the disposable stack's `DB_HOST`, `DB_PORT`, `DB_USER` and
   generated credential; and
2. the load seeder extended a four-firm game with bare `Team` rows.  Those rows
   lack the platform/product/market state Phase 1 requires, so a resolution
   measurement would exercise an invalid fixture rather than a field game.

**Reproduction:** inspect `driver.py` sampler connection construction and
`seed_field.py` before the repair; then attempt a Phase-1 resolution on the
extended fixture.

**Required repair:** use only process-local disposable PostgreSQL credentials,
seed a complete 24-firm game via `initialize_game`, attach the load instructor
to that game's course/section, and add a driver which sends the real instructor
process request concurrently with the deadline burst and continued refresh.

## Focused disposable smoke — 2026-09-11

The repair was exercised only against a generated local PostgreSQL container
and temporary backup root.  It drove eight authenticated student identities
against a complete 24-firm game, then sent the real owning-instructor
`POST .../round-control/process/` request at the deadline barrier while the
students sent their burst and continued refresh/save traffic.

| measure | result |
|---|---:|
| Phase-1 process response / engine Phase-1 time | 11.70 s / 6.87 s |
| authenticated identities | 8 / 8 |
| interactive requests / 5xx / transport failures | 96 / 0 / 0 |
| p50 / p95 / max interactive latency | 132.1 / 1,045.5 / **11,617.2 ms** |
| deadline-burst p95 / max | **11,559.5 / 11,617.2 ms** |
| resolution-window p95 / max | **11,525.0 / 11,602.4 ms** |
| business 4xx after close | 5 (expected refusals) |
| peak database connections / deadlocks | 9 / 0 |
| acknowledged writes / lost / duplicated / unexplained | 49 / 0 / 0 / 0 |
| final lifecycle state | `processed`, `RESULTS_AVAILABLE` |

The API accepted the instructor process request and reconciliation was exact,
but the fixed interactive maximum threshold is 10,000 ms.  The combined smoke
therefore **fails** on a 11,617.2 ms maximum.  The long responses occur in the
deadline-burst and resolution phases, while Phase 1 holds the lifecycle
boundary; this is an implementation/release-performance finding, not an
excuse to relax the threshold or call the smoke capacity evidence.

The complete development-only JSON was written outside the repository to
`/tmp/gsp-crv207-combined-smoke.json` during the run and intentionally is not
included in the immutable evidence checksum set.  A clean frozen candidate
must rerun the fixed 96- and 288-session profiles once a repair is chosen.

### Follow-up harness defect, recorded before repair

The first smoke also exposed an actor-selection defect: identities were stored
team-major, so slicing the first 96 would select twelve members from each of
eight firms rather than the declared four members from each of 24 firms.  The
eight-identity smoke consequently happened to use one firm's first eight
members.  It remains a valid proof that the combined route/reconciliation
workflow executes, but it is not a valid representative cohort selection.
The driver must select identities round-robin by team (one per team for smoke,
four per team for field, twelve per team for margin) before any field/margin
evidence run.

**Status:** open.  Harness proof complete; release-scale certification is
blocked by the measured interactive-latency breach.
