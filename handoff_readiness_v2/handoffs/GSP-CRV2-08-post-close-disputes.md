# GSP-CRV2-08 — Post-close retrieval and dispute browser proof

**Gates:** V2-E, V2-G  
**Owner:** browser-first QA/operator-tooling engineer

## Objective

Prove both roles retain correct historical access after advance/completion and
that an operator can answer all six disputes from supported tooling.

## Browser protocol

On an isolated completed multi-round game:

- As each team, retrieve every own prior-round report after advance and after
  game completion. Attempt another team's raw report/decision URL and prove the
  intended denial/disclosure boundary.
- As instructor, select every team and round and verify decisions, save history,
  server timestamps, actor, endpoint, request ID, hash and submission origin.
- Exercise the exact six runbook procedures: before-deadline claim, payload
  mismatch, rival access, rerun-after-final, operator change, calculation proof.
- Verify navigation, bilingual labels, empty/defaulted cases, pagination and
  export/copy behavior. Capture console and network logs.

## End-run assessment

Produce a data dictionary for a future end-run report: source model/API,
retention, role visibility and missing capture. Do not build the report.

## Acceptance

Each dispute ends answerable/unanswerable with exact screen/query and evidence.
An unanswerable competitive claim remains a finding; it cannot be converted to
PASS by adding runbook prose. Store artifacts in `evidence/post-close-disputes/`.
