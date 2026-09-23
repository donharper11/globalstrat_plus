"""W-CE3-03 / W-CE3-04: does the income statement add up?

Two questions, asked of the round results this pass's disposable game produced,
through the served payload a student's browser actually receives
(`/api/games/N/teams/T/financial-reports/history/`) and through the line set
the page renders from (`pages/incomeStatementRows.js`).

    page_gap    = gross profit - (the lines the PAGE prints) - printed net income
    served_gap  = gross profit - (every expense field the API SERVES)
                  - served operating income

A page that does not add up is W-CE3-03. A served payload that does not add up
is W-CE3-04, and it is the harder one: the charge exists in the engine and is
on no field at all.

    python3 statement_gap.py <game-name-substring> [label]
"""
import json
import os
import pathlib
import re
import sys
from decimal import Decimal as D

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                      # noqa: E402
django.setup()

from django.test import Client                                     # noqa: E402

from core.models import Game, Team, User                            # noqa: E402

ROWS_JS = (WT / 'frontend/globalstrat-frontend/src/pages'
           / 'incomeStatementRows.js')


def page_fields():
    """The statement fields the page prints, read from the page's own source.

    Not restated here: the point of the measurement is what a student sees, and
    a second list would drift from it exactly as the served payload did.
    """
    source = ROWS_JS.read_text()
    block = source.split('INCOME_STATEMENT_LINES = [')[1].split('];')[0]
    return [m.group(1) for m in re.finditer(r"field:\s*'([a-z_]+)'", block)]


# Revenue lines, the two ends of the identity, and the subtotals the page also
# prints. A subtotal counted as an expense would double every line above it,
# which is why it is named here rather than assumed.
REVENUE_FIELDS = {'total_revenue', 'total_cogs', 'gross_profit', 'net_income',
                  'operating_income'}
RATIO_SUFFIX = '_pct'


def main():
    needle = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else 'gap'
    game = Game.objects.filter(name__icontains=needle).order_by('-id').first()
    if game is None:
        raise SystemExit(f'no game matching {needle!r}')

    printed = [f for f in page_fields()
               if f not in REVENUE_FIELDS and not f.endswith(RATIO_SUFFIX)]

    client = Client(SERVER_NAME='127.0.0.1')
    instructor = User.objects.filter(role='instructor').first()
    from core.authentication import create_access_token
    token = create_access_token(instructor)

    out = {'game': game.name, 'game_id': game.id,
           'page_expense_fields': printed, 'teams': []}
    for team in Team.objects.filter(game=game).order_by('id'):
        response = client.get(
            f'/api/games/{game.id}/teams/{team.id}'
            f'/financial-reports/history/',
            HTTP_AUTHORIZATION=f'Bearer {token}')
        rounds = response.json()['rounds']
        for row in rounds:
            if row['round_number'] == 0:
                continue
            served_expense = [
                key for key, value in row.items()
                if key.endswith('_expense') or key in (
                    'admin_overhead', 'platform_amortization',
                    'platform_switch_write_off', 'other_operating_expense')]
            served_expense = [k for k in served_expense
                              if k not in ('interest_expense', 'tax_expense')]
            gross = D(str(row['gross_profit']))
            page_total = sum((D(str(row.get(f) or 0)) for f in printed), D('0'))
            page_gap = gross - page_total - D(str(row['net_income']))
            served_total = sum(
                (D(str(row.get(f) or 0)) for f in served_expense), D('0'))
            served_gap = (gross - served_total
                          - D(str(row['operating_income'])))
            below = (D(str(row['operating_income']))
                     - D(str(row['interest_expense']))
                     - D(str(row['tax_expense']))
                     - D(str(row['net_income']))
                     - D(str(row.get('other_non_operating_expense') or 0)))
            out['teams'].append({
                'team': team.name, 'round': row['round_number'],
                'gross_profit': str(gross),
                'net_income': str(row['net_income']),
                'operating_income': str(row['operating_income']),
                'served_expense_fields': served_expense,
                'page_income_statement_gap': str(page_gap),
                'page_gap_not_in_any_served_field': str(served_gap),
                'below_operating_income_gap': str(below),
            })

    path = SCRATCH.parent / f'statement-{label}.json'
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    worst_page = max((abs(D(t['page_income_statement_gap']))
                      for t in out['teams']), default=D('0'))
    worst_served = max((abs(D(t['page_gap_not_in_any_served_field']))
                        for t in out['teams']), default=D('0'))
    worst_below = max((abs(D(t['below_operating_income_gap']))
                       for t in out['teams']), default=D('0'))
    print(f'record={path}')
    print(f'worst_page_gap={worst_page} '
          f'worst_served_gap={worst_served} '
          f'worst_below_operating_income_gap={worst_below}')
    return 0 if (worst_page == 0 and worst_served == 0
                 and worst_below == 0) else 1


if __name__ == '__main__':
    raise SystemExit(main())
