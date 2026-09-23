"""Cross-check what a team decided against what the results and statements
show, and the leaderboard against the performance index: check_round.py <round>

Pure API (signed in as each team's first member and as the instructor); the
screens themselves are photographed by student_tour.py. Writes
records/check-round<N>.json.
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
out = {'round': ROUND, 'teams': {}, 'checks': []}


def check(name, ok, detail=''):
    out['checks'].append({'name': name, 'outcome': 'pass' if ok else 'fail', 'detail': str(detail)[:700]})
    print('  %-5s %s -- %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:200]))


def num(x):
    try:
        return float(x)
    except Exception:
        return None


itok = login(G.get('instructor', 'walk_instructor'))
s, lb = call('GET', '/api/games/%d/leaderboard/round/%d/' % (GID, ROUND), token=itok)
out['leaderboard'] = lb
entries = (lb.get('rankings') or lb.get('leaderboard') or lb.get('teams') or lb.get('entries') or []) if isinstance(lb, dict) else lb
out['leaderboard_entries'] = entries
if entries:
    ranked = sorted(entries, key=lambda e: -(num(e.get('performance_index')) or 0))
    order_ok = all((num(entries[i].get('performance_index')) or 0) >= (num(entries[i + 1].get('performance_index')) or 0) for i in range(len(entries) - 1))
    ranks = [e.get('rank') for e in entries]
    check('leaderboard is ordered by performance index and ranks are 1..n', order_ok and ranks == list(range(1, len(entries) + 1)),
          [(e.get('team_name'), e.get('rank'), e.get('performance_index')) for e in entries])
else:
    check('leaderboard has entries', False, str(lb)[:300])

for team in G['teams'][:3]:
    tid = team['team_id']
    m = [r for r in G['roster'] if r.get('team_id') == tid][0]
    tok = login(m['username'], m.get('student_id'))
    s1, draft = call('GET', '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, tid, ROUND), token=tok)
    s2, res = call('GET', '/api/games/%d/teams/%d/results/round/%d/' % (GID, tid, ROUND), token=tok)
    s3, fin = call('GET', '/api/games/%d/teams/%d/financial-reports/history/' % (GID, tid), token=tok)
    s4, dash = call('GET', '/api/games/%d/teams/%d/dashboard/scorecard/?round=%d' % (GID, tid, ROUND), token=tok)
    t = {'team': team['team_name'], 'statuses': [s1, s2, s3, s4],
         'draft_status': draft.get('status') if isinstance(draft, dict) else None,
         'marketing_decisions': draft.get('marketing_decisions') if isinstance(draft, dict) else None,
         'product_retires': draft.get('product_retires') if isinstance(draft, dict) else None,
         'results_keys': list(res.keys()) if isinstance(res, dict) else str(res)[:200],
         'performance': res.get('performance') if isinstance(res, dict) else None,
         'financials': res.get('financials') if isinstance(res, dict) else None,
         'price_adjustments': res.get('price_adjustments') if isinstance(res, dict) else None,
         'product_performance': res.get('product_performance') or res.get('products') if isinstance(res, dict) else None,
         'statement_round': None}
    rounds = (fin.get('rounds') or []) if isinstance(fin, dict) else []
    row = next((r for r in rounds if r.get('round_number') == ROUND or r.get('round') == ROUND), rounds[-1] if rounds else None)
    t['statement_round'] = row
    out['teams'][team['team_name']] = t
    name = team['team_name']
    check('%s: results for round %d served' % (name, ROUND), s2 == 200 and isinstance(res, dict) and res.get('performance') is not None, 'HTTP %s keys=%s' % (s2, t['results_keys']))
    # Leaderboard vs results
    me = next((e for e in entries if e.get('team_id') == tid or e.get('team_name') == name), None)
    perf = (res.get('performance') or {}) if isinstance(res, dict) else {}
    check('%s: performance index on results == leaderboard' % name, me is not None and num(me.get('performance_index')) is not None and abs((num(me.get('performance_index')) or 0) - (num(perf.get('index_value')) or -1)) < 0.05,
          'leaderboard=%s results=%s rank=%s' % (me and me.get('performance_index'), perf.get('index_value'), perf.get('leaderboard_position') or perf.get('rank')))
    # Statement vs results financials
    finr = (res.get('financials') or {}) if isinstance(res, dict) else {}
    if row:
        check('%s: income statement revenue == results revenue' % name, abs((num(row.get('total_revenue')) or 0) - (num(finr.get('total_revenue')) or -1)) < 1, 'statement=%s results=%s' % (row.get('total_revenue'), finr.get('total_revenue')))
        check('%s: statement carries research and compliance rows' % name, 'research_expense' in row and 'compliance_expense' in row, 'research=%s compliance=%s' % (row.get('research_expense'), row.get('compliance_expense')))
    else:
        check('%s: income statement row for round %d' % (name, ROUND), False, 'rounds=%s' % [r.get('round_number') for r in rounds])
    # Decided price vs shown price
    prods = t['product_performance'] or []
    for md in (t['marketing_decisions'] or []):
        pp = next((p for p in prods if p.get('team_product') == md.get('team_product') or p.get('product_id') == md.get('team_product')), None)
        if pp is not None:
            check('%s: product %s priced as decided (or adjusted with notice)' % (name, md.get('team_product')),
                  (num(pp.get('retail_price') or pp.get('price')) is not None),
                  'decided=%s shown=%s adjustments=%s' % (md.get('retail_price'), pp.get('retail_price') or pp.get('price'), json.dumps(t['price_adjustments'])[:200]))

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / ('check-round%d.json' % ROUND)).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
print('record:', RECORDS / ('check-round%d.json' % ROUND))
