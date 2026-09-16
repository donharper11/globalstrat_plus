#!/usr/bin/env bash
# V2-072 — the whole proof, on a disposable PostgreSQL that is destroyed after.
#
#   handoff_readiness_v2/evidence/v2-072/harness/prove.sh
#
# Touches nothing outside a throwaway container. It never reads the production
# secret file and never connects to 192.168.50.38.
#
# What it does, in order:
#   A  starts PostgreSQL 16 on tmpfs and rebuilds production's role shape:
#      `donwh` owning the database and every table, and a member of `postgres`
#   B  demonstrates the hazard as `donwh` -- superuser, server files, and
#      dropping an audit guard
#   C  runs ops/provision-app-role.sh to create the restricted role
#   D  attacks the restricted role: 27 escalation and guard attempts
#   E  runs the platform as the restricted role
#   F  default privileges cover a future migration; --check catches drift
#   G  runs the full backend suite as the restricted role
#
# Two credentials are generated into $WORK (0600) and never printed; the script
# shows 12-hex digest prefixes so two values can be compared without either
# being disclosed.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
WORK="${V2072_WORK:-$(mktemp -d)}"
CONTAINER="${V2072_CONTAINER:-v2072-pg}"
H=127.0.0.1
P="${V2072_PORT:-55432}"
DB=globalstrat_plus
APP=globalstrat_plus_app
IMAGE=postgres:16-alpine

umask 077
mkdir -p "$WORK"
dig() { printf '%s' "${1:-}" | sha256sum | cut -c1-12; }
hdr() { echo; echo "═══ $* ═══"; }

# ── A. a disposable server ─────────────────────────────────────────────────
hdr "A. disposable PostgreSQL"
docker rm -f "$CONTAINER" >/dev/null 2>&1
# tmpfs, fsync off: this host's disk makes an ordinary PGDATA unbearable for a
# 1000-test suite, and nothing here needs to survive the container.
docker run --rm -d --name "$CONTAINER" \
  --tmpfs /var/lib/postgresql/data:rw,size=2g \
  -e POSTGRES_PASSWORD=bootstrap-only-not-a-real-secret \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -p "$H:$P:5432" "$IMAGE" \
  -c fsync=off -c synchronous_commit=off -c full_page_writes=off \
  -c max_connections=200 >/dev/null || exit 1

# `pg_isready` answers yes while the server is still refusing queries, and a
# cold container here can take two minutes. Poll a real query instead.
export PGPASSWORD=bootstrap-only-not-a-real-secret
ready=0
for i in $(seq 1 180); do
  if psql -h $H -p $P -U postgres -d postgres -X -tAc 'select 1' >/dev/null 2>&1; then
    echo "ready after ${i}s"; ready=1; break
  fi
  sleep 1
done
[ "$ready" = 1 ] || { echo "server never became ready"; docker logs --tail 40 "$CONTAINER"; exit 1; }
psql -h $H -p $P -U postgres -d postgres -X -tAc 'select version()'

hdr "A. production's role shape, rebuilt"
python3 -c 'import secrets,sys; sys.stdout.write(secrets.token_urlsafe(32))' > "$WORK/donwh.pw"
OWNERPW="$(cat "$WORK/donwh.pw")"
printf 'CREATE ROLE donwh LOGIN CREATEDB CREATEROLE PASSWORD %s;\nGRANT postgres TO donwh;\n' \
  "'${OWNERPW//\'/\'\'}'" \
  | psql -h $H -p $P -U postgres -d postgres -X -v ON_ERROR_STOP=1 -q || exit 1
echo "donwh created (digest12 $(dig "$OWNERPW")), CREATEDB CREATEROLE, member of postgres"

export PGPASSWORD="$OWNERPW"
psql -h $H -p $P -U donwh -d postgres -X -v ON_ERROR_STOP=1 -q -c 'CREATE DATABASE globalstrat_plus;' || exit 1
psql -h $H -p $P -U donwh -d $DB -X -v ON_ERROR_STOP=1 -q \
  -f "$REPO/scripts/bootstrap/unmanaged_tables_schema.sql" >/dev/null || exit 1
