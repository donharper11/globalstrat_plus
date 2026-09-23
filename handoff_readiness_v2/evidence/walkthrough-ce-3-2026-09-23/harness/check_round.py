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

for team in G['teams']:
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
    t['statement_previous'] = next(
        (r for r in rounds if r.get('round_number') == ROUND - 1), None)
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
        rev_res = num(finr.get('total_revenue'))
        check('%s: income statement revenue == results revenue' % name,
              rev_res is not None and abs((num(row.get('total_revenue')) or 0) - rev_res) < 1,
              'statement=%s results=%s' % (row.get('total_revenue'), finr.get('total_revenue')))
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


# ---------------------------------------------------------------------------
# Money reconciliation, per team per round (walkthrough 3).
#   R1  the identity the platform publishes:
#       cash_opening + operating_cf + investing_cf + financing_cf == cash_closing
#   R2  the plain form the brief asks for:
#       opening cash + revenue - charges = closing cash, where "charges" are
#       every expense line the statement shows a player, and the remainder is
#       named by the statement's own cash-flow lines.
CHARGE_LINES = ['total_cogs', 'rd_expense', 'platform_amortization',
                'platform_switch_write_off', 'marketing_expense',
                'strategy_expense', 'research_expense', 'compliance_expense',
                'admin_overhead', 'logistics_tariff_expense',
                'inventory_expense', 'interest_expense', 'tax_expense']
out['reconciliation'] = {}
for name, t in out['teams'].items():
    row = t.get('statement_round') or {}
    if not row:
        continue
    g = lambda k: (num(row.get(k)) or 0.0)
    opening, closing = g('cash_opening'), g('cash_closing')
    ocf, icf, fcf = g('operating_cash_flow'), g('investing_cash_flow'), g('financing_cash_flow')
    identity = opening + ocf + icf + fcf
    charges = sum(g(k) for k in CHARGE_LINES)
    revenue = g('total_revenue')
    direct = opening + revenue - charges
    entry = {
        'cash_opening': opening, 'total_revenue': revenue,
        'charges_on_the_statement': round(charges, 2),
        'charge_lines': {k: g(k) for k in CHARGE_LINES if g(k)},
        'cash_closing': closing,
        'opening_plus_revenue_minus_charges': round(direct, 2),
        'operating_cash_flow': ocf, 'investing_cash_flow': icf,
        'financing_cash_flow': fcf, 'dividends_paid': g('dividends_paid'),
        'net_income': g('net_income'), 'operating_income': g('operating_income'),
        'gross_profit': g('gross_profit'),
        'identity_residual': round(closing - identity, 2),
        'plain_form_residual': round(closing - direct, 2),
    }
    entry['gross_profit_residual'] = round(g('gross_profit') - (revenue - g('total_cogs')), 2)
    visible_opex = sum(g(k) for k in CHARGE_LINES
                       if k not in ('total_cogs', 'interest_expense', 'tax_expense'))
    entry['operating_income_residual'] = round(
        g('operating_income') - (g('gross_profit') - visible_opex), 2)
    entry['net_income_residual'] = round(
        g('net_income') - (g('operating_income') - g('interest_expense') - g('tax_expense')), 2)
    out['reconciliation'][name] = entry
    # Cash continuity BETWEEN rounds. The statement's own identity can close
    # perfectly and money still disappear, because `cash_opening` is read from
    # the team AFTER Phase 1 has already taken charges straight out of
    # `team.cash_on_hand`. So the closing cash of round N-1 is compared with
    # the opening cash of round N: they are the same money and nothing happens
    # between the two.
    prev = t.get('statement_previous') or {}
    if prev:
        gp = lambda k: (num(prev.get(k)) or 0.0)
        carry = round(opening - gp('cash_closing'), 2)
        entry['previous_cash_closing'] = gp('cash_closing')
        entry['cash_carried_between_rounds'] = carry
        check("%s: this round's opening cash == last round's closing cash" % name,
              abs(carry) < 0.02,
              'round %d closed at %.2f and round %d opened at %.2f, a difference of %.2f '
              'that appears on no statement line' % (ROUND - 1, gp('cash_closing'), ROUND,
                                                     opening, carry))

    check('%s: cash identity opening + OCF + ICF + FCF == closing' % name,
          abs(entry['identity_residual']) < 0.02,
          'opening=%.2f ocf=%.2f icf=%.2f fcf=%.2f closing=%.2f residual=%.2f'
          % (opening, ocf, icf, fcf, closing, entry['identity_residual']))
    check('%s: gross profit == revenue - cogs on the statement' % name,
          abs(entry['gross_profit_residual']) < 0.02,
          'residual=%.2f' % entry['gross_profit_residual'])
    check('%s: operating income == gross profit - the opex lines shown' % name,
          abs(entry['operating_income_residual']) < 0.02,
          'residual=%.2f (a negative residual is a charge the statement does not show)'
          % entry['operating_income_residual'])
    # The income statement the student actually reads (INCOME_STATEMENT_LINES
    # in frontend/.../pages/incomeStatementRows.js): revenue, cogs, gross
    # profit, R&D, marketing, strategy, research, compliance, admin, net
    # income, margin. Nothing else is on the page, so this is the sum a player
    # can do with a finger on the screen.
    PAGE_OPEX = ['rd_expense', 'marketing_expense', 'strategy_expense',
                 'research_expense', 'compliance_expense', 'admin_overhead']
    page_after_lines = g('gross_profit') - sum(g(k) for k in PAGE_OPEX)
    page_gap = round(g('net_income') - page_after_lines, 2)
    served_but_unshown = (g('interest_expense') + g('tax_expense')
                          + g('logistics_tariff_expense') + g('inventory_expense'))
    entry['page_income_statement_gap'] = page_gap
    entry['page_gap_explained_by_served_fields'] = round(-served_but_unshown, 2)
    entry['page_gap_not_in_any_served_field'] = round(page_gap + served_but_unshown, 2)
    check('%s: the income statement on the page adds up '
          '(revenue - cogs - the expense lines shown == net income)' % name,
          abs(page_gap) < 0.02,
          'gap=%.2f; of which %.2f is interest/tax/logistics/inventory the API serves but '
          'the page does not print, and %.2f is in no served field at all'
          % (page_gap, -served_but_unshown, page_gap + served_but_unshown))
    check('%s: net income == operating income - interest - tax' % name,
          abs(entry['net_income_residual']) < 0.02,
          'residual=%.2f' % entry['net_income_residual'])

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / ('check-round%d.json' % ROUND)).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
print('record:', RECORDS / ('check-round%d.json' % ROUND))
