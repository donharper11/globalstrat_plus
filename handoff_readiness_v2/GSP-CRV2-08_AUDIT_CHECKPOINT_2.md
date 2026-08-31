# GSP-CRV2-08 — checkpoint 2, after two reworks

Superseded by the audit rulings it asked for. Kept as the record of what was
asked and what was decided, rewritten so it no longer describes a pre-rework
state or poses questions already answered.

Revisions: fixture and walkthrough `8554db3`; V2-030/V2-031 repair `45eb83c`;
first scan and finding `ebf40fc`; ownership boundary `d39ce04`; refusal
auditing this revision.

## Where CRV2-08 stands

**All six disputes settled.** Five answerable through supported paths; dispute 5
was a finding, repaired and re-proved.

| # | Dispute | Verdict | Supported path |
|---|---|---|---|
| 1 | Submitted before the deadline | answerable | instructor evidence table: saves with server timestamps, actors, request ids against the round deadline |
| 2 | Recorded decision differs | answerable | same response: per-save payload and SHA-256 |
| 3 | Rival saw our decisions | answerable | `who_accessed`: actor, target team, route, outcome, request id — refusals included |
| 4 | Rerun after final | answerable | `replay_round --export-only`: manifest hashes and timestamps |
| 5 | Operator changed something | **V2-030, repaired** | Operator Log tab and `GET /api/games/{id}/instructor/operator-events/` |
| 6 | Prove the calculation | answerable | replay reproduced round 1 exactly, hash `108c4f0a…`, exit 0 |

Dispute 3's "not answerable" wording in the runbook was stale rather than a
product gap, and is corrected there.

## Findings, and how each was decided

| ID | Sev | Disposition |
|---|---|---|
| V2-030 | P1 | Closed at `45eb83c`. Registered after repair, contrary to the standing rule; the register says so plainly. |
| V2-031 | P2 | Closed at `45eb83c`. Same late-registration note. |
| V2-032 | **P0** | Closed at `d39ce04`, accepted in audit. Shared ownership boundary, 94 routes, no exemptions. |
| V2-033 | — | **Withdrawn: not a defect.** An unowned course is a shared pilot cohort by adopted rule. Operationally: a prize cohort that is not meant to be shared must have an instructor owner assigned before launch. |
| V2-034 | P1 | Closed this revision. Refused cross-cohort mutations are recorded again. |
| V2-035 | P1 | Closed at `d39ce04`. Instructor alerts required no role at all; a signed-in student could read them. |

## The two things worth reading

**The boundary, not another view.** V2-032 was the third appearance of one
pattern: `IsInstructor` answers "is this an instructor", never "is this their
game". `GameScopeGuardMiddleware` now refuses by default for every registered
route naming a `game_id`, with the inventory built from URL patterns rather
than a list anyone maintains. Two defects surfaced while building it and are
recorded rather than smoothed over: the first inventory filtered on views that
already declared an instructor permission and so missed `/instructor/alerts/`,
which declares none; and the ownership helper read `request.user.user_id`,
which DRF populates only inside the view, so at the boundary it refused the
rightful owner.

**Refusing earlier made refusals invisible.** V2-034. Moving authorization
ahead of the view was correct and meant a cross-cohort lifecycle attempt
reached no auditing code at all — 37 refused writes with nothing to
investigate, regressing what CRV2-02 established. Refusals are recorded again,
in a narrow append-only model that claims only what happened: not an operator
action that never occurred, not a read.

## Evidence

- `evidence/post-close-disputes/dispute-answers.json` — the six disputes
- `evidence/post-close-disputes/browser-walkthrough.json` — both roles, real Chromium
- `evidence/post-close-disputes/repeat-after-repair.json` — dispute 5 with a genuine refusal rendered beside a committed action
- `evidence/post-close-disputes/instructor-ownership-scan.json` — the ten original disclosures
- `evidence/post-close-disputes/ownership-scan-after-repair.json` — 65 reads, 37 writes, 0 disclosing, 0 unrefused, 0 mutations, 37 of 37 refusals recorded

## Not run, deliberately

The fixture was not rebuilt. The six-dispute walkthrough, dispute 5, the
language repeat, the full suites, and the load, determinism, concurrency,
provider and failure drills were all left alone, as each rework instructed.

Step 6 — the data dictionary and the concise archive — remains stopped pending
this checkpoint.
