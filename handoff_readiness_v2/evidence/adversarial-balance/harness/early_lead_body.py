"""Early-lead lock-in: can a lead erode once the leader stops outperforming?

The tournament showed no candidate beating competent play. That says nothing
about this mechanism: no candidate ever established a legal lead and then
stopped working to see whether the lead held itself up. This runs that
sequence.

Rounds 1-2 the subject front-loads the strongest legal investment it can make.
Rounds 3-6 it returns to the documented baseline while every opponent plays
that baseline throughout. If the margin narrows once the subject stops
outperforming, the lead is earned each round. If it holds, the question is
whether persistent purchased state explains it -- cumulative adopters, platform
levels, plant, market presence, all things the subject paid for and still owns
-- or whether the ranking itself has become mechanically unreachable.

Run forward, not rolled back: the whole point is what accumulates.
"""
import time

from decimal import Decimal as D
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import fixture as F
import fixture_contract as FC
import search_body as S
import targeted as T

SEED = 'crv2-06-early-lead'
FRONT_LOAD_ROUNDS = 2
TOTAL_ROUNDS = 6


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('early-lead', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    from core.models import Scenario
    wanted = ('sourcing', 'trade_finance', 'compliance', 'logistics')
    chosen, _ = FC.scenario_supporting(wanted)
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    from core.engine.advance_round import _run_phase_1, advance_to_next_round
    from core.models import (DecisionSubmission, Game, Round, Team)
    from core.models.results import RoundResultAdoption
    from core.models.results_financials import (RoundResultFinancials,
                                                RoundResultPerformanceIndex)

    game = Game.objects.order_by('-id').first()
    F.apply(game, SEED)
    game.refresh_from_db()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]

    # The strongest legal front-load available: spend hard on the levers the
    # adopted rules reward, all inside the legal space and all costed.
    FRONT_LOADED = dict(T.NEUTRAL)
    FRONT_LOADED.update({
        'promotion_multiplier': 3.0,
        'volume_multiplier': 2.0,
        'marketing_budget': 8_000_000.0,
        'strategy_budget': 3_000_000.0,
        'research_budget': 2_000_000.0,
        'distribution_investment': 1_500_000.0,
        'sales_team_count': 30,
        'environmental_investment': 1_000_000.0,
        'social_investment': 1_000_000.0,
    })

    started = time.time()
    series = []

    for step in range(TOTAL_ROUNDS):
        game.refresh_from_db()
        rnd = Round.objects.get(game=game, round_number=game.current_round)
        front_loading = step < FRONT_LOAD_ROUNDS
        for team in teams:
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=rnd, defaults={'status': 'draft'})
            genome = (FRONT_LOADED
                      if (team.id == subject.id and front_loading) else None)
            S.write_candidate(submission, team, genome)
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])

        _run_phase_1(game.id)

        indices = {}
        for team in teams:
            idx = RoundResultPerformanceIndex.objects.filter(
                team=team, round_number=rnd.round_number).order_by('-id').first()
            indices[team.id] = float(idx.index_value) if idx else 0.0
        fin = RoundResultFinancials.objects.filter(
            team=subject, round_number=rnd.round_number).order_by('-id').first()
        adopters = sum(
            (D(str(a.cumulative_adopters)) for a in
             RoundResultAdoption.objects.filter(
                 team=subject, round_number=rnd.round_number)), D('0'))

        mine = indices[subject.id]
        rivals = [v for k, v in indices.items() if k != subject.id]
        best_rival = max(rivals) if rivals else 0.0
        row = {
            'round': rnd.round_number,
            'phase': 'front-loaded' if front_loading else 'baseline',
            'index': round(mine, 4),
            'best_rival_index': round(best_rival, 4),
            'margin': round(mine - best_rival, 4),
            'rank': 1 + sum(1 for r in rivals if r > mine),
            'field': len(teams),
            'cash_closing': str(fin.cash_closing) if fin else None,
            'cumulative_adopters': str(adopters),
        }
        series.append(row)
        if verbose:
            print(f"  round {row['round']} {row['phase']:<13} "
                  f"index {row['index']:>7.3f}  margin {row['margin']:>8.3f}  "
                  f"rank {row['rank']}/{row['field']}  "
                  f"adopters {row['cumulative_adopters']}", flush=True)

        if step < TOTAL_ROUNDS - 1:
            advance_to_next_round(game.id)

    front = [r for r in series if r['phase'] == 'front-loaded']
    after = [r for r in series if r['phase'] == 'baseline']
    peak_margin = max(r['margin'] for r in front) if front else 0.0
    final_margin = after[-1]['margin'] if after else 0.0

    report = {
        'seed': SEED,
        'scenario': chosen.name,
        'identity': F.identity_for(SEED),
        'subject_team': subject.name,
        'front_load_rounds': FRONT_LOAD_ROUNDS,
        'total_rounds': TOTAL_ROUNDS,
        'front_loaded_genome': FRONT_LOADED,
        'series': series,
        'peak_margin_while_front_loading': peak_margin,
        'final_margin_after_reverting': final_margin,
        'lead_was_established': peak_margin > 0,
        # The question the rework asks: once the subject stops outperforming,
        # can the margin move against it at all?
        'margin_erodes_after_revert': bool(
            after and final_margin < max(r['margin'] for r in after[:1])),
        'margin_by_round_after_revert': [r['margin'] for r in after],
        'rank_ever_lost': any(r['rank'] > 1 for r in after),
        'adopters_are_persistent_state': [
            r['cumulative_adopters'] for r in series],
        'elapsed_seconds': round(time.time() - started, 1),
    }
    margins_after = report['margin_by_round_after_revert']
    report['margin_strictly_non_decreasing_after_revert'] = all(
        b >= a for a, b in zip(margins_after, margins_after[1:]))
    return report
