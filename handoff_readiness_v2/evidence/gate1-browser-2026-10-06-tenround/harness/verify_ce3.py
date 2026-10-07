"""Reproduce walkthrough 3's display and language defects on the repaired tree.

    verify_ce3.py <lang> <team-index> <round>

One signed-in browser, the real screens, one check per W-CE3 id. Every check
records what is on the screen now, not only whether it matched. Ids covered
here: 03 (the statement adds up ON THE PAGE), 05, 06, 07, 09, 10, 11, 12, 15,
17. The rest have their own drivers (02/13/16 the affordability probes, 14
`verify_round5_unlocks.py`, 18 `verify_operator_log_refusal.py`, 19/20
`instructor_endgame.py`, 01/04 `check_round.py`).
"""
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, modal_text, sign_in, sync_playwright,
                  visible_text)

LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[0]
R = Recorder('verify-ce3-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
ZH = LANG.startswith('zh')
HAN = re.compile(r'[一-鿿]')
# An English sentence: two or more ordinary lowercase words in a row.
EN_SENTENCE = re.compile(r'\b[A-Za-z][a-z]{2,}(?:\s+[a-z]{2,}){1,}\b')
MARKET_EN = ['North America', 'East Asia', 'Western Europe', 'Africa',
             'South America']


def goto(page, path, wait=5000):
    page.goto(BASE + path, wait_until='domcontentloaded')
    page.wait_for_timeout(wait)


def tab(page, *labels):
    for label in labels:
        t = page.locator('.ant-tabs-tab', has_text=label)
        if t.count():
            t.first.click()
            page.wait_for_timeout(2500)
            return label
    return None


def english_in(text):
    return sorted({m.group(0).strip() for m in EN_SENTENCE.finditer(text)
                   if len(m.group(0).strip()) >= 9})


# ---------------------------------------------------------------- 11 -------
def briefing(page, R):
    """W-CE3-11: the Strategic Briefing a student meets after signing in."""
    txt = modal_text(page) or ''
    R.observe('post_login_modal', txt[:2500])
    if txt:
        R.screen(page, 'v4-ce3-11-post-login-modal')
    api_txt = api(page, 'GET', '/api/games/%d/teams/%d/briefing/' % (GID, TID))
    R.observe('briefing_route', str(api_txt)[:1500])
    if not ZH:
        R.step('W-CE3-11 the briefing is shown (English reader)', 'observed',
               txt[:300] or 'no modal on this sign-in')
        return
    if not txt:
        R.step('W-CE3-11 the Strategic Briefing', 'observed',
               'no post-login modal appeared for this reader in this round')
        return
    han = len(HAN.findall(txt))
    leftovers = english_in(txt)
    R.step('W-CE3-11 the Strategic Briefing is Chinese for a Chinese team',
           'pass' if han > 20 and not leftovers else 'fail',
           '%d Chinese characters; English left: %s'
           % (han, json.dumps(leftovers, ensure_ascii=False)[:500]))


# ---------------------------------------------------------------- 05 -------
def marketing(page, R):
    goto(page, '/games/%d/teams/%d/decisions/marketing' % (GID, TID))
    R.screen(page, 'v4-ce3-05-marketing')
    ctx = api(page, 'GET',
              '/api/games/%d/teams/%d/context/marketing/' % (GID, TID))['body']
    pms = (ctx or {}).get('product_markets') or []
    # The marketing context nests the markets a product sells in under
    # `markets`; walkthrough 4's first pass grouped on a `market_id` the rows
    # do not carry and concluded, wrongly, that no market held exactly one
    # product. It does -- for every playing team.
    by_market = {}
    for pm in pms:
        for mk in (pm.get('markets') or []):
            key = mk.get('market__name') or mk.get('market_name') \
                or mk.get('market_id')
            by_market.setdefault(key, []).append(pm)
    single = [m for m, rows in by_market.items() if len(rows) == 1]
    R.observe('marketing_markets', {str(m): [r.get('product_name') for r in rows]
                                    for m, rows in by_market.items()})
    # Each market is a tab, and only the open one is rendered, so every tab is
    # opened in turn and the name is looked for in the ACTIVE pane. Walkthrough
    # 4's first pass read the whole page with one tab open and reported a
    # product as missing when its tab simply was not showing.
    names = []
    tabs = page.locator('.ant-tabs > .ant-tabs-nav .ant-tabs-tab')
    labels = [(tabs.nth(i).text_content() or '').strip()
              for i in range(tabs.count())]
    R.observe('marketing_market_tabs', labels)
    for i in range(max(tabs.count(), 1)):
        if tabs.count():
            tabs.nth(i).click()
            page.wait_for_timeout(2500)
        label = labels[i] if i < len(labels) else ''
        pane_text = ''
        pane = page.locator('.ant-tabs-tabpane-active').first
        if pane.count():
            pane_text = pane.inner_text()
        R.screen(page, 'v4-ce3-05-marketing-tab%d' % i, label)
        for m, rows in by_market.items():
            if len(rows) != 1:
                continue
            if str(m) not in label and str(m) not in pane_text:
                continue
            nm = rows[0].get('product_name')
            if nm:
                names.append({'market': str(m), 'product': nm,
                              'named_on_the_card': nm in pane_text})
    R.observe('single_product_markets', names)
    if not names:
        R.step('W-CE3-05 a market holding exactly one product', 'observed',
               'no market holds exactly one product for this team this round')
        return
    R.step('W-CE3-05 the Marketing page names the product in a market that '
           'holds exactly one',
           'pass' if all(n['named_on_the_card'] for n in names) else 'fail',
           json.dumps(names, ensure_ascii=False)[:500])


# ------------------------------------------------------------- 03 / 12 -----
def financial_reports(page, R):
    goto(page, '/games/%d/teams/%d/financial-reports' % (GID, TID), 6000)
    R.screen(page, 'v4-ce3-12-financial-reports')
    labels = page.locator('.ant-tabs-tab').all_text_contents()
    labels = [l.strip() for l in labels if l.strip()]
    R.observe('financial_report_tabs', labels)
    if ZH:
        english_tabs = [l for l in labels if not HAN.search(l)
                        and re.search(r'[A-Za-z]{3,}', l)]
        R.step('W-CE3-12 every Financial Reports tab label is in the reader\'s '
               'language', 'pass' if not english_tabs else 'fail',
               'English tab labels: %s' % json.dumps(english_tabs,
                                                     ensure_ascii=False))
    # The income statement, read off the page as a player reads it.
    tab(page, 'Income Statement', '利润表', '损益表')
    page.wait_for_timeout(2500)
    R.screen(page, 'v4-ce3-03-income-statement')
    table = page.evaluate("""() => {
        const t = document.querySelector('.ant-tabs-tabpane-active table');
        if (!t) return null;
        const head = Array.from(t.querySelectorAll('thead th'))
            .map(e => e.textContent.trim());
        const rows = Array.from(t.querySelectorAll('tbody tr')).map(tr =>
            Array.from(tr.querySelectorAll('td')).map(e => e.textContent.trim()));
        return {head, rows};
    }""")
    R.observe('income_statement_table', table)
    if not table or not table.get('rows'):
        R.step('W-CE3-03 the income statement renders', 'fail',
               'no table in the active pane')
        return

    def money(cell):
        """The value a printed cell carries, and how precise the print is.

        The page abbreviates -- `$11.6M`, `$378K` -- so the printed lines can
        only ever sum to the printed total within the precision of the print
        itself. Half of the last printed digit is the most any one cell can be
        out by, and the tolerance below is the sum of those, not a number
        chosen to make the check pass.
        """
        s = (cell or '').replace(',', '').replace('$', '').strip()
        neg = s.startswith('(') or s.startswith('-') or s.startswith('−')
        s = s.lstrip('(-−').rstrip(')')
        mult = 1.0
        if s.endswith('M'):
            mult, s = 1e6, s[:-1]
        elif s.endswith('K'):
            mult, s = 1e3, s[:-1]
        elif s.endswith('%'):
            return None, 0.0
        try:
            v = float(s) * mult
        except ValueError:
            return None, 0.0
        decimals = len(s.split('.')[1]) if '.' in s else 0
        precision = 0.5 * mult / (10 ** decimals)
        return (-v if neg else v), precision

    head, rows = table['head'], table['rows']
    wanted = None
    for row in rows:
        if row and re.search(r'R%d\b' % ROUND, row[0]):
            wanted = row
    wanted = wanted or rows[-1]
    cells = dict(zip(head, wanted))
    R.observe('income_statement_row_read', cells)
    # Which printed column is which is decided by the page's own line list.
    rows_js = (SCRATCH.parents[3] / 'frontend' / 'globalstrat-frontend' / 'src'
               / 'pages' / 'incomeStatementRows.js').read_text()
    keys = re.findall(r"\{\s*key:\s*'([A-Za-z0-9_]+)'", rows_js)
    ordered = [k for k in keys]
    read = [money(c) for c in wanted[1:]]
    pairs = {k: v for k, (v, _) in zip(ordered, read)}
    precisions = {k: p for k, (_, p) in zip(ordered, read)}
    R.observe('income_statement_by_key', pairs)
    skip = {'revenue', 'cogs', 'gross_profit', 'net_income', 'margin',
            'operating_income'}
    charges = [k for k in ordered if k not in skip]
    gp, ni = pairs.get('gross_profit'), pairs.get('net_income')
    if gp is None or ni is None:
        R.step('W-CE3-03 the printed statement adds up', 'fail',
               'gross profit or net income is not a number on the page: %s'
               % json.dumps(pairs))
        return
    total = gp - sum(pairs.get(k) or 0.0 for k in charges)
    gap = round(ni - total, 2)
    tol = (precisions.get('gross_profit', 0.0) + precisions.get('net_income', 0.0)
           + sum(precisions.get(k, 0.0) for k in charges))
    R.observe('printed_statement_gap', gap)
    R.observe('printed_statement_tolerance', tol)
    R.step('W-CE3-03 the printed lines sum to the printed net income',
           'pass' if abs(gap) <= tol else 'fail',
           'gross profit %.0f less the %d printed charges = %.0f; the page '
           'prints net income %.0f; gap %.0f against a rounding allowance of '
           '%.0f, which is half of the last printed digit of every cell added '
           'up (the served figures are checked exactly in check_round.py)'
           % (gp, len(charges), total, ni, gap, tol))


# ---------------------------------------------------------------- 09 -------
def supply_chain(page, R):
    for name, route in (('logistics', 'logistics'),
                        ('trade-finance', 'trade-finance'),
                        ('sourcing', 'sourcing'),
                        ('inventory', 'inventory')):
        goto(page, '/games/%d/teams/%d/decisions/%s' % (GID, TID, route), 6000)
        R.screen(page, 'v4-ce3-09-%s' % name)
        text = visible_text(page)
        R.observe('%s_text' % name, text[:1200])
        if ZH:
            found = [m for m in MARKET_EN if m in text]
            R.step('W-CE3-09 %s carries no English market name' % name,
                   'pass' if not found else 'fail',
                   'English market names on the page: %s' % ', '.join(found))


# ---------------------------------------------------------------- 10 -------
def platform_name(page, R):
    ctx = api(page, 'GET',
              '/api/games/%d/teams/%d/context/products/' % (GID, TID))['body']
    rd = api(page, 'GET',
             '/api/games/%d/teams/%d/context/rd/' % (GID, TID))['body']
    sc = api(page, 'GET', '/api/games/%d/teams/%d/dashboard/scorecard/?round=%d'
             % (GID, TID, ROUND))['body']
    names = {
        'products[].platform_name': [p.get('platform_name')
                                     for p in (ctx or {}).get('products') or []],
        'active_platforms[].name': [p.get('name') for p in
                                    (ctx or {}).get('active_platforms') or []],
        'rd.owned_platforms[].platform_name':
            [p.get('platform_name')
             for p in (rd or {}).get('owned_platforms') or []],
        'scorecard.platform': json.dumps(sc, ensure_ascii=False)[:400],
    }
    R.observe('platform_names', names)
    goto(page, '/games/%d/teams/%d/decisions/products' % (GID, TID))
    R.screen(page, 'v4-ce3-10-products')
    if not ZH:
        R.step('W-CE3-10 the generated platform name (English reader)',
               'observed', json.dumps(names, ensure_ascii=False)[:400])
        return
    flat = [n for k, v in names.items() if isinstance(v, list) for n in v if n]
    english = [n for n in flat if re.search(r'\b(Base Platform|Platform)\b', n)]
    R.step('W-CE3-10 no served platform name keeps its English suffix',
           'pass' if not english else 'fail',
           'served names: %s' % json.dumps(flat, ensure_ascii=False)[:400])


# ------------------------------------------------------------- 06 / 07 -----
def scorecard(page, R):
    goto(page, '/games/%d/teams/%d/results/%d' % (GID, TID, ROUND), 7000)
    R.screen(page, 'v4-ce3-06-results')
    res = api(page, 'GET', '/api/games/%d/teams/%d/results/round/%d/'
              % (GID, TID, ROUND))['body']
    blob = json.dumps(res, ensure_ascii=False)
    # The Strategic Scorecard is served as `coherence.breakdown`, one entry per
    # criterion, each with its own `feedback` sentence. Walkthrough 4's first
    # attempt looked for a top-level key of that name and found nothing, which
    # would have read as a defect; the shape is checked here so it cannot.
    breakdown = ((res or {}).get('coherence') or {}).get('breakdown') or {}
    R.observe('scorecard_keys', list(breakdown.keys()))
    crit = {k: [v.get('feedback')] for k, v in breakdown.items()
            if isinstance(v, dict) and v.get('feedback')}
    R.observe('scorecard_criteria', crit)
    lbl = tab(page, 'Strategic Scorecard', '战略记分卡', 'Scorecard', '记分卡')
    page.wait_for_timeout(2500)
    R.screen(page, 'v4-ce3-07-strategic-scorecard', lbl or 'tab not found')
    if not ZH:
        R.step('W-CE3-06/07 the scorecard (English reader)', 'observed',
               json.dumps(crit, ensure_ascii=False)[:400])
        return
    gov = crit.get('governance_tax') or []
    R.step('W-CE3-06 the governance/tax sentence is in the reader\'s language',
           'pass' if gov and all(HAN.search(s) for s in gov) else 'fail',
           'governance_tax=%s; its siblings=%s'
           % (json.dumps(gov, ensure_ascii=False),
              json.dumps({k: v for k, v in crit.items() if k != 'governance_tax'},
                         ensure_ascii=False)[:300]))
    # W-CE3-07: market names inside the scorecard's own detail tables.
    paths = []

    def walk_json(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk_json(v, path + '.' + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk_json(v, '%s[%d]' % (path, i))
        elif isinstance(node, str) and node in MARKET_EN:
            paths.append({'path': path, 'value': node})

    walk_json(res, 'results')
    R.observe('english_market_names_in_results', paths[:60])
    R.step('W-CE3-07 no English market name anywhere in the results payload',
           'pass' if not paths else 'fail',
           '%d English market names, e.g. %s'
           % (len(paths), json.dumps(paths[:6], ensure_ascii=False)))


# ---------------------------------------------------------------- 15 -------
def leaderboard(page, R):
    goto(page, '/games/%d/leaderboard' % GID, 6000)
    R.screen(page, 'v4-ce3-15-leaderboard')
    lb = api(page, 'GET', '/api/games/%d/leaderboard/round/%d/'
             % (GID, ROUND))['body']
    entries = ((lb or {}).get('rankings') or (lb or {}).get('leaderboard')
               or (lb or {}).get('entries') or [])
    R.observe('leaderboard_rows',
              [{k: e.get(k) for k in
                ('rank', 'team_name', 'performance_index', 'total_revenue',
                 'commercially_inactive', 'rank_marker')} for e in entries])
    R.observe('rank_rule_note', (lb or {}).get('rank_rule_note'))
    inverted = [(entries[i].get('team_name'), entries[i].get('performance_index'),
                 entries[j].get('team_name'), entries[j].get('performance_index'))
                for i in range(len(entries)) for j in range(i + 1, len(entries))
                if (entries[i].get('performance_index') or 0)
                < (entries[j].get('performance_index') or 0)]
    R.observe('rank_inversions', inverted)
    text = visible_text(page)
    R.observe('leaderboard_text', text[:1500])
    if not inverted:
        R.step('W-CE3-15 an inversion on the leaderboard', 'observed',
               'no team is ranked below a lower index this round, so there is '
               'nothing for the screen to explain')
        return
    marked = [e.get('team_name') for e in entries if e.get('rank_marker')]
    note = (lb or {}).get('rank_rule_note')
    on_screen = bool(note and note[:12] in text)
    R.step('W-CE3-15 the leaderboard explains the inversion on the screen',
           'pass' if marked and note and on_screen else 'fail',
           'inversions=%s marked=%s note=%r note_on_screen=%s'
           % (json.dumps(inverted, ensure_ascii=False)[:200], marked,
              (note or '')[:200], on_screen))


# ---------------------------------------------------------------- 17 -------
def communications(page, R):
    goto(page, '/games/%d/teams/%d/decisions/communications' % (GID, TID), 6000)
    R.screen(page, 'v4-ce3-17-communications')
    text = visible_text(page)
    R.observe('communications_text', text[:2000])
    keys = ['framework_grounding', 'risk_acknowledgment', 'stakeholder_awareness',
            'strategic_consistency', 'clarity_and_persuasion']
    pretty = [k.replace('_', ' ').title() for k in keys]
    raw = [k for k in keys if k in text]
    prettified = [p for p in pretty if p in text]
    R.observe('evaluation_criterion_labels',
              {'raw': raw, 'prettified_storage_keys': prettified})
    if not ZH:
        R.step('W-CE3-17 the evaluation criterion names (English reader)',
               'observed', 'raw=%s prettified=%s' % (raw, prettified))
        return
    R.step('W-CE3-17 no storage key is printed as a criterion name',
           'pass' if not raw and not prettified else 'fail',
           'raw keys on screen: %s; prettified keys on screen: %s'
           % (raw, prettified))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'), rec=R)
        R.step('%s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.wait_for_timeout(3500)
        briefing(page, R)
        for _ in range(6):
            if not modal_text(page):
                break
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if b.count():
                b.last.click()
                page.wait_for_timeout(1200)
            else:
                page.keyboard.press('Escape')
                page.wait_for_timeout(800)
        for fn in (marketing, financial_reports, supply_chain, platform_name,
                   scorecard, leaderboard, communications):
            try:
                fn(page, R)
            except Exception as exc:
                R.step('%s raised' % fn.__name__, 'fail', repr(exc)[:400])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
