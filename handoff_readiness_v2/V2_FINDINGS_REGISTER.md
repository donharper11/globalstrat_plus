# GlobalStrat+ competition readiness v2 — findings register

Prepared 2026-08-28 against `competition-rc-2026.08.27.3` / `30dacac`.
Findings were recorded before repair. P0 blocks; P1 degrades; P2 cosmetic.

| ID | Area | Sev | Description | Reproduction / evidence | Initial status |
|---|---|---:|---|---|---|
| V2-001 | Determinism boundary | P0 | `output_sha256` covered only financials, performance-index rows, and leaderboard rows. It omitted coherence, product/market outcomes, adoption, resilience, share price history, and mutable `Team` state carried into the next round. | Compare original `complete_manifest()` at `30dacac` with `_run_phase_1()`. | **Closed** — see closure entry below |
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
folded into any stage of it. Credential rotation, revocation, source cleanup,
and history rewrite are complete. The remaining access-log and least-privilege
review is an operational hardening backlog; on 2026-09-05 the competition owner
accepted that residual risk as **not a competition-release blocker**. It remains
open until the DBA remediation and re-audit evidence are complete.

**Attribution unverified — awaiting owner confirmation (2026-09-12).** The
owner-acceptance sentence immediately above is recorded in builder-authored
files only; no independent record of that decision was found when the snapshot
was audited. It is left standing rather than deleted, because removing it would
lose the claim along with the doubt — but it must not be relied on as an owner
decision until the owner confirms it. What it disposes of is not small: the
operations review rates the surviving privilege item **P0** (V2-072 — the
application role can `SET ROLE postgres`), and this register's legend says P0
blocks release.

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
| 6. Restore the scanner to high-signal enforcement | **Done, in two halves.** The operator promoted `no-committed-secrets` to blocking and dispositioned its four findings with narrow, reasoned, fingerprint-pinned exceptions (`47e5748`). Detection coverage was added separately — see below. |
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

## V2-053 — Ruling 1 left R&D investment scored but mechanically inert (P1) — CLOSED at `f746cd4`

**Implemented per R10.** Both supported writes refuse a new
`DecisionRDInvestment` naming the platform-development/re-base route; the
engine precondition refuses any persisted row before competitive mutation,
refused rather than discarded or charged; `performance.py` no longer reads the
amount; `coherence.py`'s market-alignment component is removed with its scorer.

Nothing replaces either term. The surviving strategic-capability terms keep
their authored 30:30 ratio, normalised over their own weights so removal does
not deflate every team's ceiling to 0.60; coherence needed no adjustment
because the component contributed to numerator and denominator alike.

**Proved by mutation, not only by passing tests.** Restoring spend scoring
moves strategic capability 0.27 → 0.67; restoring the coherence component puts
`rd_market_alignment` back in the stored breakdown. Both first-attempt controls
*passed* under mutation — an unstaffed fixture compares 0 with 0, and a source
scan misses a restoration by another route — and that is recorded with the
evidence rather than quietly fixed.

**Carried consequences.** Ruling 1's narrower freeze is subsumed and
`frozen_platform_problem` deleted; four suites that tested sub-rules of the
retired decision are updated to the rule that now answers.
`scenario_rd_spend_target` is now an orphaned requirement — nothing divides by
it — and is left standing deliberately: removing a fail-closed guard an audit
installed was not this change's business, and the handoff fenced the setting
off. **That orphan is the one item worth an owner's decision.**

Evidence: `evidence/decision-rules/v2-053/`.

### Historical condition before R10 — superseded

**Everything in this section describes the state that raised V2-053, between
Ruling 1 and R10. None of it is current.** It is kept because it is why the
finding exists and what the implementation had to undo; the rule in force is
the one stated above.

Raised by the builder during Stage 3B, before repair, because the repair was a
rules decision rather than a defect fix.

Ruling 1 retired `_process_feature_investments`. That function was the only
consumer of `DecisionRDInvestment` that changed anything about a product. The
rows themselves were still accepted (on platforms not yet ready), still charged
against cash and the R&D budget, and still **scored**:

- `engine/performance.py` summed `rd_investments.amount` into `rd_spend` and
  scored it against the scenario's `rd_spend_target`. That was the R&D
  component of the performance index (V2-021).
- `engine/coherence.py` iterated the same rows to score feature/segment
  alignment.

So between Ruling 1 and R10 a team could spend on R&D, be charged for it, score
for it, and receive no capability in return. Spend had become score-buying
disconnected from the product.

**Two further facts, both measured at the time:**

- Rows targeting a platform that was not yet ready were **already** inert
  before Ruling 1 — the retired processor began with `if tp.status !=
  'active': continue`. So the silent-ignore predated that handoff; Ruling 1
  widened it to every row.
- Freezing *all* platforms rather than only ready ones would have closed the
  silent-ignore, but would also have taken `rd_spend` and the R&D coherence
  term to zero for every team in every round, permanently. **That was a balance
  rewrite, and was not done by a builder** — it is what R10 was raised to
  decide.

### Rule in force — R10

**Rules-owner decision, 2026-09-04.** Spending affects the simulation through
its budget, cash, financial-performance, and delivered-capability consequences;
it is not itself a score purchase. Future `DecisionRDInvestment` rows are
retired and must be refused on every supported write surface and at the engine
boundary. Direct strategic-capability and R&D-market-alignment scoring from
those rows is removed. Platform-development cost is **not** substituted as a
new direct score: a platform's actual delivered capabilities and their
market/financial outcomes are what remain competitively meaningful.

Published rounds remain immutable. An unprocessed legacy row is refused before
competitive mutation, not silently ignored or charged. See R10 in
`GSP-CRV2-10_RULE_DECISIONS.md` and the bounded implementation handoff
`handoffs/GSP-CRV2-10-v2-053-rd-scoring.md`.

### V2-054 — the V2-048 history rewrite invalidated every revision citation in the programme record (P1) — OPEN, documentation owner

Found during integrated Stage 3/4 closure, by resolving the register's own
citations rather than reading them.

The rewrite changed the SHA of every commit that carried the credential and of
every descendant — which is all of them. So every `implemented at X`,
`frozen at X` and `audited at X` written before 2026-09-04 now names a commit
this repository cannot resolve:

```
a713349 MISSING   f39b853 MISSING   f348d24 MISSING   83ec2bd MISSING
b9e1282 MISSING   5873695 MISSING   8a46599 MISSING   24687f0 MISSING
```

An auditor checking any of them gets nothing back. The evidence was not lost —
the commits exist under new SHAs — but the record could no longer reach it,
which for a programme whose whole posture is "the evidence is checkable" is the
failure that matters.

**Corrected here, scoped to this closure:** the six documents integrated Stage
3/4 closure depends on — the register and the Stage 2, 3A, 3B, 4 and Stage 4
rework checkpoints — had **55** citations translated through filter-repo's
`commit-map`, and every one now resolves.

**Not corrected, and why:** roughly 45 further narrative documents carry stale
citations, including the CRV2-01 through CRV2-08 completion reports and their
rework records. Those are other handoffs' closed records, and rewriting them is
not this closure's business.

**Deliberately not corrected:** seven files under `evidence/` also carry
pre-rewrite SHAs. Those are frozen records that were *correct when written* and
are covered by `CHECKSUMS.json`. Editing them would falsify a historical record
and break its checksum to fix a cosmetic mismatch. A frozen artifact naming the
revision that existed at the time is behaving correctly.

**The map is the dependency.** `.git/filter-repo/commit-map` is what makes any
of this translatable, and it lives in `.git/` — untracked, not pushed, and
destroyed by a fresh clone. Whoever repairs the remaining documents needs it,
or needs the pre-rewrite bundles, which are themselves scheduled for deletion
on 2026-09-18 (see `V2-048_BUNDLE_RETENTION.md`). **After that date the
translation is no longer recoverable.**

### V2-052 — the manifest schema definition chain was overwritten (P1) — implemented at `105ad44`, pending integrated Stage 3/4 closure

Raised by the Stage 4 rework re-audit at `301bb64`. The Stage 4 rework
checkpoint claimed `manifest_schema_v2.json` was "kept as the record of what
version 2 meant". It was not: the file had already been rewritten while still
declaring version 2.

**Three definitions were in force under version 2**, not the two the re-audit
named:

| Commit | Date | Handoff | Change under version 2 |
|---|---|---|---|
| `1d87281` | 2026-08-28 | GSP-CRV2-01 | version 2 as introduced |
| `4cec6ac` | 2026-08-28 | GSP-CRV2-03 | `narrative_alert` section; hashed `source` field |
| `729cc2c` | 2026-09-02 | CRV2-10 Stage 4 | `team_product_platform_history`; hashed `funded_round` |

**Bounded correctly by the re-audit:** no stored hash was ever wrongly matched.
`require_schema_version` only ever compares equal versions and refuses the
rest, so the failure is evidentiary, not a false verification result. What was
lost is the ability to say which definition a stored v2 hash was taken over —
and CRV2-08's whole dispute posture rests on being able to say exactly that.

**Repaired at `105ad44`.** All three definitions preserved under
`core/services/manifest_schema_history/` and pinned by sha256 in
`PROVENANCE.json`; `manifest_schema_v2.json` restored to its `1d87281`
content; `SchemaProvenanceTests` (4) fails on any modification to an
already-in-force definition, on a canonical v2 file that is not the original,
on an inventory that does not declare the current version, and on a current
version with no provenance entry. Both stale version references corrected.

Controls: overwriting the canonical v2 file with the `729cc2c` state — V2-052
reproduced exactly — fails the guard with both digests named; editing a pinned
historical definition fails it by name.

**Why it was possible:** nothing distinguished a *current* inventory file,
which `dump_manifest_schema` is meant to rewrite, from a *superseded* one,
which is evidence. The version guard protected comparisons between versions and
nobody had asked what protects a version's own definition.

## V2-049 through V2-051 — raised by the GSP-CRV2-10 Stage 4 audit

**Status after the Stage 4 rework.** All three are **implemented at `301bb64`
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
- `read_inventory.json` had been stale since `ac2883b` (route count 780 vs
  781). The route is POST-only and adds no read disclosure surface, but the
  guard test lived outside the affected set of both the checkpoint and the
  audit.


Registered by the independent audit of frozen runtime `ac2883b` / checkpoint
`17057d6`, before repair. The submitted hashes, clean-backend provenance and
179 distinct passing executions all reconcile; these are gaps in what that
suite exercised. Full reproduction and the bounded repair contract are in
`rework/GSP-CRV2-10_STAGE4_REWORK.md`.

### V2-049 — the platform-switch write-off is recorded but neither charged nor shown (P1) — implemented at `301bb64`, pending integrated Stage 3/4 closure

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

### V2-050 — a later re-base changes a past round's brand-awareness input (P0) — implemented at `301bb64`, pending integrated Stage 3/4 closure

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

### V2-051 — the re-base route permits cross-game competitive writes (P0) — implemented at `301bb64`, pending integrated Stage 3/4 closure

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

Stage 1 ran in two passes. The first, at `33d175b`, claimed both surfaces
throughout while its artifacts carried a single write for A1c, A3 and D1;
recorded `development_rounds: 0` as untestable when what it had measured was
creation being skipped; and raised a free ceiling-level initialisation that
measurement then disproved. All three are corrected in the entries below, and
the withdrawal is recorded rather than deleted.

Evidence: `evidence/decision-rules/STAGE1_PROBE_RECORD.md`,
`stage1-probe-record.json`, `stage1-a1b-reprobe.json`,
`stage1-rework-probes.json`.

**Status after the Stage 4 audit.** Runtime `ac2883b` contains the round-
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
`bfd5a26` and pending integrated Stage 3 closure** — not closed. Stage 3 closes
only after Stage 4 delivers re-basing and Stage 3B freezes ready platforms, so
that the product is never in a state where neither route to a better product
exists. See `GSP-CRV2-10_STAGE3A_CHECKPOINT.md`.

**Status after Stage 2.** V2-037 and V2-038 are **closed at runtime revision
`96a9aae`**, proved by `GSP-CRV2-10_STAGE2_REPORT.md` and
`stage2-authoritative-cost.json`. V2-039, V2-040, V2-041, V2-042, V2-043 and
V2-044 remain **open**: Stage 2 addressed the price of R&D and the budget rule
it escaped, and nothing else. V2-039, V2-040 and V2-044 are Stage 3's; V2-041
is Stage 5's; V2-042 is Stage 6's; V2-043 is the retirement fix.

### V2-037 — the price of R&D is set by the client (P0) — closed at `96a9aae`

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

**Repair, at runtime revision `96a9aae`.** One calculator,
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

### V2-038 — platform cost escapes the cash and budget checks (P1) — closed at `96a9aae`

`committed_cost: 999,999,999` accepted against $47,980,000 of cash and an
`rd_budget` of $1,000, and charged in full to `rd_expense`. The lock refusal
names the unlock round and three missing decision sections, and never the cost
or the cash. Confirms A2.

**Repair, at runtime revision `96a9aae`.** `rd_costs.budget_assessment` is the
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

### V2-039 — the generation unlock gate is enforced at lock only (P1) — implemented at `bfd5a26`, pending integrated Stage 3 closure

Found inside the A2 probe. A Gen 3 platform, unlocking at round 5, was
submitted in round 3 and built by the engine with `status: 'active'`. The
unlock check lives in the lock validator; the team never locked, close
defaulted the submission, and the engine created the platform anyway. Not in
Part A.

### V2-040 — authored development_rounds is off by one (P1) — implemented at `bfd5a26`, pending integrated Stage 3 closure

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

### V2-041 — no price band (P1) — repaired, pending closure

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

**Status update 2026-09-12 — repaired, pending closure.** The band is built and
merged. `core/services/price_band.py` (new, 404 lines) is the one calculator;
`price_band_pct: '0.30'` is **authored** in all three scenario YAMLs at `:38`
rather than embedded as a constant, and `core/migrations/0085_price_band_blank_price`
makes a blank price representable as one reversible `AlterField`. Commits:
`6b703e0` inventory before any runtime edit, `be0fa86` the band, its alert and
its audited adjustment, then two reworks under owner rulings — `a9b4039`
narrowing the blank rule under **R15**, and `49ea50b` under **Q4** of the same
day, after which an unpriceable blank is **not offered for sale** and the round
still resolves. The rule now in force: an out-of-band price alerts while the
round is open and is moved to the **nearer** band edge at the deadline; a blank
on a product that sold here last round is filled at the floor; a blank on a
product that never sold here is left null, recorded, and excluded from the offer
map; an in-band price is used as entered. Every deadline outcome writes a
`DecisionAuditEvent` with actor `system` and is visible to the team.

