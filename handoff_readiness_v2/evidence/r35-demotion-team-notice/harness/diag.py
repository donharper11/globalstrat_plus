import os, sys, pathlib, django
WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees/agent-ad31a78c64885fc47')
sys.path.insert(0, str(WT/'backend')); sys.path.insert(0, str(WT/'handoff_readiness_v2'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','globalstrat.settings')
django.setup()
from collections import Counter
from core.models import DecisionAuditEvent, DecisionSubmission, Game, Team
from core.models.decisions import DecisionMarketing
from core.models.results_financials import LeaderboardEntry, RoundResultFinancials, RoundResultPerformanceIndex
from core.engine import leaderboard as lb

g = Game.objects.order_by('id').first()
print('game', g.id, g.name, 'current_round', g.current_round)
for rn in (0, 1):
    print('--- round %d ---' % rn)
    for t in Team.objects.filter(game=g).order_by('id'):
        sub = DecisionSubmission.objects.filter(team=t, round__round_number=rn, round__game=g).first()
        mk = DecisionMarketing.objects.filter(submission=sub).count() if sub else 0
        fin = RoundResultFinancials.objects.filter(game=g, team=t, round_number=rn).first()
        perf = RoundResultPerformanceIndex.objects.filter(game=g, team=t, round_number=rn).first()
        ent = LeaderboardEntry.objects.filter(game=g, team=t, round_number=rn).first()
        print('  id=%-3s %-18s subid=%-5s mkrows=%-3s rev=%-16s idx=%-8s rank=%-4s carried=%s' % (
            t.id, t.name, sub.id if sub else None, mk,
            fin.total_revenue if fin else None, perf.index_value if perf else None,
            ent.rank if ent else None, t.performance_index))
print('--- demotion events ---')
for e in DecisionAuditEvent.objects.filter(game=g, action=lb.ACTION_INACTIVITY_DEMOTION).order_by('id'):
    print(' ', e.team.name, 'round', e.round.round_number if e.round_id else None, e.payload)
print('--- audit action counts ---')
print(Counter(DecisionAuditEvent.objects.filter(game=g).values_list('action', flat=True)))
