"""
Custom indexes for Group 3/4 tables + Group 2 indexes.
From 04-data-model.md index specification.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # Group 2 indexes
        migrations.RunSQL(
            "CREATE INDEX idx_segment_pref_segment ON segment_preference(segment_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_segment_pref_segment;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_segment_pref_feature ON segment_preference(feature_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_segment_pref_feature;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_feature_def_scenario ON feature_definition(scenario_id, layer);",
            reverse_sql="DROP INDEX IF EXISTS idx_feature_def_scenario;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_readiness ON market_readiness(market_id, platform_generation_id, round_number);",
            reverse_sql="DROP INDEX IF EXISTS idx_readiness;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_ai_fit ON ai_competitor_fit_by_round(ai_competitor_id, segment_id, market_id, round_number);",
            reverse_sql="DROP INDEX IF EXISTS idx_ai_fit;",
        ),
        # Group 4 indexes
        migrations.RunSQL(
            "CREATE INDEX idx_team_presence ON team_market_presence(team_id, market_id, status);",
            reverse_sql="DROP INDEX IF EXISTS idx_team_presence;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_product_market_active ON team_product_market(team_product_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_market_active;",
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_pending_gain ON pending_feature_gain(team_platform_id, applies_round, applied);",
            reverse_sql="DROP INDEX IF EXISTS idx_pending_gain;",
        ),
    ]
