# V2-048 — history rewrite record

Performed 2026-09-04, after rotation was completed and independently verified.

**The value is never reproduced in this document, in the rewritten history, or
in any commit message.** Digest prefixes are used where two values must be
compared.

---

## 1. Precondition: the credential was already dead

Rotation completed at `20260904T013615Z`; old digest `ce87835d94b0`, new digest
`0f61ba06ef43`. Before touching history I re-confirmed independently, by
attempting to authenticate with the old value: **refused**.

This ordering matters. Rewriting history while the credential is live removes
the evidence and leaves the exposure. Rotation is what makes the history
harmless; the rewrite is hygiene performed afterwards.

## 2. What was preserved first

`git bundle create --all` — a complete-history bundle covering **all 68 refs**,
including remote-tracking refs, plus `refs-before.txt` and
`for-each-ref-before.txt`. Verified with `git bundle verify`: *"The bundle
records a complete history."* Stored mode `600` in a mode `700` directory.

One leftover agent worktree (`worktree-agent-aa23a70e43fabef2c`, clean, a
superseded Stage 1 commit) was removed so the rewrite could run. It is in the
bundle.

## 3. The rewrite

`git filter-repo --replace-text`, replacing the literal with
`***REMOVED-CREDENTIAL-V2-048***`. 435 commits parsed; 15 commits carried the
value.

**Verification, all independent of the tool's own reporting:**

| Check | Result |
|---|---|
| Commits containing the credential (was 15) | **0** |
| Blobs containing it, scanning **all 5,256 objects** — not just branch tips | **0** |
| Commits carrying the replacement marker | 15 |
| Refs before / after | 40 / 40 |
| Files changed by the rewrite, union across every branch | **12** — exactly the V2-048 inventory |

No unrelated file changed on any branch. The current working branch was
tree-identical before and after, because the credential had already been
removed from `HEAD` in the earlier repair.

## 4. The push, and the thing that nearly went wrong

**`main` had diverged before any of this.** Local `main` sat at `142795c` — an
old line equal to `crv2-05-frontend-toolchain` — while `origin/main` was at
`30cc26e`. Force-pushing the rewritten *local* `main` would have destroyed
every commit on `origin/main` that the local branch lacked.

So the push was built from the **rewritten equivalent of each remote branch's
own tip**, resolved through filter-repo's `commit-map`, rather than from local
branch positions. All 25 origin tips resolved; none was missing from the map.
`main` therefore went to `9f2893a` — the rewrite of `30cc26e` — preserving
origin's content, with 171 commits before and after and only the two
credential-bearing files differing.

Pushed with `--force-with-lease` per branch, pinned to the exact SHA fetched
moments earlier, so a concurrent change on the remote would abort the push
rather than be overwritten.

**Post-push verification, against a fresh fetch:** all **25** origin tips match
their intended rewritten commits, 0 mismatches; **0** commits containing the
credential are reachable from any origin ref.

## 5. Local cleanup

The verification step fetched the pre-rewrite refs back into the local repo,
which reintroduced the old objects locally. Those refs were deleted, along with
`refs/replace/*`, followed by `reflog expire --expire=now --all` and
`gc --prune=now --aggressive`.

Re-scanned afterwards: **0 blobs of 2,446, 0 commits.**

Recorded because it is the step most easily skipped: a repository can be clean
on the remote and still hold the secret locally in a verification ref, a reflog
entry, or an unreachable object.

## 6. Not done

- **Access-log review and role-privilege reduction** (V2-048 repair step 4)
  still require the database host. The role is not a superuser but holds
  `CREATEROLE` and `CREATEDB`; `CREATEROLE` is a privilege-escalation path.
- **Every existing clone of this repository is now divergent.** Anyone holding
  one must re-clone or hard-reset; a `git pull` will produce a merge that
  reintroduces the old objects into their local store. This is the
  collaboration cost the repair order flagged, and it is now incurred.
- The working branch `crv2-10-13-rules-and-calibration-specs` carries the CRV2
  work and **is not on origin**. It was not pushed here — that is a separate
  decision, not part of this remediation.
