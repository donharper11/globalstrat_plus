# Register backlog — six merged completion reports, 2026-09-12

**Role:** programme registrar. **Date:** 2026-09-12.
**Branch:** `crv2-register-backlog-2026-09-12`, cut detached from
`crv2-release-integration` at `59347f4` in an isolated worktree, then merged up
to `17987b3` when the paid-research work landed mid-task. The main checkout was
not modified, nothing was pushed, no other worktree under `.claude/worktrees/`
was read or written.
**Changed:** `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md`, and this
report. **No runtime code and no test was changed.**

**I closed nothing.** Where merged work repairs a finding, it is recorded
**"repaired, pending closure"**. The registrar is not the auditor; GSP-CRV2-09
owns closure. Where an owner ruling disposes of a finding, that is recorded as
**ruled** — also not closed.

---

## 1. Two records existed only as uncommitted working-copy changes

The "Owner rulings landed 2026-09-12 — dispositions" table (R15–R22), the `R22`
annotation on V2-073's row, and the two launch-checklist entries added
2026-09-12 (the competition flag, the non-owner database role) were **not on
`crv2-release-integration` at `59347f4`**. They existed only as uncommitted
modifications in the main checkout's working tree, alongside the then-untracked
`OWNER_RULINGS_2026-09-12.md`.

I was instructed to preserve all three, so I carried them onto this branch
verbatim before appending anything of my own. **They have since been committed
upstream** at `7b8cd25`, and my merge reconciled the two copies — see §2.

**This is worth an owner's attention in its own right.** R19 established that a
ruling exists when it is in an `OWNER_RULINGS_*` document with a date, and
nowhere else. The corollary this session hit is that a **committed** record is
the only one another branch can see: five builders working in parallel worktrees
could not see R15–R22 at all, and two of them acted on rulings relayed out of
band. The paid-research builder's own §12 question 7 makes the same point
unprompted — *"the owner instruction behind this work reached me through the
handoff, not through a dated `OWNER_RULINGS_*` document. It should be recorded
in one to count as a ruling."*

---

## 2. The mid-task merge, and how the conflict was resolved

The integration branch advanced under me, by more than the two additions I was
told about: `7b8cd25` (rulings R15–R25 committed, with register dispositions),
`a9217ca` (R26–R29), `5a0419c` (the preference re-authoring implementing R25),
`56292ec`, `c87395c` and the merges `d2059e4` / `17987b3`.

Merging produced conflicts in both files I own. **In both, the HEAD side was a
strict superset:** my V2-074 row already contained the upstream text plus my
status update, and my V2-073 row carried the identical R22 annotation. Taking
`--ours` therefore discarded nothing from upstream, which I verified rather than
assumed — one `V2-074` row, one `V2-073` row, all eight owner ruling rows
intact, no conflict markers, no unmerged paths.

**The upstream rulings arriving mid-task changed three entries I had already
written**, and all three are corrected rather than left standing:

- **V2-084** — I registered it as open, awaiting the owner. **R29 rules on it
  directly:** keep the new column meaning. Updated to ruled, closable by the
  auditor.
- **V2-085** — I registered it as open, no data retuned. **R25 ruled re-author,
  and `5a0419c` implemented it.** Updated to repaired pending closure, with two
  factual corrections to my own text (below).
- **V2-041** — I recorded Q7 as "a rules call the builder made rather than
  received". **R26 ratifies it.** Updated.

---

## 3. ID assignment table

Continuing from **V2-075**; the ranges V2-075–V2-085 and V2-086–V2-094 were both
unused anywhere in the repository. Assignment order is documented at the head of
each block in the register, in the form the V2-056 block uses.

### Block 1 — the five reports merged at `59347f4`

