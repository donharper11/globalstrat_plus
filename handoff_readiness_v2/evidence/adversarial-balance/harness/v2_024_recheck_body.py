"""Re-run only the V2-024 tournament candidates and their controls.

Not the tournament. The three candidates that demonstrated the exploit --
equity-raise, equity-and-dividend and the neutral baseline they were built
from -- plus skeleton-crew as an untouched control, against the same three
opponent populations on the discovery identity. If the rule works, the two
equity candidates can no longer be resolved at all: an unfunded raise is
refused before the first competitive write, which is a different and stronger
result than scoring badly.
"""
import random
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import fixture as F
import search_body as S
import targeted as T

DISCOVERY_SEED = 'crv2-06-tournament-discovery'
DIVERSE_SEED = 'crv2-06-tournament-diverse'
SUBJECTS = ('equity-raise', 'equity-and-dividend', 'skeleton-crew')


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('v2024-recheck', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.engine.advance_round import EquityExceedsFundingNeedError
    from core.models import Game, Team

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    opponents = [t for t in teams if t.id != subject.id]
    diverse_rng = random.Random(DIVERSE_SEED)
    diverse = {t.id: S.random_candidate(diverse_rng) for t in opponents}
    F.apply(game, DISCOVERY_SEED)

    genome_of = {c['name']: c['genome'] for c in T.CANDIDATES}
    populations = {
        'competent': lambda team: None,
        'diverse': lambda team: diverse[team.id],
        'incumbent': lambda team: genome_of['equity-raise'],
    }

    started = time.time()
    report = {'discovery_seed': DISCOVERY_SEED,
              'identity': F.identity_for(DISCOVERY_SEED),
              'subject_team': subject.name,
              'subjects': SUBJECTS, 'results': {}, 'evaluations': 0}

    for label, opponent_for in populations.items():
        # The incumbent population plays equity-raise, which the rule now
        # refuses, so that population cannot be resolved at all. Recorded
        # rather than skipped: it is the clearest evidence the rule binds.
        cell = {}
        try:
            base = S.score(S.evaluate(game, subject, None, opponent_for),
                           subject.id)
            report['evaluations'] += 1
            cell['baseline'] = base
            cell['baseline_resolvable'] = True
        except EquityExceedsFundingNeedError as exc:
            cell['baseline_resolvable'] = False
            cell['baseline_refusal'] = str(exc)[:400]
            report['results'][label] = cell
            if verbose:
                print(f'  {label:<10} baseline REFUSED: {str(exc)[:120]}',
                      flush=True)
            continue

        rows = {}
        for name in SUBJECTS:
            try:
                fitness = S.score(
                    S.evaluate(game, subject, genome_of[name], opponent_for),
                    subject.id, base)
                report['evaluations'] += 1
                rows[name] = {'resolved': True, 'fitness': fitness}
                if verbose:
                    print(f"  {label:<10} {name:<22} advantage "
                          f"{fitness['advantage']:>8.3f}", flush=True)
            except EquityExceedsFundingNeedError as exc:
                rows[name] = {'resolved': False, 'refusal': str(exc)[:400]}
                if verbose:
                    print(f'  {label:<10} {name:<22} REFUSED', flush=True)
        cell['candidates'] = rows
        report['results'][label] = cell

    report['equity_candidates_refused'] = all(
        not report['results'][label]['candidates'][name]['resolved']
        for label in report['results']
        if report['results'][label].get('candidates')
        for name in ('equity-raise', 'equity-and-dividend'))
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
