"""Would this round process? preflight_equity.py <round>

The engine refuses to score a round in which any team's stored equity raise
exceeds the funding shortfall it claims to finance, and the console offers no
way to find that out before the round is closed -- pressing *Run post-round
processing* simply does nothing visible. This is the check the console does
not have, run from outside the product so the walkthrough can say, for each
round, whether it was safe to close.
"""
import json
import pathlib
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
out = {'round': ROUND, 'teams': {}, 'would_refuse': []}

for ix, team in enumerate(G['teams'], start=1):
    tid = team['team_id']
    member = [r for r in G['roster'] if r.get('team_id') == tid][0]
    tok = login(member['username'], member.get('student_id'))
    s, d = call('GET', '/api/games/%d/teams/%d/decisions/round/%d/'
                % (GID, tid, ROUND), token=tok)
    s2, b = call('GET', '/api/games/%d/teams/%d/decisions/round/%d/summary/'
                 % (GID, tid, ROUND), token=tok)
    fin = (d or {}).get('financing') or {}
    bs = (b or {}).get('budget_summary') or {}
    equity = float(fin.get('new_equity') or 0)
    committed = float(bs.get('committed_total') or 0)
    cash = float(bs.get('cash_on_hand') or 0)
    debt = float(fin.get('new_debt') or 0)
    repay = float(fin.get('debt_repayment') or 0)
    shortfall = max(committed + repay - (cash + debt), 0)
    entry = {'status': (d or {}).get('status'), 'new_equity': equity,
             'committed_total': committed, 'cash_on_hand': cash,
             'new_debt': debt, 'debt_repayment': repay,
             'shortfall': round(shortfall, 2),
             'excess': round(equity - shortfall, 2)}
    out['teams'][team['team_name']] = entry
    flag = '' if equity <= shortfall + 0.01 else '  <-- THE ENGINE WILL REFUSE'
    if flag:
        out['would_refuse'].append(team['team_name'])
        print('REFUSE %d %s' % (ix, team['team_name']))
    print('%-22s status=%-7s equity=%15.2f shortfall=%15.2f excess=%12.2f%s'
          % (team['team_name'], entry['status'], equity, shortfall,
             entry['excess'], flag))

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / ('preflight-equity-r%d.json' % ROUND)).write_text(
    json.dumps(out, indent=1, ensure_ascii=False) + '\n')
print('\nteams whose equity the engine would refuse: %s'
      % (out['would_refuse'] or 'none'))
print('record:', RECORDS / ('preflight-equity-r%d.json' % ROUND))
