# Audit integrity and read evidence — operations

Covers the append-only guards, the tamper-evidence chain, its external anchor,
and the record of who read a team's decisions.

## What is protected, and by what

| Layer | Stops | Does not stop |
|---|---|---|
| `Model.save()` guard | Re-saving an audit object | Anything that skips the model layer |
| Append-only triggers | `UPDATE`/`DELETE` from the ORM, raw SQL, admin, `psql`, `manage.py shell` — for every role, owner included | Someone who drops the trigger first |
| Non-owner application role | The application dropping a trigger at all | Maintenance credentials |
| Hash chain + external anchor | Nothing | Nothing — it **detects**, after the fact, and that is its whole job |

Nothing rejects a change made by someone holding the database owner's
credentials. The chain does not pretend otherwise: it makes such a change
visible afterwards by disagreeing with a digest written outside the database.

## Daily operation

Sealing is automatic. Every decision-audit and operator-audit write schedules a
seal in `transaction.on_commit`, and a completed resolution manifest does the
same. Read events are swept up by the next seal.

Sealing is deliberately **after commit**, never inside the writing transaction:
the seal takes a global advisory lock, and taking it underneath the operator
lifecycle locks certified by GSP-CRV2-02 would invert a lock order and could
deadlock. One seal is scheduled per transaction, not one per row.

### Scheduled

```bash
# After each round resolves, and before any privileged maintenance:
python3 manage.py export_audit_anchor

# Hourly, or before answering any dispute. Exits non-zero on a problem:
python3 manage.py verify_audit_chain

# Catch-up after a crash, a data migration or a raw-SQL insert:
python3 manage.py seal_audit_chain
```

`export_audit_anchor` seals first, then writes the chain head to
`<COMPETITION_BACKUP_DIR>/audit-anchors/anchor-<seq>.json` with a `.sha256`
sidecar, plus `latest.json`. Both are written to a temporary file, `fsync`ed,
renamed, and the directory `fsync`ed, so a power loss cannot leave a half-file.

**The anchor schedule is the whole security property.** An anchor exported
after a tampering event certifies the tampered state. Export before
maintenance, not after.

### Verifying the guards themselves

```bash
python3 manage.py install_audit_guards --check       # exits 1 if any is missing or disabled
python3 manage.py install_audit_guards --privileges  # who holds UPDATE/DELETE
```

`--check` belongs in the same schedule as `verify_audit_chain`: a dropped
trigger is silent, and the chain only notices the edit that follows it.

### After restoring a database

`restore_database` drops and recreates the public schema. A dump taken after
migration `0070` carries the triggers with it, but a dump taken before it does
not — so after any restore:

```bash
python3 manage.py install_audit_guards
python3 manage.py verify_audit_chain --skip-anchor
```

Then compare against the anchor that predates the restore. A restore is a
legitimate privileged change; the point is that it is visible as one.

## Answering "who accessed Team X, Round Y?"

```bash
python3 manage.py who_accessed --game 12 --team 34 --round 3
python3 manage.py who_accessed --game 12 --team 34 --outcome denied
python3 manage.py who_accessed --user 87 --since 2026-09-01T00:00:00Z --json
```

Every registered route that can serve a team's raw decisions or an audit
payload is recorded — the list is `backend/core/services/read_inventory.json`,
generated from the URL conf, not hand-kept. Refused attempts are recorded
alongside successful reads, because a rival who tried and was denied is part of
the answer a disclosure dispute needs.

**What is stored:** actor id and username at the time, game/team/round read,
route pattern, endpoint path, method, status, outcome, request id, server time.

**What is not stored, deliberately:** the response body, any decision value,
any header, any token. Copying a team's decisions into a second table in order
to investigate their disclosure would widen the exposure the table exists to
investigate. The request id correlates a read with the operator and decision
audit rows from the same request, which is where payload detail lives if it is
needed.

## Retention and access control

| Record | Retention | Who may read |
|---|---|---|
| `competition_decision_audit_event` | Life of the competition + 1 year (dispute window) | Instructors of the owning course; operators |
| `competition_operator_audit_event` | Same | Same |
| `competition_resolution_manifest` | Permanent — it is the reconstruction record | Same |
| `competition_sensitive_read_event` | 1 year | **Operators only**, via `who_accessed`. Not exposed by any API route |
| `competition_audit_chain` | Permanent | Operators |
| `audit-anchors/` | Permanent, backed up off-host | Operators |
| `recovery-audit.jsonl` | Permanent | Operators |

No API route serves `SensitiveReadEvent`. It is reachable only through
`who_accessed` on the host, so the record of who read what does not itself
become something to read.

Deletion for retention is a privileged action that breaks the chain by design.
Expire whole rounds by archiving the rows and their anchors together, and
record the action in `recovery-audit.jsonl` before performing it, so the
resulting verification failure has a documented cause. Do not delete rows to
tidy up.

## Deployment action still open

The application connects to PostgreSQL as `donwh`, which **owns** the audit
tables. The triggers protect it from every write path, but an owner can drop a
trigger, so the application currently holds credentials it should not.

```bash
python3 manage.py install_audit_guards --role-sql globalstrat_app
```

prints the SQL: create a login role, grant it ordinary table access, revoke
`UPDATE`, `DELETE` and `TRUNCATE` on the five audit tables, and set default
privileges for future tables. Run it as the owner, then point the competition
stack's `DATABASE_URL` at the new role and restart. Verify with:

```bash
python3 manage.py install_audit_guards --privileges
```

Until that switch is made, the reject layer is triggers alone.

## Migration and rollback

* `0069_audit_integrity` creates `competition_audit_chain` and
  `competition_sensitive_read_event`. No existing table is altered.
* `0070_audit_guards` installs the trigger functions and triggers. Reversible;
  the reverse drops them and rewrites nothing.

Existing audit rows are preserved by both, and neither backfills the chain:
rows written before the chain existed are sealed by the first
`seal_audit_chain`, which anchors them from that point forward. Rows are not
retroactively claimed to have been protected earlier than they were.

The append-only trigger DDL lives in `core/services/audit_guards.py`, not only
in the migration, because `manage.py test` builds its database from the models
with migrations disabled. Both the migration and the test runner install from
that module, so the guards a test exercises are the guards production has.
