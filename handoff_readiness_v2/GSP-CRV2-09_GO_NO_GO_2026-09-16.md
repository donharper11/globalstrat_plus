# GSP-CRV2-09 — final competition-readiness re-audit and GO/NO-GO

**Date:** 2026-09-16
**Auditor:** independent competition-readiness auditor (implemented none of the work audited)
**Subject revision:** `3c99d7408c8b04ed0f5ea287cb543955e1be32c3` on `crv2-release-integration`
**Verdict: NO-GO.**

---

## 0. How this audit was conducted, and what it is worth

Every claim below cites a command that was run or a file and line that was read.
A claim I could not reproduce is marked as such rather than inherited from a
builder's report. The packet's own rule is applied throughout: **a gate is not
closed by a builder's report.**

Production was treated as read-only. Read-only SQL was run against the live
database at `192.168.50.38` using the running service's own credentials, taken
from `/proc/<gunicorn pid>/environ` and prefixed with
`SET default_transaction_read_only = on;`. No migration, write, restart or
config edit was performed against the live stack. One unintended write to the
host did occur and is recorded as finding **A-07** below, with the artifacts it
created listed by sha256 and removed.

### 0.1 The candidate was not frozen, and moved during the audit

`EXECUTION_PROTOCOL.md` Phase 3 requires a code freeze commit before final
certification. The branch was not frozen:

```
$ git log --oneline -3 crv2-release-integration      # after the audit began
08cfda5 Sequence launch readiness ahead of the advisory and macro builds
3c99d74 Register V2-117 as an open question, and give the deploy gate an override path
```

`08cfda5` landed on the release branch while this audit was running, and a
further commit (`7e3c296`) landed on a sibling branch checked out in the same
working tree, moving the tree under the audit mid-run. Both are
documentation-only, and this was verified rather than assumed:

```
$ git diff --name-only 3c99d74..7e3c296 -- backend/ frontend/
(no output)
```

**Every runtime claim below therefore applies to `3c99d74`, whose `backend/` and
`frontend/` bytes are identical to the tree at the time each command ran.** That
a re-audit had to prove this at all is itself finding **A-09**.

Two other agents were working on this host concurrently (`docker ps` showed
containers `v2072-pg` and `gsp-consolidation-verify`). Remediation may be in
flight; this report is a snapshot of `3c99d74`.

---

## 1. Verification I performed

### 1.1 Full backend regression suite — PASS

```
$ flock -w 1800 /tmp/globalstrat-backend-test.lock \
    bash -lc 'cd backend && ./scripts/test-postgres core'
LOCK ACQUIRED 2026-09-16T12:00:22+00:00 PID=1852004 branch=3c99d74
...
Ran 1013 tests in 320.445s

OK
real 5m32.906s     EXIT=0
```

`core` is the only application in `INSTALLED_APPS` (`globalstrat/settings.py`),
and `core/engine/tests/` sits inside it, so `test core` **is** the full suite.
`OK` with no qualifier: zero failures, zero errors, zero skips.

This closes the launch-checklist gate at `LAUNCH_CHECKLIST_V2.md:69-73` — *"Full
backend suite run and green on the freeze candidate"* — which V2-074 left open
and assigned to this handoff. It is the first green full-suite figure this
programme has: the previous run, 842 tests at `acee4ea`, gave 4 failures and 3
errors.

### 1.2 Frontend regression — PASS, and thin

Runtime `node v22.17.1` / `npm 10.8.2`, matching `package.json` engines
(`>=22.17.0 <23`, `>=10.8.0 <11`) and `.nvmrc`.

| command | result |
|---|---|
| `npm ci --no-audit --no-fund` | exit 0, 1623 packages; `git diff --stat -- package-lock.json` empty afterwards |
| `CI=true npm test -- --watchAll=false` | exit 0 — **Test Suites: 7 passed, 7 total; Tests: 33 passed, 33 total** |
| `npm run build` | exit 0, *"Compiled with warnings"*, `main.797abe22.js` 769.22 kB |
| `node eslint-warning-count.js build.log` | exit 0 — `eslint warnings: 55 (baseline 57)` |
| `backend/scripts/check-participant-strings --repo .` | exit 0 — `participant-string-hygiene: PASS 2185 unit(s) examined, 0 reviewed suppression(s)` |
| `backend/scripts/check-participant-strings-selftest` | exit 0 — `selftest: 22 ok, 0 failed` |

**Read this correctly.** 33 tests across 7 files against 75 non-test JS sources
and 27 page components, finishing in 2.9 seconds, is not regression protection
for a release. The build, the lint ratchet and the i18n gate are load-bearing;
the unit suite is not. A green Jest run here is not evidence that the frontend
works, and the launch checklist's browser-pass gate
(`LAUNCH_CHECKLIST_V2.md:74-81`) remains the real control — see §2.5.

### 1.3 Independent same-host deterministic replay at the audited bytes — PASS

Run on a disposable `postgres:16-alpine` container (tmpfs, `fsync=off`), removed
afterwards. The production database was never contacted.

