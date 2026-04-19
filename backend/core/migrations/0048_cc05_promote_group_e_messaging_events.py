"""CC-5 §5.5 Group E: Promote Messaging + Events ghosts (5 models).

Models promoted:
- Message → messages
- MessageResponse → message_responses
- MessageThread → message_threads
- NotificationLog → notification_logs
- TriggeredEvent → triggered_events

Authorized by CC-5 Amendment A1 rule #2 (live runtime reference):
- persona_engine.py, views/course.py call Message
- persona_engine.py calls TriggeredEvent
- MessageResponse, MessageThread, NotificationLog — viewset and related
  service-layer usage within the messaging subsystem

Note: TeamNotification is intentionally excluded — it was promoted in
CC-3.5 (migration 0040) and is already queryable.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_cc05_promote_group_d_simulation_state'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='message', options={'managed': True}),
                migrations.AlterModelOptions(name='messageresponse', options={'managed': True}),
                migrations.AlterModelOptions(name='messagethread', options={'managed': True}),
                migrations.AlterModelOptions(name='notificationlog', options={'managed': True}),
                migrations.AlterModelOptions(name='triggeredevent', options={'managed': True}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS messages (
                            message_id SERIAL PRIMARY KEY,
                            sender_name VARCHAR(255) NULL,
                            sender_title VARCHAR(255) NULL,
                            sender_type VARCHAR(50) NULL DEFAULT 'system',
                            persona_key VARCHAR(50) NULL,
                            recipient_type VARCHAR(50) NULL DEFAULT 'Team',
                            recipient_id INTEGER NULL,
                            subject VARCHAR(255) NULL,
                            message_body TEXT NULL,
                            round_number INTEGER NULL,
                            severity VARCHAR(20) NULL,
                            source VARCHAR(50) NULL,
                            avatar_image VARCHAR(255) NULL,
                            parent_message_id INTEGER NULL,
                            thread_root_id INTEGER NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            due_date TIMESTAMP WITH TIME ZONE NULL,
                            escalation_triggered BOOLEAN NULL DEFAULT FALSE,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS messages_recipient_idx
                            ON messages (recipient_type, recipient_id);
                        CREATE INDEX IF NOT EXISTS messages_thread_root_idx
                            ON messages (thread_root_id);

                        CREATE TABLE IF NOT EXISTS message_responses (
                            response_id SERIAL PRIMARY KEY,
                            message_id INTEGER NULL,
                            team_id INTEGER NULL,
                            response_text TEXT NULL,
                            impact_on_scores NUMERIC(10, 2) NULL,
                            feedback TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );
                        CREATE INDEX IF NOT EXISTS message_responses_message_id_idx
                            ON message_responses (message_id);

                        CREATE TABLE IF NOT EXISTS message_threads (
                            thread_id SERIAL PRIMARY KEY,
                            root_message_id INTEGER NULL,
                            follow_up_message_id INTEGER NULL,
                            thread_status VARCHAR(50) NULL DEFAULT 'Open',
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS message_threads_root_idx
                            ON message_threads (root_message_id);

                        CREATE TABLE IF NOT EXISTS notification_logs (
                            notification_id SERIAL PRIMARY KEY,
                            recipient_type VARCHAR(50) NULL,
                            recipient_id INTEGER NULL,
                            notification_text TEXT NOT NULL,
                            round_id INTEGER NULL,
                            sent_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS notification_logs_recipient_idx
                            ON notification_logs (recipient_type, recipient_id);

                        CREATE TABLE IF NOT EXISTS triggered_events (
                            triggered_event_id SERIAL PRIMARY KEY,
                            event_id INTEGER NULL,
                            round_id INTEGER NULL,
                            team_id INTEGER NULL,
                            resolved BOOLEAN NULL,
                            resolution_details TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS triggered_events_team_round_idx
                            ON triggered_events (team_id, round_id);
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS triggered_events;
                        DROP TABLE IF EXISTS notification_logs;
                        DROP TABLE IF EXISTS message_threads;
                        DROP TABLE IF EXISTS message_responses;
                        DROP TABLE IF EXISTS messages;
                    """,
                ),
            ],
        ),
    ]
