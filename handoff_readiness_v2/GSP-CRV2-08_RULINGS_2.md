# GSP-CRV2-08 — disposition on V2-030 and V2-031

> ## CORRECTION 2026-08-31 — section 2 of this document is WRONG
>
> **The audit at `8644ad4` returned FAIL / REWORK and found that the dispute-5
> repeat contains a false-positive assertion. It is right. Section 2 below told
> the builder not to rerun dispute 5. Ignore that instruction.**
>
> Verified independently against the artifact: `operatorLog.outcomes` holds ten
> entries, all `committed`; `operatorApi.rejectedCount` is `0`; and the harness
> marks "committed and refused actions are both visible" as passed when
> `committed` is merely present. The step's own detail line reads
> `outcomes shown: committed`. **It passed vacuously — the fixture never produced
> a refusal for the log to display, so the assertion was never tested.**
>
> That is worse than a failing test, because it wrote passing evidence. The
> harness assertion must fail when either outcome is absent, per the rework
> document.
>
> **Why this document got it wrong:** it accepted the checkpoint's summary of the
> artifact instead of reading the artifact. The one claim in the repeat that
> could not be true — a log of refusals, from a fixture that had produced none —
> is exactly the one a reader should have checked.
>
> Also corrected: `summary.consoleErrors` is `1`, not 0 — a `405 Method Not
> Allowed`, which is the *expected* result of the write-refusal probe and is
> benign. Describing the run as having "no console failure" was still imprecise;
> the rework document's "no *unexpected* console/network failure" is the right
> wording.
>
> Section 1 (register V2-030 and V2-031, preserving the true chronology) and
> section 3 (V2-032 blocks completion) stand unchanged, and the audit reached the
> same conclusion on both. The authoritative instruction is now
> `rework/GSP-CRV2-08_CHECKPOINT_2_REWORK.md`, not this file.

**Issued 2026-08-31 by the product owner.** Supersedes the two "outstanding"
items in `GSP-CRV2-08_RULINGS.md`. One of those two was wrong; see the
correction below before acting on anything here.

## 1. V2-030 and V2-031 — register them now, do not rewrite history

Both are absent from `V2_FINDINGS_REGISTER.md` and exist only in the `45eb83c`
commit message. Add both **before the completion report**.

The standing rule is that findings are logged before they are repaired, and here
implementation preceded canonical registration. **That is a process violation and
it is documented as one — it is not repaired by reverting or repeating the
work.** The repairs are sound and the evidence is real; what is missing is the
record.

Each entry states:

- that the finding was discovered during the walkthrough;
- **that implementation mistakenly preceded canonical registration** — recorded
  plainly, not smoothed over;
- the original reproduction, as it failed, before the repair;
- severity;
- repair revision `45eb83c`;
- the focused tests;
- the repeat evidence.

Mark each **closed only after those facts are recorded.** A closure entry that
omits the process violation is the same defect a second time.

## 2. Dispute 5 — already repeated. Do not rerun it.

`GSP-CRV2-08_RULINGS.md` asked for a repeat of dispute 5. **That instruction was
issued in error and is withdrawn.** It was written against
`crv2-06-adversarial-balance` at `45eb83c`, which did not yet contain the
builder's step 5 — that work had been committed to a different branch, so the
repeat was invisible to the reader, not absent from the handoff.

The repeat exists and stands: `repeat_failed_paths.js` drives the real browser
path, and `repeat-after-repair.json` records the repaired run at `ebf40fc` —
Operator Log tab present, operator rows rendered, required fields returned,
committed and refused outcomes both shown, writes refused with 405, summary
**7/7** with no console failure and no relevant network failure.

**No further browser run is required for dispute 5.** What is required is
reconciliation of the document that still describes it as open.

### Update `DISPUTE_PATH_INVENTORY.md`

`:58` still reads "suspected gap A — dispute 5 has no operator-facing path."
Replace that with:

- **"finding confirmed and closed as V2-030"** — not "suspected", and not
  silently deleted;
- the supported path named: the **Operator Log** tab and
  `GET /api/games/{id}/instructor/operator-events/`;
- links to the original failing walkthrough, the focused tests, and
  `repeat-after-repair.json`;
- **the historical explanation preserved**: the Django admin was considered and
  rejected as a supported operator path, because it requires a separate staff
  identity that competition instructors do not have. A future reader asking why
  a whole endpoint was built for one dispute needs that reasoning intact. Do not
  edit it out now that it reads as settled.

