# GSP-CRV2-08 checkpoint 2 — REWORK 3

## Decision

**FAIL / REWORK**

Revision audited: `5a777ba`.

The V2-034 refusal capture itself works: 37/37 foreign writes are refused, recorded and non-mutating. The checkpoint fails because the report claims the new table is database-protected and audit-chained, while neither property is fully installed on the production upgrade path.

## Blocking defect 1 — migration does not install database guards

Migration `0078_authorization_refusal_event.py` creates `competition_authorization_refusal_event` but installs no UPDATE/DELETE or TRUNCATE triggers. Merely adding the table to `audit_guards.PROTECTED_TABLES` affects the test runner and future `install_audit_guards` commands; it does not alter an already migrated competition database.

The focused audit-integrity tests mask this because the custom test runner installs the current live guard list after creating its test database.

Add a forward migration that installs the append-only and no-TRUNCATE triggers for the new table on an ordinary upgrade. Its reverse must remove only this table’s triggers; it must not uninstall guards from the existing audit tables.

## Blocking defect 2 — refusal rows are not scheduled for sealing

The table is present in `audit_chain.PROJECTIONS` and `SEAL_ORDER`, so a later manual or unrelated seal pass can include it. But `AuthorizationRefusalEvent.save()` and the middleware creation path never call `audit_chain.schedule_seal()`. A final refusal can therefore remain unsealed indefinitely, contradicting the report’s claim that these rows are chained and tamper-evident like the other audit records.

Schedule sealing after a successfully created refusal, using the existing on-commit mechanism so the chain lock is never held with request/lifecycle locks. Do not seal inside the write transaction.

## Focused acceptance

Prove only:

1. applying migrations to a disposable database installs both new-table triggers without running `install_audit_guards` manually;
2. `install_audit_guards --check` passes immediately after migration;
3. direct SQL/ORM UPDATE and DELETE are refused for the new table;
4. TRUNCATE is refused under the established non-test policy;
5. reversing the new guard migration removes only the new table’s triggers and leaves existing audit-table guards present;
6. committing a refusal schedules one seal callback and produces an `AuditChainEntry` for that refusal;
7. chain verification reports no unsealed refusal row after the callback runs;
8. rollback does not create a chain entry for a row that did not commit.

Use focused migration/guard/chain tests and a disposable database walkthrough if needed. Do not rerun the 37-write ownership scan: its refusal-recording claim is already accepted and these changes do not alter authorization or response behavior.

## Documentation

Update the V2-034 closure and checkpoint report to name the guard-install migration and automatic seal proof. Do not claim that listing a table in a registry alone installs protection.

## Verification budget

Run only the new focused migration/guard/chain tests, directly affected audit-integrity tests, migration/static checks, `git diff --check`, clean-tree and checksum verification.

Do not run browser paths, fixture setup, ownership scans, full suites, load, determinism, concurrency, provider or failure drills. Step 6 remains stopped until this checkpoint passes.
