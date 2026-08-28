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
| V2-009 | Frontend verification environment | P1 | Lockfile selects `react-router-dom` 7.1.1 (Node >=20), but the VM runs Node 18.20.8. Production build completes, while Jest cannot resolve the router and one suite cannot start. | `npm install` reports EBADENGINE; `CI=true npm test -- --watchAll=false` has 1 pass / 1 load failure. | Open |

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
| V2-010 | RNG cohort key | **P1** | Competition-rules owner (via GSP-CRV2-09) | Two different cohort keys are in use. `core/engine/rng.py` seeds on `game.section_id or game.id`; `sc_engine._seed()` and `compliance_engine` seed on `game.id`. Two sections of one class running the same scenario therefore receive the same event stream but different supply-chain and compliance streams. Escalates to **P0** if parallel sections are ever scored against one another, because the disruption exposure they face would differ by construction. | Compare `core/engine/rng.py` with `core/engine/sc_engine.py:_seed` and `core/engine/compliance_engine.py`. | Open — rules decision required, see disposition below. |
| V2-011 | Shared RNG stream | **P1** | Competition-rules owner (via GSP-CRV2-09) | The supply-chain and compliance passes consume a single `random.Random` across all teams, so draw *n* belongs to whichever (team, regime, market) triple reaches the roll *n*-th. Iteration order is now explicit and replay is exact, but adding or withdrawing a team shifts every later team's draw — one team's presence changes another team's outcome. | `core/engine/compliance_engine.py:enforce_compliance`; `core/engine/sc_engine.py:run_sc_state`. | Open — rules decision required, see disposition below. |
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

## Scope notes

- The Phase-2 LLM path is outside the existing output hash and is dispatched only after the deterministic transaction commits. No LLM value is read by the Phase-1 scoring call graph. This part of the v1 claim is structurally sound, subject to outage/restart verification.
- Wall-clock values are lifecycle/audit metadata or duration fields. They are excluded from the competitive hash by rule (`manifest_sections.MEASURED_TIME_FIELDS`) and kept in the input envelope as frozen facts about the starting state.
- The unordered-query sweep is complete: 168 iterated querysets in `core/engine/` had no explicit ordering — 93 written inline and 75 reached through a local name, the second group found only after a cross-environment replay failed (V2-012). All now declare one except six documented exemptions whose result cannot depend on order. See `ORDERING_AUDIT.md`. An AST test fails the suite on any new unordered loop in either form, and a forward/reverse insertion test re-runs the whole Phase-1 pipeline over reordered rows.
