# GSP-CRV2-04 — database-enforced audit integrity and read evidence

**Finding:** V2-007 (P1) — **closed**
**New finding raised:** V2-017 (P1) — logged, not repaired here
**Baseline:** `1752315` (branch `crv2-04-audit-integrity`, cut from `main`)
**Freeze commit:** `db2fd08`
**Runtime source digest:** `53bca53cbe952f91b6167e0c05831070c3c3ffd19e0b2523582ed98031e06c9a`
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
| **Rejected** | Triggers on all five audit tables | Every write the application can make, at any layer, for every role including the owner |
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
assumed a migrated database can serve a request (roughly fifty models are
`managed=False`, so `users`, `enrollment` and `course` exist only where raw SQL
created them), and the negative transcripts ran before the clean baseline was
anchored, so an attack could be mistaken for the cause of a verification
failure.

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
