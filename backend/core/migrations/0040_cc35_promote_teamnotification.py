"""CC-3.5 Part B: Promote messaging.TeamNotification from ghost to managed.

Prior to this migration the model was declared with ``managed=False`` and no
physical table existed — every ``TeamNotification.objects.create(...)`` was
silently swallowed by a try/except. This migration:

1. Flips the model to managed in Django's state tree.
2. Creates the ``team_notifications`` table for real.

We use ``SeparateDatabaseAndState`` because Django's autodetector only
emitted the state change; the table creation has to be spelled out.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_update_num_rounds_default_to_10'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='teamnotification',
                    options={},
                ),
                migrations.AlterField(
                    model_name='teamnotification',
                    name='is_read',
                    field=models.BooleanField(default=False),
                ),
                migrations.AlterField(
                    model_name='teamnotification',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS team_notifications (
                            notification_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            notification_text TEXT NOT NULL,
                            is_read BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_notifications_team_id_idx
                            ON team_notifications (team_id);
                        CREATE INDEX IF NOT EXISTS team_notifications_round_id_idx
                            ON team_notifications (round_id);
                    """,
                    reverse_sql="DROP TABLE IF EXISTS team_notifications;",
                ),
            ],
        ),
    ]
