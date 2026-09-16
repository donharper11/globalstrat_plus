# V2-072 — evidence

Two things happened. One was a read-only look at the competition database, so
the design would match the live shape rather than the register's account of it.
The other was a disposable PostgreSQL in Docker, where the change was actually
made and then attacked.

**Nothing was changed on `192.168.50.38`.** Every statement in
`harness/inspect-production.sh` is a `SELECT` against a catalog view.

## Files

| file | what it is |
| --- | --- |
| `harness/inspect-production.sh` | the read-only inspection. Reads the credential from the running service's own environment, prints a 12-hex digest prefix and never the value |
| `production-inspection.txt` | its output, 2026-09-16 |
| `harness/prove.sh` | the whole proof on a throwaway container: rebuild production's role shape, demonstrate the hazard, provision the role, attack it, run the platform as it, run the suite as it, roll it back |
| `proof-transcript.txt` | its output, 2026-09-16 |

Neither file contains a credential. `prove.sh` generates two throwaway
passwords into a working directory at 0600 and prints digest prefixes only; the
container is destroyed at the end.

## What the inspection established

`donwh`, the role GlobalStrat+ connects as, is `rolsuper = f` — and a member of
`postgres`, with `rolinherit = t`. It both inherits superuser privileges and can
`SET ROLE postgres`. It holds `CREATEROLE` and `CREATEDB`. It owns
`globalstrat_plus` and **all 193 tables in `public`**, the six audit tables
included. It is a member of eleven unrelated service roles. `log_connections`,
`log_disconnections` and `logging_collector` are all `off`;
`listen_addresses` is `*`; the only extension installed is `plpgsql`.

Two corrections to the record fall straight out of that:

* The operations review says `donwh` "has server-file-read capability".
  `pg_read_server_files` and `pg_read_all_data` are both `f`. It reads server
  files by first becoming `postgres`. Revoking a grant it does not hold would
  change nothing.
* V2-048 counts "87 non-template databases" reachable with the credential.
  There are **126**.

And one addition: **the application owns the audit tables it writes to.**
Neither the review nor the register says so, and it is the reason this finding
undermines GSP-CRV2-04 rather than merely sitting beside it.

## What the proof established

The disposable server is PostgreSQL 16.13 — the same minor version as
production — with `donwh` rebuilt the same way: owner of the database, owner of
all 193 tables, member of `postgres`, 12 guard triggers installed by the real
migrations.

**The hazard is real, not theoretical.** As `donwh`: `SET ROLE postgres`
succeeds and reports `superuser=true`; `pg_read_file('postgresql.conf')`
returns the file; `DROP TRIGGER competition_decision_audit_event_append_only`
succeeds and leaves five append-only triggers where there were six.

**The restricted role cannot do any of it.** Each attempt is refused with the
reason the server gave: `SET ROLE postgres`, `SET ROLE donwh`, `CREATE ROLE`,
`CREATE DATABASE`, `ALTER ROLE donwh PASSWORD`, `pg_read_file`,
`COPY TO PROGRAM`, `DROP TRIGGER`, `ALTER TABLE ... DISABLE TRIGGER`,
`DROP TABLE`, `CREATE OR REPLACE FUNCTION`, `ALTER TABLE ... OWNER TO`,
`CREATE TABLE`, `TRUNCATE`, `DELETE`, `UPDATE` on an audit table, the same
`TRUNCATE` after setting `globalstrat.allow_truncate = 'on'`, and three
migration-shaped DDL statements. It holds zero role memberships, can `SET ROLE`
to zero superusers, and can create objects in zero databases on the server.

**And it still runs the platform.** It reads and writes every application
table, appends to an audit table and then cannot change or delete what it just
appended, updates the resolution manifest (authorised) while the same statement
shape on an audit table is refused, takes the `pg_dump` the round resolver takes
before every resolution (883 KB, exit 0), and runs `check`,
`install_audit_guards --check`, `check_round_deadlines` and the narrative
worker. **The full backend suite passes as the restricted role: `Ran 1016 tests
in 161.766s`, `OK`.**

**One thing it cannot do that it arguably should (V2-072a).**
`competition_backup.restore_database()` opens with `DROP SCHEMA public CASCADE`,
which needs schema ownership: `ERROR: must be owner of schema public`, then
`ERROR: permission denied for database globalstrat_plus`, with all 193 tables
still there afterwards. `recover_competition_round` and `replay_round` are owner
operations from now on. The `pg_dump` half of the same module is not affected.

**The rollback works, including when it should refuse.** `--revoke` leaves the
role able to log in and unable to read a single application table. `--drop-role`
is refused while the role still owns the test database's 388 objects, and the
script says so rather than half-succeeding; once nothing depends on the role it
drops cleanly. The twelve audit guards are untouched throughout.

## The one accommodation, stated plainly

Django's test runner needs `CREATE DATABASE`, which this role must not have. So
the test database is created by the owner and the suite runs with `--keepdb`;
Django 5.2's PostgreSQL backend skips `CREATE DATABASE` when `--keepdb` finds
the database already there
(`django/db/backends/postgresql/creation.py::_execute_create_test_db`). Inside
`test_globalstrat_plus` the app role owns the tables it creates, because the
runner builds the schema from the models.

That is a property of the disposable test database only. The competition
database's grants are the ones section D attacks and
`ops/provision-app-role.sh --check` asserts, and there the role owns nothing.

## Reproducing

    handoff_readiness_v2/evidence/v2-072/harness/prove.sh

Needs Docker and about six minutes, most of it the suite. It takes
`flock /tmp/globalstrat-backend-test.lock` first, because other agents run
suites on this machine.

    handoff_readiness_v2/evidence/v2-072/harness/inspect-production.sh

Needs to run on the application host, where `globalstrat-backend.service` is
running. Read-only.
