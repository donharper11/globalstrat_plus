"""
Session tracking for the custom core.models.User model.

Auth is stateless JWT, so there is no Django session to inspect. To answer
"who is logged in right now, and for how long?" we record a row per login and
touch last_seen_at on each authenticated request (throttled by middleware).

The `users` table is managed=False (legacy raw-SQL table), so this lives in its
own managed table rather than as columns on User.
"""
from django.db import models
from django.utils import timezone


class UserSession(models.Model):
    """One row per login. Considered 'active' while last_seen_at is recent."""

    # A session is considered live if seen within this many minutes.
    IDLE_TIMEOUT_MINUTES = 15

    id = models.BigAutoField(primary_key=True)
    user_id = models.IntegerField(db_index=True)
    username = models.CharField(max_length=255, blank=True, default='')
    display_name = models.CharField(max_length=200, blank=True, default='')
    role = models.CharField(max_length=50, blank=True, default='')

    # Denormalised so the instructor console can filter by game without
    # re-deriving enrollment on every poll.
    game_id = models.IntegerField(null=True, blank=True, db_index=True)
    team_id = models.IntegerField(null=True, blank=True)
    team_name = models.CharField(max_length=200, blank=True, default='')

    login_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    logout_at = models.DateTimeField(null=True, blank=True)

    ip_address = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        db_table = 'user_session'
        indexes = [
            models.Index(fields=['game_id', 'last_seen_at']),
        ]

    def __str__(self):
        return f'{self.username} @ {self.login_at:%Y-%m-%d %H:%M}'

    @property
    def is_active(self):
        if self.logout_at:
            return False
        cutoff = timezone.now() - timezone.timedelta(
            minutes=self.IDLE_TIMEOUT_MINUTES,
        )
        return self.last_seen_at >= cutoff

    @property
    def duration_minutes(self):
        """Minutes from login until logout, or until last seen if still live."""
        end = self.logout_at or self.last_seen_at
        return int((end - self.login_at).total_seconds() // 60)

    @property
    def idle_minutes(self):
        return int((timezone.now() - self.last_seen_at).total_seconds() // 60)

    @classmethod
    def active_qs(cls, game_id=None):
        cutoff = timezone.now() - timezone.timedelta(
            minutes=cls.IDLE_TIMEOUT_MINUTES,
        )
        qs = cls.objects.filter(logout_at__isnull=True, last_seen_at__gte=cutoff)
        if game_id is not None:
            qs = qs.filter(game_id=game_id)
        return qs.order_by('-last_seen_at')
