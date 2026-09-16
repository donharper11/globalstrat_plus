#!/usr/bin/env bash
# V2-072 — provision the least-privilege GlobalStrat+ application role.
#
#   ops/provision-app-role.sh [--check] [--revoke] [--drop-role]
#                             [--password-file PATH] [--generate-password PATH]
#
# The application has always connected as `donwh`, which owns the database and
# every table in it, is a member of the `postgres` superuser role, and holds
# CREATEROLE and CREATEDB. The audit guards in core/services/audit_guards.py are
# written on the assumption that the writer cannot drop them; an owner can. This
# script creates the role that makes that assumption true.
#
# WHAT IT DOES NOT DO. It does not touch `donwh`. That role is shared by
# GlobalStrat+, GlobalStrat v1 and BECSR, so narrowing it is a separate,
# DBA-owned change with three consumers to re-verify; see
# ops/V2-072_CUTOVER_RUNBOOK.md. This script only adds a second, restricted
# login and grants it exactly what GlobalStrat+ needs. Nothing that works today
# stops working because this ran.
#
# THE SECRET IS NEVER PRINTED. Not on success, not on failure, not in --check.
# Digest prefixes are shown so two values can be compared without either being
# disclosed. The password is never passed on a command line either: it reaches
# psql through a variable read from a 0600 file.
#
# Idempotent: every run converges on the same end state, and a run with no
# password file changes no credential at all — it only re-applies grants, which
# is what you want after a migration adds a table.
set -uo pipefail

ROLE="${APP_ROLE:-globalstrat_plus_app}"
DB="${PGDATABASE:-globalstrat_plus}"
HOST="${PGHOST:-192.168.50.38}"
PORT="${PGPORT:-5432}"
ADMIN="${PGUSER:-donwh}"          # the role that owns the database today
MODE=apply
PASSWORD_FILE=''
GENERATE_TO=''
DROP_ROLE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --check)             MODE=check ;;
    --revoke)            MODE=revoke ;;
    --drop-role)         DROP_ROLE=1 ;;
    --password-file)     PASSWORD_FILE="${2:?--password-file needs a path}"; shift ;;
    --generate-password) GENERATE_TO="${2:?--generate-password needs a path}"; shift ;;
    -h|--help)           sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

dig() { printf '%s' "${1:-}" | sha256sum | cut -c1-12; }
die() { echo "ERROR: $*" >&2; exit 1; }

# The audit tables. Kept in step with core/services/audit_guards.py:
# PROTECTED_TABLES are append-only for everyone; the resolution manifest is the
# one audit row the application updates by design (written once before the round
# resolves, once when it completes), so it keeps UPDATE and the trigger — not
# the privilege — is what freezes it at `completed_at`.
APPEND_ONLY_TABLES=(
  competition_decision_audit_event
  competition_operator_audit_event
  competition_sensitive_read_event
  competition_authorization_refusal_event
  competition_audit_chain
)
MANIFEST_TABLE=competition_resolution_manifest

psql_admin() { psql -h "$HOST" -p "$PORT" -U "$ADMIN" -d "$DB" -X -v ON_ERROR_STOP=1 "$@"; }
q() { psql -h "$HOST" -p "$PORT" -U "$ADMIN" -d "$DB" -X -tA -c "$1"; }

echo "V2-072 application-role provisioning"
echo "  server      : $HOST:$PORT/$DB"
echo "  admin role  : $ADMIN"
echo "  app role    : $ROLE"
echo "  mode        : $MODE"
echo ""

q 'select 1' >/dev/null || die "cannot connect as $ADMIN (PGPASSWORD not set, or wrong)"

# Refuse to run against a database that is not this application's. Without this
# the script would happily "provision" against a wrong PGDATABASE, grant DML on
# 193 tables belonging to something else, and report PASS -- because with no
# audit tables present there is nothing for the audit assertions to fail on.
for t in "${APPEND_ONLY_TABLES[@]}" "$MANIFEST_TABLE"; do
  [ "$(q "select count(*) from pg_tables where schemaname='public' and tablename='$t'")" = "1" ] \
    || die "$DB has no table $t. Either this is not the GlobalStrat+ database, or the audit table list here has drifted from core/services/audit_guards.py."
done

OWNER="$(q "select pg_get_userbyid(datdba) from pg_database where datname = current_database()")"
[ -n "$OWNER" ] || die "cannot determine the owner of $DB"
echo "database owner: $OWNER"
[ "$OWNER" = "$ADMIN" ] || echo "NOTE: you are connected as $ADMIN but $DB is owned by $OWNER;" \
                                "default privileges are recorded per grantor, so run this as $OWNER."
echo ""

