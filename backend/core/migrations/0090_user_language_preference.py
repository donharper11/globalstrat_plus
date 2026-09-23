"""W-CE2-08: a place to store the language of a user who is not enrolled.

An instructor created from the console has no `Enrollment`, so
`PUT /api/user/preferences/` wrote nothing and `get_instructor_language`
could only answer `'en'` -- the AI Coach was English on a Chinese console.

Creates `user_language_preference`: one row per user id, holding the language
they last chose. It is a preference store only. No engine reads it, it is in
no manifest section, and no existing table or migration is altered. Reverse
drops the table.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0089_r47_compliance_expense_line'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLanguagePreference',
            fields=[
                ('user_id', models.IntegerField(primary_key=True,
                                                serialize=False)),
                ('language', models.CharField(default='en', max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'user_language_preference',
            },
        ),
    ]
