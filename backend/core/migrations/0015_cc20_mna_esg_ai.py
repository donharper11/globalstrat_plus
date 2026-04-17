"""CC-20: M&A models, AI competitor behavior, team modifiers.

Restructures DecisionAcquisition (removes market/target/offer_price, adds acquisition_target FK).
Creates AcquisitionTarget, TeamAcquisition, TeamMarketModifier, AICompetitorBehavior.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_add_distribution_channel_detail'),
    ]

    operations = [
        # New models
        migrations.CreateModel(
            name='AcquisitionTarget',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('target_name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('base_acquisition_cost', models.DecimalField(decimal_places=2, max_digits=15)),
                ('market_share_gained', models.DecimalField(decimal_places=4, max_digits=5)),
                ('includes_plant', models.BooleanField(default=False)),
                ('plant_capacity', models.IntegerField(default=0)),
                ('includes_distribution', models.BooleanField(default=False)),
                ('distribution_reach_bonus', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('talent_bonus', models.JSONField(default=dict)),
                ('min_round_available', models.IntegerField(default=2)),
                ('requires_market_presence', models.BooleanField(default=True)),
                ('integration_rounds', models.IntegerField(default=2)),
                ('integration_cost_per_round', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='acquisition_targets', to='core.marketdefinition')),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acquisition_targets', to='core.scenario')),
            ],
            options={
                'db_table': 'acquisition_target',
                'unique_together': {('scenario', 'market')},
            },
        ),
        migrations.CreateModel(
            name='TeamAcquisition',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('acquired_round', models.IntegerField()),
                ('integration_complete', models.BooleanField(default=False)),
                ('integration_rounds_remaining', models.IntegerField()),
                ('total_cost_paid', models.DecimalField(decimal_places=2, max_digits=15)),
                ('acquisition_target', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='team_acquisitions', to='core.acquisitiontarget')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acquisitions', to='core.team')),
            ],
            options={
                'db_table': 'team_acquisition',
                'unique_together': {('team', 'acquisition_target')},
            },
        ),
        migrations.CreateModel(
            name='TeamMarketModifier',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('modifier_type', models.CharField(max_length=50)),
                ('value', models.FloatField()),
                ('source', models.CharField(max_length=200)),
                ('expires_round', models.IntegerField(blank=True, null=True)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='team_modifiers', to='core.marketdefinition')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='market_modifiers', to='core.team')),
            ],
            options={
                'db_table': 'team_market_modifier',
            },
        ),
        migrations.CreateModel(
            name='AICompetitorBehavior',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('strategy_type', models.CharField(choices=[('aggressive', 'Aggressive — pursues market share'), ('defensive', 'Defensive — protects existing position'), ('niche', 'Niche — focuses on specific segments'), ('adaptive', 'Adaptive — responds to market leader')], max_length=30)),
                ('price_sensitivity', models.DecimalField(decimal_places=2, default=0.5, max_digits=3)),
                ('innovation_rate', models.DecimalField(decimal_places=2, default=0.3, max_digits=3)),
                ('market_entry_threshold', models.DecimalField(decimal_places=4, default=0.05, max_digits=5)),
                ('primary_segments', models.JSONField(default=list)),
                ('ai_competitor', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='behavior', to='core.aicompetitordefinition')),
            ],
            options={
                'db_table': 'ai_competitor_behavior',
            },
        ),
        # Restructure DecisionAcquisition: remove old fields, add new FK
        migrations.RemoveField(model_name='decisionacquisition', name='market'),
        migrations.RemoveField(model_name='decisionacquisition', name='target'),
        migrations.RemoveField(model_name='decisionacquisition', name='offer_price'),
        migrations.AddField(
            model_name='decisionacquisition',
            name='acquisition_target',
            field=models.ForeignKey(
                default=1,  # placeholder; table is empty after flush
                on_delete=django.db.models.deletion.PROTECT,
                related_name='acquisition_decisions',
                to='core.acquisitiontarget',
            ),
            preserve_default=False,
        ),
    ]
