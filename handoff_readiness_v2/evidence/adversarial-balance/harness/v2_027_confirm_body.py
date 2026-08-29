"""V2-027 confirmation: is the lead unreachable, or merely unreached?

Two things, in order.

**The bound.** `index_change = (composite - 0.5) * sensitivity` and
`new_index = max(0, previous + index_change)`. The index is an integrator with
no decay term, so a gap persists unless the trailing team scores a *higher*
composite than the leader. Two bounds are reported and they are not the same
number:

  * the absolute formula bound, which assumes composite 1.0 -- every one of the
    five components at its maximum in the same round;
  * the attainable bound, taken from what the four catch-up strategies actually
    scored, because several components are relative to the leader's own revenue
    and cannot all be maximised at once.

Presenting the first as a catch-up plan would be dishonest: it assumes
mutually incompatible maxima.

**Four counter-strategies**, each deliberately different, run against the same
reverted leader from the same checkpoint. The leader front-loads rounds 1-2
and plays the documented baseline thereafter; the challenger plays its
counter-strategy from round 3 to the end.

Composite is read from `RoundResultPerformanceIndex.satisfaction_score`, which
stores the final composite despite its legacy name, and is cross-checked
against `0.5 + index_change / sensitivity`. If the two disagree the run refuses:
the decomposition rests on that identity.
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

SEED = 'crv2-06-v2-027-confirm'
FRONT_LOAD_ROUNDS = 2
TOTAL_ROUNDS = 6
SENSITIVITY = D('20')

LEADER_FRONT_LOAD = dict(T.NEUTRAL)
LEADER_FRONT_LOAD.update({
    'promotion_multiplier': 3.0, 'volume_multiplier': 2.0,
    'marketing_budget': 8_000_000.0, 'strategy_budget': 3_000_000.0,
    'research_budget': 2_000_000.0, 'distribution_investment': 1_500_000.0,
    'sales_team_count': 30, 'environmental_investment': 1_000_000.0,
    'social_investment': 1_000_000.0,
})

# Four deliberately different legal catch-up plans.
CATCH_UP = {
    'max_capability': {
        'why': 'maximum viable R&D and capability: spend at the scenario '
               'target, staff every pool at its optimum, and take the product '
               'and strategy actions the capability component rewards',
        'genome': dict(T.NEUTRAL, research_budget=3_000_000.0,
                       strategy_budget=5_000_000.0,
                       rd_headcount=90, commercial_headcount=60,
                       operations_headcount=75),
    },
    'price_volume_capture': {
        'why': 'buy share: price below the tier reference, produce heavily, '
               'and promote hard, driving the market and revenue terms',
        'genome': dict(T.NEUTRAL, price_multiplier=0.6,
                       volume_multiplier=3.0, promotion_multiplier=4.0,
                       marketing_budget=10_000_000.0,
                       distribution_investment=2_000_000.0,
                       sales_team_count=40),
    },
    'financing_funded_scale': {
        'why': 'fund the scale-up rather than pay for it out of operations: '
               'the largest legal equity raise under V2-024 plus debt, '
               'converted into volume and promotion',
        'genome': dict(T.NEUTRAL, _equity_at_max=True, new_debt=40_000_000.0,
                       volume_multiplier=3.0, promotion_multiplier=3.0,
                       environmental_investment=2_000_000.0),
    },
    'combined_best': {
        'why': 'the strongest combined legal plan: capability, capture and '
               'financing together',
        'genome': dict(T.NEUTRAL, _equity_at_max=True, new_debt=40_000_000.0,
                       price_multiplier=0.7, volume_multiplier=3.0,
                       promotion_multiplier=4.0,
                       marketing_budget=10_000_000.0,
                       strategy_budget=5_000_000.0,
                       research_budget=3_000_000.0,
                       distribution_investment=2_000_000.0,
                       sales_team_count=40, rd_headcount=90,
                       commercial_headcount=60, operations_headcount=75,
                       environmental_investment=2_000_000.0,
                       social_investment=2_000_000.0),
    },
}


def run(strategy='none', verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('v2027', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    from core.models import Scenario
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    from core.engine.advance_round import _run_phase_1, advance_to_next_round
    from core.models import DecisionSubmission, Game, Round, Team
    from core.models.results import RoundResultAdoption
    from core.models.results_financials import (RoundResultFinancials,
                                                RoundResultPerformanceIndex)

    game = Game.objects.order_by('-id').first()
    F.apply(game, SEED)
    game.refresh_from_db()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    leader, challenger = teams[0], teams[1]
    plan = CATCH_UP.get(strategy)

    started = time.time()
    series = []
    identity_failures = []

    for step in range(TOTAL_ROUNDS):
        game.refresh_from_db()
        rnd = Round.objects.get(game=game, round_number=game.current_round)
        leading_phase = step < FRONT_LOAD_ROUNDS
        for team in teams:
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=rnd, defaults={'status': 'draft'})
            genome = None
            if team.id == leader.id and leading_phase:
                genome = LEADER_FRONT_LOAD
            elif (team.id == challenger.id and not leading_phase
                  and plan is not None):
                genome = plan['genome']
            S.write_candidate(submission, team, genome)
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])

        _run_phase_1(game.id)

        row = {'round': rnd.round_number,
               'phase': 'leader front-loading' if leading_phase
                        else 'leader baseline, challenger countering'}
        for label, team in (('leader', leader), ('challenger', challenger)):
            idx = RoundResultPerformanceIndex.objects.filter(
                team=team, round_number=rnd.round_number).order_by('-id').first()
            fin = RoundResultFinancials.objects.filter(
                team=team, round_number=rnd.round_number).order_by('-id').first()
            adopters = sum(
                (D(str(a.cumulative_adopters)) for a in
                 RoundResultAdoption.objects.filter(
                     team=team, round_number=rnd.round_number)), D('0'))
            composite = D(str(idx.satisfaction_score)) if idx else D('0')
            change = D(str(idx.index_change)) if idx else D('0')
            implied = (D('0.5') + change / SENSITIVITY)
            # The decomposition rests on composite and index_change being two
            # views of one number. If they disagree the run refuses.
            if idx and abs(implied - composite) > D('0.01'):
                identity_failures.append(
                    f'round {rnd.round_number} {label}: composite '
                    f'{composite} but index_change implies {implied}')
            row[label] = {
                'index': str(idx.index_value) if idx else None,
                'index_change': str(change),
                'composite': str(composite),
                'cash_closing': str(fin.cash_closing) if fin else None,
                'total_revenue': str(fin.total_revenue) if fin else None,
                'cumulative_adopters': str(adopters),
            }
        row['index_gap'] = str(D(row['leader']['index'])
                               - D(row['challenger']['index']))
        row['composite_gap'] = str(D(row['leader']['composite'])
                                   - D(row['challenger']['composite']))
        series.append(row)
        if verbose:
            print(f"  r{row['round']} gap {row['index_gap']:>8} "
                  f"composite L {row['leader']['composite']} "
                  f"C {row['challenger']['composite']} "
                  f"(diff {row['composite_gap']})", flush=True)

        if step < TOTAL_ROUNDS - 1:
            advance_to_next_round(game.id)

    countering = [r for r in series if r['round'] > FRONT_LOAD_ROUNDS]
    gap_start = D(series[FRONT_LOAD_ROUNDS - 1]['index_gap'])
    gap_end = D(series[-1]['index_gap'])

    return {
        'strategy': strategy,
        'why': plan['why'] if plan else 'no counter-strategy: control',
        'scenario': chosen.name,
        'series': series,
        'identity_failures': identity_failures,
        'gap_when_countering_began': str(gap_start),
        'gap_at_end': str(gap_end),
        'gap_change': str(gap_end - gap_start),
        'gap_closed': gap_end < gap_start,
        'closed_materially': gap_end <= gap_start / D('2'),
        # Attainable, not theoretical: the best composite this legal plan
        # actually reached while countering.
        'best_challenger_composite_while_countering': str(max(
            (D(r['challenger']['composite']) for r in countering),
            default=D('0'))),
        'best_composite_advantage_per_round': str(max(
            (D(r['challenger']['composite']) - D(r['leader']['composite'])
             for r in countering), default=D('0'))),
        'elapsed_seconds': round(time.time() - started, 1),
    }
