# Release integration of snapshot `cbe2656` — 2026-09-12

**Branch:** `crv2-release-integration`, cut from `a521f7a`
**Head:** 20 commits; final content commit `c1ee2c9`
**Specification:** the audit of `cbe2656`, its file classification, proposed
commit split (0–15) and defect list AUD-1..AUD-8
**Safety snapshot:** `wip/release-readiness-snapshot-2026-09-11` is untouched at
`cbe2656`. `main` is untouched at `ed8c423`. Nothing was pushed.

## What this branch is

`cbe2656` was an emergency snapshot: 53 files of mixed, unreviewed work in one
commit, which turned seven passing tests red, silently repaired an unregistered
500, and carried about fifteen findings with no register entry. This branch
converts it into reviewed, focused commits, registers what was repaired, and
restores a green focused-test baseline.

**It closes nothing.** Every closure below is a builder's claim awaiting an
auditor; several items are explicitly blocked on a rules-owner ruling.

---

## 1. Commits

Audit numbering in brackets. Two commits are additions the audit named as
needed for a green suite but did not number.

| # | Commit | Why |
|---|---|---|
| [0] | `04c366b` | Register V2-056..V2-073, correct V2-017 and V2-043, record owner rulings R11–R14. Log before repair. |
| [1] | `4ab5e25` | `backend/scripts/test-postgres`: run the suite against a disposable PostgreSQL, so testing no longer needs the production credential. |
| — | `6ea59a7` | Repair the R&D ordering cohort to R10 — the rule in force — not the rule it was written against. |
| — | `62f8744` | Record the product re-base route in the route inventory (stale since `ac2883b`). |
| [2] | `39a9b77` | CRV2-13 D2: one committed-spend total across lock, summary and finance. Also fixes the V2-056 `NameError` 500. |
| [3] | `51d6616` | CRV2-12: route decision refusals through the bilingual catalogue. Carries the AUD-5 test repairs so no commit is red alone. |
| [4] | `246a8ca` | CRV2-12 Stage 1 static player-string inventory and its freshness check. |
| [5] | `85ed885` | CRV2-07 V2-063: fail fast on contended decision writes with an explained 409. |
| [6] | `67f3267` | CRV2-07 V2-062: an admissible combined-resolution load harness, plus the AUD-3 production host it missed. |
| [7] | `5c2e6ec` | V2-017: the competition admin becomes a read-only evidence surface (R13). |
| [8] | `68e3d3b` | CRV2-13 D4: stop swallowing organisational speed lookup failures. |
| [9] | `aa20462` | CRV2-13 D5: name the segment loop variable for what it holds. |
| [10] | `354ff13` | CRV2-13 D1 / V2-043: deactivate offered markets on end-of-round retirement. |
| [11] | `1c2a665` | Deploy the durable narrative worker unit (committed, **not installed**). |
| [12] | `312a5ff` | CRV2-11 fixed-policy field size and sensitivity under Fix A. |
| [13] | `b410ff7` | CRV2-11 Stage 2 round-zero parity — re-landed **unratified** (V2-073). |
| [14] | `949a9e9` | CRV2-11 product-allocation audit and ruling records. |
| [15] | `acee4ea` | V2-048 operations review, and its acceptance attribution marked unverified. |
| — | `c1ee2c9` | Register V2-074 — the true full-suite baseline, seven pre-existing failures nobody had counted. |
| — | *(this report)* | The completion record for this branch. |

**History was rewritten twice on this branch, before review, and only here.**
Commits 4 and 6 were amended because their first messages asserted evidence that
had not been obtained — an `exit 0` that had not happened, and "no occurrence
remains" when two non-executable occurrences did. The corrected messages state
what was actually true. No other branch was touched.

## 2. End-state verification

`git diff cbe2656 crv2-release-integration` contains only the intended
additions — the register and ruling documents, the test repairs, the route
inventory refresh, and the harness host fix. Measured at `acee4ea`, the last
commit that changes snapshot content:

```
 backend/core/services/route_inventory.json         |  12 +-
 backend/core/tests/test_platform_freeze.py         |  15 +-
 backend/core/tests/test_rd_ordering.py             | 103 ++++++++----
 backend/core/tests/test_rd_scoring_retired.py      |   9 +-
 handoff_readiness_v2/GSP-CRV2-10_RULE_DECISIONS.md |  39 ++++-
 handoff_readiness_v2/OWNER_RULINGS_2026-09-11.md   | 181 +++++++++++++++++++++
 handoff_readiness_v2/V2_FINDINGS_REGISTER.md       | 112 ++++++++++++-
 .../harness/failure_walkthrough_body.py            |  15 +-
 8 files changed, 429 insertions(+), 57 deletions(-)
```

