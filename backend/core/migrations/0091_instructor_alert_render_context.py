"""W-CE3-08: let a stored coach alert be re-rendered in the reader's language.

An `InstructorAlert` is written in the language stored at processing time, so
alerts written before an instructor set their language stayed English for ever
and the AI Coach panel was permanently mixed (W-CE2-08's recorded residue).
Unlike a coherence breakdown, the row keeps no numbers to re-derive the
sentence from -- only the finished sentence -- so the rendering inputs are
stored: `{'key': …, 'language': …, 'values': {…}}`.

`render_context` is excluded from both manifest sections that claim this model
(`instructor_alert`, `narrative_alert`) with that justification, so no hashed
value changes and the manifest envelope does not move. Adding the column
alters no existing value: it is nullable with a `None` default, and an alert
written before it existed is served exactly as stored.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0090_user_language_preference'),
    ]

    operations = [
        migrations.AddField(
            model_name='instructoralert',
            name='render_context',
            field=models.JSONField(blank=True, null=True, default=None),
        ),
    ]
