# GSP-CRV2-01 — Deterministic reconstruction and replay

**Findings:** V2-001 (P0), V2-002 (P1)  
**Owner:** backend competition-integrity engineer  
**Blocks:** all later acceptance evidence

## Objective

Make one manifest sufficient to identify the exact competitive input and prove
all published and next-round competitive state, then demonstrate equality with
a changed model, no LLM, and a second environment.

## Required implementation

1. Review the uncommitted expanded output envelope field by field. Enumerate
   every model mutated in Phase 1 and every value read in a later round. Add any
   omitted competitive state; explicitly justify every exclusion.
2. Replace the metadata-only input manifest with canonical snapshots or durable
   content-addressed references for: accepted decision payloads, scenario and
   engine configuration, active market/event/modifier state, starting team and
   relevant per-team state, roster/participation, seed derivation inputs, code
   revision and schema migration state.
3. Version the manifest schema. Old manifests must remain readable and must not
   be silently interpreted as the new envelope.
4. Ensure canonical serialization is independent of surrogate sequence values,
   locale, timezone, dictionary/query iteration and Decimal representation.
5. Audit unordered Phase-1 querysets. Add explicit ordering wherever iteration
   can bind RNG draws, mutate state, decide ties, or accumulate non-associative
   numeric values.
6. Provide a supported replay command that verifies input integrity before
   mutation and prints per-section diffs on mismatch.

## Acceptance tests

- Unit tests enumerate expected input/output sections and reject schema drift.
- Forward/reverse row insertion tests cover every RNG-consuming or mutating
  loop identified by the audit.
- Restore one completed round and replay it:
  1. original LLM configuration;
  2. different model/endpoint returning deliberately different prose;
  3. unreachable endpoint/timeouts;
  4. a second container/VM with different timezone and locale.
- All four runs match the expanded competitive hash. Narrative hashes may differ
  and must be reported separately.
- Corrupt one decision payload, one scenario value and one carried-state value;
  each must fail verification before processing.

## Evidence

Store manifest JSON, environment fingerprints, command transcript, old/new
hashes, section diffs from negative tests and database dump checksums under
`handoff_readiness_v2/evidence/determinism/`.

## Done only when

V2-001 and V2-002 have tests, second-environment artifacts, documentation, and
reviewed closure entries. A same-process replay alone is insufficient.
