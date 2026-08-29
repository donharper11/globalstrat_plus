"""Stage 2 — bounded sensitivity characterisation.

Deliberately not 24 independent sweeps. The 107-probe screen already provides
the minimum/baseline/maximum points for every dimension; this adds only what
those three points cannot show.

* **Categorical** dimensions are tabulated from the recorded screen. Not rerun.
* **Formula families** — dimensions computed by the same expression and
  differing only by which organisational pool they name — are swept once through
  a representative, with the equivalence shown from the code rather than
  re-measured three times.
* **Ordinary monotonic cost** dimensions get two interior points, enough to
  show the shape between the ends the screen already has.
* **Joint mechanisms** get a small grid, because a one-field curve through them
  is misleading: R&D budget with R&D spend, and price with volume.
"""
import json
import time
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF

SEED = 'crv2-06-characterise-1'

# Families the engine computes with one expression, looped over a pool name.
# `costs.py` runs `for prefix in ['rd', 'commercial', 'operations']` and applies
# identical arithmetic to `{prefix}_headcount`, `{prefix}_salary_level` and
# `{prefix}_training_budget`; sweeping all nine would measure the loop, not the
# model.
FORMULA_FAMILIES = {
    'talent headcount': {
        'representative': ('talent', 'rd_headcount'),
        'members': ['talent.rd_headcount', 'talent.commercial_headcount',
                    'talent.operations_headcount'],
        'evidence': "core/engine/costs.py: `for prefix in ['rd','commercial',"
                    "'operations']` then `hc = getattr(talent_decision, "
                    "f'{prefix}_headcount')` and `pool_salary = hc * "
                    "salary_base[sl]` — one expression, three pool names.",
    },
    'talent training budget': {
        'representative': ('talent', 'rd_training_budget'),
        'members': ['talent.rd_training_budget',
                    'talent.commercial_training_budget',
                    'talent.operations_training_budget'],
        'evidence': "core/engine/costs.py and core/engine/talent.py read "
                    "`f'{prefix}_training_budget'` inside the same pool loop.",
    },
    'talent salary level': {
        'representative': ('talent', 'rd_salary_level'),
        'members': ['talent.rd_salary_level', 'talent.commercial_salary_level',
                    'talent.operations_salary_level'],
        'evidence': "core/engine/costs.py indexes one shared salary_base table "
                    "with `f'{prefix}_salary_level'`.",
    },
    'esg investment': {
        'representative': ('esg', 'environmental_investment'),
        'members': ['esg.environmental_investment', 'esg.social_investment'],
        'evidence': "core/engine/costs.py: `strategy_expense += "
                    "esg.environmental_investment + esg.social_investment` — "
                    "one line, both fields, same coefficient.",
    },
}

# Ordinary monotonic accounting costs: two interior points each.
MONOTONIC_REPRESENTATIVES = [
    ('esg', 'environmental_investment', ['500000', '1000000']),
    ('talent', 'rd_training_budget', ['250000', '750000']),
    ('talent', 'rd_headcount', ['25', '75']),
    ('marketing', 'promotion_budget', ['150000', '600000']),
    ('platforms', 'committed_cost', ['250000', '750000']),
    ('market-entry', 'initial_investment', ['250000', '750000']),
]

# Joint mechanisms. A single-field curve through either is misleading.
JOINT_RD = {
    'name': 'R&D budget x R&D spend',
    'all_rows': False,
    'why': 'V2-021 moved the capability denominator from the declared budget '
           'to a scenario constant. The grid shows whether the declared budget '
           'still interacts with spend at all, which a curve through either '
           'field alone cannot answer.',
    'grid': [('budget', 'rd_budget', b, 'rd', 'amount', a)
             for b in ('1', '2000000', '50000000')
             for a in ('0', '1000000', '2000000')],
}
JOINT_PRICE = {
    'name': 'retail price x production volume',
    'all_rows': True,
    'why': 'Revenue is price times units sold, and units sold is bounded by '
           'both production and demand. Either field alone traces a curve that '
           'depends entirely on where the other one was pinned.',
    'grid': [('marketing', 'retail_price', p, 'marketing', 'production_volume', v)
             for p in ('50', '420', '2000')
             for v in ('0', '20000', '60000')],
}


