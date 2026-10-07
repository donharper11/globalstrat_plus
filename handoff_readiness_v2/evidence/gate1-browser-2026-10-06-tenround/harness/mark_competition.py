"""Mark the walkthrough game as a competition heat: mark_competition.py <game_id>

The console has no control for this (nothing in the frontend writes
`SimulationInstance.settings['is_competition']`), so it is set here the way
an operator would have to: directly on the row. Recorded as such in the
walkthrough; the delete-refusal test depends on it.
"""
import json
import os
import pathlib
import sys

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
from core.models.course import SimulationInstance                 # noqa: E402
from core.services.cohort_caps import is_competition_game         # noqa: E402
from core.models import Game                                      # noqa: E402

gid = int(sys.argv[1])
inst = SimulationInstance.objects.filter(game_id=gid).first()
settings = dict(inst.settings or {})
settings['is_competition'] = True
inst.settings = settings
inst.save(update_fields=['settings'])
print(json.dumps({'instance_id': inst.instance_id, 'settings': inst.settings,
                  'is_competition_game': is_competition_game(Game.objects.get(pk=gid))}))
