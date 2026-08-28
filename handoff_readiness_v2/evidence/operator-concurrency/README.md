# GSP-CRV2-02 operator-concurrency evidence

Closes **V2-004**, second submission. 12 pairs × 100 races × both arrival
orders = **1200 races**, real threads against real PostgreSQL,
barrier-synchronised. `backend/core/tests/test_operator_concurrency.py`.

## Route coverage

Built from `urls.py` outward, not from the routes anyone remembered:

| | |
|---|---|
| Registered mutating routes | 214 |
| Lifecycle-mutating | 36 |
| On the boundary | 20 |
| Reviewed exemptions (view-keyed, each with a reason) | 16 |
| **Unguarded** | **0** |

Checked in as `backend/core/services/route_inventory.json`;
`RouteCoverageTests` fails on drift, on a new unguarded route, or on an
exemption that no longer matches a registered view.

Six registered routes were **removed** rather than repaired: four returned 500
to every caller (`Round.objects.get(round_id=...)` — a field this project's
Round does not have) and all six were a second vocabulary for close, reopen,
deadline and bulk scheduling. `Round.decisions_locked` — which the student
write path reads independently of `Round.status`, and which legacy unlock could
set to disagree with it — is now a projection maintained only by close/reopen.

## Result

| Pair | Outcomes observed | Deadlocks | 5xx |
|---|---|---|---|
| close + extend | 200+200 ×47, 200+400 ×53 | 0 | 0 |
| close + reopen | 200+200 ×56, 200+409 ×44 | 0 | 0 |
| process + correct | 200+409 ×58, 400+200 ×42 | 0 | 0 |
| process + process | 200+409 ×53, 409+200 ×47 | 0 | 0 |
| advance + correct | 200+409 ×100 | 0 | 0 |
| deactivate + process | 200+200 ×100 | 0 | 0 |
| scheduler-close + manual-close | manual 200 ×93, manual 409 ×7 | 0 | 0 |
| **bulk schedule + close** | 200+200 ×52, 400+200 ×48 | 0 | 0 |
| **bulk schedule + process** | 400+200 ×100 | 0 | 0 |
| **bulk schedule + scheduler-close** | 200 ×90, 400 ×10 | 0 | 0 |
| **extend + set-deadline** | 200+200 ×100 | 0 | 0 |
| **pause + process** | 200+200 ×100 | 0 | 0 |

The split in each row is the evidence that both arrival orders really raced —
process+process resolved 53 times from one operator and 47 from the other,
schedule+close went 52/48. Nothing here has a fixed winner.

`pg_stat_database.deadlocks` is unchanged across all twelve pairs, and each
pair's JSON records advisory-lock rows sampled *during* the race showing two
sessions on the same lock with one `granted: false`.

## What the new pairs prove

* **bulk schedule + close / + process / + scheduler-close** — the route the
  audit found unguarded. It is now validate-all-then-write: a schedule applies
  to every round it names or to none, and it is refused outright once a round
  is closed or processed. A separate assertion writes a deliberately invalid
  bulk request and checks no round moved.
* **extend + set-deadline** — two read-modify-writers on one column. The stored
  deadline is always exactly what the second writer computed, never a value
  derived from a deadline the first had already replaced.
* **pause + process** — `GamePauseView` used a bare `game.save()`, which
  rewrites every column from its own copy and could restore `current_round` to
  the value it read before a concurrent advance. The assertion is on the data:
  the game is never rewound.

## Request-id correlation

One id per request, resolved once and cached on it. Previously a server-minted
id was a fresh UUID per call, so a refusal's response carried an id that no
audit row had. `RequestIdCorrelationTests` asserts that the id in the response
matches **exactly one** audit row — for caller-supplied and server-generated
ids, and for commits, 409 conflicts and 400 preconditions alike.

## Honest limits

* The scheduler wins 7 of 100 races against a manual close (and 10 of 100
  against a bulk schedule): a management command starts slower than an API
  request, so the operator usually arrives first. Real coverage of that
  direction, but thin, and a slower machine would shift the ratio.
* Phase 2 is stubbed in these tests. It runs after the boundary is released and
  is outside the competitive envelope; its durability is GSP-CRV2-03.
* The fixture is a deliberately minimal scenario — two teams, one market. These
  tests are about coordination, not scoring.

## Files

```
SUMMARY.json                    consolidated index, including route coverage
<pair>.json                     per-pair: status-code tally, deadlock counter
                                either side, advisory locks sampled mid-race,
                                and the first iterations' full API responses
matrix-transcript.txt           the verbose test run
MANIFEST.sha256                 sha256 of every file above
```

## Reproducing

```bash
cd backend
python3 manage.py dump_route_inventory --check
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput
```

About fifteen minutes. `ITERATIONS` at the top of the test module sets the race
count.
