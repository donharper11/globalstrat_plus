# GSP-CRV2-10 Stage 4 rework checkpoint — V2-049, V2-050, V2-051

Runtime revision: `b9e1282` (frozen before evidence)
Audited revision that failed: `8a46599` / checkpoint `762d70d`
Evidence: `handoff_readiness_v2/evidence/decision-rules/stage4-rework/`

**Status: implemented, pending integrated Stage 3/4 closure. Stage 3 is not
closed and Stage 3B has not started.**

All three registered defects are repaired, each with a reason control showing
the new test fails for the intended cause. The audit's own reproductions are
reproduced here — an instructor's HTTP 200 cross-game write, a past round's
awareness collapsing to zero, and operating income stuck at `-500,000.00`.

---

## 1. V2-051 — the route did not bind the team to the game

**Root cause was one shared helper, not one route.** `_get_team(team_id)`
resolved by global primary key, and **nine** call sites used it; only one view
in the module bound the team to the URL game itself. Fixing the re-base route
alone would have left eight.

`_get_team(game_id, team_id)` now resolves through the game. The product and
the target platform resolve through that team, so no object is fetched by a
primary key the caller supplied without a parent to check it against.

**Why neither guard caught it**, stated because it explains why this needed a
lookup rather than a permission: the student guard proves membership in the URL
*team* but not that the team is in the URL *game*; the instructor guard proves
ownership of the URL *game*, and `IsTeamMember` exempts instructors. Each guard
is correct about the half it sees, and the relationship between the halves was
nobody's.

**A cross-cohort attempt now leaves a record.** The middleware refusal never
fired here — the instructor genuinely owns the URL game — so a deliberate
attempt was invisible. `_record_cross_game_refusal` writes one
`AuthorizationRefusalEvent`, outside the request transaction for the reason the
middleware gives. The response stays a uniform 404 whether or not the team
exists elsewhere, so the record costs the caller no information about what
exists.

Tests: `RebaseGameBindingTests` (6) — student direction, instructor direction,
no successful audit row for a refused call, the refusal record, an unknown team
recording nothing, and a positive control asserting one coherent
game → team → product → platform hierarchy on a successful event.

## 2. V2-050 — a later switch rewrote past brand awareness

The historical marketing query filtered on `team_product__team_platform`, a
live foreign key, and compared it against a round-resolved platform. After a
re-base those two can never agree, so every qualifying row dropped out of the
cumulative sum. Nothing raised, because an emptied sum is still a number — the
same reason BECSR's defect B measured zero rather than failing.

Each row is now attributed to the platform its product used **in that row's own
round**, resolved once per distinct round rather than once per row.

**The Stage 4 inventory could not have found this.** It looked for direct
attribute reads and calls to `resolved_platform`; this was neither. A static
guard, `PlatformConsumerGuardTests`, now covers relationship traversals as
well, and on its first run it found **a second latent copy of the same shape**
in `_team_has_generation` — uncalled, so not a live defect, but corrected
rather than left as the seed of a repeat.

Tests: `BrandAwarenessReplayTests` (3), `PlatformConsumerGuardTests` (2).

## 3. V2-049 — the write-off was recorded but neither charged nor shown

It reached `context.opex` and stopped: the statement assembly enumerated six
other opex keys by name. The team was charged nothing, shown nothing, and taxed
as though the switch had not happened.

- `platform_switch_write_off` joins `total_opex`, so it reaches operating
  income, net income and — through net income — operating cash flow. Treated as
  cash-effective, consistent with `retirement_expense`, its closest sibling.
- Added to the tax deduction enumeration.
- A distinct `RoundResultFinancials.platform_switch_write_off` field, exposed
  on the team's own results. **Deliberately not on the competitor block**: when
  a rival re-based, and what it cost them, is not public information.
- Decimal units end to end. `int(units)` was discarding part of a real balance —
  100.50 units wrote off $750.00 instead of $753.75 — and the history field is
  now decimal to match.

**Every previous write-off test was true while the charge was invisible**,
because they read the history row or `context.opex`. The new ones assert from
`RoundResultFinancials` — what the results API and UI actually read — and
resolve a whole independent game per case, because a resolved round is
immutable and cannot be re-run to produce a comparison.

