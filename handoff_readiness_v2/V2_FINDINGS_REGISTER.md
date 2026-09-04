# GlobalStrat+ competition readiness v2 — findings register

Prepared 2026-08-28 against `competition-rc-2026.08.27.3` / `7452ee7`.
Findings were recorded before repair. P0 blocks; P1 degrades; P2 cosmetic.

| ID | Area | Sev | Description | Reproduction / evidence | Initial status |
|---|---|---:|---|---|---|
| V2-001 | Determinism boundary | P0 | `output_sha256` covered only financials, performance-index rows, and leaderboard rows. It omitted coherence, product/market outcomes, adoption, resilience, share price history, and mutable `Team` state carried into the next round. | Compare original `complete_manifest()` at `7452ee7` with `_run_phase_1()`. | **Closed** — see closure entry below |
| V2-002 | Reconstruction / disputes | P1 | The input manifest stores decision-event IDs and payload hashes, but not the decision payload, scenario parameters, market state, starting team state, or engine configuration. The backup can reconstruct these, but the manifest alone cannot prove the calculation or explain an input. | Inspect `prepare_manifest()`: its fields are game/round IDs, six audit metadata fields, active team IDs, and scenario ID. | **Closed** — see closure entry below |
| V2-003 | Dispute tooling | P1 | Instructor decision drill-down showed the stored snapshot and lock actor/time, but not each accepted save's actor, server timestamp, request ID, endpoint, payload, and hash. | V2 API/UI now exposes ordered audit evidence in the historical decisions modal. | Repaired |
| V2-004 | Concurrent operator actions | P0 | Reopen, deadline change, and advance did not share the row-lock transaction used by close/process. Tracing the routes found the problem was wider: several endpoints read the round's status outside any lock and met the conflict inside the engine, where it surfaced as a 500 or a second resolution. | Compare the pre-repair `RoundProcessView` (unlocked status read, blanket `except Exception` → 500) and `InstructorExtendDeadlineView` (no lock, no transaction, silently reopened a closed round). | **Closed** — see closure entry below |
| V2-005 | Failure visibility | P1 | A Phase-1 exception rolled back `PROCESSING`; `_mark_failed()` then required the rolled-back value, leaving no FAILED indicator. | Injected disk-full exception now leaves `Round.processing_status=FAILED`; focused and full suites pass. | Repaired |
| V2-006 | Backend restart / narrative | P1 | Phase 2 runs only in a daemon thread. A worker restart can silently abandon it; no durable queued job or startup retry exists, and an abrupt process death cannot populate `narrative_error`. Numeric results remain valid, but operator visibility/recovery is incomplete. | Process a round, terminate the worker after Phase 2 dispatch and before completion, restart, then inspect `narrative_generated`, `narrative_error`, and logs. | **Closed** — see closure entry below |
| V2-007 | Audit integrity | P1 | Audit models reject a second `.save()`, but queryset `.update()`/`.delete()` and direct SQL can alter them. The database does not enforce append-only history, so stored data alone cannot prove absence of operator/database tampering. | In an isolated database, call `DecisionAuditEvent.objects.filter(pk=...).update(action='tampered')`; it bypasses model `save()`. | **Closed** in GSP-CRV2-04 — see closure entry below |
| V2-008 | Dry-run failure path | P2 | The `process_round(dry_run=True)` exception handler referenced undefined `sid`, masking the original failure. | Removed invalid rollback; outer atomic block owns rollback. | Repaired |
| V2-009 | Frontend verification environment | P1 | Lockfile selects `react-router-dom` 7.1.1 (Node >=20), but the VM runs Node 18.20.8. Production build completes, while Jest cannot resolve the router and one suite cannot start. | `npm install` reports EBADENGINE; `CI=true npm test -- --watchAll=false` has 1 pass / 1 load failure. | **Closed** in GSP-CRV2-05 — see closure entry below. The stated cause was wrong; the repair is described there. |

## V2-030 through V2-035 — raised by GSP-CRV2-08

**Chronology, stated plainly.** V2-030 and V2-031 were found during the CRV2-08
browser walkthrough and **repaired before they were registered here**, contrary
to the standing rule that a finding is recorded before repair. The audit of
checkpoint 2 caught the omission. Registration did not precede implementation
and this entry does not imply it did. V2-032 onwards were registered before
repair, as the rule requires.

## V2-048 — a live database credential is committed to Git (P0) — REMEDIATED at `192b6e1`; one review item open

**Owner: security and operations.** Not a GSP-CRV2-10 finding and not to be
folded into any stage of it. Stage 4 development may continue; this finding
blocks integrated release approval.

**A credential committed to a repository must be treated as compromised.** The
value is not reproduced here, in the inventory below, or in any commit message.

### What is exposed

The password for the PostgreSQL role `donwh` on the competition database host
appears in **14 occurrences across 12 tracked files**. It is the **active**
credential: confirmed by authenticating with it, not by comparing strings.

The role is not a superuser, but it holds **CREATEROLE and CREATEDB**. CREATEROLE
is the significant one: it is a privilege-escalation path, not merely read and
write on existing data. **87 non-template databases** are reachable with it,
including the live competition database.

`listen_addresses` is `*`, so the host accepts connections on every interface —
the credential is not protected by the database being unreachable.

The repository has a GitHub remote (`donharper11/globalstrat_plus`), so exposure
is not limited to this machine. The value appears in **14 commits across
history**, the earliest being the baseline snapshot the repository was seeded
from, so removing it from `HEAD` alone does not remove it from the repository.

### Sanitized inventory (path:line, value never printed)

```text
backend/globalstrat/settings.py:133                              <- runtime default
handoff_readiness_v2/audit_integrity_evidence.py:31
handoff_readiness_v2/audit_truncate_rework_evidence.py:36
handoff_readiness_v2/evidence/adversarial-balance/harness/inventory_run.py:31
handoff_readiness_v2/evidence/decision-rules/harness/stage1_probes.py:87
handoff_readiness_v2/evidence/load-failure/harness/driver.py:212
handoff_readiness_v2/evidence/load-failure/harness/driver.py:247
handoff_readiness_v2/evidence/load-failure/harness/driver.py:273
handoff_readiness_v2/evidence/load-failure/harness/failure_walkthrough_body.py:321
handoff_readiness_v2/evidence/load-failure/harness/failure_walkthrough_run.py:58
handoff_readiness_v2/evidence/load-failure/harness/stack.py:103
handoff_readiness_v2/evidence/post-close-disputes/harness/ownership_scan.py:125
handoff_readiness_v2/evidence/post-close-disputes/harness/start_stack.py:29
rework/REWORK_SPEC_2026-07-13.md:156
```

The runtime default at `settings.py:133` is the origin; every harness copy took
it from there, several of them written by me across CRV2-04, CRV2-07, CRV2-08
and CRV2-10. Copying an existing default is how a single exposure became
fourteen.

### How it surfaced

Found by inspecting tracked files during CRV2-10 Stage 4, after the
`no-committed-secrets` pre-commit output drew attention to committed-secret
hygiene in this repository.

**The check did not report this credential, and does not report it now.** Its
four findings are two throwaway `DJANGO_SECRET_KEY` values used only by a
disposable evidence stack, and two hardcoded JWTs in `rework/browser_pass.js`.
`backend/globalstrat/settings.py:133` — the origin of all fourteen occurrences
— is not among them. The pattern that hides it is an environment lookup with a
literal fallback: `os.environ.get('DB_PASSWORD', '<literal>')` reads as
configuration, not as an assigned secret.

So the check currently has a **100% miss rate on the one credential that
matters and a 50% false-positive rate on what it does report**, while running
report-only. That combination is why its output went unread, and it means
"restore the scanner to high-signal enforcement" is a detection-coverage
requirement, not only an exception-scoping one.

The two JWTs are noted for the same owner's assessment — whether they are
live-signed session tokens or artifacts of a disposable stack was not
determined here, because probing stopped once the credential was confirmed
compromised.

### Repair complete at `192b6e1` — one review item remains

**The credential is rotated, revoked and verified refused. The history is
rewritten and the cleaned branches are pushed.** The exposure is closed.

| Step | State |
|---|---|
| 1. Rotate or revoke | **Done** 2026-09-04. Old digest `ce87835d94b0` independently confirmed refused; new `0f61ba06ef43`. All three consumers updated and restarted; the v1 deadline cron verified authenticating. |
| 2. Move to deployment secret configuration | **Done.** No fallback in any environment; `_required_db_password()` refuses to boot without it. |
| 3. Remove tracked defaults and copies | **Done.** All 14 occurrences across 12 files. |
| 4. Assess access logs and role privileges | **OPEN.** Needs the database host. The role is not a superuser but holds `CREATEROLE` (a privilege-escalation path) and `CREATEDB`. |
| 5. History rewrite | **Done.** 15 commits rewritten, 0 of 5,256 objects retain the value, 25 origin branches force-pushed with lease protection and re-verified from a fresh fetch. See `V2-048_HISTORY_REWRITE_RECORD.md`. |
| 6. Restore the scanner to high-signal enforcement | **Done.** Blocking, four findings dispositioned with pinned reasons, plus repo-owned AST detection for the env-lookup-with-literal-fallback shape gitleaks misses. |
| 7. Disposition the two JWTs | **Done.** Decoded; expired April 2026. |

**Consequence, incurred deliberately:** every existing clone is now divergent
and must be re-cloned or hard-reset. A `git pull` would merge the old objects
back into a local store.

**Historical record of the original exposure**, kept because the finding's
severity rested on it: the value was live, held `CREATEROLE`/`CREATEDB`, reached
87 databases, sat behind a GitHub remote on a host with `listen_addresses = *`,
and was shared by three applications across two repositories.

| Step | State |
|---|---|
| 1. Rotate or revoke | **NOT DONE — blocking.** Requires database administrator action on a live host holding 87 databases, including a competition database. Not taken unilaterally. |
| 2. Move to deployment secret configuration | **Partly.** `DB_PASSWORD` is now read from the environment with no fallback; wiring it into the systemd `EnvironmentFile` is the operator's step. |
| 3. Remove tracked defaults and harness copies | **Done.** All 14 occurrences across 12 files. `_required_db_password()` raises `ImproperlyConfigured` rather than defaulting, in every environment. |
| 4. Assess access logs and role privileges | **NOT DONE.** Needs the database host. Recorded privileges stand: not superuser, but CREATEROLE and CREATEDB. |
| 5. Decide on history rewriting | **NOT DONE — a decision, not a task.** 14 commits, earliest the baseline snapshot, GitHub remote. |
| 6. Restore the scanner to high-signal enforcement | **Done, in two halves.** The operator promoted `no-committed-secrets` to blocking and dispositioned its four findings with narrow, reasoned, fingerprint-pinned exceptions (`a4479cb`). Detection coverage was added separately — see below. |
| 7. Disposition the two JWTs | **Done.** Decoded by the operator: instructor and student walkthrough tokens, `exp` April 2026, expired five months. |