```
migrate OK · load_scenario OK · dump_manifest_schema --check → "Manifest schema inventory is current."
v6_envelope_fixture.py --teams 4
  schema_version   = 6
  input_sha256     = 5276a8b86e2216306c0b1453f6ead2bf8ea74aef18364f8fa95b1d3395ec3917
  output_sha256    = 2f098f9e5debb99f8519acef7183448c57b40bbf6d5b53f19d93ea03c81f036d
  narrative_sha256 = 739a1be3a66b402cfe1827d183c596f49fc9a47c40e10b543d14cb56fe033357
  source_tree_sha256 = 4c77dadb7edf6392af29e39b0d5ee1897fccbb8c749e0161d5692c6d69654d75
  output_section_row_counts: decision_research_purchase=11, decision_marketing=18,
                             decision_submission=4, financials=8, product_market=24

replay_round --restore --confirm --expected-manifest ... --require-env tz_env=UTC --require-env python=3.10.12
  Source verified: 4c77dadb…
  Input verified:  5276a8b8…
  Competitive hash expected 2f098f9e…  actual 2f098f9e…
  Narrative hash   expected 739a1be3…  actual 739a1be3…
  Replay reproduced the round exactly.       REPLAY_EXIT=0
```

**Negative control and tamper refusal:**

| run | expectation | result |
|---|---|---|
| restore + `--verify-only` | exit 0 | `CONTROL_EXIT=0`, input verified |
| corrupt one `decision_research_purchase.price` `50000 → 50001`, `--verify-only` | exit 2 | `TAMPER_EXIT=2`, reported `section decision_research_purchase: 0 missing, 0 added, 1 changed … .price: '50000' -> '50001'` |

This is a genuinely independent reproduction: the v6-envelope evidence committed
at `3d8c2b3` was produced at `e398fc6`, and `backend/core/engine/`,
`backend/core/services/funding_need.py` and **all three scenario YAMLs** changed
after it (`git diff --name-only e398fc6..HEAD -- backend/core/engine
backend/core/services backend/scenarios`), so under `EXECUTION_PROTOCOL.md`
§Phase 1.2 that evidence did **not** carry to this revision. It does now, at
these bytes.

The replay also ran with **no model gateway configured at all** and still
resolved, and reproduced a byte-identical narrative hash. Narrative generation
is not able to block or fail a resolution — V2-A item 3's availability
requirement holds.

### 1.4 Operator-concurrency route inventory — re-certified at this revision

```
$ python3 manage.py dump_route_inventory --check
Route inventory is current.                      EXIT=0
```
`backend/core/services/route_inventory.json`: **219 mutating · 37
lifecycle-mutating · 21 guarded · 16 exempt · 0 unguarded**, and the file is
unmodified against `3c99d74`. `test_operator_concurrency` passed inside the 1013.

This is the re-certification `LAUNCH_CHECKLIST_V2.md:16-28` explicitly reserved
for this handoff after V2-079 and V2-087. It holds — with the V2-017 caveat in
§2.4.

### 1.5 Live database — migrations and privilege

```
$ python3 manage.py migrate --check --noinput          EXIT=0   (no unapplied migrations)
SELECT date_trunc('day',applied), count(*) FROM django_migrations GROUP BY 1 ORDER BY 1 DESC;
  2026-09-16 → 19        2026-08-28 → 8        2026-08-27 → 2   …
```
The 19-migration claim is **confirmed**; code and schema agree.

```
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;
  donwh | f | t | t
SELECT pg_has_role(current_user,'postgres','MEMBER'), pg_has_role(current_user,'postgres','USAGE');
  t | t
-- 16 role memberships, including postgres, keycloak_svc, rl_owner, tenant_svc …
SELECT name,setting FROM pg_settings WHERE name IN
  ('log_connections','log_disconnections','logging_collector','ssl');
  log_connections=off  log_disconnections=off  logging_collector=off  ssl=on
```
**V2-072 is open and unremediated, exactly as recorded.** The application role
inherits `postgres` (it can `SET ROLE postgres`), holds `CREATEROLE` and
`CREATEDB`, and no connection history exists to review. Under **R19** the
2026-09-05 acceptance was withdrawn as never given, so this stands as an open
**P0 launch blocker**.

### 1.6 Narrative worker — installed and running; not yet proven end to end

```
$ systemctl show globalstrat-narratives.service -p ActiveEnterTimestamp -p UnitFileState -p NRestarts
NRestarts=0   UnitFileState=enabled   ActiveEnterTimestamp=Wed 2026-09-16 05:27:05 UTC
$ diff deploy/globalstrat-narratives.service <(systemctl cat … | tail -n +2)   # identical
```
The installed unit is byte-identical to the committed one. **Two halves of
V2-068 remain:**

1. `NARRATIVE_WORKER_OPERATIONS.md:22-40` still documents a *different* unit —
   user `globalstrat`, `WorkingDirectory=/opt/globalstrat/backend`, a mandatory
   `EnvironmentFile=/etc/globalstrat/backend.env`, `TimeoutStopSec=60`. The
   shipped unit is user `ubuntu`, `/home/ubuntu/projects/globalstrat+/backend`,
   `EnvironmentFile=-/etc/globalstrat-plus.env`, `TimeoutStopSec=180`. An
   operator following the runbook installs a unit that does not exist.
