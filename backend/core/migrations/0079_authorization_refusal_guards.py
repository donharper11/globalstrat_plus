"""Install the append-only guards for the refusal table.

Migration 0078 created `competition_authorization_refusal_event` and stopped
there. Adding the table to `audit_guards.PROTECTED_TABLES` changes what
`install_audit_guards` would install and what the test runner installs when it
builds a test database; it does nothing to a competition database that has
already been migrated. On that database the table existed with no UPDATE,
DELETE or TRUNCATE protection at all, while the report claimed otherwise.

Reverse removes only this table's two triggers. The shared trigger functions
stay: every other audit table uses them, and dropping them here would unprotect
tables this migration never touched.
"""
from django.db import migrations

TABLE = 'competition_authorization_refusal_event'


def install(apps, schema_editor):
    from core.services.audit_guards import install_table_sql
    with schema_editor.connection.cursor() as cursor:
        for statement in install_table_sql(TABLE):
            cursor.execute(statement)


def remove(apps, schema_editor):
    from core.services.audit_guards import uninstall_table_sql
    with schema_editor.connection.cursor() as cursor:
        for statement in uninstall_table_sql(TABLE):
            cursor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [('core', '0078_authorization_refusal_event')]

    operations = [migrations.RunPython(install, remove)]
