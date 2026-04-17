from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_results_and_event_fk'),
    ]

    operations = [
        migrations.RunSQL(
            sql='CREATE INDEX idx_adoption_team_round ON round_result_adoption(team_id, round_number);',
            reverse_sql='DROP INDEX IF EXISTS idx_adoption_team_round;',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX idx_adoption_game_round ON round_result_adoption(game_id, round_number);',
            reverse_sql='DROP INDEX IF EXISTS idx_adoption_game_round;',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX idx_modifier_game_expires ON active_modifier(game_id, expires_round);',
            reverse_sql='DROP INDEX IF EXISTS idx_modifier_game_expires;',
        ),
    ]