Every runtime file in the snapshot is byte-identical to `cbe2656`. The four
files needing a hunk split — `views/decisions.py`, `rd_processing.py`,
`test_platform_lifecycle.py`, `test_rd_costs.py` — reassemble exactly.

Two record-keeping commits follow `acee4ea`: the V2-074 register entry, which
grows a file already in that list, and this report. Against the final head the
diff is therefore the same eight paths plus
`handoff_readiness_v2/completion/RELEASE_INTEGRATION_2026-09-12.md` — nine in
all, and **no further runtime or evidence file**. The verified output is at the
foot of this report.

## 3. Owner rulings recorded

Recorded in `OWNER_RULINGS_2026-09-11.md`, indexed as R11–R14 in
`GSP-CRV2-10_RULE_DECISIONS.md`.

- **R11** — round-0 adopters are derived from the authored starter sales; the
  unauthored `* 10` is retired. **Not implemented here** — it belongs to
  GSP-CRV2-11. Recorded with the measurement proving the factor display-only:
  zero differing rows in rounds 1–10 across all ten result tables. This
  contradicts `CRV2-13_D2_D6_FOLLOWUP.md`, which is corrected in V2-060 — the
  evidence document itself is left as the record of its own time.
- **R12** — 8 firms per game, 3–5 members per team; the authored defaults are
  right and enforcement is what is missing. Recorded only; V2-042's owner
  implements it.
- **R13** — the Django admin is a read-only evidence surface. **Dispositions
  V2-017**, implemented in `5c2e6ec`. The route-inventory blind spot is
  explicitly *not* closed by it.
- **R14** — A5 operating budget and overspend financing deferred; the
  refuse-beyond-cash rule stands. **A5 closes as "deliberately not built"**, and
  CRV2-09 must not carry it as an open gap.

## 4. Register IDs assigned

Order is documented in the register itself: the unidentified findings first, in
the order the audit lists them; V2-062/V2-063 at the numbers their rework
documents already used; then AUD-2..AUD-8 ascending; then the baseline and
governance findings.

| Audit item | ID | Sev | Status |
|---|---|---:|---|
| AUD-1 — student lock `NameError` 500 | V2-056 | P1 | Repaired in `39a9b77`; **P0/P1 needs a ruling** |
| D2 — committed-spend drift | V2-057 | P1 | Repaired |
| D4 — swallowed org-speed lookup | V2-058 | P1 | Repaired |
| D5 — segment loop variable | V2-059 | P2 | Repaired (rename) |
| D6 — unauthored round-0 factor | V2-060 | P2 | Open; ruled by R11, unimplemented |
| F-PL-01 — English-only refusals | V2-061 | P1 | Repaired |
| load harness inadmissible | V2-062 | P1 | Repaired (row never existed) |
| contended writes starve refreshes | V2-063 | P1 | Repaired (row never existed) |
| AUD-2 — fast-fail scope | V2-064 | P1 | **Open — awaiting ruling** |
| AUD-3 — production host in harness | V2-065 | P1 | Repaired |
| AUD-4 — no refusal evidence | V2-066 | P2 | Open |
| AUD-5 — 7 tests turned red | V2-067 | P2 | Repaired inside `51d6616` |
| AUD-6 — narrative worker not installed | V2-068 | P1 | Open — deployment owner |
| AUD-7 — residual language defects | V2-069 | P2 | Open — CRV2-12 owner |
| AUD-8 — `end_of_round` dominance | V2-070 | P1 | **Open — awaiting ruling** |
| pre-existing red suite | V2-071 | P1 | Repaired |
| V2-048 `SET ROLE postgres` | V2-072 | **P0** | Open — DBA/operations |
| CRV2-11 Stage 2 gate edit | V2-073 | P1 | **Open — awaiting ruling** |
| full-suite baseline — raised by this branch | V2-074 | P1 | Open — not this branch's to repair |

AUD-7 was registered although the audit's list of fifteen omitted it: it is a
finding the audit raised that had no entry, which is the same defect.

**Corrections, not new IDs.** V2-017's text named `SCEventInstance` among the
models with admin write routes; it was never registered in admin at all.
V2-043's description was wrong — end-of-round retirement did not leave the
product on sale, because demand already filtered on status; what the stale rows
moved was stored state inside the output hash. Its severity is raised **P2 →
P1** on the register's own rule that anything able to change a published result
is never P2.