# ───────────────────────── check / report ──────────────────────────────────
report() {
  echo "── role attributes ────────────────────────────────────────────────"
  q "select format('%s: super=%s createrole=%s createdb=%s login=%s replication=%s bypassrls=%s inherit=%s',
                  rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin,
                  rolreplication, rolbypassrls, rolinherit)
       from pg_roles where rolname = '$ROLE'"
  echo "── role memberships (must be empty) ───────────────────────────────"
  q "select r.rolname from pg_auth_members m
       join pg_roles r on r.oid = m.roleid
       join pg_roles u on u.oid = m.member
      where u.rolname = '$ROLE' order by 1"
  echo "── can it reach a superuser? (must be f) ──────────────────────────"
  q "select format('%s reachable: inherit=%s set_role=%s', rolname,
                  pg_has_role('$ROLE', oid, 'USAGE'), pg_has_role('$ROLE', oid, 'MEMBER'))
       from pg_roles where rolsuper order by rolname"
  echo "── audit-table privileges (update/delete/truncate must be f) ──────"
  for t in "${APPEND_ONLY_TABLES[@]}" "$MANIFEST_TABLE"; do
    q "select format('%-46s owner=%-18s select=%s insert=%s update=%s delete=%s truncate=%s',
                    '$t', (select tableowner from pg_tables where tablename='$t'),
                    has_table_privilege('$ROLE','$t','SELECT'),
                    has_table_privilege('$ROLE','$t','INSERT'),
                    has_table_privilege('$ROLE','$t','UPDATE'),
                    has_table_privilege('$ROLE','$t','DELETE'),
                    has_table_privilege('$ROLE','$t','TRUNCATE'))"
  done
  echo "── schema public (create must be f) ───────────────────────────────"
  q "select format('usage=%s create=%s',
                  has_schema_privilege('$ROLE','public','USAGE'),
                  has_schema_privilege('$ROLE','public','CREATE'))"
  echo "── application tables the role cannot write (must be empty) ───────"
  # The audit tables are listed above with their own, deliberately narrower
  # grants; they are excluded here so the deliberate absence of DELETE does not
  # read as a missing grant.
  q "select tablename from pg_tables
      where schemaname='public'
        and tablename not in ('${APPEND_ONLY_TABLES[0]}','${APPEND_ONLY_TABLES[1]}',
                              '${APPEND_ONLY_TABLES[2]}','${APPEND_ONLY_TABLES[3]}',
                              '${APPEND_ONLY_TABLES[4]}','$MANIFEST_TABLE')
        and not (has_table_privilege('$ROLE', schemaname||'.'||tablename, 'SELECT')
             and has_table_privilege('$ROLE', schemaname||'.'||tablename, 'INSERT')
             and has_table_privilege('$ROLE', schemaname||'.'||tablename, 'UPDATE')
             and has_table_privilege('$ROLE', schemaname||'.'||tablename, 'DELETE'))
      order by 1"
  echo "── sequences the role cannot use (must be empty) ──────────────────"
  q "select sequencename from pg_sequences
      where schemaname='public'
        and not has_sequence_privilege('$ROLE', schemaname||'.'||sequencename, 'USAGE')
      order by 1"
}