**Why the two reworks matter to anyone reading this entry later.** The first
implementation fabricated a floor-priced `DecisionMarketing` row for any active
product-market that had none; because `bass_engine` builds its offer map from
marketing rows alone (verified this revision at `bass_engine.py:66-72`, the
`.exclude(retail_price__isnull=True)` now at `:72`) and gives a product with no
row 0.0 attractiveness, that fabricated row would have entered the
attractiveness denominator at a very competitive price, taken share from every
rival and then sold nothing. **Rivals would have been penalised for another
team's inaction.** The second implementation guarded a null price with a
fail-closed engine precondition, which would have stalled an entire heat on one
team's omission, because there is no supported way for an instructor to set a
missing price — `InstructorTeamDecisionsView` is GET-only (`results_api.py:1097-1101`,
moved from the report's cited `:1061-1065`) and R13 made the Django admin
read-only for every competition model. The round must always resolve; the
precondition survives only as defence in depth for a skipped deadline.

Proof: `core.tests.test_price_band` — 45 tests, OK; freeze regression of 300
tests across eleven modules including `test_engine` and `test_calibration`,
175.780s, OK. The focused tests fail without the change: `price_band.py` does
not exist at `cbe2656` and `_apply_price_band` and `price_band_pct` each occur
0 times there.

**Not closed, and two reasons it is not.** The builder states plainly that no
gate is closed. **The student-visible half is unverified in a browser** —
`node_modules` was absent in that worktree after both rebases, so
`MarketingPage.js` and `ResultsPage.js` were never built, linted or clicked; the
legal-range hint, the blank alert, the "clear the price box" interaction and the
results-screen notice are proven by backend tests only. The new dispute-2 cases
have also not been walked through a live operator stack. A launch-checklist gate
for that browser pass was added 2026-09-12. **Rollback hazard, recorded because
it is easy to miss:** migration `0085` reverses cleanly, but the not-for-sale
rule means a resolved round can now legitimately *contain* null `retail_price`
rows, so a downgrade below `0085` must price or delete those rows first.

**One rules call the builder made rather than received, and flagged as such
(Q7):** a team that produces units for a product that then turns out not to be
for sale still pays COGS and carries the unsold units as inventory — only the
revenue is zero. The alternative, skipping the row in `revenue.py`, would
silently refund a production decision the team really made. That is a one-line
change in `revenue.py` if the owner rules otherwise.

**Both open questions above are now ruled, 2026-09-12 — update.** **R24**
settles the blank branch as implemented: an unpriced product with no price
history is **not for sale** that round, the team is told why on its own results
screen, and **the round always resolves**. The ruling records the deciding
constraint explicitly — `InstructorTeamDecisionsView` is read-only and R13 made
the admin read-only, so a refusing round could only have been cleared by
reopening it mid-competition. The lock-time refusal stays, because a team that
deliberately locks is at a moment it can act on. **R26 ratifies the builder's
Q7 call**: a product that cannot be sold is still paid for — the units are
charged and sit in inventory, because *"you built stock you then could not
sell… not pricing a product does not refund manufacturing"*. `revenue.py`
processing the row at a zero price rather than skipping it **is** the
implementation of that rule, so **no change is required to what was built**.
The Q7 note above therefore stands as the record of how the decision was
reached, not as an open exposure: it was a builder's call at the time, and it
is now a dated owner ruling that happens to agree with it.

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

### V2-042 — cohort caps are not enforced (P1) — repaired, pending closure

Eight students enrolled through the roster surface (all 201) and assigned to one
team through team management (200, `{'updated': 8, 'errors': []}`), leaving
**11 active members on a team whose `team_size_max` is 5**. Neither surface
consults `max_teams`, `team_size_min` or `team_size_max`. Confirms A6.

**Status update 2026-09-12 — repaired, pending closure.** Enforced at `f035884`
to the caps **R12** settled: 8 firms per game, 3–5 members per team, with the
authored `Section` defaults correct as authored and enforcement the thing that
was missing. `core/services/cohort_caps.py` (new) is the single place caps are
computed and `core/utils/cohort_messages.py` (new) carries the bilingual refusal
catalogue — a separate module so the contended `participant_messages.py` was not
touched. **No migration and no schema change**: the cohort tables are
`managed = False`.

**Three verify-before-wire results changed the implementation, and the third is
the one that makes this a real cap.** `CourseSection` does not exist — the model
is `Section`, and the builder did not invent the model the spec named. Team
membership has **two live representations**: `Enrollment.team_id` is
authoritative while `User.team_id` is written independently by `UserViewSet` and
never synced, so team assignment had **three** write surfaces. A cap on one of
them is not a cap, so occupancy is enforced as the **union** of both, and a
member present in both records is counted once.

Proof: `core.tests.test_cohort_caps` — 25 tests, OK. The falsification run is
what makes it evidence rather than assertion: with the six edited files reverted
to `cbe2656`, 8 failures and 4 errors of 24, and the baseline behaviours are the
finding verbatim — over-capacity enrolment returns **201, not 400**; the sixth
team member is **accepted**; the `assign-team` route returns **200** with the
second membership record uncapped; a game above the section cap draws no
refusal. Negative tests assert **state, not just status**: enrolment count
unchanged, `team_id` still `None`, zero games created, team still at five
members. Refusals name the cap in business language and leak no storage name
(`max_teams`, `team_size_max`, `Enrollment`, `section_id` all asserted absent),
and are localised for zh-CN.

**Reversible defaults the builder applied, each a rules question it did not
have answered:** the cap binds at **both** enrolment and assignment (enrolment
at `max_teams × team_size_max`, 40 by default); `team_size_min` **reports, never
refuses**, because a team is legitimately under-minimum while being filled;
teams already over cap are **grandfathered** and `link_users_to_game` stays
uncapped so an over-cap cohort can be repaired; `max_teams` counts active `Team`
rows excluding `withdrawn`. Ruling 4's 6–8 field size is enforced only on the
**upper** bound — the lower bound stays 2 because `Section` has no authored
`min_teams` and refusing a 4-team pilot game would be inventing a rule. A
narrowed `max_teams=6` binds immediately, so CRV2-11 narrowing the field needs
no code change.

**Not closed:** the `RoundControlCard.js` change is unproven — `node_modules`
was absent in that worktree, so it could not be built, linted or driven in a
browser. What was checked is that both locale files parse at exact EN/ZH key
parity (260/260 `instructor` keys) with all 8 new keys present in both. See
V2-080 for the rest of that card, and the browser-pass checklist gate added
2026-09-12.

### V2-043 — end_of_round retirement left its offered markets active (~~P2~~ **P1**) — repaired on `crv2-release-integration`

**Description corrected 2026-09-12, and the severity with it.** The original
text — "end_of_round retirement leaves the product on sale" — is inaccurate,
and the inaccuracy is what made it look cosmetic.

**What was actually true.** `{timing: 'end_of_round'}` set `TeamProduct.status`
to `retired` and left every `TeamProductMarket.is_active` row true; the
`immediate` branch deactivated them. But the product was **not** left on sale.
Retirement runs before scoring (`advance_round.py:624` before `:646`), and both
demand (`preference_engine.py:526-531`) and readiness
(`readiness_engine.py:22-34`) already filter on `status='active'`. **Demand
does not change.** What the stale rows changed is the **stored
`team_product_market` state**, which is inside the output hash
(`manifest_sections.py:448`) — so it is determinism-boundary state, not a
display defect.

**Severity raised to P1.** P2 is cosmetic, and the register's own rule is that
anything that can change a published result is never P2. This sits inside the
certified output envelope (V2-001), so a divergence here is a divergence in
what the manifest attests.

**Repaired**, with `core.tests.test_product_retirement.ProductRetirementTests`,
which fails without the change. **CRV2-09 must run a focused replay regression**
for this: it moves stored state that `output_sha256` covers.

**Related, and NOT repaired: see V2-070.** Because the two timings now have the
same market timing, they differ only in fire-sale recovery — 50% of unit cost
for `end_of_round` against 25% for `immediate` (`costs.py:870-871, 905-908`).
`immediate` is therefore a strictly worse choice with no compensating benefit.
That is a live balance defect awaiting a rules-owner ruling, and repairing
V2-043 is what exposed it.

### V2-044 — the write path accepts another team's platform; only the lock refuses it (P1) — implemented at `bfd5a26`, pending integrated Stage 3 closure

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

### V2-045 — platform auto-funding spends the same opening cash more than once (P1) — implemented at `1f68f5e`, pending integrated Stage 3 closure

Raised by the independent audit of the Stage 3A checkpoint at `a79c935`, before
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

**Repair, at runtime revision `1f68f5e`.**
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

**Disposition: implemented at `1f68f5e`, pending integrated Stage 3 closure.**
Not closed: Stage 3 closes with the integrated Stage 3/4 evidence, after
immutability lands.


### V2-046 — duplicate generation requests create and charge duplicate platforms (P1) — implemented at `5ccb9f8`, pending integrated Stage 3 closure

**Current status: implemented at `5ccb9f8`.** The repair took three passes; the
two superseded states below are dated historical audit notes, not current
guidance.

**The defect, as raised** at `6c1126a`. The V2-045 allocation refactor collected
every new request before creating any `TeamPlatform`, so the existing-platform
query saw the same initial state for two rows naming one generation. Both
entered the candidate set, both were funded, both were created. The supported
per-type write returned 200 and persisted two same-generation rows; with
$3,000,000 of cash and two authoritative $1,000,000 rows the production
lifecycle created two `in_development` platforms for one generation, gave both
`funded_round=1`, and the accounting output booked $2,000,000. Before the
refactor, creation happened inside the decision loop, so the second row
observed the first platform and was skipped.

**Repair, completed at `5ccb9f8`.** Three layers on the decision side, and a
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

- *At `1aaecac`:* refused duplicate rows within a submission, but never
  reconciled a carried draft against another non-retired platform of the same
  generation, so an upgrade residue from `1f68f5e` still promoted into a second
  live platform.
- *At `2195a0b`:* the allocator's defence built its live-generations set by
  excluding `unfunded_draft`, so two carried drafts for one generation were
  invisible to it and the de-duplication promoted the first — choosing a winner
  from inventory that should have been refused, and charging for it. Phase 1
  refused that state upstream, which is why the ordinary path looked correct;
  the audit found it by invoking the allocator directly.


### V2-047 — an already-held generation is accepted, persisted and silently ignored (P1) — implemented at `2195a0b`, pending integrated Stage 3 closure

Raised by the independent audit of the V2-046 repair at `b6e17f9`, before
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

**Repair, at runtime revision `2195a0b`.**

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
`1f68f5e` could create it, which is why the guard exists.

**Verification.** `HeldGenerationTests`, 9 tests: both write surfaces refusing
a held generation, including when the holding row is a draft; a refusal leaving
the previously accepted payload unchanged; the stored-row bypass refused at
Phase 1 with nothing created and no financial rows; the active-plus-draft and
two-draft residues refusing with every conflicting row named; the allocator
declining to promote a residue draft and booking zero; and the retired
positive control on the write surface. V2-045 and V2-046 controls unchanged.

**Disposition: implemented at `2195a0b`, pending integrated Stage 3 closure.**


### V2-030 — operator actions unreadable outside the Django admin (P1) — closed at `380df63`

**Found** during the CRV2-08 dispute walkthrough. The runbook's dispute-5
procedure tells an operator to "review operator events in timestamp order;
compare before/after, actor, reason and request ID". Every lifecycle action and
every refusal had been writing `OperatorAuditEvent` rows since CRV2-02, and no
product API or UI returned any of them. The only reader was
`core/admin.py:811`, a read-only Django admin registration behind a separate
maintenance login that competition instructors do not hold.

**Original failing evidence.** `evidence/post-close-disputes/dispute-answers.json`
at `01101a1`: 13 operator audit rows for the game, `answerable: false`, no route
returning any of them. The auditor ruled that the Django admin does not count as
the supported operator path.

**Repair** at `380df63`: read-only, ownership-scoped
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

### V2-031 — language preference never persisted (P2) — closed at `380df63`

**Found** in the CRV2-08 usability smoke. `LanguageSwitcher` built its URL as
`process.env.REACT_APP_API_URL || ''` while `api/client.js` uses `|| '/api'`.
In a default build the PUT went to `/user/preferences/` instead of
`/api/user/preferences/` and 404ed inside a silent `.catch(() => {})`: the
interface changed language and the choice was never stored, so it reverted at
the next sign-in or on another device.

**Original failing evidence.** `evidence/post-close-disputes/browser-walkthrough.json`
at `01101a1`: the shipped URL returned HTTP 404 and the identical call under
`/api` returned HTTP 200, in the same browser session.

**Repair** at `380df63`: the same default as the API client. **Verification:**
re-proven at HTTP 200 in `repeat-after-repair.json`. **Disposition: closed.**

### V2-032 — game ownership not enforced for instructor routes (P0) — closed at `4540163`

**Severity P0.** An instructor with no connection to a cohort could read that
cohort's raw submitted decisions, their payload hashes, the actor and the
request id — the evidence CRV2-08 certifies as the answer to disputes 1 and 2.
That is a competitive-confidentiality failure and is launch-blocking.

**Reproduction** at `7f6d813`,
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

**Disposition: closed at `4540163`, accepted in audit.**

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

**Amended 2026-09-12 — the entry above was stale as written, and the Stage 6
builder was right to say so.** It records V2-033 as "withdrawn, not a defect"
and states that "no code change alters that", while the Stage 6 handoff states
the repair is there. Both are now true, under the narrow reading Stage 6
implemented, and the wording is corrected here rather than left to contradict
itself. (The Stage 6 inventory cites this entry as
`V2_FINDINGS_REGISTER.md:909`; on this branch it is at `:946`.)

**What is unchanged:** `instructor_can_access_game` itself. A course whose
`instructor_id` is NULL is still a shared pilot cohort visible to any
instructor, the helper has no new branch, and
`test_an_unowned_course_is_readable_by_any_instructor_on_two_routes` still
passes. Narrowing the helper would break the live pilot, which the CRV2-08
auditor ruled must not happen.

**What is new:** a **competition precondition on the game**, added at `f035884`
inside `operator_action` (`core/services/lifecycle.py`) — one choke point
covering all 11 lifecycle actions. A game flagged as a competition whose course
has no instructor of record is refused **400** with
`competition_course_unowned` on every lifecycle action (close, reopen, process,
advance, deadline, extend, inject), the round **stays open**, and the refusal
says what to do next. So the operational implication this entry already carried
— that a prize-competition course must have an instructor owner assigned before
launch — is now **enforced** for competition games rather than left to
procedure, while pilot behaviour is preserved exactly.

Proof: `test_cohort_caps.CompetitionOwnershipTests` — a competition game on an
unowned course is refused and the round stays open; the refusal says what to do
next; the refusal **is recorded**; a pilot game on an unowned course still
closes normally; competition mode defaults off. The refusal record is pinned by
`test_the_refusal_is_recorded`, asserting an `OperatorAuditEvent` with
`action='close_round'`, `outcome='rejected'`,
`conflict.code == 'competition_course_unowned'`, a `request_id` **equal to the
one returned to the operator**, `round_id is None` and `after == {}`. Two
details make that work and both were deliberate: the precondition is raised
**after** `holder.game = game`, because `_record_rejection` runs only under
`if holder.game is not None` and raising one line earlier would have produced
**no record at all** — the exact V2-034 failure shape; and
`OperatorAuditEvent.round` is `null=True, blank=True`
(`core/models/competition_audit.py:65`, verified this revision), so a refusal
raised before the round is ever read still produces a row.

**The protection is silent when unarmed, and that is the load-bearing caveat.**
It keys off `SimulationInstance.settings['is_competition']` — chosen because it
needs no migration, is per-heat and is reversible by deleting a key. **If nobody
sets it, the refusal never fires and the protection is absent with no error, no
banner and no log line to notice.** A heat that is not flagged behaves exactly
like a pilot game, so its unowned course stays readable by every instructor on
the deployment. That is a launch step, not tribal knowledge: the checklist entry
and the per-heat verification snippet are recorded against it.

**Status: repaired, pending closure** — and the closure is conditional on the
flag being set and verified for every heat, which is an operational act this
repository cannot evidence.

### V2-034 — refused non-owner writes were not recorded (P1) — closed at this revision

**Registered before repair.** Every one of the 37 mutation routes exercised as
an unrelated instructor was refused with 403 and changed nothing, and none of
those refusals was recorded: no operator audit row, no read-log row. Original
evidence: `refused_writes_not_recorded_anywhere: 37` in
`ownership-scan-after-repair.json` at `4540163`.

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
management command and no serializer at `8b52c49`; the 37 rows produced by the
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
had passed on an unrelated `SnapshotError`. **Audited as blocking** at `adf20f9`
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

**Reproduction at `adf20f9`** (historical):
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

## V2-010 and V2-011 — closed at `0c2e122` (option A adopted)

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

**RNG-impact gate.** The Stage 2 screen was recorded at `5face63`, before this
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
| V2-023 | Balance / price response | **P1 closed by rules change** | GSP-CRV2-06 (raised, confirmed, repaired, reworked) | Two mechanisms, one finding. A team alone in its positioning group had no price response at all. Repairing that with an absolute reference price left a second: `price_competitiveness` is a bounded feature that reaches zero at 1.5x the reference -- \$630 -- and clamps, so above that point demand stopped responding while revenue kept multiplying by an unbounded `retail_price`. Both are closed: an absolute reference price, plus a scenario elasticity of 1.5 applied to adoption above the reference. Revenue and net income now peak at the reference and fall monotonically above it. | `v2-023-gate.json` and `characterisation.json`, both re-run at `786e8f2` across \$50 to \$200,000. | **Closed.** Both mechanisms measured above and below the clamp. |

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

Both measured by same-game transactional counterfactual at `5821bc9`: one team,
one frozen checkpoint, one decision changed, everything rolled back. The
baseline was resolved twice and the delta was exactly zero on every metric, so
these differences are the rule and not noise. Evidence:
`evidence/adversarial-balance/rule-probes.json`.

| ID | Area | Sev | Owner | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|---|
| V2-021 | Scoring / strategic capability | **P1** | Rules owner (raised by GSP-CRV2-06) | `_strategic_capability_component` scores R&D as `rd_spend / rd_budget`, clamped to 1, and capability carries 0.25 of the performance index. The denominator is the team's *own declared budget*, so the ratio measures self-consistency rather than investment. Declaring **$1** and spending **$1** scores 1.00 where a $100,000 programme against a $2,000,000 budget scores 0.05. Measured: index **56.54 → 58.45 (+1.91)**, composite **0.5772 → 0.6724 (+0.0952)**, while spending **$99,999 less** — cheaper *and* higher-scoring, and independent of what any opponent does. | `rule-probes.json` → `capability_ratio`. Single round; the multi-round trade-off is unmeasured — see the uncertainty note below. | **Closed** at `e57426c` under an adopted disposition — see below |
| V2-022 | Scoring / anti-exploit guard | **P1** | Rules owner (raised by GSP-CRV2-06) | `_is_voluntarily_commercially_inactive` caps the composite at 0.25 only when *every* marketing row has production, promotion, distribution and sales staffing at or below zero. It tests the **decisions**, not the outcome. Setting `production_volume = 1` on one row defeats it: composite **0.2500 → 0.4123 (+0.1623)**, index **50.00 → 53.25 (+3.25)** — for **$181.86**. Critically, **`total_revenue` is `0.00` in both cases**: the team sold nothing. The guard is escaped by declaring an intention to produce, not by competing. | `rule-probes.json` → `one_unit_bypass`. The hypothesis was "sell one unit"; the measurement shows no sale is needed. | **Closed** at `e57426c` under an adopted disposition — see below |

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

**The original exploit probes, re-run against the repaired rules at `e57426c`:**

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
| V2-020 | Engine / equity issuance | **P0** | GSP-CRV2-06 (raised) | `generate_financial_statements` prices newly issued shares with `share_price_est = total_equity / shares_outstanding` at `financials.py:212`, but `total_equity` is not assigned until line 262 — fifty lines later, inside the same per-team loop. For the **first** team in the loop that raises equity this is `UnboundLocalError`, and because the call sits inside `_run_phase_1`, **the whole round fails to resolve for every team**. For any **later** team it silently holds the *previous team's* closing equity, so one company's shares are priced off another company's balance sheet and the dilution written to the leaderboard is wrong. Raising equity is an ordinary legal decision exposed by `DecisionFinancing.new_equity`. | Found by Stage 2 screening: setting `financing.new_equity` to its funded maximum crashed resolution. Nothing in the repository exercises `new_equity > 0` — every test and seed command sets it to `0`, which is why it survived. Inherited from the baseline snapshot `111d541`, so it predates globalstrat+. | **Closed** at `4c27c3e` under an adopted rules disposition — see the closure entry below |

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

**Verification at `4c27c3e`** (`core/tests/test_equity_issuance.py`, 7 tests):

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
| V2-019 | API uniformity / determinism | ~~P1~~ **Withdrawn — filed in error** | GSP-CRV2-06 | Filed as "the per-type R&D endpoint accepts a duplicate platform+feature payload the whole-submission endpoint rejects". **That was measured on the serializers, not the endpoints, and described as endpoint behaviour.** `DecisionPartialUpdateView` has called `validate_rd_investment_targets` on the assembled list since `2592f93`, so both endpoints always refused the duplicate. Contract tests written against the real API pass unchanged on the pre-repair code. What was real is narrower and not an exploit: the rule lived in two places — the submission serializer and the view — so any third caller using `DecisionRDInvestmentSerializer(many=True)` directly would have missed it. | `core/tests/test_decision_limits.DuplicateRdRowApiTests`: both paths refuse for the intended reason, the distinct-feature control is accepted, and neither writes a row. These pass before and after the repair. | **Withdrawn.** The duplication is repaired anyway: the rule now lives in `DecisionRDInvestmentListSerializer` and runs wherever the rows arrive together |

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
| V2-017 | Operator boundary / route inventory | **P1** | GSP-CRV2-02 boundary (raised by GSP-CRV2-04) | The route inventory that certified "0 unguarded mutating routes" can only inspect routes whose callback exposes a view class. Django's admin add/change/delete views are function-based, so **216 admin write routes are skipped entirely** — including `Game`, `Round`, `Team`, `DecisionSubmission`, `ActiveModifier` and — **in error** — `SCEventInstance`. **Correction, 2026-09-12:** `SCEventInstance` was never registered in the Django admin at all, so it never had an admin write route; enumerating `admin.site._registry` finds it absent and `git log -S` on `admin.py` finds no commit that ever registered it. The original text named it without checking. A staff user can move round state through `/admin/` with no lifecycle lock and no `OperatorAuditEvent`. The `<path:object_id>/` routes that *do* appear resolve to `RedirectView` and are reported `lifecycle_mutating: false`, which is how a whole write surface came to be counted as harmless. | `_walk(get_resolver())` yields 778 routes; 371 have no view class and are skipped by `mutating_routes()`, 216 of them admin add/change/delete. `core/services/route_inventory.json` lists `admin/core/round/<path:object_id>/` as `RedirectView`, `lifecycle_mutating: false`, and lists no `.../change/` route at all. | **Ruled and repaired — R13 (competition owner, 2026-09-11).** The Django admin is a read-only evidence surface for every competition-domain model; lifecycle services and the instructor UI are the only supported write paths. Implemented on `crv2-release-integration`: 65 competition admins moved to `CompetitionReadOnlyAdmin`, joining the 5 already read-only through `AppendOnlyAdmin` — 70 of 70 `core` admins read-only, no admin actions exposed, inlines unsaveable. Losing admin editing of scenario and team-membership rows is accepted by the ruling, not a regression. `auth.User`/`auth.Group` stay writable as Django account administration outside the competition boundary. **The route-inventory blind spot is NOT closed**: `route_inventory.py:129-136` still skips any route with no view class, so the inventory still cannot see the admin — it is now harmless rather than visible. That remainder stays open. **Confirmed still open 2026-09-12, with the citation corrected.** The legacy-removal handoff repaired a *different* defect in the same module (marker resolution — see **V2-079**) and reports explicitly that it does **not** narrow this gap. Verified on this branch: the skip is now at `route_inventory.py:194-202`, where `mutating_routes()` reads `view_class = getattr(callback, 'cls', None) or getattr(callback, 'view_class', None)` and does `if view_class is None: continue`. The line numbers moved with the detector rewrite at `d9cbd43`; the behaviour did not. Proof: `core.tests.test_audit_integrity.CompetitionAdminBoundaryTests`. See `OWNER_RULINGS_2026-09-11.md`. |

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
| V2-010 | RNG cohort key | **P1** | GSP-CRV2-06 | Two different cohort keys are in use. `core/engine/rng.py` seeds on `game.section_id or game.id`; `sc_engine._seed()` and `compliance_engine` seed on `game.id`. Two sections of one class running the same scenario therefore receive the same event stream but different supply-chain and compliance streams. Escalates to **P0** if parallel sections are ever scored against one another, because the disruption exposure they face would differ by construction. | Compare `core/engine/rng.py` with `core/engine/sc_engine.py:_seed` and `core/engine/compliance_engine.py`. | **Closed** at `0c2e122` — option A adopted, see below |
| V2-011 | Shared RNG stream | **P1** | Competition-rules owner (via GSP-CRV2-09) | The supply-chain and compliance passes consume a single `random.Random` across all teams, so draw *n* belongs to whichever (team, regime, market) triple reaches the roll *n*-th. Iteration order is now explicit and replay is exact, but adding or withdrawing a team shifts every later team's draw — one team's presence changes another team's outcome. | `core/engine/compliance_engine.py:enforce_compliance`; `core/engine/sc_engine.py:run_sc_state`. | **Closed** at `0c2e122` — option A adopted, see below |
| V2-012 | Iteration order | **P0** | GSP-CRV2-01 (closed) | The first ordering sweep inspected only inline loop iterators, so `rows = X.objects.filter(...)` followed by `for row in rows` was never checked. `_score_entry_mode_risk` iterated an unordered `TeamMarketPresence` scan; a restored database returned two markets in the opposite order, changing `RoundResultCoherence.breakdown` and the competitive hash. A published round did not reproduce. | Cross-environment replay of game 34 round 1: three same-host replays agreed with each other and disagreed with the original resolution; the section diff named `coherence` and the reordered `entry_mode_risk` list. | **Repaired** — 75 further sites ordered; the AST guard now resolves a loop over a local name back to its assignment. |
| V2-013 | Manifest envelope | **P1** | GSP-CRV2-01 (closed) | The output snapshot held only the competitive sections, so foreign keys pointing at configuration it did not contain (`Team.firm_starter_profile`, `Game.scenario`, `Team.home_market`) fell back to `core.Scenario#surrogate:7`. The competitive hash carried raw sequence values, defeating the surrogate-independence requirement. Never broke a replay, because a restored database reproduces the ids. | Inspect any pre-repair `output_manifest` for `#surrogate:`. | **Repaired** — both envelopes now pull in whatever identity requires; a test forbids `#surrogate:` in either. |
| V2-014 | Narrative envelope | **P1** | GSP-CRV2-01 (closed) | A narrative section's prose is separated into `narrative_rows` by the snapshot, and the narrative envelope was built from `rows` alone. `narrative_sha256` hashed briefing ids and round numbers, not a word of text — so a replay against a deliberately different model produced an identical narrative hash and the "prose differs, result does not" claim was unverifiable. | Two runs of game 36 round 1 under different endpoints reported the same `narrative_sha256`. | **Repaired** — the envelope carries `prose` and `prose_digests`; tests require that changing a briefing changes the narrative hash and leaves the competitive hash alone. |

| V2-015 | Narrative / manifest reconciliation | **P1** | GSP-CRV2-03 | Phase 2 writes into rows and fields that `output_sha256` covers, after that hash has been taken: `RoundResultCoherence.rag_score/blended_score/breakdown`, `SCEventInstance.resolution_data['narrative']`, and newly created `InstructorAlert` coaching rows. The hash never moves — it is computed inside the Phase-1 transaction — so every replay matches; what diverges is the *stored database* from the manifest that certified it, which no replay compares. | Resolve a round with an API key configured, wait for Phase 2, then rebuild the output manifest and compare with the stored `output_sha256`. | **Repaired in GSP-CRV2-03** — see closure entry. |
| V2-016 | LLM reaches a graded number | **P1** | GSP-CRV2-03 (closed) | `RoundResultCoherence.blended_score` is read by `core/services/grading.py`. With an LLM reachable, coherence was `0.6·formula + 0.4·RAG`; without one, the formula score stood. Two identical competitions therefore graded differently depending on an external service's availability. Rank was unaffected: neither `performance.py` nor `leaderboard.py` reads coherence. | `grep blended_score core/services/grading.py`; compare a round resolved with and without `DASHSCOPE_API_KEY`. | **Closed** at `4bf93e9` — see closure entry below |

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

### V2-016 — LLM reaches a graded number (P1) — closed at `4bf93e9`

**Adopted rule: published coherence and the grades derived from it are the
deterministic formula score. Retrieval is instructor commentary and nothing
else.**

The first GSP-CRV2-03 submission made the blend configurable and defaulted it
off. The audit rejected that: a setting a supported deployment can flip is not
a safe competition configuration, and default-off left the defect one
environment variable away. The rework removed the Phase-2 write path outright.

At `4bf93e9`:

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

## V2-055 — equal-fit products lacked a deterministic selection rule (P1) — closed by `0644cf5`

**Raised by the GSP-CRV2-11 Stage 2 audit.** The audit rework recorded this
finding before the bounded runtime repair; this register entry follows that
audit record. `calculate_fit_scores()` keeps the first product with a strictly
greater fit, while `_get_team_products_in_market()` had returned an unordered
queryset. An equal-fit product could therefore change the product whose
production capacity limited adoption without a different team decision.

`cb7e6f9` retains a lower-ID tie-break for compatibility presentation, but the
repair is `0644cf5`: every eligible product now has its own fit,
attractiveness, share, unconstrained demand, capacity, sales, and lost-demand
row. Firm-level adoption and financials are exact product-result aggregates.
The focused contract proves two products can both receive demand, stockout is
product-local, zero demand is distinguishable from a stockout, allocation is
insertion-order invariant, and the firm/AI/Bass accounting identities hold.
`836cf2e` keeps cent-rounded product rows from exceeding their own capacity.

V2-055 is closed. CRV2-11 Stage 2 is complete: the only starter-parity rule is
round-zero base-index and shared-rank equality, which bootstrap provides. The
repaired competent-field evidence is recorded in
`evidence/calibration/STAGE2_PARITY_MEASUREMENTS.md`; later-round index spreads
are outcomes, not a calibration gate.

**This closure is unratified — see V2-073.** The acceptance criterion it
certifies against was rewritten, in the same snapshot that closed it, by the
builder who closed it: the requirement that no archetype hold "a material
unearned edge", and the instruction to adjust starter profiles until that held,
were deleted from the handoff. The rule now stated may well be the right one and
the measurement behind it is real, but a builder editing their own gate and then
certifying against the remainder is not a closure. CRV2-09 must not treat
Stage 2 as closed until the rules owner records that ruling with a date and
their own name.

## V2-056 through V2-073 — raised by the audit of snapshot `cbe2656` (2026-09-11/12)

**Chronology, stated plainly.** Every finding in this section was **repaired
before it was registered**, or found during the audit of an emergency snapshot
that had already repaired it — the opposite of the standing rule. The snapshot
`cbe2656` ("WIP: snapshot competition readiness work") committed 53 files of
mixed, unreviewed work by a previous builder; the audit of that snapshot found
about fifteen repairs and defects with no register entry at all. Registration
did not precede implementation and these entries do not imply it did. They are
recorded here **before** the snapshot's content is re-landed as reviewed,
focused commits on `crv2-release-integration`, so that the reviewed branch
begins from a complete record.

**ID assignment order — stable and documented.** The range V2-056 to V2-061 was
unused anywhere in the repository.

- **V2-056–V2-061** are the findings that had no identifier at all, in the
  order the audit lists them: the lock crash, then the CRV2-13 known-list items
  D2, D4, D5 and D6, then the CRV2-12 evidence-only finding F-PL-01.
- **V2-062 and V2-063** keep the numbers their rework documents already gave
  them. They were never rows in this register; that is the defect being fixed.
- **V2-064–V2-070** are the audit's own defects **AUD-2 through AUD-8**, in
  ascending AUD order. AUD-1 is V2-056 above.
- **V2-071** is the verification-baseline finding (the suite's pre-existing
  red tests).
- **V2-072 and V2-073** are the two governance findings — an unregistered P0
  from the V2-048 operations review, and a handoff gate closed on a
  builder-authored edit.

Severities use the register's legend: **P0 blocks; P1 degrades; P2 cosmetic** —
and anything that can change a published result is never P2.

| ID | Area | Sev | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|
| V2-056 | Decision lock / student API | **P1** | Every call to the student lock endpoint for a team that has a budget allocation raised `NameError: name 'total_budget' is not defined` and returned **500**. `views/decisions.py:851` used `total_budget` in `_full_validate`'s projected-ending-cash check after `96a9aae` (2026-09-01) deleted the binding. Locking was therefore impossible for any team past the budget step, for ten days, unnoticed because no test locked successfully. | `POST /api/games/<id>/teams/<id>/decisions/round/<n>/lock/` with a `DecisionBudgetAllocation` present, on `a521f7a`: `NameError` → 500. Audit run 3 reproduces it; the only test that exercises `/lock/` is the new D2 test. | **Repaired** as part of the V2-057 (D2) commit, which replaces the dangling name with `assessment['committed_total']`. Proof: `test_rd_costs.AuthoritativePriceTests.test_budget_vs_cash_rule_agrees_on_lock_summary_and_finance_context`, which fails with `NameError` without the change. **P0/P1 is unresolved and belongs to the rules owner:** it is P1 if closing a round still resolves unlocked drafts, P0 if locking is a required competition action. It is recorded at P1 pending that answer, and the answer also decides whether any round already played between `96a9aae` and `a521f7a` was affected. |
| V2-057 | Budget vs cash rule / participant surfaces | **P1** | CRV2-13 **D2**. V2-038 consolidated the budget-versus-cash rule into `rd_costs.budget_assessment`, but three participant surfaces had not finished delegating to it: the lock validator still referred to its deleted `total_budget` local (V2-056), and Decision Summary and Finance context re-added only the three visible budget lines, omitting `research_budget` and platform development from their cash presentation. A participant-facing contradiction: an amount can be refused at lock and then disappear from the Summary or Finance cash figure. | `evidence/bug-sweep/CRV2-13_D2_D6_FOLLOWUP.md`. $900 cash against an otherwise empty $1,000 submission ($100/$200/$300/$400 across the four budget lines). | **Repaired.** Lock and Finance projected cash use `committed_total`; Summary and Finance publish `total_allocated`, `research_allocated`, `platform_development_committed` and `committed_total` separately; unallocated is cash less `committed_total`. `research_budget` remains a legacy model field — this gives it **no new in-round charge and changes no competition rule**; it makes existing cash checks report the already-enforced amount consistently. Proof: `AuthoritativePriceTests.test_budget_vs_cash_rule_agrees_on_lock_summary_and_finance_context`, exercising all three real surfaces. **Open question for the rules owner:** whether `research_budget` counting toward committed spend is a live rule at all — the API cannot write it and the engine never charges it, and the lock code's own comment says research queries are free. **Status update 2026-09-12 — the open question is answered by R23, and the ground under it has moved.** R23 rules that **research was never meant to be free**: reports are a paid mechanic and their being free was an oversight, not a design decision. So the answer to "is `research_budget` a live rule at all" is that research genuinely costs money — but **not through this field**. The implementation merged at `d2059e4` puts purchases in their own table (`DecisionResearchPurchase`) as a new committed line in `committed_outlay`, in exactly the position `platform_development` occupies, and deliberately **not** in `research_budget`, which stays a **declaration** like `marketing_budget` and `strategy_budget` — it feeds coherence scoring and is not a second cash gate (A5/R14: budgets declare, decisions spend). The residual question is therefore now cleanly separable and materially smaller than when it was raised: whether the dormant `research_budget` bucket should count toward committed spend **at all**, given that the API still cannot write it and the engine still never charges it. That remains open with the rules owner. |
| V2-058 | Engine / organisational speed modifier | **P1** | CRV2-13 **D4**. `rd_processing._development_rounds_for` wrapped the organisational-structure speed lookup in `except Exception: pass`. A persistence or query failure therefore silently changed the rule in force — the platform development clock, which R5/R6 make the whole competitive content of a platform decision — instead of failing. Missing organisation state is a legitimate no-modifier case and must keep its normal result; a broken lookup must not be indistinguishable from it. | `evidence/bug-sweep/CRV2-13_KNOWN_LIST_D1_D3_D4_D5.md`. Patch `TeamOrganizationalStructure.objects.filter` to raise and resolve a round: on `a521f7a` the error is swallowed and the round resolves with the wrong clock. | **Repaired** — the lookup is now fail-closed and aborts resolution. `decision_speed_modifier` is non-null with default 1.0 (migration `0031:32`), so this adds no new crash path. Proof: `test_platform_lifecycle.PlatformTimingTests.test_org_structure_lookup_errors_are_not_silently_ignored` (fails without the change: "RuntimeError not raised") plus the positive control `test_active_org_structure_applies_its_development_speed_modifier`, which passes on `a521f7a` too and is therefore a control. |
| V2-059 | Engine / readability | P2 | CRV2-13 **D5**. `preference_engine.calculate_fit_scores` named its `context.segments` loop variable for something other than what it holds, against the dictionary contract (`segment_id`). | Read `preference_engine.py:51` against `core.engine.utils` segment-state construction. | **Repaired** — rename only. The loop body never read the old name, so behaviour cannot change and no test can distinguish the two; this is recorded as a readability repair, not a behavioural one. Genuinely P2: it cannot change a published result. |
| V2-060 | Calibration / round-zero adoption provenance | P2 | CRV2-13 **D6**. `bootstrap.py:175` multiplies the round-zero Bass increment by an unauthored constant 10, introduced in the baseline snapshot (`111d541`, 2026-04-17) with the sole comment "Scale for meaningful numbers". No scenario YAML authors a round-zero duration, an initial cumulative-adoption target, or an adoption-scale parameter, and nothing connects the resulting per-segment adoption row to the authored starter volumes. | Four 10-round, 8-team replays of Consumer Electronics 2026 (factor 10 vs factor 1; the pair repeated with pinned team names; a factor-10 control with different names). Artefacts under `scratchpad/d6/` — `comparison_pinned_baseline_f10_vs_pinned_variant_f1.json` first. | **Open — implementation belongs to GSP-CRV2-11; the rule is settled by R11.** **The factor is display-only, measured, not argued:** zero differing rows in rounds 1–10 across all ten result tables; round-1 `cumulative_adopters` equals round-1 `new_adopters`, so round-0 adopters never carry forward (`bass_engine.py:313-345` returns 0.0 for `prev_round < 1`); the only differences are the 40 round-0 adoption rows' `new_adopters`/`cumulative_adopters`, exactly ×10. **This corrects `CRV2-13_D2_D6_FOLLOWUP.md`**, which claims the multiplier "changes the round-one Bass cumulative state and therefore later competitive demand" — that claim is wrong. **Note for any replay comparison:** `output_sha256` differs in every round 0–10 across a factor change, because the adoption manifest section spans all rounds and so carries round 0 inside every round's hash; outcomes are nonetheless identical. **R11 (2026-09-11):** the `* 10` is retired and round-0 adopters are derived from the authored starter sales, apportioned across home-market segments, with no unauthored constant. Recorded at P2 because it is proven display-only; it stays open because the authored derivation is not built. **Status update 2026-09-12 — R11 implemented; repaired, pending closure.** Built at `2f012c2`. The `* 10` is **deleted and no constant replaces it** — not 10, not 1, not a new scale key; verified on this branch, where `bootstrap.py` retains the retired line only in its module docstring at `:42` as the rule's history, and the derivation is `_apportion_starter_units` at `:103`, called at `:304`. Round-0 adopters are now the authored `FirmStarterProduct.unit_volume` apportioned across the home market's customer segments in proportion to `bass_p × population × preference fit`, settled to the cent: each segment takes `units × weight / Σweight` rounded **down**, and the leftover cents are handed out one at a time, largest discarded fraction first, ties broken by the caller's segment order — so two runs are identical and the allocations sum to the authored units **exactly** rather than nearly, which matters because this is inside the CRV2-01 determinism boundary. Segments whose `min_generation_required` exceeds the generation the team starts on are excluded and keep a zero baseline row, exactly as `preference_engine.py:70-78` excludes them from round 1 onward. Where a scenario authors starting sales but no reachable segment, `bootstrap_round_zero` **raises** rather than defaulting, naming the team, profile, market and unit count. **The reconciliation is the point of the ruling and it now holds:** round-0 adopters equal round-0 units sold for all three shipped scenarios, loaded through the real `load_scenario` and `initialize_game`. How far apart they were before: consumer electronics 208,650 against 65,000 (**3.21×**), clean energy 2,725 against 8,000 (**0.34×**), media 201,000 against 9,000 (**22.3×**) — mis-scaled in **different directions in different scenarios**, which is the concrete proof that no single constant could ever have reconciled all three. Proof: `core.tests.test_round_zero_adoption`, 9 test methods; against the pre-change engine, 11 failures across 8 of the 9, the one survivor being the pinned display-oddity assertion, which is deliberately a statement about unchanged behaviour. Rounds 1–10 are unchanged, re-measured by a fresh two-arm replay rather than inherited: 0 differing rows in all ten result tables, with the probe recording the round-zero rule it actually ran in each arm rather than asserting it. **Two things this did not fix, both recorded rather than buried:** the round-0 `team_share_pct` column changed meaning — now **V2-084**; and round-0 `cumulative_adopters` still does not carry into round 1 (`bass_engine._get_total_cumulative` / `_get_team_cumulative` return 0.0 for `prev_round < 1`, verified this revision at `:323-352`, correcting this entry's earlier citation of `:313-345`), so a student still sees Cumulative **fall** between round 0 and round 1 whatever the round-0 figure is. That anomaly is unchanged in direction, smaller now for consumer electronics and media and larger for clean energy, and is pinned by `test_round_zero_cumulative_equals_new_adopters` so any future change to it is deliberate; it belongs to GSP-CRV2-12 as a presentation matter. |
| V2-061 | Player-facing language / decision refusals | **P1** | **F-PL-01** (CRV2-12), previously recorded only in evidence. `serializers/decisions.py` and `views/decisions.py` returned English-only validation and refusal strings on the main draft save, per-decision PATCH and lock paths, several of them exposing storage identifiers (`channel_digital_pct`, `new_debt`, `allocation_amount`). The partial-decision endpoint also built serializers with no request context, so even catalogue-backed serializers could not honour `Accept-Language`. A Simplified-Chinese participant received English or technical text at exactly the point a decision must be corrected. | `evidence/player-language/CRV2-12_DECISION_PATH_FINDINGS.md`, recorded before repair on 2026-09-11. | **Repaired** — refusals route through the bilingual catalogue `core/utils/participant_messages.py`; `context={'request': request}` is supplied on the decision paths. Every serializer and view refusal keeps the same condition, threshold and control flow: **wording only**, verified hunk by hunk. No engine code is touched. Proof: `test_participant_messages`, plus the wording assertions in `test_decision_limits`, `test_platform_lifecycle` and `test_rd_costs`. Repair boundary is the participant-facing decision surfaces only; it does not claim the Stage 1 inventory is complete. See V2-067 and V2-069 for what it cost and what it left. |
| V2-062 | Load evidence / harness admissibility | **P1** | **Registered late — the row never existed.** The CRV2-07 combined-resolution load gate had no admissible harness: the driver sampled a **named production host and account** rather than the stack under test, so it measured a different database than the one being loaded, and the disposable-stack helper could not create a database whose label contained the human-facing profile hyphen. | `rework/GSP-CRV2-07_COMBINED_RESOLUTION_FINDING.md`; `evidence/load-failure/COMBINED_RESOLUTION_INVENTORY.md`. | **Repaired** — `driver.py` samples the current disposable stack through `_psql()`, taking host, port, user and a generated credential from the environment; `stack.py` sanitises the database identifier, reports the real creation error, uses a temporary backup root, and names the run honestly as disposable rather than presenting a dirty tree as a frozen release candidate. Run through `backend/scripts/run-load-postgres`, which generates its password in memory and never reads the production systemd environment file. **The same production-host pattern survived in a second file — see V2-065.** |
| V2-063 | Concurrency / decision write path | **P1** | **Registered late — the row never existed.** A synchronous Phase-1 resolution holds the exclusive game lock for several seconds. Student decision writes queued behind it in sync Gunicorn workers, so a burst of late submissions could consume every worker and make otherwise lock-free refreshes appear stalled. | `rework/GSP-CRV2-07_V2-063_WORKER_QUEUE_FINDING.md`. | **Repaired** — `try_lock_game_for_decision_write` takes the shared boundary with `pg_try_advisory_xact_lock_shared`; a failure returns an explained **409** instead of waiting. Permission checks still run **before** the 409 (`_lifecycle_busy_response` runs DRF `initialize_request` + `initial()`, so anonymous and other-team callers still get 401/403), the success path keeps the shared-game → team → handler lock order, and a refused write provably executes no handler and writes no audit or decision row. Non-PostgreSQL backends keep the historical no-op. **Its scope is a live open question — see V2-064** — and its refusal leaves no evidence — **see V2-066**. |
| V2-064 | Concurrency / operator actions vs student writes | **P1** | **AUD-2.** The V2-063 try-lock fails whenever **any** exclusive operator action holds the game lock, not only Phase-1 resolution: `set_deadline`, `extend_deadline`, `reopen_round`, `inject_event`, `inject_sc_event`, `team_participation`, team config and `advance_round` (`round_control.py:179-445`, `results_api.py:704-831`, `instructor_sc.py:226`, `team_control.py:39`, `team_config.py:79`). Before the change a student write waited milliseconds and succeeded; now it receives a 409 saying "This round is being processed. Refresh shortly to see the results", which is **false** for a deadline change. The frontend autosave (`DecisionContext.js:49-61`) catches the error and only logs it, and re-arms only when the draft changes, so there is **no retry**; `GameStatusBar.js:58-60` keeps showing the last successful "Saved" time. **A student editing while an instructor extends the deadline can therefore lose that edit without being told, which can change a published result.** | Hold an exclusive operator lock on one connection and `PATCH .../decisions/round/<n>/budget/` as a team member on another: 409 in ~6 ms. Audit probe log `wip-audit/run4.log`. | **Open — awaiting rules-owner ruling.** The ruling decides whether the fast-fail applies only during Phase-1 resolution or to every exclusive operator action. **If every action, two things must follow:** the message must stop claiming the round is being processed, and the frontend must surface or retry the 409 rather than swallowing it. Not repaired here: changing either the lock scope or the frontend is a rules and UX decision, and instructor screens are outside this branch's scope. Also unmeasured, and following from PostgreSQL's lock-queue rule: the try-lock should additionally fail while an exclusive request is merely *waiting* in the queue. |
| V2-065 | Security / evidence harness | **P1** | **AUD-3.** `evidence/load-failure/harness/failure_walkthrough_body.py:321-322` hard-coded the **production database host** `192.168.50.38` with role `donwh`, and ran `pg_terminate_backend` against it. V2-062 repaired exactly this pattern in `driver.py` and **missed this file**. The failure drill therefore aimed a connection-killing statement at production from a development harness. | Read `failure_walkthrough_body.py:315-330` at `cbe2656`; compare with the repaired `driver.py::_psql`. Listed in the V2-048 sanitized inventory as `failure_walkthrough_body.py:321`. | **Repaired** on `crv2-release-integration`: the killer takes its connection from the disposable stack's environment (`DB_HOST`/`DB_PORT`/`DB_USER` and the generated credential) exactly as `driver.py` does, targeting the disposable container's own database and no other. No production host, no named role, and `pg_terminate_backend` can reach nothing but the disposable stack. |
| V2-066 | Audit / refusal evidence | P2 | **AUD-4.** A V2-063 **409 refusal leaves no evidence at all**: no `DecisionAuditEvent`, no log line, and no request ID in the response header or body. Operator rejections (`lifecycle.py::_record_rejection`) and middleware refusals (`middleware.py:352-387`) are both recorded; this refusal is not. A consequence for CRV2-07: its count of 32 busy 409s is client-side only and has no server-side corroboration. | Refuse a write by holding the lock, then query `DecisionAuditEvent` for the team/round: zero rows, and nothing in the application log. | **Open.** Recorded P2 because it degrades dispute evidence rather than changing a result, and because no refused write mutates anything. **It is a rules-owner question whether that is acceptable:** if the dispute record must be able to prove a student's write was refused — which V2-036 established as the standard for operator refusals — this is P1 and needs an audit row. Not repaired here: adding an audit write to the refusal path is a change to the audited boundary. |
| V2-067 | Test suite integrity | P2 | **AUD-5.** The CRV2-12 wording change turned **7 passing tests red**: `test_platform_freeze.FreezeWriteSurfaceTests` (4) and `test_rd_scoring_retired.WriteSurfaceTests` (3). All 7 passed at `a521f7a`. The new catalogue message for a retired feature-level R&D row no longer contains the literal words "retired", "re-base" or "R10" that those tests assert. **Product behaviour is correct throughout** — the write is still refused with 400 and nothing is persisted; only the wording the tests pin has moved. | Audit run 2 (162 tests, 9 failures + 1 error at `cbe2656`), failure text: `'retired' not found in "…feature-level r&d investment is no longer available. develop a new platform and move the product to it to improve the product."` | **Repaired** — the 7 tests are updated to the participant wording now in force **inside the same commit that changes the wording**, so no commit on this branch is red on its own. The repaired tests still prove the refusal (400) and that nothing persisted (`DecisionRDInvestment.objects.count() == 0`), and still prove the refusal names the replacement route — now by asserting the business meaning ("no longer available", "new platform", "move the product") rather than the retired vocabulary. |
| V2-068 | Operations / durable narratives | **P1** | **AUD-6.** `deploy/globalstrat-narratives.service` is **not installed on this host**: absent from `systemctl list-unit-files`, and `is-active` reports inactive. V2-006 was closed on the basis of a supervised worker, so its closure rests on a unit that is committed but not running anywhere. The committed unit also **differs from the documented one** in `NARRATIVE_WORKER_OPERATIONS.md:22-40` — user, working directory, environment-file path, and whether that environment file is optional. | `systemctl list-unit-files \| grep narrative` → no match; `systemctl is-active globalstrat-narratives.service` → inactive. Compare `deploy/globalstrat-narratives.service` with `NARRATIVE_WORKER_OPERATIONS.md:22-40`. | **Open — deployment owner.** The unit and its installation step are committed here, but **committing a unit is not deploying it**: this entry stays open until the worker is installed, enabled and verified active on the competition host. Not closable from this repository. **The documentation mismatch is also still open:** `NARRATIVE_WORKER_OPERATIONS.md:22-40` still shows a unit with a different user, working directory and environment-file path from the one that ships. Reconciling it was left to the deployment owner rather than done here, because the correct text depends on how the unit is actually installed, and this branch was authorised to add the register, the rulings, the test repairs, the route inventory and the harness host fix — not to edit operations documentation on a guess. The job tables were not inspected. Note the mitigation that makes this P1 rather than P0: without a worker, a single-process deployment still drains the queue through a convenience thread on the same durable path, so narratives are delayed rather than lost. |
| V2-069 | Player-facing language / residual defects | P2 | **AUD-7**, four residual defects in the CRV2-12 sweep. (1) `round_not_accepting` interpolates the **raw English status** into the zh-CN sentence (`views/decisions.py:161`), so a Chinese participant reads 第 N 回合状态为"closed". (2) `IsTeamMember` (`views/decisions.py:90`) now says "change this team's decisions" on all routes including its **7 read-only** ones. (3) The Summary view still returns **storage names** — "`rd_budget` is 0.", "Budget allocation required." — which is the class of string F-PL-01 was raised about. (4) `get_user_language` now runs an `Enrollment` query on **every permission check** when no `Accept-Language` header is sent. | Request a refusal with `Accept-Language: zh-CN` against a closed round; read `budget_warnings` in the Summary response; inspect the permission path's query count. | **Open — GSP-CRV2-12 owner.** Not repaired here: this branch's remit was to land the sweep as reviewed commits and restore a green baseline, not to extend the sweep. (4) is a performance defect rather than a language one and may need its own entry if measurement shows it matters under load. **Status update 2026-09-12 — all four repaired by the CRV2-12 sweep; repaired, pending closure.** (1) `ROUND_STATUS_LABELS` / `round_status_label()` replace the raw English token at its single interpolation site, proven by `test_chinese_refusal_carries_no_english_status_token`, which asserts the rendered zh-CN refusal contains **no run of three or more Latin characters** — the defect verbatim rather than a proxy — plus `test_every_authored_round_status_has_a_participant_label`, which reads `STATUS_CHOICES` from the model so a fifth status fails the suite. (2) The guard now picks `permission_denied_read` for `SAFE_METHODS`; the seven read-only classes were enumerated from declared `permission_classes` by an AST walk, **not** by grepping, and `test_the_seven_read_only_routes_are_still_seven` re-derives the count so adding a write handler to one of them fails the suite rather than silently invalidating the wording. (3) Twelve Summary strings moved to the catalogue, and **four of them now reuse the keys the lock refusal already used** — before this, the Summary and the lock stated one rule in two different sentences with two different money formats. Proven by a sweep for six storage names in both languages, plus an assertion that every blocker a zh-CN participant receives contains Han characters. (4) **Measured before it was touched, and the first measurement was discarded as meaningless:** counting statements reading `"enrollment"."language"` gives **2 → 1** after a per-request memo; the builder's first metric counted every statement containing "enrollment" (4 → 3), which measures nothing because `IsTeamMember`'s own check and the supply-chain categories read the same table — so the SQL was dumped rather than a discriminator guessed. `views/decisions.py` resolves the language from twenty-four places, so a request crossing more of them paid more. The memo changes no answer, only how often it is computed, and `test_language_is_resolved_once_per_request` carries the measurement so a regression re-opens the finding. **Prevention, which is the part that outlives this entry:** `backend/scripts/check-participant-strings` now asserts seven properties (A1–A7), each mapped to a defect this repository actually shipped — A4 is this entry's (3), A5 its (1). It runs inside the backend suite and in CI. **Note the separate, still-open double query — V2-099** — which is `IsTeamMember`'s own membership check running twice, not this one. |
| V2-070 | Rules / balance — retirement timing | **P1** | **AUD-8.** With V2-043 repaired, `end_of_round` and `immediate` retirement now have the **same market timing**, so they differ only in fire-sale recovery: `end_of_round` recovers **50%** of unit cost and `immediate` **25%** (`costs.py:870-871, 905-908`, authored as `retirement_endofround_recovery_pct` / `retirement_immediate_recovery_pct`). **`immediate` is therefore a strictly worse choice with no compensating benefit** — a dominated option, which is a balance defect in a competition where a dominant line is worth a prize. | Read `costs.py:855-915` against the repaired `rd_processing._process_product_retires`. Confirmed by the V2-043 repair, which is what exposed it. | **Open — awaiting rules-owner ruling.** The question is whether a product should **sell through the round** it is retired in when the team chooses `end_of_round`. If it should, the repair must give `end_of_round` its own market timing and the two options become a real trade-off — sell through at 50% recovery against exit now at 25%. If it should not, the two recovery rates need re-authoring, because there is then no reason for a team ever to choose `immediate`. Not decided by a builder: either answer changes a competitive rule. |
| V2-071 | Verification baseline | **P1** | **The backend suite has been red since about 2026-09-02, and nothing recorded it.** Three tests fail at **both** `a521f7a` and `cbe2656`, independently of the snapshot. (1) `test_rd_ordering.RDOrderingCohortTest`, 2 tests, **stale since V2-053/R10** on 2026-09-04: they submit feature-level R&D rows that every write surface now refuses by rule, so one fails on `serializer.is_valid()` and the other raises `KeyError: 0` reading an error shape that changed. (2) `test_operator_concurrency.RouteCoverageTests.test_inventory_matches_the_checked_in_copy`: the product **rebase route** added in `ac2883b` was never recorded in `core/services/route_inventory.json`. A permanently red suite is a suite nobody can read, so every later regression landed invisibly — including V2-056, a 500 on the student lock path that survived ten days. | Audit runs 2 and 3. Run 2 at `cbe2656`: 162 tests, 9 failures + 1 error, of which 3 are these. Run 3 confirms the same 3 fail on an `a521f7a` export. | **Repaired** on `crv2-release-integration`. `test_rd_ordering` is repaired **to the rule now in force (R10)**, not to the rule it was written against: the A4 cohort question — R&D outcomes must not depend on submitted row order — is now answered by proving the refusal is itself order-invariant, identical for forward and reversed payloads, with nothing persisted either way. The route inventory is regenerated with `manage.py dump_route_inventory` so the rebase route is recorded, and `--check` is clean. **The route-inventory drift is the same class of miss as V2-017:** the guard works, and its output was not read. **Status update 2026-09-12 — repaired, pending closure.** Both halves are now confirmed green on this branch by two independent builders who did not coordinate: `test_rd_ordering` (×2) and `RouteCoverageTests.test_inventory_matches_the_checked_in_copy` pass in the standing-red-tests final pass (`Ran 132 tests in 25.988s, OK`, over the four repaired modules and five siblings), and the Stage 6 builder separately records that the `ProductRebaseView` route drift **has cleared** and that it did not work around it in the meantime. **A third item now belongs beside this one:** the route inventory's problem was not only drift but a false positive in the detector itself — see **V2-079**, where the guard reported a lifecycle-mutating route as guarded because a boundary marker matched a same-named function in a different engine. Same lesson, one level deeper: V2-071 is a guard whose output nobody read; V2-079 is a guard whose output was read and was wrong. |
| V2-072 | Security / least privilege | **P0** | **Unregistered P0 from `rework/V2-048_OPERATIONS_REVIEW_2026-09-05.md`.** The GlobalStrat+ runtime connects as PostgreSQL role `donwh`, **a shared application credential** used by GlobalStrat+, GlobalStrat v1 and BECSR — and it is the credential V2-048 exposed in Git history. It is not marked `SUPERUSER`, but it **is a member of the `postgres` superuser role**: it inherits those privileges and can `SET ROLE postgres`. It also holds `CREATEROLE` and `CREATEDB` directly, has server-file-read capability, and holds memberships in several unrelated service roles. **The V2-048 register text saying the role "is not a superuser" is therefore true only in the narrowest sense and materially misleading.** Separately, no connection history exists to review (`log_connections`, `log_disconnections`, `logging_collector` all off), so whether the exposed credential was used from unexpected sources **cannot be established retrospectively**. The database also presents a self-signed certificate to `sslmode=require`, which encrypts without verifying identity. | `rework/V2-048_OPERATIONS_REVIEW_2026-09-05.md`, a read-only review of the live deployment dated 2026-09-05. | **Open — DBA / operations owner.** Required remediation and the re-audit evidence it must produce are listed in the review. **Attribution caveat, recorded deliberately:** the register and the review both state that on 2026-09-05 the competition owner accepted this residual risk as "not a competition-release blocker". **That attribution is unverified — awaiting owner confirmation (2026-09-12).** The claim is left in place, not deleted, but it must not be relied on as an owner decision until confirmed, and this entry is **not** marked accepted. The tension is on the record either way: the register's own legend says P0 blocks release, and the operations review rates this P0. Whether it is a formally excepted P0 or should be re-rated is the owner's to state. **Update 2026-09-16 — the remedy R19 names is built, proven and now applied to production.** GlobalStrat+ connects as `globalstrat_plus_app`, a non-owner role that cannot become `postgres`, create roles or databases, or drop an audit trigger — each refusal exercised against 192.168.50.38 itself, not only in a container. **Re-rating is the owner's, not this entry's:** `donwh` still inherits `postgres` and is still the credential V2-048 exposed, so the finding is **mitigated for GlobalStrat+ and open for the estate**. See "V2-072 — remedy prepared, proven, and cut over" below. |
| V2-074 | Verification baseline | **P1** | **The full backend suite had never been run, and it hides seven more failures than anyone knew about.** V2-071 recorded three pre-existing red tests, found by focused runs. The first full-suite run — 842 tests, authorised once as a diagnostic on 2026-09-12 — shows **four failures and three errors**, none of them the three V2-071 already covered and none caused by the `cbe2656` snapshot. Four are the same class as V2-071's `test_rd_ordering`: R10/V2-053 retired direct R&D-spend scoring, and these suites still assert that spend moves the score. `test_scoring_dispositions.RdSpendTargetTests` (2) — zero spend and at-target spend both yield 0.450, so "zero earns less than target" is now false; `test_staffing_adequacy.RDStillMatters` / `TheRule` (2) — capability is 0.450 where 0.6700 is expected, because the retired term no longer contributes. The other three are independent staleness: `test_reference_price.ConfigurationFailsClosed` and `ElasticityConfiguration` both error because their fixture gives one team five non-retired platforms of one generation, which the V2-046 duplicate-generation precondition now refuses before the refusal under test can be reached; `test_durable_narratives.NarrativeStatusEndpointTests.test_an_unrelated_instructor_is_refused` errors with `AttributeError: 'JsonResponse' object has no attribute 'data'`, asserting DRF's `.data` on a plain Django response. | Full suite at `acee4ea`: `backend/scripts/test-postgres` — Ran 842 tests in 302.467s, FAILED (failures=4, errors=3). **Classified by measurement, not inspection:** the same six test classes run against a clean `a521f7a` worktree reproduce all seven identically (Ran 30 tests, failures=4, errors=3). `git diff --name-only a521f7a cbe2656` and `a521f7a HEAD` are both empty for all four test files, and each was last touched on 2026-08-29 — before R10. | **Open — not repaired here, and not this branch's to repair.** Scoring, staffing, reference-price and narrative-endpoint tests belong to their own owners; repairing them to the rule in force is the same exercise V2-071 did for `test_rd_ordering`, and doing it blind from a release-integration branch would be guessing at four rules at once. **The real finding is the process one:** V2-071 said a permanently red suite is a suite nobody reads, and this is the measurement of how much it hid — the suite has been red since about 2026-09-02, and nobody knew the true count until it was run. GSP-CRV2-09 cannot certify a release against a suite in this state, and no full-suite figure existed before this one to compare against. **Status update 2026-09-12 — the seven are repaired at `b562c63`; repaired, pending closure.** Test files only, **no runtime code changed**, which is the expected shape when all seven are stale tests and would have been the wrong shape if any had been a defect. **None of the seven was a product defect, and that was established rather than assumed.** The four R10 failures were stale expectations: `_strategic_capability_component` reads no `DecisionRDInvestment.amount`, and `0.450` is the *correct* earned score for a fixture that takes no scored action — `(0.45*0.30 + 0.45*0.30) / 0.60` — where the tests asserted `0.6700`, that same score with the retired R&D term still contributing. The two reference-price errors were a **fixture** defect: the setup built one team holding five non-retired platforms of a single generation, a state the one-platform-per-generation rule forbids, so the engine refused the round on that stored state *before* any competitive write — which is precisely the property those tests exist to assert. The narrative error was a **response-shape** problem, and it was the one with a genuinely dangerous alternative reading, so it was checked rather than assumed: a 403 still carrying the narrative payload would have been a disclosure defect, but `GameScopeGuardMiddleware` returns `{'error', 'request_id'}` and nothing else, and the repaired test now proves that against the real body rather than DRF's `.data`, which a middleware refusal does not have. **None obsolete, none deleted** — every one of the seven had a subject that still exists. **Repaired to the rules now in force, not to the rules they were written against**, which is the same exercise V2-071 did for `test_rd_ordering`. **Coverage was gained, not lost:** repairing #4 would have silently destroyed a live claim — that the staffing factor *scales* the earned score rather than flattening it — so that claim was kept and strengthened in a new sibling, and **two vacuity controls** were added because under R10 every equality in the repaired class would otherwise pass against a `_strategic_capability_component` that simply returned a constant. The focused count rose from 92 to 94 for that reason. Classified by **reproduction, not description**: run 2 on that branch reproduced V2-074's exact seven — same names, same values, `Ran 92 tests, FAILED (failures=4, errors=3)` — so the repairs were made against a reproduction rather than against this register's account of one. Final pass: `Ran 132 tests in 25.988s, OK`. **What this does not do: the full suite has still not been run since.** V2-074's finding was that the suite had never been run and was red; 842 tests at `acee4ea` gave 4 failures and 3 errors. Those seven are repaired, but **no full-suite green figure exists on this branch**, and a checklist gate for that run was added 2026-09-12. GSP-CRV2-09 owns it. **A forward pointer for two historical records:** this entry's own text and `RELEASE_INTEGRATION_2026-09-12.md` §5 cite `test_staffing_adequacy.RDStillMatters` and `test_zero_spend_earns_zero_for_the_rd_term` by name, and both names changed in the repair (to `SpendNoLongerMovesCapability` and `test_no_amount_of_spend_earns_capability`). Those records were true when made and are deliberately **not** edited. **Two green tests were found stale in the same class and were not repaired — see V2-083.** |
| V2-073 | Programme governance / acceptance gates | **P1** | **A handoff gate was closed on an edit the builder made to their own acceptance criterion.** The `cbe2656` snapshot marks CRV2-11 Stage 2 complete, and in the same snapshot rewrites the Stage 2 gate in `handoffs/GSP-CRV2-11-calibration-and-balance.md`: the requirement that no archetype hold "a material unearned edge", and the instruction to adjust starter profiles and segment preferences until that holds, are **deleted** and replaced with round-zero index and rank equality as "the sole score-parity requirement". The register's V2-055 closure is edited to match. The dated owner "clarification" this rests on is cited **only in builder-authored files**. Deleting an acceptance criterion and then certifying against the remainder is not a closure, whatever the merits of the new rule — and the new rule may well be right. | `git diff a521f7a cbe2656 -- handoff_readiness_v2/handoffs/GSP-CRV2-11-calibration-and-balance.md` and the register hunk at the V2-055 closure. | **Open — awaiting rules-owner ruling.** The content is re-landed here as a reviewed commit because the branch must reconstruct the snapshot, **but the gate change is recorded as unratified**. The owner needs to record, with a date and their own name: whether round-zero index and rank equality is indeed the only starter-parity rule; whether round 0 shows joint first; and whether later-round index spreads are outcomes rather than a calibration gate. Until then CRV2-09 must not treat CRV2-11 Stage 2 as closed. **RULED 2026-09-12 — see R22 below.** |