**Detection coverage.** The scanner is now blocking *and green*, which is a
stronger claim than the report-only version made on the same detection — and it
still does not see this credential's shape. `os.environ.get('DB_PASSWORD',
'<literal>')` reads as configuration rather than as an assigned secret, so
gitleaks' default ruleset passes over it. Upstream `aide-checks` builds its
config with `useDefault = true` and no rule extension point, so rather than
fork a rev-pinned vendored tool, `core/tests/test_no_credential_literals.py`
adds an AST check in this repository's own suite. **Adding the rule upstream
would be the better fix and is recorded as an upstream request.**

That check found a **thirteenth** file the inventory above had missed:
`DASHSCOPE_API_KEY` in `narrative_restart_drill.py:116`. Read and confirmed
benign — `'drill-key'`, nine characters, in the same dict that points
`DASHSCOPE_COMPATIBLE_URL` at a local stall server on `127.0.0.1`, where a real
DashScope key is `sk-` plus 32 hex. Pinned to one file:line:variable with its
reason, and a further test fails if the pin stops matching the line it was
written for.

### Repair order (not performed here)

1. **Rotate or revoke the credential first.** Everything else is cleanup;
   until this is done the exposure is live.
2. Move runtime credentials to deployment secret configuration, so no default
   value exists in tracked source.
3. Remove every tracked default and harness copy, including the ones in this
   directory.
4. Assess database access logs for use of the credential from unexpected
   sources, and review whether the role needs CREATEROLE and CREATEDB at all.
5. Decide whether coordinated history rewriting is required, given the GitHub
   remote and the 14 commits carrying the value. That is a decision with
   collaboration cost, not a mechanical step.
6. Restore the check to high-signal enforcement. Two parts, both needed:
   add narrowly scoped exceptions for the genuine throwaway-key false
   positives so it is not muted wholesale, **and** extend detection to the
   environment-lookup-with-literal-fallback pattern it currently misses —
   otherwise the check would still pass over the credential this finding is
   about. Then make it blocking rather than report-only.
7. Assess the two hardcoded JWTs in `rework/browser_pass.js`: determine which
   secret signed them and whether they are still valid.

**Disposition: open.** No repair attempted, no rotation performed, and nothing
about the exposure changed by recording it.

## V2-053 — Ruling 1 leaves R&D investment scored but mechanically inert (P1) — OPEN, rules owner / GSP-CRV2-11

Raised by the builder during Stage 3B, before repair, because the repair is a
rules decision rather than a defect fix.

Ruling 1 retires `_process_feature_investments`. That function was the only
consumer of `DecisionRDInvestment` that changed anything about a product. The
rows themselves are still accepted (on platforms not yet ready), still charged
against cash and the R&D budget, and still **scored**:

- `engine/performance.py` sums `rd_investments.amount` into `rd_spend` and
  scores it against the scenario's `rd_spend_target`. This is the R&D component
  of the performance index (V2-021).
- `engine/coherence.py` iterates the same rows to score feature/segment
  alignment.

So after Ruling 1 a team can spend on R&D, be charged for it, score for it, and
receive no capability in return. Spend becomes score-buying disconnected from
the product.

**Two further facts, both measured:**

- Rows targeting a platform that is not yet ready were **already** inert before
  Ruling 1 — the retired processor began with `if tp.status != 'active':
  continue`. So the silent-ignore predates this handoff; Ruling 1 widens it to
  every row.
- Freezing *all* platforms rather than only ready ones would close the
  silent-ignore, but it would take `rd_spend` and the R&D coherence term to zero
  for every team in every round, permanently. **That is a balance rewrite and
  was not done.**

**Options for the owner, neither taken here:**

1. Point `rd_score` and the coherence term at platform-development spend, which
   is where R&D investment now actually happens. Note that platform spend is
   lumpy — one large charge in a funding round, nothing in others — so the
   ratio against a per-round target needs recalibration. That makes it
   GSP-CRV2-11 work, not a drop-in.
2. Keep `DecisionRDInvestment` as pure research spend with no feature effect,
   and say so in the student-facing rules, so a team is not buying a capability
   that never arrives.

**Not repaired in Stage 3B.** The freeze was implemented exactly as ruled —
ready platforms only — precisely so that this decision stays with the owner
rather than being made silently by a builder closing a test failure.

## V2-052 — the manifest schema definition chain was overwritten (P1) — implemented at `5873695`, pending integrated Stage 3/4 closure

Raised by the Stage 4 rework re-audit at `b9e1282`. The Stage 4 rework
checkpoint claimed `manifest_schema_v2.json` was "kept as the record of what
version 2 meant". It was not: the file had already been rewritten while still
declaring version 2.

**Three definitions were in force under version 2**, not the two the re-audit
named:

| Commit | Date | Handoff | Change under version 2 |
|---|---|---|---|
| `61c43da` | 2026-08-28 | GSP-CRV2-01 | version 2 as introduced |
| `f63e8b7` | 2026-08-28 | GSP-CRV2-03 | `narrative_alert` section; hashed `source` field |
| `24687f0` | 2026-09-02 | CRV2-10 Stage 4 | `team_product_platform_history`; hashed `funded_round` |

**Bounded correctly by the re-audit:** no stored hash was ever wrongly matched.
`require_schema_version` only ever compares equal versions and refuses the
rest, so the failure is evidentiary, not a false verification result. What was
lost is the ability to say which definition a stored v2 hash was taken over —
and CRV2-08's whole dispute posture rests on being able to say exactly that.

**Repaired at `5873695`.** All three definitions preserved under
`core/services/manifest_schema_history/` and pinned by sha256 in
`PROVENANCE.json`; `manifest_schema_v2.json` restored to its `61c43da`
content; `SchemaProvenanceTests` (4) fails on any modification to an
already-in-force definition, on a canonical v2 file that is not the original,
on an inventory that does not declare the current version, and on a current
version with no provenance entry. Both stale version references corrected.

Controls: overwriting the canonical v2 file with the `24687f0` state — V2-052
reproduced exactly — fails the guard with both digests named; editing a pinned
historical definition fails it by name.

**Why it was possible:** nothing distinguished a *current* inventory file,
which `dump_manifest_schema` is meant to rewrite, from a *superseded* one,
which is evidence. The version guard protected comparisons between versions and
nobody had asked what protects a version's own definition.

## V2-049 through V2-051 — raised by the GSP-CRV2-10 Stage 4 audit

**Status after the Stage 4 rework.** All three are **implemented at `b9e1282`
and pending integrated Stage 3/4 closure** — not closed. Each has a reason
control reverting the repair in isolation and reproducing the audit's own
figures; see `GSP-CRV2-10_STAGE4_REWORK_CHECKPOINT.md` and
`evidence/decision-rules/stage4-rework/reason-controls.md`.

- **V2-051** — the root cause was the shared `_get_team()` helper, used by nine
  call sites, not the one route the audit probed. All nine now resolve the team
  through the URL game. A cross-cohort attempt on the mutating route is
  recorded as an `AuthorizationRefusalEvent`, which nothing was doing: the
  middleware refusal never fired because the instructor genuinely owns the URL
  game.
- **V2-050** — historical marketing rows are attributed to the platform their
  product used in each row's own round. A new static guard covers relationship
  traversals, not only direct reads, and found a second latent copy of the same
  shape in `_team_has_generation` (uncalled; corrected).
- **V2-049** — the write-off reaches `total_opex`, operating income, net
  income, cash and the tax deductions, and is stored as its own
  `RoundResultFinancials` field exposed on the team's own results but not on
  the competitor block. Decimal units preserved end to end.

Two further items surfaced during the rework and are recorded rather than left
implicit:

- `MANIFEST_SCHEMA_VERSION` moved to **3**. The new financial field and Stage
  4's earlier `team_product_platform_history` section both change what a round
  hashes to; the section landed without a bump, which it should have had. Two
  envelope definitions sharing one version is the one case
  `require_schema_version` cannot survive — it would read a definition change
  as tampering.
- `read_inventory.json` had been stale since `8a46599` (route count 780 vs
  781). The route is POST-only and adds no read disclosure surface, but the
  guard test lived outside the affected set of both the checkpoint and the
  audit.


Registered by the independent audit of frozen runtime `8a46599` / checkpoint
`762d70d`, before repair. The submitted hashes, clean-backend provenance and
179 distinct passing executions all reconcile; these are gaps in what that
suite exercised. Full reproduction and the bounded repair contract are in
`rework/GSP-CRV2-10_STAGE4_REWORK.md`.

### V2-049 — the platform-switch write-off is recorded but neither charged nor shown (P1) — open

`calculate_operating_expenses()` records `platform_switch_write_off` in
`context.opex`, but `generate_financial_statements()` does not include it in
`total_opex`, operating income, net income or cash, and `calculate_tax()` does
not include it in deductions. `RoundResultFinancials` has no distinct field,
so the results surfaces cannot show the line the Stage 4 rule promises.

An isolated real-path probe produced the authoritative $750 history/context
amount for 100 units at $50 and 15%, then stored operating income without that
$750. A second probe exposed an amount error before financial assembly:
`units_unsold` is decimal, but the service and history coerce it to integer;
100.50 units were recorded as 100 and undercharged accordingly.

**Disposition: open.** The stored result/visible line, P&L, tax, cash and exact
decimal basis must all agree at the actual Phase-1/results boundary.

### V2-050 — a later re-base changes a past round's brand-awareness input (P0) — open

`preference_engine._derive_brand_awareness()` compares an as-of-round target
platform with historical decisions filtered through
`team_product__team_platform`, the product's live pointer. After a later
switch, the two sides refer to different dates and the old promotion rows
vanish. With $1,000,000 historical promotion spend, the same round-3 call
changed from `0.9516258196404048` before a round-4 switch to `0` after it.

The submitted replay test covers the helper ID and a platform feature value,
not this cumulative marketing feature. The six-site inventory also searched
for direct reads and missed a relational ORM traversal.

**Disposition: open.** A published round's competitive input changes after
later state, so the CRV2-01 determinism boundary is not preserved.

### V2-051 — the re-base route permits cross-game competitive writes (P0) — open

`ProductRebaseView` resolves the URL game and the URL team independently. A
student can use an unrelated game's current round/status to re-base a product
on the student's own team. More severely, an instructor who owns game A can
place a team/product from instructor-owned game B in game A's URL: the game
scope guard approves A, the team permission exempts instructors, and the view
mutates B. The isolated probe returned HTTP 200 and moved the foreign product
from platform 1 to platform 2.

The resulting successful decision-audit event is attributed to URL game A and
its round while naming game B's team, so both state and evidence cross the
cohort boundary.

**Disposition: open.** Resolve and authorize the game/team/product/platform as
one hierarchy before any switch or successful audit write.

## V2-037 through V2-044 — raised by GSP-CRV2-10 Stage 1

**Eight confirmed findings, one withdrawn theory.** All registered before any
repair, from executed probes rather than source reading: each item was
submitted against an isolated stack and read back from the rows.

Surfaces: A1, A1b, A1c, A2, A3, A4 and D1 were each measured through **both**
supported decision-write surfaces — the per-type `PATCH` and the
whole-submission `POST`. A6 has no decision surface and was measured through
the two operator surfaces it does have, `POST /api/roster/` and
`PUT /api/team-management/`. The per-probe matrix is in the Stage 1 record.

Stage 1 ran in two passes. The first, at `c20ebbb`, claimed both surfaces
throughout while its artifacts carried a single write for A1c, A3 and D1;
recorded `development_rounds: 0` as untestable when what it had measured was
creation being skipped; and raised a free ceiling-level initialisation that
measurement then disproved. All three are corrected in the entries below, and
the withdrawal is recorded rather than deleted.

Evidence: `evidence/decision-rules/STAGE1_PROBE_RECORD.md`,
`stage1-probe-record.json`, `stage1-a1b-reprobe.json`,
`stage1-rework-probes.json`.

**Status after the Stage 4 audit.** Runtime `8a46599` contains the round-
versioned platform history, switch service, endpoint and Phase-1 precondition,
but Stage 4 **failed independent audit** with open V2-049, V2-050 and V2-051;
see `rework/GSP-CRV2-10_STAGE4_REWORK.md`. It is not implemented-pending-
closure yet. Stage 3B (freezing ready platforms and removing the old feature-
upgrade path) has not started and must not begin during this rework.

V2-039, V2-040, V2-044, V2-045, V2-046 and V2-047 all remain implemented-
pending-closure at their recorded revisions; Stage 4 did not close any of them.

Stage 4 touched the CRV2-01 determinism boundary twice, both recorded in
`GSP-CRV2-10_STAGE4_CHECKPOINT.md`: `team_product_platform_history` joined the
enumerated manifest envelope, and the V2-012 ordering guard was found not to
reach `core/services`, where Stage 4 put round-correct resolution. One real
unordered iteration existed there and is fixed; the guard now covers the
services the engine imports and derives that list from the engine rather than
from a hand-kept one. See `GSP-CRV2-10_STAGE4_CHECKPOINT.md`.

**Status after Stage 3A.** V2-039, V2-040 and V2-044 are **implemented at
`a713349` and pending integrated Stage 3 closure** — not closed. Stage 3 closes
only after Stage 4 delivers re-basing and Stage 3B freezes ready platforms, so
that the product is never in a state where neither route to a better product
exists. See `GSP-CRV2-10_STAGE3A_CHECKPOINT.md`.

**Status after Stage 2.** V2-037 and V2-038 are **closed at runtime revision
`75503cf`**, proved by `GSP-CRV2-10_STAGE2_REPORT.md` and
`stage2-authoritative-cost.json`. V2-039, V2-040, V2-041, V2-042, V2-043 and
V2-044 remain **open**: Stage 2 addressed the price of R&D and the budget rule
it escaped, and nothing else. V2-039, V2-040 and V2-044 are Stage 3's; V2-041
is Stage 5's; V2-042 is Stage 6's; V2-043 is the retirement fix.

### V2-037 — the price of R&D is set by the client (P0) — closed at `75503cf`

A platform authored at $15,000,000 (in-house) or $35,000,000 (licensed) is
obtained for `committed_cost: 0` on both write surfaces, becomes `active`, and
is charged **$0.00**. The same shape on the feature path: `target_level` at the
generation ceiling with `amount: 0` and `calculated_cost: 0` raises the feature
from 11.00 to its 14.00 ceiling and charges nothing in any round. The authored
prices exist in `PlatformGenerationDefinition` and in the level-cost table the
view already reads for display; nothing compares them to what was submitted.

Confirms A1 and A1b. The feature grant is lagged through `PendingFeatureGain`,
so it lands one round after the round it was submitted for — which is why the
first probe read it as unchanged, and why it was re-probed rather than withdrawn.

**Repair, at runtime revision `75503cf`.** One calculator,
`core/services/rd_costs.py`, with the adopted rule stated once: the cost a team
is shown is the cost the server computes, and the cost the server computes is
the cost it charges.

- **Platform price is authored by generation and method** —
  `development_cost` for `in_house`, `license_cost` for `license`. `method`
  previously changed neither the price nor the lead time; it now changes the
  price. Lead time is Stage 3's question.
- **Feature-upgrade price is the authored sum of `FeatureLevelCost` rows**
  between the current and target level. `RDContextView._build_cost_schedule`
  delegates to the same service, so the display path and the charge path read
  one table through one code path.
- **On both write surfaces**: an omitted client cost is filled with the
  authored figure, a matching value is accepted unchanged, and a disagreeing
  value is refused with the authored figure named and nothing persisted. Never
  silently corrected — a submitted decision quietly replaced with a different
  one looks ordinary afterwards, which is what made this finding invisible for
  as long as it existed. The cost fields became advisory to make server-filling
  possible; required and advisory cannot both be true.
- **A persisted disagreement refuses before competitive mutation**, in V2-018's
  shape, naming model, row, team, stored value and authored value. Measured
  with a row edited behind the API: `process` returned 400 and financial rows
  were 0 before and 0 after — a refusal, not a rollback.

**Bounded proof.** `evidence/decision-rules/stage2-authoritative-cost.json`;
`GSP-CRV2-10_STAGE2_REPORT.md`; `core/tests/test_rd_costs.py` (15 tests) inside
116 passing directly-affected contract tests. The single-source check asks the
scenario, the service, the engine precondition, the stored row, the budget
rule and the display schedule for the same platform and records
`all_agree: true`, computed from the figures rather than asserted.

**Disposition: closed.**

### V2-038 — platform cost escapes the cash and budget checks (P1) — closed at `75503cf`

`committed_cost: 999,999,999` accepted against $47,980,000 of cash and an
`rd_budget` of $1,000, and charged in full to `rd_expense`. The lock refusal
names the unlock round and three missing decision sections, and never the cost
or the cash. Confirms A2.

**Repair, at runtime revision `75503cf`.** `rd_costs.budget_assessment` is the
single answer to whether a team can afford what it has committed, and
**platform development counts against both cash and the R&D budget** through
it.

It replaced three copies of that rule which disagreed: `views/decisions.py:548`
and `:888` summed three budget lines, `:1015` summed four by including
`research_budget`, and none of the three counted platform development at all.
Three rules that disagree is one rule that does not exist.

**Bounded proof.** `core/tests/test_rd_costs.py` pins that a platform
development committed against a $1,000 R&D budget fails both the cash and the
R&D-budget checks and produces two named problems, and that a submission within
its means passes. The Stage 2 evidence records the same platform figure
appearing in the budget rule's `platform_development` line as in the service
and the stored row.

**Disposition: closed.**

### V2-039 — the generation unlock gate is enforced at lock only (P1) — implemented at `a713349`, pending integrated Stage 3 closure

Found inside the A2 probe. A Gen 3 platform, unlocking at round 5, was
submitted in round 3 and built by the engine with `status: 'active'`. The
unlock check lives in the lock validator; the team never locked, close
defaulted the submission, and the engine created the platform anyway. Not in
Part A.

### V2-040 — authored development_rounds is off by one (P1) — implemented at `a713349`, pending integrated Stage 3 closure

A generation authored `development_rounds: 2` is `active` with
`development_rounds_remaining: 0` after a single close/process/advance.
Confirms A3's second half.

**A3's first half is now measured too.** The Stage 1 rework retired both
subject teams' starting platforms so creation was not skipped, then submitted a
`development_rounds: 0` generation on both surfaces in round 1. After the first
advance — the processing of its own creation round — the platform is `active`
with `development_rounds_remaining: **-1**`. The negative value is the
create-then-decrement in a single call. It is ready in the round it was
created, exactly as Part A read it.

### V2-041 — no price band (P1) — open, Stage 5 owns the rule

Confirmed absent as Part A stated. In one open round the same product was
priced at 99999 (accepted, both surfaces) and then at 1 (accepted, both
surfaces), and 1.00 is what was stored. No anchor, alert, refusal or
adjustment exists.

**Severity P1, and the justification matters because this is an absent rule
rather than a broken one.** It is registered as a finding rather than as
scheduled Stage 5 work because the exposure is live now: a competition run
today has no band, so a team can price at 1 or at 99999 with nothing to stop
it, and the competitive consequence lands on every other team. Calling it
planned work would describe the schedule accurately and the risk not at all.
The rule itself is Stage 5's to build; the exposure until then is this
finding.

### Withdrawn — "free ceiling-level feature initialisation"

Raised in the first Stage 1 pass as a distinct mechanism inside V2-037: a newly
created platform appearing to receive ceiling-level features without a decision
naming them.

**Withdrawn. The reading was wrong, twice.** Measured against the authored
ceilings for the generation in question, a platform created with
`feature_levels: {}` initialises to 10.00, 10.00, 10.00, 8.00, 8.00 against
ceilings of 17, 16, 16, 17, 16 — every level below its ceiling. I had compared
one generation's observed levels against a different generation's ceilings, and
had not read the authored ceilings for that generation at all.

Initialising a new platform to its generation's baseline capability is ordinary
behaviour. The mechanism is recorded in the Stage 1 record so Stage 3 can
confirm the baseline levels are the intended ones; it is not evidence that
anything was obtained for free, and it is not a finding.

### V2-042 — cohort caps are not enforced (P1) — open, Stage 6 owns

Eight students enrolled through the roster surface (all 201) and assigned to one
team through team management (200, `{'updated': 8, 'errors': []}`), leaving
**11 active members on a team whose `team_size_max` is 5**. Neither surface
consults `max_teams`, `team_size_min` or `team_size_max`. Confirms A6.

### V2-043 — end_of_round retirement leaves the product on sale (P2) — open

`{timing: 'end_of_round'}` sets `TeamProduct.status` to `retired` and leaves
`TeamProductMarket.is_active` true; the `immediate` branch deactivates those
rows. Confirms D1 exactly.

### V2-044 — the write path accepts another team's platform; only the lock refuses it (P1) — implemented at `a713349`, pending integrated Stage 3 closure

Not in Part A. Narrowed after the Stage 1 rework measured what the first pass
left open.

**Proven.** Both write surfaces accept an R&D investment naming another team's
`team_platform`: per-type **200**, whole-submission **201**. With every other
required section filled so the validator is reached, the complete lock attempt
is refused **400** with `R&D investment references a platform not owned by this
team.`

**So the ownership check is correct and it runs at lock.** The finding is the
gap before it: the write surfaces persist the foreign row, and a team that
never locks is defaulted at close, so the row reaches the engine anyway. In the
first probe run exactly that happened — duplicate `PendingFeatureGain` rows
against the other team's platform, and a round left unprocessable by a
natural-key collision, the same failure class as V2-029.

Same shape as V2-039: a gate that exists only at lock time does not bind a team
that never locks.

Found by accident — the first probe run reused one team's platform id for both
teams. Registered because the API accepted it, not because the harness sent it.

### V2-045 — platform auto-funding spends the same opening cash more than once (P1) — implemented at `f39b853`, pending integrated Stage 3 closure

Raised by the independent audit of the Stage 3A checkpoint at `f81426c`, before
repair. `rd_costs.can_fund_platform()` compares each candidate's authoritative
price with the same unchanged `team.cash_on_hand`; the new-platform and carried-
draft loops do not reserve the cost of an earlier accepted candidate.

Reproduced with two $1,000,000 carried drafts and $1,500,000 of round-opening
cash. Both changed from `unfunded_draft` to `in_development`, both recorded
`funded_round=2`, and both clocks started. The real
`calculate_operating_expenses` output then booked $2,000,000 of `rd_expense` in
round 2. The lifecycle therefore labels both platforms funded even though the
team cannot fund them together, reopening the cash side of V2-038 on the new
auto-funding path.

**Repair, at runtime revision `f39b853`.**
`rd_costs.allocate_platform_funding` decides funding **once per team per
round** over every candidate — the drafts carried from earlier rounds and the
new requests in this submission — walking them with a running balance and
reserving each accepted authoritative cost before considering the next. It
returns only the funded set, so the lifecycle and the accounting path read one
authoritative selection; no second cost is approximated and no price is
lowered.

Priority is carried drafts first, then new requests, each in generation order,
then name, then id. Drafts first because a team that committed in an earlier
round and could not pay should not be pushed behind a request it made later,
which would let an old draft starve indefinitely. Deterministic either way,
which is what the accounting depends on. A candidate that does not fit stays
`unfunded_draft` with a null funded round and start round and no running clock,
and is reconsidered next round.

**Verification.** `AggregateFundingTests`, four tests at the real lifecycle and
accounting boundary: the reported two-draft case, where exactly one platform
starts and `context.opex` reports one price rather than two, and the remaining
draft is booked once in the later round its own clock starts; the same-round
two-request control; a pair written straight to the table, so aggregate safety
does not depend on the serializer having run; and the capitalisation mode
observing the same selection. The allocator was also run directly against the
audit's reported figures — two $1,000,000 candidates, $1,500,000 cash — and
funds one.

**Disposition: implemented at `f39b853`, pending integrated Stage 3 closure.**
Not closed: Stage 3 closes with the integrated Stage 3/4 evidence, after
immutability lands.


### V2-046 — duplicate generation requests create and charge duplicate platforms (P1) — implemented at `f348d24`, pending integrated Stage 3 closure

**Current status: implemented at `f348d24`.** The repair took three passes; the
two superseded states below are dated historical audit notes, not current
guidance.

**The defect, as raised** at `c20bd8b`. The V2-045 allocation refactor collected
every new request before creating any `TeamPlatform`, so the existing-platform
query saw the same initial state for two rows naming one generation. Both
entered the candidate set, both were funded, both were created. The supported
per-type write returned 200 and persisted two same-generation rows; with
$3,000,000 of cash and two authoritative $1,000,000 rows the production
lifecycle created two `in_development` platforms for one generation, gave both
`funded_round=1`, and the accounting output booked $2,000,000. Before the
refactor, creation happened inside the decision loop, so the second row
observed the first platform and was skipped.

**Repair, completed at `f348d24`.** Three layers on the decision side, and a
fourth on state:

- **Both write surfaces** refuse a submission naming one generation twice, as a
  cross-row rule raised before any row is priced, so a refusal writes none of
  the replacement payload.
- **The Phase-1 precondition** refuses a stored duplicate pair before any
  platform, result or accounting mutation. It refuses rather than
  de-duplicates: discarding a row would leave the stored decision and the
  resolved decision disagreeing.
- **The allocator** counts every non-retired platform per generation, drafts
  included, and a generation holding more than one promotes none of them — no
  status change, no funded round, no start round, nothing booked.
- **Existing duplicate state** refuses the round outright, naming every
  conflicting row, and is never deleted, retired or merged.

**Verification.** `DuplicateGenerationTests` (8) and
`ConflictedDraftAllocatorTests` (5): refusal on both surfaces with nothing
persisted; a refused pair leaving an earlier accepted row untouched; the
Phase-1 refusal with no platform created and no financial rows; the two-draft
case driven directly at the lifecycle and accounting boundary in both
accounting modes, with a single-draft control and a further control asserting
each draft is individually fundable, so the refusal can only be the conflict
rather than an unpriced candidate.

**Historical — superseded, recorded because each was audited as incomplete:**

- *At `9987688`:* refused duplicate rows within a submission, but never
  reconciled a carried draft against another non-retired platform of the same
  generation, so an upgrade residue from `f39b853` still promoted into a second
  live platform.
- *At `83ec2bd`:* the allocator's defence built its live-generations set by
  excluding `unfunded_draft`, so two carried drafts for one generation were
  invisible to it and the de-duplication promoted the first — choosing a winner
  from inventory that should have been refused, and charging for it. Phase 1
  refused that state upstream, which is why the ordinary path looked correct;
  the audit found it by invoking the allocator directly.


### V2-047 — an already-held generation is accepted, persisted and silently ignored (P1) — implemented at `83ec2bd`, pending integrated Stage 3 closure

Raised by the independent audit of the V2-046 repair at `f878ab6`, before
repair. The serializer's new cross-row rule compares generations only within
the incoming payload; the persisted precondition compares them only within the
current submission. Neither refuses a single request for a generation the team
already holds as active, in development or unfunded draft.

Reproduced through the supported per-type write with an active platform. The
request returned 200 and persisted its server-authored $1,000,000 cost. The
lifecycle's defensive `held` set then skipped it, created nothing and the real
accounting path booked zero. The stored decision therefore says “develop this
platform” while the resolved state and charge say no decision existed.

*Disposition when raised (historical): open.* Both supported writes and the
Phase-1 persisted boundary had to refuse an already-held non-retired generation
before mutation, leaving the retired-generation exception intact. See
`rework/GSP-CRV2-10_STAGE3A_REWORK_5.md`. The current status is the repair
below.

**Repair, at runtime revision `83ec2bd`.**

- **Both write surfaces** refuse a request for a generation the team already
  holds as active, in development or unfunded draft, validated **before**
  replacement so a previously accepted payload is untouched on refusal. The
  retired exception is preserved and asserted: a retired generation may be
  rebuilt.
- **The Phase-1 precondition** refuses a stored request against a held
  generation before any platform, result or accounting mutation, rather than
  skipping it and booking nothing.
- **Existing state** holding more than one non-retired platform per team and
  generation refuses the round outright, naming every conflicting row. Refused,
  never repaired: deleting, retiring or merging a row would silently discard
  competition state. The allocator additionally declines to promote such a
  draft, as a defence behind the refusal rather than a silent repair.

**Candidate database inventoried, not inferred.** `globalstrat_plus` holds 302
non-retired platform rows across 302 distinct team/generation pairs — zero
duplicates today. No database constraint prevents the state and runtime
`f39b853` could create it, which is why the guard exists.

**Verification.** `HeldGenerationTests`, 9 tests: both write surfaces refusing
a held generation, including when the holding row is a draft; a refusal leaving
the previously accepted payload unchanged; the stored-row bypass refused at
Phase 1 with nothing created and no financial rows; the active-plus-draft and
two-draft residues refusing with every conflicting row named; the allocator
declining to promote a residue draft and booking zero; and the retired
positive control on the write surface. V2-045 and V2-046 controls unchanged.

**Disposition: implemented at `83ec2bd`, pending integrated Stage 3 closure.**


### V2-030 — operator actions unreadable outside the Django admin (P1) — closed at `45eb83c`

**Found** during the CRV2-08 dispute walkthrough. The runbook's dispute-5
procedure tells an operator to "review operator events in timestamp order;
compare before/after, actor, reason and request ID". Every lifecycle action and
every refusal had been writing `OperatorAuditEvent` rows since CRV2-02, and no
product API or UI returned any of them. The only reader was
`core/admin.py:811`, a read-only Django admin registration behind a separate
maintenance login that competition instructors do not hold.

**Original failing evidence.** `evidence/post-close-disputes/dispute-answers.json`
at `8554db3`: 13 operator audit rows for the game, `answerable: false`, no route
returning any of them. The auditor ruled that the Django admin does not count as
the supported operator path.

**Repair** at `45eb83c`: read-only, ownership-scoped
`GET /api/games/{id}/instructor/operator-events/` and an Operator Log tab.
Returns actor, server timestamp, action, outcome, round, before, after,
conflict, reason and request id; filters by round, action and outcome; newest
first; refusals returned beside successes, because a race is one committed row
and one rejected row and returning only successes hides the half being asked
about. Registered in the sensitive-read inventory as an audit-category read.

**Verification.** `core/tests/test_operator_events_view.py`, 7 tests.
Repeat evidence `evidence/post-close-disputes/repeat-after-repair.json`: the
browser renders both a committed and a genuine rejected action, the rejected
filter returns a row, and the refusal carries actor, action, reason, conflict
and request id. An earlier repeat asserted only that `committed` was present
while claiming both outcomes were visible; that false positive was caught in
audit and the assertion now fails when either outcome is absent.

**Disposition: closed.**

### V2-031 — language preference never persisted (P2) — closed at `45eb83c`

**Found** in the CRV2-08 usability smoke. `LanguageSwitcher` built its URL as
`process.env.REACT_APP_API_URL || ''` while `api/client.js` uses `|| '/api'`.
In a default build the PUT went to `/user/preferences/` instead of
`/api/user/preferences/` and 404ed inside a silent `.catch(() => {})`: the
interface changed language and the choice was never stored, so it reverted at
the next sign-in or on another device.

**Original failing evidence.** `evidence/post-close-disputes/browser-walkthrough.json`
at `8554db3`: the shipped URL returned HTTP 404 and the identical call under
`/api` returned HTTP 200, in the same browser session.

**Repair** at `45eb83c`: the same default as the API client. **Verification:**
re-proven at HTTP 200 in `repeat-after-repair.json`. **Disposition: closed.**

### V2-032 — game ownership not enforced for instructor routes (P0) — closed at `d39ce04`

**Severity P0.** An instructor with no connection to a cohort could read that
cohort's raw submitted decisions, their payload hashes, the actor and the
request id — the evidence CRV2-08 certifies as the answer to disputes 1 and 2.
That is a competitive-confidentiality failure and is launch-blocking.

**Reproduction** at `ebf40fc`,
`evidence/post-close-disputes/instructor-ownership-scan.json`: as
`crv208_outsider`, an instructor owning an unrelated course, ten instructor GET
routes answered 200 for another instructor's game, including
`instructor/teams/{id}/decisions/`. Only the three routes carrying an explicit
`instructor_can_access_game` call refused.

**Third instance of one pattern.** V2-007's rework and CRV2-07's authorization
FAIL were both `IsInstructor` without an ownership check. `IsInstructor`
answers "is this an instructor"; it is not authorization for *this* game.

**Repair.** `GameScopeGuardMiddleware` enforces ownership by default for every
registered route naming a `game_id`, with `core/services/game_scope.py` building
the inventory from the URL patterns rather than from a list anyone maintains.
Exemptions must be explicit and carry a reason, and a contract test fails on an
exemption without one. The ownership rule itself is unchanged:
`instructor_can_access_game` remains the single definition.

Two defects were found while building it, both recorded rather than smoothed
over. The first inventory filtered on views already declaring an instructor
permission and so missed `/instructor/alerts/`, which declares none — an
inventory that asks views whether they are protected finds only the protected
ones. And `instructor_can_access_game` read `request.user.user_id`, which DRF
only populates inside the view, so at the middleware boundary it refused the
rightful owner; it now uses the same JWT-derived identity as the role check.

**Verification.** `core/tests/test_game_scope_boundary.py`, 9 tests.
Post-repair scan `evidence/post-close-disputes/ownership-scan-after-repair.json`:
94 routes inventoried, 65 reads and 37 writes exercised as an unrelated
instructor against a disposable clone, **0 disclosing, 0 not refused, 0 state
mutations**, owner reads 200 and reaches a normal `409` on a lifecycle control.

**Disposition: closed at `d39ce04`, accepted in audit.**

### V2-033 — unowned course readable by any instructor — **withdrawn, not a defect**

`instructor_can_access_game` treats a course whose `instructor_id` is NULL as a
shared pilot cohort visible to any instructor. Raised here as a possible
limitation; the auditor ruled it is the **adopted authorization rule**, not a
defect. CRV2-07 pinned the behaviour because the live pilot genuinely relies on
it, and the V2-032 rework was instructed to preserve the same helper semantics.

**Operational implication, which is the part that matters at launch:** a
prize-competition course that is not intended to be shared between instructors
**must have an instructor owner assigned before launch**. An unowned course is
shared by design, and no code change alters that.

The helper is unchanged and no ownership evidence was rerun for this
disposition. The two-route assertion in
`test_an_unowned_course_is_readable_by_any_instructor_on_two_routes` stays as a
pin on adopted behaviour, so narrowing it later is deliberate rather than
accidental.

### V2-034 — refused non-owner writes were not recorded (P1) — closed at this revision

**Registered before repair.** Every one of the 37 mutation routes exercised as
an unrelated instructor was refused with 403 and changed nothing, and none of
those refusals was recorded: no operator audit row, no read-log row. Original
evidence: `refused_writes_not_recorded_anywhere: 37` in
`ownership-scan-after-repair.json` at `d39ce04`.

**Why it happened.** V2-032's boundary refuses before the view, which is the
correct place to refuse, and it meant a cross-cohort lifecycle attempt reached
no auditing code at all. CRV2-02 established that operator refusals are
auditable; moving authorization earlier silently regressed that for exactly the
attempts most worth investigating.

**Repair.** `AuthorizationRefusalEvent`, a narrow append-only model, written at
the boundary before the 403 is returned. It carries the actor id and username,
the game attempted, the HTTP method, the resolved route and endpoint, the
server timestamp, `outcome='rejected'`, an ownership reason, and the same
`request_id` the caller receives in the response body.

Deliberately **not** an `OperatorAuditEvent`: that model describes a lifecycle
action with a before and an after, and the attempt never reached one — writing
it there would imply an action that did not happen. Deliberately **not** a
`SensitiveReadEvent`: a refused POST is not a read.

**No payload, header or credential is stored.** What the caller was trying to
send is not needed to investigate that they were refused, and copying it here
would place another cohort's payload into a table created to protect it.

Reads are not recorded here. `SensitiveReadLogMiddleware` already records a
denied read with the same actor, route, outcome and request id, and a second
row would double-count one disclosure attempt.

The write happens in its own transaction, so a record cannot vanish with a
rollback of the refused request, and a logging failure cannot turn a refusal
into a 500 — the 403 is returned either way.

**Protection and chaining, corrected.** The first repair claimed the table was
trigger-protected and chained because it had been added to
`audit_guards.PROTECTED_TABLES` and `audit_chain.SEAL_ORDER`. Neither claim held
on a deployed upgrade, and the audit caught both.

*Listing a table in a registry installs nothing.* `PROTECTED_TABLES` drives the
`install_audit_guards` command and the custom test runner, neither of which
touches a competition database that has already been migrated. Migration `0078`
created the table with no UPDATE, DELETE or TRUNCATE protection at all.
Migration `0079_authorization_refusal_guards` now installs both triggers on an
ordinary upgrade, using `audit_guards.install_table_sql`; its reverse calls
`uninstall_table_sql` and removes only this table's two triggers, leaving the
shared functions and every other audit table's guards in place. The focused
audit tests could not have caught this: the test runner installs the current
guard list after building its database, which is precisely what masked it.

*Being eligible for sealing is not being sealed.* Membership of `SEAL_ORDER`
only lets a pass triggered by something else include the row, so a final
refusal could sit unsealed indefinitely.
`AuthorizationRefusalEvent.save()` now calls the same `_schedule_seal()` every
other audit row uses: on commit, never inside the write, since the seal takes a
global advisory lock and taking it under the lifecycle locks would invert an
order CRV2-02 certified. One callback per transaction, not one per row.

Fixing this exposed a third defect that predates it. Migrations `0070`, `0071`
and `0072` called `install_sql()` with no arguments, which reads the *live*
`PROTECTED_TABLES`, so adding the refusal table made those historical
migrations try to install a trigger on a table created eight migrations later.
Every already-migrated database was unaffected and silent; every fresh install
failed. Each now pins the table list it was written against.

**Verification.** `core/tests/test_refusal_audit_integrity.py`, 11 tests, plus
a disposable-database walkthrough: migrating an empty database from scratch
installs both triggers with no manual step, `install_audit_guards --check`
passes immediately afterwards, direct SQL and ORM UPDATE and DELETE are refused,
TRUNCATE is refused under the non-test policy, reversing `0079` removes only
this table's triggers while the other five audit tables keep theirs, a
committed refusal produces exactly one `AuditChainEntry`, one seal callback is
scheduled per transaction rather than per row, the chain reports no unsealed
refusal, and a rolled-back refusal is neither stored nor chained.

`core/tests/test_refusal_audit.py`, 8 tests: recorded exactly
once; response and record share one request id; no state change and no operator
event; no payload or credential stored, asserted against the model's complete
field list; PATCH recorded; a refused read is *not* recorded here but is
recorded as a denied read; the owner is not audited by the boundary; the record
is append-only. Post-repair scan: **37 of 37 refusals recorded**, still 0
disclosing reads, 0 unrefused writes, 0 state mutations.

**Disposition: closed.**

### V2-036 — refusal evidence has no supported reader (P1) — closed at this revision

**Registered before implementation**, as the rule requires and as V2-030 and
V2-031 were not.

V2-034 made cross-cohort mutation attempts captured, append-only, trigger-
protected and chained. Nothing returns them: no endpoint, no management
command, no screen. Investigating "did another instructor try to act on our
competition?" requires ad hoc database access.

This is the same sufficiency class as V2-030. An append-only row the operator
cannot retrieve through supported tooling does not answer the incident it was
created to investigate, and the CRV2-08 ruling already rejected Django admin or
direct database access as a supported operator path. I recorded this in the
data dictionary as a "deliberate boundary of that repair", which was wrong:
naming a gap is not a disposition, and the audit was right to reject it.

**Reproduction.** `AuthorizationRefusalEvent` appears in no URL pattern, no
management command and no serializer at `ef9aca6`; the 37 rows produced by the
ownership scan are reachable only with a database client.

**Repair.** `python3 manage.py who_attempted`, read-only, the companion to
`who_accessed`: that command answers who *read* a team's decisions, this one
answers who tried to *change* a game they do not own and was refused. Filters
by `--game`, `--request-id`, `--user`/`--username`, `--method`,
`--route-contains` and `--since`/`--until`, with `--json` for an incident file.
Each row returns actor, game attempted, method, route and endpoint, server
timestamp, rejected outcome, ownership reason and request id.

No payload, header or credential can appear because none is stored on the row;
the command runs one SELECT and writes nothing.

A management command rather than an endpoint, on the ruling that one surface is
enough and the command is the bounded repair. Documented in
`OPERATOR_RUNBOOK.md` beside the read-ledger query it complements, and in the
data dictionary.

**Verification.** `core/tests/test_who_attempted.py`, 10 tests: found by game
and by request id; every incident field present; text and JSON describe the same
row; nonmatching game, actor, username, request id, method, route and time
range each exclude it; an unparseable timestamp is refused with a clear
message; no payload, token or credential string appears in either output; and
the command leaves the rows and the audit chain unchanged.

Demonstrated end to end in `who-attempted-walkthrough.txt`: an unrelated
instructor's attempt to close another cohort's round was refused with a 403
carrying a request id, and that id retrieves exactly that row.

**Disposition: closed.**

### V2-035 — instructor alerts readable by any signed-in student (P1) — closed at this revision

Found while widening the V2-032 inventory. `InstructorAlertsView`,
`InstructorAlertSummaryView`, `InstructorAlertAcknowledgeView` and
`TeamChangesView` declared no `permission_classes` and inherited the project
default of `IsAuthenticated`. A signed-in student read `/instructor/alerts/`
and `/instructor/alerts/summary/` with HTTP 200 — instructor-facing analysis of
teams, including other teams.

This is a role failure, not an ownership failure, and the two are repaired
separately: `permission_classes = [IsInstructor]` on the four views, with the
ownership boundary covering the other half. Verified: student and unrelated
instructor now receive 403 on both routes, the owning instructor 200.

## V2-029 — an accepted student write stalls the round (P0) — raised and closed by GSP-CRV2-07

**Raised** during the CRV2-07 failure walkthrough, while diagnosing a stage that
had passed on an unrelated `SnapshotError`. **Audited as blocking** at `16d49fc`
and closed by the repair described here.

**Defect.** `DecisionProductCreate.product_name` was free text with no
uniqueness validation on either supported write surface. Two reachable payloads
returned HTTP 200 and then made the round impossible to resolve:

1. two product creates in one payload sharing a name — refused by the input
   manifest's `decision_product_create` key `(submission_id, product_name)`,
   before Phase 1;
2. one create reusing the name of a product the team already owned — the
   decision rows are unique, so Phase 1 ran and created the second
   `TeamProduct`, and `complete_manifest` then tripped `team_product`'s key
   `(team_id, name)`.

In both cases the round stayed `open`, every retry failed identically, and the
instructor could not close the round. Because `complete_manifest` shares Phase
1's transaction (`advance_round.py:230`), the resolution rolled back whole: no
duplicate was ever persisted and no decisions were lost. Nothing was corrupted;
the round was stalled. Rollback integrity is not a substitute for validating an
ordinary student decision, and manual SQL was not an acceptable recovery.

**Reproduction at `16d49fc`** (historical):
`evidence/load-failure/duplicate-product-name.json`, driven through the student
HTTP endpoint for both variants.

**Repair.** One shared validator, `validate_product_names(creates, team)` in
`core/serializers/decisions.py`, enforcing both rules and raising an actionable
400 naming `product_name`. It is called from the per-type `.../products/`
endpoint before the replacement delete, so a refused payload leaves the team's
persisted decisions untouched, and from `DecisionSubmissionSerializer.validate`
so the whole-submission endpoint enforces the identical rule. Names are compared
exactly, after the serializer's own string handling — no case folding or fuzzy
matching was introduced. A retired product does not release its name, because
the manifest key spans the whole table.

The manifest natural-key refusals are unchanged and remain the backstop for
rows introduced outside the supported APIs.

**Verification.** `core/tests/test_product_name_uniqueness.py`, 10 tests: both
endpoints refuse both variants; neither writes a replacement row; two distinct
names accepted; another team may reuse the name; a retired name stays taken; a
rejected payload leaves the previous set intact; a corrected payload is accepted
and the round then resolves; and ORM-inserted duplicates are still refused at
the manifest boundary with zero partial results. Directly affected contract
suites (`test_decision_limits`, `test_permissions`, `test_auth_rounds`, 91
tests) pass unchanged.

## V2-010 and V2-011 — closed at `8ddd983` (option A adopted)

**V2-010.** `sc_engine` and `compliance_engine` now use `_cohort_key(game)` =
`game.section_id or game.id`, the rule `events.py` already applied. Two sections
of one class previously met the same events and different supply-chain and
compliance disruptions.

**V2-011.** Each probabilistic operation draws from its own stream, keyed by
cohort, round, subsystem and the identity of the thing being decided —
`sc_event_trigger:{template}` and
`compliance_enforcement:{regime_id}:{team}:{market_code}`. A single sequential
RNG previously meant draw *n* belonged to whichever combination reached it
*n*-th, so one team's presence moved another team's outcome.

Team is keyed on `id` rather than `name`, deliberately: instructors can rename a
team mid-game, and a rename must not resegment that team's stream — so the
manifest's `(game_id, name)` natural key is the wrong identity here.
`regime.regime_id` and `market.code` are scenario codes and are used directly.
`events.py`'s existing `operation_id` strings are untouched, because changing
them would resegment a stream that prior rounds were replayed against.

12 focused tests. The six required properties are asserted directly; because the
repaired engines no longer contain a shared sequential RNG, three further tests
reproduce that pattern in miniature and demonstrate the order-dependence and
cross-team coupling the keyed scheme does not have.

**RNG-impact gate.** The Stage 2 screen was recorded at `e3654ec`, before this
change. Rather than rerun it because source moved, the gate resolved the same
baseline and six representative probes under the repaired RNG: **baseline
unchanged, 6/6 probe deltas unchanged**, so the 107-probe screen still describes
the system it claims to and is retained. Narrow claim, stated as such — this is
evidence that *this fixture's* outputs did not move, not that the repair is
inconsequential in general. The fixture is a round-1 game where the
supply-chain and compliance subsystems have little to fire.

## New observation raised by GSP-CRV2-06 Stage 2 characterisation

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-023 | Balance / price response | **P1 closed by rules change** | GSP-CRV2-06 (raised, confirmed, repaired, reworked) | Two mechanisms, one finding. A team alone in its positioning group had no price response at all. Repairing that with an absolute reference price left a second: `price_competitiveness` is a bounded feature that reaches zero at 1.5x the reference -- \$630 -- and clamps, so above that point demand stopped responding while revenue kept multiplying by an unbounded `retail_price`. Both are closed: an absolute reference price, plus a scenario elasticity of 1.5 applied to adoption above the reference. Revenue and net income now peak at the reference and fall monotonically above it. | `v2-023-gate.json` and `characterisation.json`, both re-run at `9c909ae` across \$50 to \$200,000. | **Closed.** Both mechanisms measured above and below the clamp. |

**Mechanism confirmed.** `backend/core/engine/preference_engine.py:288`,
`_derive_price_competitiveness`, averages over teams sharing the product's
positioning in that market *excluding self*, then appends the team's own price:

```python
prices = [float(d.retail_price) for d in all_mkt_decisions]  # excludes self
prices.append(team_price)
market_avg_price = sum(prices) / len(prices) if prices else team_price
ratio = team_price / market_avg_price
value = f_max * (1.5 - ratio)
```

Where no rival shares that positioning, `prices == [team_price]`, the average is
the team's own price, `ratio` is exactly 1.0 at every price, and the feature is
`0.5 * f_max` identically. The gate measures that identity directly: 0.5000 at
$50 and at $2,000.

Two corrections to the earlier characterisation. The 4.76x revenue multiple was
an artefact of the range swept, not a bound — the relationship is exactly linear
in price with no demand penalty, so the multiple is whatever ratio of prices a
team chooses. And self-inclusion dampens price response for *every* team, not
only isolated ones: the shared team's own price enters its average, so at $2,000
its market average is 1,210 rather than the rival's 420. Being alone is the
degenerate case of a general effect, not a separate mechanism.

The exploit is a strategy choice rather than luck, because positioning is a team
decision: a team can take an unoccupied positioning and then price without
demand consequence.

**Severity.** P1 confirmed. The impact is unbounded in price, requires no
insight beyond reading the scoring rules, and compounds through cash into later
rounds.

**Stage 3 is stopped pending a rules disposition.** Optimising against a
confirmed pricing exploit would characterise the exploit, not the balance.
Three candidate dispositions, in the order they were offered:

1. Absolute price anchoring against a scenario or segment reference price.
   Largest change; removes the exploit at its root.
2. Exclude self from the average and fall back to a scenario reference price
   when no rival shares the positioning. Smallest change addressing the
   measured cause; also removes the self-inclusion dampening.
3. Widen the comparison set to the whole market rather than the positioning
   group. Keeps relative scoring; a positioning can no longer be empty.

Option 2 is the builder's recommendation. Any of the three changes scoring for
every existing scenario, so the choice is the rules owner's.

**Repair, and the evidence for it.** The adopted disposition scores price
against a scenario-authored reference:

```
price_ratio = team_retail_price / scenario_reference_price
price_competitiveness = clamp(f_max * (1.5 - price_ratio), f_min, f_max)
```

The reference is seeded at $420 -- the established baseline price, and the
price at which the old relative rule and the new absolute one agree, so a team
playing the documented baseline scores as it did before. Migration `0074` writes
it to existing scenarios and the three scenario YAMLs carry it for fresh loads.
`ScenarioConfig` is already an input and config manifest section, so the
reference is inside the deterministic input envelope by construction rather than
by addition. A missing, zero or negative reference fails the round closed in
`advance_round`'s precondition block, before the first competitive write; there
is deliberately no fallback to a team or cohort price, because that fallback is
the defect.

Re-run gate, both subjects:

| | $50 | $420 | $2,000 |
|---|---|---|---|
| price fit, isolated team | 1.0000 | 0.5000 | 0.0000 |
| price fit, shared team | 1.0000 | 0.5000 | 0.0000 |
| units, isolated team | 2584.99 | 3600.37 | 2569.01 |
| units, shared team | 1064.87 | 1434.51 | 1052.33 |

The isolated team's units were constant at 3600.37 across that whole range
before the change. Both teams now score identically at identical prices, which
is the independence property the disposition required.

Re-run price x production grid, at production 20,000. The grid records revenue
rather than units, and sets one price on every row, so units are revenue divided
by price exactly:

| price | revenue | implied units |
|---|---|---|
| $50 | 84,980.80 | 1699.62 |
| $420 | 887,174.40 | 2112.32 |
| $2,000 | 3,373,840.00 | 1686.92 |

Units were 2112.32 at all three prices before; they now fall about 20% at both
extremes. The composite index also stops rewarding price monotonically: it is
56.49 at the reference and 56.43 at $2,000, where before it rose from 53.17 to
56.34 with price.

Units fall at the cheap end as well as the dear end because segment preference
for price competitiveness is a gaussian ideal-point match rather than
more-is-better. That is pre-existing scenario design, not something this
disposition introduced.

**The rework, and why the first repair was not enough.** The paragraph that
stood here said revenue still rose with price, that net income at $2,000 was
about $2.4M better than at $420, and that this was a balance question for Stage
3 rather than the V2-023 defect. That was wrong, and the number contradicting it
was in the evidence beside it. `price_competitiveness` is a bounded preference
feature: with `f_max` 1.0 it reaches zero at a ratio of 1.5 -- $630 against a
$420 reference -- and clamps. `retail_price` has no upper bound beyond its
column precision and an API positivity check. Above $630, price stopped reducing
demand through fit entirely while revenue went on multiplying by price. The
original unbounded mechanism survived above the clamp, and the acceptance prices
of $50, $420 and $2,000 could not see it, because two of the three sat at or
above the clamp point.

Adoption now carries an absolute demand response, applied above the reference:

```
high_price_multiplier = (retail_price / reference_price) ** -elasticity
```

seeded at 1.5. Strictly greater than 1 is the property that bounds the tail: at
exactly 1 revenue would be flat above the reference rather than falling, and
below 1 it would still grow. Missing, non-finite and `<= 1` values fail the
round closed beside the reference check, before the first competitive write.

Two design choices worth recording. The multiplier scales the team's own
adopters rather than its competitive share, because a share penalty cancels out
when every team raises price together, which would leave collective inflation
free. And it applies before the production cap, because a team cannot sell what
nobody will buy at that price; production is a separate ceiling.

Re-run gate, five prices spanning two orders of magnitude above the clamp:

| price | fit | units (isolated) | revenue (isolated) | units (shared) | revenue (shared) |
|---|---|---|---|---|---|
| $50 | 1.0000 | 2584.99 | 14,269.14 | 1064.87 | 46,002.38 |
| $420 | 0.5000 | 3600.37 | **166,941.96** | 1434.51 | **520,554.99** |
| $2,000 | 0.0000 | 247.23 | 54,588.38 | 101.28 | 175,011.84 |
| $20,000 | 0.0000 | 7.83 | 17,288.64 | 3.20 | 55,296.00 |
| $200,000 | 0.0000 | 0.25 | 5,520.00 | 0.10 | 17,280.00 |

Price fit is a constant zero from $2,000 upward for both subjects -- the
premise of the defect, measured rather than assumed -- while units and revenue
fall strictly across that whole range. Revenue is maximised at the reference for
both, not at the top.

Re-run price x production grid, at production 20,000:

| price | revenue | implied units | net income | index |
|---|---|---|---|---|
| $50 | 84,980.80 | 1699.62 | -18,453,570.28 | 53.32 |
| $420 | 887,174.40 | 2112.32 | **-17,670,974.97** | **56.49** |
| $2,000 | 324,688.00 | 162.34 | -18,237,695.27 | 54.98 |
| $20,000 | 102,560.00 | 5.13 | -18,454,861.29 | 53.44 |
| $200,000 | 32,000.00 | 0.16 | -18,523,358.27 | 52.95 |

Revenue, net income and the index all peak at the reference and fall
monotonically above it. The $50 and $420 cells are byte-identical to the
pre-rework run, which is the evidence that ordinary below-reference behaviour is
untouched: the elasticity acts only above the reference.

**On how this was missed.** The first closure reported a 20% unit fall for a
4.76x revenue rise and called it a residual balance property. It was the defect,
still running, one clamp point higher. The lesson is the one this handoff keeps
producing: a response measured inside a range is not a response, and the
acceptance prices have to straddle the point where the mechanism changes rather
than sit inside one regime.

**Gate integrity note.** The gate refused five times before producing evidence:
a stale primary key, outcomes read after the rollback, a decimal string
comparison, a mis-keyed adoption query, and a non-existent `code` field on
`SegmentDefinition`. Every defect was in the harness, and none produced a wrong
number, because each surfaced as a refusal or an exception rather than as a
plausible result. The adoption defect is the one worth recording: the query
filtered on team and market and took `.first()` from a table unique per segment,
printing a fit that did not move when price moved -- in a run whose entire
subject is what moves when price moves.

## New findings raised by the GSP-CRV2-06 coverage probes

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-026 | Progressive disclosure / read surfaces | **P1** | GSP-CRV2-06 coverage rework | Write serializers consult `get_effective_unlock_round`; the SC read serializers use `fields = '__all__'` and never do. A value legally written while an instructor override was in force remains readable after the override is removed, in a round where the field is locked: `inventory.buffer_days` (unlock round 3) was returned at round 1 by `sc/round/1/inventory/` in both its list and direct round-object forms. | `progressive-disclosure-probe.json`. Real student walkthrough with a signed JWT; positive control 200; write refused at 400 before unlock and accepted at 201 under override; value 4242 persisted and read back. | **Closed by repair.** The registry now governs reads. |

**Repair.** `DisclosureGatedReadMixin` applies the same registry to reads that
`_reject_locked_fields` applies to writes, across all ten SC read serializers.
It **default-denies**: without a game and a round in the serializer context
there is no way to know whether a field is unlocked, and the safe answer to "I
cannot tell" is to withhold it, so a caller that forgets to pass context hides
gated fields rather than exposing them. The SC views now pass game and round on
every read.

Thirteen focused authorization tests cover each required proof: the field is
hidden before its unlock round and so is its companion; ungated fields are
untouched; the value appears after its legitimate unlock; missing and partial
context both deny; an override unlocks it for that class only; restoring the
schedule re-hides it -- the exact sequence that produced the leak; another
class's override cannot expose it; direct-object access renders exactly what
list rendering does; and another team's row is gated by the same round.

One test is a package-wide contract rather than a case: it walks every
serializer in `core.serializers`, takes the field names DRF actually renders,
and fails if any renders a registry-gated field without the gate. `esg` and
`plants` fields are gated on write and appear in no serializer's field list
today, which is incidental rather than enforced -- adding one name to one list
would have reopened the hole silently. The contract closes that.

**Severity.** Reclassified from P3 to P1 on the rules owner's instruction. The
original P3 rested on the exposure needing an instructor override-then-restore
and on the value being the team's own; the controlling fact is that a
disclosure schedule enforced on one side only is not a schedule.

| V2-028 | API / user endpoint | **P1** | GSP-CRV2-06 coverage rework | `/api/users/` is a registered route (`router.register(r'users', UserViewSet)`) and could not answer. `User.team_id` is a plain `IntegerField` -- the table is unmanaged and the column was never declared as a relation -- but `UserSerializer` and `UserWriteSerializer` both declared a `team` field and sourced `team_name` from `team.team_name`, and the viewset called `select_related('team')`. DRF raised `ImproperlyConfigured` before rendering anything, so every list and retrieve through the endpoint failed, as did the `assign-team` action's response. `assign-team` also set `user.team`, an attribute the model does not persist, so team assignment silently did nothing. | `test_user_endpoint.py`, five focused tests. Reachability established by search: the serializer is referenced only from `core/views/core.py` (`get_serializer_class` and the `assign-team` action) and re-exported from `core/serializers/__init__.py`; the viewset is routed at `core/urls.py:139`. | **Closed by repair.** |

**V2-028 repair.** Both serializers now expose `team_id`, the column the model
declares, with `team_name` resolved through a lookup rather than a join. The
viewset drops `select_related`, and `assign-team` writes `user.team_id`, which
persists. A dangling `team_id` renders a null name rather than failing, since
nothing enforces the target of a column that is not a foreign key.

Found while writing the V2-026 package-wide contract, which walks every
serializer and could not instantiate this one. It is recorded as its own
finding rather than folded into V2-026: a routed endpoint that always raises is
not a disclosure defect.

**Catalogue visibility — adopted rule, not an open question.** Scenario
supplier, lane, trade-finance-instrument and compliance catalogues are
authenticated scenario reference data, available from round 1. Progressive
disclosure governs team decision *fields* and stored team decision *values*, not
the existence or contents of shared scenario catalogues. Catalogue visibility is
symmetric across competitors and carries no team-specific decision value, so it
is not a disclosure surface. This is the adopted rule; it is not a limitation
and not an unresolved question.

**Probe field selection, and a fixture correction.**
`trade_finance.buyer_payment_instrument` was the first choice of disclosure
probe field. Its write serializer validates against the scenario's
trade-finance instrument catalogue, and the fixture then in use declared no
instruments, so the probe refused rather than reporting a vacuous pass and the
field was replaced with `inventory.buffer_days`.

That empty catalogue was a **fixture-selection defect, not a property of the
authoritative scenario**, and an earlier version of this register said otherwise.
`setup_test_game` takes the first available scenario when none is named —
`clean_energy_tech_2026`, which declares neither instruments nor suppliers —
while `consumer_electronics_2026` declares both and `load_scenario` creates
them. Loaded through the authoritative definition, the capable fixture reports
**6 trade-finance instruments, 25 suppliers, 20 shipping lanes and 5 compliance
regimes** (`value-conservation-probe.json`, fixture contract). Every claim that
the authoritative scenario lacks trade-finance instruments is withdrawn.

**Trade finance was exercised, and conserves value.** On that capable fixture
the instrument was cycled with the trade held constant, `letter_of_credit`
proved persisted on the intended row: cash and cash-plus-inventory move **0.00
in every round** against a matched control. Fees, coverage and settlement
duplicate no proceeds and turn no cost into income. `fixture_contract.py` now
asserts before any measurement that every decision family a probe claims has at
least one legal value, so a fixture that cannot express a mechanism says so
before it measures rather than after.

| V2-027 | Balance / early-lead lock-in | **Withdrawn permanently — measured, no lock-in** | GSP-CRV2-06 coverage rework | Two rounds of front-loaded legal investment produce a lead that does not erode and that a later identical investment cannot close. The subject front-loads rounds 1-2, then plays the documented baseline: its margin over the field goes 0.91, 2.59 while investing, then **10.36, 10.35, 10.33** after it stops. In a second playthrough an opponent front-loads in rounds 3-4 instead; its own index **falls** 59.26 → 53.80 → 48.80 while investing, and the gap widens from 2.59 to **17.78**, settling at 17.72. The gap never closes: measured drift after the challenger stops is **-0.03 per round**, which is **590.7 rounds** to close in a game of ten. | `early-lead-probe.json`. Two forward playthroughs, one disposable database each, six rounds, four teams, `Consumer Electronics 2026`. | **Withdrawn permanently.** Measured under controlled conditions: the lead erodes unaided and the strongest legal counter reverses it. |

**Withdrawn on the confirmation evidence.** The confirmation run reproduced the
same front-load against the same baseline opponents and the leader finished
**14.32 behind**, where the original probe had it 10.33 ahead. The control --
challenger doing nothing at all -- closed the gap as thoroughly as any of the
four counter-strategies, which is the tell that the strategies were not what
moved it.

The cause is recorded rather than inferred. The leader drew
`customs_documentation` enforcement in **NA, its revenue-bearing market**, in
rounds 4 and 5; revenue went to 0.00 in both, the V2-022 inactivity cap set its
composite to exactly 0.2500, and its index fell 63.72 → 58.72 → 53.72. The
challenger's freezes landed in LATAM and APAC, where it earns nothing, and cost
it nothing. That chain is the adopted V2-022 rule working as dispositioned: a
compliance-frozen team below the material-revenue floor receives the cap, and
production intent does not exempt it.

**What this says about the original finding.** Which market a freeze lands in
swings a six-round playthrough by roughly 25 index points -- larger than the
17.72 gap the original probe measured and reported as a structural property of
the scoring rule. That gap is consistent with a first-mover advantage and
equally consistent with the challenger having been frozen in a market that
mattered. One playthrough cannot distinguish them, and the original finding was
filed on one playthrough.

**Neither the bounds nor the four strategies can be read from this run.** The
attainable bound was computed against a leader capped at 0.2500 for a third of
the game, so 0.36 to 0.41 composite advantage per round measures the freeze
rather than the strategy. The absolute formula bound stands as arithmetic --
composite 1.0 gives +10.0 index change per round, +8.65 against a leader at
0.5675 -- and remains what it always was, a ceiling that assumes market and
financial maxima which are scored relative to the highest revenue in the field
and therefore require already out-earning the leader.

**What the index rule does say, independent of all this.** `index_change =
(composite - 0.5) x sensitivity` and `new_index = max(0, previous +
index_change)`: the index integrates with no decay term, so any gap persists
unless the trailing team scores a strictly higher composite. That is a property
of the formula and is not in question. Whether it produces an unassailable lead
in play is exactly what remains unmeasured.

**Measured under control, and the lock-in is not there.** Two playthroughs with
every exogenous shock silenced in scenario data -- five compliance regimes and
thirty-eight event templates, twenty of them supply-chain, all set to zero
probability -- with the baseline run twice and identical round for round, no
sales stopping and the inactivity cap never applying:

| | gap when front-load ended | gap at end | composite gap at end | adopter gap at end |
|---|---|---|---|---|
| both return to baseline | 2.53 | **1.88** | -0.0007 | +48,965.70 |
| challenger plays the strongest legal counter | 2.53 | **-4.39** | -0.0867 | **-111,034.30** |

**Classification: an intended first-mover return, and a reversible one.** With
neither team doing anything special the lead decays on its own -- 2.53, 2.38,
1.92, 1.90, 1.88 -- and the composite gap settles at -0.0007, meaning
current-round performance is equal to four decimal places. What remains is the
accumulated index plus a retained adopter advantage of 48,965 that the leader
paid for. Against the strongest catch-up plan already constructed, the
challenger takes the lead outright by round 4 and finishes 4.39 ahead, having
built an adopter base 111,034 larger than the leader's. A lead that erodes
unaided and reverses under a legal counter is not unassailable.

**The 17.72 gap was the freeze.** Under control the same front-load produces a
peak margin of 2.53, not 17.72. The original figure was compliance enforcement
in the challenger's revenue-bearing market, not a property of the scoring rule,
and the finding was filed on a single playthrough that could not tell the two
apart.

**No performance-index change is warranted on this evidence.** The integrator
property is real -- no decay term, so a gap persists unless the trailing team
scores a higher composite -- but under controlled conditions the trailing team
does score higher, both by simply playing on and far more so when it counters.

**Harness lesson, recorded because it caused the error.** The original probe
measured index, rank, cash and adopters, and could not say *why* a team's
revenue went to zero. Two rounds of enforcement were therefore indistinguishable
from a structural advantage. Every playthrough probe now records, per team per
round, whether sales stopped, whether the inactivity cap applied, and which
compliance freezes and events fired. A balance measurement that cannot explain
its own outliers will eventually report one as a finding.

**Bounds, so this is not read as more than it is.** One counter-strategy was
tested. Front-loading later fails to close the gap; that is not a proof that no
legal strategy closes it, and none is claimed. One scenario, one fixture
identity, a four-team field, six rounds, and a two-round front-load: other
schedules, fields and lengths are unmeasured. What is established is that the
one obvious counter -- do what the leader did -- makes the challenger worse off
and leaves the gap seven times wider than when it started.

**The tournament could not have found this.** Its candidates were single
policies applied every round, so no candidate ever built a lead and then
stopped working to see whether the lead held itself up. "No candidate exceeded
competent play" and "a lead is unassailable once established" are compatible,
and the second is the one this probe was asked to test.

## New findings raised by the GSP-CRV2-06 Stage 3 tournament

Measured by the bounded adversarial tournament at `stage3-tournament.json`:
15 targeted candidates against three opponent populations on one discovery
fixture identity, then the strongest three against all three populations on
three unused identities. Advantage is the subject's index minus what the same
team scores playing the documented baseline against the same opponents on the
same identity, so the fixture's own team advantage divides out.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-024 | Balance / opponent-independent dominance | **P1** | GSP-CRV2-06 Stage 3 | Issuing equity raises the performance index at no cost in the index. `equity-raise` -- the documented baseline plus `new_equity = $20,000,000` and nothing else -- beat competent play in **9 of 9 holdout cells**, worst-case **+0.66**, median +0.66. Its advantage is near-identical against competent (0.670), diverse (0.680) and incumbent (0.660) opponents, which is what opponent independence looks like in the data: the strategy does not compete for anything, it improves its own balance sheet. | `stage3-tournament.json`. Same-game counterfactual, three rounds per candidate, every candidate checked against the `decision_limits` policy before resolution. | **Open — stops the handoff.** |
| V2-025 | Balance / cost-minimisation dominance | **P1 closed by rules change** | GSP-CRV2-06 Stage 3 | Stripping the firm to nothing beats competent play. `skeleton-crew` -- zero R&D, commercial and operations headcount, zero ESG, zero strategy budget, everything else at baseline -- won **9 of 9 holdout cells**, worst-case **+0.22**. `rd-starved` won every discovery population on the same mechanism (worst +0.08). The saved cost raises net income, and the capability and satisfaction components do not charge enough for the loss to offset it. | `stage3-tournament.json`, `v2-025-attribution.json`, `v2-025-recheck.json`. | **Closed.** Strategic capability is now multiplied by staffing adequacy. Re-evaluated across the same nine holdout cells: skeleton-crew went from 9/9 cells won at +0.22 to **0/9 at -7.17 worst case**, and no zero-headcount variant retains an opponent-independent advantage. |

**V2-025 attribution, measured before any weighting change.** Each stripped
input varied on its own from one frozen checkpoint, everything else at the
documented baseline, every mutation proved to reach the row scoring reads
(`v2-025-attribution.json`). Baseline: strategy expense $3,900,000, revenue
$887,174.40, capability 0.6200, satisfaction 0.5772, index 56.54.

| arm | cost | revenue | capability | composite (`satisfaction_score`) | net income | index |
|---|---|---|---|---|---|---|
| rd headcount → 0 | -500,000 | 0 | **0.0000** | +0.0008 | +500,000 | +0.02 |
| commercial headcount → 0 | -300,000 | -420 | **0.0000** | +0.0005 | +299,582 | +0.01 |
| operations headcount → 0 | -400,000 | 0 | **0.0000** | 0.0000 | +162,043 | +0.00 |
| all headcount → 0 | -1,200,000 | -420 | **0.0000** | +0.0014 | +961,624 | +0.03 |
| ESG → 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| ESG → +1,000,000 | +1,000,000 | +19,676 | 0.0000 | -0.0005 | -980,407 | -0.01 |
| strategy budget → 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| R&D amount → 0 | 0 | 0 | **-0.0200** | -0.0049 | +100,000 | -0.09 |
| R&D amount → baseline | 0 | 0 | 0 | 0 | 0 | 0.00 |
| R&D amount → target | 0 | 0 | **+0.3800** | +0.0916 | -1,900,000 | **+1.84** |

**Headcount is the mechanism, and the reason is that nothing charges for it.**
Payroll is a real cash cost -- $1.2M across the three pools -- while the
capability component moves by exactly 0.0000 when every pool is emptied.
`_strategic_capability_component` reads R&D spend, product actions and strategy
actions, and never reads headcount at all; the word does not appear in
`performance.py`. So the saving converts directly into net income with no
offsetting term. The single-round index gain is +0.03, and the tournament
measured +0.22 over three rounds, which is that gain compounding through cash.

**The "satisfaction" column is not satisfaction, and the reading taken from it
was wrong.** `RoundResultPerformanceIndex.satisfaction_score` stores the final
composite score despite its legacy name. The +0.0014 recorded against
all-headcount-zero is therefore the composite moving with the index (+0.03), not
stakeholder satisfaction rewarding redundancies. No separate satisfaction sign
defect exists and none is registered. The attribution table's column is retained
because it is what the field is called, and is read here as the composite.

**The other two stripped inputs contribute nothing, for two different reasons.**
ESG at zero changes nothing because the documented baseline already invests
nothing, so `skeleton-crew`'s ESG term was a no-op; the positive-ESG arm was run
to establish the sign, and shows ESG *costs* index (-0.01) while raising revenue
(+$19,676). Strategy budget at zero changes nothing because it is a declared
budget, inert exactly as V2-021 established for R&D.

**The R&D gap the tournament left is now closed, and it inverts the picture.**
Actual R&D spend at the scenario target is worth **+1.84 index** -- sixty times
the headcount saving -- and zero spend costs -0.09. R&D intensity is strongly
rewarded. The tournament's "low-cost versus meaningful R&D" family measured
none of this because it varied `rd_budget`, the declared figure V2-021 made
inert, while actual spend sat pinned at the baseline in all three arms.

**V2-024 mechanism, confirmed in code.** `performance.py:110`
`_financial_component` scores `debt_score = 1 - clamp01(debt_to_equity / 2)` at
20% of the financial component. Issuing equity increases `total_equity`, which
lowers debt-to-equity, which raises the index. The issuance path at
`financials.py:207` correctly increments `shares_outstanding` under the V2-020
disposition -- and **the performance index never reads `shares_outstanding`**.
Dilution, ownership and the cost of equity appear nowhere in scoring, so the
gain has no offsetting term. It is repeatable every round and compounds.

`equity-and-dividend` (+0.57 in all nine cells, zero variance) shows the money
does not even have to be kept: raising equity and paying it straight back out
still beats competent play. That is the shape of a risk-free loop, and it is
why this is P1 rather than a balance preference.

**What the tournament did not find.** No candidate that attacks a closed
finding paid. Pricing at the V2-023 clamp scored -0.97, above the clamp -1.35,
and above the clamp with costs stripped -4.25. Commercial inactivity scored
-17.99 and near-inactivity -6.22, so the V2-022 cap holds. The three strongest
random-discovery candidates all lost to competent play against competent
opponents (-0.44, -0.52, -0.53) while winning against diverse opponents (+1.63,
+0.90, +1.21) -- exactly the population-specific win the worst-case-first
selection rule exists to reject.

**A family that was not validly exercised, stated rather than glossed.** The
"low-cost versus meaningful R&D" candidates varied
`DecisionBudgetAllocation.rd_budget`, the *declared* budget, which V2-021
deliberately made inert. Actual R&D spend lives in `DecisionRDInvestment.amount`,
which the genome never touches and which `build_optional` pins at $100,000.
`rd-at-target` and `rd-saturated` therefore scored exactly 0.000 against every
population -- identical to the baseline, because they *were* the baseline in
every respect that scoring reads. `rd-starved`'s +0.11 comes from zeroing
headcount and research budget, not from R&D. That family tested cost, not R&D
intensity, and the R&D dimension remains unexercised by this tournament.

**V2-025 re-evaluation, the nine existing holdout cells.**

| candidate | worst | median | best | cells won |
|---|---|---|---|---|
| skeleton-crew | -7.17 | -7.14 | -7.12 | **0/9** |
| rd-actual-zero | -0.24 | -0.23 | -0.22 | 0/9 |
| rd-actual-target | +4.29 | +4.35 | +4.40 | 9/9 |

Both closure conditions are met: skeleton-crew no longer wins every cell, and
no zero-headcount variant produces an opponent-independent advantage.

The incumbent population plays skeleton-crew here, where the tournament's played
equity-raise. The V2-024 rule now refuses equity-raise outright, so it cannot
form a population at all; "incumbent" therefore does not mean the same thing
across the two runs, and the artifact records it.

**A limitation this run exposed in the harness baseline, not in the game.**
`rd-actual-target` beats the baseline in all nine cells by about +4.3. That is
not an exploit: it costs $1,900,000 of real cash and buys capability, which is
the game rewarding investment. It is large because **the harness baseline
underspends R&D**. `baseline.py` declares an `rd_budget` of $2,000,000 -- the
documented competent figure -- while writing a single `DecisionRDInvestment`
row of `OPTIONAL_AMOUNT`, $100,000, a placeholder chosen so that every decision
type had a row to vary. Declared and actual differ by twenty times, and only
actual spend reaches scoring.

Every advantage figure in this handoff is measured against that baseline, so
each is relative to a competitor that underspends R&D. The V2-024 and V2-025
findings are unaffected in kind, because both were strategies that gained
*without* cost and would gain against any baseline; but the absolute margins
would be smaller against a baseline that spent the documented R&D budget. This
is recorded as a limitation of the evidence rather than corrected, because
correcting it means re-running the tournament, which the disposition excludes.

## New findings raised by GSP-CRV2-06 Stage 2 rule probes

Both measured by same-game transactional counterfactual at `b43c132`: one team,
one frozen checkpoint, one decision changed, everything rolled back. The
baseline was resolved twice and the delta was exactly zero on every metric, so
these differences are the rule and not noise. Evidence:
`evidence/adversarial-balance/rule-probes.json`.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-021 | Scoring / strategic capability | **P1** | Rules owner (raised by GSP-CRV2-06) | `_strategic_capability_component` scores R&D as `rd_spend / rd_budget`, clamped to 1, and capability carries 0.25 of the performance index. The denominator is the team's *own declared budget*, so the ratio measures self-consistency rather than investment. Declaring **$1** and spending **$1** scores 1.00 where a $100,000 programme against a $2,000,000 budget scores 0.05. Measured: index **56.54 → 58.45 (+1.91)**, composite **0.5772 → 0.6724 (+0.0952)**, while spending **$99,999 less** — cheaper *and* higher-scoring, and independent of what any opponent does. | `rule-probes.json` → `capability_ratio`. Single round; the multi-round trade-off is unmeasured — see the uncertainty note below. | **Closed** at `827a2e1` under an adopted disposition — see below |
| V2-022 | Scoring / anti-exploit guard | **P1** | Rules owner (raised by GSP-CRV2-06) | `_is_voluntarily_commercially_inactive` caps the composite at 0.25 only when *every* marketing row has production, promotion, distribution and sales staffing at or below zero. It tests the **decisions**, not the outcome. Setting `production_volume = 1` on one row defeats it: composite **0.2500 → 0.4123 (+0.1623)**, index **50.00 → 53.25 (+3.25)** — for **$181.86**. Critically, **`total_revenue` is `0.00` in both cases**: the team sold nothing. The guard is escaped by declaring an intention to produce, not by competing. | `rule-probes.json` → `one_unit_bypass`. The hypothesis was "sell one unit"; the measurement shows no sale is needed. | **Closed** at `827a2e1` under an adopted disposition — see below |

### Adopted dispositions and closure — V2-021 and V2-022

**V2-021 adopted rule**

```
rd_score = clamp01(rd_spend / scenario_rd_spend_target)
```

`rd_spend_target` is a scenario configuration value the team cannot choose,
initialised at **$2,000,000** — the figure `load_demo` scripts as competent
R&D, so a team playing the documented baseline scores what it always did. A
missing, zero or negative target raises `InvalidScenarioConfiguration` and the
round is not scored; a silent default would change what the competition rewards
without anyone deciding to, which is the failure V2-021 was. Cohort-maximum
normalisation was explicitly **not** adopted: it would hand $1 full credit
whenever $1 was the largest spend in the room.

Seeded in scenario YAML for fresh loads and by migration `0073` for scenarios
already in a database. `scenario_config` is already a manifest input section,
so the value is in the deterministic digest.

**V2-022 adopted rule**

```
material_revenue_floor = max($1, 0.01 x highest positive team revenue this round)
```

A team whose realised revenue is below that floor is commercially inactive.
The composite cap and the ranking guard now consume this one classification, so
the two controls cannot disagree about who competed. Declarations of
production, promotion, staffing or distribution do not exempt a team.

**The original exploit probes, re-run against the repaired rules at `827a2e1`:**

| Probe | Before | After |
|---|---|---|
| `$1` budget / `$1` spend | index **+1.91**, composite **+0.0952** | index **−0.09**, composite **−0.0048** |
| One unit of production | composite **0.2500 → 0.4123** (+0.1623) | composite **0.2500 → 0.2500** (0.0000) |

Both exploits fail. The `$1/$1` strategy is now marginally *worse* than the
baseline rather than better: it still keeps the $99,999 it declined to spend,
which is ordinary thrift, but it no longer buys a higher capability score.
The token-production team is capped exactly as the silent team is.

Controls: 13 focused tests for the two rules, 108 passing across the affected
set (`test_scoring_dispositions`, `test_cc18_compliance`, `test_equity_issuance`,
`test_decision_limits`, `test_engine`).

### V2-022 supplementary disposition — compliance-frozen teams (adopted)

A compliance-frozen team whose realised revenue is below the material revenue
floor **receives the commercial-inactivity composite cap.** Production intent
does not exempt it.

The two controls address different consequences and are meant to stack:

* the **compliance freeze** is the consequence of a compliance failure;
* the **inactivity cap** stops a team without material realised sales from
  keeping a competitively misleading composite score.

This reverses the previous behaviour, where a team with real production and
promotion but no revenue was explicitly not classified as inactive. Two tests in
`test_cc18_compliance` asserted that older rule; they are preserved and reversed
rather than deleted, and one now asserts the compliance-frozen, below-floor case
directly.

### Superseded — the disposition request as originally filed

### Disposition requested — V2-021

The ratio needs a denominator the team does not choose. Three candidates, in
the order I would rank them:

1. **Normalise against the cohort, as the other components already do.**
   `_market_component` and `_financial_component` both score with
   `_ratio(value, max_across_teams)`. Scoring R&D spend the same way makes
   capability comparable between firms and removes the incentive to shrink the
   denominator. Smallest conceptual change; consistent with the surrounding code.
2. **Normalise against a scenario-configured target R&D spend.** Stable across
   cohorts and explainable to students, but adds a parameter per scenario.
3. **Normalise against the team's own revenue or asset base.** Defensible as an
   intensity measure, but couples capability to size in a way the current model
   does not.

### Disposition requested — V2-022

The guard should test what happened, not what was declared. Concrete options:

1. **Cap on outcome, not intent** — apply the composite cap when revenue is
   below a configured floor rather than when the decisions are all zero. This
   also closes the variant found here, where revenue was zero and the cap still
   did not apply.
2. **Require materiality** — treat production below a threshold relative to
   demand or capacity as inactivity, so a token unit does not qualify as
   competing.

Option 1 is the smaller change and matches the guard's stated purpose. Note that
`_enforce_zero_revenue_invariant` is a *separate* control keyed on zero revenue;
whichever option is chosen, the two guards should be brought onto the same
definition rather than left with different tests for the same idea.

### Uncertainty on both

These are **single-round** measurements. A team declaring a $1 R&D budget also
funds no real R&D, so its feature levels should fall behind over a full game;
whether the index gain survives multiple rounds is unmeasured. Establishing that
is Stage 3's multi-round search, which is blocked on V2-010/V2-011. Neither
finding is claimed as a proven whole-game dominant strategy — each is a
demonstrated, repeatable, opponent-independent advantage within a round.

## New finding raised by GSP-CRV2-06 Stage 2

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-020 | Engine / equity issuance | **P0** | GSP-CRV2-06 (raised) | `generate_financial_statements` prices newly issued shares with `share_price_est = total_equity / shares_outstanding` at `financials.py:212`, but `total_equity` is not assigned until line 262 — fifty lines later, inside the same per-team loop. For the **first** team in the loop that raises equity this is `UnboundLocalError`, and because the call sits inside `_run_phase_1`, **the whole round fails to resolve for every team**. For any **later** team it silently holds the *previous team's* closing equity, so one company's shares are priced off another company's balance sheet and the dilution written to the leaderboard is wrong. Raising equity is an ordinary legal decision exposed by `DecisionFinancing.new_equity`. | Found by Stage 2 screening: setting `financing.new_equity` to its funded maximum crashed resolution. Nothing in the repository exercises `new_equity > 0` — every test and seed command sets it to `0`, which is why it survived. Inherited from the baseline snapshot `2509518`, so it predates globalstrat+. | **Closed** at `c781c8f` under an adopted rules disposition — see the closure entry below |

### V2-020 rules disposition — adopted

**Adopted formula:**

```
issuance_price = opening_total_equity / opening_shares_outstanding
```

Book equity per share, measured before the raise. Adopted because it preserves
the apparent intent of the defective expression, is available before the raise,
is specific to the issuing team, is deterministic, avoids pricing a raise with
the equity that raise creates, and is the smallest change from what was there.

**Considered and not adopted:** the latest price from `SharePriceHistory`. That
would move the model from book-value issuance to market-price issuance and
needs policy for missing and stale prices — a larger rules change than the
defect required.

**Verification at `c781c8f`** (`core/tests/test_equity_issuance.py`, 7 tests):

| Requirement | Test |
|---|---|
| First team raising equity resolves | `test_the_first_team_raising_equity_does_not_fail_the_round` — every team is still scored |
| Teams price from their own opening equity, never another's | `test_shares_are_priced_off_the_issuing_team_s_own_equity` |
| Equal equity-per-share ratios price identically | `test_equal_book_value_per_share_gives_equal_issuance_price` — $1m/1,000 shares and $10m/10,000 shares issue the same count |
| Different ratios give the counts the rule requires | `test_different_ratios_give_the_share_counts_the_rule_requires` — exact counts derived from the formula, and a fiftieth of the price buys fifty times the shares |
| No-raise behaviour unchanged | `test_a_team_that_raises_nothing_is_unchanged` |
| Replay inputs carry every opening value used | `test_the_manifest_captures_every_opening_value_the_price_uses` — `total_equity` and `shares_outstanding` are both in the input manifest's `team` section |
| The defect's shape cannot return | `test_equity_is_not_priced_from_a_figure_computed_later` |

Three of these fail against the unrepaired engine; the no-raise control passes
either way, which is what makes it a control.

## New findings raised by GSP-CRV2-06

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-018 | Decision validation / value loop | **P0** | GSP-CRV2-06 | **Thirteen** investment and headcount fields accepted a negative value, and `costs.py` adds several straight into `strategy_expense`, so a negative investment was income. Measured on resolved rounds: `environmental_investment = -5,000,000` turned a $1,130,000 loss into a $3,990,000 profit with zero revenue; a negative **headcount**, multiplied by a salary band, was worth **$50,002,530,000**. Seven further fields accepted negatives but were masked in the first probe by another field failing first, plus one supply-chain field — 21 in all. No lower bound existed anywhere, and the fields were reachable through the ordinary decision API. | `evidence/adversarial-balance/value-loop.json` and `negative-sweep.json`: identical teams differing in one field's sign, resolved through `_run_phase_1`; `strategy_expense_delta` equals the injected amount. | **Closed** by two defences. **API prevention:** one table in `core/serializers/decision_limits.py`, applied at field level to 21 fields across both write surfaces. **Engine fail-closed:** `_run_phase_1` applies the same table to the *persisted* rows before any competitive mutation and raises `InvalidPersistedDecisionError` naming model, row, submission and field — it refuses, it does not clamp, because a clamped value is a team's decision quietly replaced with a different one and scored as theirs. Needed because rows can also arrive from a migration, import, admin, shell or restore, and the engine scores rows. 17 focused tests; the API tests fail against the pre-repair serializers and the five engine tests fail with the precondition removed. |
| V2-019 | API uniformity / determinism | ~~P1~~ **Withdrawn — filed in error** | GSP-CRV2-06 | Filed as "the per-type R&D endpoint accepts a duplicate platform+feature payload the whole-submission endpoint rejects". **That was measured on the serializers, not the endpoints, and described as endpoint behaviour.** `DecisionPartialUpdateView` has called `validate_rd_investment_targets` on the assembled list since `86c2ad4`, so both endpoints always refused the duplicate. Contract tests written against the real API pass unchanged on the pre-repair code. What was real is narrower and not an exploit: the rule lived in two places — the submission serializer and the view — so any third caller using `DecisionRDInvestmentSerializer(many=True)` directly would have missed it. | `core/tests/test_decision_limits.DuplicateRdRowApiTests`: both paths refuse for the intended reason, the distinct-feature control is accepted, and neither writes a row. These pass before and after the repair. | **Withdrawn.** The duplication is repaired anyway: the rule now lives in `DecisionRDInvestmentListSerializer` and runs wherever the rows arrive together |

V2-018 was found in Phase 1, from the serializer registry and a controlled
engine probe, before any optimizer was built.

V2-019 is left in the register as a withdrawn entry rather than deleted,
because how it was filed matters more than that it was wrong. The check
compared `DecisionSubmissionSerializer` with `DecisionRDInvestmentSerializer`
and reported the result as "the API accepts". It never made a request, so it
could not see that the view supplies the rule the serializer lacks. Before it
reached even that state it reported "no divergence" twice for two different
wrong reasons — an unavailable platform/feature pair, then missing `team` and
`round` fields that stopped DRF calling `validate()` at all. A probe that
cannot tell "allowed" from "refused for an unrelated reason" is not evidence,
and neither is one that measures a layer and names a different one.

## New finding raised by GSP-CRV2-04

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-017 | Operator boundary / route inventory | **P1** | GSP-CRV2-02 boundary (raised by GSP-CRV2-04) | The route inventory that certified "0 unguarded mutating routes" can only inspect routes whose callback exposes a view class. Django's admin add/change/delete views are function-based, so **216 admin write routes are skipped entirely** — including `Game`, `Round`, `Team`, `DecisionSubmission`, `ActiveModifier` and `SCEventInstance`. A staff user can move round state through `/admin/` with no lifecycle lock and no `OperatorAuditEvent`. The `<path:object_id>/` routes that *do* appear resolve to `RedirectView` and are reported `lifecycle_mutating: false`, which is how a whole write surface came to be counted as harmless. | `_walk(get_resolver())` yields 778 routes; 371 have no view class and are skipped by `mutating_routes()`, 216 of them admin add/change/delete. `core/services/route_inventory.json` lists `admin/core/round/<path:object_id>/` as `RedirectView`, `lifecycle_mutating: false`, and lists no `.../change/` route at all. | Open — logged, not repaired here |

Reach is limited to Django `is_staff` accounts, not the JWT instructor role, so
this is P1 rather than P0. It is logged rather than repaired because the fix
belongs to V2-004's boundary, and changing that boundary here would invalidate
the concurrency certification GSP-CRV2-02 produced. GSP-CRV2-04 repaired only
the part inside its own scope: the five audit-record admins it registered are
read-only, and the database triggers refuse the writes regardless.

## New findings raised by GSP-CRV2-01

Severity legend, restated because the first triage of V2-010/V2-011 used it
wrongly: **P0 blocks; P1 degrades; P2 cosmetic.** A behaviour that can change a
published result is never P2.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-010 | RNG cohort key | **P1** | GSP-CRV2-06 | Two different cohort keys are in use. `core/engine/rng.py` seeds on `game.section_id or game.id`; `sc_engine._seed()` and `compliance_engine` seed on `game.id`. Two sections of one class running the same scenario therefore receive the same event stream but different supply-chain and compliance streams. Escalates to **P0** if parallel sections are ever scored against one another, because the disruption exposure they face would differ by construction. | Compare `core/engine/rng.py` with `core/engine/sc_engine.py:_seed` and `core/engine/compliance_engine.py`. | **Closed** at `8ddd983` — option A adopted, see below |
| V2-011 | Shared RNG stream | **P1** | Competition-rules owner (via GSP-CRV2-09) | The supply-chain and compliance passes consume a single `random.Random` across all teams, so draw *n* belongs to whichever (team, regime, market) triple reaches the roll *n*-th. Iteration order is now explicit and replay is exact, but adding or withdrawing a team shifts every later team's draw — one team's presence changes another team's outcome. | `core/engine/compliance_engine.py:enforce_compliance`; `core/engine/sc_engine.py:run_sc_state`. | **Closed** at `8ddd983` — option A adopted, see below |
| V2-012 | Iteration order | **P0** | GSP-CRV2-01 (closed) | The first ordering sweep inspected only inline loop iterators, so `rows = X.objects.filter(...)` followed by `for row in rows` was never checked. `_score_entry_mode_risk` iterated an unordered `TeamMarketPresence` scan; a restored database returned two markets in the opposite order, changing `RoundResultCoherence.breakdown` and the competitive hash. A published round did not reproduce. | Cross-environment replay of game 34 round 1: three same-host replays agreed with each other and disagreed with the original resolution; the section diff named `coherence` and the reordered `entry_mode_risk` list. | **Repaired** — 75 further sites ordered; the AST guard now resolves a loop over a local name back to its assignment. |
| V2-013 | Manifest envelope | **P1** | GSP-CRV2-01 (closed) | The output snapshot held only the competitive sections, so foreign keys pointing at configuration it did not contain (`Team.firm_starter_profile`, `Game.scenario`, `Team.home_market`) fell back to `core.Scenario#surrogate:7`. The competitive hash carried raw sequence values, defeating the surrogate-independence requirement. Never broke a replay, because a restored database reproduces the ids. | Inspect any pre-repair `output_manifest` for `#surrogate:`. | **Repaired** — both envelopes now pull in whatever identity requires; a test forbids `#surrogate:` in either. |
| V2-014 | Narrative envelope | **P1** | GSP-CRV2-01 (closed) | A narrative section's prose is separated into `narrative_rows` by the snapshot, and the narrative envelope was built from `rows` alone. `narrative_sha256` hashed briefing ids and round numbers, not a word of text — so a replay against a deliberately different model produced an identical narrative hash and the "prose differs, result does not" claim was unverifiable. | Two runs of game 36 round 1 under different endpoints reported the same `narrative_sha256`. | **Repaired** — the envelope carries `prose` and `prose_digests`; tests require that changing a briefing changes the narrative hash and leaves the competitive hash alone. |