cd "$REPO/backend" || exit 1
DB_NAME=$DB DB_USER=donwh DB_PASSWORD="$OWNERPW" DB_HOST=$H DB_PORT=$P \
  python3 manage.py migrate --noinput 2>&1 | tail -2
o() { psql -h $H -p $P -U donwh -d $DB -X -tA -c "$1" 2>&1 | head -3; }
o "select 'tables in public: '||count(*)||', owned by donwh: '||count(*) filter (where tableowner='donwh') from pg_tables where schemaname='public'"
o "select 'guard triggers: '||count(*) from pg_trigger where not tgisinternal and (tgname like '%_append_only' or tgname like '%_no_truncate')"

# ── B. the hazard ──────────────────────────────────────────────────────────
hdr "B. the hazard, as donwh -- the role the application uses today"
echo "B1 SET ROLE postgres                       [expect: it works]"
o "set role postgres; select 'now '||current_user||', superuser='||(select rolsuper from pg_roles where rolname=current_user)::text"
echo "B2 role attributes                         [expect: both true]"
o "select format('createrole=%s createdb=%s', rolcreaterole, rolcreatedb) from pg_roles where rolname='donwh'"
echo "B3 read a server file                      [expect: it works]"
o "set role postgres; select 'read '||length(pg_read_file('postgresql.conf'))||' bytes of postgresql.conf'"
echo "B4 drop the append-only guard              [expect: it works]"
o "drop trigger competition_decision_audit_event_append_only on competition_decision_audit_event"
o "select 'append_only triggers left: '||count(*) from pg_trigger where not tgisinternal and tgname like '%_append_only'"
echo "B5 restore it"
DB_NAME=$DB DB_USER=donwh DB_PASSWORD="$OWNERPW" DB_HOST=$H DB_PORT=$P \
  python3 manage.py install_audit_guards 2>&1 | head -1
o "select 'guard triggers: '||count(*) from pg_trigger where not tgisinternal and (tgname like '%_append_only' or tgname like '%_no_truncate')"

# ── C. provision ───────────────────────────────────────────────────────────
hdr "C. ops/provision-app-role.sh"
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --generate-password "$WORK/app.pw"
echo "provision exit: $?"
APPPW="$(cat "$WORK/app.pw")"

hdr "C2. the same grant set, emitted by provision_app_role_sql() and re-applied"
DB_NAME=$DB DB_USER=donwh DB_PASSWORD="$OWNERPW" DB_HOST=$H DB_PORT=$P \
  python3 manage.py install_audit_guards --role-sql $APP > "$WORK/role.sql"
cat "$WORK/role.sql"
PGPASSWORD="$OWNERPW" psql -h $H -p $P -U donwh -d $DB -X -v ON_ERROR_STOP=1 -f "$WORK/role.sql" 2>&1 | tail -3
echo "re-apply exit: $?"

# ── D. attack it ───────────────────────────────────────────────────────────
a() { PGPASSWORD="$APPPW" psql -h $H -p $P -U $APP -d $DB -X -tA -c "$1" 2>&1 | head -2; }

