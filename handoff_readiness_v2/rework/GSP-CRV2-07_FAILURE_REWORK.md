# GSP-CRV2-07 failure/recovery — REWORK

## Decision

**FAIL / REWORK**

Revision audited: `16d49fc`

The seven-stage failure and restore walkthrough is accepted as evidence for those mechanisms. The handoff cannot pass while an ordinary accepted student payload can deterministically prevent the competition round from resolving.

## Blocking defect: duplicate product names are accepted and stall resolution

The submitted evidence proves both reachable cases through the student API:

1. two `DecisionProductCreate` rows in one payload with the same `product_name`; and
2. a new product whose name equals a `TeamProduct` already owned by that team.

Both writes return HTTP 200. The first is then refused by the input-manifest natural key; the second reaches Phase 1 and is refused by the output-manifest natural key. The shared transaction prevents corruption, but every retry fails and the entire round remains open until somebody edits competition data directly in PostgreSQL.

Rollback integrity is not an acceptable substitute for validating a normal student decision. Manual SQL recovery is not an acceptable launch disposition.

Register this as a blocking finding owned by CRV2-07 and close it before resubmission.

## Required correction

1. Enforce product-name uniqueness on every supported decision write surface, including:
   - duplicates within the submitted `product_creates` list; and
   - collision with an existing product owned by the same team.
2. Return an actionable HTTP 400 identifying `product_name`; do not accept the write and defer failure to manifest generation.
3. Apply the check to the fully assembled list/context so both the whole-submission endpoint and the per-type `.../products/` endpoint enforce the same rule. Prefer one shared validator/ListSerializer rather than duplicated view logic.
4. Preserve replacement semantics: after a rejected payload, the previously valid persisted decision set must remain unchanged. A student must be able to submit a corrected unique list through the API and then resolve the round without database intervention.
5. Keep the manifest natural-key refusals as defence in depth for invalid rows introduced outside supported APIs. Do not weaken or remove them.
6. Update the findings register and CRV2-07 report. Remove the manual-SQL procedure as the normal recovery for this defect; it may remain only as historical evidence tied to `16d49fc`.

Use the manifest's existing exact product-name identity after normal serializer string normalization. Do not introduce a new case-folding or fuzzy-name competition rule as part of this repair.

## Focused acceptance proof

Add endpoint-level regressions proving:

- the per-type endpoint rejects two same-name creates with 400 and writes neither invalid replacement row;
- the whole-submission endpoint rejects the same payload for the same reason;
- both endpoints reject a create matching an existing team product;
- two distinct names are accepted (control);
- the same name owned by a different team does not collide (scope control);
- after each rejection, a corrected unique payload is accepted and the affected round resolves;
- direct/ORM-inserted invalid state is still refused by the manifest/engine boundary without partial competitive results.

## Proportionate verification budget

Run only:

- the new focused product-name API/round-resolution tests;
- directly affected serializer/decision endpoint contract tests;
- manifest focused tests only if manifest code changes (it should not need to);
- static inventories if changed, `git diff --check`, and evidence checksums.

Do **not** rerun either load profile, the 96-user authentication drive, readiness walkthrough, seven-stage failure walkthrough, concurrency/determinism matrices, narrative drills, or the full backend suite. This is deterministic validation on a bounded request path; repeating capacity certification would be over-certification.

## Resubmission

Return the repair revision, finding identifier/disposition, changed files, focused test results, clean-tree status, and checksum result. The previously recorded load, authentication, readiness, failure-injection, and deploy/restore evidence may be carried forward by revision with no regeneration.
