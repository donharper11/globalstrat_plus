"""CC-31J: Governance commitment types and team governance tracking."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_cc31g_investor_fund_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='GovernanceCommitmentType',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=30)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('ongoing_cost_per_round', models.DecimalField(
                    decimal_places=2, max_digits=10,
                    help_text='Cash cost per round while commitment is active',
                )),
                ('benefits', models.JSONField(default=list, help_text='List of stakeholder feature boosts when commitment is active')),
                ('interactions', models.JSONField(default=list, help_text='Conditional effects based on other team decisions')),
                ('revocation_penalty', models.JSONField(default=dict, help_text='Penalties applied after revoking: duration_rounds, investor_confidence_drop, etc.')),
                ('prerequisite', models.JSONField(blank=True, null=True, help_text='Condition that must be met to activate this commitment')),
                ('amplifier', models.JSONField(blank=True, null=True, help_text='If set, this commitment multiplies the effectiveness of another ESG investment')),
                ('display_order', models.IntegerField(default=0)),
                ('scenario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='governance_commitments',
                    to='core.scenario',
                )),
            ],
            options={
                'db_table': 'governance_commitment_type',
                'ordering': ['display_order'],
                'unique_together': {('scenario', 'code')},
            },
        ),
        migrations.CreateModel(
            name='TeamGovernanceCommitment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=False)),
                ('activated_round', models.IntegerField(blank=True, null=True)),
                ('revoked_round', models.IntegerField(blank=True, null=True)),
                ('penalty_rounds_remaining', models.IntegerField(
                    default=0,
                    help_text='Rounds of revocation penalty still active. Decrements each round.',
                )),
                ('commitment_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team_commitments',
                    to='core.governancecommitmenttype',
                )),
                ('game', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='governance_commitments',
                    to='core.game',
                )),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='governance_commitments',
                    to='core.team',
                )),
            ],
            options={
                'db_table': 'team_governance_commitment',
                'unique_together': {('game', 'team', 'commitment_type')},
            },
        ),
    ]
