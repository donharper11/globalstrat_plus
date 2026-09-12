# V2-048 operations review — application-role privilege and audit gap

Date: 2026-09-05

Scope: read-only review of the live GlobalStrat+ deployment and its PostgreSQL
role. No database role, database configuration, credential, or service setting
was changed by this review.

## Deployment recovery verified

After the production secret file was corrected and
`globalstrat-backend.service` restarted, the service received a new process ID.
A deliberately nonexistent login returned its expected `401` response rather
than a database `500`. The prior database authentication failure is therefore
recovered for the GlobalStrat+ backend.

## Finding — P0: the shared application role can assume the database superuser

The GlobalStrat+ runtime connects as PostgreSQL role `donwh`. It is an
application credential shared by GlobalStrat+, GlobalStrat v1, and BECSR; it is
not merely a human administrator identity. The credential was the subject of
V2-048's repository exposure and must therefore be assessed as an application
secret with the privileges an attacker would receive if it were compromised.

Read-only PostgreSQL metadata established:

- `donwh` is not marked `SUPERUSER`, but is a member of the `postgres` role.
- `postgres` is a superuser role; `donwh` both inherits its privileges and can
  `SET ROLE postgres`.
- `donwh` directly has `CREATEROLE` and `CREATEDB`.
- `donwh` has server-file-read capability and can create objects in the current
  database and `public` schema.
- The role has memberships in several unrelated service roles. Because this is
  a shared application login, revoking any membership must be checked against
  all three consumers rather than inferred from GlobalStrat+ alone.

This is not a concern about the human named by the role. It is a least-privilege
failure: a runtime password previously exposed in source history can become
database-superuser authority and potentially reach unrelated databases.

## Access-log result

PostgreSQL reports:

- `log_connections = off`
- `log_disconnections = off`
- `logging_collector = off`
- `log_destination = stderr`
- `pg_current_logfile()` is empty

There is therefore no PostgreSQL connection-history record from which to assess
whether the exposed credential was used from unexpected sources. The requested
historical access-log review cannot be completed retrospectively. The database
administrator must choose and operate a forward-looking connection-audit and
retention control.

## Additional transport observation

The database accepts TLS, but presents a self-signed certificate. GlobalStrat+
connects with `sslmode=require`, which encrypts the connection without verifying
the server's identity. This is a separate hardening item: deploy a trusted CA
or pinned certificate and use `sslmode=verify-full` after validating the host
name and rollout path.

## Required DBA-approved remediation

1. **Immediately remove superuser reachability** from `donwh`: revoke its
   membership in `postgres` and verify it can neither inherit nor `SET ROLE`
   to that role.
2. Remove `CREATEROLE`, `CREATEDB`, server-file-read capability, and any other
   privilege not demonstrably required by each consumer.
3. Inventory the existing memberships and object/database grants for
   GlobalStrat+, GlobalStrat v1, and BECSR. Replace the shared role with
   separate, schema-scoped runtime roles where practical; do not remove a
   needed grant blindly from a live shared login.
4. Enable retained connection/audit logging, or a host-level equivalent, that
   records timestamp, database role, source address, database, and connection
   outcome. Define retention and access ownership before enabling it.
5. Deploy verified TLS identity validation after the least-privilege change.
6. Validate each consumer after every privilege change with its supported,
   non-destructive health/identity route. A GlobalStrat+ invalid-login probe
   must return `401`, not `500`.

## Re-audit evidence required

- DBA metadata showing `donwh` cannot inherit or `SET ROLE postgres`, cannot
  create roles/databases, and lacks server-file-read capability.
- A documented minimum grant set for each consumer, with separate roles or a
  justified temporary shared-role exception.
- A forward-looking connection-audit configuration and a sample redacted log
  entry.
- Successful non-destructive checks for GlobalStrat+, v1, and BECSR after the
  privilege change.
- Verified TLS identity configuration, or an explicit, time-bounded exception.

## Disposition

V2-048 credential rotation recovery is verified for GlobalStrat+. Its
access-log and least-privilege review remains open as an operational hardening
backlog. On 2026-09-05, the competition owner explicitly accepted that residual
risk and ruled that it is **not a competition-release blocker**. The DBA
remediation and re-audit evidence remain required before this operations finding
can be closed; they are not a condition of the current competition-readiness
decision.
