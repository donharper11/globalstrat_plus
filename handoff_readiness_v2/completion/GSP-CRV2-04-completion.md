# GSP-CRV2-04 — database-enforced audit integrity and read evidence

**Finding:** V2-007 (P1) — **closed**
**New finding raised:** V2-017 (P1) — logged, not repaired here
**Baseline:** `1752315` (branch `crv2-04-audit-integrity`, cut from `main`)
**Freeze commit:** `54a0d50` (clean tree, `git status --untracked-files=no` = 0)
**Runtime source digest:** `7f945727ad31c9af31c7132141687353357443599bed6afe1783e4269547b52f`
**Evidence:** `handoff_readiness_v2/evidence/audit-integrity/`

## What the finding was, and what decided the design

The audit models raised on a second `.save()`. That was the whole defence, and
it held for every write that went through the model layer — which is not the
same set as every write. `Model.objects.filter(...).update()`, `.delete()`,
raw SQL, `manage.py shell` and the admin all skip `save()`.
`ResolutionManifest` had no guard at any layer.

Phase 1 then established the fact that decided everything else: **the
application connects to PostgreSQL as the owner of the tables it audits**
(`donwh`; `pg_tables.tableowner` and `has_table_privilege` both confirm it, and
there were no triggers on any `competition_*` table). Revoking `UPDATE` and
`DELETE` from the connecting role achieves nothing while that role can grant
them straight back, and an owner can drop any trigger it is subject to.

So the work is deliberately split into two claims that are easy to blur:

| | Mechanism | Covers |
|---|---|---|
| **Rejected** | Triggers on all five audit tables: `UPDATE`/`DELETE` per row, `TRUNCATE` per statement | Every write the application can make, at any layer, for every role including the owner |
| **Detected** | Forward hash chain, head exported outside the database | The change made by whoever can drop the trigger first |

**Nothing rejects the second category, and this report does not claim it does.**
A privileged edit is caught after the fact, by a digest written down somewhere
the database cannot reach.

## Changed files

**New runtime**
- `core/models/audit_integrity.py` — `AuditChainEntry`, `SensitiveReadEvent`
- `core/services/audit_guards.py` — the trigger DDL, privilege reporting, role provisioning
- `core/services/audit_chain.py` — sealing, verification, canonical row projections
- `core/services/audit_anchor.py` — export and comparison against the external anchor
- `core/services/read_inventory.py` + `read_inventory.json` — generated sensitive-read inventory
- `core/management/commands/` — `seal_audit_chain`, `verify_audit_chain`, `export_audit_anchor`, `install_audit_guards`, `who_accessed`, `dump_read_inventory`
- `core/migrations/0069_audit_integrity.py`, `0070_audit_guards.py`, `0071_audit_truncate_guards.py`

**Modified runtime**
- `core/models/competition_audit.py` — schedule a seal after commit
- `core/services/resolution_manifest.py` — seal a manifest when it completes
- `core/middleware.py` + `globalstrat/settings.py` — `SensitiveReadLogMiddleware`
- `core/admin.py` — the five audit records registered read-only
- `core/services/route_inventory.json` — +5 admin routes, still **0 unguarded**
- `globalstrat/test_runner.py` — install the guards, and mark the test database

**Tests / evidence**
- `core/tests/test_audit_integrity.py` — 47 tests
- `handoff_readiness_v2/audit_integrity_evidence.py` — the harness
- `AUDIT_INTEGRITY_INVENTORY.md`, `AUDIT_INTEGRITY_OPERATIONS.md`, `V2_FINDINGS_REGISTER.md`

## Decisions worth reviewing

**The manifest is not simply immutable.** `ResolutionManifest` is written twice
by design — `prepare_manifest` before resolution, `complete_manifest` after — so
a blanket no-`UPDATE` rule would have broken round resolution. Its trigger
allows updates while `completed_at IS NULL` and freezes the row the moment it is
set. `DELETE` is refused at all times.