**V2-048's owner acceptance is annotated, not accepted.** The claim that the
competition owner accepted the residual risk on 2026-09-05 appears only in
builder-authored files. It is left in place and marked *attribution unverified —
awaiting owner confirmation (2026-09-12)*. It is **not** marked accepted.

## 5. Tests

All runs used `backend/scripts/test-postgres` under `flock` on
`/tmp/globalstrat-backend-test.lock`, each with its own disposable
PostgreSQL 16 container. No production database was contacted and no systemd
environment file was read.

| Run | Labels | Tests | Suite time | Wall | Result |
|---|---|---:|---:|---:|---|
| a | `test_rd_ordering` | 2 | 1.343 s | 13 s | OK |
| b | `test_rd_costs` | 16 | 0.286 s | 12 s | OK |
| c | 6 CRV2-12 modules | 121 | 5.115 s | 16 s | OK |
| d | `test_competition_locks` | 1 | 5.475 s | 16 s | OK |
| e | `test_audit_integrity` | 58 | 20.151 s | 178 s | OK |
| f | `test_platform_lifecycle` | 55 | 2.256 s | 25 s | OK |
| g | `test_product_retirement` | 1 | 0.014 s | 19 s | OK |
| h | `test_leaderboard_tiebreak` | 2 | 0.062 s | 186 s | OK |
| **final 1** | audit run-1 modules (8) | **160** | 28.289 s | 39 s | **OK** |
| **final 2** | audit run-2 modules (9) | **162** | 169.328 s | 181 s | **OK** |

Wall times on runs e and h include waiting on the host lock held by another
session; suite time is the honest measure of the work.

**The baseline is restored.** The run-2 module set was **9 failures and 1 error**
at `cbe2656`; it is 162 passing here. Seven of those were AUD-5, three were the
pre-existing red tests nobody had registered.

Two static checks:

```
python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py --check   → exit 0
manage.py dump_route_inventory --check                                                → clean after 62f8744
```

The inventory `--check` is **not** clean at commit `246a8ca` where the inventory
lands, because it is generated against the whole snapshot and the
`lifecycle_in_progress` string arrives in the next commit. That is recorded in
that commit's message rather than papered over by regenerating a different
inventory than the work produced.

### Full backend suite — the authorised single diagnostic

```
backend/scripts/test-postgres          (no labels: the whole suite)
revision acee4ea, disposable PostgreSQL 16, flock-serialised
Ran 842 tests in 302.467s
FAILED (failures=4, errors=3)          wall 316 s, rc=1
```

Run **once**, as authorised. Nothing was re-run to see whether a failure flakes.

**All seven failures are pre-existing. None is caused by this branch, and none
is repaired by it.** That is measured, not inferred: the same six test classes
run against a clean `a521f7a` worktree reproduce all seven identically —
`Ran 30 tests in 3.291s, FAILED (failures=4, errors=3)`, same names. None of the
four test files was touched by the snapshot (`git diff --name-only a521f7a
cbe2656` is empty for all four), by this branch, or by anything since
2026-08-29 — which is before R10.

| Test | Diagnosis | Verdict |
|---|---|---|
| `test_scoring_dispositions.RdSpendTargetTests.test_zero_spend_earns_zero_for_the_rd_term` | R10 retired direct R&D-spend scoring, so zero spend and at-target spend both yield 0.450 and "zero earns less" is false. | Pre-existing |
| `test_scoring_dispositions.RdSpendTargetTests.test_a_dollar_against_a_dollar_no_longer_earns_full_credit` | Same cause: the V2-021 exploit is asserted against a term that no longer contributes. | Pre-existing |
| `test_staffing_adequacy.TheRule.test_staffing_at_each_optimum_preserves_capability` | Capability is 0.450 where 0.6700 is expected, because the retired R&D-spend term no longer feeds it. | Pre-existing |
| `test_staffing_adequacy.RDStillMatters.test_actual_rd_spend_still_moves_capability` | Asserts by name the thing R10 removed — spend moving capability. | Pre-existing |
| `test_reference_price.ConfigurationFailsClosed.test_resolution_refuses_before_any_competitive_write` | ERROR: the fixture gives one team five non-retired platforms of one generation; the V2-046 duplicate-generation precondition refuses the round before the refusal under test is reached. | Pre-existing |
| `test_reference_price.ElasticityConfiguration.test_resolution_refuses_before_any_competitive_write` | Same fixture, same precondition. | Pre-existing |
| `test_durable_narratives.NarrativeStatusEndpointTests.test_an_unrelated_instructor_is_refused` | ERROR: `AttributeError: 'JsonResponse' object has no attribute 'data'` — asserts DRF's `.data` on a plain Django response. | Pre-existing |

