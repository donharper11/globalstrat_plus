# GSP-CRV2-03 audit decision — FAIL / focused rework

**Audited branch:** `crv2-03-durable-narratives`  
**Audited completion:** `a339782` (freeze/evidence revision `ef01237`)  
**Finding claimed closed:** V2-006  
**Decision:** **FAIL / REWORK**

The core V2-006 objective already works: jobs commit with Phase 1, a real
SIGKILL left a durable claim, a fresh worker recovered all six jobs, provider
failures degraded visibly, and the competitive hash remained unchanged. Do not
rebuild or re-certify that machinery.

Two narrow product gaps remain.

## R1 — Required narrative status is not visible to instructors

The model stores narrative type/state, degradation, model name, template
version, attempts, lease timestamps, and sanitized error, but no authenticated
instructor read surface exposes those fields. The existing management command is
adequate for operational retry; it does not satisfy instructor observability.

### Required repair

- Add one authenticated instructor-only read endpoint, preferably by extending
  an existing round-status/detail response rather than creating a new subsystem.
- Return narrative type, state, degraded, model name/version available from the
  provider configuration, template version, attempts/max attempts, sanitized
  error, and relevant timestamps.
- Add focused permission/response tests: owning instructor succeeds; student and
  unrelated instructor are denied; one degraded/failed fixture exposes the
  expected fields without a secret.
- Do not build a dashboard or new frontend workflow for this rework.

## R2 — Configuration can re-enable competitive Phase-2 writes

`COMPETITION_RAG_AFFECTS_COHERENCE=true` makes Phase 2 write hashed coherence
fields used by grading. That recreates V2-015/V2-016. Default-off does not make
the supported competition configuration safe.

### Required repair

- Remove the Phase-2 competitive mutation path, or fail startup/resolution closed
  when the legacy flag is enabled in a competition environment.
- Keep RAG output as instructor commentary only. A future rules choice to grade
  it is a separate Phase-1/certification change.
- Add one focused test proving the unsafe configuration cannot alter a grade or
  competitive manifest.

## Proportionate verification

1. Run the focused endpoint permission/contract tests.
2. Run the focused coherence isolation test.
3. Perform one short instructor API walkthrough showing a pending or degraded job
   and its sanitized metadata.
4. Freeze the repair and run the existing durable-narrative test module once.
5. Generate a small rework evidence note and checksum.

Do **not** rerun the real SIGKILL drill, live-provider matrix, determinism matrix,
operator race matrix, or full backend suite for this rework. The existing
evidence already proves those unaffected paths. The final integrated suite and
product playthrough belong to GSP-CRV2-09.

## Audit basis

The auditor reviewed the model, claim/run/retry services, worker, dispatch,
coherence setting/path, tests, and evidence, and reran
`core.tests.test_durable_narratives`: **28 tests passed in 40.035 seconds**.