| V2-015 | Narrative / manifest reconciliation | **P1** | GSP-CRV2-03 | Phase 2 writes into rows and fields that `output_sha256` covers, after that hash has been taken: `RoundResultCoherence.rag_score/blended_score/breakdown`, `SCEventInstance.resolution_data['narrative']`, and newly created `InstructorAlert` coaching rows. The hash never moves — it is computed inside the Phase-1 transaction — so every replay matches; what diverges is the *stored database* from the manifest that certified it, which no replay compares. | Resolve a round with an API key configured, wait for Phase 2, then rebuild the output manifest and compare with the stored `output_sha256`. | **Repaired in GSP-CRV2-03** — see closure entry. |
| V2-016 | LLM reaches a graded number | **P1** | GSP-CRV2-03 (closed) | `RoundResultCoherence.blended_score` is read by `core/services/grading.py`. With an LLM reachable, coherence was `0.6·formula + 0.4·RAG`; without one, the formula score stood. Two identical competitions therefore graded differently depending on an external service's availability. Rank was unaffected: neither `performance.py` nor `leaderboard.py` reads coherence. | `grep blended_score core/services/grading.py`; compare a round resolved with and without `DASHSCOPE_API_KEY`. | **Closed** at `49d6514` — see closure entry below |

### Disposition required for V2-010 and V2-011