| ID | Source | What it is | Sev | Status |
|---|---|---|---:|---|
| V2-075 | Stage 6 finding 1, reconciled with `LEGACY_CONTROL_REMOVAL` + R16 | Legacy `/simulation-control/` routed with no ownership check; `_reset` unscoped across the deployment — one judge's reset would reset every heat | **P0** | Repaired by deletion at `a37bb92` |
| V2-076 | `LEGACY_CONTROL_REMOVAL` F2 | The same unscoped SQL survives as the `reset_simulation` management command | **P1** | Open |
| V2-077 | `LEGACY_CONTROL_REMOVAL` F1 | `round_engine.advance_round` referenced an unbound `stakeholders`; the legacy `advance` was already dead | P2 | Closed by the deletion |
| V2-078 | `LEGACY_CONTROL_REMOVAL` F3 | `core/services/scoring.py` is now unreferenced | P2 | Open |
| V2-079 | `LEGACY_CONTROL_REMOVAL` §3 | `uses_boundary` substring-matched, certifying a lifecycle route as guarded on a name collision | **P1** | Repaired at `d9cbd43` |
| V2-080 | Stage 6 finding 2 | `RoundControlCard.js` entirely untranslated — five destructive confirmations in English | **P1** | Open |
| V2-081 | Stage 5 §6 row 1 | `RoundResultsView` declares no `permission_classes` | P2 | Open |
| V2-082 | Stage 5 §6 row 2 | Price-band events carry `request_id=''` | P2 | Open |
| V2-083 | `STANDING_RED_TESTS` | Two green tests in `RdSpendTargetTests` pass vacuously | P2 | Open |
| V2-084 | `GSP-CRV2-11` entry 2 | Round-0 `team_share_pct` changed meaning | **P1** | **Ruled (R29)** — closable |
| V2-085 | `GSP-CRV2-11` entry 3 | Gen-1 unreachable preference weight is two mechanics | P2 | **Ruled (R25/R27), implemented at `5a0419c`** |

### Block 2 — the paid-research merge and the cash path beside it

| ID | Source | What it is | Sev | Status |
|---|---|---|---:|---|
| V2-086 | `PAID_RESEARCH` §7 + §9 | Manifest envelope v5 → v6; **no replay regression run**, though R18 requires one | **P1** | Open |
| V2-087 | `PAID_RESEARCH` finding 6 | Two lifecycle-mutating routes genuinely unguarded once research became a write | **P1** | Repaired at `c87395c` |
| V2-088 | `PAID_RESEARCH` finding 7 + the release-integration owner's own verification | Organisational-structure switch charges cash outside every calculator, irreversibly | **P1** | Open |
| V2-089 | `PAID_RESEARCH` finding 2 | The `channels` report is a hardcoded constants table | P2 | Open |
| V2-090 | `PAID_RESEARCH` finding 3 | The `products` report is mostly the team's own data | P2 | Open |
| V2-091 | `PAID_RESEARCH` finding 4 | `research_allocated` emitted and rendered nowhere | P2 | Repaired |
| V2-092 | `PAID_RESEARCH` finding 5 | `StakeholdersTab` had no `.catch` | P2 | Repaired |
| V2-093 | `PAID_RESEARCH` finding 1 | A handoff cited `price_band_pct` as landed precedent when it did not exist | P2 | Open |
| V2-094 | `PAID_RESEARCH` §9 | A team is charged for an analyst query **without being shown the price** | **P1** | Open |

### Deliberately **not** given an ID

- **`LEGACY_CONTROL_REMOVAL` F5** — V2-017's own explicitly open remainder, which
  R13 already carried forward. Recorded as a status note on V2-017, **with its
  citation corrected** (`route_inventory.py:129-136` → `:194-202`).
- **`LEGACY_CONTROL_REMOVAL` F4** — the pre-commit hook fails on a revision
  mismatch. Four of six handoffs report it identically; it describes the checks
  tooling, not this product. See §8.
- **`PAID_RESEARCH` finding 8** — "V2-057's open question is now materially
  different" is a status update to V2-057, not a new finding.
- **R28's new authoring task** (more starter profiles) and every §12 rules
  question — the owner's, not mine.
- **Stage 6's own draft numbering**, which pre-numbered its two findings
  `V2-056` and `V2-057` — both already taken. Its completion report is the
  correct authority: IDs are allocated by the release-integration pass.

---

## 4. Sources reconciled into a single finding