This is inventory reconciliation and registration only. No fixture rebuild, no
walkthrough repeat, no replay of the five disputes that passed.

## 3. What still blocks completion

**V2-032 has no disposition.** `GSP-CRV2-08_AUDIT_CHECKPOINT_2.md` reports it as
a disclosure finding wider than this handoff's remit, with the scan at
`evidence/post-close-disputes/instructor-ownership-scan.json`, and asks for a
scope ruling. Steps 1–5 are done and all six disputes are settled; the data
dictionary and evidence archive remain. **CRV2-08 cannot complete until V2-032
is dispositioned**, and that ruling has not yet been given.

## Note on branch state

Steps 5 and the second checkpoint (`ebf40fc`, `8644ad4`) were committed onto
`crv2-10-13-rules-and-calibration-specs` rather than
`crv2-06-adversarial-balance`, because a spec branch was created in this shared
checkout and left as `HEAD`. `GSP-CRV2-08_RULINGS.md` went to the other branch
for the same reason. **Nothing is lost — every commit is reachable** — and the
decision is to leave the refs alone until CRV2-08 lands rather than move them
under a live builder. Reconciled afterwards.

The practical consequence for this handoff's completion report: state the
revisions by hash (`8554db3`, `45eb83c`, `ebf40fc`, `8644ad4`), not by branch
name, since the branch name does not presently describe what it holds.


---

# Addendum 2026-08-31 — one fact for the V2-032 register entry

Verified against `backend/core/services/read_inventory.json` (32 routes) at the
audited revision. It bears on how V2-032 is written up, not on the repair the
rework document specifies, which stands as written.

**Only four of the ten leaking routes are logged as sensitive reads.**

| Leaking route | In the sensitive-read inventory? |
|---|---|
| `instructor/teams/{id}/decisions/` | **yes** — category `audit` |
| `instructor/dashboard/` | **yes** — category `audit` |
| `instructor/team-config/` | **yes** — category `decisions` |
| `instructor/sc-panel/` | **yes** — category `decisions` |
| `instructor/briefings/` | **no** |
| `instructor/alerts/` and `/summary/` | **no** |
| `instructor/research-queries/` | **no** |
| `instructor/event-templates/` | **no** |
| `instructor/sc-event-catalog/` | **no** |

Two consequences, and they point in opposite directions:

1. **Mitigating, for the worst route.** The endpoint carrying raw decision
   payloads, hashes, actors and request ids *is* logged. A cross-cohort read of
   it is attributable through `who_accessed` — so the historical question "did
   anyone actually read our decisions before this was fixed?" is answerable from
   stored data. Worth stating in the register entry: the exposure was open, but
   it was not silent.

2. **Aggravating, and it outlives the repair.** Six routes are neither
   ownership-checked nor logged. `briefings` returns per-team executive
   summaries and `alerts` returns per-team coaching alerts by name — competitive
   analysis, not reference data. Once the ownership boundary closes, cross-cohort
   reads stop; but **within** a cohort those reads remain unattributable, so
   "who accessed our briefings?" has no answer. That is a CRV2-04 gap sitting
   next to V2-032, not part of it.

**Suggested, not required:** when the route inventory the rework mandates is
built, give it a second column — *ownership-enforced* and *read-logged* — since
it is the same enumeration of the same routes, and building it once is cheaper
than discovering the second gap later. Whether the six unlogged routes are
worth logging is a separate disposition.

## Two notes for the programme, not for this handoff

- **V2-026 did not cover this and should not be read as covering it.** It closed
  progressive disclosure over *fields* — read serializers that consulted nothing.
  V2-032 is *game ownership*. They are complementary, and a reader who assumes
  the first covered the second will conclude this class is closed when it is not.
  V2-032 is the third instance of `IsInstructor` without ownership, after
  V2-007's rework and CRV2-07's authorization FAIL.
- **A shared permission boundary is a CRV2-09 Phase 1 item.** It changes an
  interface every certified handoff's evidence sits on. Under 09's own rule that
  is "the boundary changed", so it requires a focused regression rather than
  accepting the prior evidence intact. Name it in the resubmission so 09 does not
  have to rediscover it.
- **GSP-CRV2-13 should cite this rather than repeat it.** Its bug-sweep spec
  carries a line to "confirm the CRV2-04 scope guard covers the surfaces added
  since it was certified." V2-032 is that check, run early and failed. The
  route-coverage contract the rework mandates also does part of CRV2-13's Stage-1
  reachability inventory; reuse it, do not rebuild it.