Neither is implemented inside GSP-CRV2-01: changing a seed or a draw order
changes published results, which is a rules decision, not a hardening one. The
choice the competition-rules owner has to make is stated here so it cannot stay
ambiguous.

* **V2-010.** Either (a) cohort identity is meant to give every section of one
  class the same scenario stream, in which case `sc_engine` and
  `compliance_engine` must move to `game.section_id or game.id` and a test must
  pin all three call sites to one key; or (b) supply-chain exposure is meant to
  be per-game, in which case that is a published rule and the event stream
  should arguably move to `game.id` for the same reason. Silence is not a third
  option: today the two halves of the engine disagree.
* **V2-011.** Either (a) per-team independence is required — each roll keys on
  `(team, regime, market)` through `get_rng`, as the rest of the engine already
  does — or (b) a shared stream is accepted and the rules state that a
  withdrawal changes later teams' draws, with the withdrawal procedure written
  to match. Option (a) is the smaller change and matches `core/engine/rng.py`'s
  documented convention.

### V2-016 — LLM reaches a graded number (P1) — closed at `49d6514`

**Adopted rule: published coherence and the grades derived from it are the
deterministic formula score. Retrieval is instructor commentary and nothing
else.**

The first GSP-CRV2-03 submission made the blend configurable and defaulted it
off. The audit rejected that: a setting a supported deployment can flip is not
a safe competition configuration, and default-off left the defect one
environment variable away. The rework removed the Phase-2 write path outright.

