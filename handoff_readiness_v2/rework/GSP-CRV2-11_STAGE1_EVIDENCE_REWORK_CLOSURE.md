# GSP-CRV2-11 Stage 1 runtime evidence audit — rework closure

Rework revision audited: `f3a8954`.

## Decision

**PASS — the Stage 1 growth-provenance documentation rework is accepted.**

The commit is constrained to the two required evidence artifacts:

- `evidence/calibration/STAGE1_MEASUREMENTS.md`
- `evidence/calibration/independent_bass.py`

The historical comparison is now consistently labelled **pre-CRV2-11**, and
compounding is consistently labelled the **current shipped runtime**. The
standalone verifier independently produced the corrected headings and the
recorded round-1, round-5, and round-10 values. `git diff --check` passes.
Neither saved runtime-evidence JSON file changed.

This closes the provenance contradiction identified in
`GSP-CRV2-11_STAGE1_EVIDENCE_REWORK.md`; no runtime, YAML, migration, baseline,
or Stage 2 change was introduced.

## Programme status remains deliberately narrow

This is **not** a CRV2-11 completion or a final-certification decision. The
competent-field measurement remained outstanding when this Stage 1 closure was
written. The later product-allocation re-audit accepted it; round-zero parity
is the only starter-parity requirement.
CRV2-08's completion report also remains a required input before CRV2-12 can
be finally certified.
