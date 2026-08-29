"""Focused checks on seed-varied fixture identity, run before the freeze.

Two questions, and the second is the one that matters. Does the same seed
reproduce exactly? And do different seeds actually draw different numbers, or
have I only relabelled the same fixture? The first Stage 3 plan failed the
second question without noticing, because nothing asked it.

A third question is asked and answered honestly rather than assumed: do
different streams change the resolved outcome in this fixture at all? If the
stochastic subsystems never fire here, differing identities will produce
identical metrics, and holdout across identities would be measuring nothing.
That result is reported either way rather than being allowed to look like
agreement.
"""
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import fixture as F
import search_body as S

SEEDS = ('identity-a', 'identity-b', 'identity-c')


def run():
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('identity-check', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import Game, Team

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    started = time.time()

    identities = {seed: F.identity_for(seed) for seed in SEEDS}
    report = {
        'seeds': list(SEEDS),
        'identities': identities,
        'identities_are_distinct': len(set(identities.values())) == len(SEEDS),
        'identity_is_stable': all(
            F.identity_for(seed) == identities[seed] for seed in SEEDS),
        'stream_probes': list(F.STREAM_PROBES),
    }

    # Do different identities draw different numbers?
    pairs = {}
    for i, first in enumerate(SEEDS):
        for second in SEEDS[i + 1:]:
            detail = F.streams_differ(identities[first], identities[second])
            pairs[f'{first} vs {second}'] = {
                'per_stream': detail,
                'all_differ': all(v['differs'] for v in detail.values()),
            }
    report['stream_differences'] = pairs
    report['every_pair_differs_on_every_stream'] = all(
        p['all_differ'] for p in pairs.values())

    # Does the same identity reproduce exactly, and do different identities
    # change what the round actually produces?
    metrics = {}
    for seed in SEEDS:
        F.apply(game, seed)
        first = S.score(S.evaluate(game, subject, None, lambda t: None),
                        subject.id)
        second = S.score(S.evaluate(game, subject, None, lambda t: None),
                         subject.id)
        metrics[seed] = {'first': first, 'repeatable': first == second}

    report['per_identity_baseline'] = metrics
    report['every_identity_is_repeatable'] = all(
        m['repeatable'] for m in metrics.values())
    signatures = {seed: (m['first']['index'], m['first']['cash_closing'],
                         m['first']['total_revenue'])
                  for seed, m in metrics.items()}
    report['outcome_signatures'] = {k: list(v) for k, v in signatures.items()}
    report['identities_change_the_outcome'] = (
        len(set(signatures.values())) == len(SEEDS))
    report['distinct_outcomes'] = len(set(signatures.values()))
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
