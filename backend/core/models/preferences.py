"""Where a user's language lives when they are not enrolled anywhere.

A student's language is their `Enrollment.language`, which the in-game switch
and the sign-in record through `PUT /api/user/preferences/`. An instructor
created from the console has no enrolment at all, so that route had nothing to
write to and `get_instructor_language` could only ever answer `'en'`: the AI
Coach spoke English on a Chinese console whatever the instructor clicked
(W-CE2-08, second Consumer Electronics walkthrough).

This is a preference, not course data: one row per user, no section, no team,
nothing an engine reads and nothing in the determinism manifest. It is the
store the preference route writes for everyone; an enrolment is still written
too, so the two never disagree.
"""
from django.db import models


class UserLanguagePreference(models.Model):
    """The language a user last chose, by user id.

    `user_id` is the primary key rather than a foreign key because the two
    user tables this platform authenticates against (`core.User` for the
    platform's own accounts, Django's auth user for the ones a game is
    recorded against) do not share a key space, and a preference must not
    fail to save because the id belongs to the other one.
    """

    user_id = models.IntegerField(primary_key=True)
    language = models.CharField(max_length=10, default='en')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_language_preference'

    def __str__(self):
        return f'User {self.user_id}: {self.language}'
