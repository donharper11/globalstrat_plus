# GSP-CRV2-02 operator-concurrency evidence

Closes **V2-004**. 7 pairs × 100 races × both arrival orders = **700 races**,
real threads against real PostgreSQL, barrier-synchronised.
`backend/core/tests/test_operator_concurrency.py`.

## Result

| Pair | Outcomes observed | Deadlocks | 5xx |
|---|---|---|---|
| close + extend | 200+200 ×49, 200+400 ×51 | 0 | 0 |
| close + reopen | 200+200 ×52, 200+409 ×48 | 0 | 0 |
| process + correct | 200+409 ×58, 400+200 ×42 | 0 | 0 |
| process + process | 200+409 ×47, 409+200 ×53 | 0 | 0 |
| advance + correct | 200+409 ×100 | 0 | 0 |
| deactivate + process | 200+200 ×100 | 0 | 0 |
| scheduler-close + manual-close | manual 200 ×92, manual 409 ×8 | 0 | 0 |

The split in each row is the evidence that both arrival orders really raced —
process + process resolved 47 times from one operator and 53 from the other,
and process + correct went each way 58/42. Nothing here is a fixed winner.

`pg_stat_database.deadlocks` is unchanged across every pair, and each pair's
JSON records advisory-lock rows sampled *during* the race showing two sessions
on the same lock with one `granted: false`. That is the boundary being
contended rather than the races quietly missing each other.

## What each pair proves

* **process + process** — exactly-once resolution. Every one of the 100 rounds
  has exactly one `ResolutionManifest` with an `output_sha256`, and exactly one
  financial and leaderboard row per team. The loser is a 409, never a 500 and
  never a second resolution. This is the P0.
* **process + correct** — the gap the v2 register left open. When resolution
  wins, the correction is refused; when the correction wins, resolution refuses
  with a 400. Asserted on the data as well as the codes: no round in the
  database resolved while any of its submissions was a draft.
* **advance + correct** — a correction can never reach a round the game has
  moved past; refused in both arrival orders.
* **deactivate + process** — the roster a round *scored* equals the roster its
  input manifest *recorded*, so a withdrawal lands wholly before or wholly
  after a resolution, never inside one.
* **close + extend** and **close + reopen** — the round's status and its
  submissions' lock state always agree. A round left `closed` with unlocked
  submissions would let a team edit past the deadline; `open` with locked ones
  would deny them time they were given back.
* **scheduler-close + manual-close** — the pair that runs every minute in
  production. Closed exactly once, with one close reason, and the operator
  either wins or is told the scheduler got there first.

## Honest limits

* The scheduler wins only 8 of 100 races: a management command has more startup
  cost than an API request, so the operator usually arrives first. Eight
  scheduler wins is real coverage of that direction, but it is thin, and a
  slower machine would shift the ratio.
* Phase 2 (narrative generation) is stubbed out in these tests. It runs after
  the boundary is released, is outside the competitive envelope, and its
  durability is GSP-CRV2-03's subject; leaving 100 background threads racing
  the test teardown only produced connection noise.
* The fixture is a deliberately minimal scenario — two teams, one market. These
  tests are about coordination, not scoring; a full scenario makes Phase 1 slow
  enough that 700 races would take an hour.

## Files

```
SUMMARY.json                    consolidated index
<pair>.json                     per-pair: status-code tally, deadlock counter
                                either side, advisory locks sampled mid-race,
                                and the first iterations' full API responses
matrix-transcript.txt           the verbose test run
MANIFEST.sha256                 sha256 of every file above
```

## Reproducing

```bash
cd backend
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput
```

Takes about nine minutes. `ITERATIONS` at the top of the test module sets the
race count.
