"""Turn the per-round records into the tables the report prints.

    round_table.py <from> <to>

Prints, per round: how it was resolved, who locked, the standings, and the
per-team money reconciliation -- opening cash + revenue - charges = closing
cash, whether this round's opening cash is last round's closing cash, and
whether the printed income statement sums to the printed net income.
"""
import json
import pathlib
import sys

RECORDS = pathlib.Path(__file__).resolve().parent.parent / 'records'
FROM = int(sys.argv[1]) if len(sys.argv) > 1 else 1
TO = int(sys.argv[2]) if len(sys.argv) > 2 else FROM


def load(name):
    p = RECORDS / name
    return json.loads(p.read_text()) if p.exists() else None


def money(x):
    try:
        v = float(x)
    except Exception:
        return '--'
    return ('-$%s' % format(-v, ',.0f')) if v < 0 else ('$%s' % format(v, ',.0f'))


for rnd in range(FROM, TO + 1):
    chk = load('check-round%d.json' % rnd)
    if not chk:
        print('\n### Round %d -- no check record' % rnd)
        continue
    resolve = None
    for way in ('console', 'force', 'lifecycle'):
        for lang in ('en', 'zh-CN'):
            r = load('instructor-round%d-%s-%s.json' % (rnd, way, lang))
            if r:
                resolve = (way, lang, r)
    print('\n### Round %d' % rnd)
    if resolve:
        way, lang, r = resolve
        steps = {s['name']: s for s in r['steps']}
        phase1 = r['observed'].get('phase1_seconds')
        print('resolved: %s (console language %s); %d checks passed, %d failed'
              % (way, lang, r['summary']['passed'], r['summary']['failed']))
        for s in r['steps']:
            if s['outcome'] == 'fail':
                print('   instructor FAIL: %s -- %s' % (s['name'], s['detail'][:200]))
        if phase1:
            print('phase 1: %s s' % phase1)
    locked = []
    for t, row in (chk.get('teams') or {}).items():
        if row.get('draft_status') == 'locked':
            locked.append(t)
    print('locked: %s' % (', '.join(locked) or 'none'))
    entries = chk.get('leaderboard_entries') or []
    print('standings: %s' % ' | '.join(
        '%s %s %.2f' % (e.get('rank'), e.get('team_name'),
                        float(e.get('performance_index') or 0)) for e in entries))
    inactive = [e.get('team_name') for e in entries if e.get('commercially_inactive')]
    marked = [e.get('team_name') for e in entries if e.get('rank_marker')]
    if inactive or marked:
        print('commercially inactive: %s; marked on the leaderboard: %s'
              % (inactive, marked))
    print()
    print('| team | opening cash | revenue | charges | closing cash | '
          'opening == last closing | statement adds up |')
    print('|---|---:|---:|---:|---:|---|---|')
    for name, e in (chk.get('reconciliation') or {}).items():
        carry = e.get('cash_carried_between_rounds')
        carry_txt = ('--' if carry is None
                     else ('yes' if abs(carry) < 0.02
                           else '**no, %s**' % money(carry)))
        gap = e.get('page_income_statement_gap')
        gap_txt = ('yes' if gap is not None and abs(gap) < 0.02
                   else '**no, %s**' % money(gap))
        print('| %s | %s | %s | %s | %s | %s | %s |'
              % (name, money(e.get('cash_opening')), money(e.get('total_revenue')),
                 money(e.get('charges_on_the_statement')),
                 money(e.get('cash_closing')), carry_txt, gap_txt))
    fails = [c for c in chk.get('checks') or [] if c['outcome'] == 'fail']
    if fails:
        print('\nfailed cross-checks (%d):' % len(fails))
        for c in fails:
            print('  - %s -- %s' % (c['name'], c['detail'][:240]))