hdr "D. escalation attempts as $APP"
echo "connected as: $(a 'select current_user')"
echo "D1  SET ROLE postgres                      [expect: denied]";        a "set role postgres; select current_user"
echo "D2  SET ROLE donwh                         [expect: denied]";        a "set role donwh; select current_user"
echo "D3  role attributes                        [expect: all false]";     a "select format('super=%s createrole=%s createdb=%s replication=%s bypassrls=%s', rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls) from pg_roles where rolname=current_user"
echo "D4  CREATE ROLE                            [expect: denied]";        a "create role attacker_role login"
echo "D5  CREATE DATABASE                        [expect: denied]";        a "create database attacker_db"
echo "D6  ALTER ROLE donwh PASSWORD              [expect: denied]";        a "alter role donwh password 'x'"
echo "D7  pg_read_file                           [expect: denied]";        a "select pg_read_file('postgresql.conf')"
echo "D8  COPY TO PROGRAM                        [expect: denied]";        a "copy (select 1) to program 'cat > /tmp/owned'"
echo "D9  memberships held                       [expect: 0]";             a "select count(*) from pg_auth_members m join pg_roles u on u.oid=m.member where u.rolname=current_user"
echo "D10 reachable superusers                   [expect: 0]";             a "select count(*) from pg_roles where rolsuper and pg_has_role(current_user, oid, 'MEMBER')"
echo "D11 databases it may create objects in     [expect: 0]";             a "select count(*) from pg_database where not datistemplate and has_database_privilege(current_user, oid, 'CREATE')"

hdr "D. the audit guards, attacked as $APP"
echo "D12 DROP TRIGGER on an audit table         [expect: must be owner]";  a "drop trigger competition_decision_audit_event_append_only on competition_decision_audit_event"
echo "D13 ALTER TABLE ... DISABLE TRIGGER        [expect: must be owner]";  a "alter table competition_decision_audit_event disable trigger competition_decision_audit_event_append_only"
echo "D14 DROP the audit table                   [expect: must be owner]";  a "drop table competition_decision_audit_event"
echo "D15 CREATE OR REPLACE the guard function   [expect: denied]";         a "create or replace function competition_audit_reject_change() returns trigger as \$\$ begin return new; end \$\$ language plpgsql"
echo "D16 ALTER TABLE ... OWNER TO me            [expect: must be owner]";  a "alter table competition_decision_audit_event owner to $APP"
echo "D17 CREATE TABLE in public                 [expect: denied]";         a "create table attacker_t (id int)"
echo "D18 TRUNCATE an audit table                [expect: denied]";         a "truncate competition_decision_audit_event"
echo "D19 DELETE from an audit table             [expect: denied]";         a "delete from competition_decision_audit_event"
echo "D20 UPDATE an audit table                  [expect: denied]";         a "update competition_decision_audit_event set action='rewritten'"
echo "D21 set allow_truncate then TRUNCATE       [expect: still denied]";   a "set globalstrat.allow_truncate='on'; truncate competition_decision_audit_event"
echo "D22 migration-shaped DDL                   [expect: must be owner]"
a "alter table game add column v2072_probe integer"
a "create index v2072_probe_idx on game (id)"
a "drop table django_session"

# ── E. it still runs the platform ──────────────────────────────────────────
hdr "E. what the restricted role must still be able to do"
echo "E1  read every application table"
a "select 'of '||count(*)||' public tables, readable='||count(*) filter (where has_table_privilege(current_user, schemaname||'.'||tablename,'SELECT')) from pg_tables where schemaname='public'"
echo "E2  write an ordinary table                [expect: INSERT 1 / DELETE 1]"
a "insert into django_session (session_key, session_data, expire_date) values ('v2072probe','x', now())"
a "delete from django_session where session_key='v2072probe'"
echo "E3  append to an audit table               [expect: INSERT 1]"
a "insert into competition_audit_chain (seq, source_table, source_id, row_sha256, prev_sha256, entry_sha256, sealed_at) values (999999,'v2072_probe',1,repeat('a',64),repeat('0',64),repeat('b',64),now())"
echo "E4  then rewrite what it just wrote        [expect: denied]"
a "update competition_audit_chain set row_sha256=repeat('c',64) where source_table='v2072_probe'"
echo "E5  then delete it                         [expect: denied]"
a "delete from competition_audit_chain where source_table='v2072_probe'"
echo "E6  the row is intact                      [expect: aaaaaaaa]"
a "select 'row_sha256 starts '||left(row_sha256,8) from competition_audit_chain where source_table='v2072_probe'"
echo "E7  UPDATE the manifest                    [expect: UPDATE 0, i.e. authorised]"
a "update competition_resolution_manifest set output_sha256=repeat('2',64) where false"
echo "E8  the same shape on an audit table       [expect: denied]"
a "update competition_decision_audit_event set action='x' where false"
echo "E9  DELETE the manifest                    [expect: denied]"
a "delete from competition_resolution_manifest where false"
echo "E10 use a sequence                         [expect: a number]"
a "select nextval(pg_get_serial_sequence('competition_audit_chain','id'))"
# The probe row is a forged chain entry; the owner removes it, which is the
# privileged maintenance action the guards are designed to make visible.
PGPASSWORD="$OWNERPW" psql -h $H -p $P -U donwh -d $DB -X -q -c \
  "alter table competition_audit_chain disable trigger competition_audit_chain_append_only;
   delete from competition_audit_chain where source_table='v2072_probe';
   alter table competition_audit_chain enable trigger competition_audit_chain_append_only;" >/dev/null 2>&1

