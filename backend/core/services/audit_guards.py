"""Database triggers that refuse to change an audit record.

The application's model layer already raised on re-saving an audit row, and
that guard held for exactly as long as the write went through the model layer.
`Model.objects.filter(...).update()`, `.delete()`, the admin, a psql session and
a `manage.py shell` all skip `save()` entirely. These triggers sit underneath
all of them, so "append-only" is a property of the table rather than a property
of the code that usually writes to it.

The triggers stop everyone, including the owner, until the owner explicitly
drops them — which is a privileged maintenance action, and the thing the hash
chain and its external anchor exist to make visible afterwards. `TRUNCATE`
needs a statement-level trigger of its own; see `TRUNCATE_SETTING` below.
Privileges are the last layer: `provision_app_role_sql()` produces a login role
that is not the owner and therefore cannot drop a trigger at all.

The DDL lives here rather than only in the migration because `manage.py test`
runs against a database built straight from the models with migrations
disabled. A guard that exists only in a migration is a guard that no test can
observe, so both the migration and the test runner install from this module.
"""

# The resolution manifest is the one audit record written twice by design:
# once before the round is resolved, once when it completes. It is frozen from
# the moment `completed_at` is set, which is the moment it starts being
# evidence.
PROTECTED_TABLES = (
    'competition_decision_audit_event',
    'competition_operator_audit_event',
    'competition_sensitive_read_event',
    'competition_authorization_refusal_event',
    'competition_audit_chain',
)

MANIFEST_TABLE = 'competition_resolution_manifest'

REJECT_FUNCTION = 'competition_audit_reject_change'
MANIFEST_FUNCTION = 'competition_manifest_reject_change'
TRUNCATE_FUNCTION = 'competition_audit_reject_truncate'

# `TRUNCATE` does not fire row-level triggers, so the guards above let it
# through: one statement empties the audit log and every `BEFORE DELETE`
# trigger stays silent. It needs a statement-level trigger of its own.
#
# Django's `TransactionTestCase` resets the database by truncating every table,
# so the guard needs some way to recognise a test database — but the first
# version recognised one by asking the session, and
# `SET globalstrat.allow_truncate = 'on'` is available to any session,
# including the application's own. That authorised precisely the destruction it
# was meant to gate.
#
# The allowance now requires two things, and the one that matters is the one a
# session cannot change: the database must be named the way Django names an
# isolated test database. The setting is kept because it lets a test withdraw
# the allowance and watch the guard fire, and because an explicit marker is
# worth having — but it can only ever make the rule stricter. Setting it in a
# competition database changes nothing.
TRUNCATE_SETTING = 'globalstrat.allow_truncate'

# Django builds an isolated test database as TEST['NAME'] or, by default, the
# configured name with this prefix. A competition database is never named this.
TEST_DATABASE_PREFIX = 'test_'

# `_` is a LIKE wildcard, so the prefix has to be escaped before it becomes a
# pattern: an unescaped `test_%` also matches `testXfoo`.
TEST_DATABASE_LIKE = TEST_DATABASE_PREFIX.replace('_', r'\_') + '%'

POLICY_FUNCTION = 'competition_truncate_is_allowed'


def _trigger_name(table):
    return f'{table}_append_only'


def _truncate_trigger_name(table):
    return f'{table}_no_truncate'


FUNCTIONS_SQL = f"""
CREATE OR REPLACE FUNCTION {REJECT_FUNCTION}() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'append-only audit table %: % on row % is not permitted',
        TG_TABLE_NAME, TG_OP, OLD.id
        USING ERRCODE = 'insufficient_privilege',
              HINT = 'Audit records are evidence. Correct them by appending.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION {MANIFEST_FUNCTION}() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'resolution manifest % cannot be deleted', OLD.id
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.completed_at IS NOT NULL THEN
        RAISE EXCEPTION
            'resolution manifest % completed at %; it is immutable',
            OLD.id, OLD.completed_at
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'Re-resolving a round writes a new round, not a new manifest.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Kept as its own function so the policy can be interrogated with a database
-- name that is not the caller's, which is the only way to test from inside a
-- test database that a production database would refuse.
CREATE OR REPLACE FUNCTION {POLICY_FUNCTION}(db_name text) RETURNS boolean AS $$
BEGIN
    RETURN db_name LIKE '{TEST_DATABASE_LIKE}'
       AND COALESCE(current_setting('{TRUNCATE_SETTING}', true), 'off') = 'on';
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION {TRUNCATE_FUNCTION}() RETURNS trigger AS $$
BEGIN
    IF {POLICY_FUNCTION}(current_database()) THEN
        RETURN NULL;
    END IF;
    RAISE EXCEPTION
        'append-only audit table %: TRUNCATE is not permitted', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege',
              HINT = 'Truncating an audit table destroys the evidence it holds.';
END;
$$ LANGUAGE plpgsql;
"""