Four of the seven are the **same class as the ordering cohort this branch
repaired**: R10 fallout, stale since 2026-09-04. The V2-053 closure said four
suites that tested sub-rules of the retired decision were updated; these were
not.

**Registered as V2-074, not repaired.** Repairing four suites to four rules from
a release-integration branch would be guessing at rules that belong to their
owners — and the same discipline that made `test_rd_ordering` a legitimate
repair here (it is the rule this branch is re-landing) makes these not.

**This is the number that did not exist before.** The suite has been red since
about 2026-09-02, every run since has been a focused subset, and the true count
was unknown until now. V2-071 recorded three red tests found by focused runs;
the full suite shows seven more on top of them. **GSP-CRV2-09 cannot certify a
release against a suite in this state**, and there is no earlier full-suite
figure to compare this one against.

## 6. Deviations from the audit's specification

Stated rather than done silently.

1. **The audit marked commits 5, 10, 13 and 15 "Hold" pending rulings. I landed
   them.** The end state has to reconstruct `cbe2656`, so holding a commit would
   leave the branch unable to satisfy its own acceptance test. Each hold is
   converted into a registered open finding (V2-064, V2-070, V2-073, V2-072) and
   stated in the commit message, so nothing is presented as settled.
2. **Commit 11 does not reconcile `NARRATIVE_WORKER_OPERATIONS.md`,** which the
   audit asked for. Editing it would add a ninth file to a diff authorised to
   contain eight, and the correct text depends on how the unit is actually
   installed. The mismatch is recorded in V2-068 for the deployment owner, and
   the register wording was corrected in the same commit so it does not claim a
   reconciliation that did not happen.
3. **The audit's reason for ordering commit 4 after commit 3 is slightly
   wrong.** The inventory matches the *whole snapshot*, not commit 3's strings,
   so `--check` is clean only at the end of the branch.
4. **AUD-7 was registered** although it was absent from the audit's list of
   fifteen unregistered items.

## 7. What I deliberately did not do

- **No frontend changes at all**, including the AUD-2 autosave that swallows the
  409. Instructor screens and `DecisionContext.js` belong to other builders.
- **No pricing logic, no course/enrolment/team-assignment code.** R12's
  enforcement is therefore recorded and not built.
- **R11 is not implemented.** The round-0 derivation belongs to GSP-CRV2-11.
- **The route-inventory blind spot is not fixed.** R13 makes the admin harmless;
  the inventory still cannot see function-based routes.
- **No audit row was added for a refused 409** (V2-066): that changes the
  audited boundary and needs a ruling first.
- **The narrative worker was not installed**, and no systemd or production host
  state was touched.
- **No expensive evidence was regenerated** — not CRV2-07's load harness, not
  CRV2-11's replays, not CRV2-01's determinism matrix. The protocol reserves
  integrated regeneration for CRV2-09.
- **Not verified:** the provenance of `fixed_policy_measurements.json`, the
  authorship of the swept-in CRV2-11 audit documents, the genuineness of the
  V2-048 owner acceptance, and zh-CN translation quality.
- **The seven pre-existing full-suite failures are not repaired** (V2-074).
  They belong to the scoring, staffing, reference-price and narrative-endpoint
  owners; four of them need a rule read, not a test edit.
- **Nothing was pushed**, and no failure from the full-suite diagnostic was
  re-run to see whether it flakes.

## 8. Still blocked on a rules-owner ruling

1. **V2-064 (AUD-2)** — does the 409 fast-fail apply only to Phase-1 resolution,
   or to every exclusive operator action? If the latter, the message is false
   for a deadline change and the frontend must stop silently swallowing it. **A
   student edit can currently be lost without being told.**
2. **V2-070 (AUD-8)** — should a retiring product sell through its final round?
   Until answered, `immediate` retirement is strictly dominated by
   `end_of_round` (25% vs 50% recovery).
3. **V2-056** — was locking required in any round played between `96a9aae` and
   `a521f7a`? The answer decides P0 vs P1, and whether any played round was
   affected.
4. **V2-073** — ratify or reject the rewritten CRV2-11 Stage 2 gate. Until then
   Stage 2 is not closed.
5. **V2-072 / V2-048** — is the `SET ROLE postgres` capability a formally
   excepted P0, and did the owner actually accept it? The register's legend says
   P0 blocks release.
6. **V2-066 (AUD-4)** — must a dispute record be able to prove a student write
   was refused?
7. **V2-057** — is `research_budget` counting toward committed spend a live
   rule? The API cannot write it and the engine never charges it.
