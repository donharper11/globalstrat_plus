# GSP-CRV2-03 — Durable Phase-2 narrative execution

**Finding:** V2-006 (P1)  
**Owner:** backend jobs/reliability engineer

## Objective

Replace fire-and-forget daemon-thread semantics with durable, idempotent,
operator-visible narrative work while preserving strict isolation from scoring.

## Requirements

- Persist a job/outbox record in the same transaction that commits Phase 1.
- A worker claims jobs with safe locking, bounded retries, timeout and terminal
  failure state. Restarting any web/job worker must resume eligible work.
- Idempotency key is game+round+narrative type/version; retries cannot duplicate
  messages or overwrite newer approved content.
- Model name/version, prompt/template version, attempt count and sanitized error
  are observable to instructors. Never store API secrets.
- Numeric results remain available when the job is pending/failed. Operator can
  retry narratives without rerunning scoring.
- Deployment documentation includes worker supervision and backlog alerting.

## Acceptance

Kill the web worker immediately after Phase-1 commit, kill the narrative worker
mid-call, return timeout/429/500/malformed output, and remove the API key. In all
cases competitive hashes remain unchanged; jobs recover or terminate visibly;
no duplicate narrative rows appear. Test restart recovery on an isolated stack.

Evidence: `handoff_readiness_v2/evidence/durable-narratives/`.
