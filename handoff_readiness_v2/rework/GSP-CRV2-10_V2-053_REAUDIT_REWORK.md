# GSP-CRV2-10 V2-053 re-audit — runtime pass / documentation rework

Date: 2026-09-04  
Audited runtime revision: `8c3edb978e18fdf9c765e290da571c5f560c28a7`  
Audited packet revision: `6262915a5b0f55589e7d9d97a8f770118bcb587c`  
Rules decision: R10, `GSP-CRV2-10_RULE_DECISIONS.md`

## Verdict

**V2-053 runtime implementation: PASS. Canonical documentation: REWORK
REQUIRED.**

The implementation correctly retires future feature-level R&D investment,
refuses persisted legacy rows before competitive mutation, and removes direct
spend scoring without replacing it with platform-development cost. Its negative
proof is credible: each removed score was restored in isolation and caused its
new behavioral test to fail.

V2-053 cannot close yet because the finding register now makes two incompatible
current claims. Its new status says the rows are refused and unscored; the
unlabelled text immediately below says that the rows "are still accepted",
"still charged", and "still scored". Those sentences describe the condition
that raised V2-053, but are not identified as historical. A downstream reader
cannot safely tell which rule applies now.

## Runtime and evidence accepted — do not redo

- `8c3edb9` is in the pushed packet chain and follows the Phase 3 accepted
  commit.
- The two supported decision writes reject a non-empty legacy
  `DecisionRDInvestment`, name the platform-development/re-base route, and
  leave no row behind. Clearing an empty list remains possible.
- The Phase-1 engine precondition rejects a planted persisted row before
  financial or other competitive writes, and preserves the row for correction.
- `performance.py` no longer derives strategic capability from an investment
  amount. `coherence.py` no longer carries the R&D-market-alignment component
  or its scorer. Platform-development cost is not substituted as a score.
- The surviving capability terms retain their 30:30 ratio and are normalised
  over the surviving 0.60 weight, so removal does not silently cap every team
  at 60% of its former ceiling.
- The signed evidence packet's four declared files independently match its
  SHA-256 manifest. Its transcript records 318 tests passing from clean runtime
  revision `8c3edb9`; its 14-test V2-053 inventory covers both writes, engine
  refusal, no financial mutation, and both direct-score removals.
- Independent re-execution of that focused V2-053 suite against a disposable
  local PostgreSQL database passed **14 tests in 2.687 seconds**. No production
  credential or database was used; the disposable database was removed after
  the run.
- Mutation proof is behavioral, not merely a source scan: restoring the former
  performance term changes strategic capability from 0.27 to 0.67; restoring
  coherence restores `rd_market_alignment` in the persisted breakdown.
- GitHub Actions run
  [`33912256446`](https://github.com/donharper11/globalstrat_plus/actions/runs/33912256446)
  is a successful first-attempt push run for packet commit `6262915`; its
  selftest, runner, receipt assertion, artifact upload, and final gate all
  succeeded.

## Blocking documentation contradiction

In `handoff_readiness_v2/V2_FINDINGS_REGISTER.md`, the current V2-053 header
and implementation summary correctly state that R10 retires the decision and
its direct scores. The later paragraphs remain in present tense:

- "The rows themselves are still accepted ... still charged ... still
  **scored**".
- "So after Ruling 1 a team can spend on R&D ... score for it ...".

These are the pre-R10 findings. They must remain as audit history, but must be
introduced as such and consistently written in the past tense. The later R10
decision paragraph does not cure an earlier unqualified false current claim;
this programme has correctly treated that record shape as rework before.

## Required documentation-only correction

1. Add an explicit heading such as **"Historical condition before R10 —
   superseded"** before the pre-implementation narrative in V2-053.
2. Change its present-tense operational claims to past tense. Preserve the
   original facts, measurements, and reason V2-053 was raised.
3. Leave the current R10 implementation summary and the evidence references
   intact. Do not change runtime code, tests, evidence files, checksums, or
   their cited revisions.
4. Commit only the register correction, run `git diff --check`, and verify the
   four evidence-packet checksums still match.

## Owner follow-up — not a V2-053 rework condition

`scenario_rd_spend_target` is now an unused fail-closed configuration
requirement. Its presence does not restore direct spend scoring and therefore
does not invalidate R10. It should receive a separate owner decision: retain it
as a scenario-schema compatibility invariant, or remove it in a narrowly
reviewed configuration cleanup. Do not silently remove it during this
documentation correction.

## Re-audit budget

No runtime tests, migrations, probes, or evidence regeneration. Re-audit is
limited to the Markdown correction, `git diff --check`, unchanged evidence
checksums, and clean committed-tree identity.

## Final disposition

**RUNTIME PASS / DOCUMENTATION REWORK REQUIRED.** V2-053 closes after the
record states one unambiguous current rule.
