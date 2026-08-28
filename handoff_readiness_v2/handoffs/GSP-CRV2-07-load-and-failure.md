# GSP-CRV2-07 — Load ceiling, recovery, and infrastructure failures

**Gates:** V2-C, V2-D, V2-F  
**Owner:** reliability/performance engineer

## Test field

Baseline is 24 teams × 4 members = 96 concurrent sessions. Model all sessions
refreshing on a slow-link profile, all teams saving/locking in the final 60
seconds, and resolution activity while authenticated users remain active.

## Load protocol

Run baseline, 3×, then step upward until a predefined degradation/failure
threshold is crossed. Use separate identities and realistic payloads. Report
throughput, p50/p95/p99/max, error/status distribution, DB pool/locks, CPU,
memory and disk. Reconcile attempted/acknowledged writes against immutable audit
events and final submissions: zero unexplained loss/duplication.

## Failure protocol

On disposable PostgreSQL/application stacks exercise DB loss mid-resolution,
backend restart, LLM timeout/error, disk full during dump, operator conflicts,
app/DB clock skew, session expiry mid-submit, and frontend/backend partition at
deadline. For each assert fail-closed state, recoverability and operator-visible
diagnostic. Integrate GSP-CRV2-02/03 controls rather than retesting old code.

## Recovery/deploy protocol

Confirm old revision dumps are rejected, break-glass override is audited and
requires compatibility review, and a fresh post-deploy backup restores/replays.
Verify the hard deploy-freeze runbook wording from a clean operator procedure.

## Acceptance evidence

Store harness source/config, environment capacity, raw results, graphs, DB
reconciliation, dump hashes and recovery transcripts in `evidence/load-failure/`.
State the observed ceiling and failure mode. “3× passed” without a ceiling fails.