8. **V2-060 / R11** — ruled, unimplemented; GSP-CRV2-11 owns the derivation and
   the regression that must pin the authored source.

## 9. EXECUTION_PROTOCOL auditor preflight checklist

| Question | Answer |
|---|---|
| Did inventory start from registered routes/models/jobs, not only code using the new abstraction? | Yes. The route inventory is regenerated from the live URL conf by `manage.py dump_route_inventory` (219 → 220 mutating, 0 unguarded), and the admin surface was enumerated from `admin.site._registry`, not by grepping for the new admin base class. |
| Is there an active legacy or alternate entry point? | Yes, and they are named. The Django admin was one — now read-only per R13, though the inventory still cannot see it. Raw SQL and `manage.py shell` remain, covered by the database triggers. The retired feature-level R&D decision is refused on both write surfaces *and* at the engine boundary, because rows can also arrive by restore, import or shell. |
| Does a failure/refusal audit survive rollback? | **Not for the V2-063 409.** A refused contended write leaves no audit row, no log line and no request id — registered as V2-066 and not repaired here. Operator rejections and middleware refusals are still recorded. |
| Is each correlation ID generated once and identical in response/audit/log? | Not exercised by this branch; no correlation-ID path was changed. The 409 refusal carries no request id at all (V2-066). |
| Is background/external work delayed until the outer transaction commits? | Unchanged here. Narrative jobs are written in the same transaction as the numbers; the worker that drains them is committed but **not installed** (V2-068). |
| Do claimed environment values describe the executing process? | Yes. Every test ran in a disposable container whose generated credential was injected into that process only; the harness repairs (V2-062, V2-065) exist precisely so a sampler stops describing a different database than the one under test. |
| Does provenance identify runtime bytes, including required untracked files? | Partly. Commits and diffstat are exact and verified against `cbe2656`. `fixed_policy_measurements.json` is committed with its provenance explicitly marked unverified. |
| Do README commands run exactly as written against stored artifacts? | Verified for the two commands this branch adds or repairs: `backend/scripts/test-postgres <labels>` and `generate_inventory.py --check`. The CRV2-07 load and calibration harnesses were **not** run. |
| Do P0/P1/P2 labels match their definitions? | Checked against the register's legend, and two labels moved as a result: V2-043 P2 → P1 (it moves state inside the output hash), and V2-070 is P1 rather than P2 for the same reason. V2-072 is recorded at the P0 its source review assigns, with the tension against "P0 blocks release" left visible rather than resolved by a builder. |
| Does each negative test prove mutation/engine execution did not occur? | Yes for the tests this branch touched. The repaired AUD-5 tests now assert `DecisionRDInvestment.objects.count() == 0` alongside the refusal wording, and the repaired ordering cohort asserts stored capability is unchanged. **The committed V2-063 lock test is weaker than that**: it uses an `AllowAny` probe view, so it proves no handler ran but not permission-before-409 or the absence of audit rows. The real-route probe covered those; adopting it as a test is follow-up work. |

## 10. Rollback

Every commit is independently revertible. The branch is unpushed and
`cbe2656` remains the safety snapshot: `git checkout
wip/release-readiness-snapshot-2026-09-11` restores the original state exactly.

---

## 11. Verified end state

`git diff cbe2656 crv2-release-integration --name-status` at the final head.
The **file list** is the verification that matters and is stable; line counts
shift by the length of this closing section, which is why they are not restated
here.

```
M	backend/core/services/route_inventory.json
M	backend/core/tests/test_platform_freeze.py
M	backend/core/tests/test_rd_ordering.py
M	backend/core/tests/test_rd_scoring_retired.py
M	handoff_readiness_v2/GSP-CRV2-10_RULE_DECISIONS.md
A	handoff_readiness_v2/OWNER_RULINGS_2026-09-11.md
M	handoff_readiness_v2/V2_FINDINGS_REGISTER.md
A	handoff_readiness_v2/completion/RELEASE_INTEGRATION_2026-09-12.md
M	handoff_readiness_v2/evidence/load-failure/harness/failure_walkthrough_body.py
```

Nine paths: the four test and inventory repairs, the three register and ruling
documents, the harness host fix, and this report. **No runtime file, no evidence
artefact, and no handoff specification differs from `cbe2656`.**

State of the refs, unchanged by this work:

```
wip/release-readiness-snapshot-2026-09-11 = cbe2656332b413316b29fca7c1dfa5112f406e61
main                                      = ed8c42341959394ded6fb7781d80106ecac6e233
```

20 commits on `crv2-release-integration`, working tree clean, **nothing pushed**.
The three other agents' worktrees were not touched.