verdict() {
  local bad=0
  local row
  row="$(q "select coalesce(bool_or(rolsuper or rolcreaterole or rolcreatedb or rolreplication or rolbypassrls), true)
              from pg_roles where rolname='$ROLE'")"
  [ "$row" = "f" ] || { echo "FAIL: $ROLE holds a role attribute it must not have (or does not exist)"; bad=1; }
  row="$(q "select count(*) from pg_auth_members m join pg_roles u on u.oid=m.member where u.rolname='$ROLE'")"
  [ "$row" = "0" ] || { echo "FAIL: $ROLE is a member of $row role(s); it must be a member of none"; bad=1; }
  row="$(q "select count(*) from pg_roles where rolsuper and pg_has_role('$ROLE', oid, 'MEMBER')")"
  [ "$row" = "0" ] || { echo "FAIL: $ROLE can SET ROLE to a superuser"; bad=1; }
  row="$(q "select has_schema_privilege('$ROLE','public','CREATE')")"
  [ "$row" = "f" ] || { echo "FAIL: $ROLE can CREATE in schema public, so it can own (and unguard) a table"; bad=1; }
  for t in "${APPEND_ONLY_TABLES[@]}"; do
    row="$(q "select (select tableowner from pg_tables where tablename='$t') = '$ROLE'
                  or has_table_privilege('$ROLE','$t','UPDATE')
                  or has_table_privilege('$ROLE','$t','DELETE')
                  or has_table_privilege('$ROLE','$t','TRUNCATE')")"
    [ "$row" = "f" ] || { echo "FAIL: $ROLE can rewrite or own the audit table $t"; bad=1; }
    row="$(q "select has_table_privilege('$ROLE','$t','INSERT') and has_table_privilege('$ROLE','$t','SELECT')")"
    [ "$row" = "t" ] || { echo "FAIL: $ROLE cannot append to the audit table $t"; bad=1; }
  done
  row="$(q "select (select tableowner from pg_tables where tablename='$MANIFEST_TABLE') <> '$ROLE'
                and has_table_privilege('$ROLE','$MANIFEST_TABLE','UPDATE')
                and not has_table_privilege('$ROLE','$MANIFEST_TABLE','DELETE')
                and not has_table_privilege('$ROLE','$MANIFEST_TABLE','TRUNCATE')")"
  [ "$row" = "t" ] || { echo "FAIL: $MANIFEST_TABLE privileges are wrong (needs UPDATE, must not have DELETE/TRUNCATE, must not be owned by $ROLE)"; bad=1; }
  row="$(q "select count(*) from pg_tables where schemaname='public' and tableowner='$ROLE'")"
  [ "$row" = "0" ] || { echo "FAIL: $ROLE owns $row table(s) in public"; bad=1; }
  echo ""
  if [ "$bad" = 0 ]; then echo "PASS: $ROLE is a least-privilege, non-owning application role."; else
    echo "FAILED: $ROLE does not meet the V2-072 least-privilege contract."; fi
  return "$bad"
}

if [ "$MODE" = check ]; then
  report; echo ""; verdict; exit $?
fi

# ───────────────────────── revoke / rollback ───────────────────────────────
if [ "$MODE" = revoke ]; then
  echo "revoking every grant made to $ROLE (the role itself is kept unless --drop-role)"
  psql_admin -q <<SQL || die "revoke failed"
DO \$\$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = '$ROLE') THEN
    EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM $ROLE';
    EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM $ROLE';
    EXECUTE 'REVOKE ALL ON SCHEMA public FROM $ROLE';
    EXECUTE 'REVOKE ALL ON DATABASE ' || quote_ident(current_database()) || ' FROM $ROLE';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER IN SCHEMA public REVOKE ALL ON TABLES FROM $ROLE';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER IN SCHEMA public REVOKE ALL ON SEQUENCES FROM $ROLE';
  END IF;
END
\$\$;
SQL
  echo "  grants revoked"
  if [ "$DROP_ROLE" = 1 ]; then
    # PostgreSQL refuses to drop a role that still owns objects or holds grants
    # anywhere on the server, and it names the database in the DETAIL line
    # above. Run --revoke there too, or drop that database if it is disposable.
    psql_admin -q -c "DROP ROLE IF EXISTS $ROLE;" && echo "  role dropped" \
      || die "DROP ROLE failed — $ROLE still owns objects or holds grants in another database on this server (named in the DETAIL above). Revoke there first; the role is kept and the grants in $DB are already gone."
  fi
  echo ""
  echo "ROLLBACK COMPLETE. GlobalStrat+ must be pointed back at $OWNER"
  echo "(DB_USER in /etc/globalstrat-plus.env) and restarted."
  exit 0
fi

# ───────────────────────── password handling ───────────────────────────────
# Never on argv (argv is world-readable in /proc), never echoed, never logged.
NEWPW=''
if [ -n "$GENERATE_TO" ]; then
  [ -n "$PASSWORD_FILE" ] && die "use either --password-file or --generate-password, not both"
  umask 077
  python3 -c 'import secrets,sys; sys.stdout.write(secrets.token_urlsafe(32))' > "$GENERATE_TO" \
    || die "could not write $GENERATE_TO"
  chmod 600 "$GENERATE_TO"
  PASSWORD_FILE="$GENERATE_TO"
  echo "generated a new credential into $PASSWORD_FILE (0600)"
fi
if [ -n "$PASSWORD_FILE" ]; then
  [ -f "$PASSWORD_FILE" ] || die "$PASSWORD_FILE does not exist"
  NEWPW="$(cat "$PASSWORD_FILE")"
  [ -n "$NEWPW" ] || die "$PASSWORD_FILE is empty"
  echo "credential digest : $(dig "$NEWPW")  (not printed anywhere else)"
else
  echo "credential        : unchanged (no --password-file given; grants only)"
fi
echo ""

