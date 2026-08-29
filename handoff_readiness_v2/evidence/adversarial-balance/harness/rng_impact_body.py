"""Does the repaired RNG change what the Stage 2 screen measured?

The screen was recorded at `e3654ec`, before V2-010 and V2-011. Source changed,
which is not by itself a reason to spend eleven minutes again: what matters is
whether *this fixture's* stochastic outputs and probe deltas moved.

Resolves the same baseline and a few representative probes under the repaired
RNG and compares them with the recorded screen. If they match, the screen still
describes the system it claims to; if they do not, it is stale and must be rerun.
"""
import json

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF

# A deliberately mixed sample: a cost dimension, a marketing dimension, a
# categorical, and one on each side of the screen's escalate/flat line.
SAMPLE = [
    ('esg', 'environmental_investment', 'funded_maximum'),
    ('talent', 'rd_headcount', 'funded_maximum'),
    ('marketing', 'promotion_budget', 'funded_maximum'),
    ('marketing', 'channel_digital_pct', 'funded_maximum'),
    ('budget', 'marketing_budget', 'legal_minimum'),
    ('financing', 'new_debt', 'funded_maximum'),
]

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('rng-gate', 'a@e.com', 'x')
call_command('load_all_scenarios', verbosity=0)
call_command('setup_test_game', verbosity=0)

from core.models import DecisionSubmission, Game, Round, Team
import screening_body as S

game = Game.objects.order_by('-id').first()
rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
teams = list(Team.objects.filter(game=game).order_by('id'))
subject = teams[0]

recorded = json.loads(open(SCREEN_PATH).read())
recorded_by_key = {
    (r['decision_type'], r['field'], r['label']): r
    for r in recorded['results'] if r.get('applied')
}

baseline = CF.evaluate(game, rnd, subject,
                       lambda: S.prepare(game, rnd, teams))
out = {
    'recorded_screen_revision': recorded.get('code_revision'),
    'recorded_baseline': recorded.get('baseline_metrics'),
    'repaired_baseline': baseline,
    'baseline_delta': CF.delta(recorded.get('baseline_metrics') or {}, baseline),
    'probes': {},
}
out['baseline_unchanged'] = CF.is_zero(out['baseline_delta'])

for decision_type, field, label in SAMPLE:
    key = (decision_type, field, label)
    was = recorded_by_key.get(key)
    if was is None:
        out['probes'][f'{decision_type}.{field}:{label}'] = {
            'comparable': False, 'why': 'not in the recorded screen'}
        continue
    probe = dict(was, _team_id=subject.id)
    metrics = CF.evaluate(
        game, rnd, subject,
        lambda p=probe: S.prepare(game, rnd, teams, p))
    now_delta = CF.delta(baseline, metrics)
    drift = CF.delta(was.get('delta') or {}, now_delta)
    out['probes'][f'{decision_type}.{field}:{label}'] = {
        'comparable': True,
        'recorded_delta': was.get('delta'),
        'repaired_delta': now_delta,
        'drift': drift,
        'unchanged': CF.is_zero(drift),
    }

comparable = [p for p in out['probes'].values() if p.get('comparable')]
out['probes_compared'] = len(comparable)
out['probes_unchanged'] = sum(1 for p in comparable if p['unchanged'])
out['screen_remains_applicable'] = bool(
    out['baseline_unchanged'] and comparable
    and all(p['unchanged'] for p in comparable))

print('---RNG-GATE-JSON---')
print(json.dumps(out, default=str))