MODEL_FOR = {
    'budget': ('core.models.decisions', 'DecisionBudgetAllocation'),
    'esg': ('core.models.decisions', 'DecisionESG'),
    'marketing': ('core.models.decisions', 'DecisionMarketing'),
    'talent': ('core.models.talent', 'DecisionTalent'),
    'rd': ('core.models.decisions', 'DecisionRDInvestment'),
    'platforms': ('core.models.decisions', 'DecisionPlatformDevelopment'),
    'market-entry': ('core.models.decisions', 'DecisionMarketEntry'),
}


def model_for(decision_type):
    import importlib
    module, name = MODEL_FOR[decision_type]
    return getattr(importlib.import_module(module), name)


def set_field(submission, decision_type, field, value, all_rows=False):
    """Set one field. `all_rows` applies it across the team's portfolio.

    The first version of the price/volume grid wrote to `rows[0]` only, and
    every one of its nine cells came back with revenue identical to the cent —
    including production_volume=0. The team carries two marketing rows and the
    one being edited sells nothing at baseline, so the grid was varying a
    product with no sales and reporting that as "price and volume do nothing".
    A team-wide price or volume decision is the joint mechanism worth
    characterising, so the grid sets every row.
    """
    model = model_for(decision_type)
    rows = list(model.objects.filter(submission=submission).order_by('pk'))
    if not rows:
        return False
    targets = rows if all_rows else rows[:1]
    for row in targets:
        django_field = row._meta.get_field(field)
        kind = django_field.get_internal_type()
        if kind == 'DecimalField':
            coerced = D(str(value))
        elif 'Integer' in kind:
            coerced = int(D(str(value)))
        else:
            coerced = value
        setattr(row, field, coerced)
        row.save(update_fields=[field])
    return True


def run(verbose=True):
    from core.models import DecisionSubmission, Game, Round, Team

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('char-owner', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    game = Game.objects.order_by('-id').first()
    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]

    def prepare(changes=()):
        def apply():
            for team in teams:
                sub, _ = DecisionSubmission.objects.get_or_create(
                    team=team, round=rnd, defaults={'status': 'draft'})
                BASE.build(sub, team)
                BASE.build_optional(sub, team)
                if team.id == subject.id:
                    for change in changes:
                        decision_type, field, value = change[:3]
                        all_rows = change[3] if len(change) > 3 else False
                        set_field(sub, decision_type, field, value, all_rows)
                sub.status = 'locked'
                sub.locked_at = timezone.now()
                sub.save(update_fields=['status', 'locked_at'])
        return apply

    started = time.time()
    baseline = CF.evaluate(game, rnd, subject, prepare())
    repeat = CF.evaluate(game, rnd, subject, prepare())
    report = {
        'seed': SEED,
        'baseline_metrics': baseline,
        'baseline_is_repeatable': CF.is_zero(CF.delta(baseline, repeat)),
        'formula_families': FORMULA_FAMILIES,
        'interior_points': {},
        'joint': {},
        'evaluations': 2,
    }

    def measure(changes):
        report['evaluations'] += 1
        metrics = CF.evaluate(game, rnd, subject, prepare(changes))
        return {'metrics': metrics, 'delta': CF.delta(baseline, metrics)}

    # A grid whose cells are all identical measured nothing; recorded so the
    # reader can tell a flat mechanism from a probe that never landed.
    def grid_is_degenerate(cells):
        revenues = {c['metrics']['total_revenue'] for c in cells.values()}
        return len(revenues) == 1

    for decision_type, field, points in MONOTONIC_REPRESENTATIVES:
        key = f'{decision_type}.{field}'
        report['interior_points'][key] = {}
        for value in points:
            report['interior_points'][key][value] = measure(
                [(decision_type, field, value)])
            if verbose:
                print(f'  interior {key} = {value}', flush=True)

    for spec in (JOINT_RD, JOINT_PRICE):
        cells = {}
        for a_type, a_field, a_value, b_type, b_field, b_value in spec['grid']:
            label = f'{a_field}={a_value} x {b_field}={b_value}'
            wide = spec.get('all_rows', False)
            cells[label] = measure([(a_type, a_field, a_value, wide),
                                    (b_type, b_field, b_value, wide)])
            if verbose:
                print(f'  joint {label}', flush=True)
        report['joint'][spec['name']] = {
            'why': spec['why'], 'cells': cells,
            'all_rows': spec.get('all_rows', False),
            'degenerate_revenue': grid_is_degenerate(cells)}

    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
