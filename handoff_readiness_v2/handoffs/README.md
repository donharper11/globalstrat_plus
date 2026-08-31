# GlobalStrat+ competition-readiness v2 remediation handoffs

These handoffs convert the v2 findings and incomplete acceptance gates into
implementation-ready work. They are specifications, not proof that the work is
complete.

## Binding reading

Every owner must read:

1. `handoff_readiness_v2/GlobalStrat_Competition_Readiness_v2.md`
2. `handoff_readiness_v2/V2_FINDINGS_REGISTER.md`
3. `handoff_readiness_v2/DETERMINISM_BOUNDARY.md`
   (owners of 10–13 also read
   `handoff_readiness_v2/RULES_AND_CALIBRATION_ASSESSMENT.md`, and the BECSR
   prior art it cites — those rules were litigated to a ruling once already, in
   code, and the reasoning is preserved in the module docstrings)
4. `specs/STANDING-DISCIPLINE.md`
5. `handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`
6. This file and the assigned handoff.

Work only in `/home/ubuntu/projects/globalstrat+`. All destructive, load and
failure injection must use disposable isolated stacks. Production is read-only.
Log new findings before repairing them. Do not close a verification gate from
code inspection alone.

## Cost control is part of correctness

Follow `EXECUTION_PROTOCOL.md`: inventory before implementation; never run
concurrent Django suites against one database; use cheap harness settings while
coding; freeze a clean commit before expensive evidence; run the full suite and
release-scale evidence once per freeze candidate. Repeated certification runs
are not a substitute for focused diagnosis.

## Baseline warning

The VM working tree contains uncommitted v2 repairs for V2-001, V2-003,
V2-004, V2-005 and V2-008. The first owner must preserve them and establish a
named integration baseline before parallel work. Unrelated `gap_closing/` files
pre-existed and are out of scope.

## Dispatch sequence

**Handoff numbers are identifiers, not positions.** They were assigned when each
handoff was authored and they never move, because completion reports, rework
reports, evidence records and the findings register cite them by number — the
open finding V2-011 names GSP-CRV2-09 as its owner, and four handoffs deferred
their integrated regression to it by name. Renumbering to tidy the sequence
would mean editing frozen records to fix an appearance.

So the list below is the running order, and it is the only thing that says what
runs when. 03/04/05 already share one step, 06–08 may build harnesses ahead of
their slot, and **09 runs last by design** — it is the re-audit, so it certifies
whatever the numbers before it produced, including the later-numbered 10–13.

1. **GSP-CRV2-01** — deterministic reconstruction and cross-environment replay
2. **GSP-CRV2-02** — fail-closed concurrent operator actions
3. In parallel after 01/02 interfaces settle:
   - **GSP-CRV2-03** — durable Phase-2 narrative execution
   - **GSP-CRV2-04** — database-enforced audit integrity and read evidence
   - **GSP-CRV2-05** — supported frontend toolchain and green tests
4. **GSP-CRV2-06** — adversarial optimizer and sensitivity analysis
5. **GSP-CRV2-07** — pinned load ceiling and infrastructure failure drills
6. **GSP-CRV2-08** — post-close retrieval and dispute browser proof
7. **GSP-CRV2-10** — decision rules and the economic legal space
8. **GSP-CRV2-11** — calibration: economy, starting field, stakeholder response
9. **GSP-CRV2-12** — player-facing language sweep
10. **GSP-CRV2-13** — integrated bug sweep
11. **GSP-CRV2-09** — independent final re-audit and launch decision

Handoffs 06–08 may build harnesses earlier, but their final evidence must use
the integrated release candidate produced by 01–05. Handoff 09 must be owned by
someone who did not implement 01–08 or 10–13.

Each builder certifies only their assigned handoff. Do not regenerate previous
handoffs' expensive evidence after every merge; GSP-CRV2-09 performs the single
integrated regeneration on the final release candidate.

## The 10–13 block, and why it precedes 09

Added 2026-08-30 from `RULES_AND_CALIBRATION_ASSESSMENT.md`. Handoffs 01–08 ask
whether the *platform* holds up. They do not ask whether the *rules of play* are
right and hold — GSP-CRV2-06 came closest, but its legal-space gate asked whether
a decision value was in range, not whether a field naming a price agrees with the
price the scenario authored.

These four run **before** 09 rather than after it, because 09 is the GO/NO-GO and
its verdict rules make any open P0 a NO-GO. The assessment's suspected P0 — the
price of R&D is set by the client — would either be found by 09, or, worse, not
be found by 09 and be found instead by a team playing for a prize. A GO issued
against rules that are about to change is a GO that has to be withdrawn.

**Entry condition: GSP-CRV2-08 through its audit gate.** CRV2-08 is generating
walkthrough evidence and repairing product code inside the same candidate these
handoffs would mutate, and the protocol is explicit that a runtime change after
evidence starts invalidates that evidence. Fifteen rework documents across
handoffs 01–07 say audit sends work back as a matter of course, so "CRV2-08 is
nearly done" is not an entry condition. GSP-CRV2-10 Stage 1 — probe-only,
commits no runtime code — may run in parallel under EXECUTION_PROTOCOL Phase 0
with a separately named database and run-time port claiming.

They are sequential among themselves and the order is load-bearing:

- **10 before 11** — do not calibrate rules known to be broken. A dominant line
  found under client-priced R&D says nothing about the game that ships. This is
  GSP-CRV2-06's own Stage-1 doctrine, applied one level up.
- **11 before 12** — recalibration changes the numbers and thresholds that
  student-facing messages quote.
- **12 before 13** — the sweep walks the product a participant sees, including
  its words.
- **13 before 09** — 09 runs the single integrated regression, once, on what the
  block produced.

Consequence to plan for: where 10 and 11 change a boundary that 01–08 certified,
that evidence covers its own named commit and not the new one. 09's Phase 1
already governs this — accept intact evidence where the runtime boundary did not
change, require a focused regression where it did. GSP-CRV2-06's tournament
result is the most exposed: its strongest-strategy finding is evidence for its
own scenario revision, not automatically for a recalibrated one.

Four rulings are requested at the end of the assessment. 10's Stage 1 can run
without them; nothing after Stage 1 can.

## Universal completion report

Each owner records: baseline revision, changed files/migrations, tests and exact
commands, isolated-stack identity, evidence paths/hashes, findings opened or
closed, rollback notes, unresolved risks, and duration/count of every full suite
or release-scale harness run. “Tests pass” without counts and artifacts is not
a completion report.