At `49d6514`:

* `update_coherence_with_rag()` writes no competitive field in any
  configuration. It records the evaluation as an `InstructorAlert` with
  `source='narrative'`, which the manifest keeps outside the competitive
  section.
* `COMPETITION_RAG_AFFECTS_COHERENCE` is retired. The name survives only so a
  stack still setting it fails loudly:
  `require_safe_rag_configuration()` runs before the resolution transaction
  opens, so a misconfigured stack stops without taking a backup or a lock.
  Silently ignoring the flag would be worse than either behaviour — an operator
  who set it deliberately would believe retrieval was being graded when it is
  not.
* `core/tests/test_durable_narratives.py::CoherenceIsolationTests` proves all
  three legs: flag unset, flag set with the job run, and resolution attempted
  with the flag set.

Grading retrieval remains a legitimate rules choice. It is now a Phase-1
change — inside the transaction the manifest hashes, certified with the rest of
scoring — and not a flag. Nothing is outstanding for the rules owner.

- Evidence: `evidence/durable-narratives-rework/`.
- Completion: `completion/GSP-CRV2-03-completion.md`, rework addendum.

## Closure entries

### V2-001 — expanded output envelope (P0) — closed

`output_sha256` now covers **72 enumerated sections**: game/round lifecycle,
roster, every accepted decision table (including all ten supply-chain decision
tables), live market/event/modifier state, all eighteen carried per-team state
tables, and all published result tables. The section list, each section's
natural key, and the classification of every model field are recorded in
`backend/core/services/manifest_schema_v2.json`; every excluded field carries a
written justification, and `test_manifest_determinism` fails if a model gains a
field that no rule and no justification covers.