ALL_TABLES = PROTECTED_TABLES + (MANIFEST_TABLE,)


def install_sql(protected=None, manifest=True, all_tables=None):
    """Every statement that installs the guards, in order.

    `protected` and `all_tables` exist so a historical migration can pin the
    tables that existed when it was written. Migration 0070 called this with no
    arguments, which read whatever `PROTECTED_TABLES` holds today, so adding a
    table to that tuple made 0070 try to install a trigger on a table three
    migrations before it is created -- breaking every fresh install while
    leaving already-migrated databases untouched and therefore silent.
    """
    protected = PROTECTED_TABLES if protected is None else tuple(protected)
    all_tables = ((protected + ((MANIFEST_TABLE,) if manifest else ()))
                  if all_tables is None else tuple(all_tables))
    statements = [FUNCTIONS_SQL]
    for table in protected:
        name = _trigger_name(table)
        statements.append(f'DROP TRIGGER IF EXISTS {name} ON {table};')
        statements.append(
            f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} '
            f'FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION}();')
    if manifest:
        name = _trigger_name(MANIFEST_TABLE)
        statements.append(f'DROP TRIGGER IF EXISTS {name} ON {MANIFEST_TABLE};')
        statements.append(
            f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {MANIFEST_TABLE} '
            f'FOR EACH ROW EXECUTE FUNCTION {MANIFEST_FUNCTION}();')
    for table in all_tables:
        name = _truncate_trigger_name(table)
        statements.append(f'DROP TRIGGER IF EXISTS {name} ON {table};')
        statements.append(
            f'CREATE TRIGGER {name} BEFORE TRUNCATE ON {table} '
            f'FOR EACH STATEMENT EXECUTE FUNCTION {TRUNCATE_FUNCTION}();')
    return statements


def install_table_sql(table):
    """Guards for one table, for the migration that creates it.

    A table added by a later migration is not protected by having been added to
    `PROTECTED_TABLES`: that list drives `install_audit_guards` and the test
    runner, neither of which runs against a competition database that has
    already been migrated. The migration has to install the triggers itself.
    """
    if table not in ALL_TABLES:
        raise ValueError(f'{table} is not a guarded audit table')
    reject = REJECT_FUNCTION if table in PROTECTED_TABLES else MANIFEST_FUNCTION
    name = _trigger_name(table)
    truncate = _truncate_trigger_name(table)
    return [
        # CREATE OR REPLACE throughout, so installing one table's guards on a
        # database that already has the others is a no-op for them.
        FUNCTIONS_SQL,
        f'DROP TRIGGER IF EXISTS {name} ON {table};',
        f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} '
        f'FOR EACH ROW EXECUTE FUNCTION {reject}();',
        f'DROP TRIGGER IF EXISTS {truncate} ON {table};',
        f'CREATE TRIGGER {truncate} BEFORE TRUNCATE ON {table} '
        f'FOR EACH STATEMENT EXECUTE FUNCTION {TRUNCATE_FUNCTION}();',
    ]


def uninstall_table_sql(table):
    """Remove one table's triggers, and nothing else.

    Deliberately leaves the shared functions in place: they are used by every
    other guarded table, and a reverse migration that dropped them would
    unprotect the audit tables it never touched.
    """
    return [
        f'DROP TRIGGER IF EXISTS {_trigger_name(table)} ON {table};',
        f'DROP TRIGGER IF EXISTS {_truncate_trigger_name(table)} ON {table};',
    ]


