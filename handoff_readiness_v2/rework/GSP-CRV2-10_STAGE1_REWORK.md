# GSP-CRV2-10 Stage 1 audit — FAIL / REWORK

Audited revision: `c20ebbb`

## Binary decision

**FAIL / REWORK. Do not begin Stage 2.**

The reproduced defects are credible, but Stage 1 has not met its own closure contract. This is an evidence-and-classification rework only. Do not repair runtime code, run broad suites, begin the optimizer, or perform later-stage work.

## Blocking reasons

1. **The required `development_rounds: 0` case was not measured.** The artifact records `team_already_owned_this_generation: true`; the submitted development was skipped and the before/after platform rows are identical. A `200` response is not evidence of activation timing. Stage 1 explicitly requires a zero-round generation and a two-round generation, with the round each becomes active.

2. **The record claims every item was exercised through both submission APIs, but its artifacts do not support that claim.** A1, A1b, A2 and A4 contain explicit per-type and whole-submission records. A1c contains one write, A3 contains one `submit_status` per arm, and D1 contains one `submit_status`. A6 uses roster/team-management APIs and is correctly not a decision-surface pair. Replace the blanket claim with a per-probe surface matrix and fill the missing decision-surface executions.

3. **The free initialization of five ceiling-level features is a distinct confirmed mechanism but is not cleanly registered.** Client-controlled price and automatic initialization of unnamed features are different causes and may need different repairs and acceptance tests. Register the initialization mechanism before any repair, with its own ID/severity/owner, or explicitly split it as a separately testable subfinding under V2-037. Do not leave it only in narrative prose.

4. **V2-041 is internally inconsistent.** The submission calls these “eight findings” while classifying V2-041 as a “gap” with no severity. Stage 1 requires a severity for each confirmed finding. Either assign and justify a severity while keeping it in the findings register, or classify it as a planned Stage 5 rule requirement rather than one of the eight findings. Do not describe it both ways.

5. **V2-044 is broader than its proof.** The artifact proves that one supported write accepted a foreign `team_platform`; its lock attempt stopped earlier on a missing budget. Exercise the other write surface and a complete lock attempt, or narrow the finding text to exactly what is proven and carry the remaining lock/engine behavior as explicit repair acceptance work.

## Required rework

1. Build the smallest isolated fixture in which the subject team does not already own the `development_rounds: 0` generation. Exercise it through both supported decision APIs and record submission response, resulting decision row, processing result, and exact activation round. Preserve the `development_rounds: 2` control.
2. Add a compact surface-coverage table for A1, A1b, A1c, A2, A3, A4 and D1. For each, name the endpoint, status, persisted row/result, and disposition. Re-run only missing surface cases. Mark A6 not applicable with its actual roster/team-management paths.
3. Reconcile V2-037/free feature initialization and V2-041 classification as described above.
4. Bound or complete V2-044 as described above.
5. Correct the Stage 1 record and findings register, regenerate only the Stage 1 checksum inventory, commit, and stop for re-audit.

## Verification budget

- Use the existing isolated stack and focused probe harnesses.
- No runtime repair.
- No full backend/frontend suite.
- No determinism, concurrency, load, browser, tournament, or optimizer run.
- No Stage 2–5 evidence.
- Verify clean tree, `git diff --check`, and the Stage 1 checksum inventory.

## Acceptance for re-audit

Stage 1 may pass only when every mandatory probe has a measured disposition, every applicable decision probe has evidence from both supported write surfaces (or the finding is explicitly narrowed), every confirmed mechanism is registered before repair, and every registered finding has an unambiguous classification and severity.
