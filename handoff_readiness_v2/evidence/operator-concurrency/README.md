# GSP-CRV2-02 operator-concurrency evidence

Closes **V2-004**. Third submission — the certification pass required by
`handoffs/EXECUTION_PROTOCOL.md`.

| | |
|---|---|
| Frozen revision | `830b7adee8ae5bad180a66cfe1797753b45d7e56` |
| Source tree digest | `a35c665d973478ddfd2ac2b3f5d8395b426637a6d5504acb57038be29c894fe3` |
| Races | 12 pairs × 100 = **1200** |
| Deadlocks / 5xx | **0 / 0** |

Both values are read by the process running the races and written into each
pair's JSON, not stamped in afterwards. All twelve files carry the same pair,
which is the check that the whole matrix came from one commit.

## What 100 means

**Total races per pair, not per arrival order.** `_race` alternates which
thread is released first by iteration parity, so 100 is 50 races with each
action arriving first — deliberate control, not a hope that the scheduler
varies. Every pair's JSON records
`arrival_orders: {first-first: 50, second-first: 50}`, and the per-iteration
`arrival_order` is in its transcript.

## Iteration profiles

`GSP_CRV2_02_ITERATIONS` accepts 1, 10 or 100 and nothing else:

| Profile | Value | Whole matrix | Use |
|---|---:|---:|---|
| Development | **1** (default) | ~33 s | the edit loop |
| Preflight | 10 | ~92 s | before a freeze commit |
| Certification | 100 | ~15 min | release evidence only |

`GSP_CRV2_02_EVIDENCE_DIR` refuses to run below 100, so a cheap sample cannot
overwrite a release artifact. `IterationProfileTests` covers all three profiles,
the rejection of any other value, and that guard — without running the matrix
three times.

## Result

| Pair | Outcomes observed (100 races) | Deadlocks | 5xx |
|---|---|---|---|
| close + extend | 200+200 ×46, 200+400 ×54 | 0 | 0 |
| close + reopen | 200+200 ×51, 200+409 ×49 | 0 | 0 |
| process + correct | 200+409 ×64, 400+200 ×36 | 0 | 0 |
| process + process | 200+409 ×51, 409+200 ×49 | 0 | 0 |
| advance + correct | 200+409 ×100 | 0 | 0 |
| deactivate + process | 200+200 ×100 | 0 | 0 |
| scheduler-close + manual-close | manual 200 ×92, 409 ×8 | 0 | 0 |
| bulk schedule + close | 200+200 ×53, 400+200 ×47 | 0 | 0 |
| bulk schedule + process | 400+200 ×100 | 0 | 0 |
| bulk schedule + scheduler-close | 200 ×85, 400 ×15 | 0 | 0 |
| extend + set-deadline | 200+200 ×100 | 0 | 0 |
| pause + process | 200+200 ×100 | 0 | 0 |

Where a row splits, neither side is a fixed winner — process+process resolved 51
times from one operator and 49 from the other. Each pair's JSON also records
advisory-lock rows sampled *during* the race with a waiter present, so the
boundary was contended rather than the races quietly missing each other.

## Route coverage

Built from `urls.py` outward (`core/services/route_inventory.py`, checked in as
`route_inventory.json`):

| | |
|---|---|
| Registered mutating routes | 214 |
| Lifecycle-mutating | 36 |
| On the boundary | 20 |
| Reviewed exemptions (view-keyed, each with a reason) | 16 |
| **Unguarded** | **0** |

## Expensive runs, this certification

| Operation | Count | Duration | Scale |
|---|---:|---:|---|
| Concurrency matrix | 1 | 938 s | 12 pairs × 100 races, 31 tests |
| Full backend suite | 1 | 164 s | 359 tests |

The suite is 164 s rather than the 1024 s of the previous submission because the
matrix inside it now runs at the cheap default.

## Honest limits

* The scheduler wins 8 of 100 races against a manual close and 15 of 100 against
  a bulk schedule: a management command starts slower than an API request, so
  the operator usually arrives first. Real coverage of that direction, but thin,
  and a slower machine would shift the ratio.
* Phase 2 is stubbed in these tests. It runs after the boundary is released and
  is outside the competitive envelope; its durability is GSP-CRV2-03.
* The fixture is a deliberately minimal scenario — two teams, one market. These
  tests are about coordination, not scoring.

## Files

```
SUMMARY.json                    consolidated index: revision, digest, profiles,
                                route coverage, run durations, per-pair tallies
<pair>.json                     per-pair: revision and digest read at run time,
                                arrival-order split, status-code tally, deadlock
                                counter either side, advisory locks sampled
                                mid-race, first iterations' full API responses
matrix-transcript.txt           the verbose test run
MANIFEST.sha256                 sha256 of every file above
```

## Reproducing

From the frozen commit, in this order:

```bash
cd backend
python3 manage.py dump_route_inventory --check
python3 manage.py dump_manifest_schema --check
python3 manage.py makemigrations --check --dry-run

GSP_CRV2_02_ITERATIONS=100 \
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput

python3 manage.py test core --noinput
```

Then regenerate `MANIFEST.sha256` and run `git diff --check`.