2. `SELECT state, count(*) FROM narrative_job GROUP BY 1;` returns **0 rows**.
   No job has ever been processed by this worker on this host. "Active" is
   proven; "works" is not.

### 1.7 Model routing — code is clean, the deployment is not covered

The backend process environment carries
`LLM_GATEWAY_URL=http://192.168.50.220:4100/v1/chat/completions` and a gateway
key. The guards exist and run: `core/tests/test_narrative_llm_routing.py`
(inside the 1013), `.github/workflows/backend-guards.yml` on every push, and a
deploy gate at `frontend/deploy-frontend.sh:39-87` with a named, attributable
`MODEL_GUARD_OVERRIDE`. The claim *"no platform code calls a model provider"* is
true of the **source**. Its limits are finding **A-05**.

---

## 2. Gate by gate

### V2-A · Determinism vs. the LLM in the resolution path — **NO-GO**

**What passes.** The envelope reproduces byte-identically at these bytes (§1.3);
a single tampered value in the section new at v6 is refused before the engine
runs; resolution completes with no model configured; `output_sha256`,
`input_sha256` and `narrative_sha256` are separate, and `decision_audit_event`
sits in the input envelope only.

**What fails, and it is the exact claim this gate exists to test.**

V2-A item 2 requires proof that **no LLM output reaches any score component**.
V2-016 is recorded closed on precisely that basis — *"published coherence and
the grades derived from it are the deterministic formula score. Retrieval is
instructor commentary and nothing else."* **That is false at this revision.**

Traced in code, not inferred:

- `core/rag/communication_eval.py:34-49` — `evaluate_communication()` calls the
  model, takes `overall_score` from the model's JSON, and writes
  `TeamCommunication.coherence_contribution = overall_score × coherence_weight × 100`.
- `core/engine/coherence.py:145` — `comm_score_val = _calculate_communication_coherence(...)`,
  which sums those contributions (`:275-284`).
- `core/engine/coherence.py:163-168` — on the **production path**
  (`advance_round.py:880` is the only caller, and it passes `skip_rag=True`,
  so `rag_score_val` is always `None`):
  ```python
  else:
      rag_score = None
      if comm_score_val > 0:
          blended_val = 0.90 * float(formula_score) + 0.10 * comm_score_val
  ```
- `core/services/manifest_sections.py:512` — `Section('coherence',
  'core.RoundResultCoherence', …)` is a **hashed output section**.
- `core/services/grading.py:206-220` — `_extract_coherence_score` averages
  `blended_score` into a graded rubric component.

So a model's judgement of a free-text memo enters a number that is hashed into
`output_sha256`, published to the team, and averaged into its grade. The
`skip_rag` branch that V2-016's rework removed is not the only path; this second
one was never in scope.

It is not hypothetical. Five communication assignments ship in every scenario
YAML (`scenarios/consumer_electronics_2026.yaml:7375`) and are loaded in the
**live** database today:

```
code                trigger_type      trigger_condition                              coherence_weight
expansion_memo_r2   ROUND_MILESTONE   {"round": 2}                                   0.05
investor_letter_r4  ROUND_MILESTONE   {"round": 4}                                   0.05
crisis_statement    EVENT_BASED       {"event_category":["GEOPOLITICAL","SANCTIONS"]} 0.03
employee_message_r6 ROUND_MILESTONE   {"round": 6}                                   0.05
final_review_r8     ROUND_MILESTONE   {"round": 8}                                   0.08
```

Blast radius today is nil — `SELECT count(*) FROM team_communication` → **0** —
which is the only reason this is not already a scoring incident, and it stops
being true the first time a cohort writes a board memo in round 2.

Two further consequences:

- `TeamCommunication` appears in **neither** manifest envelope (no match for
  `communication` in `manifest_sections.py` or `manifest_snapshot.py`). The
  hashed output therefore depends on an **unhashed input**: altering
  `coherence_contribution` between resolution and replay would change
  `blended_score` without the input-manifest verification refusing — the gate
  that just refused a tampered research price would not refuse this.
- V2-117 registers this as *"Not a finding and nothing here is defective"* — an
  open marking-scale question for the PI. The scale question is real, but the
  premise is wrong: the defect is that the number is scored at all.

**Determinism itself is intact** — replay reproduces because the contribution is
read back from the restored database. The isolation claim is not.

**NO-GO.** Cross-environment replay (V2-A item 5) is also still unperformed; see
V2-116 in §3.

### V2-B · Adversarial balance and exploits — **NO-GO**

CRV2-06's closures (V2-018, V2-020 through V2-026, V2-028) are intact in the
suite and none of their boundaries was reopened by later work. But:

- The register's row for **V2-024** still reads **"Open — stops the handoff."**
  while the same file's body at `:1852` says *"The V2-024 rule now refuses
  equity-raise outright"* and `GSP-CRV2-06_COMPLETION_REPORT.md:31` and `:70`
  record it Closed. The status column and the evidence disagree; a reader of the
  register cannot tell which is in force.
