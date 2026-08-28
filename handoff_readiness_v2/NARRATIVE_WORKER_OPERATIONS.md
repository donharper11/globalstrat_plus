# Running the narrative worker

GSP-CRV2-03. Phase 2 no longer lives in a daemon thread that dies with the web
process; it is a durable queue, and something has to drain it.

## What changed for an operator

Resolving a round writes six `NarrativeJob` rows **in the same transaction as
the numbers**. If the numbers committed, the work is recorded. Nothing about
narratives can block, delay or alter a resolution, and nothing about a
narrative failure invalidates a result.

The console still reads `Round.processing_status` and `Round.narrative_error`.
Those are now a *projection* of the job rows rather than the only record, so an
abrupt process death no longer leaves them permanently wrong.

## Supervision

Run at least one worker per environment, supervised so it restarts:

```ini
# /etc/systemd/system/globalstrat-narratives.service
[Unit]
Description=GlobalStrat narrative worker
After=network.target postgresql.service

[Service]
Type=simple
User=globalstrat
WorkingDirectory=/opt/globalstrat/backend
EnvironmentFile=/etc/globalstrat/backend.env
ExecStart=/usr/bin/python3 manage.py run_narrative_worker --loop --interval 10
Restart=always
RestartSec=5
# Give it longer than the LLM batch timeout to finish the job in hand.
TimeoutStopSec=60
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

`SIGTERM` is handled: the worker finishes the job it is holding and then stops,
so a deploy does not leave a claim to expire. `SIGKILL` is safe too — that is
what the restart drill exercises — it just means waiting out the lease.

**More than one worker is fine.** Claims use `SELECT … FOR UPDATE SKIP LOCKED`,
so workers take different jobs rather than queueing behind each other, and two
can never run the same job.

**Without a worker**, a single-process deployment still gets its narratives: a
convenience thread drains the queue after each resolution, through the same
durable path. It is a convenience, not the mechanism — if it never runs, the
rows are still there.

## The lease

A claim is a lease, default 300 s (`--lease`). It must exceed the LLM batch
timeout (`TIMEOUT_PER_CALL`, 30 s per call), or a slow-but-alive worker would
have its job taken. A worker that dies leaves the lease to expire and the next
worker reclaims the job — nothing has to notice the death.

## Backlog alerting

```bash
python3 manage.py run_narrative_worker --status
```

```
       pending: 0
       claimed: 1
  stale_claims: 0
     succeeded: 42
        failed: 0
```

Alert on:

| Signal | Threshold | Means |
|---|---|---|
| `failed > 0` | any, during a competition | a round has given up on its prose; an operator must decide whether to retry |
| `degraded > 0` | any, during a competition | the job finished but the model did not answer, so the prose is a template fallback. Students are not blocked; the provider is not working |
| `stale_claims > 0` | sustained over two lease periods | workers are dying mid-job, or the lease is shorter than the provider's latency |
| `pending` not falling | over ~2 minutes with rounds resolved | no worker is running |

`degraded` exists because a provider outage would otherwise be invisible: every
producer falls back to a template, so the job reports `succeeded` and the
briefing arrives — just written by the engine rather than the model. That is
the right outcome for students and a silent one for operators, so the job
records how many calls fell back and why.

`stale_claims` is the one worth paging on: it is the shape of a crash loop, and
a single stale claim that clears itself is normal after a deploy.

## Retrying a failed narrative

```bash
python3 manage.py retry_narrative_jobs --game 12 --round 4 --dry-run
python3 manage.py retry_narrative_jobs --game 12 --round 4
```

This resets job rows and nothing else. **Scoring is not re-run**, the manifest
is untouched, and the competitive hash cannot move — which is the whole reason
narratives were separated from resolution. Never use the recovery workflow to
fix a narrative.

## What is never stored

No API key, and no error text containing one. Provider errors quote the failing
request, and that request carries an `Authorization` header, so every error is
passed through `sanitize_error()` before it reaches a row an instructor can
read. `model_name` and `model_endpoint` are configuration and are recorded, so
a disputed briefing can be attributed to the model that wrote it.

## The coherence switch

`COMPETITION_RAG_AFFECTS_COHERENCE` is **off** by default. With it off,
coherence is the deterministic formula score and the retrieval-grounded
evaluation is recorded beside it as instructor commentary. With it on, the LLM
score is blended into the published number — which makes a graded value depend
on an external service answering, and puts Phase 2 back inside the competitive
hash. See V2-016; turning it on is a competition-rules decision, not an
operational one.