**Sealing runs after commit, not in the write.** The seal takes a global
advisory lock. Taking it inside an audit write would put it underneath the
operator lifecycle locks GSP-CRV2-02 certified, inverting a lock order that can
deadlock. `schedule_seal()` registers in `transaction.on_commit`, once per
transaction, and deduplicates by reading Django's pending-callback list rather
than setting a flag — because Django discards that list on rollback, so a
rejected operator action cannot leave a stale marker suppressing the next seal.
The preflight concurrency matrix (10 races/pair, 120 races) confirms no
deadlock was introduced.

**The trigger DDL is not only in the migration.** `manage.py test` builds its
database from the models with migrations disabled, so a guard living only in a
migration is a guard no test can observe. `core/services/audit_guards.py` is the
single source, applied by both the migration and the test runner.

**Read events are not sealed on the read path.** Sealing on every read would
take the global lock on a high-volume path. Read events are swept up by the next
audit write or by `seal_audit_chain`. The window is stated rather than papered
over: a read event written and then deleted before the next seal leaves no
trace.

**The read evidence stores no payload.** Actor, subject, route, status, outcome,
request id, time. No response body, header or token. Copying a team's decisions
into a second table in order to investigate their disclosure would widen the
exposure the table exists to investigate. No API route serves it; it is
reachable only through `manage.py who_accessed`, and a test asserts that.

## Defects found by this handoff's own certification

**`TRUNCATE` bypassed every guard.** The first certification run attempted each
bypass against a migrated database and one worked: `TRUNCATE` fires no
row-level trigger, so `0070`'s guards watched three audit rows disappear
without firing, and the chain reported them as `row_deleted` afterwards —
detection working, prevention absent. Fixed by a statement-level
`BEFORE TRUNCATE` trigger in `0071`, gated on a session setting so Django's
`TransactionTestCase` can still reset the database. That gate is the reason the
guard is testable at all rather than installed where no test could reach it.

Two harness defects were found in the same run and fixed: the walkthrough
assumed a migrated database can serve a request (ten models are `managed=False`
— `users`, `enrollment`, `course`, `section` and the grading tables — so they
exist only where raw SQL created them), and the negative transcripts ran before the clean baseline was
anchored, so an attack could be mistaken for the cause of a verification
failure.

## What the final read found, and what that says about the tests

Reading every new file end to end before submitting caught a defect no test
would have: the fix that made the inventory fast changed `logged_routes()` and
left `SensitiveReadLogMiddleware` calling the live 6.3-second scan. The test
written for that fix passed, because it asserted on the helper the middleware
was *supposed* to call rather than on the middleware. The focused module ran
76 s before the correction and 28 s after — the scan was being paid on the
first sensitive read of every test class that made one.

The test now drives `middleware._sensitive()` directly. The general lesson is
in the docstring: a test aimed at the helper rather than the caller proves the
helper.

The heavier finding came from reordering the harness. Moving the deliberate
tamper to the end meant asking which checks needed a healthy chain, and that
question exposed a **false claim in the anchor verification**:
`verify_against_anchor()` compared the stored head with the anchored head and
recomputed that single entry *from its own stored fields*. That proves the
chain row was not edited and says nothing whatever about the audit rows beneath
it. A row modified three entries below the head passed the anchor check
cleanly — the earlier evidence file shows exactly that, `"anchor": {"ok":
true}` beside `"chain": {"ok": false}`. The module docstring asserted "one
matching head covers the whole prefix", which was the intended property and not
the implemented one.

It now replays every sealed entry from the rows the database holds today and
compares the resulting head. Three tests cover a row edited below the head, a
row deleted below the head, and a chain entry removed below the head; all three
fail against the previous implementation and pass against this one. The overall
command always reported the tamper, because `verify_chain()` catches it
independently — but a defence-in-depth design in which one of the two layers
silently does not work is worth knowing about before a dispute, not during one.

The same pass added `UNCHAINED_FIELDS`. Seven manifest columns are outside the
chain — three covered by their own digests, three paths to content those
digests commit to, and `environment`, which is outside every hash by design.
All seven were correct and none were written down, which is the state in which
an omission nobody recorded is indistinguishable from one nobody noticed. A
test now fails if a new column joins neither list.

