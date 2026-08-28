"""What a demo-seeded game gives us to screen against, and how fast."""
import json, time
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

t0 = time.time()
if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('screen-owner', 'a@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)
t1 = time.time()
call_command('load_demo', verbosity=0)
t2 = time.time()

from core.models import Game, Round, Team
from core.models.team_state import TeamProduct, TeamPlatform, TeamMarketPresence

game = Game.objects.order_by('-id').first()
teams = list(Team.objects.filter(game=game).order_by('id'))
rounds = list(Round.objects.filter(game=game).order_by('round_number'))

out = {
    'scenarios_seconds': round(t1 - t0, 1),
    'demo_seconds': round(t2 - t1, 1),
    'game': game.id, 'current_round': game.current_round,
    'teams': [(t.id, t.name) for t in teams],
    'rounds': [(r.round_number, r.status) for r in rounds],
    'per_team': {
        t.name: {
            'products': TeamProduct.objects.filter(team=t, status='active').count(),
            'platforms': TeamPlatform.objects.filter(team=t).count(),
            'markets': TeamMarketPresence.objects.filter(team=t, status='active').count(),
            'cash': str(t.cash_on_hand),
        } for t in teams
    },
}
print('---SEED-JSON---')
print(json.dumps(out, default=str))
