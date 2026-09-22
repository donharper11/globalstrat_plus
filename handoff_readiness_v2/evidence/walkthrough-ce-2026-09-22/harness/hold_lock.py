"""Hold the exclusive lifecycle lock on a game, the way an operator action does.

Copied from evidence/open-interface-defects/harness/hold_lock.py and pointed
at this worktree and this stack's dbenv. While it is held a student's
decision write is refused with 409 `lifecycle_in_progress`, which is how the
walkthrough surfaces an autosave failure with the product's own refusal.

Run as:  hold_lock.py <game_id> <seconds>
"""
import os
import pathlib
import sys
import time

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]
for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value
sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                     # noqa: E402
django.setup()

from django.db import transaction                                 # noqa: E402
from core.services.competition_locks import lock_game_for_lifecycle  # noqa: E402

GAME_ID = int(sys.argv[1])
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0


def main():
    with transaction.atomic():
        lock_game_for_lifecycle(GAME_ID)
        print('HELD game %d for %.0fs' % (GAME_ID, SECONDS), flush=True)
        time.sleep(SECONDS)
    print('RELEASED', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
