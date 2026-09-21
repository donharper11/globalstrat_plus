"""The durable record of a committed game deletion (R45, V2-134).

Creates `competition_game_deletion_audit_event` and installs its append-only
and truncate guards in the same migration. The two belong together: migration
0078 created the refusal table and stopped there, and because adding a table to
`audit_guards.PROTECTED_TABLES` does nothing to a database that has already
been migrated, that table sat unprotected on a deployed upgrade until 0079
caught up. Here there is no commit at which the table exists without its
triggers.

No existing table is altered and no row is backfilled: a deletion committed
before this migration was recorded only in the `core.lifecycle` log, and this
table does not claim otherwise.

Reverse drops this table's two triggers and then the table. The shared trigger
functions stay, because every other audit table uses them.

AFTER APPLYING, ON THE COMPETITION HOST: re-run `ops/provision-app-role.sh`
and then `ops/provision-app-role.sh --check`. Default privileges hand the
application role UPDATE and DELETE on every new table, this one included; the
script is what takes them back off, and `--check` fails until it has.
"""
from django.db import migrations, models

TABLE = 'competition_game_deletion_audit_event'


def install_guards(apps, schema_editor):
    from core.services.audit_guards import install_table_sql
    with schema_editor.connection.cursor() as cursor:
        for statement in install_table_sql(TABLE):
            cursor.execute(statement)


def remove_guards(apps, schema_editor):
    from core.services.audit_guards import uninstall_table_sql
    with schema_editor.connection.cursor() as cursor:
        for statement in uninstall_table_sql(TABLE):
            cursor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0087_merge_20260912_0446'),
    ]

    operations = [
        migrations.CreateModel(
            name='GameDeletionAuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('game_id_deleted', models.BigIntegerField()),
                ('game_name', models.CharField(max_length=200)),
                ('scenario_id_value', models.BigIntegerField(blank=True, null=True)),
                ('scenario_name', models.CharField(blank=True, default='', max_length=200)),
                ('actor_user_id', models.IntegerField()),
                ('username', models.CharField(blank=True, default='', max_length=150)),
                ('action', models.CharField(default='delete_game', max_length=64)),
                ('reason', models.TextField()),
                ('before', models.JSONField(default=dict)),
                ('request_id', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': TABLE,
                'ordering': ['id'],
                'indexes': [
                    models.Index(fields=['game_id_deleted'], name='competition_game_id_02bc04_idx'),
                    models.Index(fields=['actor_user_id', 'created_at'], name='competition_actor_u_c9fa2e_idx'),
                    models.Index(fields=['created_at'], name='competition_created_211267_idx'),
                ],
            },
        ),
        migrations.RunPython(install_guards, remove_guards),
    ]
