# Competition launch checklist v2

- [x] Findings logged before repair.
- [x] Expanded deterministic envelope implemented/unit-tested.
- [x] LLM structurally isolated; no-key regression green.
- [x] Expanded replay: changed model, outage, second environment — game 32
      round 1, four runs, one competitive hash; `evidence/determinism/`.
- [x] Unordered-query entropy sweep closed — 93 sites ordered, 6 justified
      exemptions, AST guard + forward/reverse insertion test;
      `ORDERING_AUDIT.md`.
- [ ] Random/extremal exploit search, optimizer and sensitivity plots complete.
- [x] Deploy freeze and break-glass path documented.
- [ ] Fresh post-deploy backup restored on isolated stack.
- [x] Field pinned: 24 teams × 4 members / 96 sessions.
- [ ] Combined deadline burst + refresh + resolution at field and 3×.
- [ ] Actual load ceiling/failure mode measured.
- [ ] Post-close browser retrieval captured for both roles.
- [ ] All infrastructure failure modes exercised in isolation.
- [x] Submission audit evidence exposed in instructor tooling.
- [x] Six dispute procedures added to runbook.
- [x] Backend regression: 312/312 PASS, VM, 2026-08-28 (34 new determinism
      tests).
- [x] Frontend production build PASS (warnings), 2026-08-28.
- [ ] Frontend Jest: one suite blocked by Node 18 vs router v7 (requires Node 20).

Decision: **NO-GO for a prize competition at this checkpoint.** GSP-CRV2-01
(V2-001, V2-002) is closed with cross-environment evidence, but the remaining
v2 acceptance exercises — adversarial balance, load and failure modes,
post-close retrieval, durable narratives, audit integrity — are incomplete, and
v1 GO cannot substitute for them.
