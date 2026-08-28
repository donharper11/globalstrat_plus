"""Close a caller-controlled TRUNCATE bypass in the audit guards.

`0071` authorised the test-reset exception on `current_setting(
'globalstrat.allow_truncate')` alone. PostgreSQL lets any ordinary session set
a custom setting, and the application connects as the tables' owner, so the
application context the guards exist to refuse could run:

    SET globalstrat.allow_truncate = 'on';
    TRUNCATE competition_decision_audit_event;

without dropping a single trigger. The allowance now also requires the database
to be named the way Django names an isolated test database, which a session
cannot change. The setting is kept, so a test can withdraw the allowance and
watch the guard fire, but it can only make the rule stricter.

Existing databases need this migration: `0071` installed the permissive
function body into the database, and editing the Python source that generated
it does not reach an installed function.
"""
from django.db import migrations

from core.services.audit_guards import install_sql, uninstall_sql


class Migration(migrations.Migration):

    dependencies = [('core', '0071_audit_truncate_guards')]

    operations = [
        migrations.RunSQL(sql=install_sql(), reverse_sql=uninstall_sql()),
    ]
