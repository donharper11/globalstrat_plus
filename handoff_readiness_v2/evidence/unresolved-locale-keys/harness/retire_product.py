"""Retire one product so `common.retired` has a live call site to render.

`ProductsPage.js:185` is one of only two label-less StatusBadge call sites, and
it renders `common.retired` only for a product whose status is 'retired'. The
seeded fixture's products are all active, so without this the key has nothing
to render and a browser pass would prove nothing about it.
"""
import os
import pathlib
import sys

import django

WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                  '/agent-ad31a78c64885fc47')
sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from core.models import Game, Team                      # noqa: E402
from core.models.team_state import TeamProduct          # noqa: E402


def main():
    game = Game.objects.order_by('id').first()
    team = Team.objects.filter(game=game).order_by('id').first()
    products = list(TeamProduct.objects.filter(team=team).order_by('id'))
    if len(products) < 2:
        raise SystemExit('need at least two products; found %d' % len(products))
    target = products[-1]
    target.status = 'retired'
    target.save(update_fields=['status'])
    print('game=%s team=%s' % (game.id, team.name))
    for p in TeamProduct.objects.filter(team=team).order_by('id'):
        print('   %-20s status=%s positioning=%s' % (p.name, p.status,
                                                     p.positioning))
    print('retired: %s -- common.retired now has something to render'
          % target.name)


if __name__ == '__main__':
    main()
