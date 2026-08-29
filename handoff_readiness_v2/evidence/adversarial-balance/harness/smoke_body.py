"""Stage 3 development smoke: one opponent, one seed, 20 candidates.

Deliberately creates no evidence. The handoff's verification budget puts the
smoke in development, where its job is to prove the search harness resolves
multi-round candidates, rolls back cleanly, keeps every candidate inside the
legal decision space and produces a usable spread of fitness -- not to
characterise the game. Nothing here is written under `evidence/` and nothing
enters SHA256SUMS.
"""
import random
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import search_body as S

SEED = 'crv2-06-stage3-smoke-1'
CANDIDATES = 20

def run():
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('stage3-smoke', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import Game, Round, Team  # noqa: E402

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    rng = random.Random(SEED)

    report = {
        'seed': SEED,
        'candidates_requested': CANDIDATES,
        'rounds_per_candidate': S.ROUNDS_PER_CANDIDATE,
        'opponent_population': 'competent baseline',
        'subject_team': subject.name,
        'field_size': len(teams),
        'genes': [g[0] for g in S.GENES],
        'evidence': 'none -- development smoke',
    }

    started = time.time()

    # The baseline candidate is not a candidate: it is what the population plays,
    # evaluated once so every candidate has something to be better or worse than.
    baseline_result = S.evaluate(game, subject, None, lambda team: None)
    report['baseline'] = S.score(baseline_result, subject.id)

    repeat_result = S.evaluate(game, subject, None, lambda team: None)
    report['baseline_is_repeatable'] = (
        S.score(repeat_result, subject.id) == report['baseline'])
    base = report['baseline']

    rows = []
    for n in range(CANDIDATES):
        genome = S.random_candidate(rng)
        result = S.evaluate(game, subject, genome, lambda team: None)
        fitness = S.score(result, subject.id, base)
        rows.append({'n': n, 'genome': genome, 'fitness': fitness})
        print(f"  candidate {n:>2}  index {fitness['index']:>8.3f}  "
              f"advantage {fitness['advantage']:>8.3f}  "
              f"field margin {fitness['field_margin']:>8.3f}  "
              f"rank {fitness['rank']}/{fitness['field']}", flush=True)

    rows.sort(key=lambda r: r['fitness']['advantage'], reverse=True)
    report['candidates'] = rows
    report['elapsed_seconds'] = round(time.time() - started, 1)
    report['evaluations'] = CANDIDATES + 2

    indices = [r['fitness']['advantage'] for r in rows]
    report['fitness_spread'] = {
        'best': indices[0], 'worst': indices[-1],
        'distinct_values': len(set(indices)),
        'all_identical': len(set(indices)) == 1,
    }
    report['beat_baseline'] = sum(
        1 for r in rows if r['fitness']['advantage'] > 0)
    return report
