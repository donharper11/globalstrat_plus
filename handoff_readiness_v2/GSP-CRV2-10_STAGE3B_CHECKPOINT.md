# GSP-CRV2-10 Stage 3B checkpoint — the upgrade path is retired

Runtime revision: `dc60131` (frozen before evidence)
Evidence: `handoff_readiness_v2/evidence/decision-rules/stage3b/`

**Status: implemented, pending integrated Stage 3/4 closure.**

Ruling 1: a ready platform is frozen. Building a new platform, and re-basing a
product onto it, is the only route to a better product.

---

## 1. Removed, not gated

`_process_feature_investments` is deleted, along with its now-dead imports. A
test asserts the function no longer exists, because a gated-but-present
implementation is the thing that comes back — a later change flips the gate and
the mechanic returns without a decision.

Retired with it: per-generation ceilings as a live upgrade path, licensing as a
mid-life mechanic, feature time lags, and the creation of `PendingFeatureGain`
rows. **The model and its manifest section remain**, so the competitive
envelope does not move and no schema version bump is needed; nothing creates
new rows.

## 2. Refused on all three surfaces, never ignored

Both write surfaces refuse with a message naming what to do instead, and a
Phase-1 precondition refuses a stored row before competitive mutation. An
ignored row would be a team's decision silently not happening while they are
charged for the rest of the same submission — the shape V2-047 was raised for.

**Precondition order: ownership → frozen → cost.** Both orderings were wrong
before being fixed, and each produced a misleading refusal:

- with *frozen* before *ownership*, a row naming another team's platform was
  refused as "frozen" rather than as foreign — losing the security-relevant
  answer;
- with *cost* before *frozen*, a row for a mechanic that no longer exists was
  refused for its price, telling the operator to author missing
  `FeatureLevelCost` rows for an upgrade that can never happen.

## 3. No gap between the two routes

The handoff required that the product never be in a state where neither route
to a better product exists. Checked across every commit in the window rather
than asserted:

```
COMMIT      UPGRADE PATH   RE-BASE ROUTE   VERDICT
eae18e5 ... 088ce08   present        present         ok      (12 commits)
WORKTREE             retired        present         ok — re-base is the route
```

The upgrade path was present at every commit until the re-base route existed,
and is retired only now that it does. Full table in
`evidence/.../transition-check.txt`.

## 4. Four existing suites had to move, and why that is not test-fitting

`test_rd_costs`, `test_decision_limits` and `test_platform_lifecycle`'s
ownership suite used a feature upgrade as the **vehicle** for testing something
else — authoritative pricing, duplicate-row limits, platform ownership. Ruling 1
froze the vehicle, not the subject.

Their platforms move from `active` to `in_development`, which is still a legal
target for a stored R&D row. Each test then exercises its own subject again
rather than the freeze. Nothing was deleted and no assertion was weakened.

The `test_manifest_determinism` integration fixture seeded R&D rows against
active base platforms with the comment "binds the feature-level and pending-gain
mutation loops" — loops that no longer exist. It now seeds against a drafting
platform on its own generation, so those rows still populate their manifest
section for envelope coverage.

## 5. What I found and did not decide — V2-053

`_process_feature_investments` was the only consumer of `DecisionRDInvestment`
that changed anything about a product. The rows are still charged and still
**scored**: `performance.py` sums them into `rd_spend` against the scenario
target, and `coherence.py` scores feature/segment alignment from them.

After Ruling 1, a team can spend on R&D, be charged, score for it, and receive
no capability.

Freezing *every* platform rather than only ready ones would close that. It
would also take `rd_spend` and the R&D coherence term to **zero for every team
in every round, permanently**. That is a balance rewrite, so it was not done:
the freeze is implemented exactly as ruled, and the decision is registered as
**V2-053** for the rules owner / GSP-CRV2-11 with two costed options.

Also measured: rows targeting a not-yet-ready platform were **already** inert
before Ruling 1 — the retired processor opened with `if tp.status != 'active':
continue`. The silent-ignore predates this handoff; Ruling 1 widens it.

## 6. Consequence for GSP-CRV2-06

Ruling 1 **invalidates the strategy space GSP-CRV2-06's tournament searched**.
That tournament's strongest-strategy result is evidence for the game as it was,
when buying up the feature curve on a held platform was available. CRV2-09 must
not accept it as current. Recorded in `GSP-CRV2-10_RULE_DECISIONS.md`.

## 7. Verification

Affected focused set, run once from clean revision `dc60131`:
**298 distinct, 298 executed, `OK`**, whole tree clean at both ends, same
revision at both ends.

- `makemigrations --check --dry-run` → `No changes detected`
- `dump_manifest_schema --check` → `Manifest schema inventory is current.`
- `dump_read_inventory --check` → `Read inventory is current.`

New: `test_platform_freeze` (11) — both write surfaces, the engine boundary
with a smuggled row, no competitive write on refusal, the stored level
unchanged, a healthy round still resolving, the processor's absence, and no new
`PendingFeatureGain`.

## 8. What this checkpoint does not claim

- Stage 3 and Stage 4 findings remain *implemented, pending integrated
  closure*. V2-053 is **open** and is not mine to close.
- No full suite, browser, concurrency, load or tournament run.
- **V2-048 remains an open P0.** The credential is prepared for rotation and
  drill-validated but **not rotated**; release stays NO-GO.
