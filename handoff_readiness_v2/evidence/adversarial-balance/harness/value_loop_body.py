"""Does a negative investment pay the team? Asked of the engine, not the source.

Phase 1 established that twelve investment and headcount dimensions accept a
negative value at the serializer. Reading `costs.py` says those values are added
to `strategy_expense`, so a negative one should reduce expenses — which is
income. That is a reading, and a reading is not a finding.

This gives two otherwise identical teams in the same game the same decisions
except for one field, resolves the round through the real Phase-1 engine, and
compares what the books say. Same game, same round, same RNG stream: the
difference is the field.
"""
import json
from decimal import Decimal as D

from django.utils import timezone

from core.models import (DecisionSubmission, Game, Round, Team)
from core.models.decisions import DecisionBudgetAllocation, DecisionESG

game = Game.objects.order_by('-id').first()
rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
teams = list(Team.objects.filter(game=game).order_by('id'))
control, probe = teams[0], teams[1]

PROBE_AMOUNT = D('-5000000.00')

results = {'game': game.id, 'round': rnd.round_number,
           'control_team': control.id, 'probe_team': probe.id,
           'probe_amount': str(PROBE_AMOUNT)}


def submission_for(team):
    sub, _ = DecisionSubmission.objects.get_or_create(
        team=team, round=rnd, defaults={'status': 'draft'})
    DecisionBudgetAllocation.objects.filter(submission=sub).delete()
    DecisionBudgetAllocation.objects.create(
        submission=sub, rd_budget=D('1000000'), marketing_budget=D('1000000'),
        strategy_budget=D('1000000'), research_budget=D('0'))
    return sub


# Every team must be locked or the engine refuses to resolve, so all of them
# submit the identical baseline. Only the probe team's ESG figure differs, and
# it differs only in sign.
subs = {team.id: submission_for(team) for team in teams}
control_sub, probe_sub = subs[control.id], subs[probe.id]

DecisionESG.objects.filter(submission__in=list(subs.values())).delete()
for team in teams:
    amount = PROBE_AMOUNT if team.id == probe.id else D('0')
    DecisionESG.objects.create(submission=subs[team.id],
                               environmental_investment=amount,
                               social_investment=D('0'))

for sub in subs.values():
    sub.status = 'locked'
    sub.locked_at = timezone.now()
    sub.save(update_fields=['status', 'locked_at'])

results['teams_locked'] = len(subs)
results['esg_rows'] = {
    str(team.id): str(DecisionESG.objects.get(
        submission=subs[team.id]).environmental_investment)
    for team in teams
}

cash_before = {t.id: D(str(t.cash_on_hand)) for t in teams}

from core.engine.advance_round import _run_phase_1
_run_phase_1(game.id)

for team in teams:
    team.refresh_from_db()

from core.models import RoundResultFinancials, RoundResultPerformanceIndex


def financials(team):
    row = (RoundResultFinancials.objects
           .filter(team=team, round_number=rnd.round_number).order_by('-id').first())
    if row is None:
        return None
    keep = ('total_revenue', 'gross_profit', 'strategy_expense',
            'operating_income', 'net_income', 'cash_opening', 'cash_closing')
    return {f: str(getattr(row, f)) for f in keep if hasattr(row, f)}


def index_for(team):
    row = (RoundResultPerformanceIndex.objects
           .filter(team=team, round_number=rnd.round_number).order_by('-id').first())
    return None if row is None else {
        'index_value': str(row.index_value),
        'satisfaction_score': str(row.satisfaction_score),
    }


results['financials'] = {
    'control': financials(control),
    'probe': financials(probe),
}
results['performance_index'] = {
    'control': index_for(control),
    'probe': index_for(probe),
}
results['cash_after'] = {
    'control': str(control.cash_on_hand),
    'probe': str(probe.cash_on_hand),
}
results['cash_before'] = {
    'control': str(cash_before[control.id]),
    'probe': str(cash_before[probe.id]),
}
results['cash_delta'] = {
    'control': str(D(str(control.cash_on_hand)) - cash_before[control.id]),
    'probe': str(D(str(probe.cash_on_hand)) - cash_before[probe.id]),
}

control_delta = D(results['cash_delta']['control'])
probe_delta = D(results['cash_delta']['probe'])
advantage = probe_delta - control_delta
results['probe_advantage_cash'] = str(advantage)

# The expense line the negative figure is added to. If the engine treated the
# value as a cost of zero it would match the control; if it credited it, the
# probe team's strategy expense is lower by the amount.
def strategy_expense(side):
    row = results['financials'][side]
    return D(row['strategy_expense']) if row and 'strategy_expense' in row else None

ctrl_se, probe_se = strategy_expense('control'), strategy_expense('probe')
results['strategy_expense_delta'] = (
    str(probe_se - ctrl_se) if (ctrl_se is not None and probe_se is not None) else None)

results['value_loop_confirmed'] = bool(
    (results['strategy_expense_delta'] is not None
     and D(results['strategy_expense_delta']) < 0)
    or advantage > 0)
results['credit_matches_probe_amount'] = bool(
    results['strategy_expense_delta'] is not None
    and abs(D(results['strategy_expense_delta']) - PROBE_AMOUNT) < D('1'))

print(json.dumps(results, indent=2, default=str))
print('---VALUE-LOOP-JSON---')
print(json.dumps(results, default=str))
