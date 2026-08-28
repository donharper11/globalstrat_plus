"""Two candidate rule findings, probed cheaply before anyone classifies them.

The handoff names both and asks for a small controlled probe first, because a
mechanism that looks exploitable in the source may be worth nothing on the
board. Neither is repaired here: a confirmed rules-sensitive finding gets a
disposition request, not a silent change to a published scoring formula.

**A. `$1 budget / $1 spend`.** `_strategic_capability_component` scores R&D as
`rd_spend / rd_budget`, clamped to 1, and capability is 25% of the performance
index. A team declaring a one-dollar budget and spending one dollar scores the
ratio a team spending millions against a realistic budget cannot beat. The
probe: identical teams, one on the documented baseline, one declaring a minimal
budget and matching it, everything else equal.

**B. One-unit anti-exploit bypass.** Two guards protect against a firm that
does not compete — `_is_voluntarily_commercially_inactive`, which caps the
composite at 0.25, and `_enforce_zero_revenue_invariant`, which holds a
zero-revenue firm below the lowest revenue-positive one. Both are written
against *zero* revenue. The probe: a team that sells a single unit, so revenue
is positive by the smallest possible margin, against a team that sells nothing.
"""
import json
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE

results = {}


def fresh_game():
    call_command('setup_test_game', verbosity=0)
    from core.models import Game, Round, Team
    game = Game.objects.order_by('-id').first()
    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    return game, rnd, teams


def submissions(rnd, teams):
    from core.models import DecisionSubmission
    subs = {}
    for team in teams:
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(sub, team)
        subs[team.id] = sub
    return subs


def lock(subs):
    for sub in subs.values():
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])


def read(team, rnd):
    from core.models import RoundResultFinancials, RoundResultPerformanceIndex
    fin = (RoundResultFinancials.objects
           .filter(team=team, round_number=rnd.round_number)
           .order_by('-id').first())
    idx = (RoundResultPerformanceIndex.objects
           .filter(team=team, round_number=rnd.round_number)
           .order_by('-id').first())
    return {
        'total_revenue': str(fin.total_revenue) if fin else None,
        'net_income': str(fin.net_income) if fin else None,
        'index_value': str(idx.index_value) if idx else None,
        'satisfaction_score': str(idx.satisfaction_score) if idx else None,
    }


# --- A. the capability ratio ------------------------------------------------
from core.engine.advance_round import _run_phase_1
from core.models.decisions import DecisionBudgetAllocation, DecisionMarketing
from core.models.decisions import DecisionRDInvestment

game, rnd, teams = fresh_game()
subs = submissions(rnd, teams)
control, probe = teams[0], teams[1]

# The probe declares a one-dollar R&D budget. It spends nothing on R&D either,
# so the ratio is 0/1 rather than 1/1 — the point is to see whether the
# denominator alone moves capability, without adding an R&D row the control
# does not have.
budget = DecisionBudgetAllocation.objects.get(submission=subs[probe.id])
budget.rd_budget = D('1')
budget.save(update_fields=['rd_budget'])

lock(subs)
_run_phase_1(game.id)
results['capability_ratio'] = {
    'question': 'does declaring a one-dollar R&D budget change the outcome?',
    'control_rd_budget': str(BASE.BUDGET['rd_budget']),
    'probe_rd_budget': '1',
    'control': read(control, rnd),
    'probe': read(probe, rnd),
}

# --- B. one unit of revenue -------------------------------------------------
game2, rnd2, teams2 = fresh_game()
subs2 = submissions(rnd2, teams2)
silent, seller = teams2[0], teams2[1]

# The silent team withdraws from the market entirely: no production, no
# promotion, no distribution, no sales staff — the state both guards describe.
for row in DecisionMarketing.objects.filter(submission=subs2[silent.id]):
    row.production_volume = 0
    row.promotion_budget = D('0')
    row.distribution_investment = D('0')
    row.sales_team_count = 0
    row.demand_estimate = 0
    row.save()

# The seller does the same, except for one unit.
rows = list(DecisionMarketing.objects.filter(submission=subs2[seller.id]).order_by('pk'))
for index, row in enumerate(rows):
    row.production_volume = 1 if index == 0 else 0
    row.promotion_budget = D('0')
    row.distribution_investment = D('0')
    row.sales_team_count = 0
    row.demand_estimate = 1 if index == 0 else 0
    row.save()

lock(subs2)
_run_phase_1(game2.id)
results['one_unit_bypass'] = {
    'question': 'does selling a single unit escape the zero-revenue guards?',
    'silent': read(silent, rnd2),
    'one_unit_seller': read(seller, rnd2),
    'other_teams': {t.name: read(t, rnd2) for t in teams2[2:]},
}

print('---RULE-PROBE-JSON---')
print(json.dumps(results, default=str))