echo "E11 the restore path                       [expect: refused -- V2-072a]"
# competition_backup.restore_database() opens with exactly these two
# statements. They need schema ownership, which is the point of this role not
# having it -- so `recover_competition_round` and `replay_round` are owner
# operations. Safe to attempt: a refusal changes nothing, and the table count
# after it says so.
a "DROP SCHEMA public CASCADE"
a "CREATE SCHEMA public"
a "select 'tables in public after the attempt: '||count(*) from pg_tables where schemaname='public'"

echo "E12 pg_dump -- the pre-resolution backup the round resolver takes"
PGPASSWORD="$APPPW" pg_dump --format=custom --no-owner --host $H --port $P \
  --username $APP --file "$WORK/probe.dump" $DB 2>&1 | head -3
echo "    exit=$? size=$(stat -c%s "$WORK/probe.dump" 2>/dev/null) bytes"

echo "E13 the platform's own commands, as $APP"
run() { DB_NAME=$DB DB_USER=$APP DB_PASSWORD="$APPPW" DB_HOST=$H DB_PORT=$P "$@"; }
run python3 manage.py check 2>&1 | tail -1
run python3 manage.py install_audit_guards --check 2>&1 | tail -1
run python3 manage.py check_round_deadlines 2>&1 | tail -1
run python3 manage.py run_narrative_worker --status 2>&1 | tail -3
run timeout 60 python3 manage.py run_narrative_worker --limit 1 2>&1 | tail -1

# ── F. drift ───────────────────────────────────────────────────────────────
hdr "F. default privileges, and the drift --check exists to catch"
echo "F1  the owner creates a table, as a migration would"
o "create table v2072_future_table (id bigserial primary key, x text)"
o "select format('app role: select=%s insert=%s update=%s delete=%s, owner=%s',
        has_table_privilege('$APP','v2072_future_table','SELECT'),
        has_table_privilege('$APP','v2072_future_table','INSERT'),
        has_table_privilege('$APP','v2072_future_table','UPDATE'),
        has_table_privilege('$APP','v2072_future_table','DELETE'),
        (select tableowner from pg_tables where tablename='v2072_future_table'))"
o "select format('its sequence usable=%s', has_sequence_privilege('$APP','v2072_future_table_id_seq','USAGE'))"
o "drop table v2072_future_table"
echo "F2  someone grants UPDATE on an audit table. --check must fail."
o "grant update on competition_decision_audit_event to $APP"
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --check 2>&1 | tail -3
echo "    --check exit: ${PIPESTATUS[0]}"
echo "F3  re-running the provisioner repairs it"
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" 2>&1 | tail -1
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --check 2>&1 | tail -1
echo "    --check exit: ${PIPESTATUS[0]}"