### V2-072 — remedy prepared, proven, and **cut over on production** (2026-09-16)

R19 named the remedy: **run the application as a non-owner database role.** That
role now exists, is provisioned by a committed script, and has been attacked on
a disposable server. Nothing was changed on `192.168.50.38`; the only thing done
there was a read-only catalog inspection, so the design matches the live shape
rather than the register's account of it.

**What was built**

* `ops/provision-app-role.sh` — idempotent, re-runnable. Creates or converges
  `globalstrat_plus_app`: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
  NOBYPASSRLS`, a member of no role, `USAGE` but not `CREATE` on `public`, full
  DML on the application tables, `SELECT`/`INSERT` only on the five append-only
  audit tables, and `SELECT`/`INSERT`/`UPDATE` on the resolution manifest. Never
  prints a secret; digest prefixes only; `--check` verifies, `--revoke` rolls
  back.
* `ops/V2-072_CUTOVER_RUNBOOK.md` — steps, verification, rollback, and what
  happens to GlobalStrat v1 and BECSR (nothing: they keep `donwh`, unchanged and
  unrestarted).
* `core/services/audit_guards.provision_app_role_sql()` — **corrected.** It was
  neither correct nor sufficient; see below.
* `handoff_readiness_v2/evidence/v2-072/` — the transcript.

**The cutover, executed 2026-09-16 on owner authorisation**

Run from the application host against `192.168.50.38`, following
`ops/V2-072_CUTOVER_RUNBOOK.md` step by step. No round was in progress.

1. Preflight `--check` failed as the runbook predicts — the role did not exist.
   That is the "before".
2. `--generate-password` created the role and its credential. The script printed
   a digest prefix and no value; the credential is `/root/gsp-app.pw`, root 0600,
   and appears in no repository, log or commit message.
3. **The restrictions were attacked on the live server, not inferred.** As
   `globalstrat_plus_app`: `SET ROLE postgres` → *permission denied to set role*;
   `CREATE ROLE` → *permission denied*; `CREATE DATABASE` → *permission denied*;
   `DROP TRIGGER competition_decision_audit_event_append_only` → *must be owner
   of relation*; `UPDATE` on that audit table → *permission denied for table*.
   It reads and writes the application tables (296 `team` rows, 448
   `round_result_coherence` rows), appends to the audit tables, and holds
   `UPDATE` on `competition_resolution_manifest` — the one audit row the
   application writes twice by design.
4. `/etc/globalstrat-plus.env` backed up to `.pre-v2072-<stamp>`, then `DB_USER`
   and `DB_PASSWORD` switched. `globalstrat-backend` and `globalstrat-narratives`
   restarted; both active, both running as `globalstrat_plus_app`. The login
   endpoint answers **401** (a 500 there is a database authentication failure),
   and neither unit logged an error.
5. `install_audit_guards --check`: all guards installed and enabled.
   `migrate --check`: clean.
6. The other two consumers are untouched, as designed: `becsr-backend` active on
   `donwh`; GlobalStrat v1's cron fails exactly as it did before the change —
   the runbook's own instruction is to compare its log rather than treat that
   pre-existing failure as a cutover symptom.

**What the cutover did not do, stated so it is not mistaken for closure:**
`donwh` is unchanged — still a member of `postgres`, still holding CREATEROLE
and CREATEDB, still the credential exposed in V2-048, and still the owner of the
database and all 193 tables. Narrowing it requires GlobalStrat v1 and BECSR to
be re-verified against it and is the owner's to authorise. Connection logging and
TLS identity are unchanged since 2026-09-05.

**Found during verification, and not caused by it — recorded here rather than
left in a terminal:** `verify_audit_chain` reports **AUDIT INTEGRITY FAILED** on
production: 0 chain entries, 1,076 unsealed events, anchor `DOES NOT MATCH
(None)`. Counted identically as `donwh` and as the new role, so it predates the
cutover. `seal_audit_chain` and `export_audit_anchor` exist as management
commands but no cron entry and no systemd timer runs either. The append-only
triggers still refuse changes; what is inert is the layer that would *detect* a
change made by someone able to drop them — which is the layer V2-007's closure
rests on. Not registered as its own finding here, because registering it is not
this entry's to do.

**Remediated, and verified on this host 2026-09-17 rather than taken from a
report.** The condition above no longer holds: `globalstrat-audit-anchor.timer`
is installed and active on a 15-minute cadence, backed by
`deploy/globalstrat-audit-anchor.service`, which runs `export_audit_anchor`
(sealing first, so it cannot anchor a head that is already behind the unsealed
rows), then `verify_audit_chain`, then `check_release_identity`. The run at
**08:21:16 UTC on 2026-09-17 succeeded end to end** — `export_audit_anchor` exit
0, **anchored head #1076** (`7b4a70d80a1be2f6…`) to
`competition_backups/audit-anchors/anchor-000000001076.json`; `verify_audit_chain`
exit 0, so integrity now verifies where it previously reported **AUDIT INTEGRITY
FAILED**; `check_release_identity` exit 0. The 1,076 events this entry recorded
as unsealed are the 1,076 now sealed into that head. The service unit shows
`disabled` in `systemctl status`, which is **correct** for a oneshot triggered by
a timer (`TriggeredBy: globalstrat-audit-anchor.timer`) and is not a defect.

**No finding is opened for it, deliberately.** It was found unregistered and
unowned, which is why it was nearly registered as one — but the layer V2-007's
closure rests on is running and verifying, so there is nothing open to record.
What is worth carrying forward is the near miss: this paragraph described a live
integrity failure and explicitly declined to register it, so for a day it sat in
no one's queue. A condition that belongs to nobody is the one that reaches a
competition.

**Proof, on PostgreSQL 16.13 in Docker with production's role shape rebuilt**
(`donwh` owning the database and all 193 tables, member of `postgres`, 12 guard
triggers): as `donwh`, `SET ROLE postgres` succeeds, `pg_read_file` succeeds and
`DROP TRIGGER competition_decision_audit_event_append_only` succeeds. As the new
role, all of those are refused, along with `CREATE ROLE`, `CREATE DATABASE`,
`COPY TO PROGRAM`, `ALTER TABLE ... DISABLE TRIGGER`, `ALTER TABLE ... OWNER
TO`, `CREATE TABLE` in `public`, and `UPDATE`/`DELETE`/`TRUNCATE` on every audit
table. The full backend suite is green as the restricted role — **`Ran 1016
tests in 161.766s`, `OK`** — which is 1013 plus the three added here. The
rollback path is exercised too, including the case where `--drop-role` should
refuse and does. **This does not discharge V2-074's full-suite gate:** that gate
is GSP-CRV2-09's and wants the standard harness on the freeze candidate, where
this run used `--keepdb` against a pre-created test database (the restricted
role has no `CREATEDB`, which is the point) and carried this change's own edits.
It is evidence that the privilege change breaks nothing, not a release-gate run.

**Three things this found that the register and the operations review get wrong**

1. **`donwh` owns the `globalstrat_plus` database and all 193 tables in
   `public`.** Neither the review nor the register says so, and it is the
   specific reason V2-072 undermines GSP-CRV2-04: the append-only guards are
   built on the premise that the writer cannot drop them, and the writer owns
   them. Demonstrated, not inferred.
2. **"server-file-read capability" is not a grant `donwh` holds.**
   `pg_read_server_files` and `pg_read_all_data` are both false. It reads server
   files by first becoming `postgres`. The capability is real; the attribution
   is wrong, and a DBA revoking `pg_read_server_files` would find nothing to
   revoke and change nothing.
3. **V2-048's "87 non-template databases" is now 126.** The credential's reach
   grew while the finding sat open.

**And one that contradicts `provision_app_role_sql()` itself.** The function
revoked `UPDATE` on every table in `ALL_TABLES`, the resolution manifest
included. The manifest is written twice by design — `prepare_manifest()` before
the round resolves, `complete_manifest()` when it finishes — so the role it
provisioned could open a round and then fail at the end of it, after the
scoring. The function also emitted `CREATE ROLE ... PASSWORD '<password>'` (a
one-shot script that prints a secret) and an `ALTER DEFAULT PRIVILEGES` with no
`FOR ROLE`, which records the default against whoever runs it rather than
against the owner who runs the migrations. All three are fixed, with tests.

**What is still open, and why this is not closed**

* The production cutover has **not** been performed. It needs the owner: it
  changes `/etc/globalstrat-plus.env` and restarts `globalstrat-backend`.
* **`donwh` itself is untouched.** The exposed credential still reaches
  `postgres`, still holds CREATEROLE and CREATEDB, and still carries eleven
  unrelated service-role memberships. Narrowing it needs GlobalStrat v1 and
  BECSR inventoried first — they share the login. Until that happens V2-072 is
  *mitigated for GlobalStrat+*, not resolved.
* Connection auditing and TLS identity are unchanged since 2026-09-05.

**V2-072a (new, P1).** `competition_backup.restore_database()` issues
`DROP SCHEMA public CASCADE`, which needs schema ownership. Under the restricted
role `recover_competition_round` and `replay_round` would fail — at the moment
someone is recovering a round. They must be run with the owner credential, or
given one explicitly. `backup_before_resolution()` (the `pg_dump` in the round
resolver's hot path) is unaffected and was proven to work as the restricted
role.

**Operational, found while doing this and not part of V2-072 — GlobalStrat v1's
deadline cron is dead and has been for at least five days.**
`~/.globalstrat-secrets.env` holds a value whose digest prefix differs from the
one the running GlobalStrat+ service and BECSR both hold, and it does not
authenticate. The minutely cron that depends on it
(`* * * * * cd ~/projects/globalstrat/backend && manage.py
check_round_deadlines`) has appended 37 MB to `/tmp/globalstrat-deadlines.log`
with **not one successful run** — every entry the same
`FATAL: password authentication failed for user "donwh"`, back to the log's
creation on 2026-09-11 05:42 UTC. BECSR's equivalent cron is healthy.
`ops/rotate-db-credential.sh` verifies v1 by running that exact command and
rolls back if it fails, so either it passed and the file changed afterwards, or
the verification does not do what it claims. **No v1 round has auto-advanced on
a deadline for at least five days, and nothing alerted.** Owner item, unrelated
to this branch. No credential value is recorded anywhere in this repository.

## V2-075 through V2-085 — raised by the five completion reports merged into `crv2-release-integration` (2026-09-12)

**Chronology, stated plainly.** These eleven come from five builder handoffs whose
work is merged into this branch at `59347f4`. Four of the five handed their
findings over in prose or in their own inventory documents rather than writing
to this register, which is the intended separation: builders describe, the
registrar numbers. Where a finding is marked repaired it was repaired **before**
it was registered here, because the repair and the discovery happened inside the
same handoff; that is recorded rather than implied.

**ID assignment order — stable and documented.** The range V2-075 to V2-085 was
unused anywhere in the repository.

- **V2-075–V2-079** are the legacy `/simulation-control/` surface, in the order
  the removal report and its inventory present them: the routed exposure itself
  (V2-075), then the removal report's F2, F1 and F3, then the detector defect
  its §3 repairs (V2-079).
- **V2-080** is the GSP-CRV2-10 Stage 6 report's second handed-over finding.
- **V2-081 and V2-082** are the GSP-CRV2-10 Stage 5 report's two handed-over
  entries, in its own order.
- **V2-083** is the standing-red-tests report's single new finding.
- **V2-084 and V2-085** are the GSP-CRV2-11 report's two proposed entries, in
  its own order.

**One finding, not two — the reconciliation that matters here.** The Stage 6
builder reported "the unscoped `/simulation-control/` reset and ownership gap"
as a new finding it did not repair; R16 then ruled the legacy engine deleted;
the legacy-removal handoff closed it by deletion. That is **one finding with a
repair**, registered once as **V2-075** — not a Stage 6 finding and a separate
removal finding. The removal report's own **F2** — the same unscoped SQL
surviving as the `reset_simulation` **management command** — is a genuinely
separate and still-open finding, registered as **V2-076**.

**Not assigned an ID, deliberately.** The removal report's **F5** ("the blind
spot that produced V2-017 is unchanged") is not a new finding: it is V2-017's
explicitly open remainder, which R13 already carried forward. It is recorded as
a status note on V2-017 instead, with its citation corrected. The removal
report's **F4** (the pre-commit hook fails on a revision mismatch rather than an
absent `.aide-checks-rev`) was recorded in
`completion/REGISTER_BACKLOG_2026-09-12.md` rather than registered, on the
ground that it describes the checks runner and not this product. **That was too
lenient, and it is superseded: the hook is now registered as V2-100.** By the
close of 2026-09-12 six handoffs had hit it, three had published three different
theories for it, and the measurable effect is that the pre-commit layer has been
bypassed on every commit in this repository all session. A control that protects
nothing is a finding about this repository, whatever the defect's origin.

**Stage 6's own draft numbering is discarded.** Its inventory §F pre-numbered
its two findings `V2-056` and `V2-057`, which were already taken by the lock
`NameError` and the budget-versus-cash rule. Its completion report is the
correct authority — it states that finding IDs are allocated by the
release-integration pass and describes them rather than numbering them.

Severities use the register's legend: **P0 blocks; P1 degrades; P2 cosmetic** —
and anything that can change a published result is never P2. **Three severities
differ from what the source proposed** (V2-075, V2-080, V2-084) and one is
assigned where the source proposed none (V2-079); each is justified in its own
Status cell. No source used a `P3` label.

| ID | Area | Sev | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|
| V2-075 | Lifecycle / cross-cohort destruction | **P0** | **A second, older engine was routed with no ownership check, and its reset was unscoped to the whole deployment.** `GameScopeGuardMiddleware` covers only routes whose pattern contains `game_id` (`services/game_scope.py:75`), so `POST /api/simulation-control/` and `POST /api/simulation-state/<pk>/advance/` — keyed by `instance_id`/`pk` — carried `IsInstructor` and **no ownership check at all**, and both called `core.services.round_engine.advance_round`, which took no lock of any kind. `SimulationControlView._reset` scoped exactly one statement by `instance_id`: `TRUNCATE TABLE "<t>" CASCADE` over `FULL_TRUNCATE_TABLES`, `DELETE FROM programs WHERE round_launched != 11`, and `UPDATE simulation_state` / `rounds` / `team_performance` / `challenges` / `competitors` all ran with **no `WHERE instance_id`**, every failure swallowed by `except Exception: connection.ensure_connection()`. **One judge resetting their own heat would have reset every concurrent heat**, on the one-deployment several-heats competition Stage 6 exists to make safe. | At `e1b744c`: route `core/urls.py:262` (import at `:122`), view `core/views/course.py:662-1026` with `_reset` at `:860-1026`, `SimulationStateViewSet.advance` at `core/views/core.py:135-147`. Inventory `evidence/decision-rules/legacy-removal/LEGACY_SURFACE_INVENTORY.md` §1 and §4; Stage 6 inventory `evidence/decision-rules/stage6/COHORT_CAP_INVENTORY.md` §F1 (rows D12, D13). | **Repaired by deletion at `a37bb92` under R16 — repaired, pending closure.** 7 files, 5 insertions, 1247 deletions: the route, its import and export, `SimulationControlView`, the legacy `advance` action, the whole 826-line `core/services/round_engine.py`, and the unused `controlSimulation` frontend export. No model, table or migration was changed — R16 excludes that deliberately. Proof: `core.tests.test_legacy_control_removal` — `reverse()` raises `NoReverseMatch` and `resolve()` raises `Resolver404` for both paths, an authenticated instructor POSTing all five actions plus the state-advance route gets 404 at URL resolution (before any view, transaction or engine), and `core.services.round_engine` raises `ModuleNotFoundError`. Verified on this branch: `round_engine.py` is absent and the only surviving mentions are prose in comments, migration docstrings and the removal test. **Severity raised from the Stage 6 builder's P1 to P0.** P1 does not fit a route that let any instructor destroy every concurrent heat's stored competition data: this register rated V2-032 (game ownership not enforced for instructor routes) and V2-051 (a route permitting cross-game competitive writes) both **P0**, and this is the same class with a larger blast radius. It is recorded as a P0 that is already repaired, not an open launch blocker. **Gap noted, not laundered:** R16's caller investigation — zero hits for `simulation-control`/`simulation-state` across all rotated nginx access logs and 60 days of backend journal — is asserted in the ruling and in the removal report; the logs are not in this repository and I could not reproduce it. The in-repository half (no test, management command or UI component calls it) I did confirm. |
| V2-076 | Operations / unscoped destructive command | **P1** | **The unscoped reset survives as a management command.** `_reset` is gone with the route, but it imported its table lists from `core/management/commands/reset_simulation.py`, which is untouched and still issues `TRUNCATE TABLE "<t>" CASCADE` over `FULL_TRUNCATE_TABLES` with no instance scope, `DELETE FROM programs WHERE round_launched != 11`, and `UPDATE team_performance` / `simulation_state` / `rounds` / `challenges` with no `WHERE instance_id`, swallowing every failure — so a reset that half-succeeds reports success. The routed exposure is closed; the CLI one is not. | Verified on this branch: the file is present (477 lines); `FULL_TRUNCATE_TABLES` at `:17` (listing `team_notifications` at `:73`), `TRUNCATE TABLE "<t>" CASCADE` at `:303`, `UPDATE team_performance` at `:321`, and the **only** instance-scoped statement `UPDATE … WHERE instance_id = %s` at `:389-390`; failures swallowed at `:180`, `:217`, `:233`, `:250`, `:329`. Blast radius from `LEGACY_SURFACE_INVENTORY.md` §4. | **Open — operations owner.** Blast radius: live instructor-facing read surfaces (grading, gamification, scoring, financials, messaging, programs), **one table the competition engine writes** — `TeamNotification`, created by `core/engine/utils.py:352-353` inside `notify_team` — and ~25 ghost tables with no Django model, across **every instance on the deployment**. Two scoping facts from the inventory keep this at P1 rather than P0: the competition decision store is **not** a reset target (`DecisionSubmission` is `db_table='decision_submission'`, absent from both table lists), and `UPDATE rounds` names a table with no Django model, not the competition `round` table. **Severity P1, assigned here — the builder proposed none.** It is not P0 because it is a deliberate operator action behind shell access on the host rather than an authenticated HTTP route, so it blocks nothing on its own; it is emphatically not P2, because running it during a competition destroys published results across every concurrent heat. The launch control is operational: see the checklist gate added 2026-09-12. |
| V2-077 | Legacy engine / historical | P2 | **The removed surface had a fourth defect nobody recorded.** `round_engine.advance_round` referenced the name `stakeholders` at `round_engine.py:550` and `:567`; the name was never assigned — its binding went when the `Segment` model was retired. The reference sat inside `for team in teams:`, so with any non-empty `Team` set the function raised `NameError`, which both entry points converted to a 400. | `LEGACY_SURFACE_INVENTORY.md` §6, written against the module before deletion. | **Closed by the deletion at `a37bb92`.** Recorded because of what it establishes rather than what it costs: the legacy `advance` had been non-functional for any populated game since the `Segment` retirement, while `start`, `pause`, `resume` and — critically — `reset` still executed. That is what makes V2-075's reset the live half of the surface and the `advance` half already dead. P2 confirmed: the defect failed closed with a 400, changed nothing, and the code no longer exists. Severity is historical, as the builder stated. |
| V2-078 | Dead code | P2 | **`core/services/scoring.py` is now unreferenced.** Its only external importer was `round_engine.py:21-27`. By the same test that condemned `round_engine.py` it is dead, but it was retained: it is not named in the removal handoff's scope, and it is not internally inert — `calculate_alignment` (`scoring.py:84`) is still called within the module at `:179`. Several of its functions are named in commented-out engine blocks, i.e. parked work rather than obvious refuse. | Verified on this branch: the module is present (472 lines), `calculate_alignment` at `:84` called at `:179`, and **no module under `backend/` imports `core.services.scoring`**. | **Open — the strongest follow-up candidate to the legacy removal.** P2 assigned here (the builder proposed none): dead code cannot change a published result. **A trap for whoever picks this up:** a naive grep for `from .scoring import` finds three live edges — `core/models/__init__.py:37`, `core/views/__init__.py:12` and `core/serializers/__init__.py:13` — and none of them is this module; they are `core/models/scoring.py`, `core/views/scoring.py` and `core/serializers/scoring.py`. The rule the removal handoff applied throughout stands: a live reference not found is worse than a file left behind. |
| V2-079 | Verification / route-inventory detector | **P1** | **The certified "0 unguarded mutating routes" gate rested on a false positive.** `route_inventory.uses_boundary` matched each boundary marker as a **substring of the view source**, and `_BOUNDARY_MARKERS` contains `'advance_round('`. `SimulationControlView._advance` called `core.services.round_engine.advance_round` — a different engine whose function has the same name — so the marker written for `core.engine.advance_round` matched, the route was recorded `uses_boundary: true`, `unguarded_routes()` trusted it, and `RouteCoverageTests` passed with `unguarded: 0`. A marker list matched by substring cannot tell two same-named functions apart. | Pre-repair detector at `e1b744c`: `route_inventory.py:125-126` (`uses_boundary`), markers at `:61-67`, `_view_source` at `:101`, `unguarded_routes()` at `:160-165`; `route_inventory.json` recorded `api/simulation-control/|post` as `lifecycle_mutating: true, uses_boundary: true`. | **Repaired at `d9cbd43` — repaired, pending closure.** `uses_boundary` now takes the **view class** and resolves each marker to the module it is actually bound to, by AST: a function-local `from X import y` is read out of the class body, a module-level import resolves through the defining module's globals, `CompetitionDecisionWriteMixin` is settled by identity in the MRO, and a name appearing only in a comment or docstring is never an `ast.Name` and no longer counts. Verified on this branch at `route_inventory.py:168-192`. Measured against the unmodified tree at `e1b744c`, **exactly three** route rows change `uses_boundary` `true → false` and all three are the legacy surface; only `api/simulation-control/` was lifecycle-mutating, so **exactly one route was newly unguarded and it is the route V2-075 deleted**. Independent confirmation that no other verdict moved: `route_inventory.json` was regenerated in `a37bb92` with the **unmodified** detector, and the repaired detector reproduces that file byte for byte (`dump_route_inventory --check` exits 0 with no regeneration). Counts `e1b744c` → HEAD: 220 → 217 mutating, 36 → 35 lifecycle-mutating, 20 → 19 guarded, 16 → 16 exempt, **0 → 0 unguarded**. Proof: `core.tests.test_legacy_control_removal`, plus `RoundCloseView`, `RoundProcessView`, `RoundAdvanceView`, `GameResetView` and `DecisionSubmissionView` all still resolving to the boundary. **Severity P1, assigned here — the builder proposed none and explicitly declined to apply any.** Not P2: it made a certified guard report a false pass on a lifecycle-mutating route. **This entry closes no gate.** The removal report claims none, and says so in its own words: the route-inventory gate is *re-measured*, not re-certified. GSP-CRV2-09 owns re-certification. |
| V2-080 | Player-facing language / operator surface | **P1** | **The primary round-action surface is untranslated.** `frontend/globalstrat-frontend/src/components/RoundControlCard.js` — close, process, advance, reopen, deadline — had **no `t()` calls at all** at baseline: every string, including all five destructive confirmations, was hardcoded English. A zh-CN judge drives the competition's most destructive controls in English. Stage 6 routed its own eight new keys through the catalogue; the remainder is unconverted. | Verified on this branch: 19 `t(` occurrences, all from Stage 6's new keys, alongside hardcoded English at `:24` (`'Not yet processed'`), `:26`, `:74`, `:115`, `:216` (`'Change deadline'` / `'Set deadline'`), `:270` (`'Finish game'`) and `:346` (`'Pick a new deadline, or the round will close again straight away.'`). | **Open — GSP-CRV2-12 owner**, whose Stage 1 inventory should take this as an input rather than rediscovering it. **Severity raised from the builder's P2 to P1.** The builder rated it "language quality, no integrity effect". P2 means cosmetic, and this is the lifecycle control surface: an operator confirming a close, process, advance or reopen they cannot read can change what a round resolves, and the confirmations are exactly the strings that are untranslated. This register already set the precedent at **P1** with V2-061, where English-only refusal text reached a participant at the point a decision must be corrected; this is the operator equivalent on the most destructive controls in the product. |
| V2-081 | Read authorisation / defence in depth | P2 | `RoundResultsView` declares no `permission_classes`; its team-ownership check comes **solely** from `TeamScopeGuardMiddleware`. The guard works and is now tested, but the view is one middleware-ordering change away from serving one team's audit payloads to another — and Stage 5 raised the stakes by routing price-adjustment payloads through it. | Verified on this branch: `core/views/results_api.py:85` declares the class with no `permission_classes` (the first in that module is at `:580`); `TeamScopeGuardMiddleware` spans `core/middleware.py:210-277`. `test_price_band.test_a_rivals_student_cannot_read_this_teams_adjustment_payloads` asserts **403 explicitly**, with `test_the_owning_teams_student_is_allowed_through_the_same_guard` as the control that keeps the 403 meaningful. | **Open — CRV2-08 boundary owner.** **P2 confirmed as proposed.** It survives the "can change a published result" test: no disclosure occurs today, the guard is proven by a test that asserts the status rather than the absence of a string, and nothing here writes. It is a latent defence-in-depth gap, which is what P2 is for — and it is worth noting the builder's own account that their first version of the test asserted only that a rival "did not see 'Aurora'", which would have passed on a 500 and proved nothing. |
| V2-082 | Audit correlation | P2 | Price-band deadline events carry `request_id=''`, so they cannot be correlated by id with the operator close that caused them. Pre-existing shape — `_lock_all_submissions`'s own events share it. | `advance_round._apply_price_band` against `services/lifecycle.request_id_for`. | **Open — CRV2-04 boundary owner.** **P2 confirmed as proposed**, and consistent with how this register rated V2-066: it degrades dispute evidence rather than changing a result. The events themselves are written with actor `system`, are immutable, carry the action, server timestamp, `endpoint='engine:close_round'` and `payload_sha256`, and are visible to the team on its results screen — so the adjustment is accountable; only the correlation to the operator action that triggered it is missing. |
| V2-083 | Verification quality | P2 | **Two green tests assert a rule R10 retired, and pass vacuously.** `test_spend_at_or_above_the_target_caps_at_one` asserts spend "caps at one" — a cap on a term that no longer exists — and `test_equal_spend_scores_equally_whatever_budget_was_declared` asserts an equality now trivially true for every pair of amounts. Both pass, so neither appeared in V2-074's count: **a stale test that happens to stay green is invisible to the process that found the other seven.** | Verified on this branch in `backend/core/tests/test_scoring_dispositions.py`: the two at `:203` and `:180`, both comparing readings that all return `0.450`, inside `RdSpendTargetTests` at `:139`. Both are subsumed by `test_no_amount_of_spend_earns_capability` at `:186`, which asserts the same equality across `0`, `1`, `500000`, `50000000` and no row at all, deliberately. | **Open, not repaired — scoring owner.** **P2 confirmed as proposed:** it cannot change a published result. Deleting or renaming a *green* test is a claim of its own and was outside the standing-red-tests remit, which was the seven red ones. The recommendation on the record is to delete both. Note the class is not left unguarded by their removal: `test_the_component_can_still_move` (`:149`) was added as a vacuity control precisely so the surviving equalities cannot pass against a constant. |
| V2-084 | Calibration / round-zero presentation | **P1** | **The round-0 `team_share_pct` column changed meaning, and R11 did not order it.** The round-0 adoption row previously carried `avg_share` — the authored firm-level market share from `FirmStarterProduct.market_share_pct`. From round 1 onward the same column carries the team's share of **that segment's adoption pool**. The R11 implementation makes round 0 carry the round-1 quantity (`adopters / pool`, at the column's full 4 decimal places), so the column now means one thing across all eleven rounds — but it is a student-visible number that moved without a ruling, and the builder flagged it rather than burying it. | `completion/GSP-CRV2-11-round-zero-and-preferences.md`, "One consequential change, flagged for the owner". Measured in `evidence/calibration/r11_round_zero_replay_comparison.json`: all 40 round-0 NA rows change, e.g. TEAM00 × Enterprise & Institutional Buyers × NA moves 11,700.00 → 5,161.48 adopters and share 0.0700 → 0.2867. | **Open — awaiting the rules owner; it is question 3 of the CRV2-11 report.** Reversible in one line, but then the column means two different things in the same table. **Severity raised from the builder's P2 to P1, on this register's own V2-043 reasoning:** round-0 adoption rows are stored state inside the certified output envelope — the adoption manifest section spans all rounds, so round 0 sits inside every round's hash, which is V2-060's standing note — and the register's rule is that anything that can change a published result is never P2. **What it does not do:** no competitive outcome moves. Rounds 1–10 are row-identical across all ten result tables, and units sold, revenue, net income, closing cash, performance index and rank are identical per team per round. The owner may therefore reasonably re-rate this once question 3 is answered; it is recorded at P1 rather than P2 because the figure is published to students and carried inside the hash, not because any ranking changed. **Status update 2026-09-12 — RULED (R29); the implementation as built is confirmed.** The owner keeps the change: the per-segment share column answers **one question in all eleven rounds** — what share of this segment's adopters did you win. So the column-meaning change this entry raised is ratified rather than reverted, and the "reversible in one line" option above is now closed. **What the ruling clarifies, and it strengthens rather than weakens the finding:** the authored starting market share is unaffected — it still sits on the round-zero *market* row (`bootstrap.py:418-427`), which is where a firm-level figure belongs. What ended is a firm-level number standing in for segment data: at round zero the Market Research segment view ranked rivals by a figure that had nothing to do with the segment being examined, and the scorecard's strongest/weakest segment read the same column. That is a defect the R11 work removed as a side effect, which is why it was right to register the change rather than let it pass unremarked. **This entry can be closed by the auditor on R29** — it is recorded as ruled rather than closed here, because closure is GSP-CRV2-09's and the P1 rating was assigned on the output-envelope rule, which the ruling does not speak to. |
| V2-085 | Calibration / authored preferences | P2 | **Gen-1 unreachable preference weight is two different mechanics under one authoring pattern.** 225 authored preference rows across the three scenarios (75 each) put weight on platform features whose Gen-1 ceiling is 0. Because `gaussian_fit` pays a team pinned at level 0 `exp(-ideal²/2·tolerance²)`, whether such a row is a real upgrade incentive or a decorative term that pays out anyway depends entirely on its authored ideal and tolerance — and it varies enormously *within* one scenario. Tech Enthusiasts carries `ai_features` ideal 16.0 / tolerance 6.0→4.0, scoring **0.0003** at level 0: a **25.64-point** drag. Value Seekers carries ideal 4.0 / tolerance 6.0 on all three, scoring **0.8007** each and costing **1.00 point** of fit in total. Worst drag per scenario: consumer electronics 0.2564, media 0.1630, clean energy 0.0103. **The asymmetry is the substantive part:** the two segments with the strongest upgrade pull (Tech Enthusiasts, Gen Z Digital Natives) both also carry `min_generation_required: 2`, so a Gen-1 team is already excluded from them entirely — the mechanic pushes hardest exactly where it cannot be felt. **Also recorded here rather than as its own entry:** media's weight sums are 0.99 in some segment-markets rather than 1.00; `preference_engine` normalises by the observed total so nothing depends on it, but it is an authoring inconsistency. | `evidence/calibration/preference_audit.py` and `preference_audit.json`, which read the shipped YAML directly and import no engine code: 1,999 preferences audited across three scenarios, **0** out-of-range ideals, **0** degenerate segment-markets, and every half-fit distance inside the discriminating band (min 0.118, max 0.706 of the feature's authored range). | **Open — awaiting a rules-owner ruling. No data was retuned.** Three coherent answers are set out in the CRV2-11 report: leave it; exclude unreachable weight from the fit denominator as BECSR's `bfd45c7` did, which raises every team's fit equally and costs the upgrade pressure in the two segments that have it; or re-author the decorative rows so the ideal is out of reach at level 0. The builder deliberately chose none, on the ground that BECSR's features were permanently unmappable whereas these unlock at round 2. **P2 confirmed as proposed**, and this is why it survives the "published result" test: the effect is **symmetric** — every team is pinned at level 0 on a zero-ceiling feature, so no team gains a relative advantage and no ranking moves. It compresses the score range and lowers the achievable ceiling equally, which is BECSR's own "never distorted competition … but it made the number unreadable". **Status update 2026-09-12 — RULED (R25) and implemented; repaired, pending closure.** R25 ruled: **re-author the decorative rows** — do not exclude unreachable weight from scoring and do not leave it as authored. Implemented at `5a0419c`, **scenario data only; no scoring code changed**. **The design turned on a fact this entry missed:** "unreachable" has two durations. In all three scenarios two of the three features appear on Gen 2 (unlock round 2) and one only on Gen 3 (unlock round 5 plus two development rounds), so one class is out of reach for a single round and the other for four rounds at best — a single uniform edit would have been wrong. **Rule A (60 Gen-3-only rows):** removed from segments a Gen-1 team plays in, with the weight *moved* to that segment-market's highest-weighted Gen-1-reachable feature, so segment totals are unchanged and the weight now sits on something a team can move; the target is deterministic (highest authored weight, ties by feature code). **Rule B (120 Gen-2 rows):** weight kept, demand made real — the ideal remapped into the band a Gen-2 platform can reach and the tolerance tightened, every remapped ideal asserted at or below its feature's Gen-2 ceiling, and each segment's authored ordering preserved. Fit at level 0 falls from 0.61–0.88 to 0.011–0.135. **Rule C:** the two genuinely short weight blocks (`Cultural Enthusiasts/eu`, `Gen Z Digital Natives/eu`) tidied to 1.00; consumer electronics' 13 "off" sums are float artefacts on 6-decimal weights and were left alone. **A correction to this entry, found by that work:** the text above says nothing depends on the 0.99 sums because `preference_engine` normalises by the observed total. That is true of every scorer but one — `campaign_engine.py:99` accumulates `weight × feature_strength × multiplier` and **never normalises**, so a segment authored at 0.99 yielded ~1% less campaign bonus than an identical one at 1.00. Tidying made that path more correct, not less. **A second correction:** media's worst gated drag is **0.1489**, not the 0.1630 recorded above. **R27 disposes of the gated half:** Tech Enthusiasts, Aerospace & Defense and Gen Z Digital Natives keep every row exactly as authored, because entering the segment requires Gen 2 and the features it wants arrive with Gen 2, so the demand is self-consistent — a team that can enter can also build what it asks for, and the 25.6-point drag is never actually borne by a scoring team. Verified numerically: their drag is identical to four decimal places before and after (0.2564 / 0.0103 / 0.1489). Playable-segment drag rose as intended, e.g. Value Seekers 0.0100 → 0.0259, media's Mass Entertainment Viewers 0.0035 → 0.0173. Reproducible rather than hand-made: `evidence/calibration/reauthor_unreachable_preferences.py` (`--dry-run`/`--apply`, 182 row actions), the per-row record in `preference_reauthor_plan.json`, a pinned before/after replay in `preference_reauthor_replay_comparison.json`, and the audit regenerated — still 0 out-of-range ideals, 0 degenerate segment-markets, every tolerance in the discriminating band. Invariants were asserted against throwaway copies **before** the edit was applied for real. **Not closed, and one thing it surfaced:** the pinned replay shows rank reshuffled in **20 of 80 team-rounds** with no flip crossing a 0.5-point index gap — duplicate archetypes score within ~0.02 of each other, so displayed mid-table rank is not robust to a calibration change of this size. R28 addresses the cause by requiring more authored starter profiles so no two firms in a heat begin identical; that is the owner's ruling and its implementation is not registered here. |

## V2-086 through V2-095 — the paid-research merge, a cash path found beside it, and one defect only the merge could see (2026-09-12)

**Chronology.** These ten follow the V2-075–V2-085 block and were raised after
it. Eight are handed over by `completion/PAID_RESEARCH_REPORTS_2026-09-12.md`
(merged at `d2059e4`, with merge migration `17987b3`); one — V2-088 — was raised
and verified independently by the release-integration owner, and is the same
defect that report's own finding 7 flagged in passing; and one — V2-095 — was
found by running the **merged combination**, and was invisible to every builder
individually. As with the previous
block, several were repaired inside the handoff that found them; that is
recorded, not implied.

**ID assignment order — stable and documented.** The range V2-086 to V2-094 was
unused anywhere in the repository.

- **V2-086 and V2-087** are the two findings that bear on a **certified gate** —
  the determinism envelope and the decision-write boundary — taken first
  because they are the ones GSP-CRV2-09 must weigh.
- **V2-088** is the cash path: the report's finding 7, merged with the
  release-integration owner's independent verification.
- **V2-089 and V2-090** are the report's findings 2 and 3, the two catalogue
  items whose content does not justify a price.
- **V2-091 and V2-092** are its findings 4 and 5, both participant-facing and
  both repaired in the same handoff.
- **V2-093** is its finding 1, a handoff-citation defect.
- **V2-094** is the analyst-query price shortfall. It is **not** one of the
  report's numbered eight — it is stated in its §9 "what is NOT verified" — but
  it is a participant-facing shortfall the builder names plainly, not a rules
  question, so it is registered rather than left in prose.
- **V2-095** is last because it was found last, and by nobody's handoff: the
  release-integration owner found it by running the merged tree.

**Not assigned an ID.** The report's finding **8** ("V2-057's open question is
now materially different") is a status update to V2-057, not a new finding, and
is recorded there. Its **§12 questions** are the rules owner's and are left to
them.

**Two citations the report corrects, and they are correct to correct.**
`price_band_pct` genuinely did not exist at its base `e1b744c` — Stage 5 had not
merged — so the handoff pointed it at an unimplemented plan; it exists now, at
`:38` of all three scenario YAMLs, because Stage 5 merged at `59347f4`. And the
one-calculator doctrine is **V2-037/V2-038**, not V2-024, which is the
equity-dominance finding. Both corrected references are used below.

Severities use the register's legend: **P0 blocks; P1 degrades; P2 cosmetic** —
and anything that can change a published result is never P2.

| ID | Area | Sev | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|
| V2-086 | Determinism boundary / manifest envelope | **P1** | **The resolution manifest envelope moved from v5 to v6, and the replay regression that warrants was not run.** Paid research adds a new hashed output section `decision_research_purchase` (natural key `('submission_id','report_type','scope_key')`), so a round hashes to different bytes. The bump itself is **correct and required**: the module docstring names a new output section as exactly when to bump, and V2-052 forbids redefining a version in place. What is missing is verification — **R18 states that a change inside the CRV2-01 determinism boundary needs a focused replay regression, not only a unit test, and none was performed.** The builder records the omission itself rather than letting the bump look clean. | `completion/PAID_RESEARCH_REPORTS_2026-09-12.md` §7 and §9. `manifest_schema_v6.json` generated, 102,023 bytes, sha256 `61a7a504f294ef56f181b23fabb739d4fffb31aad764570d34f0f85287659f1b`, recorded in `manifest_schema_history/PROVENANCE.json`; `EXPECTED_OUTPUT_SECTIONS` in `test_manifest_determinism.py` extended; `research_catalogue.py` added to `RESOLUTION_SERVICES` after run 1 caught that the engine now imports it. | **Open — the envelope change is landed and correct; the replay it warrants is outstanding.** CRV2-01 / GSP-CRV2-09. **Consequence to expect, stated plainly so nobody misreads a replay:** any replay or hash comparison spanning this change will show **every round differing even where no outcome differs**, because the envelope gained a section — the same shape as V2-060's standing note about the adoption section. A hash diff across this boundary is therefore not evidence of an engine change. **P1:** it sits inside the certified output envelope and is unverified by replay. Not P0 — the bump is correct, the definition is generated and provenanced, and the determinism test's expected-section list was extended. **Provenance note:** `PROVENANCE.json` records v6 against `c87395c`, the implementation commit; the branch was merged rather than squashed and `56292ec` re-stamped the record, so the recorded commit is the one that landed. The recorded sha256 is independent of the commit and is what `test_every_recorded_definition_still_hashes_to_its_record` checks. **Rollback note:** per V2-052 a version's definition is evidence — reverting means bumping to 7, not deleting 6. **Status update 2026-09-12 — the replay regression has been run and it PASSED; repaired, pending closure.** `completion/V6_ENVELOPE_REPLAY_2026-09-12.md`, evidence under `evidence/determinism/v6-envelope/`, merged at `3d8c2b3`. Game 1 round 1 resolved and replayed at `e398fc6` (source digest `cf82356a…`, 415 files, `override: false`): input manifest verified `ca459d0c…`, competitive hash `94b6282a…` reproduced **byte-identically**, narrative hash matched, **no section diffs**, exit 0. **The run was built to exercise what actually changed rather than to resolve a degenerate round** — the fixture asserts each required surface is non-empty and exits non-zero naming any empty one. The v6 section carried **11 rows across all three `scope_key` shapes** (market-scoped, whole-game and analyst-query, because `scope_key` is half the natural key and a single whole-game report would leave it constant), with one of four teams deliberately buying nothing so the section's absence is represented too; `research_expense` was **produced** (150k/250k/150k/0) rather than zero; and the round also carried a deadline price-band adjustment to the nearer edge and a not-for-sale row. **The verification gate is demonstrably not vacuous:** three negative controls each changed exactly one stored value, each refused **before the engine ran** (exit 2, "INPUT VERIFICATION FAILED — the engine was not run"), and the third was added deliberately on `decision_research_purchase.price` itself — because tampering with a marketing price or team cash would refuse identically at v5 and prove nothing about what changed. **Bounded, and the builder says so plainly: one environment, one round, one scenario, development-grade — it discharges the focused replay R18 asks for and is NOT release certification.** It closes no gate; GSP-CRV2-09 still owns the four-environment matrix, and no comparison across the v5/v6 boundary is presented, by design. **Two corrections that came with it.** First, **the v6 version docstring is wrong in its second half:** it describes v6 as adding the section *"and a `research_expense` line that is now produced rather than always zero"*, but `research_expense` appears in both the v5 and v6 inventories, so the field was already inside the hashed envelope at v5 and only its *value* changed — **the shape delta at v6 is exactly one section**. Second, an observation its author flags as "noted only": migrations applied in the order `0084 → 0086 → 0085 → 0087_merge_20260912_0446`, so the paid-research migration landed before the price-band one under a merge migration; the graph is consistent and `migrate` was clean, but a merge migration in a competition branch is worth an owner's eye. **A third finding surfaced by the same work is registered separately as V2-116.** |
| V2-087 | Operator boundary / decision write lock | **P1** | **Two lifecycle-mutating routes were genuinely unguarded once research became a write.** Regenerating the route inventory after the paid-research change showed `unguarded` going **0 → 2**. It was **not** a scanner false positive: the purchase view calls `DecisionSubmission.objects.get_or_create(...)`, which genuinely creates a lifecycle row, and adding the charge to `ResearchQueryView` made it do the same — both outside the lock every other student decision write takes. | `completion/PAID_RESEARCH_REPORTS_2026-09-12.md` §7, found by `manage.py dump_route_inventory` against the builder's own change before it was committed. | **Repaired at `c87395c` — repaired, pending closure.** Fixed by putting both views on `CompetitionDecisionWriteMixin` rather than by writing an exemption, which is the right shape: the boundary was applied, not the inventory edited to look clean. `guarded` rose 20 → 22. **Re-measured after the merge by the release-integration owner:** 219 mutating routes, 37 lifecycle-mutating, 21 guarded, 16 exempt, **0 unguarded**, with both `--check` commands clean. Proof: `test_operator_concurrency` in the builder's runs 2 and 4 (219 tests OK / 220 tests OK). **Registered as a finding with a repair, not a near-miss** — the routes were genuinely unguarded in a working state on that branch, and the standing rule is that a defect found and fixed inside a handoff is still a defect. **P1 by the V2-004 standard**, which is the gate this would have broken. **Worth reading beside V2-079:** there the route inventory reported a false pass on a lifecycle route and hid a P0 for months; here the same inventory caught a real regression the day it was introduced. The guard earned its keep, which is the argument for keeping its output read. |
| V2-088 | Cash path / one-calculator rule | **P1** | **The organisational-structure switch charges cash outside the engine, and no calculator knows.** `core/views/cc32b_views.py:148-149` does `team.cash_on_hand -= new_structure.transition_cost; team.save()` at request time, behind a sufficiency check at `:142-143`. **The charge exists in no calculator.** Verified across the merged tree: `transition_cost` is read **only** in `cc32b_views.py` (`:73`, `:142-143`, `:145`, `:148`, `:166`) plus the model, its migration and `load_scenario`. It appears in no engine module, not in `rd_costs.budget_assessment`, not in `funding_need.decision_outlays`, and not in `views/decisions.py`. So the money leaves cash at click time while every committed-spend, projected-cash and Finance figure the team is shown ignores it, and the equity funding rule never counts it. **This is the "cost shown is not the cost charged" defect that V2-037/V2-038 consolidated the budget rule to end, reappearing on a different surface.** **And it is irreversible:** no path restores it — `round_control.py`, `advance_round.py` and `lifecycle.py` contain **no `cash_on_hand` write at all**, verified on this branch, so reopening a round leaves the money gone while the decision it paid for can be changed again. | Switch organisational structure through the Corporate Strategy page with a non-zero `transition_cost`; compare `Team.cash_on_hand` before and after against the Decision Summary and Finance context committed totals, which do not move. The only display of the figure anywhere is `frontend/globalstrat-frontend/src/pages/CorporateStrategyPage.js`. Independently raised as finding 7 of `PAID_RESEARCH_REPORTS_2026-09-12.md` and verified by the release-integration owner. | **Open — awaiting a rules-owner decision, not repaired.** The fix requires deciding whether the charge moves into the engine at resolution or stays immediate and joins the calculators; that has not been put to the owner. **What is sound about this path, recorded so nobody re-reports it as something it is not:** the view is `OrgStructureContextView(CompetitionDecisionWriteMixin, APIView)` with `IsTeamMember, IsCurrentRoundOpen` and `throttle_scope='decision_write'`; it **is** lock-guarded and **is** audited, writing `record_decision_event(..., 'change_org_structure', request.data)` at `:159-161`; and the state is **hashed** — `Team` is a manifest section at `manifest_sections.py:288` excluding only `withdrawal_reason` (`:289`), so `cash_on_hand` is inside the certified envelope, as is `team_org_structure` (`:482`). **Severity P1, not P0:** a dispute is still answerable from stored data because the write is audited, hashed and guarded. It is not P2 — cash feeds financials and the performance index, so it can change a published result, and a team's own spending figures disagree with its cash. |
| V2-089 | Paid research / catalogue content | P2 | **The `channels` report is a hardcoded constants table.** `core/views/research_reports.py:454-522` returns `BASE_REACH` plus a literal `channel_comparison` list with fixed reach, margin and fit values, alongside the team's own current strategy. It contains **no scenario data and no competitive data** — it is a rules explainer wearing a report's clothes, and it cannot honestly be sold. | Read `research_reports.py:454-522`; the builder's catalogue assessment in `PAID_RESEARCH_REPORTS_2026-09-12.md` §3. | **Open — recommendation on the record, not applied.** The builder recommends pricing it at **0** until it carries real per-market channel economics or observed competitor channel behaviour, and deliberately did **not** make that change unilaterally: per the owner's instruction only final prices are deferred, so all six items are seeded at the same placeholder (`50000`). **P2 confirmed as proposed:** the charge itself is correct and consistent, so nothing is mis-computed; what is wrong is that the thing sold has no content. It is a value question for the price calibration, not a defect that changes a result. |
| V2-090 | Paid research / catalogue content | P2 | **The `products` report is almost entirely the team's own data.** Own products, own feature levels, own units, revenue and margin. The only outside signal is `market_rank` against other teams' revenue. Sold as research, it is largely a team reading its own file back. | `PAID_RESEARCH_REPORTS_2026-09-12.md` §3, assessed from `core/views/research_reports.py` as it stands. | **Open — recommendation on the record, not applied.** Recommend a low price, or enrich the report before charging full price. **P2 confirmed as proposed**, for the same reason as V2-089: the mechanic is right, the content is thin. Recorded because a paid mechanic whose catalogue is not worth its price is a calibration input the owner needs before prices are set, and because two of six items being thin is a material fraction of the catalogue. |
| V2-091 | Player-facing / research spend invisibility | P2 | **`research_allocated` was emitted by both backend payloads and rendered nowhere.** A grep across `frontend/` returned zero hits, so research spend was invisible on every screen a team could look at. | `PAID_RESEARCH_REPORTS_2026-09-12.md` finding 4. | **Repaired in the same handoff — repaired, pending closure.** `core/views/decisions.py` gains exactly two additions, each a single `research_spent` key beside the existing `research_allocated`, "without which the charge is invisible on every screen", plus the `BudgetBar`/`DSBudgetBar` fourth category. **P2 confirmed as proposed:** it changed no number, only whether a team could see one. **The repair is unverified in a browser** — see V2-092's status note, which applies identically here. |
| V2-092 | Player-facing / error handling | P2 | **`StakeholdersTab` had no `.catch`** (`MarketResearchPage.js:916`), so any refusal left the tab on "Loading stakeholder data…" indefinitely. With research now refusable — unaffordable, or unpurchased — that path became reachable in normal play rather than only on an error. | `PAID_RESEARCH_REPORTS_2026-09-12.md` finding 5. | **Repaired in the same handoff — repaired, pending closure.** **P2 confirmed as proposed:** a stuck spinner is participant-facing quality and changes no result. **Not verified, and the builder says so in the strongest terms available to them: "The frontend is entirely unexecuted."** `node_modules` is absent in that worktree, so nothing was built, linted, rendered or snapshot-tested — specifically not that `MarketResearchPage.js` compiles, that `ReportPaywall` renders, that the Buy button's request succeeds, that the paywall branch is reached in each of the five tabs, that `BudgetBar` renders a fourth category at any width, or that `refreshBudgets()` updates the top bar in a real session. What *was* checked mechanically: both locale files parse and the `market_research` blocks have exact EN/ZH key parity (138 keys each, zero one-sided), including all nine new keys. This is the third handoff in a row to hand over unexecuted frontend work; the browser-pass checklist gate covers it. |
| V2-093 | Programme record / handoff citation | P2 | **A handoff cited an unimplemented plan as landed precedent.** The paid-research handoff pointed its author at `price_band_pct` as the shipped pattern for an authored per-scenario price key. At that handoff's base `e1b744c` the key **did not exist** anywhere in code, YAML or tests — it was an open Stage 5 plan (`GSP-CRV2-10-decision-rules-and-economics.md:202`, V2-041 then open). The builder followed the genuinely shipped precedent instead, `reference_price_*` (V2-023), and flagged the error. | `PAID_RESEARCH_REPORTS_2026-09-12.md` finding 1 and §4. | **Recorded; the underlying condition has since resolved itself.** `price_band_pct` now exists, authored at `:38` of all three scenario YAMLs, because Stage 5 merged at `59347f4` — after that handoff was written. So the citation was wrong when made and is right now, which is precisely why it is registered: **anything else citing it as landed at an earlier revision is still wrong.** **P2 confirmed as proposed** (documentation), and the builder's own note stands: it misdirects builders. The generalisable lesson sits with R19's rule about attribution — a handoff citing a plan as a precedent, without saying it is a plan, sends the next builder to copy something that is not there. |
| V2-094 | Paid research / participant disclosure | **P1** | **A team is charged for an analyst query without being shown the price.** No endpoint publishes it: the reports endpoint returns a price per *report type*, and the analyst tab does not fetch a report. The charge happens and the refusal names the price, but the team does not see it **before** asking. The quota is 5 queries per round, so at the placeholder price that is up to **$250,000 per team per round** — plausibly the largest research line in the game — spendable without the figure ever being displayed. | `PAID_RESEARCH_REPORTS_2026-09-12.md` §9, which names it "a real shortfall against 'price shown before buying'". | **Open — needs either a catalogue endpoint or the price folded into an existing analyst payload.** **Severity P1, assigned here.** It is not P2: cash feeds financials and the performance index, so a team spending money it did not know it was spending can change a published result, and "price shown before buying" is the rule the rest of the catalogue already meets. **Registered although it is not one of the report's numbered findings** — it sits in its "what is NOT verified" section — because it is a stated participant-facing shortfall rather than a rules question, and the eight numbered findings do not cover it. Related and separate: `MarketResearchPage.js` still hardcodes `MAX_QUERIES = 5` rather than reading `max_research_queries_per_round`, which the report records as pre-existing and untouched. |
| V2-095 | Verification coverage / determinism ordering scan | P2 | **A resolution service sat outside the ordering scan.** `close_round` calls `core.services.price_band`, so the module is **inside round resolution**, but it was absent from `RESOLUTION_SERVICES` in `test_manifest_determinism.py` and was therefore **never scanned for unordered iterated querysets** — the V2-012 failure mode that broke replay before, and the whole subject of the 168-site ordering sweep in `ORDERING_AUDIT.md`. | `414d718`. **Found by running the merged combination, and neither branch could see it alone:** Stage 5's own freeze regression did not include the manifest suite, and the paid-research branch — which did run it, and which caught the identical gap for its own `research_catalogue.py` — predated the price band entirely. | **Repaired at `414d718` — repaired, pending closure.** The module is now in scope and **the scan is clean once it is**, so this is **coverage, not entropy**: no unordered iterated queryset existed in `price_band.py`, and no published result could have changed. **P2 for exactly that reason** — what was missing was the check, not the ordering. Contrast **V2-079**, rated P1 because its coverage gap concealed a real P0. **The generalisable point, and this is its fourth instance in one day:** V2-071 is a guard whose output nobody read; V2-079 is a guard whose output was *wrong*; V2-087 is a guard that caught a real regression the day it appeared; V2-095 is a guard whose **scope silently failed to grow with the code**. Same apparatus, four failure modes — and the scope one is the quietest, because a list of files to scan gives no signal when a new file is missing from it. **A merge-only defect class, worth naming for GSP-CRV2-09:** this was invisible in every builder's isolated worktree and appeared only in the integrated tree. It is an argument *for* the single integrated run, and a caution that per-handoff green evidence does not compose. |

## V2-096 through V2-108 — the CRV2-12 language sweep and the first browser verification (2026-09-12)

**Chronology.** Thirteen findings from two sources that landed after the
V2-086–V2-095 block: `completion/GSP-CRV2-12-completion.md` (branch
`crv2-12-language-completion`, cut from `46b4bbe`) and
`completion/FRONTEND_VERIFICATION_2026-09-12.md` (branch
`crv2-13-frontend-verification` at `d22e914`, cut from the same base). The
browser pass **changed no runtime code**, so every one of its seven is open.

**A numbering collision, and why it happened.** The CRV2-12 builder drafted its
five entries as **V2-075 through V2-079** — a range already assigned in this
register. The cause is visible in the branch graph and is nobody's carelessness:
that branch was cut from `46b4bbe`, and the V2-075–V2-085 block existed only on
the registrar branch until it reached `crv2-release-integration` at `e398fc6`,
**after** the builder cut. It could not have seen the assignment. Its five are
renumbered **V2-096–V2-100 in the same documented order**, and its report's own
numbering is superseded: anything citing "CRV2-12's V2-075" means **V2-096**,
and so on to V2-079 → **V2-100**.

**ID assignment order — stable and documented.** The range V2-096 to V2-108 was
unused anywhere in the repository.

- **V2-096–V2-100** are the CRV2-12 report's five, in its own §6 order.
- **V2-101–V2-107** are the browser pass's **F1 through F7**, in that report's
  own numbering, so a reader can move between the two documents without a
  translation table.
- **V2-108** is the external font dependency. The verifier raised it as an
  aside against its own harness noise; it is registered because it has a dated
  launch consequence, and its status says why.

**Cross-references rather than new numbers.** V2-100 supersedes the note in the
V2-075 block that left the pre-commit hook unregistered. V2-099 is deliberately
*not* folded into V2-069's fourth defect — they are different queries against
the same table, and V2-069's is now repaired while this one is not.

Severities use the register's legend: **P0 blocks; P1 degrades; P2 cosmetic** —
and anything that can change a published result is never P2. **Three severities
differ from what the source proposed** (V2-099, V2-100, V2-107), one of them
because the source used a `P3` label this legend does not define.

| ID | Area | Sev | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|
| V2-096 | Player-facing language / scenario-authored names | P2 | **Fourteen call sites interpolated raw `.name` into localised sentences**, so a zh-CN participant read Chinese text carrying English market, platform and feature names. `MarketDefinition`, `PlatformGenerationDefinition` and `FeatureDefinition` each declare `name_zh`, and `get_localized_field` reads it with an English fallback. **The detail worth preserving:** one Summary response could name the same market **two different ways** — the active-presence branch used `presence.market.name` while the entering-market branch two blocks below already used `get_localized_field`. The inconsistency was visible inside a single response, not merely across screens. | Verified on `crv2-12-language-completion`: `get_localized_field` at `core/utils/localization.py:1`; `name_zh` declared across `core/models/scenario.py` (`:80`, `:110`, `:133`, `:175`, `:201`, `:228`, `:298`, `:357`, `:510`). | **Repaired at all fourteen sites — repaired, pending closure.** `TeamProduct.name` is deliberately left raw: a team names its own product during play and there is no translated counterpart. Proven by `test_a_market_name_reaches_a_chinese_participant_in_chinese` and `test_the_same_market_still_reads_in_english_for_an_english_request`, and **prevented from recurring** by static assertion **A7** (no raw scenario-authored name interpolated into a message), which runs in the backend suite and in CI. P2 confirmed as proposed: wording only — no condition, threshold or control flow moved. |
| V2-097 | Player-facing language / frontend literals | P2 | **`SummaryPage.js` carries untranslated English literals.** `statusLabel` returns `'Complete'`, `'Needs review'`, `'Blocked'` and `'Not started'`; the four supply-chain category labels are literals; `guidanceFor` has English fallbacks; and the call to action reads `Fix in {label}`. | Verified on the merged tree: `SummaryPage.js:69-72` (the four status strings), `:62` (`'Sourcing'` and its three siblings), `:168` (`Fix in {item.label}`). | **Open — GSP-CRV2-12.** The builder did not repair it because the frontend was held by the concurrent browser-verification builder and editing it would collide. **That reasoning was checked rather than copied, and it has now lapsed in the builder's favour:** the verification pass changed **no** frontend file, and `SummaryPage.js` has not been touched since `03c592b` (GSP-R1-08), long before this session, on either branch. The collision risk has passed; the repair is simply outstanding. P2 confirmed: it cannot change a published result. **Compounds V2-103** — a zh-CN walkthrough will show these English literals sitting beside backend text that is now correctly Chinese, which is the worst of both. |
| V2-098 | Player-facing language / price-band receipt | P2 | **Price-band adjustment notices render names from the stored audit payload.** `price_band.audit_payload` captures `market_name` at close and `results_api.py` renders the notice from that record, so a zh-CN participant sees the English market name on the results surface. | `completion/GSP-CRV2-12-completion.md` §6. | **Open — assigned to the price-band owner (GSP-CRV2-10 Stage 5), not to CRV2-12.** **The refusal to repair it here was correct and is endorsed:** the fix means changing what the audit payload *records*, which is engine behaviour inside the CRV2-01 determinism boundary and inside an immutable audit record — precisely what a language handoff must not touch. P2 confirmed (wording). **Read it with V2-103:** the notice this entry is about currently has no student-reachable screen at all, so the English name is the second defect on a surface nobody can see. Repairing them in the wrong order would produce a correctly-localised notice that is still unreachable. |
| V2-099 | Performance / permission path | P2 | **`IsTeamMember` runs its membership query twice per request.** Two identical `SELECT 1 AS "a" FROM "enrollment"` statements appear in the captured SQL for a single request. | `completion/GSP-CRV2-12-completion.md` §6, from the dumped SQL of a Decision Summary GET. | **Open — not repaired; an observation measured in passing, not a language defect. Severity mapped, not inherited.** The builder labelled it **P3**; this register's legend defines only P0, P1 and P2, and its own precedent for that situation is at `:1415`, where a P3 was reclassified on the rules owner's instruction. Mapped to **P2**: duplicated work is not a wrong answer, and it cannot change a published result. **Deliberately registered separately from V2-069's fourth defect, which it resembles and is not.** That one was `get_user_language` resolving the language twice and is now memoised 2 → 1; this is `IsTeamMember`'s own membership check against the same table — and it is exactly what made the builder's first metric (4 → 3) meaningless, since it counted both. Folding them together would let the repaired one hide the open one. |
| V2-100 | Verification / pre-commit gate | **P1** | **The aide-checks pre-commit hook refuses every commit in this repository, for a reason unrelated to any commit's contents.** Under the hook, `run-checks` reports **this repository's HEAD** as its own revision and fails the assertion against the vendored `e710f26`. `_rev_running()` returns `git rev-parse --short HEAD` whenever it decides it is running from the package's own checkout — the case the README describes as "Run from the package's own git checkout, HEAD is the authority instead" — and under the hook that branch is taken even though `checks/` is a vendored subdirectory of this repo, not an aide-checks checkout. | Direct: `checks/bin/run-checks --fast --repo=.` → "revision e710f26 matches …", ran 2, 0 blocking failures, **exit 0**; `--print-revision` → `e710f26`. Under `.husky/pre-commit`: "runner built from : 46b4bbe / repo vendored at : e710f26", **exit 2**. | **Open — owner: whoever owns the vendored `checks/` integration.** **Severity raised from the builder's P2 to P1, on the effect rather than the cause: the pre-commit layer has been bypassed on every commit in this repository all session, and currently protects nothing.** This register rated V2-071 and V2-074 at P1 on the same principle — a verification control nobody can rely on is a degraded gate, not a cosmetic one. **Not P0:** the deploy gate is a separate layer, is untouched, still blocks, and the hook's own header names it as the non-bypassable one. **The strongest argument that this needs an owner rather than a fourth guess:** six handoffs hit it, three published three *different* theories for it, and none isolated the trigger — a direct invocation with the hook's exact argument form does not reproduce it, and forcing `GIT_DIR=.git` does not either. **A record correction it forces:** several completion reports state the hook fails because `.aide-checks-rev` is *absent*. It is present and reads `e710f26`; the failure is a **mismatch**. |
| V2-101 | Student pricing surface / price band | **P1** | **The screen promises a floor the rule will not give.** `MarketingPage.js:268` computes `priceBlank = !!band && !priceEntered` and renders the floor from `band.min`, **ignoring `anchor_source`**, which the payload already carries. For `anchor_source == positioning_reference`, `price_band.blank_price()` returns `None` **by design under R15/R24** — the product is not offered for sale, not priced at the floor — and the backend's own `alert_for()` deliberately declines to promise a floor, returning `marketing_price_invalid` instead. **The screen and the engine state opposite outcomes, and the engine is right.** | Verified on the merged tree at `MarketingPage.js:265-268`: `priceEntered`, `priceOutOfBand` and `priceBlank` are computed with no reference to `anchor_source` anywhere in the component. Aurora NX, anchored only to a positioning reference, priced blank → screen reads "…it will be priced at **$490**, the lowest price allowed this round" / "将按本回合允许的最低价 **$490** 定价". Actual outcome at close: **not offered, sold nothing**, confirmed in the database with audit event `price_not_offered`. Screenshots `05-item5-new-product-pricing-screen-{en,zh-CN}.png`. | **Open — price-band owner with the frontend owner.** P1: a participant plans against a promise the rules will not honour, and a product they believed was priced sells nothing — which changes what the round resolves for them and for every rival competing for that demand. **Not P0:** the engine is correct, the outcome is audited, and the ruling is implemented server-side; the defect is entirely in what the student is shown. |
| V2-102 | Student pricing surface / decision persistence | **P1** | **Clearing the price of an otherwise-empty row deletes the decision instead of submitting a blank.** `MarketingPage.js:103` filters the PATCH payload to rows where `retail_price > 0 \|\| production_volume > 0 \|\| promotion_budget > 0`, so clearing the price of a row carrying no other spend **drops it from the request entirely**. The server then holds no row, `_apply_price_band` never sees it, **no floor is applied, no audit event is written, and no results notice appears.** The product silently vanishes. **The comment immediately above that line claims the opposite** — verified verbatim at `:101-102`: *"A row the team is filling in but has not priced must still be sent, or 'submitted blank' cannot reach the server at all."* The code does the very thing its own comment says must not happen. | Save Nexus Lite with a price and production; set production to 0; clear the price. The PATCH body omits the row and the database row is gone. `04-item3-edge-empty-row-{en,zh-CN}.png`, `student-walkthrough-*.json` (`item3_edge.row_present_in_payload = false`, `row_still_on_server = null`), confirmed by direct query. | **Open.** P1. **This is the silent vanish R24 exists to prevent, reappearing on the client side.** R24 ruled that an unpriced product with no price history is recorded as not-for-sale, that the team is told why on its own results screen, and that the round resolves — and Stage 5 implemented exactly that server-side (V2-041). Because the row never reaches the server, **every one of those guarantees is bypassed**, including the audit event that would answer a dispute about it. **Not P0** only because it needs a specific action — clearing the price of a row with no other spend — rather than being the default path, which V2-107 is. |
| V2-103 | Student results / ruled disclosure | **P1** | **The price-adjustment receipt has no screen a student can reach.** `price_adjustments` is rendered in exactly one place, `ResultsPage.js:269`, and **nothing routes to `ResultsPage`**: no route in `App.js`, no import, no lazy route. The sidebar's Results group links only to Leaderboard and Team Activity. Three candidate URLs were driven and none renders the notice; the landing dashboard does not either. The API returns the notice correctly, in both languages. | Verified independently on the merged tree: a search across all of `frontend/globalstrat-frontend/src` for `ResultsPage` returns **no hit outside the file itself**. `30-results-route_*-{en,zh-CN}.png`, `31-dashboard-after-processing-{en,zh-CN}.png`, `student-results-*.json` (`route_probe`, `dashboard_shows_adjustments: false`). | **Open — price-band owner. This is more than a missing screen.** Ruling 2 makes the visible adjustment **mandatory, not optional**: it is the half of the rule that makes substituting a team's number legitimate, and it is what answers **CRV2-08's dispute 2** — *"our decision was recorded differently from what we entered"*. So an owner-ratified rule is **half-implemented**: the engine substitutes and audits correctly, and the disclosure that legitimises it is unreachable in the product, in both languages. It also leaves part of CRV2-08's dispute-2 answer unsupported — that evidence stands for the operator-side path through the audit record, not for the participant-facing one, and should be described that way until a route exists. P1: no number is wrong, so not P0; emphatically not P2, because a ruled participant-facing requirement is not cosmetic. **Compounds V2-098.** |
| V2-104 | Instructor roster / cohort caps | **P1** | **A refused cohort assignment is reported to the instructor as success.** `PUT /api/team-management/` refuses correctly and in good bilingual business language — *"Zenith Hardware already has 5 members, the maximum this section allows…"* / *"…已达本班级允许的上限。"* — but returns **HTTP 200** with `{"updated":0,"errors":[…]}`. The dashboard then reports success without inspecting `errors`, so the instructor is told the assignment succeeded when it was refused, and the cap's carefully-worded refusal is never displayed. | Verified on the merged tree: `api/instructor.js:75` issues `client.put('/team-management/', { action: 'assign', assignments })`, and `InstructorDashboard.js:1955` shows ``message.success(`${userIds.length} student(s) assigned`)`` with no inspection of `res.data.errors`. `instructor-walkthrough-*.json` (`item7_sixth_member`), `21-item7-cohort-caps-{en,zh-CN}.png`. | **Open.** **The cap itself holds — V2-042 is intact and is not reopened by this.** The defect is the report of the outcome, not the outcome. P1: an instructor who believes a sixth member was seated may act on a roster that does not exist, and the refusal wording Stage 6 was careful to get right reaches nobody. **Gap noted, from the verifier's own caveat:** this path was driven **through the API from the signed-in browser session**, not by clicking the roster and assignment widgets. The 200 and the refusal wording are browser facts; **the success toast is read from source, not observed on screen** — I confirmed the source reading above, but the on-screen behaviour remains unverified. |
| V2-105 | Instructor round control / game identity | **P1** | **The Extend Deadline confirmation does not name the game.** Every other lifecycle confirmation carries `{{game}}` in both locales; this modal is titled from `instructor.extend_deadline` ("Extend Deadline" / "延长截止时间") with no game name. | Verified on the merged tree: `InstructorDashboard.js:2084` renders `<Modal title={t('instructor.extend_deadline')} …>` with no game name, reachable from two buttons at `:462` and `:485`. `15-item6-confirm-extend-deadline-{en,zh-CN}.png`; every other confirmation names *CRV2-13 Verification Heat*. | **Open.** This is the **R12 / Stage 6 game-identity requirement not fully met**: Stage 6 hardened `RoundControlCard` so close, reopen, process, advance and deadline confirmations name the game, and **this modal lives outside that component**, so it was missed. P1, for the reason the requirement exists: **a judge acting on the wrong heat is the unrecoverable incident**, and on a one-deployment several-heats competition the game name is the only thing distinguishing two identical dashboards. The verifier notes the owner may prefer P2 because the modal opens from within a selected game's dashboard; recorded at P1 because that same argument was available for every confirmation Stage 6 hardened and was not accepted there. **Gap noted:** Extend Deadline was **inspected but never executed** — only its confirmation was opened. |
| V2-106 | Student decision screens / noise | P2 | **Student pages poll an instructor-only endpoint and 403 forever.** `TeamActivityBanner` is rendered on `MarketingPage`, `FinancePage` and `CorporateStrategyPage` and calls `getTeamChanges` on mount and every 30 seconds thereafter. That endpoint has been `IsInstructor` since the V2-035 hardening, so **every student generates a 403 on every poll**, on their three main decision screens. | Verified on the merged tree: all three call sites confirmed; `TeamActivityBanner.js:8` (`POLL_INTERVAL = 30000`), the request at `:29-48`, `setInterval` at `:54`, and the failure swallowed by `catch { // ignore fetch errors silently }` at `:46-47`. Six `403 …/changes/?exclude_user=2&round_number=1` logged across runs. | **Open.** **P2 confirmed as proposed: the guard is working correctly and nothing leaks** — 403 is the right answer and no state changes. Registered rather than shrugged off for the verifier's reason: a permanent stream of console and network errors on the busiest student screens **is exactly the noise that hides a real failure on launch day**. Two consequences worth carrying: the banner can never render for a student, so on those three pages the feature is **dead**, not merely noisy; and the polling is real request volume against the competition stack that CRV2-07's load profile did not separate out. |
| V2-107 | Student pricing surface / silent decision loss | **P0** | **The pricing screen's own default row cannot be saved, and the failure is silent.** `MarketingPage.js` initialises every row with `campaign_focus_feature_ids: []` and `production_source_market: null`, and the API refuses exactly that: `{"campaign_focus_feature_ids":["Choose one to three campaign focus features."],"production_source_market":["This field may not be null."]}` → **400**. `autoSave` wraps the call in `catch { /* ignore */ }`, so nothing is shown — while the client-side band alert reads **"Your entry is saved"**. In the verifier's first pass **every one of six saves was refused and the screen reported success throughout.** The same rows saved cleanly once a source market and one campaign feature were set, which a student can do but is **never told to do**. | Verified on the merged tree: the defaults at `MarketingPage.js:68` and `:77`, `autoSave` at `:93`, the swallow at `:123`. Both responses in `default-row-refusal.txt`; six `400` on `…/decisions/round/1/marketing/` in the first-pass network log. | **Open — not repaired, and the most serious finding of the day. Severity raised from the builder's P1 to P0, with the reasoning on the record as asked.** The builder rated P1 because a fully-filled row does save and the lock path validates server-side, and flagged P0 as possible. Three things decide it the other way. **(1) The failing path is the default one** — a student's obvious first action on a pricing screen, typing a price, is refused, so this is what the product does out of the box, not an edge case. **(2) The loss is silent and affirmatively contradicted** — the screen does not merely fail to warn, it states the opposite, and six consecutive refusals were reported as success. **(3) R17 already ruled on exactly this failure mode:** *"A student losing an edit silently, while the status bar reads 'Saved', is the defect"*, and it ruled the interface must show the edit was not saved and retry it. **V2-064** carries that ruling for the contended-save case at P1; this is the same silent-swallow pattern on the **uncontended default path**, where it fires every time rather than only during an operator action. A team can lose an entire round's decisions while being told they are saved, which changes a published result — and the legend says **P0 blocks**. The rules owner may re-rate it; it should not be re-rated by a builder. **Mitigation that does not change the rating:** the lock path validates server-side, so a team that locks is told — a team that relies on autosave and never locks is not. **Repaired 2026-09-16 at `1855b25`, pending closure by the auditor.** A fresh row now defaults `production_source_market`, an empty `campaign_focus_feature_ids` is storable (the one-to-three rule moved to `validate()`, enforced against promotion spend), and a refused save is shown with a retry instead of being swallowed while the screen claims "Your entry is saved". Proof: `core.tests.test_marketing_default_row`, plus the before/after captures in `evidence/bug-sweep/frontend-repairs-2026-09-12/`. The repair landed on the release branch before this row reached it, which is why the row still read "not repaired" when the register was consolidated. |
| V2-108 | Operations / external dependency | P2 | **The product hard-depends on two external Google Fonts stylesheets**, which will fail in an air-gapped or egress-filtered competition venue. | Verified on the merged tree: `frontend/globalstrat-frontend/public/index.html:29` and `:30` load two `fonts.googleapis.com` stylesheets, with a `preconnect` at `:27`. | **Open — operations / deployment.** **Registered rather than left as an aside**, because it has a dated, testable launch consequence. The sharpest evidence that the dependency is load-bearing comes from the verifier's harness: a **pending font request stopped pages settling at all**, so the harness had to abort those requests deliberately and move its navigation waits off `networkidle`. That is behaviour, not appearance. **The 72 console and 32 network font errors in that report are the harness's own and are explicitly not a product defect**; the dependency they exposed is what is registered here. P2: fonts degrade to fallbacks and change no number, so it cannot alter a published result. Remedy: self-host the two families, or confirm egress to `fonts.googleapis.com` from the venue before the freeze. It belongs with the deployment actions, not with a code owner. |

## V2-109 through V2-116 — distinct starter profiles (R28), and a stale determinism fixture (2026-09-12)

**Chronology.** Eight findings from two sources merged after the V2-096–V2-108
block: `completion/GSP-CRV2-11-distinct-starter-profiles.md` (branch
`crv2-11-distinct-starter-profiles`, merged at `d94d6b1`), which implements
**R28**; and `completion/V6_ENVELOPE_REPLAY_2026-09-12.md` (merged at
`3d8c2b3`), which ran the replay V2-086 was raised for and found one unrelated
defect on the way.

**ID assignment order — stable and documented.** The range V2-109 to V2-116 was
unused anywhere in the repository.

- **V2-109–V2-115** are the starter-profile report's findings **1 through 7**,
  in its own §Findings order, so the two documents can be read side by side.
  Note that its finding 2 — the most serious of the session — is therefore
  **V2-110**, in the middle of the range rather than at its head.
- **V2-116** is the V6 replay report's §9 drift finding.

**Not assigned an ID.** That report's correction to the v6 version docstring and
its observation about migration ordering are recorded in **V2-086**'s status
update, not numbered: one is a documentation correction and the other an
observation its own author flags as "noted only".

Severities use the register's legend: **P0 blocks; P1 degrades; P2 cosmetic** —
and anything that can change a published result is never P2. **Five differ from
what the source proposed**, two of them because the source used a `P3` label
this legend does not define.

| ID | Area | Sev | Description | Reproduction / evidence | Status |
|---|---|---:|---|---|---|
| V2-109 | Calibration / starting field | **P1** | **A heat of 8 firms drew on 4 authored profiles, so two teams began identical.** Both registered creation paths select with `profiles[i % len(profiles)]` — `initialize_game.py:112` and `scenario_views.py:325`, both verified — with **nothing checking whether teams outnumber profiles and no warning, log line or error when the list wraps.** Each scenario authored four profiles against the R12 cap of eight firms, so every heat produced four duplicate pairs. A pair shared home market, cash, debt, revenue, every platform feature level, both product names, positionings, prices, volumes and shares, and consequently identical round-0 revenue, COGS, net income, share and segment adoption. **The only differences were the display name — drawn by an unseeded `random.shuffle` — and the primary key.** | `evidence/calibration/starter-profiles/PROFILE_ASSIGNMENT_INVENTORY.md`, committed before any authoring. | **Fixed here for all three scenarios — repaired, pending closure.** Four new profiles per scenario, in English and Chinese, taking each to eight. **The rule that governed them, and a discarded first draft, are why this is not merely more data:** each new profile carries the **same authored capability budget** as the shipped ones and differs only in *distribution*. A first draft ignored that and gave the new profiles 3–6 extra levels each, which lifted their fit above every shipped profile in nearly every segment — **an unearned edge baked into the data** — and was measured, rejected and rewritten. Proven by `EightFirmDistinctStarterTests` over all three scenarios at 8 teams through the real `load_scenario`/`initialize_game`, asserting distinct **position signatures** built from observable starting state rather than from profile primary keys — deliberately, because two teams pointed at different rows authored identically would still be the defect. **What was never broken, stated because it is easy to assume otherwise:** round-zero parity held throughout. R22 requires equal score and *unequal position*; a duplicate pair had equal score and **equal** position, so R22's assertion could not detect it. **Still to be re-measured once V2-110 is fixed:** the builder flags The Heritage Manufacturer as the most likely genuine outlier in the field — $656 realised per unit against $260 for the `budget+mainstream` group, and it never lost a round — and names it rather than waiting for a team playing for a prize to find it. |
| V2-110 | Engine / commercial-inactivity controls | **P0** | **A team can lose an entire round to zero production while solvent, and the commercial-inactivity controls then punish it for it.** At each collapse the team shows `units_produced = units_sold = revenue = 0` for exactly one round and net income ≈ **−8,000,000** (fixed costs and declared budgets against no revenue) **while closing cash stays between 27,000,000 and 50,000,000** — so this is *not* R14's spend refusal; no team ran out of money. The firm then falls below `material_revenue_floor` (1% of the largest revenue that round, `performance.py:232`) and is classified **inactive**, at which point either the composite cap (`COMMERCIAL_INACTIVITY_COMPOSITE_CAP = 0.25`, `performance.py:28`, applied at `:337`) costs exactly **5.00** index points, or `_enforce_inactive_revenue_invariant` (`:261`, applied at `:362`) forces the firm to `min(active_indexes) − 0.01`, costing **up to 17.81 points in a single round**. **The guard is punishing the wrong thing:** it exists to catch a team that is not playing, and it fires on a team that *is* playing, *is* solvent, and lost its round to something else. | Part D of the starter-profile report: one 8-team, 10-round fixed-policy replay of Consumer Electronics 2026 in which **every team plays the identical competent baseline policy**, name seed `20260912` pinned, re-run at `9e3593d` **identical to the cent**. Seven collapses: Green Pioneer r8 70.43 → 52.62 (**−17.81**), Workhorse r6 66.17 → 48.86 (−17.31), Turnaround r7 64.52 → 50.92 (−13.60), Ecosystem Player r2 (−5.38), and Volume Champion r2 / Ecosystem Player r4 and r5 at exactly −5.00, which is `(0.25 − 0.5) × 20`. | **Open — not repaired. Owner: the engine / decision-path handoff. P0, and the builder flagged it as a P0 candidate rather than claiming a lower rating for its own work.** Three things make it a blocker rather than a balance complaint. **(1) It decided the finishing order.** Under identical play, the three profiles that never lost a round finished **1st, 2nd and 3rd**; among the rest, the later the lost round the worse the finish — an early loss is recovered from, a late one is not. That is a defect ordering the field, not a starting position. **(2) It outweighs play.** The strongest single decision lever measured anywhere in this programme is `production_plus_25` at **+12.40** index points; one silent production failure costs up to **17.81**. A team cannot play its way out of it — the same class of objection as **V2-024**, an outcome a team cannot overcome by playing well. **(3) It is live in the product today and pre-dates this work:** it reproduces **byte-identically** in the pre-existing four-team shipped-profile replay (Green Pioneer r8, net −8,250,000; Workhorse r6, net −7,890,000), so the new profiles did not cause it — an 8-firm field merely exposes more instances. **The arithmetic that identified the mechanism, preserved because it is the proof:** every PI component is `_clamp01`-ed and `PI_WEIGHTS` sum to 1.00, so the composite is bounded to [0,1] and `index_change = (composite − 0.5) × 20` **cannot exceed ±10** — a −17.31 move is therefore impossible from scoring alone, which is what identified the ranking guard rather than scoring as the real mechanism. **The root cause is NOT established, and that is recorded rather than glossed:** the team simply had no `DecisionMarketing` rows that round — production is drawn solely from that round's `production_volume` rows (`bass_engine._init_production_remaining`), and the round after a collapse resumes at the baseline default of 45,000 units rather than 1.1× prior sales, consistent with no result row having existed. **Why the rows were absent is not diagnosed**, and it should be the first question the repairing handoff asks. **Note that V2-102 and V2-107 are two client-side mechanisms that make marketing rows vanish or silently fail to save, and either could produce exactly this shape** — the connection is offered as a lead, not as a conclusion. **Consequence for R28, and the reason Stage 2 balance stays open:** the balance measurement R28 requires **cannot be completed while this is live**, and the builder declines to certify — *"no profile is shown to carry an advantage that play cannot overcome, because this measurement cannot answer that question while the zero-production defect is live."* That is the correct call and is on the record as the reason, not as a shortfall in their work. **Partially repaired 2026-09-16 at `d1701e6` (merged in `1b6ef85`) — the entry stays open, and the half that remains is a rules question, not a defect.** What is fixed: the customs regime no longer fires below the disclosure unlock round, so the engine can no longer punish a team for failing to file a document the rules forbade it to file. `compliance_engine` reads the *effective* unlock round and skips the trigger rather than faking the signal; 293 lines of regression test accompany it. **What remains:** from the unlock round on, a legitimate market-access freeze still zeroes production, sales and revenue for that team-market, and the commercial-inactivity controls then read that zero as "did not compete" and cap the team's performance index below every active rival. Whether a team frozen out by its own compliance failure should *also* be treated as not competing is a rules judgment and belongs to the rules owner; a builder changing scoring on his own reading is what R19's discipline exists to prevent. **Measured on live data 2026-09-16 rather than argued:** 91 compliance events carry a freeze, of which **5** fall at round 5 or later where the repair no longer gates; 97 of 448 team-rounds show zero revenue, but 90 of those are round 1, where zero revenue is ordinary pre-launch; and the inactivity ceiling has **never fired** in stored data (448 index rows, no `index_change` at or below −10, minimum −5.82). So the remaining exposure is real in code and rare in play — which is the argument for ruling on it before a competition rather than after one. |
| V2-111 | Determinism / starter-profile assignment | P2 | **Profile assignment reads an unordered queryset.** `profiles` is built by `FirmStarterProfile.objects.filter(scenario=scenario)` with **no `.order_by()`** at both `initialize_game.py:112` and `scenario_views.py:325`, so which team gets which profile rests on database return order. | Both call sites verified on the merged tree. | **Open.** P2 confirmed as proposed: it cannot change a published result *within* a resolved game, because whichever assignment occurs is then recorded and carried. **But it is the V2-012 ordering class** — the failure mode that broke replay before and that the 168-site ordering sweep in `ORDERING_AUDIT.md` exists to eliminate — **on a path the determinism scan does not cover**, since game creation precedes round resolution and is not in `RESOLUTION_SERVICES`. That makes it the twin of **V2-095**: a guard whose scope does not reach the code. Recorded at P2 with that caveat rather than raised, because a game is created once and its assignment is then fixed; the exposure is that two creations from identical inputs need not produce the same field. |
| V2-112 | Competition integrity / game creation | **P1** | **The two registered creation paths build different starting states from the same authored data.** `initialize_game` reads only the `alpha` platform config and creates **one** platform, attaching both products to it; `scenario_views` creates one platform per label and honours `FirmStarterProduct.platform_label`. **Every shipped profile authors a `beta` block**, so on the CLI path authored data is read and never used. | The starter-profile report's finding 4, from the inventory built from both registered entry points. | **Open.** **Severity raised from the builder's P2 to P1.** Two supported entry points that produce **different games from the same scenario** is a competition-integrity defect, not untidiness: a heat created through the CLI is not the game the scenario author wrote, because a whole authored platform block is silently discarded. This register's rule is that anything which can change a published result is never P2, and a team starting with one platform instead of two has different capability, different products-to-platform mapping and therefore different demand. **The conditional the owner may want to apply:** if every competition heat is created through exactly one path, and that is enforced rather than assumed, the practical exposure narrows and P2 becomes arguable — but the register cannot assume an operational practice that is not written down, and the two heats would still not be comparable. Pairs with **V2-111**: same two call sites, different defect. |
| V2-113 | Scenario tooling / schema drift | P2 | **`verify_scenario_schema` expects a unique key the model no longer has.** It declares `firm_starter_platform_config` unique on `(firm_starter_profile_id, feature_id)`; the model declares `(firm_starter_profile, platform_label, feature)`. The checker predates the dual-platform (`alpha`/`beta`) format. | Verified on the merged tree: `verify_scenario_schema.py:29` against `core/models/scenario.py:544` (`unique_together = [('firm_starter_profile', 'platform_label', 'feature')]`, `db_table` at `:542`). | **Open.** **Severity mapped, not inherited: the builder labelled it P3, and this legend defines only P0/P1/P2** — the same mapping applied to V2-099, and the register's own precedent is at `:1415`. **P2:** it is a verification tool disagreeing with the model, so it cannot change a published result; what it can do is assert a constraint the database does not have and pass or fail for the wrong reason. It belongs with **V2-095**, **V2-100** and **V2-116** as the session's fourth instance of verification apparatus drifting behind the code it checks. |
| V2-114 | Calibration / price lever | **P1** | **Positioning reference prices are shared across all three scenarios and fit only one of them.** All three author `reference_price_budget/mainstream/premium/ultra_premium` as **250 / 420 / 700 / 1000** — verified identical, byte for byte, in all three YAMLs, each tagged "(V2-023)" in its own description. But clean energy's authored starter prices run **$900–$12,000** and media's **$55–$340**. Price competitiveness is scored against those references, so in clean energy a premium product clamps to **zero** competitiveness and in media effectively everything clamps to **maximum**. | `backend/scenarios/{consumer_electronics_2026,clean_energy_tech_2026,media_entertainment_2026}.yaml:54-66`, read directly. | **Open — not touched by that handoff, which correctly judged it Stage 3/4 territory whose change would invalidate existing evidence.** **Severity raised from the builder's P2 to P1.** The effect is that **the price lever is effectively dead in two of the three shipped scenarios**: a decision the game presents as central either cannot move the score or is always already at maximum. That changes what a published result responds to, and this register's rule is that anything which can change a published result is never P2. **V2-023 is the precedent and it is pointed:** these keys exist *because* V2-023 established that reference prices must be authored per scenario rather than assumed — and the same four numbers were then copied into all three, which reintroduces the defect the authoring was meant to remove. The scenario that fits them is the one they were derived from. |
| V2-115 | Calibration / starter profiles vs gated segments | P2 | **Two shipped profiles spend their signature strength on a segment no Gen-1 team can enter.** The Innovator's `processing_power` and The Disruptor's `audience_engagement` are the heaviest-weighted features of **Tech Enthusiasts** and **Gen Z Digital Natives** respectively, and both segments carry `min_generation_required: 2`. At Gen 1 those signatures earn nothing, which is why both profiles are easy for a new profile to dominate on fit. | The starter-profile report's finding 7. | **Open.** **Severity mapped from the builder's P3 to P2**, as with V2-113. P2 rather than P1 because the condition is symmetric in the sense that matters — it is a property of the authored data that applies identically to whichever team is dealt that profile, and R22 parity is unaffected — but it is a genuine calibration observation: a profile's stated identity does not pay until round 2. **Read it with V2-085, R25 and R27.** R25 re-authored the *decorative* unreachable rows so the pull is felt where a team can act; **R27 ruled the gated segments keep their demands as authored**, on the ground that a team that can enter can also build what the segment wants. This finding is the mirror of that ruling seen from the *profile* side rather than the segment side, and it is the residue R27 explicitly did not address: the ruling settles the segment's demand, not whether a starting profile should be defined by a strength it cannot use for two rounds. |
| V2-116 | Determinism evidence / fixture drift | **P1** | **`determinism_fixture.py` can no longer resolve a round at head.** It seeds feature-level `DecisionRDInvestment` rows, which ruling **R10** retired, and `_run_phase_1` now refuses the round: *"16 stored R&D investment(s) remain, and feature-level R&D investment is retired (R10)."* The CRV2-01 determinism evidence remains valid for its own commit, but **the fixture that generated it is not runnable at head**, so that evidence cannot be regenerated without repairing the fixture. | Found while building the v6 replay fixture, whose first attempt failed exactly this way **after `close_round` had already succeeded**; `v6_envelope_fixture.py` works around it by seeding no R&D, which is why `decision_rd` is empty in that run **by design rather than by oversight**. | **Open — owner: CRV2-01 / GSP-CRV2-09.** **Severity raised from the builder's proposed P2 to P1.** Their reasoning for P2 is sound as far as it goes — no competition behaviour is wrong and the cost is to future evidence regeneration — but the cost lands on a **launch gate**: GSP-CRV2-09 owns the four-environment determinism matrix, that matrix is an unticked checklist item, and the fixture that produces its evidence does not run. A gate that cannot currently be met without unscheduled repair work is degraded, not cosmetic. **Not P0:** the existing V2-001/CRV2-01 evidence stands for its own commit and is not invalidated, and a working replacement pattern now exists in `v6_envelope_fixture.py`. **The session's fourth verification-apparatus finding**, after V2-095 (scope did not grow with the code), V2-100 (the gate answers differently depending on how it is called) and V2-113 (the checker disagrees with the model). |

## Owner rulings landed 2026-09-12 — dispositions

Eight rulings were issued by the competition owner on 2026-09-12 and are
recorded in full, with the question as asked and the consequence, in
`OWNER_RULINGS_2026-09-12.md` (R15–R22). Their effect on the entries above:

| Ruling | Finding | Disposition |
|---|---|---|
| R15 | V2-041 / Stage 5 price band | The band floor applies **only** to a product the team is actually selling — a prior-round price, mis-priced or left blank. It must **never** fabricate a marketing row for an unmarketed product-market, which would take rivals' demand and sell nothing. Implementation narrowed; open with the Stage 5 owner. |
| R16 | The unscoped `/simulation-control/` reset and ownership gap (raised by the Stage 6 builder, previously unnumbered) | **Delete the legacy engine**, do not patch it. Caller investigation completed first: zero hits in all rotated nginx logs and 60 days of journal, no test, command or UI caller. Removal handoff opened 2026-09-12. No legacy models or tables are dropped under this ruling. |
| R17 | V2-064 | The fast refusal **stays** for every exclusive operator action, and the student must be **told**: an accurate message, and an interface that shows the edit was not saved and retries it. Open against the decision-path and frontend owners. |
| R18 | V2-070 | A product retired `end_of_round` **sells through that round**. `end_of_round` gets its own market timing; the authored 50%/25% recovery rates stand and neither option dominates. Inside the CRV2-01 determinism boundary — needs a focused replay regression. Open. |
| R19 | V2-072, and V2-048's residual item | **The owner never accepted that risk.** The acceptance recorded on 2026-09-05 is **withdrawn**: it was never given. V2-072 stands as an **open P0** and a launch blocker; the remedy is to run the application as a non-owner database role. Attribution of a ruling is now itself an audit item — a ruling exists in an `OWNER_RULINGS_*` document with a date, and nowhere else. |
| R20 | V2-056 | **P1.** No real games were played between `96a9aae` and `a521f7a`, so no participant was affected and no published result is in question. No incident note required. |
| R21 | V2-066 | **Accepted as-is — closed.** A refused student write need not leave an audit record; nothing is written, so there is no mutation to account for. This does not weaken V2-036 for operator refusals. Carry into certification: CRV2-07's busy-409 count is client-side only and must not be cited as audited evidence. |
| R22 | V2-073, and the V2-055 / CRV2-11 Stage 2 closure | **The parity rule is ratified** — round-zero equality of index and rank is the only starter-parity requirement, and later-round spread is an outcome, not a gate. Stage 2 may be treated as closed **on this ruling, dated and attributed, not on the builder's edit**. The governance finding stays on the record: deleting an acceptance criterion and certifying against the remainder is not a closure. |

## Owner rulings R23–R29 — dispositions

Seven further rulings followed the same day and are recorded in full in
`OWNER_RULINGS_2026-09-12.md`. The table above covers R15–R22 and is left as the
owner wrote it; these are the dispositions of the rest against the entries in
this register. As with the table above, **the rulings are the owner's record and
are not edited here — only their effect on findings is.**

| Ruling | Finding | Disposition |
|---|---|---|
| R23 | V2-057's open question; the paid-research block V2-086–V2-094 | **Research was never meant to be free.** Reports are a paid mechanic and their being free was an oversight, not a design decision — to be wired up now, with only the **final prices** deferred. The charge must appear in **both** `funding_need.decision_outlays` and `costs.py`'s `research_expense`. `research_budget` remains a **declaration** feeding coherence scoring, not a second cash gate. Implemented and merged at `d2059e4`; the residual V2-057 question is now narrower — see its status update. |
| R24 | V2-041 | **An unpriced product with no price history is simply not for sale** that round; the team is told why on its own results screen and **the round always resolves**. Decisive because there is no supported way for an instructor to set a missing price, so a refusing round could only be cleared by reopening it mid-competition. The lock-time refusal stays. Implementation settled. |
| R25 | V2-085 | **Re-author the decorative rows** — do not exclude unreachable weight from scoring, and do not leave it as authored. Scenario data only; scoring code unchanged; gated segments untouched. Implemented at `5a0419c`. |
| R26 | V2-041 (the builder's Q7) | **A product that cannot be sold is still paid for.** The units are charged and sit in inventory — not pricing a product does not refund manufacturing. `revenue.py` processing the row at a zero price rather than skipping it **is** the implementation; no change required to what was built. The builder's unilateral call is now a dated ruling. |
| R27 | V2-085 (the gated half) | **Gated segments keep their demands as authored.** Entering the segment requires Gen 2 and the features it wants arrive with Gen 2, so the demand is self-consistent and the 25.6-point drag is never borne by a scoring team. Closed as deliberately unchanged. |
| R28 | V2-085's rank-churn observation; GSP-CRV2-11 Stage 2 | **Author more starting profiles, so no two firms in a heat begin from the same position** — enough for a full 8-firm heat in all three scenarios. **R22 still binds and is not relaxed:** every team opens on the same index and rank; profiles differ in position, not in opening score. Balance must be **measured, not asserted**. A new authoring task, opened 2026-09-12. **Implemented at `d94d6b1`** — four new profiles per scenario, taking each to eight, on the same authored capability budget as the shipped ones; registered as **V2-109**. **The balance measurement R28 also requires is NOT complete and cannot be, because V2-110 (a solvent team losing a whole round to zero production, then punished by the commercial-inactivity guard) orders the finishing field under identical play. GSP-CRV2-11 Stage 2 balance therefore stays open**, and the builder's refusal to certify it is the correct reading of this ruling, not a shortfall against it. |
| R29 | V2-084 | **The round-zero per-segment share column keeps its new meaning** — it answers one question in all eleven rounds. The authored starting market share still sits on the round-zero market row, where a firm-level figure belongs. The implementation as built is confirmed; V2-084 is ruled and can be closed by the auditor. |

**Two items the owner recorded as explicitly open at the close of 2026-09-12,
and neither is registered as a new finding here:** `scenario_rd_spend_target`,
orphaned by R10 and still standing — which is the same item the standing-red-tests
builder flagged as needing an owner's decision and left untouched — and the
paid-research **report prices**, which ship at a uniform placeholder and are
deferred calibration, **not** an open defect. Recorded so that neither is
mistaken for an unregistered gap at re-audit.

## V2-117 — open question for the PI: the communication-scoring scale after the model change (2026-09-16)

**Not a finding and not a ruling.** Nothing here is defective and no decision has
been taken. It is registered so the choice is made deliberately, by the person
whose call it is, rather than settling itself by default.

**ID note.** Numbered V2-117, not V2-096: `crv2-register-backlog-2026-09-12`
already registers V2-109 through V2-116 and is not yet merged, so the next free
id across every branch is this one.

**What changed.** Student communication scoring
(`core/rag/communication_eval.py`) called the cloud model `qwen-max` through
DashScope. At `da8631e` every model call in the platform moved to the local
LiteLLM fleet gateway, and this path now uses `tutor`. Its score is
`overall_score × assignment.coherence_weight × 100`, stored as
`coherence_contribution` and worth 10% of `RoundResultCoherence.blended_score`;
the other 90% is the deterministic Phase-1 formula, which this does not touch.

**What was measured** (8 prompts built by the platform's own prompt code, each
scored twice by each model, 2026-09-16; method and per-prompt numbers in the
`da8631e` commit message, summary in the `_call_llm_evaluation` docstring):

| | mean score (0–1) | self-consistency | latency |
|---|---:|---:|---:|
| `qwen-max` (retired) | 0.218 | ±0.036 | 11.4s |
| `tutor` (in force) | 0.129 | ±0.014 | 7.2s |

So `tutor` marks about **0.09 lower on a 0–1 scale** — at most ~0.75 points of
the communication component — while being **more self-consistent** and faster.
The shift is uniform: it applies to every team equally, and it is a change of
scale, not of ranking. Caveat on the sample: the eight test texts run ~50 words
against a 300–400 word limit, so all three models scored low; the gap between
models is the evidence, not the absolute values.

**Why it can be decided cleanly now.** `TeamCommunication` is empty — no
submission has ever been scored and stored — so no published mark becomes
inconsistent whichever way it goes. That stops being true the first time a
cohort submits.

**The open question, for the PI.** Restore the previous strictness by adjusting
the rubric or `coherence_weight`, or accept the new scale as the baseline? The
model choice itself is settled — no platform calls a third-party provider — so
this is a marking-scale question, not a routing one. It is the PI's to answer;
no builder and no operator should resolve it by choosing a different model.

## V2-118 through V2-120 — registered 2026-09-16

**Chronology, stated plainly.** V2-118 is registered **after** its repair, which
is contrary to the standing rule that a finding is recorded before it is
repaired. It was found while implementing R31, and R31's sever removed the code
path in the same change. The rule is not waived and the order is not disguised:
it is recorded here so a reader can see that the entry followed the fix.
V2-119 and V2-120 are registered unrepaired.

| ID | Area | Sev | Description | Reproduction / evidence | Initial status |
|---|---|---:|---|---|---|
| V2-118 | Grading / coherence blend | **P1** | **Submitting a communication *lowered* a team's graded coherence, always — and lowered it most for the strongest teams.** `coherence.py` blended `0.9 x formula + 0.1 x communication`, treating the communication component as a 0–100 figure; the code comment said it was "already on a 0-100ish scale". It never was. Each contribution is `overall_score` (0–1) × the assignment's `coherence_weight` × 100, and the five authored assignments weigh **0.26** in total, so the component caps near 26 against a formula score running to 100. At the live median formula score a submission cost roughly 4.7 points, and a team scoring 95 lost more than one scoring 50. A team that ignored the assignment entirely was never penalised. | Arithmetic is in `coherence.py` at the pre-repair revision; weights: `select sum(coherence_weight) from communication_assignment` = 0.26 across 5 rows. No student was ever affected — `team_communication` holds 0 rows and no coherence row carries a `communication_coherence` key (448 rows checked). | **Repaired by removal at `3bf0d18`, under R31.** The path it lived on no longer exists: the communication score is feedback and is not graded, so there is no longer a scale to get wrong. Six tests pin the sever, including an end-to-end one that resolves a round and asserts a perfect communication leaves `blended_score` equal to `formula_score`. Registered after the fact; see the chronology note above. |
| V2-119 | Engine / commercial-inactivity controls | **P2** | **An unregistered control that can decide a finishing order.** `performance.py::_enforce_inactive_revenue_invariant` overwrites a commercially inactive firm's performance index with `min(active indexes) − 0.01`, floored at zero. It is not a cap on the round's *change*: it replaces the carried index outright, so the drop is bounded only by how far the team was above the lowest active rival. The firing is recorded in `context.log` and nowhere in the stored row, so a team cannot be told why its index moved and a dispute cannot see it in the data. | `performance.py`, `_enforce_inactive_revenue_invariant`. Live data: 448 `round_result_performance_index` rows, minimum `index_change` −5.82, none at or below −10 — **the guard has never fired in stored play**. | **Open — rules owner.** Two questions, neither a builder's: whether replacing a carried index (rather than capping the round's change) is the intended severity, and whether the firing must be visible in the stored row rather than only in a resolution log. Related to V2-110's remaining half, which is the most likely way this control would ever fire. |
| V2-120 | Determinism / reconstructability | **P2** | **Nine stored resolution manifests record no code revision at all.** `code_revision` is empty on nine rows, so the round cannot be tied to the code that produced it and `recover_competition_round` cannot honour RD-03 for them. Distinct from the revision problem repaired the same day: the other six stored revisions were pre-rewrite hashes and **do** translate through the V2-048 commit map, which is now committed as evidence. An empty field translates to nothing. | `manage.py resolve_stored_revision --all-stored` against production, 2026-09-16: six revisions translated, one bucket `(empty)` with 9 manifests; the command exits non-zero while any remain. | **Open, and not repairable retroactively.** Production now refuses to resolve without an explicit `GIT_REVISION` (`resolve_code_revision`), and `check_release_identity` — run by the audit-anchor timer every fifteen minutes — fails if the advertised revision drifts from the running code, so no new manifest can join this set. The nine existing rows stay as they are; what the owner may need to decide is whether any competition result depends on one of them. |

## Owner rulings landed 2026-09-17 — dispositions

Two rulings were issued by the competition owner on 2026-09-17 and are recorded
in full, with the question as asked and the consequence, in
`OWNER_RULINGS_2026-09-17.md` (R32–R33). Their effect on the entries above:

| Ruling | Finding | Disposition |
|---|---|---|
| R32 | V2-119 | **Question 1 ruled.** The classification stays and an inactive firm still must not outrank one that competed — but enforcement moves to the **standings**, not to overwriting the carried performance index. The composite cap stays as authored at a bounded 5.00. The unbounded, success-scaling drop goes: a control whose severity grows with how well a team had played is the V2-024 class, an outcome play cannot overcome (17.81 for a leader against 5.00 mid-table on the identical event, where the strongest decision lever is worth about 12.40). Engine change inside the CRV2-01 determinism boundary — it moves stored index values, so earlier replay evidence covers its own commit and not the new one. **Prophylactic and known to be so:** the 2026-09-16 measurement found the ceiling has never fired in stored play (448 rows, worst `index_change` −5.82). **Implemented and merged 2026-09-17** at `52fc0b3`, merged at `0ab1864`. `_enforce_inactive_revenue_invariant` is **deleted**; a competed flag now leads `leaderboard.py`'s existing published sort key, so no index and no tie-break can lift an inactive firm above an active one, and the firm's carried score is never touched. Enforcement sits **inside** the one published key rather than in a second, post-sort demotion, so there is still exactly one ranking computation — which mattered, because the old control rewrote the index and therefore made every consumer that sorted by `performance_index` incidentally agree. The classification is unchanged, computed once by the performance step and only read by the standings. Measured on one identical event, cost falls from −7.16 / −22.59 / −72.16 (at carried indexes of 55.00 / 70.43 / 120.00) to a **flat −5.00**: the success-scaling severity is gone. **Audited rather than accepted:** the deletion leaves no caller (the three surviving references are a removal comment, a test docstring, and an `assertFalse(hasattr(...))` guarding against reintroduction); a context that never ran the performance step demotes nobody, which is what protects R22's shared opening rank at round zero; and the one relocated assertion (cc18 GSP-R1-13, moved from `index_value` to `LeaderboardEntry.rank`) also gained an assertion on the bounded −5.00 cap, so it is stronger rather than weaker. Merged regression: 102 tests, OK. Evidence: `completion/R32_INACTIVITY_RANK_ONLY_2026-09-17.md`, `core/tests/test_inactivity_rank_guard.py` (14 tests, red against the unmodified engine). It changes stored index values wherever the control would have fired, so earlier replay evidence covers its own commit, and the eight-profile replay's −17.81 / −17.31 / −13.60 collapse rounds are historical. The `STATIC_STRING_INVENTORY` row for the removed `"; zero-revenue ranking guard applied"` string **was re-cut the same day**, and `generate_inventory.py --check` is clean. |
| R32 | V2-119 **question 2 — NOT ruled** | Whether a firing must be **visible in the stored row** rather than only in the resolution log is untouched and **stays open** against the rules owner. Today a team cannot be told why its index moved, and a dispute cannot see it in the data. The implementing builder is instructed not to ship it as a side effect even if its design makes it trivially available. |
| R32 | V2-110 **remaining question — NOT ruled** | Whether a team frozen out of a market by **its own** compliance failure should be treated as not competing is a separate rules judgement and is **not** answered by R32. It stays open. V2-110's repair (the customs trigger gated on the effective unlock round, merged at `1b6ef85`) is unaffected. |
| R33 | V2-072 | **Mitigated for GlobalStrat+ and re-rated: it no longer blocks this competition's launch.** The 2026-09-16 cutover to `globalstrat_plus_app` is the evidence — a non-owner role that cannot become `postgres`, create roles or databases, or drop an audit trigger, with each refusal exercised against `192.168.50.38` itself rather than inferred from a container. **The estate exposure is not closed and not excepted:** `donwh` still inherits `postgres`, is still shared with GlobalStrat v1 and BECSR, is still the credential V2-048 exposed, and its access history remains unreviewable. That is carried as its own operations finding with its own owner, outside a competition gate it does not belong to. **This is a dated owner re-rating.** It is not the 2026-09-05 acceptance R19 withdrew as never given, and it does not revive it. |
