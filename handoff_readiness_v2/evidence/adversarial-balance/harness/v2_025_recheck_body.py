"""Re-evaluate only what V2-025 touched, across the existing nine holdout cells.

skeleton-crew, the corrected actual-R&D candidates, and their matched baselines
against the competent, diverse and incumbent populations on the three holdout
fixture identities. Not the tournament: three candidates, nine cells.

The R&D candidates are the corrected ones. The tournament's R&D family varied
`rd_budget`, the declared figure V2-021 made inert, so it never tested R&D
intensity at all. These vary `DecisionRDInvestment.amount`, which is what
capability actually reads.

The incumbent population plays skeleton-crew rather than equity-raise: the
tournament's incumbent is now refused outright by the V2-024 funding rule, so
it cannot form a population. Recorded here because it changes what "incumbent"
means between the two runs.
"""
import random
import statistics
import time

from decimal import Decimal as D
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import fixture as F
import search_body as S
import targeted as T

DIVERSE_SEED = 'crv2-06-tournament-diverse'
HOLDOUT_SEEDS = ('crv2-06-holdout-1', 'crv2-06-holdout-2', 'crv2-06-holdout-3')
POPULATIONS = ('competent', 'diverse', 'incumbent')
RD_TARGET = 2_000_000.0


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('v2025-recheck', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import Game, Team
    from core.models.decisions import DecisionRDInvestment

    game = Game.objects.order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    opponents = [t for t in teams if t.id != subject.id]
    diverse_rng = random.Random(DIVERSE_SEED)
    diverse = {t.id: S.random_candidate(diverse_rng) for t in opponents}

    genome_of = {c['name']: c['genome'] for c in T.CANDIDATES}
    skeleton = genome_of['skeleton-crew']

    # Actual R&D spend, not the declared budget. Applied as a post-write hook
    # because it lives in DecisionRDInvestment rows rather than the genome.
    def rd_spend_genome(amount):
        genome = dict(T.NEUTRAL)
        genome['_rd_amount'] = amount
        return genome

    CANDIDATES = {
        'skeleton-crew': skeleton,
        'rd-actual-zero': rd_spend_genome(0.0),
        'rd-actual-target': rd_spend_genome(RD_TARGET),
    }

    original_write = S.write_candidate

    def write_with_rd(submission, team, genome):
        original_write(submission, team, genome)
        if genome and '_rd_amount' in genome:
            for row in DecisionRDInvestment.objects.filter(
                    submission=submission):
                row.amount = D(str(genome['_rd_amount']))
                row.save(update_fields=['amount'])
    S.write_candidate = write_with_rd

    populations = {
        'competent': lambda team: None,
        'diverse': lambda team: diverse[team.id],
        'incumbent': lambda team: skeleton,
    }

    started = time.time()
    report = {'holdout_seeds': list(HOLDOUT_SEEDS),
              'identities': {s: F.identity_for(s) for s in HOLDOUT_SEEDS},
              'incumbent_population': 'skeleton-crew',
              'incumbent_note': 'the tournament incumbent was equity-raise, '
                                'which the V2-024 funding rule now refuses, so '
                                'it cannot form a population',
              'subject_team': subject.name, 'cells': [], 'evaluations': 0}

    for seed in HOLDOUT_SEEDS:
        F.apply(game, seed)
        for label in POPULATIONS:
            opponent_for = populations[label]
            base = S.score(S.evaluate(game, subject, None, opponent_for),
                           subject.id)
            report['evaluations'] += 1
            for name, genome in CANDIDATES.items():
                fitness = S.score(
                    S.evaluate(game, subject, genome, opponent_for),
                    subject.id, base)
                report['evaluations'] += 1
                report['cells'].append({
                    'seed': seed, 'population': label, 'name': name,
                    'advantage': fitness['advantage'],
                    'index': fitness['index'],
                    'baseline_index': base['index']})
                if verbose:
                    print(f"  {seed[-1]} {label:<10} {name:<18} advantage "
                          f"{fitness['advantage']:>8.3f}", flush=True)

    summary = {}
    for name in CANDIDATES:
        values = [c['advantage'] for c in report['cells'] if c['name'] == name]
        summary[name] = {
            'distribution': sorted(values),
            'worst_case': min(values), 'median': statistics.median(values),
            'best_case': max(values), 'cells_won': sum(1 for v in values if v > 0),
            'cells_total': len(values),
            'wins_every_cell': all(v > 0 for v in values),
        }
    report['summary'] = summary
    report['skeleton_still_wins_every_cell'] = summary[
        'skeleton-crew']['wins_every_cell']
    report['zero_headcount_has_opponent_independent_advantage'] = (
        summary['skeleton-crew']['worst_case'] > 0)
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
