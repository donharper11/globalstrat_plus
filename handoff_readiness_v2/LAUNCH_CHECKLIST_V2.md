# Competition launch checklist v2

- [x] Findings logged before repair.
- [x] Expanded deterministic envelope implemented/unit-tested.
- [x] LLM structurally isolated; no-key regression green.
- [x] Expanded replay: changed model, outage, second environment — game 37
      round 1, four runs from one verified source tree, one competitive
      hash, four narrative hashes; `evidence/determinism/`.
- [x] Unordered-query entropy sweep closed — 168 sites ordered (93 inline, 75
      via a local name, the latter found by a failing replay: V2-012), 6
      justified exemptions, AST guard + forward/reverse insertion test;
      `ORDERING_AUDIT.md`.
- [x] Random/extremal exploit search and bounded sensitivity characterisation
      complete — legal-space screen, grouped sweeps and tournament; V2-018 and
      V2-020 through V2-025 closed; `GSP-CRV2-06_COMPLETION_REPORT.md`.
- [x] Operator concurrency fail-closed — 0 of 214 registered mutating routes
      unguarded, 1200 races, 0 deadlocks, 0 5xx;
      `OPERATOR_CONCURRENCY_MATRIX.md`.
- [x] Phase-2 narratives durable and recoverable — jobs committed with the
      numbers, SIGKILL drill recovers, competitive hash unmoved;
      `NARRATIVE_WORKER_OPERATIONS.md`.
- [ ] Narrative worker supervised in the competition stack (systemd unit
      documented; deployment action outstanding).
- [x] Deploy freeze and break-glass path documented.
- [x] Fresh pre-resolution backup restored on an isolated stack; tampered and
      out-of-root dumps refused; CRV2-07 failure walkthrough.
- [x] Field pinned: 24 teams × 4 members / 96 sessions.
- [x] Field and 3× traffic profiles carried with reconciled writes — 96 and
      288 sessions, p95 90.1 ms / 175.0 ms, zero 5xx, transport failures,
      deadlocks or lost writes; `GSP-CRV2-07_LOAD_REPORT.md`.
- [ ] Combined deadline burst + refresh + Phase-1 resolution under load. CRV2-07
      measured refresh/save/lock traffic at field and 3× but explicitly did not
      drive instructor resolution under load; do not relabel that evidence.
- [x] Supported load ceiling measured at at least 3× field; staged
      authentication procedure and session-readiness gate proven.
- [x] Post-close browser retrieval captured for both roles; all six disputes
      answerable through supported paths; `GSP-CRV2-08_COMPLETION_REPORT.md`.
- [x] Failure and recovery walkthrough complete — concurrent process, restart,
      deadline refusal, backup failure, database loss and verified restore;
      `GSP-CRV2-07_FAILURE_REPORT.md`.
- [x] Submission audit evidence exposed in instructor tooling.
- [x] Six dispute procedures added to runbook.
- [x] Backend regression: 387/387 PASS, VM, 2026-08-28, from frozen commit
      `ef01237` (50 determinism + 31 concurrency + 28 durable-narrative tests).
- [x] Resolution refuses an unidentified build; replay refuses a source-tree
      mismatch before mutation.
- [ ] Competition stack sets `COMPETITION_REQUIRE_CLEAN_BUILD=true` (or
      `ENVIRONMENT=production`) — deployment action, not yet done.
- [x] Frontend production build PASS (warnings), 2026-08-28.
- [x] Frontend clean install, Jest and production build pass on the supported
      toolchain; V2-009 closed by GSP-CRV2-05.
- [ ] Decision rules and economic legal space certified (GSP-CRV2-10).
- [ ] Economy, starting-field and stakeholder calibration certified
      (GSP-CRV2-11).
- [ ] Player-facing bilingual language sweep complete (GSP-CRV2-12).
- [ ] Integrated breadth bug sweep complete (GSP-CRV2-13).
- [ ] Independent integrated re-audit, single backend/frontend regression and
      final GO/NO-GO complete (GSP-CRV2-09 — runs last).

Decision: **NO-GO for a prize competition at this checkpoint.**

Closed with evidence from named revisions: GSP-CRV2-01 (V2-001, V2-002,
V2-012, V2-013, V2-014), GSP-CRV2-02 (V2-004), GSP-CRV2-03 (V2-006, V2-015,
V2-016), GSP-CRV2-04 (V2-007), GSP-CRV2-05 (V2-009), GSP-CRV2-06
(V2-018, V2-020 through V2-026, V2-028; V2-019 and V2-027 withdrawn),
GSP-CRV2-07 (V2-029), and GSP-CRV2-08 (V2-030 through V2-032 and V2-034
through V2-036; V2-033 withdrawn under the shared-pilot rule).

Outstanding: GSP-CRV2-10 through 13, followed by GSP-CRV2-09's final integrated
re-audit; V2-017, which leaves 216 Django admin write routes outside the audited
lifecycle boundary; and three deployment actions — supervise the narrative
worker, set `COMPETITION_REQUIRE_CLEAN_BUILD=true` (or production environment),
and run the application as a non-owner database role so it cannot drop its own
audit guards. V2-010 and V2-011 are closed at `8ddd983`; they are no longer a
rules blocker. v1 GO and evidence from the pre-10–13 ruleset cannot substitute
for the final integrated verdict.