## V2-017, raised while building the inventory

The route inventory that certified "0 unguarded mutating routes" inspects only
routes whose callback exposes a view class. Django admin's add/change/delete
views are function-based: `_walk` yields 778 routes, 371 have no view class and
are skipped, and **216 of those are admin write views** — including `Game`,
`Round`, `Team`, `DecisionSubmission`, `ActiveModifier` and `SCEventInstance`.
The `<path:object_id>/` routes that do appear resolve to `RedirectView` and are
reported `lifecycle_mutating: false`. A staff account can therefore move round
state through `/admin/` with no lifecycle lock and no `OperatorAuditEvent`.

Reach is limited to Django `is_staff` accounts, not the JWT instructor role, so
P1 rather than P0. Logged and not repaired here: the fix belongs to V2-004's
boundary, and changing that boundary in this handoff would invalidate the
concurrency certification GSP-CRV2-02 produced. What was repaired is the part
inside this scope — the five audit-record admins are read-only, and the
triggers refuse the writes regardless.

## Still open, deliberately

The application holds the owning credentials.
`install_audit_guards --role-sql globalstrat_app` provisions a non-owner role,
the SQL is in the evidence and its shape is tested, but pointing the
competition stack at that role is a deployment action, not a code change. Until
it is done, the reject layer is the triggers alone. Recorded in
`AUDIT_INTEGRITY_OPERATIONS.md` under "Deployment action still open".

## Commands, in the order they ran

Certification ran from `54a0d50`. Five earlier freeze candidates were
abandoned, each returning to Phase 3 rather than patching a certification in
progress:

| Candidate | Why it was abandoned |
|---|---|
| `08c10d9` | Certification found `TRUNCATE` bypassed every guard |
| `db2fd08` | Reviewing the artifacts found a 6.3-second lazy inventory build |
| `286beaa` | The guard report listed every table twice, which reads like a double registration |
| `02c2772` | A file-by-file read before submitting found the middleware still calling the slow scan (below) |
| `e58f9f2` | Tracing the harness's own step order found that anchor verification could not detect a tampered row below the head (below) |

The full backend suite ran once from `54a0d50`. Two earlier full-suite runs
were started and stopped: the first because its output was piped through
`tail -80` and fixture logging pushed the summary out of the window, the second
because the anchor defect above was found while it was in flight. Stopping a
suite whose result would have to be discarded is cheaper than finishing it, and
both are recorded here rather than presented as a single clean run.

The harness was paid seven times across six freeze candidates. That is the cost
of returning to Phase 3 instead of patching a certification in progress, and the
alternative — certifying `02c2772` or `e58f9f2` and repairing afterwards —
would have submitted evidence for code this report then contradicted, including
a security claim that was not true.

```bash
# 1. static guards
python3 manage.py dump_route_inventory --check     # current, 0 unguarded
python3 manage.py dump_read_inventory --check      # current
python3 manage.py dump_manifest_schema --check     # current
python3 manage.py makemigrations --check --dry-run # no changes
python3 manage.py check                            # 0 issues

# 2. release-scale harness, against a database it creates and drops
python3 handoff_readiness_v2/audit_integrity_evidence.py

# 3. full backend suite, once
python3 manage.py test core --noinput
```

| Run | Count | Duration |
|---|---:|---:|
| Focused `test_audit_integrity` (final) | 53 tests | 28.7 s |
| Focused regression: hardening + determinism + durable narratives | 97 tests | 142.5 s |
| Preflight concurrency sample (10 races/pair, 120 races) | 31 tests | 93.4 s |
| Evidence harness (23 steps, all as expected) | — | ~55 s |
| **Full backend suite** | **447 tests, OK** | **243.8 s** |

Deliberately **not** run, per `EXECUTION_PROTOCOL.md`: CRV2-01's
four-environment replay matrix, CRV2-02's 100-races-per-pair matrix, CRV2-03's
SIGKILL and live-provider drills. Certification is task-local; GSP-CRV2-09
regenerates the integrated set.