Phase-2 prose is hashed separately as `narrative_sha256` and reported
separately. Measured wall clock is excluded from the competitive hash and kept
in the input envelope, where it is a frozen fact about the starting state.

No surrogate primary key or foreign-key id reaches either envelope: a row is
identified by a natural-key token with foreign keys resolved recursively, and
the snapshot pulls in whatever sections identity requires (V2-013).

- Code: `core/services/manifest_sections.py`, `manifest_snapshot.py`,
  `manifest_schema.py`, `canonical_json.py`, `build_identity.py`,
  `resolution_manifest.py`; migrations `0061`, `0062`.
- Tests: `core/tests/test_manifest_determinism.py` (50), plus the updated
  envelope assertion in `core/tests/test_competition_hardening.py`.
  Backend suite 328.
- Evidence: `evidence/determinism/` — four replays of game 37 round 1 all
  produce `129a374ec6a82f22da9514ad3c263b856381024f46ad31790e5a36e08589b383`,
  including a second container on Debian 12 / Python 3.11 whose *process*
  timezone is `Asia/Kolkata` (`time.tzname == ('IST','IST')`) under
  `LC_ALL=de_DE.UTF-8`, asserted with `--require-env` rather than labelled.
  Four different narrative hashes, with the prose stored beside each.
- Docs: `DETERMINISM_BOUNDARY.md`, `ORDERING_AUDIT.md`,
  `evidence/determinism/README.md`.

