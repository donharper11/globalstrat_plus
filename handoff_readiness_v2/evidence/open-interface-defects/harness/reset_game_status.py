"""Put the fixture game back to `active` between language passes.

The English pass exercises Pause, which leaves the game `paused` -- and the
Pause control only renders for an active game, so the Chinese pass would find
nothing to click and would report a defect that is not there. Resetting the
status between runs keeps the two passes comparable.

Only `status` is touched; no round, submission or result is altered.
"""
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                  '/agent-a32f4655be8cf1452')

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                     # noqa: E402
django.setup()

from core.models import Game                                      # noqa: E402

import json                                                       # noqa: E402
fx = json.loads((SCRATCH / 'fixture.json').read_text())
game = Game.objects.get(pk=fx['game_id'])
was = game.status
Game.objects.filter(pk=game.pk).update(status='active')
print('game %d: %s -> active' % (game.id, was))