# ── G. the suite ───────────────────────────────────────────────────────────
hdr "G. the full backend suite, as $APP"
# Django's test runner needs CREATE DATABASE, which this role must not have. So
# the owner creates the test database and grants CREATE on its schema, and the
# suite runs with --keepdb: Django 5.2's postgresql backend skips CREATE
# DATABASE when --keepdb finds the database already there
# (django/db/backends/postgresql/creation.py::_execute_create_test_db).
#
# Inside test_globalstrat_plus the app role owns the tables it creates. That is
# true of the disposable test database only; the competition database's grants
# are the ones section D attacked and --check asserts.
PGPASSWORD="$OWNERPW" psql -h $H -p $P -U donwh -d postgres -X -v ON_ERROR_STOP=1 -q \
  -c "DROP DATABASE IF EXISTS test_globalstrat_plus;" \
  -c "CREATE DATABASE test_globalstrat_plus;" || exit 1
PGPASSWORD="$OWNERPW" psql -h $H -p $P -U donwh -d test_globalstrat_plus -X -v ON_ERROR_STOP=1 -q \
  -c "GRANT ALL ON SCHEMA public TO $APP;" || exit 1
echo "test database pre-created by the owner; $APP granted CREATE on its public schema"
# Other agents run suites on this machine; the lock is shared with them.
#
# The credential is exported inside the subshell rather than passed through
# `env`: an `env VAR=value cmd` prefix puts the value in env's argv, and argv is
# readable by anyone who can run `ps`. Exported variables are not.
export DB_NAME=$DB DB_USER=$APP DB_HOST=$H DB_PORT=$P
export DB_PASSWORD="$APPPW"
flock -w 1800 /tmp/globalstrat-backend-test.lock \
  python3 manage.py test --noinput --keepdb > "$WORK/suite.log" 2>&1
echo "suite exit: $?"
# The suite's own chatter runs to thousands of lines; these are the ones that
# say what happened. The whole log stays in $WORK.
grep -E '^(Found [0-9]+ test|Ran [0-9]+ test|OK|FAILED|Using existing|Preserving)' \
  "$WORK/suite.log"
unset DB_PASSWORD

# ── H. rollback ────────────────────────────────────────────────────────────
hdr "H. the rollback path"
echo "H1  --revoke"
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --revoke 2>&1 | tail -3
echo "H2  the role can still log in, and can now read nothing [expect: denied]"
a "select count(*) from game"
# USAGE on public survives the revoke because PostgreSQL grants it to PUBLIC,
# not to this role. It confers nothing without a privilege on an object.
a "select 'schema usage (granted to PUBLIC, not to this role)='||has_schema_privilege(current_user,'public','USAGE')"
echo "H3  the application on the old role is unaffected     [expect: a count]"
o "select 'game rows='||count(*) from game"
echo "H4  --revoke --drop-role, while the test database's objects still exist"
echo "    [expect: refused, and the role kept]"
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --revoke --drop-role 2>&1 | tail -3
o "select 'roles named globalstrat_plus_app: '||count(*) from pg_roles where rolname='$APP'"
echo "H5  the same, once nothing depends on the role [expect: dropped]"
PGPASSWORD="$OWNERPW" psql -h $H -p $P -U donwh -d postgres -X -q \
  -c "DROP DATABASE IF EXISTS test_globalstrat_plus;" 2>&1 | head -2
PGHOST=$H PGPORT=$P PGUSER=donwh PGDATABASE=$DB PGPASSWORD="$OWNERPW" \
  bash "$REPO/ops/provision-app-role.sh" --revoke --drop-role 2>&1 | tail -3
o "select 'roles named globalstrat_plus_app: '||count(*) from pg_roles where rolname='$APP'"
echo "H6  and the audit guards are exactly where they were  [expect: 12]"
o "select 'guard triggers: '||count(*) from pg_trigger where not tgisinternal and (tgname like '%_append_only' or tgname like '%_no_truncate')"

hdr "done"
echo "credentials generated in $WORK (0600). Digest prefixes only:"
echo "  donwh (owner stand-in): $(dig "$OWNERPW")"
echo "  $APP: $(dig "$APPPW")"
echo "removing the container"
docker rm -f "$CONTAINER" >/dev/null 2>&1 && echo "container removed"
