"""Which of the twelve negative-accepting fields actually pay the team?

V2-018 was established with one field. Twelve accept a negative value, and they
feed different parts of the engine — an ESG figure is added to an expense line,
a headcount is multiplied by a salary band, a plant capacity is a quantity. Some
may be credited, some ignored, some may do something else entirely. A P0 that
names one field when twelve are open is an incomplete P0.

One team per field, all identical apart from the single negative value, plus a
control that sets nothing. Same game, same round, same RNG stream.
"""
import json
from decimal import Decimal as D

from django.utils import timezone

from core.models import (DecisionSubmission, Game, Round, RoundResultFinancials,
                         Team)
from core.models.decisions import DecisionBudgetAllocation, DecisionESG

# A fresh game: the value-loop probe already resolved round 1 of the previous
# one, and a resolved round cannot be resolved again.
from django.core.management import call_command
call_command('setup_test_game', verbosity=0)

game = Game.objects.order_by('-id').first()
rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
profile = Team.objects.filter(game=game).first().firm_starter_profile

NEGATIVE = D('-5000000.00')

# (label, decision model path, field, extra required fields)
CASES = [
    ('esg.environmental_investment', 'esg', 'environmental_investment', {}),
    ('esg.social_investment', 'esg', 'social_investment', {}),
    ('talent.rd_training_budget', 'talent', 'rd_training_budget', {}),
    ('talent.commercial_training_budget', 'talent', 'commercial_training_budget', {}),
    ('talent.operations_training_budget', 'talent', 'operations_training_budget', {}),
    ('talent.rd_headcount', 'talent', 'rd_headcount', {}),
    ('talent.commercial_headcount', 'talent', 'commercial_headcount', {}),
    ('talent.operations_headcount', 'talent', 'operations_headcount', {}),
]

# Teams are created to order so every case gets an otherwise identical firm.
def make_team(name):
    return Team.objects.create(
        game=game, name=name, firm_starter_profile=profile,
        performance_index=100, cash_on_hand=D('60000000'),
        total_equity=D('60000000'))


existing = list(Team.objects.filter(game=game).order_by('id'))
control = existing[0]
control.name = 'CONTROL'
control.save(update_fields=['name'])

case_teams = {}
for label, _model, _field, _extra in CASES:
    case_teams[label] = make_team(f'PROBE {label}'[:100])

all_teams = [control] + list(case_teams.values())
# Teams seeded by setup_test_game that are not part of the experiment still
# have to submit, or the engine refuses to resolve.
bystanders = existing[1:]


def baseline_submission(team):
    sub, _ = DecisionSubmission.objects.get_or_create(
        team=team, round=rnd, defaults={'status': 'draft'})
    DecisionBudgetAllocation.objects.filter(submission=sub).delete()
    DecisionBudgetAllocation.objects.create(
        submission=sub, rd_budget=D('1000000'), marketing_budget=D('1000000'),
        strategy_budget=D('1000000'), research_budget=D('0'))
    DecisionESG.objects.filter(submission=sub).delete()
    DecisionESG.objects.create(submission=sub,
                               environmental_investment=D('0'),
                               social_investment=D('0'))
    return sub


subs = {t.id: baseline_submission(t) for t in all_teams + bystanders}

from core.models.talent import DecisionTalent

TALENT_DEFAULTS = dict(
    rd_headcount=10, commercial_headcount=10, operations_headcount=10,
    rd_salary_level=3, commercial_salary_level=3, operations_salary_level=3,
    rd_training_budget=D('0'), commercial_training_budget=D('0'),
    operations_training_budget=D('0'),
)

applied = {}
for label, model_key, field, extra in CASES:
    team = case_teams[label]
    sub = subs[team.id]
    if model_key == 'esg':
        row = DecisionESG.objects.get(submission=sub)
        setattr(row, field, NEGATIVE)
        row.save()
        applied[label] = str(getattr(DecisionESG.objects.get(submission=sub), field))
    elif model_key == 'talent':
        DecisionTalent.objects.filter(submission=sub).delete()
        values = dict(TALENT_DEFAULTS)
        values[field] = int(NEGATIVE) if 'headcount' in field else NEGATIVE
        DecisionTalent.objects.create(submission=sub, **values)
        applied[label] = str(getattr(
            DecisionTalent.objects.get(submission=sub), field))

# The control team also gets a talent row at the defaults, so the comparison is
# the sign of one field rather than the presence of the decision.
DecisionTalent.objects.filter(submission=subs[control.id]).delete()
DecisionTalent.objects.create(submission=subs[control.id], **TALENT_DEFAULTS)

for sub in subs.values():
    sub.status = 'locked'
    sub.locked_at = timezone.now()
    sub.save(update_fields=['status', 'locked_at'])

cash_before = {t.id: D(str(t.cash_on_hand)) for t in all_teams}

from core.engine.advance_round import _run_phase_1
_run_phase_1(game.id)


def books(team):
    row = (RoundResultFinancials.objects
           .filter(team=team, round_number=rnd.round_number)
           .order_by('-id').first())
    if row is None:
        return None
    return {f: D(str(getattr(row, f))) for f in
            ('total_revenue', 'strategy_expense', 'admin_overhead',
             'operating_income', 'net_income', 'cash_closing')}


control_books = books(control)
results = {'game': game.id, 'round': rnd.round_number,
           'negative_value': str(NEGATIVE), 'applied': applied,
           'control': {k: str(v) for k, v in (control_books or {}).items()},
           'cases': {}}

for label, _m, _f, _e in CASES:
    team = case_teams[label]
    team.refresh_from_db()
    b = books(team)
    if b is None or control_books is None:
        results['cases'][label] = {'measured': False}
        continue
    deltas = {k: str(b[k] - control_books[k]) for k in b}
    pays = (b['net_income'] - control_books['net_income']) > 0
    results['cases'][label] = {
        'measured': True,
        'books': {k: str(v) for k, v in b.items()},
        'delta_vs_control': deltas,
        'pays_the_team': bool(pays),
        'net_income_advantage': str(b['net_income'] - control_books['net_income']),
    }

results['fields_that_pay'] = sorted(
    l for l, r in results['cases'].items() if r.get('pays_the_team'))
results['fields_measured'] = sorted(
    l for l, r in results['cases'].items() if r.get('measured'))

print(json.dumps(results, indent=2, default=str))
print('---NEGATIVE-SWEEP-JSON---')
print(json.dumps(results, default=str))