- **V2-110 (P0)** — a solvent team losing a whole round to zero production,
  costing up to **17.81 index points** where the strongest measured decision
  lever is worth **+12.40** — is registered only on the unmerged branch
  `crv2-register-backlog-2026-09-12`. Its partial repair `d1701e6` **is** merged
  here: `compliance_engine.py:83-87` now gates the customs regime on the
  effective unlock round. Its own commit message states four collapses remain at
  rounds 5-8, and that the inactivity classification — the mechanism that turns
  a zero-production round into a −17.81 swing — *"is untouched … a rules-owner
  decision"*. The P0 is mitigated in rounds 1-4 and open from round 5 on.
- **V2-070** (R18: `end_of_round` retirement must sell through the round) is
  ruled and **not implemented**; `immediate` remains a dominated option.
- **V2-114 (P1, unmerged)** records identical `reference_price_*` values in all
  three scenario YAMLs, leaving the price lever effectively dead in two of three
  shipped scenarios.

### V2-C · RD-03 and the deploy freeze — **NO-GO**

The mechanism holds. `recover_competition_round.py:53-56` compares
`manifest.code_revision` against the running `resolve_code_revision()` and
refuses unless `--allow-code-revision-mismatch`, and the hard deploy-freeze rule
is written at `handoff_readiness/OPERATOR_RUNBOOK.md:89`.

**The deployment defeats it.** The running backend advertises

```
GIT_REVISION=86c2ad40fb300a666e154915aa392cb2e56f2ad6
$ git cat-file -t 86c2ad40fb300a666e154915aa392cb2e56f2ad6
fatal: git cat-file: could not get object info
```

That commit does not exist in this repository. Neither does any revision
recorded in the live manifest table:

```
SELECT id, code_revision, schema_version FROM competition_resolution_manifest ORDER BY id DESC;
 16 | 1189a50d41a502955f77fc505610165735ba6fac | 2
 15 | 3ffba4d363535346b8ea3aca3f813360762b8034 | 2
 14 | 564bb3c38e75bc8581ddbf2dc01bb62bf6b431d3 | 2
 13 | 7df03edfcd4f8962494a853ee0bc5cb25bb23377 | 2
 12 | 61c43da4a864ca6022d1e088c11a4f9f09246399 | 2
 11 | 30cc26e93c7fb1e3edc23c19e54c051f6194067c-dirty | 2   (source_tree_sha256 empty)
  9..1 | (empty) | 1                                        (environment = {})
```
All six named hashes: `MISSING`. This is V2-054's history rewrite reaching
inside the competition data store, not merely the programme documentation.

**Today, RD-03 would refuse recovery of every stored round on this host** —
manifests 1-9 because the recorded revision is empty, 11-16 because it differs
from the running `86c2ad4`. The mitigation V2-C asked for (`--allow-code-revision-mismatch`)
exists, but the recovery point it protects is unidentifiable either way.

Worse, the guard that should have caught this is inert in production.
`build_identity.require_identified_build()` (`:105-125`) refuses only when
`code_revision_is_dirty`, and `resolve_code_revision()` (`resolution_manifest.py:96-104`)
returns a configured `GIT_REVISION` **verbatim** — the `-dirty` suffix is only
ever produced by the non-production git branch at `:128`. So
`COMPETITION_REQUIRE_CLEAN_BUILD=true`, which `settings.py:332-333` defaults on
in production, cannot fire. The checklist's ticked item *"Resolution refuses an
unidentified build"* is true only for an **empty** identifier, not a wrong one.

The one thing that does pin runtime bytes is `source_tree_sha256`, and only 5 of
15 stored manifests carry it.

### V2-D · Load against a named field — **NO-GO**

No new load run was required or performed; CRV2-07's field is pinned at 24 teams
× 4 members / 96 sessions with 3× at 288, p95 90.1/175.0 ms, zero 5xx
(`GSP-CRV2-07_LOAD_REPORT.md`). The gate fails on an item the checklist itself
leaves open at `LAUNCH_CHECKLIST_V2.md:41-43`: **combined deadline burst +
refresh + Phase-1 resolution under load was explicitly not driven.** V2-A item
2 of the readiness document names exactly that case — all teams submitting in
the final 60 seconds while resolution runs — as the worst realistic one. It is
also the case V2-063/V2-064 made sharper: a student write now fast-fails with
409 while any exclusive operator lock is held.

Under **R21** the CRV2-07 busy-409 count is client-side only and must not be
cited as audited evidence.

### V2-E · Post-competition retrieval — **GO, with a named limit**

