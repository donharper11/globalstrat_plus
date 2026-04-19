"""
Bootstrap the legacy `users` table so later CreateModel migrations that FK
to `core.User` can emit their REFERENCES constraints successfully.

The `core.User` model is declared `managed = False` (legacy BECSR table),
so Django does not emit a CREATE TABLE for it during 0001_initial. That's
fine on production DBs — the table already exists from before Django
managed migrations on this project. It is NOT fine on fresh DBs (test DB
setup, new developer workstations), where migrations 0016, 0018, 0031h,
etc. create tables with FK constraints to `users` and fail with
``relation "users" does not exist``.

This migration uses `run_before` to insert itself at the root of the graph
— ahead of 0001_initial — and runs `CREATE TABLE IF NOT EXISTS users`, so
fresh DBs get the table before any FK references it. Production DBs are
unaffected: the IF NOT EXISTS clause makes the statement a no-op when the
table already exists, and the migration is recorded as applied.

Field layout mirrors `core.User` (see backend/core/models/core.py). If
that model changes, this migration should be updated in lockstep; since
`managed = False`, Django won't detect or regenerate it automatically.
"""
from django.db import migrations


class Migration(migrations.Migration):

    run_before = [('core', '0001_initial')]
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(50) NULL,
                    team_id INTEGER NULL,
                    email VARCHAR(200) NULL,
                    student_id VARCHAR(50) NULL,
                    display_name VARCHAR(200) NULL
                );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
