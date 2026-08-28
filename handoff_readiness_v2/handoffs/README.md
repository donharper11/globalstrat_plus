# GlobalStrat+ competition-readiness v2 remediation handoffs

These handoffs convert the v2 findings and incomplete acceptance gates into
implementation-ready work. They are specifications, not proof that the work is
complete.

## Binding reading

Every owner must read:

1. `handoff_readiness_v2/GlobalStrat_Competition_Readiness_v2.md`
2. `handoff_readiness_v2/V2_FINDINGS_REGISTER.md`
3. `handoff_readiness_v2/DETERMINISM_BOUNDARY.md`
4. `specs/STANDING-DISCIPLINE.md`
5. This file and the assigned handoff.

Work only in `/home/ubuntu/projects/globalstrat+`. All destructive, load and
failure injection must use disposable isolated stacks. Production is read-only.
Log new findings before repairing them. Do not close a verification gate from
code inspection alone.

## Baseline warning

The VM working tree contains uncommitted v2 repairs for V2-001, V2-003,
V2-004, V2-005 and V2-008. The first owner must preserve them and establish a
named integration baseline before parallel work. Unrelated `gap_closing/` files
pre-existed and are out of scope.

## Dispatch sequence

1. **GSP-CRV2-01** — deterministic reconstruction and cross-environment replay
2. **GSP-CRV2-02** — fail-closed concurrent operator actions
3. In parallel after 01/02 interfaces settle:
   - **GSP-CRV2-03** — durable Phase-2 narrative execution
   - **GSP-CRV2-04** — database-enforced audit integrity and read evidence
   - **GSP-CRV2-05** — supported frontend toolchain and green tests
4. **GSP-CRV2-06** — adversarial optimizer and sensitivity analysis
5. **GSP-CRV2-07** — pinned load ceiling and infrastructure failure drills
6. **GSP-CRV2-08** — post-close retrieval and dispute browser proof
7. **GSP-CRV2-09** — independent final re-audit and launch decision

Handoffs 06–08 may build harnesses earlier, but their final evidence must use
the integrated release candidate produced by 01–05. Handoff 09 must be owned by
someone who did not implement 01–08.

## Universal completion report

Each owner records: baseline revision, changed files/migrations, tests and exact
commands, isolated-stack identity, evidence paths/hashes, findings opened or
closed, rollback notes, and unresolved risks. “Tests pass” without counts and
artifacts is not a completion report.
