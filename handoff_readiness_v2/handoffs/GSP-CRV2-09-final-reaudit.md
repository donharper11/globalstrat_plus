# GSP-CRV2-09 — Independent v2 final re-audit

**Status:** Run only after GSP-CRV2-01 through 08 are integrated and deployed to
an isolated release-candidate environment.  
**Owner:** independent competition-readiness auditor

## Purpose

Decide technical readiness from raw evidence. Do not implement fixes during this
audit. Log any new finding and issue a targeted follow-up handoff.

## Required audit

1. Verify baseline tag/revision, clean migration state and build provenance.
2. Re-run the determinism matrix, including second environment and LLM outage.
3. Inspect optimizer source data/seeds and reproduce a sample plus strongest line.
4. Re-run pinned field and 3× load; confirm the documented ceiling/failure mode.
5. Sample every failure drill and repeat at least DB loss, worker restart and
   concurrent operators independently.
6. Complete post-close student/operator browser retrieval and all disputes.
7. Reverify v1 register and repaired V2-001/003/004/005/008 on the integrated
   build, not the branch where each was fixed.
8. Confirm runbooks/checklists match actual commands and UI.

## Verdict rules

- P0 open or required acceptance evidence missing: **NO-GO**.
- P1 open: **NO-GO** unless explicitly accepted by named rules/operations owner
  with a tested mitigation that cannot affect competitive outcome.
- PASS requires artifact paths, hashes, test counts and reproducible commands.
- Human volunteer/sign-off activities remain separate and cannot repair a failed
  technical gate.

Deliver `V2_FINAL_READINESS_REPORT.md`, reconciled findings register, final
launch checklist and immutable evidence index.
