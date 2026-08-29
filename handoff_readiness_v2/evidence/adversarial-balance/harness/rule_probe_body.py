"""The two candidate rule findings, measured by counterfactual.

Same discipline as the screen: one game reaches a checkpoint, and every variant
is resolved from that identical state and rolled back. The team is compared only
with itself, so a difference is the rule and not the firm.

**A. `$1 R&D budget / $1 R&D spend`.** `_strategic_capability_component` scores
R&D as `rd_spend / rd_budget`, clamped to 1, and capability carries 0.25 of the
performance index. The baseline spends $100,000 against a $2,000,000 declared
budget — a ratio of 0.05. Declaring $1 and spending $1 is a ratio of 1.0 while
spending $99,999 less. If the index rises, the metric rewards a smaller
programme for being smaller.

**B. One-unit revenue bypass.** Two guards protect against a firm that does not
compete: `_is_voluntarily_commercially_inactive` caps the composite at 0.25, and
`_enforce_zero_revenue_invariant` holds a zero-revenue firm below the lowest
revenue-positive one. Both are written against *zero* revenue. The probe
compares a team that withdraws completely with the same team doing the same
thing except for a single unit of production.

Neither probe repairs anything. A confirmed finding gets a severity and a
disposition request, as V2-020 did.
"""
import json
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('rules-owner', 'a@e.com', 'x')
call_command('load_all_scenarios', verbosity=0)
call_command('setup_test_game', verbosity=0)

from core.models import DecisionSubmission, Game, Round, Team
from core.models.decisions import (DecisionBudgetAllocation, DecisionMarketing,
                                   DecisionRDInvestment)

game = Game.objects.order_by('-id').first()
rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
teams = list(Team.objects.filter(game=game).order_by('id'))
subject = teams[0]


def prepare():
    for team in teams:
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(sub, team)
        BASE.build_optional(sub, team)
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])


def subject_submission():
    return DecisionSubmission.objects.get(team=subject, round=rnd)


results = {'game': game.id, 'round': rnd.round_number, 'subject': subject.id}

baseline = CF.evaluate(game, rnd, subject, prepare)
# Determinism is already established by the screen's self-test; repeating the
# baseline here makes this file self-contained.
baseline_again = CF.evaluate(game, rnd, subject, prepare)
results['baseline'] = baseline
results['baseline_repeat_delta'] = CF.delta(baseline, baseline_again)
results['baseline_is_repeatable'] = CF.is_zero(results['baseline_repeat_delta'])


# --- A. the capability ratio ------------------------------------------------
def dollar_rd():
    prepare()
    sub = subject_submission()
    budget = DecisionBudgetAllocation.objects.get(submission=sub)
    budget.rd_budget = D('1')
    budget.save(update_fields=['rd_budget'])
    for row in DecisionRDInvestment.objects.filter(submission=sub):
        row.amount = D('1')
        row.save(update_fields=['amount'])


probe_a = CF.evaluate(game, rnd, subject, dollar_rd)
results['capability_ratio'] = {
    'question': 'does declaring $1 of R&D budget and spending $1 beat a '
                '$100,000 programme against a $2,000,000 budget?',
    'baseline_ratio': '100000 / 2000000 = 0.05',
    'probe_ratio': '1 / 1 = 1.00 (clamped at 1)',
    'baseline': baseline,
    'probe': probe_a,
    'delta': CF.delta(baseline, probe_a),
}


# --- B. one unit of revenue -------------------------------------------------
def withdraw(units):
    def apply():
        prepare()
        sub = subject_submission()
        rows = list(DecisionMarketing.objects.filter(submission=sub).order_by('pk'))
        for index, row in enumerate(rows):
            row.production_volume = units if index == 0 else 0
            row.demand_estimate = units if index == 0 else 0
            row.promotion_budget = D('0')
            row.distribution_investment = D('0')
            row.sales_team_count = 0
            row.save()
    return apply


silent = CF.evaluate(game, rnd, subject, withdraw(0))
one_unit = CF.evaluate(game, rnd, subject, withdraw(1))
results['one_unit_bypass'] = {
    'question': 'does producing a single unit escape the guards written '
                'against zero revenue?',
    'silent': silent,
    'one_unit': one_unit,
    'delta_one_unit_vs_silent': CF.delta(silent, one_unit),
    'delta_silent_vs_baseline': CF.delta(baseline, silent),
    'delta_one_unit_vs_baseline': CF.delta(baseline, one_unit),
}

print('---RULE-PROBE-JSON---')
print(json.dumps(results, default=str))
