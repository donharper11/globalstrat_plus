"""CC-32A: Stakeholder communication assignments and team submissions."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_cc31j_governance_commitments'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunicationAssignment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=200)),
                ('trigger_type', models.CharField(max_length=30, choices=[
                    ('ROUND_MILESTONE', 'Fires at a specific round'),
                    ('DECISION_BASED', 'Fires when team makes a specific decision'),
                    ('EVENT_BASED', 'Fires when a specific event type hits the team'),
                ])),
                ('trigger_condition', models.JSONField(help_text="E.g., {'round': 2} or {'event_category': ['GEOPOLITICAL', 'SANCTIONS']}")),
                ('audience', models.CharField(max_length=50, choices=[
                    ('BOARD', 'Board of Directors'),
                    ('EMPLOYEES', 'All Employees'),
                    ('INVESTORS', 'Investor Community'),
                    ('REGULATORS', 'Regulatory Authorities'),
                    ('PUBLIC', 'Press / Public Statement'),
                    ('PARTNER', 'Alliance / JV Partner'),
                ])),
                ('prompt_text', models.TextField(help_text='Scenario/context shown to students explaining what to communicate and why')),
                ('word_limit', models.IntegerField(default=300)),
                ('evaluation_criteria', models.JSONField(help_text='List of {criterion, weight, description} dicts for LLM evaluation')),
                ('is_mandatory', models.BooleanField(default=False)),
                ('coherence_weight', models.DecimalField(decimal_places=2, default=0.05, max_digits=4, help_text='How much this communication contributes to the coherence score')),
                ('display_order', models.IntegerField(default=0)),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comm_assignments', to='core.scenario')),
            ],
            options={
                'db_table': 'communication_assignment',
                'ordering': ['display_order'],
                'unique_together': {('scenario', 'code')},
            },
        ),
        migrations.CreateModel(
            name='TeamCommunication',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('content', models.TextField(default='', help_text="The team's drafted communication")),
                ('word_count', models.IntegerField(default=0)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('is_draft', models.BooleanField(default=True)),
                ('evaluation', models.JSONField(blank=True, null=True, help_text='LLM evaluation results')),
                ('coherence_contribution', models.DecimalField(decimal_places=2, default=0, max_digits=4, help_text='Points added to coherence score based on evaluation quality')),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='core.communicationassignment')),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communications', to='core.game')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communications', to='core.team')),
                ('round', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communications', to='core.round')),
            ],
            options={
                'db_table': 'team_communication',
                'unique_together': {('game', 'team', 'round', 'assignment')},
            },
        ),
    ]
