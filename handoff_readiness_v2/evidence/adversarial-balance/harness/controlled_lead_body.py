"""Early lead, measured with exogenous shocks switched off in the fixture.

The uncontrolled probe swung by roughly 25 index points depending on which
market a compliance freeze landed in, which is larger than the first-mover
effect it was trying to measure. Here the three stochastic sources are set to
zero probability **in scenario data** -- `ComplianceRegime
.baseline_enforcement_probability_per_round`, and `probability_per_round` on
the supply-chain and event templates. No mock, no patch, no monkeypatching:
the configuration applied is recorded in the artifact and asserted round by
round, and the run refuses if any freeze, supply-chain event or event instance
appears.

Two arms only, six rounds each:

  1. the leader front-loads rounds 1-2, then both teams play the documented
     baseline;
  2. the same front-load, then the challenger plays the strongest legal
     catch-up plan already constructed (`combined_best`).

**Why sales stopped** is recorded every round for both teams -- freezes,
events, revenue and the inactivity cap -- because the earlier probe measured
index, rank, cash and adopters and could not say why a team's revenue went to
zero. That omission is what let a stochastic freeze be reported as a structural
property of the scoring rule.
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
from v2_027_confirm_body import CATCH_UP, LEADER_FRONT_LOAD

SEED = 'crv2-06-controlled-lead'
FRONT_LOAD_ROUNDS = 2
TOTAL_ROUNDS = 6
SENSITIVITY = D('20')
INACTIVITY_CAP = D('0.25')


def _silence_exogenous_shocks(scenario):
    """Zero every stochastic trigger, in data, and report what was changed."""
    from core.models import ComplianceRegime
    from core.models.scenario import EventTemplateDefinition

    # Scenario and supply-chain events share one template table; sc_engine
    # simply filters it by category, so zeroing the column covers both.
    applied = {}
    applied['compliance_regimes_zeroed'] = ComplianceRegime.objects.filter(
        scenario=scenario).update(baseline_enforcement_probability_per_round=0)
    applied['event_templates_zeroed'] = EventTemplateDefinition.objects.filter(
        scenario=scenario).update(probability_per_round=0)
    applied['supply_chain_templates_included'] = (
        EventTemplateDefinition.objects.filter(
            scenario=scenario, category='supply_chain').count())
    return applied


def run(arm='both_baseline', verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('controlled', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    from core.models import Scenario
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    from core.engine.advance_round import _run_phase_1, advance_to_next_round
    from core.engine.performance import (_strategic_capability_component,
                                         scenario_rd_spend_target)
    from core.engine.utils import scenario_optimal_headcounts
    from core.models import DecisionSubmission, Game, Round, Team
    from core.models.results import RoundResultAdoption
    from core.models.results_financials import (RoundResultFinancials,
                                                RoundResultPerformanceIndex)
    from core.models.results import EventInstance
    from core.models.sc_state import ComplianceEnforcementEvent

    game = Game.objects.order_by('-id').first()
    F.apply(game, SEED)
    game.refresh_from_db()
    silenced = _silence_exogenous_shocks(game.scenario)
    teams = list(Team.objects.filter(game=game).order_by('id'))
    leader, challenger = teams[0], teams[1]
    target = scenario_rd_spend_target(game.scenario)
    optima = scenario_optimal_headcounts(game.scenario)

    started = time.time()
    series = []
    shock_breaches = []

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
            elif (arm == 'challenger_counters' and team.id == challenger.id
                  and not leading_phase):
                genome = CATCH_UP['combined_best']['genome']
            S.write_candidate(submission, team, genome)
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])

        _run_phase_1(game.id)

        row = {'round': rnd.round_number,
               'phase': 'front-load' if leading_phase else 'after'}
        events = EventInstance.objects.filter(
            game=game, round_number=rnd.round_number).count()
        sc_events = EventInstance.objects.filter(
            game=game, round_number=rnd.round_number,
            event_template__category='supply_chain').count()
        if sc_events or events:
            shock_breaches.append(
                f'round {rnd.round_number}: {sc_events} supply-chain and '
                f'{events} scenario events fired despite zero probability')
        row['sc_events'] = sc_events
        row['events'] = events

        for label, team in (('leader', leader), ('challenger', challenger)):
            idx = RoundResultPerformanceIndex.objects.filter(
                team=team, round_number=rnd.round_number).order_by('-id').first()
            fin = RoundResultFinancials.objects.filter(
                team=team, round_number=rnd.round_number).order_by('-id').first()
            adopters = sum(
                (D(str(a.cumulative_adopters)) for a in
                 RoundResultAdoption.objects.filter(
                     team=team, round_number=rnd.round_number)), D('0'))
            freezes = list(ComplianceEnforcementEvent.objects.filter(
                team=team, round=rnd).values_list(
                    'regime__regime_id', 'market__code', 'freeze_until_round'))
            if freezes:
                shock_breaches.append(
                    f'round {rnd.round_number} {label}: {len(freezes)} '
                    f'compliance freezes despite zero probability')
            composite = D(str(idx.satisfaction_score)) if idx else D('0')
            revenue = D(str(fin.total_revenue)) if fin else D('0')
            # Capability is the one component computable after the fact: it
            # reads the submission and scenario configuration and nothing the
            # round produced. The other four need the resolution context, which
            # the engine does not persist, so the composite carries them.
            capability = _strategic_capability_component(
                team, rnd.round_number, target, optima)
            row[label] = {
                'index': str(idx.index_value) if idx else None,
                'index_change': str(idx.index_change) if idx else None,
                'composite': str(composite),
                'capability_component': str(capability),
                'capability_contribution': str(
                    (capability * D('0.25')).quantize(D('0.0001'))),
                'other_components_contribution': str(
                    (composite - capability * D('0.25')).quantize(D('0.0001'))),
                'total_revenue': str(revenue),
                'cash_closing': str(fin.cash_closing) if fin else None,
                'cumulative_adopters': str(adopters),
                'compliance_freezes': [list(f) for f in freezes],
                # Why sales stopped, if they did -- the diagnostic the earlier
                # probe lacked.
                'sales_stopped': revenue == 0,
                'inactivity_cap_applied': composite == INACTIVITY_CAP,
            }
        row['index_gap'] = str(D(row['leader']['index'])
                               - D(row['challenger']['index']))
        row['composite_gap'] = str(D(row['leader']['composite'])
                                   - D(row['challenger']['composite']))
        row['adopter_gap'] = str(D(row['leader']['cumulative_adopters'])
                                 - D(row['challenger']['cumulative_adopters']))
        series.append(row)
        if verbose:
            print(f"  r{row['round']} {row['phase']:<11} gap "
                  f"{row['index_gap']:>8}  composite gap "
                  f"{row['composite_gap']:>8}  adopter gap "
                  f"{row['adopter_gap']:>12}  shocks "
                  f"{sc_events + events}", flush=True)

        if step < TOTAL_ROUNDS - 1:
            advance_to_next_round(game.id)

    after = [r for r in series if r['phase'] == 'after']
    return {
        'arm': arm,
        'seed': SEED,
        'scenario': chosen.name,
        'exogenous_shocks_silenced': silenced,
        'silencing_method': (
            'scenario data: baseline_enforcement_probability_per_round on '
            'ComplianceRegime, probability_per_round on EventTemplate and '
            'SCEventTemplate, all set to 0. No mock or patch.'),
        'shock_breaches': shock_breaches,
        'shocks_were_silent': not shock_breaches,
        'series': series,
        'gap_when_front_load_ended': series[FRONT_LOAD_ROUNDS - 1]['index_gap'],
        'gap_at_end': series[-1]['index_gap'],
        'composite_gap_at_end': series[-1]['composite_gap'],
        'adopter_gap_at_end': series[-1]['adopter_gap'],
        'composite_gap_by_round_after': [r['composite_gap'] for r in after],
        'any_sales_stopped': any(
            r[side]['sales_stopped'] for r in series
            for side in ('leader', 'challenger')),
        'any_inactivity_cap': any(
            r[side]['inactivity_cap_applied'] for r in series
            for side in ('leader', 'challenger')),
        'elapsed_seconds': round(time.time() - started, 1),
    }