### V2-002 — manifest sufficient to explain an input (P1) — closed

`input_sha256` covers canonical snapshots of the accepted decision payloads
themselves (not hashes of them), the full scenario and engine configuration,
per-class configuration overrides, live market/event/modifier state, starting
team and per-team state, the roster, the ordered decision audit trail, the RNG
seed derivation inputs, and the applied migration list. The code revision and a
host fingerprint are recorded alongside — outside the hash, deliberately, so a
cross-environment replay can match.

Surrogate primary keys appear nowhere: every row is identified by a natural-key
token with foreign keys resolved recursively, so a diff names the row a person
can recognise (`team(game("…")|"Nova Circuit")`) rather than an integer.

The envelope is versioned. Version-1 manifests stay readable exactly as stored
and are never reinterpreted as version 2 — `require_schema_version` refuses, so
a v1 hash cannot be compared against a v2 hash and called a match.

The build that resolved a round is identified by content, not only by a commit
hash. `core/services/build_identity.py` digests every runtime source file under
`backend/`; a `-dirty` suffix names the commit but not the modifications on top
of it, and two different patches on one HEAD produce the same string.
Resolution refuses an unidentified build when `COMPETITION_REQUIRE_CLEAN_BUILD`
is on (the default in production), and replay refuses a source mismatch before
it mutates anything.

