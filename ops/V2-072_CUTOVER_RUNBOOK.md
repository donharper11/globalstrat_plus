# V2-072 — cutover to a least-privilege application role

Status: **prepared and proven on a disposable server; not applied to
production.** Nothing in this runbook has been run against 192.168.50.38. The
only thing done there was a read-only privilege inspection, recorded below.

## The finding, restated against what the server actually says

Read-only inspection of `192.168.50.38/globalstrat_plus` on 2026-09-16
(`pg_roles`, `pg_auth_members`, `pg_tables`, `pg_settings`; no change made):

| claim | server |
| --- | --- |
| app connects as `donwh` | yes — `DB_USER` default in `backend/globalstrat/settings.py` |
| `donwh` is a member of `postgres` | yes, and `rolinherit = t`, so it both inherits and can `SET ROLE postgres` |
| `donwh` holds CREATEROLE and CREATEDB | yes, both |
| `donwh` "has server-file-read capability" | **not directly.** `pg_read_server_files` and `pg_read_all_data` are both `f`. It reads server files by first becoming `postgres`, which it can. The capability is real; the review's phrasing attributes it to the wrong grant |
| "memberships in several unrelated service roles" | yes — `accounting_svc`, `aibstudy`, `exporter_svc`, `gateway_svc`, `keycloak_svc`, `nexus_api_runtime`, `nexus_sql_studio_readonly`, `prism_user`, `rl_app`, `rl_owner`, `tenant_svc`, plus `postgres` |
| "87 non-template databases" (V2-048 text) | **126** today |
| `log_connections` / `log_disconnections` / `logging_collector` | all `off` — unchanged since the review |
| `listen_addresses` | `*` — unchanged |

And the part the register does not say, which is the reason the audit guards
need this change: **`donwh` owns the `globalstrat_plus` database and all 193
tables in `public`**, including the six audit tables. The append-only triggers
in `core/services/audit_guards.py` are written on the premise that the writer
cannot drop them. Today the writer owns them. Reproduced on a disposable
PostgreSQL 16.13 with the same role shape: as `donwh`, `DROP TRIGGER
competition_decision_audit_event_append_only` succeeded.

## What this change does, and deliberately does not do

**Does:** adds one new login role, `globalstrat_plus_app`, with connect + DML
on `globalstrat_plus` and nothing else, and points GlobalStrat+ at it.

**Does not:** touch `donwh`. That role is shared by GlobalStrat+, GlobalStrat
v1 and BECSR. Revoking its `postgres` membership, CREATEROLE and CREATEDB is
step 2 of remediation and needs all three consumers re-verified; it is listed
under "What still needs the owner" below, not done here.

So the blast radius of this cutover is GlobalStrat+'s own units. GlobalStrat v1
and BECSR keep using `donwh` with the credential they have now, unchanged, and
are not restarted. Neither reads `/etc/globalstrat-plus.env`: BECSR runs from
`~/projects/BECSR/.becsr-secrets.env` under `becsr-backend.service` and its own
cron, and v1 from `~/.globalstrat-secrets.env` under a minutely cron. Nothing
they do today stops working because this ran — see item 6 under "What still
needs the owner" for what v1 is *already* not doing, which this change neither
causes nor fixes.

## The role

`ops/provision-app-role.sh` creates or converges it. Idempotent: run it as
often as you like, and re-run it after every migration (see Drift).

    NOSUPERUSER  NOCREATEDB  NOCREATEROLE  NOREPLICATION  NOBYPASSRLS
    member of no role at all
    CONNECT, TEMPORARY on globalstrat_plus
    USAGE (not CREATE) on schema public
    SELECT, INSERT, UPDATE, DELETE on every table
    USAGE, SELECT, UPDATE on every sequence
      minus, on the five append-only audit tables:
        UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
      minus, on competition_resolution_manifest:
        DELETE, TRUNCATE, REFERENCES, TRIGGER   (UPDATE kept — see below)

`competition_resolution_manifest` keeps `UPDATE` because the manifest is the
one audit row the application writes twice by design: `prepare_manifest()`
before the round is resolved, `complete_manifest()` when it finishes. What
freezes it is the trigger, at `completed_at`, not the privilege. The first
version of `provision_app_role_sql()` revoked `UPDATE` on it along with the
others, which would have failed *at the end of a round*, after the scoring —
that is fixed in this change.

## Steps

Everything below runs from the application host. `$OWNER` is `donwh` (the
current owner of the database). Nothing here is destructive; step 5 is the only
one that changes a running service.

**1. Preflight — confirm the shape you are changing.**

    PGPASSWORD=<owner secret> PGHOST=192.168.50.38 PGUSER=donwh \
      PGDATABASE=globalstrat_plus ops/provision-app-role.sh --check

Expect `FAIL: globalstrat_plus_app holds a role attribute it must not have (or
does not exist)` — the role is not there yet. That is the "before".