Tests: `WriteOffAccountingTests` (8) — own line, no-switch control, the exact
operating-income delta, net income and cash, tax, a later round not charged
again, reprocessing refused with the stored amount unchanged, and the
fractional balance.

---

## 4. The manifest schema version had to move

Adding a competitive field changes what a round hashes to. So does Stage 4's
earlier `team_product_platform_history` section, which **should have bumped the
version when it landed and did not** — recording that here rather than leaving
it as an inconsistency for the next reader.

`MANIFEST_SCHEMA_VERSION` is now **3**, with the reviewed inventory written to
`manifest_schema_v3.json`; `manifest_schema_v2.json` is kept as the record of
what version 2 meant, because a version's definition is what makes its stored
hashes interpretable later.

Two envelope definitions sharing one version number is the single thing
`require_schema_version` cannot survive: it would compare a manifest written
under the old definition against a hash computed under the new one, agree the
versions match, and report the difference as a mismatch — reading a definition
change as evidence of tampering. The version and the inventory filename now
both derive from one constant in `manifest_version.py`, so they cannot drift
apart again.

## 5. A stale artifact the affected set could not have caught

The suite warned that `read_inventory.json` was stale: 780 routes recorded,
781 registered. Adding the re-base route at `8a46599` moved the count, and
`dump_read_inventory --check` pins it — a test in `test_audit_integrity`, which
was outside both my affected set and the audit's.

The count is the only change; the route is POST-only and adds no read
disclosure surface. Regenerated at `b9e1282`, and
`SensitiveReadInventoryTests` is now inside the affected set.

The general lesson is recorded because it will recur: adding a route changes
artifacts guarded by tests that no amount of coverage of the route's own
behaviour will run.

---

## 6. Verification

Affected focused set, run once from clean revision `b9e1282`:

| Area | Distinct tests |
|---|---|
| `test_product_rebase` (10 classes) | 51 |
| `test_platform_lifecycle` (10 classes) | 53 |
| `test_manifest_determinism` (6 classes) | 52 |
| `test_rd_costs.AuthoritativePriceTests` | 15 |
| `test_decision_limits` (4 classes) | 17 |
| `test_product_name_uniqueness` | 10 |
| `test_who_attempted.WhoAttemptedTests` | 10 |
| `test_game_scope_boundary.GameScopeBoundaryTests` | 9 |
| `test_audit_integrity.SensitiveReadInventoryTests` | 5 |
| **Total** | **222** |

222 distinct, 222 executed — no test-class inheritance inflation. `OK`, exit 0.

- `makemigrations --check --dry-run` → `No changes detected`
- `dump_read_inventory --check` → `Read inventory is current.`
- Migration `0082_stage4_write_off_accounting` (one added field, one altered)

**Provenance.** The transcript was generated outside the repository and moved
in afterwards. It records the **whole tree** clean at both ends — the
previously-noted `frontend/deploy-frontend.sh` was committed by the operator at
`9ada6e5`, so no outside-scope modification remains to name.

**Reason controls** are in `evidence/.../reason-controls.md`: each repair
reverted in isolation, the new tests failing with the audit's own figures, and
restored to `OK`. One honest divergence is recorded there — the student
cross-game case returned 400 under the revert rather than the 200 the audit
saw, because in this fixture it stopped on an incidental platform mismatch
rather than on any scope check. It was still not refused for the right reason.

---

## 7. What this checkpoint does not claim

- **Stage 3 is not closed and Stage 3B has not started.** The old upgrade path
  remains reachable.
- V2-039, V2-040, V2-044, V2-045, V2-046, V2-047 stay *implemented, pending
  integrated Stage 3/4 closure*. V2-049, V2-050 and V2-051 join them at
  `b9e1282`; none is closed.
- No full suite, browser, concurrency, load or tournament run.
- The write-off's cash treatment follows `retirement_expense` — a stated
  modelling choice, not a derived result. If the intended treatment is non-cash
  (an add-back, with inventory value reduced instead), that is a rule decision
  and would change the cash assertions.
- Unordered iteration remains in `core/services` modules outside the resolution
  set; unchanged from the previous checkpoint and unassessed for non-resolution
  surfaces.
- **V2-048 (P0, committed database credential) is open and unrepaired**, owned
  by security/operations. Integrated release stays NO-GO on it independently of
  Stage 4.
