# GSP-CRV2-04 audit decision — FAIL / focused rework

**Audited freeze:** `54a0d50`  
**Completion commit:** `cfb261c`  
**Decision:** **FAIL / REWORK**

The hash-chain replay, external anchor, sensitive-read inventory, read tooling,
and UPDATE/DELETE guards are sound in the reviewed paths. One application-level
TRUNCATE bypass invalidates the submitted rejection claim.

## Blocking defect — caller-controlled TRUNCATE bypass

`core/services/audit_guards.py::competition_audit_reject_truncate()` permits
TRUNCATE whenever this expression is true:

```sql
current_setting('globalstrat.allow_truncate', true) = 'on'
```

PostgreSQL custom settings can be set by an ordinary session. The application
currently connects as the table owner and therefore has TRUNCATE privilege. The
same application/raw-SQL context the handoff claims to reject can execute:

```sql
SET globalstrat.allow_truncate = 'on';
TRUNCATE competition_decision_audit_event;
```

No trigger must be dropped and the TRUNCATE guard returns without rejecting the
statement. This contradicts the completion report's claim that triggers reject
every application write, including TRUNCATE. A previously exported anchor may
detect the loss later, but detection is not the claimed reject layer.

## Required repair

- Make the test reset exception impossible in a competition database. A
  caller-settable setting alone cannot authorize audit destruction.
- A small acceptable design is to require both the explicit test-reset setting
  and a database identity that the application session cannot turn into a
  production bypass (for example, the isolated Django test-database naming
  contract). A cleaner design may temporarily remove/reinstall guards from the
  test runner while flushing. Choose the smallest robust mechanism.
- Ship the corrected trigger function to existing databases through a new
  migration; changing only the Python DDL source does not update installed
  production functions.
- Add a negative test using the current application/owner connection: set the
  custom setting to `on` in a non-test evidence database, attempt TRUNCATE, and
  prove rejection plus row preservation.
- Keep Django test teardown working and retain the legitimate isolated-test
  reset path.
- Update the completion/evidence record to state the corrected condition
  precisely.

## Proportionate verification

1. Focused trigger tests, including normal TRUNCATE rejection, attempted setting
   bypass, and permitted isolated-test cleanup.
2. One migrated disposable-database negative walkthrough proving the exact SQL
   above is rejected and the row remains.
3. Migration/static checks and `git diff --check`.
4. Freeze, record the runtime digest, and checksum only the rework evidence.

Do not rerun the full backend suite, concurrency matrix, determinism matrix,
narrative drills, complete read walkthrough, or all 23 evidence steps. The final
integrated suite belongs to GSP-CRV2-09.

## Other audit conclusions

- V2-017 is a valid separate P1 finding against the lifecycle boundary. It does
  not invalidate CRV2-04's read-only audit-record admin or database audit-table
  protections.
- The non-owner application role remains a launch deployment action already
  recorded in the checklist; this rework does not deploy it.
- Existing evidence checksums and provenance were structurally consistent.

