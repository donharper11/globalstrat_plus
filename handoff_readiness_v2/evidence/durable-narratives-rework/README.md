# GSP-CRV2-03 rework evidence

Focused rework of two audit blockers. The durable queue, SIGKILL recovery,
provider degradation and hash isolation were not rebuilt, re-run or
re-certified — their evidence in `../durable-narratives/` stands against its
own frozen revision `ef01237`.

| | |
|---|---|
| Frozen revision | `49d6514b9b9723e8d4e6244bb58236a89a3551d6` |
| Source tree digest | `0c284a835d41f1a6b1ab0e1ea76b8e20cfe1e0032c13a6def75fd3e9f651003b` |
| `git status --untracked-files=no` | clean |

## R1 — instructor observability

`GET /api/games/<id>/round-control/` — the existing instructor round-status
surface — now returns a `narratives` block. No new subsystem, no frontend
workflow.

Per job: `narrative_type`, `label`, `state`, `state_label`, `degraded`,
`attempts`, `max_attempts`, `attempts_remaining`, `template_version`,
`model_name`, sanitized `last_error`, and `created_at` / `claimed_at` /
`claim_expires_at` / `completed_at`. Plus a summary counting each state and
degradations.

Deliberately a projection, not the row: `claimed_by` is a hostname and PID that
means nothing to an instructor, and the model *endpoint* is infrastructure.

The endpoint is also now scoped to the cohort that owns the game. `IsInstructor`
checks only the role, so any instructor could read any game; this data carries a
model name and error text. Ownership follows the rule already used for student
accounts — the instructor who owns the course behind the game's section, with an
unowned course visible to any instructor, because `Course.instructor_id` is
genuinely NULL for the live pilot cohort and strict scoping would hide those
games from everyone.

### Walkthrough

`instructor-status-walkthrough.json`, one read against the isolated stack
(`globalstrat_replay`, game 37 round 1) staged into a mixed state:

```
instructor cc22_browser_inst: HTTP 200
student    student1:          HTTP 403
summary: {'total': 6, 'pending': 3, 'claimed': 1, 'succeeded': 1,
          'failed': 1, 'degraded': 1}
  briefing       succeeded  degraded=True  attempts=1/3 model=qwen-max tpl=v1
                 err=5/5 calls fell back to templates: All connection attempts…
  coaching       failed     degraded=False attempts=3/3 model=qwen-max tpl=v1
                 err=HTTP 500 upstream error
  coherence_rag  pending    degraded=False attempts=0/3
  compliance     pending    degraded=False attempts=0/3
  outlook        claimed    degraded=False attempts=0/3
  sc_event       pending    degraded=False attempts=0/3
no credential in response: True
```

## R2 — the unsafe configuration is gone, not defaulted off

`COMPETITION_RAG_AFFECTS_COHERENCE` used to let Phase 2 write
`RoundResultCoherence` — a field inside the competitive hash that
`services/grading.py` also reads. The write path is **removed**, not gated: a
setting a supported deployment can flip is not a safe configuration.

The flag name is kept only so a stack still setting it fails loudly.
`require_safe_rag_configuration()` runs before the resolution transaction
opens, so a misconfigured stack stops without taking a backup or a lock.
Silently ignoring the flag would be worse than either behaviour — an operator
who set it deliberately would believe retrieval was being graded when it is not.

RAG output remains instructor commentary (an `InstructorAlert` with
`source='narrative'`, outside the competitive section). Grading retrieval stays
a legitimate rules choice; it belongs in Phase 1, inside the transaction the
manifest hashes.

`CoherenceIsolationTests` proves all three legs in one test: flag unset, flag
set with the job run, and resolution attempted with the flag set.

## Focused checks run

| Check | Tests | Duration | Result |
|---|---:|---:|---|
| `NarrativeStatusEndpointTests` + `CoherenceIsolationTests` | 8 | 8.1 s | OK |
| `core.tests.test_auth_rounds` (round-control contract, directly affected) | 62 | 47.1 s | OK |
| `IsolationAndIdempotencyTests` + `CoherenceIsolationTests` (after the obsolete-test fix) | 6 | 70.8 s | OK |
| `core.tests.test_durable_narratives`, once from the frozen revision | **35** | **47.0 s** | **OK** |

One check failed and was diagnosed narrowly rather than with a broad suite:
`test_the_blend_can_be_restored_by_a_rules_decision`, written in the previous
submission, asserted that the flag still restored the competitive write. Its
premise is exactly what R2 removes, so it was deleted and only the affected
classes re-run before re-freezing.

**Not re-run**, per the audit: the SIGKILL drill, the live-provider matrix, the
determinism matrix, the operator concurrency matrix, and the full backend
suite.

## Changed files

```
backend/core/permissions.py                  instructor_can_access_game()
backend/core/views/round_control.py          narratives block + ownership check
backend/core/engine/coherence.py             competitive write removed
backend/core/services/narrative_jobs.py      require_safe_rag_configuration()
backend/core/engine/advance_round.py         fail closed before the transaction
backend/globalstrat/settings.py              flag documented as retired
backend/core/tests/test_durable_narratives.py  +8 tests, −1 obsolete
handoff_readiness_v2/narrative_status_walkthrough.py   harness (outside backend/)
```

No other runtime code was changed. The queue, worker, claim/lease, retry
command, migrations and manifest sections are untouched by this rework.

## Files

```
README.md                            this note
instructor-status-walkthrough.json   the walkthrough response and permissions
durable-narratives-suite.txt         the 35-test module run from 49d6514
MANIFEST.sha256                      sha256 of every file above
```