## Auditor preflight checklist

| Question | Answer |
|---|---|
| Did inventory start from registered routes/models, not from code using the new abstraction? | Yes — `urls.py`, the model registry and `pg_catalog`. It found two detector bugs before any code was written: substring matching flagged `DecisionLockedMixin` as a decision reader, and a class-only scan missed `RoundControlView`'s module-level helper. |
| Is there an active legacy or alternate entry point? | Yes, two. Raw SQL and `manage.py shell` — covered by the triggers. Django admin — 216 write routes the lifecycle inventory cannot see, logged as **V2-017**. |
| Does a failure/refusal audit survive rollback? | Yes. Read events are written by middleware after the response, outside the view's transaction; a 403 leaves a `denied` row, proven end to end in the walkthrough. |
| Is each correlation ID generated once and identical everywhere? | Yes — `request_id_for` from GSP-CRV2-02, cached on the request. The walkthrough shows one `srv-…` id per read. |
| Is background/external work delayed until the outer transaction commits? | Yes — `transaction.on_commit`, once per transaction, tested three ways including that a failed seal never breaks the write it followed. |
| Do claimed environment values describe the executing process? | Yes — `provenance.json` records the revision, source digest, clean-tree state and database name observed by the harness process. |
| Does provenance identify runtime bytes? | Yes — `source_tree_sha256`, and the harness refuses to run from a dirty tree. |
| Do README commands run exactly as written? | Yes — `evidence/audit-integrity/operations-guide-commands.txt` is a transcript of every command in `AUDIT_INTEGRITY_OPERATIONS.md` not already exercised elsewhere in the run, executed verbatim. The claim was overstated when first written; the harness step exists because checking it found three commands with no transcript. |
| Do P0/P1/P2 labels match their definitions? | V2-017 is P1: it degrades the audited boundary but reach is limited to Django `is_staff`, not the instructor role. |
| Does each negative test prove mutation did not occur? | Yes — every rejection test re-reads the row and asserts the original value. The `TRUNCATE` test additionally asserts on the guard's own message, because PostgreSQL refuses `TRUNCATE` while FK trigger events are pending and an assertion satisfied by that refusal would pass with no guard installed. |

## Rollback

`0071` and `0070` reverse by dropping the triggers and functions; `0069` drops
two new tables. No existing audit row is rewritten in either direction, and
nothing backfills the chain — rows written before the chain existed are sealed
by the first `seal_audit_chain` and are not retroactively claimed to have been
protected earlier than they were.

## Unresolved risks

1. **The application still owns its audit tables.** Deployment action, above.
2. **V2-017** leaves the admin outside the audited lifecycle boundary.
3. **A read event deleted before the next seal leaves no trace.** Sealing on the
   read path would take a global lock on a high-volume route; the window is one
   audit write or one `seal_audit_chain` run.
4. **The anchor schedule is the security property.** An anchor exported after a
   tampering event certifies the tampered state. Stated in the operations guide;
   not enforced by code.
5. **`outcome='error'` is reachable but untested.** The middleware maps a 5xx
   on a sensitive route to `error`; `allowed` and `denied` are both proven end
   to end, that third branch is not. It affects only how an operator report
   labels the row, never whether the row is written, so it was not worth
   another freeze cycle to cover — but it is an untested branch and is named
   here rather than left to be discovered.
6. **Each logged read costs one INSERT.** 30 routes, some polled by the
   frontend. Bounded at competition scale, unmeasured under GSP-CRV2-07's load
   ceiling — that handoff should watch it.
7. **Verification loads every audit row into memory.** Both `verify_chain()`
   and `verify_against_anchor()` build a per-table cache to recompute digests.
   At competition scale that is tens of megabytes; over a long-running
   deployment accumulating read events it would grow without bound. These are
   operator commands, not request-path code, so it is a scale limit rather than
   a defect — but a verification that cannot run is a verification nobody will
   run, and archiving by round (the retention procedure) is what keeps it
   inside that limit.
