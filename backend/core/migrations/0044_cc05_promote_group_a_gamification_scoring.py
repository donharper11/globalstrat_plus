"""CC-5 §5.5 Group A: Promote Gamification & Scoring ghosts (10 models).

Promotes the 10 Gamification + Scoring ghost models from ``managed=False`` to
``managed=True`` and creates their physical tables. Follows the CC-3.5
SeparateDatabaseAndState pattern — Django's autodetector emits only the
``AlterModelOptions`` state change, so table creation is spelled out in the
``database_operations``.

Models promoted:
- Achievement → achievements
- GamificationBadge → gamification_badges
- PlayerProgress → player_progress
- TeamAchievement → team_achievements
- TeamBadge → team_badges
- ScoreType → score_types
- Score → scores
- LeaderboardMetric → leaderboard_metrics
- LeaderboardScore → leaderboard_scores
- TeamPerformance → team_performance

All foreign keys are plain IntegerField columns in the model declarations
(no Django ForeignKey constraints), so the CREATE TABLE statements mirror
that: integer columns, no FK constraints, no cascades.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_cc05_prune_ghost_models'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='achievement', options={}),
                migrations.AlterModelOptions(name='gamificationbadge', options={}),
                migrations.AlterModelOptions(name='playerprogress', options={}),
                migrations.AlterModelOptions(name='teamachievement', options={}),
                migrations.AlterModelOptions(name='teambadge', options={}),
                migrations.AlterModelOptions(name='scoretype', options={}),
                migrations.AlterModelOptions(name='score', options={}),
                migrations.AlterModelOptions(name='leaderboardmetric', options={}),
                migrations.AlterModelOptions(name='leaderboardscore', options={}),
                migrations.AlterModelOptions(name='teamperformance', options={}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS achievements (
                            achievement_id SERIAL PRIMARY KEY,
                            achievement_name VARCHAR(255) NOT NULL,
                            description TEXT NULL,
                            criteria TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );

                        CREATE TABLE IF NOT EXISTS gamification_badges (
                            badge_id SERIAL PRIMARY KEY,
                            badge_name VARCHAR(255) NOT NULL,
                            description TEXT NULL,
                            criteria TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );

                        CREATE TABLE IF NOT EXISTS player_progress (
                            progress_id SERIAL PRIMARY KEY,
                            game_id INTEGER NOT NULL,
                            round_number INTEGER NOT NULL,
                            team_id INTEGER NOT NULL,
                            milestone_id INTEGER NULL,
                            achieved_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS player_progress_team_id_idx
                            ON player_progress (team_id);
                        CREATE INDEX IF NOT EXISTS player_progress_game_round_idx
                            ON player_progress (game_id, round_number);

                        CREATE TABLE IF NOT EXISTS team_achievements (
                            team_achievement_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            achievement_id INTEGER NULL,
                            round_id INTEGER NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_achievements_team_id_idx
                            ON team_achievements (team_id);

                        CREATE TABLE IF NOT EXISTS team_badges (
                            team_badge_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            badge_id INTEGER NULL,
                            round_id INTEGER NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_badges_team_id_idx
                            ON team_badges (team_id);

                        CREATE TABLE IF NOT EXISTS score_types (
                            score_type_id SERIAL PRIMARY KEY,
                            score_name VARCHAR(255) NOT NULL,
                            description TEXT NULL,
                            weight NUMERIC(5, 2) NULL
                        );

                        CREATE TABLE IF NOT EXISTS scores (
                            score_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            stakeholder_id INTEGER NULL,
                            score_type_id INTEGER NULL,
                            score NUMERIC(10, 2) NULL,
                            feedback TEXT NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS scores_team_id_idx ON scores (team_id);
                        CREATE INDEX IF NOT EXISTS scores_round_id_idx ON scores (round_id);

                        CREATE TABLE IF NOT EXISTS leaderboard_metrics (
                            metric_id SERIAL PRIMARY KEY,
                            metric_name VARCHAR(255) NOT NULL,
                            description TEXT NULL,
                            weight NUMERIC(5, 2) NULL
                        );

                        CREATE TABLE IF NOT EXISTS leaderboard_scores (
                            leaderboard_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            metric_id INTEGER NULL,
                            score NUMERIC(10, 2) NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS leaderboard_scores_team_id_idx
                            ON leaderboard_scores (team_id);

                        CREATE TABLE IF NOT EXISTS team_performance (
                            performance_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            total_score NUMERIC(10, 2) NULL,
                            average_stakeholder_satisfaction NUMERIC(5, 2) NULL,
                            ethical_alignment NUMERIC(5, 2) NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_performance_team_id_idx
                            ON team_performance (team_id);
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS team_performance;
                        DROP TABLE IF EXISTS leaderboard_scores;
                        DROP TABLE IF EXISTS leaderboard_metrics;
                        DROP TABLE IF EXISTS scores;
                        DROP TABLE IF EXISTS score_types;
                        DROP TABLE IF EXISTS team_badges;
                        DROP TABLE IF EXISTS team_achievements;
                        DROP TABLE IF EXISTS player_progress;
                        DROP TABLE IF EXISTS gamification_badges;
                        DROP TABLE IF EXISTS achievements;
                    """,
                ),
            ],
        ),
    ]
