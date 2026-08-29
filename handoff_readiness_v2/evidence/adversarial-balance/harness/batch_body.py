"""One 50-candidate discovery batch across three opponent populations.

The pre-freeze step of the Stage 3 protocol. Fitness is advantage over
competent baseline play *within the same population*: opponents differ between
populations, so a candidate's index is not comparable across them and only the
gap to what the same team scores playing the baseline against those same
opponents is.

The three populations are the ones the handoff names:

  baseline   every opponent plays the documented competent baseline;
  diverse    every opponent plays a different random legal strategy, drawn
             from a fixed seed so the population is reproducible;
  incumbent  every opponent plays the strongest candidate found in this batch
             against the baseline population -- the check that a strategy which
             beats competent play does not simply lose to itself.
"""
import random
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import search_body as S

SEED = 'crv2-06-stage3-discovery-1'
CANDIDATES = 50


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('stage3-batch', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import Game, Team

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    opponents = [t for t in teams if t.id != subject.id]

    rng = random.Random(SEED)
    candidates = [S.random_candidate(rng) for _ in range(CANDIDATES)]

    # Fixed, reproducible: one distinct legal strategy per opponent.
    diverse_rng = random.Random(SEED + '-diverse')
    diverse = {t.id: S.random_candidate(diverse_rng) for t in opponents}

    started = time.time()
    report = {
        'seed': SEED,
        'batch_size': CANDIDATES,
        'rounds_per_candidate': S.ROUNDS_PER_CANDIDATE,
        'subject_team': subject.name,
        'field_size': len(teams),
        'genes': [g[0] for g in S.GENES],
        'diverse_population': {str(k): v for k, v in diverse.items()},
        'populations': {},
        'evaluations': 0,
    }

    def sweep(label, opponent_for):
        base_result = S.evaluate(game, subject, None, opponent_for)
        base = S.score(base_result, subject.id)
        repeat = S.score(S.evaluate(game, subject, None, opponent_for),
                         subject.id)
        rows = []
        for n, genome in enumerate(candidates):
            fitness = S.score(
                S.evaluate(game, subject, genome, opponent_for),
                subject.id, base)
            rows.append({'n': n, 'genome': genome, 'fitness': fitness})
            if verbose:
                print(f"  {label:>9} {n:>2}  advantage "
                      f"{fitness['advantage']:>8.3f}  index "
                      f"{fitness['index']:>7.3f}  rank {fitness['rank']}/"
                      f"{fitness['field']}", flush=True)
        rows.sort(key=lambda r: r['fitness']['advantage'], reverse=True)
        advantages = [r['fitness']['advantage'] for r in rows]
        report['evaluations'] += CANDIDATES + 2
        report['populations'][label] = {
            'baseline': base,
            'baseline_is_repeatable': repeat == base,
            'candidates': rows,
            'beat_baseline': sum(1 for a in advantages if a > 0),
            'best_advantage': advantages[0],
            'worst_advantage': advantages[-1],
            'distinct_advantages': len(set(advantages)),
            'all_identical': len(set(advantages)) == 1,
        }
        return rows

    baseline_rows = sweep('baseline', lambda team: None)

    incumbent = baseline_rows[0]['genome']
    report['incumbent'] = {'from': 'best against the baseline population',
                           'genome': incumbent,
                           'advantage': baseline_rows[0]['fitness']['advantage']}

    sweep('diverse', lambda team: diverse[team.id])
    sweep('incumbent', lambda team: incumbent)

    report['elapsed_seconds'] = round(time.time() - started, 1)

    # A candidate only counts as a real improvement if it beats competent play
    # in every population. Winning against one and losing against the others is
    # an artefact of that population, not a strategy.
    per_population = {
        label: {row['n']: row['fitness']['advantage']
                for row in data['candidates']}
        for label, data in report['populations'].items()}
    robust = [n for n in range(CANDIDATES)
              if all(per_population[label][n] > 0 for label in per_population)]
    report['robust_winners'] = robust
    report['robust_winner_detail'] = [
        {'n': n,
         'genome': candidates[n],
         'advantage_by_population': {label: per_population[label][n]
                                     for label in per_population}}
        for n in robust]
    return report
