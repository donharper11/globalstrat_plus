# GSP-CRV2-10 — integrated Stage 3/4 closure

Runtime revision: `04e3f87` (frozen before evidence)
Evidence: `handoff_readiness_v2/evidence/decision-rules/stage34-closure/`

Submitted for re-audit. **No finding is marked closed here** — that is the
auditor's call. This packet is the reconciliation the closure needs, at one
current revision, with every citation resolvable.

---

## 1. What closure had to establish

Stage 3B removed the route teams used to improve a product. Stage 4 added the
replacement. **The two are load-bearing for each other**, and that is the thing
no per-item suite tests: each one passes on its own while a team could still be
stranded between them.

`test_stage34_closure` walks the journey end to end, across rounds, through the
engine:

| Round | What happens | Which stage it proves |
|---|---|---|
| 1 | the upgrade a team used to buy is refused | 3B |
| 1 | a new generation is requested, priced, funded; the clock starts in the funding round | 3A (V2-039, V2-045, V2-046, V2-047) |
| 2 | still in development — the authored lead time is served | 3A (V2-040) |
| 3 | ready; the product re-bases onto it | 4 |
| 3 | the write-off is charged, once | 4 (V2-049) |
| 1–2 | still resolve to the platform they were scored against | 4 (V2-050) |

Plus two controls: a stored upgrade still cannot reach the engine, and a team
that never switches is untouched — the new route is available, not compulsory.

**Six tests. The destination is asserted, not only the refusal.** A closure
packet that only proved the old route was shut would be consistent with a game
in which nobody can improve anything.

## 2. Findings reconciled

Each is implemented, has focused tests, and is now also exercised by the
integrated journey. Revisions are post-rewrite and resolve today (see §4).

| Finding | Sev | Implemented | Focused proof | In the journey |
|---|---|---|---|---|
| V2-039 unlock gate at lock only | P1 | `bfd5a26` | `UnlockGateTests` (4) | request accepted only when unlocked |
| V2-040 `development_rounds` off by one | P1 | `bfd5a26` | `PlatformTimingTests` (5) | round 2 still in development |
| V2-044 write path accepts another team's platform | P1 | `bfd5a26` | `PlatformOwnershipTests` (4) | ownership precedes the freeze check |
| V2-045 auto-funding spends the same cash twice | P1 | `1f68f5e` | `AggregateFundingTests`, `ConflictedDraftAllocatorTests` (9) | one funded platform, one charge |
| V2-046 duplicate generation requests | P1 | `5ccb9f8` | `DuplicateGenerationTests` (8) | one platform per generation |
| V2-047 already-held generation accepted then ignored | P1 | `2195a0b` | `HeldGenerationTests` (9) | — |
| V2-049 write-off recorded but not charged | P1 | `301bb64` | `WriteOffAccountingTests` (8) | charged once, in round 3 only |
| V2-050 later switch rewrites past brand awareness | P0 | `301bb64` | `BrandAwarenessReplayTests` (3) | rounds 1–2 unchanged after the switch |
| V2-051 cross-game competitive writes | P0 | `301bb64` | `RebaseGameBindingTests` (6) | — |
| V2-052 schema definition chain overwritten | P1 | `105ad44` | `SchemaProvenanceTests` (4) | — |

Two carry no journey column because they are boundary properties rather than
steps in it: V2-047 is a persisted-state refusal and V2-051 is a routing
refusal. Both are covered by their focused suites and by the engine-boundary
control in the journey.

## 3. Verification

Run once from clean revision `04e3f87`: **304 distinct, 304 executed, `OK`**,
across 51 classes. Per-class counts in `per-class-counts.txt`.

- `makemigrations --check --dry-run` → `No changes detected`
- `dump_manifest_schema --check` → `Manifest schema inventory is current.`
- `dump_read_inventory --check` → `Read inventory is current.`

The determinism boundary is inside this set: `test_manifest_determinism` (56),
including `team_product_platform_history` in the enumerated envelope and the
ordering guard extended to the resolution services.

## 4. The citation chain, repaired — V2-054

Closure resolved the register's citations rather than reading them, and **every
one failed**. The V2-048 rewrite changed the SHA of every commit carrying the
credential and of every descendant, which is all of them, so each
`implemented at X` named a commit this repository cannot find.

Fixed for the six documents this closure rests on — the register and the Stage
2, 3A, 3B, 4 and Stage 4 rework checkpoints — **55 citations translated, all
now resolving.** Registered as V2-054, with the ~45 remaining documents left to
their owners: they are other handoffs' closed records.

Frozen `evidence/` files keep their pre-rewrite SHAs deliberately. They were
correct when written and are covered by `CHECKSUMS.json`; editing them would
falsify a record and break its checksum to fix a cosmetic mismatch.

The translation depended on `.git/filter-repo/commit-map`, which is untracked,
unpushed, and lost to a fresh clone — and the pre-rewrite bundles that could
regenerate it are scheduled for deletion on **2026-09-18**. It is now exported
to `evidence/v2-048/commit-map.md` (434 mappings), so V2-054 stays fixable
after that date.

## 5. Out of scope, by instruction

- **V2-053** — Ruling 1 leaves R&D investment charged and scored but
  mechanically inert. **Not touched.** It changes what R&D spend *means*, so it
  is the rules owner's decision, not a builder's. Two costed options are in the
  register.
- **V2-048 residual** — access-log review and `CREATEROLE`/`CREATEDB`
  reduction. **A release gate, not a coding task.** The credential is rotated,
  revoked, verified refused, and purged from history.

## 6. What this packet does not claim

- No finding is closed; all ten remain implemented-pending-closure.
- Stage 3B invalidates the strategy space GSP-CRV2-06's tournament searched.
  Its strongest-strategy result is evidence for the game as it was, and
  **CRV2-09 must not accept it as current** (recorded in
  `GSP-CRV2-10_RULE_DECISIONS.md`).
- No full suite, browser, concurrency, load or tournament run.