**2. Create the role and its credential.**

    umask 077
    PGPASSWORD=<owner secret> PGHOST=192.168.50.38 PGUSER=donwh \
      PGDATABASE=globalstrat_plus \
      ops/provision-app-role.sh --generate-password /root/gsp-app.pw

The script prints a 12-character digest prefix and never the value. The
credential lands in `/root/gsp-app.pw`, 0600. It ends with
`PASS: globalstrat_plus_app is a least-privilege, non-owning application role.`
If it does not, stop: the whole transaction rolled back and nothing changed.

Note: `ALTER ROLE ... PASSWORD` is a statement the server logs under
`log_statement = 'ddl'` or higher. This server has `logging_collector = off`
and `log_statement` at its default (`none`), so nothing is written; if that
changes, rotate afterwards.

**3. Verify before touching the service.**

    PGPASSWORD=<owner secret> ... ops/provision-app-role.sh --check

and, connecting as the new role, the four things that must be refused:

    psql -h 192.168.50.38 -U globalstrat_plus_app -d globalstrat_plus \
      -c "set role postgres"                       # permission denied
      -c "create role x"                           # permission denied
      -c "create database x"                       # permission denied
      -c "drop trigger competition_decision_audit_event_append_only \
            on competition_decision_audit_event"   # must be owner

**4. Point GlobalStrat+ at it.** In `/etc/globalstrat-plus.env` (root 0600):

    DB_USER=globalstrat_plus_app
    DB_PASSWORD=<contents of /root/gsp-app.pw>

Back the file up first: `cp -p /etc/globalstrat-plus.env
/etc/globalstrat-plus.env.pre-v2072`.

**Do not touch** `~/.globalstrat-secrets.env` (v1) or
`~/projects/BECSR/.becsr-secrets.env` (BECSR). They keep `donwh`.

**5. Restart the services that read that file.** There are three, not one:

    systemctl restart globalstrat-backend.service
    systemctl restart globalstrat-narratives.service

`globalstrat-backup-monitor.service` also reads it, but it is started by
`globalstrat-backup-monitor.timer` and picks the new value up at its next run;
nothing to restart. (`grep -rl globalstrat-plus.env /etc/systemd/system/`
enumerates all three.)

`ALTER ROLE` does not disconnect live sessions and changing an env file does
not either, so without the restart the backend keeps serving on its old
connections and fails later, at the next reconnect. That was measured during
the V2-048 rotation; the same applies here.

`becsr-backend.service` is **not** restarted. The v1 deadline cron is **not**
touched. Neither reads `/etc/globalstrat-plus.env`.

**6. Verify the service.**

    systemctl is-active globalstrat-backend.service
    curl -s -o /dev/null -w '%{http_code}\n' <backend>/api/auth/login/ \
      -d '{"username":"nobody","password":"nobody"}' -H 'Content-Type: application/json'
      # expect 401, not 500 — a 500 is a database authentication failure

    cd backend && python3 manage.py install_audit_guards --check
    cd backend && python3 manage.py verify_audit_chain

and confirm the other two consumers are untouched:

    systemctl is-active becsr-backend.service      # BECSR, still on donwh
    tail -3 /tmp/becsr-deadlines.log               # BECSR cron, still on donwh

**Do not use `check_round_deadlines` as the v1 health check.** The V2-048
rotation script does, and v1 fails it *today*, before this change: see item 6
under "What still needs the owner". Comparing before and after will show the
same failure, so the check tells you nothing about this cutover. Compare
`tail /tmp/globalstrat-deadlines.log` before and after instead — the failure
must be unchanged, not newly appeared.

## Rollback

Two independent levers; use the first unless the role itself is the problem.

**Roll back the service (30 seconds, no database change):**

    cp -p /etc/globalstrat-plus.env.pre-v2072 /etc/globalstrat-plus.env
    systemctl restart globalstrat-backend.service
    systemctl restart globalstrat-narratives.service

The application is back on `donwh`. The new role still exists and is harmless.

**Roll back the database:**

    PGPASSWORD=<owner secret> PGHOST=192.168.50.38 PGUSER=donwh \
      PGDATABASE=globalstrat_plus ops/provision-app-role.sh --revoke [--drop-role]

`--revoke` removes every grant and leaves the role. `--drop-role` also drops
it, and PostgreSQL refuses that while the role owns an object or holds a grant
anywhere on the server — the error names the database, and the grants in
`globalstrat_plus` are already gone by then either way. Do the service rollback
first: dropping a role a running service is connected as leaves that service
failing at its next reconnect.

## Drift — the one thing that will break this if nobody watches it

`ALTER DEFAULT PRIVILEGES` gives the app role DML on every table the owner
creates from now on. That is what keeps migrations working without a manual
grant (proven: a table created by the owner is immediately readable and
writable by the app role, its sequence included). It also means a **future
audit table arrives with UPDATE and DELETE granted** — migration 0079 added
`competition_authorization_refusal_event` exactly this way.

