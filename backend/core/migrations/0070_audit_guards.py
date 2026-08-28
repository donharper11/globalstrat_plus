"""Install the database-level append-only guards.

Reversible: `uninstall_sql()` drops the triggers and functions, leaving every
existing audit row exactly where it was. No data is rewritten in either
direction, so a rollback on a running competition stack removes the protection
without touching the evidence it was protecting.
"""
from django.db import migrations

from core.services.audit_guards import install_sql, uninstall_sql


class Migration(migrations.Migration):

    dependencies = [('core', '0069_audit_integrity')]

    operations = [
        migrations.RunSQL(sql=install_sql(), reverse_sql=uninstall_sql()),
    ]
