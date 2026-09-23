"""W-CE3-01: the tax structure's setup cost, on a statement line.

    verify_tax_charge.py <round>

Walkthrough 3 found $2,000,000 leaving a team between rounds with no line on
any statement: `engine/costs` took it out of `team.cash_on_hand` during
Phase 1, before `engine/financials` read `cash_opening`, so the statement's
own identity closed perfectly and the money was simply gone. Integrator
decision 15 moved it into the round's charges, where it joins
`strategy_expense`.

This checks the claim from the two sides a player has:

  * the round's opening cash is the previous round's closing cash, to the
    cent -- nothing leaves between statements; and
  * for every team that switched structure in this round, the setup cost is
    inside `strategy_expense`, which is a line the Financial Reports income
    statement prints.

It reads the structure rows straight from the database (the authored
`setup_cost` and the round the switch was adopted in) so the expected figure
does not come from the same code that books it.
"""
import json
import pathlib
import subprocess
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
out = {'round': ROUND, 'checks': [], 'teams': {}}


def check(name, ok, detail=''):
    out['checks'].append({'name': name, 'outcome': 'pass' if ok else 'fail',
                          'detail': str(detail)[:600]})
    print('  %-4s %s -- %s' % ('PASS' if ok else 'FAIL', name,
                               str(detail)[:200]))


def sql(statement):
    got = subprocess.run([sys.executable, str(SCRATCH / 'dbq.py'), 'sql',
                          statement], capture_output=True, text=True,
                         cwd=str(SCRATCH))
    lines = got.stdout.strip().splitlines()
    if not lines:
        print(got.stderr[:400])
        return []
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:]]


def num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


switches = sql(
    "select ts.team_id, t.name as team_name, ts.adopted_round, ts.setup_cost_paid, "
    "s.code, s.name, s.setup_cost, s.annual_maintenance_cost "
    "from team_tax_structure ts "
    "join tax_structure_type s on s.id = ts.current_structure_id "
    "join team t on t.id = ts.team_id "
    "order by ts.team_id")
out['tax_structure_rows'] = switches
adopted_here = [r for r in switches if str(r.get('adopted_round')) == str(ROUND)]
out['switched_this_round'] = adopted_here
print('teams that adopted a structure in round %d: %s'
      % (ROUND, [r['team_name'] for r in adopted_here] or 'none'))

for team in G['teams']:
    tid = team['team_id']
    member = [r for r in G['roster'] if r.get('team_id') == tid][0]
    tok = login(member['username'], member.get('student_id'))
    s, fin = call('GET', '/api/games/%d/teams/%d/financial-reports/history/'
                  % (GID, tid), token=tok)
    rows = (fin or {}).get('rounds') or (fin or {}).get('history') or []
    if isinstance(fin, dict) and not rows:
        for key in fin:
            if isinstance(fin[key], list) and fin[key] and isinstance(fin[key][0], dict) \
                    and 'cash_closing' in fin[key][0]:
                rows = fin[key]
                break
    this = next((r for r in rows if int(r.get('round_number') or 0) == ROUND), None)
    prev = next((r for r in rows if int(r.get('round_number') or 0) == ROUND - 1), None)
    entry = {'team': team['team_name'],
             'strategy_expense': num((this or {}).get('strategy_expense')),
             'cash_opening': num((this or {}).get('cash_opening')),
             'previous_cash_closing': num((prev or {}).get('cash_closing'))}
    row = next((r for r in adopted_here if r['team_name'] == team['team_name']),
               None)
    entry['switched_this_round'] = bool(row)
    if row:
        entry['setup_cost'] = num(row.get('setup_cost'))
        entry['structure'] = row.get('name')
    out['teams'][team['team_name']] = entry
    if prev is not None and this is not None:
        gap = round(entry['cash_opening'] - entry['previous_cash_closing'], 2)
        entry['cash_carried_between_rounds'] = gap
        check('%s: nothing leaves between the two statements' % team['team_name'],
              abs(gap) < 0.02,
              'round %d closed at %.2f, round %d opened at %.2f, difference %.2f'
              % (ROUND - 1, entry['previous_cash_closing'], ROUND,
                 entry['cash_opening'], gap))
    if row and this is not None:
        cost = entry['setup_cost']
        check('%s: the %s setup cost of %.0f is inside the printed strategy '
              'expense' % (team['team_name'], row.get('name'), cost),
              entry['strategy_expense'] >= cost - 0.02,
              'strategy_expense on the statement is %.2f, the authored setup '
              'cost is %.2f' % (entry['strategy_expense'], cost))

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / ('verify-tax-charge-r%d.json' % ROUND)).write_text(
    json.dumps(out, indent=1, ensure_ascii=False, default=str))
print('record:', RECORDS / ('verify-tax-charge-r%d.json' % ROUND))
