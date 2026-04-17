"""
Custom indexes for CC-06 financial result tables.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_cc06_financial_results'),
    ]

    operations = [
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_financials_team_round ON round_result_financials(team_id, round_number);',
            reverse_sql='DROP INDEX IF EXISTS idx_financials_team_round;',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_leaderboard ON leaderboard_entry(game_id, round_number);',
            reverse_sql='DROP INDEX IF EXISTS idx_leaderboard;',
        ),
    ]
