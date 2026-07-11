from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_cc19_event_sc_effects'),
    ]

    operations = [
        migrations.AddField(
            model_name='resiliencescorehistory',
            name='disruption_impact',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
