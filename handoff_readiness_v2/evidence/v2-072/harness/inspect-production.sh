#!/usr/bin/env bash
# V2-072 — READ-ONLY inspection of the competition database's role privileges.
#
# Every statement here is a SELECT against a catalog. Nothing is created,
# altered, dropped or granted. Run it to reproduce
# ../production-inspection.txt.
#
# The credential is read from the running service's own environment, so it is
# never typed, never stored by this script and never printed: only a 12-hex
# digest prefix, which identifies a value without disclosing it.
set -uo pipefail

HOST="${PGHOST:-192.168.50.38}"
PORT="${PGPORT:-5432}"
ROLE="${PGUSER:-donwh}"
DB="${PGDATABASE:-globalstrat_plus}"
UNIT="${SERVICE_UNIT:-globalstrat-backend.service}"

PID="$(systemctl show -p MainPID --value "$UNIT")"
PGPASSWORD="$(tr '\0' '\n' < "/proc/$PID/environ" | sed -n 's/^DB_PASSWORD=//p' | head -1)"
export PGPASSWORD
[ -n "$PGPASSWORD" ] || { echo "cannot read DB_PASSWORD from $UNIT (pid $PID)"; exit 2; }
echo "credential digest12: $(printf '%s' "$PGPASSWORD" | sha256sum | cut -c1-12)"

q() { psql -h "$HOST" -p "$PORT" -U "$ROLE" -d "$DB" -X -tAF'|' -c "$1" 2>&1; }

echo "=== identity/version ==="
q "select current_user, current_database(), version()"

echo "=== role attributes for $ROLE ==="
q "select rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
          rolreplication, rolbypassrls, rolconnlimit
     from pg_roles where rolname = current_user"

echo "=== direct memberships ==="
q "select r.rolname as member_of, m.admin_option from pg_auth_members m
     join pg_roles r on r.oid = m.roleid
     join pg_roles u on u.oid = m.member
    where u.rolname = current_user order by 1"

echo "=== reachable privileged roles ==="
q "select rolname, pg_has_role(current_user, oid, 'USAGE') as inherits,
          pg_has_role(current_user, oid, 'MEMBER') as can_set_role
     from pg_roles where rolsuper or rolcreaterole or rolcreatedb order by rolname"

echo "=== predefined role membership ==="
q "select rolname, pg_has_role(current_user, rolname, 'USAGE')
     from pg_roles where rolname like 'pg\\_%' order by 1"

echo "=== owner of the audit tables ==="
q "select tablename, tableowner from pg_tables
    where tablename in ('competition_decision_audit_event',
                        'competition_operator_audit_event',
                        'competition_sensitive_read_event',
                        'competition_authorization_refusal_event',
                        'competition_audit_chain',
                        'competition_resolution_manifest') order by 1"

echo "=== schema public owner + acl ==="
q "select n.nspname, pg_get_userbyid(n.nspowner), n.nspacl::text
     from pg_namespace n where n.nspname='public'"

echo "=== database owner + acl ==="
q "select datname, pg_get_userbyid(datdba), datacl::text
     from pg_database where datname=current_database()"

echo "=== table owners in public ==="
q "select tableowner, count(*) from pg_tables where schemaname='public'
    group by 1 order by 2 desc"

echo "=== login roles on the server ==="
q "select rolname, rolsuper, rolcreaterole, rolcreatedb
     from pg_roles where rolcanlogin order by 1"

echo "=== non-template databases ==="
q "select count(*) from pg_database where not datistemplate"

echo "=== relevant GUCs ==="
q "select name, setting from pg_settings
    where name in ('log_connections','log_disconnections','logging_collector',
                   'ssl','listen_addresses','password_encryption',
                   'log_destination','log_statement')"

echo "=== extensions installed ==="
q "select extname from pg_extension order by 1"

echo "=== audit guard triggers present ==="
q "select c.relname, t.tgname, t.tgenabled from pg_trigger t
     join pg_class c on c.oid=t.tgrelid
    where not t.tgisinternal
      and (t.tgname like '%_append_only' or t.tgname like '%_no_truncate')
    order by 1,2"

echo "=== default privileges recorded in public ==="
q "select pg_get_userbyid(defaclrole), defaclobjtype, defaclacl::text
     from pg_default_acl"
