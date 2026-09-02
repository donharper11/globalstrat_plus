# GSP-CRV2-10 Stage 3A sixth re-audit — FAIL / TWO-DRAFT DEFENCE REWORK 6

Audited runtime revision: `83ec2bd`  
Audited checkpoint revision: `dedd74b`

## Verdict

**FAIL / REWORK. Stage 4 remains blocked.**

The V2-047 repair is accepted: both supported write surfaces refuse a request
for an already-held non-retired generation, and Phase 1 refuses both that
stored request and duplicate non-retired platform state before mutation. The
production inventory claim also reconciles read-only: 302 non-retired rows,
302 distinct `(team, generation)` pairs and zero duplicate groups.

The defensive allocator repair required by V2-046 is still incomplete. Two
carried `unfunded_draft` rows for one team and generation are treated as a
choice between candidates instead of invalid duplicate inventory. The first
draft is promoted and charged while the second remains a draft.

## Blocking reproduction

The direct production lifecycle/accounting path was run with two carried
drafts of the same generation, each priced at $1,000,000, and sufficient cash.
It produced:

```text
before [('Draft One', 'unfunded_draft', None),
        ('Draft Two', 'unfunded_draft', None)]
after  [('Draft One', 'in_development', 2),
        ('Draft Two', 'unfunded_draft', None)]
booked_rd_expense 1000000.00
```

`allocate_platform_funding` builds `live_generations` by excluding
`unfunded_draft`, then de-duplicates draft candidates by retaining the first
row encountered. Consequently, a two-draft conflict is not in
`live_generations`; one conflicting draft is silently selected for promotion.
The ordinary Phase-1 path does refuse the duplicate state before reaching the
allocator, but that does not satisfy the independently required allocator
defence or the checkpoint's claim that the allocator declines a residue draft.

## Evidence defect

`HeldGenerationTests` subclasses `DuplicateGenerationTests`. It defines nine
tests of its own and inherits seven additional `test_*` methods (one inherited
name is overridden), so its reported 16 tests include seven reruns. This
contradicts the checkpoint statement that no class inherits another class's
tests and inflates the lifecycle total from 48 distinct test definitions to 55
executions. There is no direct allocator test for the two-draft conflict; the
two-draft test exercises only the Phase-1 refusal.

## Required repair

1. When carried state contains more than one non-retired platform for a team
   and generation, including two drafts, the allocator must exclude every
   conflicting draft. It must not change status, `funded_round`, `start_round`
   or accounting for any of those rows.
2. Retain the Phase-1 fail-closed refusal, including conflict identifiers and
   refusal before platform, result or accounting mutation. Do not delete,
   retire, merge or otherwise repair conflicting state implicitly.
3. Add a direct lifecycle/accounting regression for two carried drafts. Assert
   that both remain `unfunded_draft` with null funding/start rounds and that
   actual R&D expense is zero. Exercise the capitalization selection without
   duplicating the test matrix unnecessarily.
4. Remove test-case inheritance. `HeldGenerationTests` should inherit the
   fixture base, or a helper-only mixin containing no `test_*` methods.
5. Regenerate the focused transcript and report accurate distinct test counts.
6. Keep V2-047 implemented pending integrated Stage 3 closure. V2-046 remains
   incomplete until this repair passes re-audit.

## Re-audit scope

Run only the focused Stage 3A platform-lifecycle/API/accounting tests under the
execution protocol's isolated database and lock. Do not run the full suite.

Acceptance requires the direct two-draft allocator case to produce no
promotion and no charge, the Phase-1 and held-generation refusals to remain
fail-closed, the retired-generation positive control to remain valid, and the
evidence transcript to contain no inherited duplicate test executions.
