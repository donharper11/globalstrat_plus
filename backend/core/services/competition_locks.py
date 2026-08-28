"""The one coordination boundary competition writes serialise on.

There is a single documented lock order, and no path acquires these in
reverse:

1. ``lock_game_for_lifecycle(game_id)`` — exclusive, or
   ``lock_game_for_decision_write(game_id)`` — shared. Same advisory lock;
   student writes take it shared so they run concurrently with each other,
   and every operator action that can change the round takes it exclusively,
   so it excludes both student writes *and* every other operator action.
2. ``Game`` row (``select_for_update``).
3. ``Round`` row (``select_for_update``).
4. ``lock_team_for_decision_write(team_id)``.
5. ``Team`` / ``DecisionSubmission`` rows.

The advisory locks are transaction-scoped: PostgreSQL releases them at commit
or rollback, they are re-entrant within one transaction, and they cost nothing
when uncontended. Taking one is therefore safe inside a nested ``atomic()``
block that already holds it.

Every precondition an operator action checks must be evaluated *after* step 1.
State read before the boundary is a guess about a value another operator may
already be changing.
"""
from django.db import connection


# Stable PostgreSQL advisory-lock namespace ("GSR").
_GAME_ROUND_LOCK_NAMESPACE = 0x475352
_TEAM_WRITE_LOCK_NAMESPACE = 0x475354


def lock_game_for_decision_write(game_id):
    """Allow concurrent student writes, while excluding every operator action."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock_shared(%s, %s)',
                [_GAME_ROUND_LOCK_NAMESPACE, game_id],
            )


def lock_game_for_lifecycle(game_id):
    """Serialise this operator action against writes and other operators.

    Held until the transaction ends, so a caller that acquires it and then
    re-reads the round is looking at state nobody else can be changing.
    """
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                [_GAME_ROUND_LOCK_NAMESPACE, game_id],
            )


# Historical name for the same lock, kept because close is its oldest caller.
lock_game_for_round_close = lock_game_for_lifecycle


def lock_team_for_decision_write(team_id):
    """Serialize first-save/upsert requests for one team without FK row locks."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                [_TEAM_WRITE_LOCK_NAMESPACE, team_id],
            )
