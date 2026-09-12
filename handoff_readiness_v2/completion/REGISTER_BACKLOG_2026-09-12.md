# Register backlog — eight completion reports, 2026-09-12

**Role:** programme registrar. **Date:** 2026-09-12.
**Branch:** `crv2-register-backlog-2026-09-12`, cut detached from
`crv2-release-integration` at `59347f4` and brought current to `e398fc6` as the
integration branch advanced under it. The main checkout was not modified,
nothing was pushed, no other worktree was read or written.
**Changed:** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md`, and this
report. **No runtime code and no test was changed.**

**Registered: V2-075 through V2-108 — thirty-four findings from eight
handoffs.** Nothing is closed. Where merged work repairs a finding it is
recorded **"repaired, pending closure"**; where an owner ruling disposes of one
it is recorded **ruled**. The registrar is not the auditor; GSP-CRV2-09 owns
closure.

**The headline for anyone reading only one line: V2-107 is a P0.** The pricing
screen's own default row is refused by the API while the screen reports "Your
entry is saved". A team can lose a round's decisions believing they are saved.

---

## 1. Two records existed only as uncommitted working-copy changes

The R15–R22 dispositions table, the `R22` annotation on V2-073, and the two
launch-checklist entries added 2026-09-12 were **not** on
`crv2-release-integration` at `59347f4`. They existed only as uncommitted
modifications in the main checkout, alongside the then-untracked
`OWNER_RULINGS_2026-09-12.md`. I carried them onto this branch verbatim before
appending anything; they were committed upstream at `7b8cd25` and my merge
reconciled the two copies.

**This matters beyond bookkeeping.** R19 established that a ruling exists in an
`OWNER_RULINGS_*` document with a date and nowhere else. The corollary this
session hit repeatedly is that a **committed** record is the only one another
branch can see — and it produced a numbering collision (§3) and two builders
acting on rulings relayed out of band. The paid-research builder made the same
point unprompted: *"the owner instruction behind this work reached me through
the handoff, not through a dated `OWNER_RULINGS_*` document."*

---

## 2. Merges, and the one I declined to perform

The integration branch advanced four times during this task. I merged it each
time; both conflicts fell in files I own, and in both the HEAD side was a strict
superset (my V2-074 row already contained upstream's text plus my status update;
V2-073 carried the identical R22 annotation), so `--ours` discarded nothing —
verified, not assumed.

**I did not complete the CRV2-12 merge, deliberately.** Merging
`crv2-12-language-completion` conflicts in
`backend/core/utils/participant_messages.py`, where integration's price-band and
paid-research keys collide with the sweep's. **That is a runtime content
decision belonging to the integration owner, not to a registrar whose remit is
explicitly "no runtime code."** I aborted the merge and verified every CRV2-12
citation against the branch directly with `git show`, which gives the same
reading without my arbitrating someone else's code. The register records what
that branch contains; the merge itself is still outstanding and is flagged here
because it will need a deliberate resolution.

**On the instruction to rebase:** `e398fc6` is a merge *of this branch* into
integration, so my HEAD was already an ancestor of it. A rebase would have been
a no-op at best and would have replayed or flattened two merge commits whose
conflict resolutions I had verified. I fast-forwarded instead, which achieves
the stated intent — read the merged tree — without that risk.

**Upstream rulings arriving mid-task changed three entries I had already
written.** All three were corrected rather than left standing: **V2-084** is
ruled by **R29**; **V2-085** is ruled by **R25/R27** and implemented at
`5a0419c`; **V2-041**'s Q7 is ratified by **R26**.

---

## 3. ID assignment, and a numbering collision

Ranges V2-075–V2-085, V2-086–V2-095 and V2-096–V2-108 were each unused when
assigned. Order is documented at the head of each block in the register.

**The collision, and why it was nobody's carelessness.** The CRV2-12 builder
drafted its five entries as **V2-075–V2-079** — a range already assigned. Its
branch was cut from `46b4bbe`, and the V2-075–V2-085 block existed only on the
registrar branch until it reached integration at `e398fc6`, *after* that cut.
The builder could not have seen the assignment. Renumbered **V2-096–V2-100 in
the same documented order**; its report's numbering is superseded, so "CRV2-12's
V2-075" means **V2-096**, through to V2-079 → **V2-100**. The register says so
explicitly, because the completion report will outlive this correction.

### Block 1 — five reports merged at `59347f4`

| ID | Source | What it is | Sev | Status |
|---|---|---|---:|---|
| V2-075 | Stage 6 f.1 + `LEGACY_CONTROL_REMOVAL` + R16 | Legacy `/simulation-control/` unscoped cross-cohort reset, no ownership check | **P0** | Repaired `a37bb92` |
| V2-076 | `LEGACY_CONTROL_REMOVAL` F2 | Same SQL survives as `reset_simulation` command | **P1** | Open |
| V2-077 | F1 | `round_engine` unbound `stakeholders`; legacy advance already dead | P2 | Closed |
| V2-078 | F3 | `core/services/scoring.py` unreferenced | P2 | Open |
| V2-079 | §3 | Route-inventory false positive on a name collision | **P1** | Repaired `d9cbd43` |
| V2-080 | Stage 6 f.2 | `RoundControlCard` untranslated | **P1** | Open |
| V2-081 | Stage 5 | `RoundResultsView` declares no `permission_classes` | P2 | Open |
| V2-082 | Stage 5 | Price-band events carry `request_id=''` | P2 | Open |
| V2-083 | `STANDING_RED_TESTS` | Two green tests pass vacuously | P2 | Open |
| V2-084 | `GSP-CRV2-11` | Round-0 `team_share_pct` changed meaning | **P1** | **Ruled (R29)** |
| V2-085 | `GSP-CRV2-11` | Unreachable preference weight is two mechanics | P2 | **Ruled (R25/R27)**, implemented |

### Block 2 — paid research, a cash path, and a merge-only defect

| ID | Source | What it is | Sev | Status |
|---|---|---|---:|---|
| V2-086 | `PAID_RESEARCH` §7/§9 | Manifest envelope v5 → v6, **no replay run** | **P1** | Open |
| V2-087 | f.6 | Two lifecycle routes unguarded once research became a write | **P1** | Repaired `c87395c` |
| V2-088 | f.7 + owner's verification | Org-structure switch charges cash outside every calculator, irreversibly | **P1** | Open |
| V2-089 | f.2 | `channels` report is a hardcoded constants table | P2 | Open |
| V2-090 | f.3 | `products` report is mostly the team's own data | P2 | Open |
| V2-091 | f.4 | `research_allocated` rendered nowhere | P2 | Repaired |
| V2-092 | f.5 | `StakeholdersTab` had no `.catch` | P2 | Repaired |
| V2-093 | f.1 | Handoff cited `price_band_pct` as landed when it did not exist | P2 | Open |
| V2-094 | §9 | Analyst query charged **without showing the price** | **P1** | Open |
| V2-095 | `414d718` | `price_band.py` outside the determinism ordering scan | P2 | Repaired `414d718` |

### Block 3 — the language sweep and the first browser verification

| ID | Source | What it is | Sev | Status |
|---|---|---|---:|---|
| V2-096 | CRV2-12 (its V2-075) | 14 sites interpolated raw `.name` into localised sentences | P2 | Repaired |
| V2-097 | its V2-076 | `SummaryPage.js` untranslated literals | P2 | Open |
| V2-098 | its V2-077 | Price-band receipt renders English names from the audit payload | P2 | Open |
| V2-099 | its V2-078 | `IsTeamMember` queries `Enrollment` twice | P2 (from **P3**) | Open |
| V2-100 | its V2-079 | Pre-commit hook refuses every commit; the layer protects nothing | **P1** (from P2) | Open |
| V2-101 | Frontend F1 | Screen promises a floor the rule will not give | **P1** | Open |
| V2-102 | F2 | Clearing a price deletes the decision — the silent vanish R24 forbids | **P1** | Open |
| V2-103 | F3 | Price-adjustment receipt has no reachable screen | **P1** | Open |
| V2-104 | F4 | Refused cohort assignment reported to the instructor as success | **P1** | Open |
| V2-105 | F5 | Extend Deadline confirmation omits the game name | **P1** | Open |
| V2-106 | F6 | Student pages poll an instructor-only endpoint, 403 forever | P2 | Open |
| V2-107 | F7 | **Default pricing row refused while the screen says "saved"** | **P0** (from P1) | Open |
| V2-108 | verifier's aside | Hard dependency on two external Google Fonts stylesheets | P2 | Open |

### Deliberately not given an ID

`LEGACY_CONTROL_REMOVAL` F5 (V2-017's existing remainder, citation corrected
`:129-136` → `:194-202`); `PAID_RESEARCH` finding 8 (a V2-057 status update);
R28's new authoring task; every §12 rules question; and Stage 6's own draft
numbering, which pre-numbered its findings `V2-056`/`V2-057` — both taken.

---

## 4. Sources reconciled into one finding

- **V2-075** — Stage 6 reported it and did not repair it; R16 ruled deletion;
  the removal handoff deleted it. One finding with a repair, not three.
- **V2-076** is genuinely separate: the routed exposure is closed, the CLI one
  is not.
- **V2-079** is separated from V2-075 deliberately — one is the exposed route,
  the other is why the guard could not see it, and the detector defect outlives
  the route.
- **V2-088** — the paid-research builder flagged it in passing as "not mine";
  the release-integration owner raised and verified it independently. One ID,
  both attributions recorded.
- **V2-099 is deliberately *not* folded into V2-069's fourth defect.** They are
  different queries against the same table; V2-069's is now repaired and this
  one is not, and folding them would let the fixed one hide the open one. It is
  also exactly what made the builder's first metric (4 → 3) meaningless.
- **V2-100 supersedes** my own earlier decision to leave the pre-commit hook
  unregistered. That was too lenient: by day's end six handoffs had hit it and
  three had published three different theories.

---

## 5. Severities changed from what the source proposed

Legend: **P0 blocks; P1 degrades; P2 cosmetic** — and anything that can change a
published result is never P2.

| ID | Proposed | Landed | Why |
|---|---|---|---|
| V2-075 | P1 | **P0** | V2-032 and V2-051 — the same class with a smaller blast radius — are both P0 here. |
| V2-080 | P2 | **P1** | P2 is cosmetic; these are the five destructive lifecycle confirmations. V2-061 set the P1 precedent for wording at the point of action. |
| V2-084 | P2 | **P1** | V2-043's rule: round-0 rows are stored state inside the certified output envelope. Stated plainly that no ranking moves. |
| V2-099 | **P3** | **P2** | The legend defines no P3. Precedent at register `:1415`, where a P3 was reclassified on the owner's instruction. Duplicated work is not a wrong answer. |
| V2-100 | P2 | **P1** | Not the cause but the effect: **the pre-commit layer has been bypassed on every commit all session and protects nothing.** V2-071 and V2-074 are P1 on the same principle. Not P0 — the deploy gate is separate and still blocks. |
| V2-107 | P1 (builder asked P0) | **P0** | See below. |

**V2-107, the reasoning on the record.** The builder rated P1 because a
fully-filled row saves and the lock path validates server-side. Three things
decide it the other way. **(1) The failing path is the default one** — typing a
price, the obvious first action, is refused; this is what the product does out
of the box. **(2) The loss is silent and affirmatively contradicted** — the
screen states the opposite, and six consecutive refusals were reported as
success. **(3) R17 already ruled on this exact failure mode:** *"A student
losing an edit silently, while the status bar reads 'Saved', is the defect"*,
and required the interface to show the edit was not saved and retry it. V2-064
carries that ruling for the **contended** case at P1; this is the same pattern
on the **uncontended default** path, firing every time. A team can lose a
round's decisions while being told they are saved — that changes a published
result, and the legend says P0 blocks. The rules owner may re-rate it; a builder
should not.

### Assigned where the source proposed none

V2-076 **P1**, V2-077 **P2**, V2-078 **P2**, V2-079 **P1**, V2-094 **P1**,
V2-095 **P2**, V2-108 **P2**.

### Confirmed unchanged

Every other entry, each with a stated reason rather than an assertion. The ones
needing most care: **V2-085** (the effect is *symmetric* — no team gains a
relative advantage — which keeps a 25.64-point fit drag out of P1);
**V2-089/V2-090** (the charge is computed correctly; the thing sold is thin —
a calibration question, not a mis-computation); **V2-106** (the guard is working
correctly and nothing leaks); **V2-103** (not P2, because a ruled
participant-facing requirement is not cosmetic).

---

## 6. Status updates to existing findings

| Finding | Update | Commit / ruling | Proof |
|---|---|---|---|
| **V2-041** | Repaired, pending closure; **R24** settles the blank branch, **R26** ratifies the builder's Q7 call | `be0fa86`→`49ea50b` | `test_price_band` 45 OK; 300-test freeze regression |
| **V2-042** | Repaired, pending closure | `f035884` | 25 OK; falsification gives 8 failures + 4 errors of 24 |
| **V2-033** | **Amended** — helper and pilot rule unchanged; a competition precondition refuses lifecycle actions on an unowned course | `f035884` | `CompetitionOwnershipTests` |
| **V2-057** | **R23** answers it — research costs money, but **not through this field** | `d2059e4` | `test_paid_research` |
| **V2-060** | R11 built; the `* 10` is gone and **no constant replaces it** | `2f012c2` | 11 failures against the reverted engine |
| **V2-069** | **All four repaired by CRV2-12**, plus a seven-assertion prevention control in the suite and CI | CRV2-12 | zh-CN refusal asserted to contain no run of 3+ Latin chars; language queries measured 2 → 1 |
| **V2-071** | Both halves green, confirmed by two builders independently | `b562c63` | `Ran 132 tests, OK` |
| **V2-074** | Seven repaired; **none a product defect**, established by reproduction | `b562c63` | **No full suite has been run since** |
| **V2-084** | **Ruled (R29)** — closable by the auditor | — | — |
| **V2-085** | **Ruled (R25/R27), implemented**; two of my own figures corrected | `5a0419c` | invariants asserted against copies before applying |
| **V2-017** | Confirmed still open; citation corrected | — | — |

**Corrections I made to my own entries:** V2-085's media gated drag is
**0.1489**, not the 0.1630 I first recorded; and my claim that nothing depends
on the 0.99 weight sums is false for `campaign_engine.py:99`, which never
normalises.

---

## 7. Launch checklist

**Ticked: none, across the whole task.** No existing box is completed by any of
this. The recurring candidates are GSP-CRV2-10/11/12 *certification*, and every
builder states it closes no gate. **CRV2-12 is not complete — only its code half
is**, because Stage 4's two bilingual walkthroughs were not performed.

**Amended, not ticked.** *Operator concurrency* keeps its `[x]` (certified by
CRV2-02, still 0 unguarded) but is annotated twice: the original "0 of 214"
rested on a false positive (V2-079), and after the paid-research merge
introduced and repaired two genuinely unguarded routes (V2-087) it reads **219
mutating, 37 lifecycle-mutating, 21 guarded, 16 exempt, 0 unguarded** — a
re-measurement, not a re-certification.

**The browser-pass gate is amended to ATTEMPTED, NOT PASSED**, per instruction
and on the evidence. It records that the pass ran on `46b4bbe` in both
languages, that **the production build passes and is explicitly not a finding**,
that it found seven defects and repaired none, that **V2-107 is a P0**, its
coverage (one firm, one market, one scenario), and that **two of the seven
intended checks could not be verified at all because no route reaches the screen
(V2-103)**.

**Six gates added by this task:** full backend suite green on the freeze
candidate; the browser pass; `reset_simulation` withheld from the competition
deployment; a downgrade guard for migration `0085`; a focused replay for the
v5 → v6 envelope; and **GSP-CRV2-12 Stage 4's two bilingual walkthroughs**.

**Deliberately not ticked:** narrative-worker supervision;
`COMPETITION_REQUIRE_CLEAN_BUILD`; the combined load run (**frozen-candidate
load run, excluded**); GSP-CRV2-09's re-audit (**the final audit, excluded**);
and the competition-flag and non-owner-database-role entries, **preserved
unticked exactly as the owner left them**. The **NO-GO** decision is untouched.

---

## 8. Claims registered as stated, with the gap noted

1. **R16's caller investigation** — the nginx/journal half is not reproducible
   from this repository. The in-repo half I confirmed.
2. **The legacy-removal report's severities were never handed over.** Its
   preflight cites a document that does not exist; there are no `V2-0XX`
   placeholders anywhere. I assigned V2-076–V2-079 myself. **There is likewise
   no `P3` in this register's legend** — the briefing's premise that the report
   used one was wrong; the only `P3` in the record is a historical
   reclassification at `:1415`. The one real P3 came later, from CRV2-12, and is
   mapped at V2-099.
3. **The manifest envelope moved without a replay** — V2-086, registered rather
   than allowed to look clean.
4. **V2-104's success toast is read from source, not seen on screen.** The
   verifier drove that path through the API from the signed-in session rather
   than clicking the roster widgets. I confirmed the source reading
   (`InstructorDashboard.js:1955`); the on-screen behaviour is unverified.
5. **V2-105's Extend Deadline was inspected but never executed** — only its
   confirmation was opened.
6. **The browser pass covered one firm, one market, one scenario.** Its own
   "what remains unverified" section is honest about this and is reproduced in
   the gate rather than summarised away.
7. **Four handoffs shipped unexecuted frontend work**, and the browser pass is
   what that cost: of its seven findings, five are in frontend code that no
   builder had ever run.
8. **The pre-commit hook** answers differently depending on how it is called and
   nobody has isolated it — now V2-100, with the explicit note that it wants an
   owner rather than a fourth theory.
9. **I did not perform the CRV2-12 merge** (§2), and it remains outstanding.

---

## 9. Citations

Every file:line citation in every entry was resolved against the merged tree or,
for CRV2-12, against its branch. **None was dropped silently.**

**Corrected for drift:** `route_inventory.py:129-136`→`:194-202`;
`results_api.py:1061-1065`→`:1097-1101`; `bass_engine.py:313-345`→`:323-352`;
`coherence.py:302`/`:700`→`:301-304`/`:705`; `bass_engine.py:57-66`→`:66-72`;
`V2_FINDINGS_REGISTER.md:909`→`:946`; `cc32b_views.py:141-149`→`:142-149`.
Deleted legacy paths and the pre-repair detector are pinned to `e1b744c`.

**Two that initially failed to resolve and then did.** V2-104's toast — the
verifier cited `message.success('N student(s) assigned')`; a literal grep found
nothing because it is a template literal, ``message.success(`${userIds.length}
student(s) assigned`)`` at `InstructorDashboard.js:1955`. And V2-106's request,
which is `getTeamChanges` imported from `../api/decisions`, not a URL literal in
the component. Both are recorded so the next reader does not judge them stale.

**Every browser-pass line number matched the merged tree**, although the pass
ran on `46b4bbe` — neither CRV2-12 nor the verification branch changed any
frontend file, which is itself worth knowing.

**One citation correct in substance but not by the obvious route:**
`core/engine/utils.py:352-353` — the string `team_notifications` does not appear
there; it is the `db_table` of `TeamNotification`, created inside `notify_team`.

**Could not resolve: one, and it is not a file:line** — R16's nginx-log and
journal evidence.

**A trap worth recording:** V2-078 says `core/services/scoring.py` has no
importer, and a naive grep for `from .scoring import` finds three live edges —
none of them this module.

---

## 10. Commit record

Five commits, in coherent steps: (1) the first register block and its status
updates; (2) the checklist; (3) the merge to `17987b3` with block 2 and the
R23–R29 dispositions; (4) the merge of `414d718` and V2-095; (5) block 3
(V2-096–V2-108), the checklist's browser-pass amendment and Stage 4 gate, and
this report.

**All used `--no-verify`, and this says so — which is now itself registered as
V2-100.** The hook refuses on a revision mismatch (`.aide-checks-rev` present,
reading `e710f26`, against a runner reporting this repo's HEAD); its own header
sanctions the bypass and names the deploy gate as the layer that is not
bypassable. **The deploy gate has not been satisfied by anything I did.** My
changes throughout are three Markdown files under `handoff_readiness_v2/`.

## 11. What a reader should not take from this document

- **No finding is closed.** Eleven are "repaired, pending closure" and two are
  ruled. Closure is GSP-CRV2-09's.
- **No gate is certified.** The route-inventory figure is re-measured, not
  re-certified; the manifest envelope moved without its replay; the browser pass
  is attempted, not passed.
- **CRV2-12 is not complete** — its code half is.
- **Per-handoff green evidence does not compose.** V2-095 appeared only in the
  merged tree, and five of the browser pass's seven findings sat in code that
  every builder had declared done.
- Work still in flight continues the sequence from **V2-109**.
