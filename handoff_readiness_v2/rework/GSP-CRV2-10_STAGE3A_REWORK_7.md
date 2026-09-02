# GSP-CRV2-10 Stage 3A seventh re-audit — RUNTIME PASS / DOCUMENTATION REWORK 7

Audited runtime revision: `f348d24`  
Audited checkpoint revision: `1c99796`

## Verdict

**The Rework 6 runtime repair passes. The submitted checkpoint does not pass
as an accurate canonical record. Stage 4 remains blocked pending a
documentation-only repair.**

Do not change runtime code or regenerate the focused test evidence for this
rework.

## Runtime and evidence accepted

- The allocator now counts every non-retired `TeamPlatform`, including drafts,
  per generation. More than one excludes every draft of that generation from
  the funding candidates.
- The independent focused run of `ConflictedDraftAllocatorTests` and
  `HeldGenerationTests` passed 14/14 under the host lock and isolated database
  `test_gsp_crv210_audit7`. It covers direct two-draft lifecycle and accounting
  refusal, both accounting selections, the individually-priced control,
  Phase-1 refusal, held-generation writes and the retired positive control.
- Static enumeration finds 53 distinct `test_*` definitions in
  `test_platform_lifecycle.py`: 5 conflicted-draft, 8 duplicate-generation and
  9 held-generation tests among the focused classes. Neither fixture nor the
  helper mixin defines a test method. The stored transcript contains 95 unique
  test IDs and no duplicate execution ID.
- The stored artifact sizes and SHA-256 hashes match `CHECKSUMS.json`, whose
  runtime revision is `f348d24`. The transcript records a clean runtime tree at
  both ends.
- The production inventory was independently re-read in a read-only
  transaction: 302 non-retired rows, 302 distinct `(team, generation)` pairs,
  zero duplicate groups.
- `backend/` exactly matches `f348d24`; the submitted tree was clean.

V2-046 is therefore functionally implemented at `f348d24`, pending integrated
Stage 3 closure. V2-047 remains implemented at `83ec2bd`, also pending that
closure.

## Blocking canonical-record contradictions

1. The checkpoint correctly reports 53 distinct lifecycle definitions near
   its opening, but its V2-047 section still says `HeldGenerationTests` has 16
   tests. It now has 9; 16 was the superseded inherited execution count.
2. The checkpoint's final status says V2-046 and every other listed finding
   were implemented at `83ec2bd`. This contradicts its runtime header and its
   own two-draft history: V2-046's final allocator repair landed only at
   `f348d24`.
3. The findings register still reports 16 `HeldGenerationTests`. Its V2-046
   entry adds the `f348d24` repair at the top but retains an unqualified current
   heading saying the repair is incomplete, an open disposition, and wording
   that the direct allocator defence “remains incomplete”, without a final
   accepted disposition. Chronology should remain, but superseded states must
   be identified as historical rather than coexist as current guidance.

These are the same class of canonical-documentation contradiction previously
treated as blocking in the Stage 1 re-audit: a later correct paragraph does not
make an earlier false present-tense claim safe for downstream readers.

## Required documentation-only repair

1. Change the checkpoint's held-generation count from 16 to 9.
2. State the final revision accurately: V2-046 is implemented at `f348d24`;
   V2-047 at `83ec2bd`; all listed Stage 3A findings are implemented **by**
   `f348d24`, pending integrated closure.
3. Give V2-046 one unambiguous current register status: implemented at
   `f348d24`, pending integrated Stage 3 closure. Keep prior failures as dated,
   explicitly historical audit notes.
4. Change the register's held-generation verification count from 16 to 9.
5. Commit only the Markdown corrections, run `git diff --check`, re-verify the
   existing evidence checksums, confirm the clean tree, and stop for re-audit.

## Verification budget

Zero tests, probes, migrations, suites or evidence regeneration. The runtime
and focused evidence are accepted. Re-audit is limited to Markdown consistency,
existing checksum verification and clean-tree/runtime identity.