# ───────────────────────── apply ───────────────────────────────────────────
# One transaction. Either the role ends up with the whole grant set or with
# none of it; a half-granted role is the state that looks fine and fails at
# round resolution.
{
  echo 'BEGIN;'
  cat <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$ROLE') THEN
    CREATE ROLE $ROLE LOGIN;
    RAISE NOTICE 'created role $ROLE';
  ELSE
    RAISE NOTICE 'role $ROLE already exists; converging its attributes';
  END IF;
END
\$\$;

-- Attributes are asserted on every run, not only at creation, so one granted
-- by hand between runs is taken away again. Issued one at a time and only when
-- the role actually has it, because a blanket
-- \`ALTER ROLE ... NOSUPERUSER NOCREATEDB ...\` is refused outright for a
-- non-superuser admin -- PostgreSQL rejects even the no-op NOSUPERUSER clause.
-- SUPERUSER, REPLICATION and BYPASSRLS can only be removed by a superuser, so
-- if the role somehow holds one this stops with a message rather than
-- reporting a least-privilege role that is nothing of the kind.
DO \$\$
DECLARE r record;
BEGIN
  SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin
    INTO r FROM pg_roles WHERE rolname = '$ROLE';
  IF r.rolsuper OR r.rolreplication OR r.rolbypassrls THEN
    RAISE EXCEPTION
      '$ROLE holds SUPERUSER/REPLICATION/BYPASSRLS; only a superuser can remove those'
      USING HINT = 'Have the DBA run: ALTER ROLE $ROLE NOSUPERUSER NOREPLICATION NOBYPASSRLS;';
  END IF;
  IF r.rolcreatedb THEN EXECUTE 'ALTER ROLE $ROLE NOCREATEDB';
    RAISE NOTICE 'removed CREATEDB from $ROLE'; END IF;
  IF r.rolcreaterole THEN EXECUTE 'ALTER ROLE $ROLE NOCREATEROLE';
    RAISE NOTICE 'removed CREATEROLE from $ROLE'; END IF;
  IF NOT r.rolcanlogin THEN EXECUTE 'ALTER ROLE $ROLE LOGIN'; END IF;
END
\$\$;

-- Memberships are the escalation path V2-072 is about. The application role
-- holds none, and any that appear are removed.
DO \$\$
DECLARE r record;
BEGIN
  FOR r IN SELECT g.rolname FROM pg_auth_members m
             JOIN pg_roles g ON g.oid = m.roleid
             JOIN pg_roles u ON u.oid = m.member
            WHERE u.rolname = '$ROLE'
  LOOP
    EXECUTE format('REVOKE %I FROM $ROLE', r.rolname);
    RAISE NOTICE 'revoked membership in %', r.rolname;
  END LOOP;
END
\$\$;
SQL
  if [ -n "$NEWPW" ]; then
    # The value reaches the server on psql's stdin, which is a pipe: it is not
    # in argv (world-readable through /proc), not in a temp file and not in this
    # script's output. `standard_conforming_strings` is on, so doubling the
    # single quotes is the whole of the escaping. It is still a statement the
    # server would log under `log_statement = 'ddl'` or higher -- that is a
    # property of ALTER ROLE, not of this script, and is called out in the
    # runbook.
    echo "ALTER ROLE $ROLE PASSWORD '${NEWPW//\'/\'\'}';"
  fi
  cat <<SQL

GRANT CONNECT, TEMPORARY ON DATABASE $DB TO $ROLE;

-- USAGE only. No CREATE: a role that can create a table in public can create
-- one it owns, and an owner can drop that table's triggers.
GRANT USAGE ON SCHEMA public TO $ROLE;
REVOKE CREATE ON SCHEMA public FROM $ROLE;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $ROLE;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO $ROLE;
SQL
  for t in "${APPEND_ONLY_TABLES[@]}"; do
    echo "REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON $t FROM $ROLE;"
  done
  cat <<SQL
REVOKE DELETE, TRUNCATE, REFERENCES, TRIGGER ON $MANIFEST_TABLE FROM $ROLE;

-- Future tables. A migration run by $OWNER creates tables $ROLE has no grant
-- on, and the application then fails on a table nobody thought about. Default
-- privileges are recorded per grantor, so this is pinned to $OWNER rather than
-- to whoever happens to run the script.
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $ROLE;
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO $ROLE;
COMMIT;
SQL
} | psql -h "$HOST" -p "$PORT" -U "$ADMIN" -d "$DB" -X -v ON_ERROR_STOP=1 -q \
  || die "provisioning transaction rolled back; nothing was changed"

echo "grants applied."
echo ""
echo "NOTE: a default privilege grants DML on every future table, including a"
echo "future audit table. Re-run this script after each migration — that is what"
echo "takes UPDATE/DELETE back off any newly added append-only table. --check"
echo "fails if it was not re-run."
echo ""
report
echo ""
verdict
