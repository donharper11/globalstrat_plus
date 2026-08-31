"""Install the database-level append-only guards.

Reversible: the triggers and functions are dropped, leaving every existing
audit row exactly where it was. No data is rewritten in either direction, so a
rollback on a running competition stack removes the protection without touching
the evidence it was protecting.

The table list is frozen here rather than read from `audit_guards`. A
historical migration has to describe the schema as it was: this originally
called `install_sql()` with no arguments, which read the live
`PROTECTED_TABLES`, so when CRV2-08 added the refusal table to that tuple this
migration began trying to install a trigger on a table that three later
migrations had not yet created. Already-migrated databases were unaffected and
said nothing; every fresh install failed.
"""
from django.db import migrations

from core.services.audit_guards import install_sql, uninstall_sql

# The audit tables that existed when this migration was written.
TABLES_AT_0070 = (
    'competition_decision_audit_event',
    'competition_operator_audit_event',
    'competition_sensitive_read_event',
    'competition_audit_chain',
)
MANIFEST_AT_0070 = 'competition_resolution_manifest'


class Migration(migrations.Migration):

    dependencies = [('core', '0069_audit_integrity')]

    operations = [
        migrations.RunSQL(
            sql=install_sql(protected=TABLES_AT_0070,
                            all_tables=TABLES_AT_0070 + (MANIFEST_AT_0070,)),
            reverse_sql=uninstall_sql(
                all_tables=TABLES_AT_0070 + (MANIFEST_AT_0070,)),
        ),
    ]
