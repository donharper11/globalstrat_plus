"""Hold the exclusive lifecycle lock on a game, the way an operator action does.

This is the condition V2-064 is about. `lock_game_for_lifecycle` is what
`extend_deadline`, `inject_event`, `close_round` and `advance_round` all take,
and while it is held a student's decision write is refused with 409
`lifecycle_in_progress` by CompetitionDecisionWriteMixin -- before any handler
runs, so nothing is validated and nothing is written.

Holding it from a separate process, rather than clicking Extend Deadline in a
second browser, is deliberate: it makes the window long enough to observe and
it holds the same lock by the same call, so the refusal the student sees is
the product's own, not a simulation of it.

Run as:  hold_lock.py <game_id> <seconds>
"""
import os
import pathlib
import sys
import time

import django

WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                  '/agent-a32f4655be8cf1452')
sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.db import transaction                                 # noqa: E402

from core.services.competition_locks import lock_game_for_lifecycle  # noqa: E402

GAME_ID = int(sys.argv[1])
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0


def main():
    # The lock is transaction-scoped (pg_advisory_xact_lock), so the holding
    # transaction has to stay open for as long as the window lasts.
    with transaction.atomic():
        lock_game_for_lifecycle(GAME_ID)
        print('HELD game %d for %.0fs' % (GAME_ID, SECONDS), flush=True)
        time.sleep(SECONDS)
    print('RELEASED', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
