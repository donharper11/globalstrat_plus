# Register backlog — ten completion reports, 2026-09-12

**Role:** programme registrar. **Date:** 2026-09-12.
**Branch:** `crv2-register-backlog-2026-09-12`, cut detached from
`crv2-release-integration` at `59347f4` and brought current as the integration
branch advanced under it six times. The main checkout was not modified, nothing
was pushed, no other worktree was read or written.
**Changed:** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md`, and this
report. **No runtime code and no test was changed.**

**Registered: V2-075 through V2-116 — forty-two findings** from ten completion
reports plus two raised directly by the release-integration owner. Nothing is
closed. Repairs are recorded **"repaired, pending closure"**; owner rulings are
recorded **ruled**. The registrar is not the auditor; GSP-CRV2-09 owns closure.

## Two open P0s, and they are the headline

- **V2-107** — the pricing screen's default row is refused by the API while the
  screen reads "Your entry is saved". Six consecutive saves were refused and
  reported as success. A team can lose a round's decisions believing they are
  saved. **This is the silent loss R17 ruled against.**
- **V2-110** — a solvent team (cash 27–50M) can lose an entire round to zero
  production, and the commercial-inactivity guard then costs it **up to 17.81
  index points**, against a best-single-lever value of **+12.40**. It decided
  the finishing order under identical competent play, and it **reproduces
  byte-identically in pre-existing evidence**, so it is live today.

Both are open and unrepaired. A third P0, **V2-075**, is repaired.

---

## 1. Records that existed only as uncommitted working-copy changes

The R15–R22 dispositions table, the `R22` annotation on V2-073, and the two
launch-checklist entries added 2026-09-12 were **not** on
`crv2-release-integration` at `59347f4` — they existed only in the main
checkout's working tree. I carried them onto this branch verbatim; they were
committed upstream at `7b8cd25` and my merge reconciled the copies.

**This produced a real defect, not just inconvenience.** R19 established that a
ruling exists in an `OWNER_RULINGS_*` document with a date and nowhere else. The
corollary is that a **committed** record is the only one another branch can see
— and that is exactly what caused the numbering collision in §3. The
paid-research builder made the same point unprompted about its own instructions.

---

## 2. Merges, and the one I declined to perform

The integration branch advanced six times during this task. I merged it each
time. Both conflicts fell in files I own, and in both the HEAD side was a strict
superset — my V2-074 row already contained upstream's text plus my status
update, and V2-073 carried the identical R22 annotation — so `--ours` discarded
nothing. Verified, not assumed: one V2-074 row, one V2-073 row, eight ruling
rows, no markers, no unmerged paths.

**I did not complete the CRV2-12 merge, deliberately.** It conflicts in
`backend/core/utils/participant_messages.py`, where integration's price-band and
paid-research keys collide with the sweep's. **That is a runtime content
decision belonging to the integration owner, not to a registrar whose remit is
explicitly "no runtime code."** I aborted it and verified every CRV2-12 citation
against the branch with `git show`, which gives the same reading without my
arbitrating someone else's code. **The merge remains outstanding.**

**On the instruction to rebase:** `e398fc6` is a merge *of this branch* into
integration, so my HEAD was already an ancestor of it. A rebase would have been
a no-op at best and would have replayed or flattened merge commits whose
conflict resolutions I had verified. I fast-forwarded instead, which achieves
the stated intent.

**Upstream rulings arriving mid-task corrected three entries I had already
written:** V2-084 is ruled by **R29**, V2-085 by **R25/R27** (and implemented at
`5a0419c`), and V2-041's Q7 is ratified by **R26**.

---

## 3. ID assignment, and a numbering collision

Four blocks; each range was unused when assigned; order is documented at the
head of each block in the register.

**The collision, and why it was structural rather than careless.** The CRV2-12
builder drafted its five entries as **V2-075–V2-079** — already assigned. Its
branch was cut from `46b4bbe`, and the V2-075–V2-085 block existed only on the
registrar branch until it reached integration at `e398fc6`, *after* that cut.
Renumbered **V2-096–V2-100 in the same documented order**; "CRV2-12's V2-075"
means **V2-096**, through to V2-079 → **V2-100**. The register says so
explicitly, because the completion report will outlive the correction.

| Block | Range | Source |
|---|---|---|
| 1 | V2-075–V2-085 | Five reports merged at `59347f4`: legacy-control removal, Stage 6, Stage 5, standing red tests, CRV2-11 round-zero |
| 2 | V2-086–V2-095 | Paid research, the org-structure cash path (owner-raised), and `414d718` |
| 3 | V2-096–V2-108 | CRV2-12 language sweep; first browser verification |
| 4 | V2-109–V2-116 | Distinct starter profiles (R28); the v6 envelope replay |

**Block 4 detail.** V2-109–V2-115 are the starter-profile report's findings 1–7
in its own order — so its finding 2, the most serious of the session, is
**V2-110**, in the middle of the range rather than at its head. V2-116 is the v6
replay report's §9 drift finding.

### Deliberately not given an ID

`LEGACY_CONTROL_REMOVAL` F5 (V2-017's existing remainder, citation corrected
`:129-136` → `:194-202`); `PAID_RESEARCH` finding 8 (a V2-057 status update);
the v6 report's docstring correction and migration-order observation (folded
into V2-086); R28's authoring task and every rules question; and Stage 6's own
draft numbering, which pre-numbered its findings `V2-056`/`V2-057` — both taken.

---

## 4. Sources reconciled into one finding

- **V2-075** — Stage 6 reported it and did not repair it; R16 ruled deletion;
  the removal handoff deleted it. One finding with a repair, not three.
- **V2-076** is separate: the routed exposure is closed, the CLI one is not.
- **V2-079** is separate from V2-075 — one is the exposed route, the other is
  why the guard could not see it, and the detector defect outlives the route.
- **V2-088** — flagged in passing by the paid-research builder as "not mine",
  raised and verified independently by the release-integration owner. One ID,
  both attributions.
- **V2-099 is deliberately not folded into V2-069's fourth defect** — different
  queries against the same table; V2-069's is repaired and this is not, and
  folding them would let the fixed one hide the open one.
- **V2-100 supersedes** my earlier decision to leave the pre-commit hook
  unregistered. That was too lenient.
- **V2-086** absorbed the v6 report's two minor corrections rather than
  spawning numbers for them.

---

## 5. Severities changed from what the source proposed — eleven

Legend: **P0 blocks; P1 degrades; P2 cosmetic** — and anything that can change a
published result is never P2.

| ID | Proposed | Landed | Why |
|---|---|---|---|
| V2-075 | P1 | **P0** | V2-032 and V2-051 — same class, smaller blast radius — are both P0 here. |
| V2-080 | P2 | **P1** | These are the five destructive lifecycle confirmations; V2-061 is the precedent. |
| V2-084 | P2 | **P1** | V2-043's rule: round-0 rows are stored state inside the certified envelope. |
| V2-099 | **P3** | **P2** | The legend defines no P3; precedent at `:1415`. Duplicated work is not a wrong answer. |
| V2-100 | P2 | **P1** | The pre-commit layer has been bypassed on every commit all session and protects nothing. V2-071/V2-074 are P1 on the same principle. |
| V2-107 | P1 (asked P0) | **P0** | See below. |
| V2-112 | P2 | **P1** | Two supported entry points producing **different games** from the same scenario; a whole authored `beta` block is silently discarded on the CLI path. |
| V2-113 | **P3** | **P2** | Same mapping as V2-099. |
| V2-114 | P2 | **P1** | The price lever is effectively dead in two of three shipped scenarios. **V2-023 is the precedent, pointedly** — these keys exist because of it, and the same four numbers were copied into all three. |
| V2-115 | **P3** | **P2** | Same mapping. |
| V2-116 | P2 | **P1** | The cost lands on a launch gate: CRV2-09 owns the four-environment matrix and the fixture that produces its evidence does not run. |

**V2-107 — the reasoning on the record.** The builder rated P1 (a fully-filled
row saves; the lock path validates server-side) and flagged P0 as possible.
Three things decide it: **the failing path is the default one**; **the loss is
silent and affirmatively contradicted**, with six consecutive refusals reported
as success; and **R17 already ruled on this exact failure mode** — *"A student
losing an edit silently, while the status bar reads 'Saved', is the defect"*.
V2-064 carries that ruling for the **contended** case at P1; this is the same
pattern on the **uncontended default** path, firing every time.

**V2-110 — P0, and the builder flagged it as a P0 candidate rather than
under-rating its own finding.** It decided the finishing order under identical
play; it outweighs the strongest decision lever (17.81 against 12.40), which
makes it the V2-024 class — an outcome a team cannot overcome by playing well;
and it pre-dates this work, reproducing byte-identically in the prior four-team
replay. Its root cause is **not** established, which is recorded rather than
glossed, with V2-102 and V2-107 offered as leads and not conclusions.

### Assigned where the source proposed none

V2-076 **P1**, V2-077 **P2**, V2-078 **P2**, V2-079 **P1**, V2-094 **P1**,
V2-095 **P2**, V2-108 **P2**.

### On P3

The briefing said the legacy-removal report used a `P3` the legend does not
define. **It did not** — that report proposed no severities at all, and the only
`P3` in the historical record is a reclassification note at `:1415`. Three real
P3s did arrive later, from CRV2-12 and the starter-profile work, and are mapped
at **V2-099, V2-113 and V2-115**.

---

## 6. Status updates to existing findings

| Finding | Update |
|---|---|
| **V2-041** | Repaired, pending closure; **R24** settles the blank branch, **R26** ratifies the builder's Q7 call |
| **V2-042** | Repaired, pending closure; falsification reproduces the finding verbatim |
| **V2-033** | **Amended** — helper and pilot rule unchanged; a competition precondition refuses lifecycle actions on an unowned course |
| **V2-057** | **R23**: research costs money, but **not through this field** |
| **V2-060** | R11 built; the `* 10` is gone and no constant replaces it |
| **V2-069** | **All four repaired by CRV2-12**, plus a seven-assertion prevention control in the suite and CI |
| **V2-071 / V2-074** | Repaired; **none of the seven was a product defect**, established by reproduction. No full suite has been run since |
| **V2-084** | **Ruled (R29)** — closable by the auditor |
| **V2-085** | **Ruled (R25/R27), implemented** at `5a0419c`; two of my own figures corrected |
| **V2-086** | **The replay has now been run and passed** at `3d8c2b3` — byte-identical, three negative controls refusing before the engine, one on the new section itself. Single-environment; closes no gate |
| **V2-017** | Confirmed still open; citation corrected |
| **R28 disposition** | Authoring landed at `d94d6b1` (V2-109); **the balance half cannot be completed while V2-110 is live**, which is why Stage 2 balance stays open |

**Corrections to my own entries:** V2-085's media gated drag is **0.1489**, not
0.1630; and my claim that nothing depends on the 0.99 weight sums is false for
`campaign_engine.py:99`, which never normalises.

---

## 7. Launch checklist

**Ticked: none, across the whole task.** No existing box is completed by any of
this, and I did not manufacture one. The recurring candidates are
GSP-CRV2-10/11/12 *certification*, and every builder states it closes no gate.

**Amended, not ticked.** *Operator concurrency* keeps its `[x]` but records that
the original "0 of 214" rested on a false positive (V2-079) and now reads **219
mutating, 37 lifecycle-mutating, 21 guarded, 16 exempt, 0 unguarded** — a
re-measurement, not a re-certification. The *browser-pass* gate is amended to
**ATTEMPTED, NOT PASSED**, with its coverage (one firm, one market, one
scenario), the fact that **the production build passes and is explicitly not a
finding**, and that **two intended checks could not be verified at all because
no route reaches the screen (V2-103)**. The *v6 replay* gate records that the
regression **ran and passed** but stays **open** pending CRV2-09's
four-environment evidence.

**Seven gates added by this task:** full backend suite green on the freeze
candidate; the browser pass; `reset_simulation` withheld from the competition
deployment; a downgrade guard for migration `0085`; the v6 envelope replay;
**GSP-CRV2-12 Stage 4's two bilingual walkthroughs**; and **the R28
starting-field balance measurement, explicitly blocked pending V2-110**.

**Deliberately not ticked:** narrative-worker supervision;
`COMPETITION_REQUIRE_CLEAN_BUILD`; the combined load run (**frozen-candidate
load run, excluded**); GSP-CRV2-09's re-audit (**the final audit, excluded**);
and the competition-flag and non-owner-database-role entries, **preserved
unticked exactly as the owner left them**. The **NO-GO** decision is untouched —
and with two open P0s it is now better supported than when I started.

---

## 8. Claims registered as stated, with the gap noted

1. **R16's caller investigation** — the nginx/journal half is not reproducible
   from this repository. The in-repo half I confirmed.
2. **The legacy-removal report's severities were never handed over.** Its
   preflight cites a document that does not exist; there are no `V2-0XX`
   placeholders anywhere. I assigned V2-076–V2-079 myself.
3. **V2-110's root cause is not diagnosed.** The builder establishes the
   mechanism and the magnitude but not why the marketing rows were absent. That
   is the first question its repairing handoff must ask.
4. **V2-104's success toast is read from source, not seen on screen**; the path
   was driven through the API rather than the roster widgets.
5. **V2-105's Extend Deadline was inspected but never executed.**
6. **The browser pass covered one firm, one market, one scenario**, and the v6
   replay one environment, one round, one scenario. Both say so themselves and
   both are recorded that way in the gates.
7. **Four handoffs shipped unexecuted frontend work**, and the browser pass is
   what that cost: five of its seven findings are in frontend code no builder
   had ever run.
8. **The pre-commit hook** answers differently depending on how it is called and
   nobody has isolated it — now V2-100, with the note that it wants an owner
   rather than a fourth theory.
9. **I did not perform the CRV2-12 merge** (§2), and it remains outstanding.

---

## 9. Citations

Every file:line citation in every entry was resolved against the merged tree or,
for unmerged branches, against the branch itself. **None was dropped silently.**

**Corrected for drift:** `route_inventory.py:129-136`→`:194-202`;
`results_api.py:1061-1065`→`:1097-1101`; `bass_engine.py:313-345`→`:323-352`;
`coherence.py:302`/`:700`→`:301-304`/`:705`; `bass_engine.py:57-66`→`:66-72`;
`V2_FINDINGS_REGISTER.md:909`→`:946`; `cc32b_views.py:141-149`→`:142-149`.
Deleted legacy paths and the pre-repair detector are pinned to `e1b744c`.

**Two that initially failed to resolve and then did.** V2-104's toast is a
template literal — ``message.success(`${userIds.length} student(s) assigned`)``
at `InstructorDashboard.js:1955` — which a literal grep missed; and V2-106's
request is `getTeamChanges`, not a URL literal in the component.

**Checked rather than copied.** V2-114's claim that the same four reference
prices are shared across all three scenarios was verified by reading all three
YAMLs: `250/420/700/1000`, identical, **each tagged "(V2-023)"**. V2-113's
mismatch was verified on both sides (`verify_scenario_schema.py:29` against
`models/scenario.py:544`). V2-097's stated reason for deferral was checked and
has **lapsed** — the frontend it was waiting on was never touched.

**One citation correct in substance but not by the obvious route:**
`core/engine/utils.py:352-353` — `team_notifications` is the `db_table` of
`TeamNotification`, created inside `notify_team`.

**Could not resolve: one, and it is not a file:line** — R16's nginx-log and
journal evidence.

---

## 10. Commit record

Six commits, in coherent steps: (1) the first register block and its status
updates; (2) the checklist; (3) the merge to `17987b3` with block 2 and the
R23–R29 dispositions; (4) the merge of `414d718` and V2-095; (5) block 3
(V2-096–V2-108) with the browser-pass amendment and Stage 4 gate; (6) block 4
(V2-109–V2-116), V2-086's update, the R28 disposition, the R28 balance gate and
this report.

**All used `--no-verify`, and that is now itself registered as V2-100.** The
hook refuses on a revision mismatch; its own header sanctions the bypass and
names the deploy gate as the layer that is not bypassable. **The deploy gate has
not been satisfied by anything I did.** My changes throughout are three Markdown
files under `handoff_readiness_v2/`.

## 11. What a reader should not take from this document

- **No finding is closed.** Fourteen are "repaired, pending closure" and two are
  ruled. Closure is GSP-CRV2-09's.
- **No gate is certified.** The route inventory is re-measured, not
  re-certified; the v6 replay is single-environment; the browser pass is
  attempted, not passed.
- **CRV2-12 is not complete** — its code half is. **CRV2-11 Stage 2 balance is
  not complete** and cannot be while V2-110 is live.
- **Per-handoff green evidence does not compose.** V2-095 appeared only in the
  merged tree; five of the browser pass's seven findings sat in code every
  builder had declared done; and V2-110 was invisible until eight firms were
  put on the board.
- Work still in flight continues the sequence from **V2-117**.
