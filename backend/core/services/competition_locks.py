"""Transaction-scoped coordination between decision writes and round close."""
from django.db import connection


# Stable PostgreSQL advisory-lock namespace ("GSR").
_GAME_ROUND_LOCK_NAMESPACE = 0x475352
_TEAM_WRITE_LOCK_NAMESPACE = 0x475354


def lock_game_for_decision_write(game_id):
    """Allow concurrent writes, while excluding the deadline-close transaction."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock_shared(%s, %s)',
                [_GAME_ROUND_LOCK_NAMESPACE, game_id],
            )


def lock_game_for_round_close(game_id):
    """Wait for active writes and prevent new writes until close commits."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                [_GAME_ROUND_LOCK_NAMESPACE, game_id],
            )


def lock_team_for_decision_write(team_id):
    """Serialize first-save/upsert requests for one team without FK row locks."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                [_TEAM_WRITE_LOCK_NAMESPACE, team_id],
            )