- Command: `manage.py replay_round` verifies the source tree, asserts its own
  environment fingerprint (`--require-env`), and verifies input integrity
  **before** any mutation (exit 2, engine not run), printing per-section diffs
  on a hash mismatch (exit 3). `manage.py dump_manifest_schema --check` guards
  the inventory. `recover_competition_round` verifies the restored state
  against the recorded manifest before re-running.
- Negative tests: a corrupted decision payload, a corrupted scenario value, a
  corrupted carried-state value and an altered source tree each fail before
  processing — `evidence/determinism/negative/`. The source-tree case is the
  telling one: `git status --untracked-files=no` reported the tree clean and
  the commit hash was unchanged, and the replay still refused.
- Durability: each envelope is also written to a content-addressed file under
  `<COMPETITION_BACKUP_DIR>/manifests/`, so it survives losing the database.
  The digest in the filename is the manifest's own `input_sha256` /
  `output_sha256`.

### V2-004 — fail-closed operator concurrency (P0) — closed (second submission)

The first submission was returned FAIL. Its inventory was built by tracing the
routes its author knew about, so five registered lifecycle endpoints were never
examined, and a server-minted request id was regenerated per call so a refusal
response pointed at an id no audit row carried. Both are repaired below, and
the inventory is now built mechanically from `urls.py` — which found **nine
more** unguarded routes than the audit had listed.

Every action that can change round state, decision state or the roster now
passes through one coordination boundary — an exclusive advisory lock per game,
taken before any row lock — and evaluates its preconditions *after* acquiring
it. Student decision writes take the same lock shared, so they run concurrently
with each other and are excluded by any operator action.

**Twenty** entry points are on it and **zero** registered mutating routes are
unguarded, measured from the URL conf rather than from calls to the boundary
(`core/services/route_inventory.py`, checked in as `route_inventory.json`).
Sixteen routes carry view-keyed reviewed exemptions, each stating what was
checked. `RouteCoverageTests` fails on drift or on a new bypass.

**Six routes were removed rather than repaired.** All came from BECSR; four
queried `Round.objects.get(round_id=...)` — a field this project's `Round` does
not have — and so returned **500 to every caller**, and all six duplicated
close, reopen, deadline or bulk scheduling under a second vocabulary. "Lock"
and "unlock" meant `Round.decisions_locked`, a flag the *student write path*
reads independently of `Round.status`, so legacy unlock could let students
write into a closed round. That flag is now a projection maintained only by
close/reopen, with a test asserting it always equals
`status in ('closed', 'processed')`.

Newly guarded in this submission: `GameRoundScheduleView` (the only bulk
scheduler; now validate-all-then-write), `GameActivateView`, `GamePauseView`,
`GameResumeView`, `GameArchiveView`, `GameResetView` and
`InstructorTeamConfigView`. The five game-status views used bare `game.save()`,
which rewrites every column from its own copy and could rewind
`Game.current_round` past a concurrent advance.

The full inventory, the lock order, the 409/400 rule and the force-flag policy
are in `OPERATOR_CONCURRENCY_MATRIX.md`.

Two behaviours worth calling out:

* **Refusals are audited.** `OperatorAuditEvent` gained `outcome` and
  `conflict`. A rejected attempt is written *after* the transaction it refused
  has rolled back, in its own transaction, with an empty `after` — so a race is
  visible to whoever investigates without the row implying the round moved.
* **Callers can prove they were not racing.** `expected_round_number` and
  `expected_status` are compared under the lock; a mismatch is a 409
  `state_moved` naming what changed, which is what separates losing a race from
  asking too early. The console sends what it rendered.
* **One request id per request.** Resolved once and cached on the request. It
  was previously regenerated on each call, so a server-minted id in a refusal
  response was not the id on that refusal's audit row — the correlation the
  runbook tells an operator to use led nowhere. Tests assert the response id
  matches exactly one audit row, for supplied and generated ids alike and for
  commits, conflicts and preconditions.

- Code: `core/services/lifecycle.py` and `route_inventory.py` (new),
  `competition_locks.py`, `round_control.py`, `results_api.py`,
  `scenario_views.py`, `course.py`, `team_config.py`, `instructor_sc.py`,
  `decisions.py`, `team_control.py`, `advance_round.py`,
  `check_round_deadlines.py`, `recover_competition_round.py`,
  `competition_audit.py`; migration `0063`.
  Phase-2 dispatch moved to `transaction.on_commit`, so a view wrapping
  `process_round` cannot have the narrative thread read a round the database
  has not accepted yet.
- Tests: `core/tests/test_operator_concurrency.py` — 12 pairs × 100 races ×
  both arrival orders, plus route-coverage and request-id correlation tests.
- Evidence: `evidence/operator-concurrency/` — **1200 races, 0 deadlocks, 0
  5xx**, with advisory-lock rows sampled mid-race showing genuine contention
  and status-code tallies showing both orders really won (process+process
  53 / 47; schedule+close 52 / 48).
- Docs: `OPERATOR_CONCURRENCY_MATRIX.md`, operator runbook.

### V2-006 — durable Phase-2 narrative execution (P1) — closed

Resolving a round writes six `NarrativeJob` rows **in the same transaction as
the numbers**: if the results committed, the outstanding work is recorded.
Workers claim with `SELECT … FOR UPDATE SKIP LOCKED` under a lease, so several
run without coordinating and a worker that dies leaves a lease the next one
reclaims — nothing has to notice the death. Attempts are bounded, `failed` is
terminal and visible, and `retry_narrative_jobs` requeues without re-running
scoring.

`Round.processing_status` and `narrative_error` still drive the console, but
they are now a projection of the job rows rather than the only record, which is
what makes an abrupt death survivable.

A job that finishes on template fallbacks is recorded as `degraded` rather than
plainly `succeeded`. The drills found that: with an unreachable provider every
job reported success, because each producer falls back — correct for students,
who still get a briefing, and silent for operators.

- Code: `core/models/narrative_jobs.py`, `core/services/narrative_jobs.py`,
  `core/engine/narratives.py` (per-type runners), `advance_round.py`,
  `coherence.py`, `manifest_sections.py`, `manifest_snapshot.py`,
  `run_narrative_worker`, `retry_narrative_jobs`; migrations `0064`–`0068`.
- Tests: `core/tests/test_durable_narratives.py` — 28 tests covering enqueue,
  claim/lease/reclaim, timeout / 429 / 500 / malformed output / no key,
  idempotency, isolation and secret redaction. Backend suite **387**.
- Evidence: `evidence/durable-narratives/` — a real SIGKILL of a worker holding
  a claimed job, with recovery; three provider conditions including the live
  model. Competitive hash unchanged in every case.
- Docs: `NARRATIVE_WORKER_OPERATIONS.md` (supervision, leases, backlog
  alerting), `NARRATIVE_JOB_INVENTORY.md` (the Phase-1 inventory).

### V2-007 — database-enforced audit integrity and read evidence (P1) — closed in GSP-CRV2-04

**What the finding was.** The audit models raised on a second `.save()`, and
that was the entire defence. `Model.objects.filter(...).update()`,
`.delete()`, raw SQL, `manage.py shell` and the admin all skip `save()`, so
"append-only" described the usual write path rather than the table.
`ResolutionManifest` had no guard at any layer.

**What decided the design.** The application connects to PostgreSQL as the
**owner** of the tables it audits (`donwh`, verified against `pg_tables` and
`has_table_privilege`). Revoking `UPDATE`/`DELETE` from the connecting role
achieves nothing while that role can grant it back, and an owner can drop any
trigger. So the repair separates two claims that are easy to blur:

* **Rejected** — every write the application can make, at any layer. Triggers
  on all five audit tables refuse `UPDATE` and `DELETE` regardless of role.
* **Detected** — a change made by whoever holds the maintenance credentials.
  Nothing can reject that. A forward hash chain over the audit rows, with its
  head exported outside the database, makes it visible afterwards.

The report does not claim the second category is prevented.

**The manifest exception.** `ResolutionManifest` is written twice by design —
`prepare_manifest` before resolution, `complete_manifest` after — so a blanket
no-`UPDATE` rule would have broken round resolution. Its trigger allows updates
while `completed_at IS NULL` and freezes the row the moment it is set, which is
the moment it becomes evidence. `DELETE` is refused at all times.

**Sealing and the lock order.** Chaining runs in `transaction.on_commit`, not
in the audit write. The seal takes a global advisory lock, and taking it
underneath the operator lifecycle locks GSP-CRV2-02 certified would invert a
lock order and could deadlock. One seal is scheduled per transaction, and the
scheduling check reads Django's pending-callback list rather than setting a
flag, so a rolled-back transaction cannot leave a marker that suppresses the
next seal.

**Read evidence.** `competition_sensitive_read_event` records reads of raw team
decisions and audit payloads: actor, subject game/team/round, route, endpoint,
status, outcome, request id, server time. Refusals are recorded alongside
successes, because a denied cross-team read is the more useful row when a team
alleges disclosure. No payload, header or token is stored, and no API route
serves the table — it is reachable only through `manage.py who_accessed`.
Coverage comes from middleware matching `core/services/read_inventory.json`,
generated from the URL conf, so a view registered later is covered by
construction rather than by memory.

**Still open, and deliberately not closed by code.** The application holds the
owning credentials. `install_audit_guards --role-sql` provisions a non-owner
role and the SQL is tested, but pointing the competition stack at it is a
deployment action. Until then the reject layer is triggers alone.

See also V2-017, raised while building this handoff's inventory.

### V2-009 — supported frontend toolchain and green verification (P1) — closed in GSP-CRV2-05

**The finding named the wrong cause.** It attributed the Jest failure to the
Node engine mismatch (`react-router-dom@7` wants `>=20`, the VM's system node is
18). Reproduced on **Node 22.17.1**, which satisfies that range, the failure is
identical: `Cannot find module 'react-router-dom' from 'src/App.js'`.

The cause is packaging. `react-router-dom@7.1.1` declares `main: "./dist/main.js"`
and does not ship that file — `dist/` holds `index.js` and `index.mjs` only. Node
resolves the package through `exports`; react-scripts 5.0.1 pins jest 27, which
predates `exports` support, falls back to `main`, and finds nothing. Checked
against the registry, **every** published 7.x carries the same dead `main`
(7.1.1 → 7.6.3 verified, including a clean install of 7.6.3), so neither a
Node upgrade nor a 7.x upgrade fixes it.

**Repair:** `react-router-dom@6.30.6`, which ships the file its `main` names and
requires only Node `>=14`. All eight router APIs this application imports exist
unchanged in v6, no data-router API is used, and the two v7 defaults that could
have behaved differently are inert — every navigation in the codebase is
absolute, so `v7_relativeSplatPath` has nothing to change.

**Three further defects were found while closing it**, none of which the finding
mentions:

1. **`npm ci` could not install the project at all.** `react-scripts` peers
   `typescript@^3||^4`, `i18next`/`react-i18next` peer `typescript@^5`, no
   version satisfies both, and npm 10 installs optional peers by default. The
   1.6 GB `node_modules` on the VM was produced by some other command than the
   one the acceptance names. `--legacy-peer-deps` was tried and **rejected on
   evidence**: it makes the install succeed and the build fail, because
   `ajv-keywords@5` then cannot find the `ajv@8` it peers on. Settled with
   `overrides: { "typescript": "^5.9.3" }`, which leaves peer resolution strict
   and pins only a package with no source files in this repository.
2. **`axios@1.7.9` fails Jest for the same reason as the router** — ESM at
   `main`, CJS only via `exports`. Babel now transforms it, so the test runs the
   same source the browser bundle does.
3. **A failed drill-down request was displayed as "no submission data"**, the
   same thing shown for a team that submitted nothing. On the screen an
   instructor opens to defend a disputed result, a server error was being
   rendered as evidence about the team. Repaired and covered by test.

**Also closed:** `yarn.lock` removed (yarn is not installed on the host, so it
was a second source of truth nothing validated); runtime pinned in `.nvmrc`,
`engines` and `packageManager`; CI added reading the runtime from `.nvmrc`;
CRA's stock `renders learn react` placeholder replaced with a test that mounts
the app and asserts the router resolves the default route.

## Scope notes

- The Phase-2 LLM path is outside the existing output hash and is dispatched only after the deterministic transaction commits. No LLM value is read by the Phase-1 scoring call graph. This part of the v1 claim is structurally sound, subject to outage/restart verification.
- Wall-clock values are lifecycle/audit metadata or duration fields. They are excluded from the competitive hash by rule (`manifest_sections.MEASURED_TIME_FIELDS`) and kept in the input envelope as frozen facts about the starting state.
- The unordered-query sweep covered `core/engine/`: 168 iterated querysets there had no explicit ordering — 93 written inline and 75 reached through a local name, the second group found only after a cross-environment replay failed (V2-012). All now declare one except six documented exemptions whose result cannot depend on order. See `ORDERING_AUDIT.md`. An AST test fails the suite on any new unordered loop in either form, and a forward/reverse insertion test re-runs the whole Phase-1 pipeline over reordered rows. **Superseded in scope by Stage 4:** that sweep and its guard stopped at `core/engine`, and CRV2-10 Stage 4 put round-correct platform resolution in `core/services`, where one unordered iteration went unseen. The guard now also covers the services the engine imports, deriving that list from the engine rather than a hand-kept one. Unordered iteration remains in `core/services` modules outside the resolution set; none is reached from `advance_round`, and their behaviour on non-resolution surfaces is unassessed. See `GSP-CRV2-10_STAGE4_CHECKPOINT.md`.
