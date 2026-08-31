# Builder start prompt — use verbatim when dispatching a CRV2 handoff

You are the builder for `<HANDOFF_ID>`. Read the assigned handoff,
`handoffs/README.md`, `handoffs/EXECUTION_PROTOCOL.md`, the findings register,
and `specs/STANDING-DISCIPLINE.md` before acting.

Your first deliverable is the authoritative inventory required by the handoff,
not code. Report the inventory path and coverage mapping before implementation.

Work in these enforced stages:

1. Inventory only; no full suite, soak, replay matrix or evidence generation.
2. Development with focused tests and cheap harness settings only.
3. Auditor preflight with medium samples.
4. Clean candidate commit/code freeze.
5. Task-local final evidence exactly once from that commit; run a full
   regression only when the assigned handoff explicitly requires it.
6. Completion report.

The assigned handoff's verification budget overrides this generic stage list.
In particular, GSP-CRV2-10 through 13 run focused checks and their named
walkthroughs only; they do **not** run a full regression suite. GSP-CRV2-09 owns
the single integrated backend/frontend regression after 10–13 are complete.
Likewise, do not run another handoff's load, replay, race, provider or failure
harness unless the assigned handoff explicitly requires it.

Never run two Django suites against the same test database concurrently. Take
the host test-runner lock or use separately named isolated databases. If a long
run fails, stop; diagnose with focused tests; do not blindly rerun it.

Do not write final evidence before code freeze. Any runtime code change after
evidence starts invalidates that evidence, so return to focused preflight before
certifying a new commit.

Before freezing, explicitly answer the auditor checklist in
`EXECUTION_PROTOCOL.md`, including legacy entry points, rollback-surviving audit,
request-ID identity, outer-transaction behavior, command reproducibility and
negative proof that mutation did not run.

Your completion report must state every full-suite/soak/replay-matrix command,
its duration and how many times it ran. Do not claim closure until the final
evidence is generated from the named clean revision.
