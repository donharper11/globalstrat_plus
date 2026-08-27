from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0058_roundresultfinancials_platform_amortization')]
    operations = [
        migrations.AddField(model_name='round', name='decisions_locked', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='round', name='lock_reason', field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AlterField(model_name='decisionsubmission', name='locked_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='locked_submissions', to='core.user')),
        migrations.CreateModel(
            name='DecisionAuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=32)), ('endpoint', models.CharField(max_length=255)),
                ('payload', models.JSONField(default=dict)), ('payload_sha256', models.CharField(max_length=64)),
                ('request_id', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.game')),
                ('round', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.round')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.team')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.user')),
            ], options={'db_table': 'competition_decision_audit_event', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='OperatorAuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=64)), ('reason', models.TextField()),
                ('before', models.JSONField(default=dict)), ('after', models.JSONField(default=dict)),
                ('request_id', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.game')),
                ('round', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.round')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.user')),
            ], options={'db_table': 'competition_operator_audit_event', 'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='ResolutionManifest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('seed', models.CharField(max_length=64)), ('input_manifest', models.JSONField(default=dict)),
                ('input_sha256', models.CharField(max_length=64)), ('output_manifest', models.JSONField(default=dict)),
                ('output_sha256', models.CharField(blank=True, default='', max_length=64)),
                ('code_revision', models.CharField(blank=True, default='', max_length=64)),
                ('backup_path', models.TextField(blank=True, default='')), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.game')),
                ('round', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='resolution_manifest', to='core.round')),
            ], options={'db_table': 'competition_resolution_manifest'},
        ),
    ]
