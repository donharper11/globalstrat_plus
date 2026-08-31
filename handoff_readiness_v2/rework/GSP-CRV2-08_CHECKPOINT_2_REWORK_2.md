# GSP-CRV2-08 checkpoint 2 — REWORK 2

## Decision

**FAIL / REWORK**

Revision audited: `d39ce04`.

The shared ownership boundary passes its focused audit: the authoritative inventory covers 94 routes with no exemptions, the unrelated-instructor scan refuses all 65 reads and 37 writes with no mutation, and the focused boundary/operator-event tests pass 16/16. V2-032 may be recorded closed at `d39ce04`. The corrected dispute-5 repeat now proves both committed and genuinely rejected actions and is accepted.

## V2-033 disposition — adopted shared-pilot authorization, not a defect

The existing and previously audited rule deliberately treats a course with `instructor_id = NULL` as a shared pilot cohort visible to any instructor. CRV2-07 pinned that behavior because the live pilot genuinely uses it, and the V2-032 rework was explicitly instructed to preserve the same helper semantics.

Reclassify V2-033 as **withdrawn/not a defect under the adopted authorization rule**, not an open limitation. State the operational implication clearly: a prize-competition course that is not intended to be shared must have an instructor owner assigned before launch. Do not change the helper or rerun ownership evidence for this disposition.

## Blocking defect — V2-034 refusal auditing

V2-034 is **P1** and must be repaired before this checkpoint can pass.

All 37 non-owner mutation attempts are correctly refused before their views and change no state, but none leaves an audit record. CRV2-02 established that operator refusals are auditable; moving authorization to middleware must not make cross-cohort lifecycle attempts invisible.

### Required repair

At the shared game-scope boundary, record each refused mutation attempt in an append-only audit trail before returning 403. The record must contain:

- one request ID, identical to the response/correlation identity;
- actor identity;
- target game;
- HTTP method and resolved endpoint/route;
- server timestamp;
- rejected outcome and an ownership-refusal reason;
- no request payload, authorization token, password or other credential.

Use an existing suitable append-only audit model where its semantics fit, or add a narrowly scoped security-refusal event if necessary. Do not write a fake lifecycle action or imply the target state was reached. Avoid duplicate rows when a downstream view also audits a different refusal.

The refusal must remain fail-closed and must occur before competitive mutation. Audit persistence must not depend on a transaction that is rolled back by the refused action.

### Focused acceptance

Prove:

1. a foreign instructor’s representative POST/PATCH mutation returns 403, changes no game/round/team state, and creates exactly one rejected audit row;
2. response and audit carry the same request ID;
3. actor, target game, method, endpoint, timestamp and ownership reason are present;
4. no payload or credential is stored;
5. a foreign GET remains refused and follows the explicitly chosen read-audit policy without creating a misleading operator mutation event;
6. an owning instructor’s normal request is not double-audited by the middleware;
7. the complete 37-write ownership scan reports every refusal recorded and still reports zero unrefused writes and zero state mutations.

Repeat only the post-repair ownership scan. Do not repeat dispute 5 or any other browser path.

## Documentation reconciliation

- Mark V2-032 closed at `d39ce04` after audit.
- Close V2-034 only after the focused proof and scan pass.
- Apply the V2-033 disposition above.
- Update `GSP-CRV2-08_AUDIT_CHECKPOINT_2.md`; it currently still describes the pre-rework state and asks questions already ruled on.
- Keep V2-030, V2-031 and V2-035 closed with their existing evidence.

## Verification budget

Run only focused refusal-audit tests, directly affected middleware/audit contract tests, one post-repair 37-write ownership scan, static inventory checks, `git diff --check`, clean-tree verification and checksums.

Do not rebuild the fixture; repeat the six-dispute walkthrough or dispute 5; run full suites; or run load, determinism, concurrency, provider or failure drills. Step 6 remains stopped until this checkpoint passes.
