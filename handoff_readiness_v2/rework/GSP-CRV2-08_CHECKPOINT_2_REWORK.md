# GSP-CRV2-08 checkpoint 2 — REWORK

## Decision

**FAIL / REWORK**

Revision audited: `8644ad4`

CRV2-08 must stop before step 6. The completed-game fixture and the five previously passing dispute paths remain reusable; do not rebuild or replay them.

## Ruling 1 — V2-030 and V2-031 registration

Neither finding is present in `V2_FINDINGS_REGISTER.md`. Register both now and preserve the true chronology:

- discovered during the CRV2-08 walkthrough;
- repaired before canonical registration, contrary to the standing rule;
- original failing evidence, repair revision `45eb83c`, focused verification and repeat evidence named;
- final closed disposition stated.

Do not imply that registration preceded implementation.

Update `DISPUTE_PATH_INVENTORY.md` so dispute 5 is no longer a suspected gap. It must name V2-030, the Operator Log UI, the ownership-scoped endpoint, focused tests and repeat artifact. Preserve Django admin as the rejected alternative.

## Blocking evidence defect — dispute 5 repeat does not prove refusals

`repeat-after-repair.json` says “committed and refused actions are both visible,” but:

- `operatorLog.outcomes` contains only `committed`;
- `operatorApi.rejectedCount` is `0`; and
- the JavaScript marks the step passed merely when `committed` is present.

This is a false-positive assertion. Seed or produce one genuine refused operator action through the supported endpoint, then repeat only dispute 5. Require all of:

- at least one committed and one rejected/refused event returned by the API;
- both outcomes visibly rendered in the Operator Log;
- the rejected filter returns at least one row;
- actor, timestamp, action, outcome, round, reason, before/after or conflict, and request ID are visible for the relevant rows;
- POST to the audit reader remains 405;
- no unexpected console/network failure.

Fix the harness assertion so absence of either outcome fails and writes no passing evidence.

V2-031’s persisted-language repeat need not run again.

## Ruling 2 — V2-032 scope and severity

Register V2-032 as **P0** before repair. An unrelated instructor can read another cohort’s raw submitted decisions, hashes, actors and request IDs. That is a launch-blocking competitive-confidentiality failure.

Do not repair only the decisions endpoint and defer the neighbouring routes. This is the third failure of the same authorization pattern; another per-view partial repair would leave an unknown boundary.

### Required boundary

1. Build an authoritative inventory from registered URL patterns for every game-scoped instructor read and mutation route, including alternate/legacy paths. Do not inventory only views already using an ownership helper.
2. Make game ownership default-deny at a shared permission/middleware boundary. Continue using the established `instructor_can_access_game` semantics, including its explicitly supported unowned-pilot behavior; do not invent a second ownership rule.
3. Any exemption must be explicit, justified and contract-tested. A route keyed by `game_id` is not exempt merely because some returned catalogue rows are shared reference data.
4. Cover all ten demonstrated GET disclosures and all registered game-scoped instructor mutation routes. Do not limit the repair to routes named in the current probe.
5. Keep role authentication and game ownership conceptually distinct: `IsInstructor` alone is not authorization.

### Mutation probe ruling

Yes: exercise the write endpoints as an unrelated instructor against a disposable clone. This is authorized within CRV2-08’s isolated fixture scope. Snapshot the expected state, issue each route’s real HTTP method with the smallest syntactically valid payload, and require 403 before mutation. Verify round/game/team state and operator audit counts remain unchanged by each refused request.

Avoid testing mutations against the completed evidence game if a route requires changing it; use a disposable clone/checkpoint dedicated to the authorization scan.

### Focused acceptance

- unrelated instructor: every inventoried protected GET/write route returns 403 and discloses no protected body;
- owning instructor: representative read and lifecycle write controls reach their normal non-authorization outcome;
- ownership of one game grants no access to another;
- student remains refused;
- unowned-pilot behavior is pinned once according to the existing helper;
- a route-coverage contract fails when a new game-scoped instructor route lacks the shared ownership boundary or an explicit exemption;
- the ten original leaking GETs all change from 200 to 403;
- every exercised write leaves the disposable clone unchanged.

After repair, repeat the ownership scan once across the complete authoritative inventory. Do not repeat the general browser walkthrough.

## Verification budget

Run only:

- focused ownership-boundary and route-inventory tests;
- directly affected instructor endpoint contract tests;
- the one dispute-5 browser repeat with a real refusal;
- one complete post-repair ownership scan against the disposable fixture;
- static inventory checks, `git diff --check`, clean-tree and checksum verification.

Do **not** rebuild the completed game; repeat disputes 1–4 or 6; rerun language persistence; run the full backend/frontend suites; or run load, replay matrices, concurrency matrices, provider drills or failure walkthroughs.

## Resubmission

Return the freeze revision, V2-030/V2-031/V2-032 register entries and dispositions, route counts including exemptions, focused test counts, dispute-5 repeat result, post-repair read/write ownership scan, evidence checksums and clean-tree status. Only after this checkpoint passes should step 6 produce the final data dictionary and concise archive.
