# GSP-CRV2-10 Stage 4 checkpoint audit — FAIL / REWORK

Audited runtime revision: `8a46599`

Audited checkpoint revision: `762d70d`

## Binary decision

**FAIL / REWORK. Do not begin Stage 3B.**

The submitted evidence is internally sound, but it does not exercise three
Stage 4 boundaries that fail independently: the supported route can write
across games, a later switch changes a past round's brand-awareness input, and
the recorded inventory write-off never reaches the financial statements or a
visible result line.

V2-049, V2-050 and V2-051 are registered open. V2-048 remains the separate
security/operations P0 and is not part of this rework.

## What passed audit

- Both submitted artifact hashes match `CHECKSUMS.json`.
- The transcript contains 179 test IDs, all 179 are unique, and all passed.
- `backend/` at checkpoint `762d70d` matches runtime `8a46599` exactly.
- The one dirty worktree path is the named, outside-scope
  `frontend/deploy-frontend.sh`; it was not touched by this audit.
- An independent run of `core.tests.test_product_rebase` passed 32/32 under
  `/tmp/globalstrat-backend-test.lock` against a separately named database.
- The service-level ownership/readiness refusals, atomic history write, prior
  association seeding, basic as-of-round platform lookup and Phase-1
  missing-resolution call are present.

The verdict is therefore not a provenance or test-count rejection. It is a
coverage rejection: the passing tests stop one layer before the outcomes the
checkpoint claims.

## Blocking defects

### 1. V2-051 (P0): the route does not bind the team to the game

`ProductRebaseView` resolves `game` from `game_id`, then resolves `team` by its
global primary key. It never requires `team.game == game`. The product is
scoped only to that independently resolved team, and the target platform is
looked up globally before the service checks only team ownership.

The shared guards do not supply the missing relationship:

- for a student, `TeamScopeGuardMiddleware` proves membership in the URL team
  but not that the team belongs to the URL game;
- for an instructor, `GameScopeGuardMiddleware` proves ownership of the URL
  game, while `IsTeamMember` deliberately exempts instructors.

Two isolated endpoint probes failed:

1. A student enrolled in team B submitted B's product through unrelated game
   A's URL. The route returned 200 and used A's current round and write gate.
2. An instructor owning game A used A's URL with a team/product belonging to
   game B, whose course is owned by a different instructor. The route returned
   200 and changed game B's product platform (`1 -> 2`).

The successful decision audit row is also attributed to the URL game/round,
not the game that owns the mutated team. This is a cross-cohort competitive
write and a false audit attribution, not only a malformed URL.

### 2. V2-050 (P0): a later switch rewrites past brand awareness

`_derive_brand_awareness()` resolves the right-hand platform as of the scored
round, but filters historical marketing rows through
`team_product__team_platform`, which is the product's **live** foreign key.
After a later re-base the left side sees the new platform while the right side
correctly asks for the old one, so every qualifying historical promotion row
disappears.

The independent probe created $1,000,000 of promotion spend on the old
platform and evaluated round 3 before and after a round-4 switch:

```text
before switch: 0.9516258196404048
after switch:  0
```

The same past round therefore receives a different competitive feature input.
The existing replay test checks platform ID and one platform feature level; it
does not cover the cumulative marketing query. The inventory based on direct
`.team_platform` reads also missed this ORM relationship traversal.

### 3. V2-049 (P1): the write-off is recorded but neither charged nor shown

`calculate_operating_expenses()` puts `platform_switch_write_off` into
`context.opex`. `generate_financial_statements()` then enumerates six other
opex keys and omits it from `total_opex`, operating income, net income and cash
flow. `calculate_tax()` independently omits it from deductions.
`RoundResultFinancials` has no field for it, so neither the result APIs nor the
UI can show the Stage 4 cost as its own line.

The independent real-path probe recorded a $750 write-off (100 units × $50 ×
15%) in history and in `context.opex`; the stored operating income remained
`-$500,000.00` instead of `-$500,750.00`. The passing write-off tests read the
history row back but never run the financial assembly.

The amount also truncates valid stock. `RoundResultProductMarket.units_unsold`
is decimal, while `unsold_on_platform()` returns `int(units)` and the new
history field is integer. A probe with 100.50 units reported 100 units (and
therefore $750 rather than $753.75 at the same cost and percentage).

## Required rework

1. Bind the endpoint hierarchy before the service runs: resolve the team
   through the URL game, and resolve the product and target platform through
   that team. Do not accept a game merely as a source of round number/status.
2. Add negative endpoint tests for both actors:
   - a student who belongs to the URL team but supplies another game ID;
   - an instructor who owns the URL game but supplies a team/product from a
     different instructor-owned game.
   Both must prove no pointer/history/financial mutation and no successful
   decision-audit row. Preserve the CRV2-08 refusal-audit contract where the
   rejection is an authorization refusal.
3. Assert every successful re-base event has one consistent game, team, round,
   product and platform hierarchy.
4. Replace the live relationship filter in brand-awareness history with
   round-versioned association resolution. Each marketing row must be
   attributed to the platform that product used in the row's round, while the
   product being scored resolves in the requested round.
5. Expand the platform-consumer inventory/guard to cover ORM relationship
   traversals, not only direct attribute reads or calls to `resolved_platform`.
   Add an actual fit-score control in which historical promotion is non-zero;
   switch in a later round and prove the earlier score/input is unchanged and
   the switch-round behavior follows the adopted platform rule.
6. Carry the stored write-off through the real accounting pipeline exactly
   once: the stored financial result, operating income, net income, cash flow
   and tax treatment must agree. Add a distinct result field and expose it on
   the supported results surface so “shown as its own line” is true.
7. Preserve decimal units end to end. Do not coerce the decimal
   `units_unsold` balance into an integer history field or calculation.
8. Test the accounting at the actual Phase-1/results boundary: one switch with
   stock, no switch, a later round, and replay/reprocessing. Assert the own
   line, P&L/cash effect and exactly-once behavior from stored results, not only
   `context.opex` or the history-row sum.
9. Correct the Stage 4 checkpoint/current findings status, regenerate only the
   focused evidence from a new frozen runtime, commit, and stop for re-audit.
   Stage 3 and all six implemented-pending-closure findings remain open.

## Verification budget

- `test_product_rebase` plus the directly affected financial/result tests.
- Focused endpoint scope tests and the existing `test_game_scope_boundary`
  contract; no broad authorization sweep.
- The 50-test CRV2-01 determinism boundary named by the handoff, plus the new
  non-zero-promotion switch/replay control.
- `makemigrations --check --dry-run`, inventory/static guards,
  `git diff --check`, clean backend source and evidence checksum verification.
- No full suite, browser run, concurrency matrix, load run, tournament,
  Stage 3B or later-stage work.

## Acceptance for re-audit

Stage 4 passes only when no actor can use one game's URL to mutate another
game's team; every successful route write and audit row has a coherent object
hierarchy; all competitive platform consumers, including relationship-based
historical queries, are round-correct; a later switch cannot change any tested
past-round score input; and the exact decimal write-off appears once as its own
stored/visible line and changes the team's P&L, tax and cash consistently.
