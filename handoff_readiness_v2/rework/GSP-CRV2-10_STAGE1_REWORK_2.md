# GSP-CRV2-10 Stage 1 re-audit — FAIL / DOCUMENTATION REWORK 2

Audited revision: `75ed75b`

## Binary decision

**FAIL / REWORK. Stage 2 remains stopped.**

The new measurements satisfy the substantive probe requests. The blocker is now limited to contradictory canonical documentation. Do not rerun a probe or change runtime code.

## Blocking inconsistency

`evidence/decision-rules/STAGE1_PROBE_RECORD.md` appends a correct rework section but leaves the superseded claims in its current opening and original disposition:

- It still opens with “Each item below was submitted ... through both supported submission APIs.”
- Its original table still labels A4 as “gap, Stage 5 owns” rather than P1.
- It still states “Nothing was withdrawn.”
- It still states that `development_rounds: 0` could not be tested and repeats that limitation under “What Stage 1 does not claim.”
- It still describes the withdrawn feature-initialisation theory as ceiling-level free capability.

The findings register contains the same class of contradiction in its introductory paragraph: it says every Part A item was submitted through both APIs and “Nothing was withdrawn,” immediately before recording the withdrawal.

An appended correction does not replace a false current claim when both are presented as current guidance. A reader should not have to infer which half of the canonical record governs.

## Required correction

1. Rewrite the opening summary, disposition table, affected A1b/A1c/A3 passages, and “What Stage 1 does not claim” section so they state the final measured position directly.
2. Retain chronology where useful, but mark superseded first-pass statements explicitly as historical and false; do not leave them phrased as current conclusions.
3. Correct the V2-037–V2-044 register introduction so it agrees with the recorded withdrawal and the actual surface matrix.
4. Keep the raw JSON artifacts immutable. No probe, engine, suite, or later-stage run is required.
5. Regenerate the Stage 1 checksum inventory only if a covered artifact changes, verify it, commit the Markdown-only correction, and stop for re-audit.

## Verification budget

- Markdown consistency review.
- `git diff --check`.
- Stage 1 checksum verification.
- Clean tree.
- Zero tests, probes, suites, drills, or Stage 2 work.

## Acceptance for re-audit

The Stage 1 record and findings register must each yield one unambiguous final tally: **eight confirmed findings, one withdrawn theory; V2-041 P1; all applicable surfaces measured; `development_rounds: 0` measured; V2-044 bounded to write/default-close behavior.**