def uninstall_sql(all_tables=None):
    statements = []
    for table in (ALL_TABLES if all_tables is None else tuple(all_tables)):
        statements.append(
            f'DROP TRIGGER IF EXISTS {_trigger_name(table)} ON {table};')
        statements.append(
            f'DROP TRIGGER IF EXISTS {_truncate_trigger_name(table)} ON {table};')
    statements.append(f'DROP FUNCTION IF EXISTS {REJECT_FUNCTION}();')
    statements.append(f'DROP FUNCTION IF EXISTS {MANIFEST_FUNCTION}();')
    statements.append(f'DROP FUNCTION IF EXISTS {TRUNCATE_FUNCTION}();')
    statements.append(f'DROP FUNCTION IF EXISTS {POLICY_FUNCTION}(text);')
    return statements


def install(connection):
    with connection.cursor() as cursor:
        for statement in install_sql():
            cursor.execute(statement)


def uninstall(connection):
    with connection.cursor() as cursor:
        for statement in uninstall_sql():
            cursor.execute(statement)


def installed_triggers(connection):
    """Which guard triggers the database actually has right now."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.relname, t.tgname, t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            WHERE NOT t.tgisinternal
              AND (t.tgname LIKE '%%_append_only'
                   OR t.tgname LIKE '%%_no_truncate')
            ORDER BY c.relname, t.tgname
        """)
        return [{'table': row[0], 'trigger': row[1], 'enabled': row[2] == 'O'}
                for row in cursor.fetchall()]


def missing_guards(connection):
    """Guard triggers that should be installed and are not, or are disabled."""
    live = {(row['table'], row['trigger']): row
            for row in installed_triggers(connection)}
    missing = []
    for table in ALL_TABLES:
        for name, label in ((_trigger_name(table), 'append-only trigger'),
                            (_truncate_trigger_name(table), 'truncate trigger')):
            row = live.get((table, name))
            if row is None:
                missing.append({'table': table, 'problem': f'{label} missing'})
            elif not row['enabled']:
                missing.append({'table': table, 'problem': f'{label} disabled'})
    return missing


def provision_app_role_sql(role, password_placeholder='<password>'):
    """SQL that creates a least-privilege application role.

    The application currently connects as the owner of its own tables, which
    means the triggers above protect it from its own bugs but not from its own
    credentials. A non-owner role cannot drop a trigger, so running the
    application as this role turns "the app must not rewrite audit history"
    from a convention into something the database enforces.
    """
    audit_tables = ALL_TABLES
    statements = [
        f"-- Run as the database owner. Replace {password_placeholder}.",
        f"CREATE ROLE {role} LOGIN PASSWORD '{password_placeholder}';",
        "GRANT USAGE ON SCHEMA public TO %s;" % role,
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        "TO %s;" % role,
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %s;" % role,
    ]
    for table in audit_tables:
        statements.append(
            f'REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM {role};')
    statements.append(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %s;" % role)
    return statements


def privilege_report(connection, roles=None):
    """Who may UPDATE, DELETE or TRUNCATE each audit table."""
    audit_tables = ALL_TABLES
    with connection.cursor() as cursor:
        if roles is None:
            cursor.execute(
                'SELECT rolname FROM pg_roles WHERE rolcanlogin ORDER BY rolname')
            roles = [row[0] for row in cursor.fetchall()]
        rows = []
        for table in audit_tables:
            cursor.execute('SELECT tableowner FROM pg_tables WHERE tablename = %s',
                           [table])
            owner = cursor.fetchone()
            for role in roles:
                cursor.execute(
                    'SELECT has_table_privilege(%s, %s, %s), '
                    '       has_table_privilege(%s, %s, %s), '
                    '       has_table_privilege(%s, %s, %s)',
                    [role, table, 'UPDATE', role, table, 'DELETE',
                     role, table, 'INSERT'])
                update, delete, insert = cursor.fetchone()
                rows.append({
                    'table': table,
                    'owner': owner[0] if owner else None,
                    'role': role,
                    'is_owner': bool(owner) and owner[0] == role,
                    'update': update, 'delete': delete, 'insert': insert,
                })
    return rows