CRV2-08 verified post-close retrieval for both roles and the six dispute answers
(`GSP-CRV2-08_COMPLETION_REPORT.md`; checklist `:46-47`). Nothing in the
intervening work touched the post-close read boundary in a way that invalidates
it, and `RoundResultsView`'s guard is now asserted by a test that checks the 403
status rather than the absence of a string (V2-081's evidence). V2-081 itself
stays open at P2: the view still declares no `permission_classes`
(`core/views/results_api.py:85`) and depends solely on `TeamScopeGuardMiddleware`.

### V2-F · Infrastructure failure modes — **GO on the matrix, NO-GO on one path**

`FAILURE_MODE_MATRIX.md` and `GSP-CRV2-07_FAILURE_REPORT.md` cover database loss
mid-resolution, backend restart, deadline refusal, backup failure and verified
restore. The narrative-outage leg is now independently confirmed: my replay ran
with no gateway configured and resolved normally (§1.3).

The open path is the restore leg, via V2-C: a verified restore is only as good
as the recovery point, and every recovery point on this host is currently
unidentifiable (§V2-C).

### V2-G · Audit trail sufficiency under dispute — **NO-GO**

Five of the six disputes are answerable through supported paths, and the
apparatus is genuinely good: append-only admin (66 `CompetitionReadOnlyAdmin` +
5 `AppendOnlyAdmin` registrations covering all 71 competition registrations),
the audit chain, the decision drill-down, and R13's read-only ruling.

Dispute 6 — *"The result is wrong — prove the calculation"* — cannot be answered
today for any round already stored, because the proof is the manifest, and every
stored manifest names a code revision that does not exist (§V2-C). Nine of
fifteen name nothing at all. The replay that would settle the dispute cannot be
run at the revision the record cites.

Two smaller gaps stand: V2-082 (price-band deadline events carry
`request_id=''`, so they cannot be correlated with the operator close that
caused them) and V2-088 (the organisational-structure `transition_cost` leaves
`Team.cash_on_hand` at click time, is charged by no calculator, and is not
restored on reopen).

### V2-H · Regression on the v1 repairs — **GO**

The v1 repairs hold on this build: 1013 backend tests green, RD-03 present at
`recover_competition_round.py:53-56`, release provenance refusing an empty
identifier, guarded backup retention, and CR-017's unsaved-changes guard now
carrying its own frontend test (`useUnsavedChangesGuard.test.js`). CR-011's FX
premium shows no new imbalance in the surviving CRV2-06 evidence.

---

## 3. Register entries whose claimed status the evidence does not support

| # | Claim | What the evidence shows |
|---|---|---|
| R-1 | **V2-016 closed** — *"published coherence and the grades derived from it are the deterministic formula score"* | False at `3c99d74`. `coherence.py:163-168` blends an LLM-derived contribution into `blended_score` at 10% whenever a team has submitted a communication. See V2-A. |
| R-2 | **V2-117** — *"Not a finding and nothing here is defective"* | The path it describes is the one that breaks V2-016. It is a defect, not only a marking-scale question. |
| R-3 | **V2-024** status cell reads *"Open — stops the handoff"* | The same file at `:1852` and `GSP-CRV2-06_COMPLETION_REPORT.md:31,70` record it closed by the funding-need rule. |
| R-4 | **V2-068** — closes once the worker *"is installed, enabled and verified active"* | Installed, enabled and active (05:27:05 UTC today, `NRestarts=0`). But `narrative_job` has **0 rows** — no job has ever run on this host — and `NARRATIVE_WORKER_OPERATIONS.md:22-40` still documents a different unit. Half-closable at best. |
| R-5 | **`LAUNCH_CHECKLIST_V2.md:16-28`** keeps `[x]` on operator concurrency | Its own amendment retracts the certifying count (*"rested on one false positive"*) and says *"this is a re-measurement, not a re-certification"*. The tick outran the evidence. It is now genuinely re-certified by §1.4 — but it was ticked before it was. |
| R-6 | The register at HEAD ends at **V2-095** (+V2-117) | **V2-096 through V2-116 exist only on the unmerged branch `crv2-register-backlog-2026-09-12`**, including **two open P0s** — V2-107 (the pricing screen's default row cannot be saved and the screen reports success) and V2-110 (zero production while solvent) — and eleven open P1s. An auditor reading only `crv2-release-integration` sees a register whose worst open item is V2-072. |
| R-7 | **V2-110** on that branch reads *"Open — not repaired"* | Its runtime repair `d1701e6` is **already merged into HEAD**, carrying **no finding ID at all** (`ZERO_PRODUCTION_DEFECT_2026-09-12.md:10-12`: *"I did not edit V2_FINDINGS_REGISTER.md"*). The release branch holds a fix for a P0 it does not record, while the register that records the P0 says it is unfixed. |
| R-8 | **V2-107**'s repair, likewise | `1855b25` repairs it (`MarketingPage.js:95` defaults `production_source_market`; `:152` `describeFailure`, `:167` `retrySave`, `:181` `autoSave` surface and retry a refused save instead of swallowing it; `serializers/decisions.py` relaxes the campaign-focus rule). Verified present at HEAD. Unregistered. |
| R-9 | CRV2-13 *"before/after"* browser evidence | `before-results-en.json` and `after-results-en.json` both carry `"revision": "135508e17114c842b6d818afa39978dc481ec2ca"`, which `git merge-base --is-ancestor 135508e 1855b25` confirms **predates the repairs by 8 commits**. The stamp cannot distinguish the repaired state from the unrepaired one; the "after" run was taken against an uncommitted tree. |
| R-10a | **V2-100 (P1, unmerged)** — *"the aide-checks pre-commit hook refuses every commit in this repository … the pre-commit layer has been bypassed on every commit all session and currently protects nothing"* | **Does not reproduce at `3c99d74`.** This report was committed through `.husky/pre-commit` with **no `--no-verify`**, and the hook passed: *"aide-checks: revision 77b8ced matches …/checks/.aide-checks-rev … ran 2, skipped 1, blocking failures 0"*. `d707141` ("re-vendor aide-checks@77b8ced (worktree hook false stale-runner fix)") appears to have fixed it. The entry is stale in the finding's favour and should be re-tested before it is carried forward — but note that `3d8c2b3`, `d1701e6` and the rest of that chain were nonetheless committed with `--no-verify`, so no check was run on them. |
| R-10 | `d1701e6`'s own message: *"Invalidates the stored R28 balance measurement, the stage-2 parity replays and any manifest hash for a game with a rounds 1-4 customs event"* | No file under `handoff_readiness_v2/evidence/calibration/` carries any invalidation marker. Known-invalid calibration evidence sits in the tree unmarked. |

---

## 4. New findings raised by this audit

Recorded, not repaired. IDs are proposed; the registrar assigns them.

| ID | Area | Sev | Finding | Evidence |
|---|---|---:|---|---|
| **A-01** | Determinism boundary / scoring isolation | **P0** | An LLM-derived number reaches a hashed, published, graded score. `communication_eval.py:34-49` → `coherence.py:145,163-168` → `manifest_sections.py:512` (hashed output) → `grading.py:206-220` (graded). Five assignments ship in every scenario and are live in the database. Contradicts V2-016's closure. Blast radius nil today only because `team_communication` is empty. | §V2-A above; `SELECT count(*) FROM team_communication` → 0; `communication_assignment` → 5 rows. |
| **A-02** | Scoring / perverse incentive | **P1** | The same blend is arithmetically backwards. `coherence_contribution` is `overall_score(0-1) × coherence_weight(0.03-0.08) × 100`, so the summed maximum across all five shipped assignments is **26**, against a `formula_score` on 0-100. `blended = 0.9×formula + 0.1×comm` therefore **lowers** the score of any team whose formula score exceeds its communication score — which is every plausible team. At the measured `tutor` mean of 0.129 (V2-117), a team with formula 60 that completes the assignments scores ~54.3; a team that ignores them scores 60. Doing the coursework is a dominated action, and it costs the strongest teams most. | `coherence.py:163-168`, `:275-284`; weights from `communication_assignment`; mean score from V2-117. |
| **A-03** | Release provenance | **P1** | Production names a commit that does not exist, and the guard cannot see it. `GIT_REVISION=86c2ad4…` is absent from the repository; `resolve_code_revision()` accepts it verbatim; `require_identified_build()` only tests the `-dirty` suffix, which production never produces, so `COMPETITION_REQUIRE_CLEAN_BUILD=true` is inert. Every stored manifest revision is likewise missing. | §V2-C; `resolution_manifest.py:96-128`; `build_identity.py:105-125`. |
| **A-04** | Provenance completeness | **P1** | Runtime configuration sits outside the certified source digest. `backend/.env` (0600, written 2026-09-16 05:27, gitignored) is loaded by `settings.py:23-26` and supplies `LLM_GATEWAY_URL`/`LLM_GATEWAY_KEY` and can supply `LLM_PURPOSE_MODELS` — which chooses the model that produces A-01's graded number. `build_identity.SOURCE_SUFFIXES` (`:33`) covers `.py/.json/.yaml/.yml/.cfg/.toml/.ini` only, so neither `.env` nor `requirements.txt` is inside `source_tree_sha256`. The auditor-preflight question *"does provenance identify runtime bytes, including required untracked files?"* is answered no. | `build_identity.py:27-59`; `settings.py:15-26,285-300`. |
| **A-05** | Verification / guard scope | P2 | The model-routing guards are substring scans with asymmetric coverage. `test_narrative_llm_routing.py:224-226` catches `import dashscope` and `from dashscope import` but only `import openai` — `from openai import OpenAI` is not matched, and no other provider SDK is named. `:238` requires the **single-quoted** literal `'/chat/completions'`, so a double-quoted occurrence passes. Scope is `core/**` plus `globalstrat/settings.py` only. Same class as V2-079. Separately, the deploy gate lives only in `frontend/deploy-frontend.sh`; there is no backend deploy script, so the path that actually ships backend code has no gate, and the gate itself silently no-ops if `_AIDE_ROOT` is empty (`:53`). | `core/tests/test_narrative_llm_routing.py:209-245`; `frontend/deploy-frontend.sh:39-87`; `ls deploy/ scripts/`. |
| **A-06** | Evidence reproducibility | P2 | The stored v6-envelope transcript does not run as written. `evidence/determinism/v6-envelope/README.md`'s Transcript section goes straight from `load_scenario` to `v6_envelope_fixture.py`, which fails with `CommandError: No superuser found. Create one first: manage.py createsuperuser` (`initialize_game.py:59`). The missing step is one line, but the preflight question is *"do README commands run exactly as written?"* | Reproduced 2026-09-16 on a disposable stack. |
| **A-07** | Harness isolation / backup hygiene | **P1** | The replay harness writes into the **live** backup root by default. `settings.py:35-36` defaults `COMPETITION_BACKUP_DIR` to `BASE_DIR/competition_backups`, and neither the fixture nor the stored transcript overrides it, so a run against a fully disposable database still deposited two pre-resolution dumps and two manifest bodies in the production backup directory — at `0664`, beside production dumps at `0600`, because the service's `UMask=0077` does not apply to a shell. This is the V2-062 / V2-065 pattern (a harness aimed at production) on a third file. I removed the four artifacts I created; their sha256s are recorded in this audit's scratch evidence, and the directory is back to 119 files / 15 manifests. | `settings.py:35-36`; `ls -lt backend/competition_backups/` before and after. |
| **A-08** | Rules governance | **P1** | A competition rule changed on the release branch with no dated ruling and no register entry. `1855b25` relaxed `DecisionMarketingSerializer.validate_campaign_focus_feature_ids` from *1-3 required* to *at most 3*, moving the requirement into `validate()` conditional on `promotion_budget > 0`. Campaign focus features feed `campaign_engine`. The change is defensible and probably right — which is exactly what V2-073 says is not the test. | `git show 1855b25 -- backend/core/serializers/decisions.py`. |
| **A-09** | Programme governance | P2 | The release candidate was not frozen. `08cfda5` landed on `crv2-release-integration` during this audit, and `7e3c296` moved the shared working tree onto another branch mid-run. Both are documentation-only and the runtime bytes were proven unchanged, but Phase 3 of the execution protocol requires a freeze commit and there is none. | §0.1. |

---

## 5. Verdict

# NO-GO

A prize competition cannot be run on `3c99d74`.

### Blocking items, in priority order

| # | ID | Sev | Item | Owner |
|---|---|---|---|---|
| 1 | **A-01** | P0 | An LLM's judgement of a free-text memo enters a hashed, published, graded number. Either disable the communication assignments for the competition (they are scenario data, so this is an authoring change) or move the contribution out of `blended_score`. Until then the determinism/isolation claim in V2-A and the closure of V2-016 are both false. | rules owner + CRV2-01 boundary |
| 2 | **V2-072** | P0 | The application connects as a role that can `SET ROLE postgres`, holds `CREATEROLE`/`CREATEDB` and 16 service-role memberships; no connection logging exists. R19 withdrew the acceptance. Run as a non-owner role. | DBA / operations |
| 3 | **V2-110** | P0 | A solvent team can still lose a whole round to zero production from round 5 on, and the inactivity controls then cost it up to 17.81 index points — more than the strongest decision lever is worth. `d1701e6` fixes rounds 1-4 only and leaves the classification untouched by design. | engine / rules owner |
| 4 | **V2-107** | P0 | Registered as an open P0 on an unmerged branch. Its repair is merged here and looks sound, but it has never been verified in a browser at a revision that contains it (R-9). Verify, then close. | CRV2-13 + registrar |
| 5 | **Register split** | P0-equivalent | `crv2-register-backlog-2026-09-12` is unmerged. Two P0s and eleven P1s are invisible from the release branch, and `d1701e6`/`1855b25` repair two of them without a register entry. **No GO decision can be taken against a register that does not contain the findings.** Merge and reconcile first. | registrar |
| 6 | **A-03 + V2-054** | P1 | Production provenance names a nonexistent commit; every stored manifest revision is unresolvable; the clean-build guard is inert in production; RD-03 would refuse recovery of every stored round. Set `GIT_REVISION` to a real commit, re-stamp the record, and make the guard verify rather than accept. | deployment owner |
| 7 | **A-02** | P1 | Completing a graded communication assignment lowers a team's coherence score. Fix the scale or the blend before any cohort submits. | rules owner |
| 8 | **Combined-load gate** | P1 | Deadline burst + refresh + Phase-1 resolution under load has never been driven, and the V2-063 409 refusal makes it materially different from what was measured. | CRV2-07 owner |
| 9 | **V2-064 / R17 frontend** | P1 | R17 requires the student be told and the edit retried on a contended save. Done on `MarketingPage.js`; the generic `DecisionContext` autosave path and the other decision pages are not covered. | decision-path + frontend |
| 10 | **V2-070 / R18** | P1 | Ruled, not implemented: `end_of_round` retirement must sell through the round. `immediate` remains dominated. | engine |
| 11 | **V2-088, V2-094, V2-080, V2-076, A-04, A-07, A-08** | P1 | Cash charged outside every calculator; a price charged without being shown; the operator's most destructive controls untranslated; `reset_simulation` still unscoped; provenance gaps; harness writing into the live backup root; an unruled rules change. | various, named in §3-4 |
| 12 | **Browser pass** | P1 | `LAUNCH_CHECKLIST_V2.md:74-81` is still unticked, and the evidence that exists is stamped with a revision that predates the repairs. Two of the four named screens (`ResultsPage` price-adjustment and not-for-sale notices) were never reachable on the verification pass. | CRV2-13 |

### What a competition could survive today

- **The engine's arithmetic.** 1013 backend tests green; a round resolved at
  these bytes replays byte-identically; a single tampered stored value is
  refused before the engine runs, including in the section added at v6.
- **Concurrent operators.** 0 unguarded of 219 mutating routes, re-certified
  here, with the inventory `--check` clean.
- **A model outage.** Resolution completes with no gateway configured and
  narratives fall back deterministically.
- **An instructor with a database console.** Admin is read-only or append-only
  across all 71 competition registrations.
- **Ordinary post-close dispute questions** — five of the six.

### What it could not survive

- **A graded communication assignment.** The first board memo submitted in round
  2 puts a model's score inside the hashed envelope and the grade, and lowers
  the team's coherence for having written it.
- **"Prove the calculation."** Every stored manifest names a code revision that
  no longer exists, so the replay that answers dispute 6 cannot be run at the
  revision the record cites.
- **A mid-competition recovery.** RD-03 refuses every recovery point on this
  host today, for the same reason.
- **A round in which a team produces nothing while solvent.** From round 5 on
  that still costs more than any decision can earn back.
- **A security review of the database role**, which can become `postgres`.
- **Its own record.** A GO taken against the register on this branch would be
  taken without two open P0s that exist on a branch nobody merged.

### One thing that should not be lost in the NO-GO

The work landed since 2026-09-12 is substantial and mostly sound: the first
green full suite this programme has ever had, a genuine v5→v6 replay regression,
the legacy cross-cohort reset deleted, the model-routing consolidation, the
narrative worker finally supervised, 19 migrations reconciled, and the
frontend defect repairs. Several builders recorded findings against their own
work that nobody would have found otherwise — `ZERO_PRODUCTION_DEFECT`'s
self-correction about the pre-commit hook and `PAID_RESEARCH_REPORTS`'s
*"the frontend is entirely unexecuted"* are the standard the rest of the
programme should be held to. The NO-GO is not a judgement on the effort. It is
that the remaining items are the ones a prize would find.

---

## 6. Reproduction

All commands below are read-only or run against disposable containers.

```bash
# full backend suite (took the host runner lock; 5m33s)
flock -w 1800 /tmp/globalstrat-backend-test.lock \
  bash -lc 'cd backend && ./scripts/test-postgres core'

# frontend
cd frontend/globalstrat-frontend && npm ci && CI=true npm test -- --watchAll=false && npm run build
node eslint-warning-count.js build.log
backend/scripts/check-participant-strings --repo .

# route inventory re-certification
cd backend && python3 manage.py dump_route_inventory --check

# independent same-host replay (disposable postgres:16-alpine, tmpfs, fsync=off)
python3 manage.py migrate --noinput
python3 manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml
python3 manage.py createsuperuser --noinput --username … --email …    # A-06: missing from the stored transcript
COMPETITION_BACKUP_DIR=<disposable path> \                            # A-07: NOT in the stored transcript
COMPETITION_REQUIRE_CLEAN_BUILD=true python3 ../handoff_readiness_v2/v6_envelope_fixture.py --teams 4
python3 manage.py replay_round --game-id 1 --round 1 --export-only --evidence-dir <dir>/recorded
COMPETITION_RECOVERY_ENABLED=true COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 manage.py replay_round --game-id 1 --round 1 --restore --confirm REPLAY-GAME-1-ROUND-1 \
  --expected-manifest <dir>/recorded/expected-manifest.json --evidence-dir <dir>/run-a \
  --require-env tz_env=UTC --require-env python=3.10.12 --wait-narrative 0
python3 ../handoff_readiness_v2/corrupt_research_purchase.py 1
python3 manage.py replay_round --game-id 1 --round 1 --verify-only \
  --expected-manifest <dir>/recorded/expected-manifest.json --evidence-dir <dir>/neg-tampered

# live database (read-only)
python3 manage.py migrate --check --noinput
psql … -c "SET default_transaction_read_only = on;" -c "<query>"
```

Live-database queries used: `django_migrations` by applied date; `pg_roles` /
`pg_auth_members` / `pg_has_role` for the application role; `pg_settings` for
connection logging and ssl; `competition_resolution_manifest`;
`narrative_job`; `team_communication`; `communication_assignment`; `round`.

**Deliverables this report does not produce, and why.** The packet also names
`V2_FINAL_READINESS_REPORT.md`, a reconciled findings register, a final launch
checklist and an immutable evidence index. A reconciled register cannot be
written while V2-096 through V2-116 sit on an unmerged branch and two merged
commits repair P0s that no register entry records; reconciliation is the
registrar's next task and blocking item 5. The launch checklist is likewise not
re-ticked here: §1.1 and §1.4 close two of its boxes on the evidence above, and
the auditor recording that in the checklist before the register is reconciled
would repeat the mistake R-5 documents.
