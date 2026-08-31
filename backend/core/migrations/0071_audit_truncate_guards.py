"""Refuse `TRUNCATE` on the audit tables.

Found by GSP-CRV2-04's own certification run, which attempted every bypass
against a migrated database and discovered that this one worked: `TRUNCATE`
does not fire row-level triggers, so `0070`'s guards watched an audit table
being emptied without firing once.

Reinstalls the whole guard set rather than only the new triggers, so a database
that has 0070 and a database that has both end up with byte-identical DDL.
"""
from django.db import migrations

from core.services.audit_guards import install_sql, uninstall_sql

# Frozen: the audit tables that existed when this migration was written. See
# 0070 for why a historical migration must not read the live table list.
TABLES_THEN = (
    'competition_decision_audit_event',
    'competition_operator_audit_event',
    'competition_sensitive_read_event',
    'competition_audit_chain',
)
MANIFEST_THEN = 'competition_resolution_manifest'



class Migration(migrations.Migration):

    dependencies = [('core', '0070_audit_guards')]

    operations = [
        migrations.RunSQL(
            sql=install_sql(protected=TABLES_THEN,
                            all_tables=TABLES_THEN + (MANIFEST_THEN,)),
            reverse_sql=uninstall_sql(
                all_tables=TABLES_THEN + (MANIFEST_THEN,)),
        ),
    ]