**V2-075 — one finding described three times.** Stage 6 reported the unscoped
reset and ownership gap and explicitly did **not** repair it; R16 ruled the
legacy engine deleted; the legacy-removal handoff deleted it at `a37bb92`. That
is one finding with a repair. Registering the description and the removal
separately would have put the same defect on the register twice and made the
repair look like it addressed something else.

**V2-076 is genuinely separate.** The routed exposure is closed; the CLI one is
not. `_reset` imported its table lists *from*
`core/management/commands/reset_simulation.py`, which is untouched. Deleting the
view removed the authenticated HTTP path to that SQL and nothing else. I read
both reports before writing either, as instructed.

**V2-079 is separated from V2-075 deliberately.** V2-075 is the exposed route;
V2-079 is why the guard could not see it. V2-079 outlives V2-075 — the route is
gone, but the detector defect was a property of the verification apparatus and
would have hidden any other same-named collision.

**V2-088 — two independent reports of one defect.** The paid-research builder
flagged it in passing as a "P1 candidate… not mine"; the release-integration
owner raised and verified it independently with fuller evidence. One finding,
one ID, both attributions recorded.

**V2-060 / R11 and V2-057 / R23** were likewise folded into the existing entries
as status updates rather than duplicated as new ones, which is what both source
reports asked for.

---

## 5. Severities changed from what the source proposed

The legend: **P0 blocks; P1 degrades; P2 cosmetic** — and anything that can
change a published result is never P2.

| ID | Proposed | Landed | Why |
|---|---|---|---|
| V2-075 | **P1** (Stage 6) | **P0** | P1 does not fit a route that let any authenticated instructor destroy every concurrent heat's competition data with no ownership check. This register rated **V2-032** and **V2-051** — the same class, smaller blast radius — both **P0**. Recorded as a P0 already repaired, not an open blocker. |
| V2-080 | **P2** (Stage 6: "no integrity effect") | **P1** | P2 means cosmetic. This is the lifecycle control surface, and all five destructive confirmations are hardcoded English. An operator acting on a confirmation they cannot read changes what a round resolves. **V2-061** set the P1 precedent for English-only text at the point a decision is made; this is its operator equivalent. |
| V2-084 | **P2** (CRV2-11) | **P1** | On this register's own **V2-043** reasoning: round-0 adoption rows are stored state inside the certified output envelope, and anything that can change a published result is never P2. Stated plainly in the entry: no competitive outcome moves. R29 has since ratified the change itself; the rating rests on the envelope rule, which the ruling does not address. |

### Assigned where the source proposed none

V2-076 **P1**, V2-077 **P2**, V2-078 **P2**, V2-079 **P1**, V2-094 **P1**.

Two worth restating. **V2-076 is P1, not P0**, because it is a deliberate
operator action behind shell access rather than an authenticated route, so it
blocks nothing on its own — and emphatically not P2, because running it during a
competition destroys published results across every heat. **V2-094 is P1**
because a team can spend up to $250,000 per round on analyst queries without the
price ever being displayed, and cash feeds financials and the performance index.

### Confirmed unchanged

V2-081, V2-082, V2-083, V2-085, V2-089, V2-090, V2-091, V2-092, V2-093 — all
**P2** as proposed; V2-086, V2-087, V2-088 — all **P1** as proposed. Each entry
states *why* it survives the "published result" test rather than asserting it.
The two that needed most care:

- **V2-085**: the effect is **symmetric** — every team is pinned at level 0 on a
  zero-ceiling feature — so no team gains a relative advantage and no ranking
  moves. That is what keeps a 25.64-point fit drag out of P1.
- **V2-089/V2-090**: the charge is computed correctly and consistently; what is
  wrong is that the thing sold has little content. A value question for price
  calibration, not a mis-computation.

### On the "P3" label

**The briefing said the legacy-removal report uses a P3 label the legend does
not define. It does not.** I grepped the report, its inventory and all of
`handoff_readiness_v2/`: the only `P3` occurrences in the entire programme
record are at `V2_FINDINGS_REGISTER.md:1415-1416`, a historical note that an
unrelated finding was *reclassified from P3 to P1*. The legacy-removal report
proposes **no severities at all** — see §8. There was nothing to map, and I did
not invent a mapping.

---

## 6. Status updates to existing findings

