# GSP-CRV2-03 rework audit — FAIL / documentation-only rework

**Audited runtime freeze:** `49d6514b9b9723e8d4e6244bb58236a89a3551d6`  
**Evidence commit:** `348f9f0`  
**Decision:** **FAIL / REWORK**

The two runtime blockers are fixed and the focused verification passes. Do not
change runtime code and do not rerun tests or drills. The remaining blocker is
that the active release record and operator documentation contradict the code.

## Blocking inconsistency

`V2_FINDINGS_REGISTER.md` still marks V2-016 **Open**, assigns it to the rules
owner, and says the system currently lets an LLM change a grade outside the
certified envelope. `NARRATIVE_WORKER_OPERATIONS.md` still tells operators that
enabling `COMPETITION_RAG_AFFECTS_COHERENCE` blends the LLM score into the
published number.

At `49d6514`, neither statement is true:

- the Phase-2 competitive write was removed;
- RAG output is commentary only;
- setting the retired flag makes resolution fail closed before mutation.

Leaving the register open would incorrectly make the final audit report a P1
NO-GO, while the operator guide describes an option that now stops resolution.

## Required correction

1. Mark V2-016 repaired/closed by the `49d6514` rework. State the adopted rule:
   published coherence/grades use the deterministic formula; RAG is commentary.
2. Replace the obsolete “Disposition required for V2-016” section with a closure
   entry describing removal of the Phase-2 write and fail-closed retired flag.
3. Update `NARRATIVE_WORKER_OPERATIONS.md`: the flag is retired and must be
   unset; enabling it refuses round resolution. Do not say it enables blending.
4. Add a short rework completion addendum or update the CRV2-03 completion
   record so the current disposition and revision are discoverable. Preserve
   the original evidence files as historical artifacts; do not rewrite them.
5. Search active Markdown outside immutable evidence for other statements that
   claim the unsafe flag still enables blending, and correct current guidance.

## Verification budget

- Documentation search for stale active guidance.
- `git diff --check`.
- No backend/frontend tests, suites, SIGKILL, provider, replay, or race evidence.
- Commit the documentation correction; runtime source digest must remain
  `0c284a835d41f1a6b1ab0e1ea76b8e20cfe1e0032c13a6def75fd3e9f651003b`.

## Runtime audit evidence already passed

- Evidence checksums: 3/3 verified.
- Independent focused rerun: 8/8 tests passed in 8.322 seconds.
- Phase-2 coherence save removed; retired flag rejected before resolution.
- Owning instructor receives job status; student and unrelated instructor are
  denied; stored credentials remain redacted.
- The only production `calculate_coherence()` call explicitly uses
  `skip_rag=True`.

