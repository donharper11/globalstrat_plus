# GSP-CRV2-08 — disposition on V2-030 and V2-031

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