| Finding | Update | Commit | Proof |
|---|---|---|---|
| **V2-041** | Heading → "repaired, pending closure"; full status block; **R24** settles the blank branch and **R26** ratifies the builder's Q7 call | `6b703e0`→`be0fa86`→`a9b4039`→`49ea50b` | `test_price_band` 45 OK; freeze regression 300 tests/175.780s OK; fails without the change (`price_band.py` absent at `cbe2656`) |
| **V2-042** | Heading → "repaired, pending closure"; status block | `f035884` | `test_cohort_caps` 25 OK; **falsification** with the six files reverted gives 8 failures + 4 errors of 24, reproducing the finding verbatim |
| **V2-033** | **Amended** — the entry said "withdrawn… no code change alters that" while Stage 6 said the repair was there. Both now stated: helper and pilot rule unchanged; a competition precondition refuses lifecycle actions on an unowned course | `f035884` | `CompetitionOwnershipTests`, incl. `test_the_refusal_is_recorded` |
| **V2-057** | **R23** answers the open question — research costs money, but **not through this field**; purchases are their own committed line, `research_budget` stays a declaration | `d2059e4` | `test_paid_research` (17) |
| **V2-060** | R11 implemented; the `* 10` is gone and **no constant replaces it** | `2f012c2` | `test_round_zero_adoption`; **11 failures across 8 of 9** against the reverted engine |
| **V2-071** | Both halves green, confirmed by two builders independently; **V2-079 added beside it** | `b562c63` + the inventory refresh | `Ran 132 tests, OK` |
| **V2-074** | The seven repaired; **none a product defect**, established by reproduction; coverage gained 92 → 94 | `b562c63` | Run 2 reproduced V2-074's exact seven first. **No full suite has been run since** |
| **V2-084** | **Ruled by R29** — the new column meaning is kept; closable by the auditor | — | — |
| **V2-085** | **Ruled by R25/R27 and implemented**; two of my own figures corrected | `5a0419c` | 182 row actions, invariants asserted against copies before applying; audit regenerated |
| **V2-017** | Confirmed **still open**; citation corrected `:129-136` → `:194-202` | — | `mutating_routes()` still does `if view_class is None: continue` |
| **V2-073** | `R22` annotation preserved through the merge | `7b8cd25` | — |

**Two corrections I made to my own V2-085 entry**, both surfaced by the
re-authoring work and both recorded in the register rather than quietly fixed:
media's worst gated drag is **0.1489**, not the 0.1630 I first recorded; and my
claim that nothing depends on the 0.99 weight sums is true of every scorer but
one — `campaign_engine.py:99` accumulates `weight × strength × multiplier` and
**never normalises**, so a 0.99 vector yielded ~1% less campaign bonus.

---

## 7. Launch checklist

### Ticked

**None.** No box on the existing list is genuinely completed by the merged work,
and I did not manufacture one. The two candidates — GSP-CRV2-10 and GSP-CRV2-11
certification — are **certification** gates, and every one of the six builders
states explicitly that it closes no gate. Stage 5 and Stage 6 are two stages of
CRV2-10; the CRV2-11 work is R11 plus Stage 5 of that handoff.

### Amended, not ticked

- **Operator concurrency fail-closed.** Left `[x]` — certified by CRV2-02, and
  the re-measured figure is still 0 unguarded — but annotated twice: the
  original "0 of 214" rested on one false positive (V2-079), and after the
  paid-research merge introduced and repaired two genuinely unguarded routes
  (V2-087) the inventory now reads **219 mutating, 37 lifecycle-mutating, 21
  guarded, 16 exempt, 0 unguarded**, both `--check` commands clean. Recorded as
  a **re-measurement, not a re-certification**.
- **Outstanding paragraph** — extended with V2-017's corrected citation and the
  full V2-075–V2-094 disposition summary.

### Deliberately not ticked

