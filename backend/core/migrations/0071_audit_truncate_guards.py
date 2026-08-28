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


class Migration(migrations.Migration):

    dependencies = [('core', '0070_audit_guards')]

    operations = [
        migrations.RunSQL(sql=install_sql(), reverse_sql=uninstall_sql()),
    ]
