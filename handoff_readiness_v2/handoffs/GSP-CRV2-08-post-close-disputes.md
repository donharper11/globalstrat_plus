# GSP-CRV2-08 — Post-close retrieval and dispute walkthrough

**Gates:** V2-E, V2-G  
**Owner:** browser-first QA/operator-tooling engineer

## Objective

Use the supported product UI and APIs to show that historical access works and
that an operator can answer the six defined dispute types. This is one coherent
playthrough, not an exhaustive permutation of every team, round, locale, empty
state, page, and export control.

## Representative completed game

Use the frozen integrated candidate and one completed game with at least three
rounds and three teams. Seed it so it includes a normal submission, a saved edit,
a late/deadline event, an operator action, and at least one default/empty value.
Reuse this game for all checks and, where practical, for CRV2-09.

## Browser walkthrough

1. **Student history:** use two representative teams. Retrieve an early and the
   final prior-round report after completion. Directly attempt one rival raw
   report/decision URL and verify the disclosure boundary.
2. **Instructor history:** inspect the seeded teams/rounds needed to demonstrate
   decisions, save history, server timestamps, actor, endpoint, request ID, hash,
   and submission origin. Use automated contract coverage—not repetitive browser
   clicking—to establish the same shape for all remaining rows.
3. **Six disputes:** answer each runbook case once: before-deadline claim,
   payload mismatch, rival access, rerun-after-final, operator change, and
   calculation proof. Record the supported screen/API/query and conclusion.
4. **Usability smoke:** exercise one bilingual switch, one empty/default case,
   one pagination boundary if pagination exists, and one export/copy action.
   Capture console/network failures for the walkthrough; pixel-perfect or
   cross-browser certification is out of scope.

If a walkthrough reveals a product failure, repair it and verify the failed path
with a focused automated test plus a repeat of that path. Do not replay already
passing disputes or rebuild the completed game unless the data contract changed.

## End-run assessment

Produce only the requested data dictionary for a future end-run report: source
model/API, retention, role visibility, and missing capture. Do not build a new
reporting feature.

## Acceptance and evidence budget

Each dispute is answerable/unanswerable with an exact supported path and evidence.
An unanswerable competitive claim remains a finding. Store a concise walkthrough
record, key screenshots/API exports, console/network log, and data dictionary in
`evidence/post-close-disputes/`.

- One completed-game setup.
- One browser walkthrough covering both roles and all six disputes.
- Targeted repeats only for paths that fail and are repaired.
- No full backend suite, load run, concurrency matrix, determinism replay, or
  provider drill. CRV2-09 owns the one integrated regression suite.