So: **re-run `ops/provision-app-role.sh` after every migration**, and run
`--check` in the release gate. `--check` fails if the app role can update,
delete, truncate or own any of the six audit tables, if it is a member of any
role, if it can reach a superuser, or if it can create in `public`. Proven:
granting `UPDATE` on one audit table by hand makes `--check` exit 1, and
re-running the provisioner repairs it.

If a migration adds a seventh audit table, add it to `PROTECTED_TABLES` in
`core/services/audit_guards.py` **and** to `APPEND_ONLY_TABLES` in
`ops/provision-app-role.sh`. The two lists are not derived from one another.

## What the app role cannot do, by design

These are owner operations. They are not regressions; they are the point.

* **Migrations.** There is no automated deploy step that migrates, so this is
  the by-hand sequence from now on — owner for the DDL, provisioner for the
  grants on whatever it created, then the restart:

      cd backend
      DB_USER=donwh DB_PASSWORD=<owner secret> python3 manage.py migrate
      PGUSER=donwh PGPASSWORD=<owner secret> PGHOST=192.168.50.38 \
        PGDATABASE=globalstrat_plus ../ops/provision-app-role.sh
      sudo systemctl restart globalstrat-backend.service globalstrat-narratives.service

  Proven: `ALTER TABLE game ADD COLUMN`, `CREATE INDEX` and `DROP TABLE` are
  all refused to the app role.
* **Restore.** `core/services/competition_backup.restore_database()` issues
  `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`. Tried as the restricted
  role: `ERROR: must be owner of schema public`, then
  `ERROR: permission denied for database globalstrat_plus` — and the 193 tables
  were still there afterwards. `recover_competition_round` and `replay_round`
  must therefore be run with the **owner** credential in the environment, not
  the service's. Recorded as V2-072a below.
* **Backups are fine.** `backup_before_resolution()` runs `pg_dump` inside
  round resolution, in the app's hot path, and works as the restricted role
  (proven: an 883 KB custom-format dump).

## What still needs the owner to authorise (not done here)

1. **The `donwh` narrowing itself.** Revoke `postgres`, `CREATEROLE`,
   `CREATEDB` and the unrelated service-role memberships. Cannot be done from
   GlobalStrat+ alone: GlobalStrat v1 and BECSR share the login, and their
   minimum grant sets have not been inventoried. Until this happens, V2-072 is
   *mitigated for GlobalStrat+* — the exposed credential still reaches a
   superuser, it just is not what the application uses.
2. **The same treatment for v1 and BECSR**, so `donwh` stops being an
   application credential at all and becomes a human admin identity again.
3. **Connection auditing.** `log_connections`, `log_disconnections` and
   `logging_collector` are still `off`, so there is still no record of who
   connects. Unchanged since 2026-09-05.
4. **TLS identity.** Still a self-signed certificate with `sslmode=require`.
   Unchanged.
5. **V2-072a (new):** the restore path needs an owner credential. Either
   document that `recover_competition_round` / `replay_round` are run with
   `DB_USER=<owner>` in the environment, or give them an explicit
   `--as-owner` credential source. Today they would fail at
   `DROP SCHEMA public` under the restricted role, at the moment someone is
   trying to recover a round.
6. **Operational, found while doing this and not part of V2-072 — GlobalStrat
   v1's deadline cron is dead, and has been for at least five days.**
   `~/.globalstrat-secrets.env` holds a value whose digest prefix differs from
   the one the running GlobalStrat+ service and BECSR both hold, and it does not
   authenticate: `psql -U donwh` with it returns
   `FATAL: password authentication failed`. The consequence is visible in
   `/tmp/globalstrat-deadlines.log`, which the minutely cron
   (`* * * * * cd ~/projects/globalstrat/backend && manage.py
   check_round_deadlines`) appends to: 37 MB, **not one successful run**, every
   entry the same authentication failure, back to the log's creation on
   2026-09-11 05:42 UTC. BECSR's equivalent cron is healthy
   (`/tmp/becsr-deadlines.log`).

   `ops/rotate-db-credential.sh` verifies v1 by running that very command and
   rolls back if it fails, so either it passed and the file changed afterwards,
   or the verification did not do what it claims. Either way **no v1 round has
   auto-advanced on a deadline for at least five days**, and nothing alerted.
   This is an owner item independent of this work. **No credential value is
   recorded anywhere in this repository.**

## Evidence

`handoff_readiness_v2/evidence/v2-072/` holds two transcripts and the scripts
that produced them:

* `production-inspection.txt` — the read-only look at 192.168.50.38 that the
  first section of this runbook is drawn from.
* `proof-transcript.txt` — the disposable server: production's role shape
  reproduced (193 tables, 12 guard triggers, `donwh` a member of `postgres`),
  the hazard demonstrated as `donwh`, the role provisioned, every escalation and
  guard attack refused, the platform's own commands run as the restricted role,
  the full backend suite green as the restricted role (`Ran 1016 tests in
  161.766s`, `OK`), and the rollback path exercised — including the case where
  `--drop-role` should refuse, and does.
