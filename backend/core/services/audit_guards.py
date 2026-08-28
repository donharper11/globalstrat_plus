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
# The escape hatch exists because Django's `TransactionTestCase` resets the
# database by truncating every table, so a guard with no way to say "this is a
# test database" could only be installed where no test could reach it. The
# setting is never set in production, and a test that wants to prove the guard
# turns it off for one transaction.
TRUNCATE_SETTING = 'globalstrat.allow_truncate'


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

CREATE OR REPLACE FUNCTION {TRUNCATE_FUNCTION}() RETURNS trigger AS $$
BEGIN
    IF COALESCE(current_setting('{TRUNCATE_SETTING}', true), 'off') = 'on' THEN
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


def install_sql():
    """Every statement that installs the guards, in order."""
    statements = [FUNCTIONS_SQL]
    for table in PROTECTED_TABLES:
        name = _trigger_name(table)
        statements.append(f'DROP TRIGGER IF EXISTS {name} ON {table};')
        statements.append(
            f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} '
            f'FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION}();')
    name = _trigger_name(MANIFEST_TABLE)
    statements.append(f'DROP TRIGGER IF EXISTS {name} ON {MANIFEST_TABLE};')
    statements.append(
        f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {MANIFEST_TABLE} '
        f'FOR EACH ROW EXECUTE FUNCTION {MANIFEST_FUNCTION}();')
    for table in ALL_TABLES:
        name = _truncate_trigger_name(table)
        statements.append(f'DROP TRIGGER IF EXISTS {name} ON {table};')
        statements.append(
            f'CREATE TRIGGER {name} BEFORE TRUNCATE ON {table} '
            f'FOR EACH STATEMENT EXECUTE FUNCTION {TRUNCATE_FUNCTION}();')
    return statements


def uninstall_sql():
    statements = []
    for table in ALL_TABLES:
        statements.append(
            f'DROP TRIGGER IF EXISTS {_trigger_name(table)} ON {table};')
        statements.append(
            f'DROP TRIGGER IF EXISTS {_truncate_trigger_name(table)} ON {table};')
    statements.append(f'DROP FUNCTION IF EXISTS {REJECT_FUNCTION}();')
    statements.append(f'DROP FUNCTION IF EXISTS {MANIFEST_FUNCTION}();')
    statements.append(f'DROP FUNCTION IF EXISTS {TRUNCATE_FUNCTION}();')
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