Narrative worker supervision (deployment action, V2-068 open); the combined
deadline-burst load run (**frozen-candidate load run, excluded by instruction**,
and CRV2-07's evidence must not be relabelled); `COMPETITION_REQUIRE_CLEAN_BUILD`
(deployment action); GSP-CRV2-10/11/12/13 certification; GSP-CRV2-09's re-audit
and final GO/NO-GO (**the final audit, excluded by instruction**); and the
competition-flag and non-owner-database-role entries, **preserved unticked
exactly as the owner left them**. The **NO-GO** decision is untouched.

### New gates added (five)

1. **Full backend suite run and green on the freeze candidate** — the seven red
   tests are repaired, but no full suite has run since and the suite has never
   been green (842 tests at `acee4ea`: 4 failures, 3 errors).
2. **Browser pass** over `MarketingPage.js`/`ResultsPage.js`,
   `RoundControlCard.js` and now `MarketResearchPage.js`/`BudgetBar` —
   `node_modules` was absent in **three** builders' worktrees.
3. **`reset_simulation` withheld from the competition deployment** (V2-076).
4. **Downgrade guard for migration `0085`** — a resolved round can now
   legitimately contain null `retail_price` rows.
5. **Focused replay regression for the v5 → v6 envelope change** (V2-086), with
   the consequence stated on the gate itself: across this point **every round
   will differ even where no outcome does**, so a hash diff here is not evidence
   of an engine change.

---

## 8. Claims registered as stated, with the gap noted

1. **R16's caller investigation** — zero hits across rotated nginx logs and 60
   days of journal. Those logs are not in this repository and **I could not
   reproduce that half**. The in-repository half I confirmed. Noted in V2-075.
2. **The legacy-removal report's severities were never handed over.** Its
   preflight states *"Proposed severities are in the register entries handed
   over separately"*. **No such document exists** — there are no `V2-0XX`
   placeholders anywhere in the repository, and its §6 carries F1–F5 as prose
   with no severity. I assigned V2-076–V2-079 myself against the legend and said
   so in each entry. This is the largest gap between the briefing and the tree.
3. **The manifest envelope moved without a replay** — registered as V2-086
   rather than allowed to look clean, exactly as instructed. The builder records
   the omission itself.
4. **Three handoffs handed over unexecuted frontend work.** Stage 5, Stage 6 and
   paid research all state that `node_modules` was absent. The paid-research
   report puts it most plainly: *"The frontend is entirely unexecuted… I am not
   claiming it works."* Recorded in each entry and covered by gate 2.
5. **The `is_competition` flag is a silent dependency** — Stage 6's protection
   fires only if it is set, with no error, banner or log line if it is not.
   Recorded in the V2-033 amendment as a condition on closure.
6. **The pre-commit hook answers differently depending on how it is called.**
   The standing-red-tests builder found the same runner with the same arguments
   reports `revision e710f26 matches` and exits 0 directly, but reports a
   mismatch and exits 2 from the hook. Unresolved, and their generalisation is
   the reason it is recorded: *a gate that answers differently depending on how
   it is called is a gate nobody can read* — the same shape as V2-071 and
   V2-079.
7. **V2-094 is registered although it is not one of the report's numbered
   findings.** It sits in its "what is NOT verified" section. I registered it
   because it is a stated participant-facing shortfall rather than a rules
   question, and the eight numbered findings do not cover it.

---

## 9. Citations resolved, corrected, or unresolved

Every file:line citation in every entry was resolved against this branch.
**None was dropped silently.**

### Corrected — moved by the merges

| As given | Corrected to | Why |
|---|---|---|
| `route_inventory.py:129-136` (V2-017 blind spot) | `:194-202` | The detector rewrite at `d9cbd43`; behaviour unchanged |
| `results_api.py:1061-1065` (`InstructorTeamDecisionsView` GET-only) | `:1097-1101` | Stage 6 added 9 lines to the file. Still GET-only: one `def get`, no write handler |
| `bass_engine.py:313-345` (V2-060's `prev_round < 1`) | `:323-352` | Stage 5's `49ea50b` added 12 lines |
| `coherence.py:302` / `:700` | `:301-304` / `:705` | Same commit's insertions |
| `bass_engine.py:57-66` (the offer gate) | `:66-72`; the `.exclude(retail_price__isnull=True)` at `:72` | The rework's comment block |
| `V2_FINDINGS_REGISTER.md:909` (Stage 6 → V2-033) | `:946` | The register grew |
| `cc32b_views.py:141-149` (paid research → the cash charge) | `:142-149`, the charge itself at `:148-149` | Off by one at the block start |
| `manifest_sections.py:288` / `:482` | resolve exactly | — |
| Pre-repair detector (`route_inventory.py:125-126`, `:61-67`, `:101`, `:160-165`) and every deleted legacy path (`urls.py:262`, `course.py:662-1026`, `core.py:135-147`, `round_engine.py:550`/`:567`, `instructor.js:87-90`) | retained, pinned to `e1b744c` | The code no longer exists; the citations are pinned to the revision where it did |

### Resolved exactly as cited

`game_scope.py:75`; `revenue.py:70-124`; `preference_engine.py:359`, `:70-78`;
`middleware.py:210-277`; `results_api.py:85`; `lifecycle.py:79-83`, `:42`;
`competition_audit.py:65`; `scoring.py:84`/`:179`; `reset_simulation.py:17`,
`:73`, `:303`, `:321`, `:389-390`; `bootstrap.py:42`, `:103`, `:304`,
`:418-427`; `test_scoring_dispositions.py:139`/`:180`/`:186`/`:203`;
`test_staffing_adequacy.py:144`/`:193`/`:204`/`:221`;
`route_inventory.py:168-192`; `campaign_engine.py:99`;
`research_reports.py:454-522`; `MarketResearchPage.js:916`;
`price_band_pct` at `:38` of all three YAMLs; migrations `0085`, `0086`, `0087`.

### One citation correct in substance but not by the obvious route

`core/engine/utils.py:352-353` — the "one real collision", a `TRUNCATE` target
the competition engine writes — **resolves**, but the string
`team_notifications` does not appear in `utils.py`. It is the `db_table` of
`TeamNotification`, created at `:352-353` inside `notify_team` (`:349`).
Recorded in V2-076 so the next reader does not judge the citation stale.

### Could not resolve

**One, and it is not a file:line citation:** R16's nginx-log and journal
evidence (§8 item 1). Everything else resolved.

**A trap worth recording:** V2-078 says `core/services/scoring.py` has no
importer, and a naive grep for `from .scoring import` finds three live edges —
`core/models/__init__.py:37`, `core/views/__init__.py:12`,
`core/serializers/__init__.py:13`. **None is this module.** The claim is
correct: nothing under `backend/` imports `core.services.scoring`.

---

## 10. Commit record

Three commits, in coherent steps rather than one lump:

1. the first register block — V2-075–V2-085, the status updates, and the
   owner's rulings table carried over from the main checkout's working copy;
2. the launch checklist — four new gates and the operator-concurrency
   amendment;
3. the merge of `crv2-release-integration` up to `17987b3`, carrying its
   conflict resolution, the second register block (V2-086–V2-094), the
   R23–R29 dispositions, the further status updates that the newly committed
   rulings forced, the checklist's fifth gate and re-measured route counts, and
   this report.

The third is a merge commit and therefore also carries the incoming
paid-research runtime changes, which are the integration branch's, not mine. My
own changes in it are confined to the three Markdown files under
`handoff_readiness_v2/`.

**All used `--no-verify`, and this says so.** The pre-commit hook refuses on an
aide-checks revision **mismatch** — `checks/.aide-checks-rev` is present and
reads `e710f26` while the runner is built from the branch, so `run-checks` exits
2 in every mode rather than emit a pass it cannot stand behind. The hook's own
header sanctions the bypass: *"Bypassable with `--no-verify`; the deploy gate is
the layer that is not."* Re-vendoring is out of scope, nothing here deploys, and
**the deploy gate has not been satisfied by anything I did.** This work changes
only Markdown under `handoff_readiness_v2/`.

## 11. What a reader should not take from this document

- **No finding is closed.** Nine moved to "repaired, pending closure" and two
  are recorded as ruled. Closure is GSP-CRV2-09's.
- **No gate is certified.** The route-inventory figure is re-measured, not
  re-certified, and the manifest envelope moved without the replay R18 asks for.
- **The remaining builders have handed in nothing that is registered here.**
  This covers exactly the six reports merged at `17987b3`.
