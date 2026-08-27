from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0059_competition_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='team', name='participation_status',
            field=models.CharField(
                choices=[('active', 'Active'), ('withdrawn', 'Withdrawn')],
                default='active', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='team', name='withdrawal_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='team', name='withdrawn_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='team', name='withdrawn_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='withdrawn_teams', to='core.user',
            ),
        ),
    ]
