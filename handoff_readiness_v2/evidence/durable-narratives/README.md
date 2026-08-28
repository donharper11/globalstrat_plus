# GSP-CRV2-03 durable-narratives evidence

Closes **V2-006**. Opens **V2-015** and **V2-016**.

| | |
|---|---|
| Frozen revision | `ef01237a6542f5950f8447531a927ce96046bb7e` |
| Source tree digest | `1e17a18eba73b33876449d9982048197ce33acf9fa184eac22bd073186d750c3` |
| Isolated stack | `globalstrat_replay`, restored from the GSP-CRV2-01 backup of game 37 round 1 |
| Full backend suite | 387 tests, 199 s, once |

Both provenance values are read by the process running each drill and written
into its own file, so the evidence says which bytes produced it.

## Restart recovery — a real SIGKILL, mid-job

`restart-drill-sigkill-mid-job.json`. The drill starts a worker in a separate
OS process against a provider that accepts the connection and never answers,
**waits until a job is actually claimed**, and then SIGKILLs the worker. SIGKILL
because V2-006 was that "an abrupt process death cannot populate
`narrative_error`" — a drill that lets the worker tidy up is not testing the
reported failure. The drill refuses to report a pass if the kill left no
orphaned claim.

| | |
|---|---|
| Killed while holding | `briefing`, leased to `ai-react:…` |
| Orphaned claims after the kill | 1 |
| Backlog before | 6 pending |
| Backlog after recovery | 6 succeeded, 0 pending, 0 failed, 0 stale |
| Competitive hash | **unchanged** |
| Jobs left claimed | none |

A fresh worker, with nothing in memory, recovered all six from the database.

## Provider conditions

Every scenario drains the same round's jobs and compares the competitive hash
either side.

| Scenario | Key | Hash unchanged | Terminal | Degraded | Failed | Secret leaked |
|---|---|---|---|---|---|---|
| working endpoint (real provider) | yes | **yes** | yes | 0 | 0 | no |
| unreachable endpoint | yes | **yes** | yes | 5 | 0 | no |
| no API key | no | **yes** | yes | 5 | 0 | no |

The working-endpoint row is the strongest: a model that answers normally still
leaves the competitive hash exactly where Phase 1 put it.

`degraded` is the signal the drills themselves produced. With an unreachable
provider every job first reported plain `succeeded`, because each producer
falls back to a template — right for students, who still get a briefing, and
silent for operators, who saw no sign the model never answered. A job now
records how many calls fell back and why, and stays `succeeded` because the
work is genuinely done.

Timeout, 429, 500 and malformed output are covered by
`core/tests/test_durable_narratives.py` with a stub provider, because they need
a server that returns a chosen failure rather than one that is merely absent.
Those tests also assert that a stored error never contains a credential: a
provider quoting the failing request would otherwise put an `Authorization`
header into a table instructors can read.

## What Phase 1's inventory found

Cross-referencing every narrative producer against the certified manifest
envelope — before writing any code — showed three of six writing into rows the
competitive hash covers, *after* that hash is taken. The hash never moved,
which is why every GSP-CRV2-01 replay matched: both sides hash at Phase-1
commit. What diverged is the stored database from the manifest that certified
it, which no replay compares. See `../../NARRATIVE_JOB_INVENTORY.md`.

Logged as **V2-015** before repair, and then demonstrated by a failing test
rather than asserted. Repaired here for SC-event prose and coaching alerts; the
coherence blend is **V2-016** and needs a rules decision, because
`blended_score` is read by `services/grading.py` and an LLM outage would
otherwise change a grade.

## Files

```
SUMMARY.json                          consolidated index
restart-drill-sigkill-mid-job.json    the kill, what it was holding, recovery
restart-drill.log                     drill transcript
provider-<scenario>.json              per-scenario job states and hashes
MANIFEST.sha256                       sha256 of every file above
```

## Reproducing

```bash
cd backend
DB_NAME=<disposable> python3 manage.py migrate core --noinput

DB_NAME=<disposable> python3 ../handoff_readiness_v2/narrative_restart_drill.py \
  --game 37 --round 1 --lease 8 --out <evidence dir>

DB_NAME=<disposable> DASHSCOPE_COMPATIBLE_URL=http://127.0.0.1:9/v1/chat/completions \
DASHSCOPE_API_KEY=drill-key \
python3 ../handoff_readiness_v2/narrative_provider_drill.py \
  --game 37 --round 1 --scenario unreachable-endpoint --out <evidence dir>

python3 manage.py test core --noinput
```
