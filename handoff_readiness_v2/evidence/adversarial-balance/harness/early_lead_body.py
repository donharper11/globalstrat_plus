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


def run(mode='subject_only', verbose=True):
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
    challenger = teams[1] if len(teams) > 1 else None

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
        # In challenger mode one opponent front-loads *after* the subject has
        # stopped, which is the only way to answer whether a lead can be
        # closed by later opponent performance rather than merely whether it
        # decays on its own.
        challenger_active = (
            mode == 'challenger'
            and FRONT_LOAD_ROUNDS <= step < FRONT_LOAD_ROUNDS * 2)
        for team in teams:
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=rnd, defaults={'status': 'draft'})
            genome = None
            if team.id == subject.id and front_loading:
                genome = FRONT_LOADED
            elif challenger_active and team.id == challenger.id:
                genome = FRONT_LOADED
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
        challenger_index = (indices.get(challenger.id)
                            if challenger is not None else None)
        challenger_adopters = str(sum(
            (D(str(a.cumulative_adopters)) for a in
             RoundResultAdoption.objects.filter(
                 team=challenger, round_number=rnd.round_number)), D('0'))
        ) if challenger is not None else None
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
            'challenger_index': (round(challenger_index, 4)
                                 if challenger_index is not None else None),
            'challenger_adopters': challenger_adopters,
            'challenger_front_loading': challenger_active,
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
        'mode': mode,
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
        'challenger_team': challenger.name if challenger else None,
        'subject_minus_challenger_by_round': [
            (None if r['challenger_index'] is None
             else round(r['index'] - r['challenger_index'], 4))
            for r in series],
        'elapsed_seconds': round(time.time() - started, 1),
    }
    margins_after = report['margin_by_round_after_revert']
    report['margin_strictly_non_decreasing_after_revert'] = all(
        b >= a for a, b in zip(margins_after, margins_after[1:]))

    # Whether a challenger closes the gap is a question about the gap before
    # it invests versus after, not about the last two rounds. An earlier
    # version compared the final gap with the midpoint and announced the gap
    # had narrowed on a drift of 0.06, while it had in fact widened sevenfold.
    if mode == 'challenger' and challenger is not None:
        gaps = report['subject_minus_challenger_by_round']
        investing = [i for i, r in enumerate(series)
                     if r['challenger_front_loading']]
        if investing and all(g is not None for g in gaps):
            before = gaps[investing[0] - 1] if investing[0] > 0 else gaps[0]
            report['gap_before_challenger_invested'] = before
            report['gap_at_end'] = gaps[-1]
            report['gap_closed_at_all'] = gaps[-1] < before
            report['gap_widened_while_investing'] = (
                gaps[investing[-1]] > before)
            report['gap_change'] = round(gaps[-1] - before, 4)
            # Erosion rate over the rounds after the challenger stops, used to
            # say how long closing would take rather than merely that it is
            # slow.
            tail = gaps[investing[-1]:]
            drift = ((tail[-1] - tail[0]) / (len(tail) - 1)
                     if len(tail) > 1 else 0.0)
            report['gap_drift_per_round_after'] = round(drift, 4)
            report['rounds_to_close_at_observed_drift'] = (
                round(abs(gaps[-1] / drift), 1) if drift < 0 else None)
    return report
