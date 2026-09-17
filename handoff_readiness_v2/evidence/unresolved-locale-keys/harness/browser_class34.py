"""A representative sample of the 34 label-map keys, read from the live DOM.

Not all 34 are photographable, and the record says which are not. Of the 11
`common.*` StatusBadge labels, only `common.retired` has a live call site:
`StatusBadge` renders `{label || text}`, and the only two label-less call sites
are `PageHeader.jsx:13` -- which every caller feeds `locked` or `draft`, both
pre-existing keys -- and `ProductsPage.js:185`, which is hard-coded to
`retired`. The other ten are declared in the `textKeys` map with no caller that
reaches them today, so they are fixed as defence in depth and are NOT claimed
as observed.

What this drives:
  * login          -- the five demo-account labels, no authentication needed
  * StatusBadge    -- two pages: the retired-product badge (a NEW key) and the
                      page-header badge (a PRE-EXISTING key, recorded as such)
  * strategy_tools -- all three tabs: Porter's five forces, PESTLE, entry matrix

**No visual claim.** This sandbox has no CJK font, so Chinese renders in the
screenshots as missing-glyph boxes. The standard is string equality against the
rendered DOM.

Run as:  browser_class34.py <en|zh-CN>
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-ad31a78c64885fc47/handoff_readiness_v2/evidence'
    '/unresolved-locale-keys')
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
fx = json.loads((SCRATCH / 'fixture_classA.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stackA.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']
GAME, TEAM = fx['game_id'], fx['team_id']

EXPECT = {
    'en': {
        'logins': ['Team 1', 'Team 2', 'Team 3', 'Team 4', 'Team 5'],
        'retired': 'Retired',
        'header_badge': ['In Progress', 'Locked'],
        'forces': ['Threat of New Entrants', 'Supplier Power', 'Buyer Power',
                   'Threat of Substitutes', 'Competitive Rivalry'],
        'pestle': ['Political', 'Economic', 'Social', 'Technological',
                   'Legal', 'Environmental'],
        'entry': ['Market Size', 'Growth Rate', 'Entry Cost', 'Tariff Rate',
                  'Regulatory Difficulty', 'Competitive Intensity',
                  'Currency Risk'],
    },
    'zh-CN': {
        'logins': ['团队 1', '团队 2', '团队 3', '团队 4', '团队 5'],
        'retired': '已停产',
        'header_badge': ['进行中', '已锁定'],
        'forces': ['新进入者威胁', '供应商议价能力', '买方议价能力',
                   '替代品威胁', '现有竞争者竞争'],
        'pestle': ['政治', '经济', '社会', '技术', '法律', '环境'],
        'entry': ['市场规模', '增长率', '进入成本', '关税税率',
                  '监管难度', '竞争强度', '汇率风险'],
    },
}[LANG]

# Tabs are clicked BY TEXT, not by index. The first run clicked `.nth(i)` and
# the labels never appeared -- with no raw key on screen either, which means
# the click landed somewhere other than the panel under test. Text targeting
# fails loudly instead of silently opening the wrong tab, and it is what the
# earlier SWOT pass used successfully.
TABS = {
    'en': {'forces': "Porter's Five Forces", 'pestle': 'PESTLE Analysis',
           'entry': 'Market Entry Matrix'},
    'zh-CN': {'forces': '波特五力分析', 'pestle': 'PESTLE分析',
              'entry': '市场进入矩阵'},
}[LANG]

RAW_PREFIXES = ('common.', 'login.team_', 'strategy_tools.force_',
                'strategy_tools.pestle_', 'strategy_tools.entry_')

record = {'language': LANG, 'steps': [], 'console': [], 'network': [],
          'screenshots': [], 'observed': {},
          'visual_claim': 'none - no CJK font in this sandbox; the standard is '
                          'string equality against the rendered DOM'}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:600]})
    print('  %-9s %s%s' % (outcome.upper(), name,
                           ' -- ' + str(detail)[:200] if detail else ''))


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / ('%s-%s.png' % (name, LANG))
    page.screenshot(path=str(path), full_page=True)
    record['screenshots'].append(path.name)


def body_text(page):
    """textContent, NOT innerText.

    The design system uppercases some headers with CSS `text-transform`, and
    Chromium's innerText reflects that. The English entry-matrix columns failed
    on exactly that while the Chinese ones passed, because Chinese has no case
    -- the same trap as the operator-panel column headers. textContent is the
    authored string, which is what these assertions are about.
    """
    return page.evaluate("() => document.body.textContent")


def raw_keys_in(text):
    return [p for p in RAW_PREFIXES if p in text]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:250]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:200], 'status': r.status})
            if r.status >= 400 else None)

        # ---- 1. login.team_* : visible before authenticating ---------------
        # The demo-account block is guarded by `isDemo`, which LoginPage
        # defines as `location.pathname === '/demo'`. These five labels
        # therefore live on /demo, not /login. The first run drove /login and
        # saw neither the labels nor a raw key -- which is what an absent
        # block looks like, not an untranslated one.
        page.goto(BASE + '/demo', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(3500)
        login_text = body_text(page)
        # Capture what IS on the login page, so an absent demo block is
        # diagnosable rather than just a failed assertion.
        record['observed']['login_buttons'] = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('button').forEach(
                b => out.push(b.textContent.trim().slice(0, 60)));
            return out;
        }""")
        missing = [x for x in EXPECT['logins'] if x not in login_text]
        record['observed']['login_labels_missing'] = missing
        step('1 login: all five demo labels render',
             'pass' if not missing else 'fail',
             'missing: %s' % missing if missing else ', '.join(EXPECT['logins']))
        step('1 login: no raw key text', 'fail' if raw_keys_in(login_text)
             else 'pass', raw_keys_in(login_text))
        shot(page, '80-login-demo-labels')

        page.goto(BASE + '/login', wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        page.fill('input#username, input[name="username"]', fx['student'])
        page.fill('input#password, input[name="password"]', fx['password'])
        page.click('button[type="submit"]')
        page.wait_for_timeout(6000)
        if not page.evaluate("() => localStorage.getItem('access_token')"):
            step('sign in', 'fail', fx['student'])
            browser.close()
            return finish()
        step('sign in', 'pass', fx['student'])

        # ---- 2. StatusBadge, page one: the retired-product badge -----------
        reached = None
        for path in ('/games/%d/teams/%d/decisions/products' % (GAME, TEAM),
                     '/games/%d/teams/%d/products' % (GAME, TEAM)):
            page.goto(BASE + path, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            if 'status-badge' in page.content():
                reached = path
                break
        record['observed']['products_route'] = reached
        products_text = body_text(page)
        badges = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.status-badge').forEach(
                b => out.push(b.textContent.trim()));
            return out;
        }""")
        record['observed']['product_page_badges'] = badges
        step('2a StatusBadge page 1: the NEW key common.retired renders',
             'pass' if EXPECT['retired'] in badges else 'fail',
             'badges: %s' % badges)
        header = [b for b in badges if b in EXPECT['header_badge']]
        step('2b StatusBadge page 1: page-header badge renders '
             '(PRE-EXISTING key, recorded not claimed)',
             'pass' if header else 'observed', header or badges)
        step('2c products page: no raw key text',
             'fail' if raw_keys_in(products_text) else 'pass',
             raw_keys_in(products_text))
        shot(page, '81-products-retired-badge')

        # ---- 3. strategy_tools: all three label-map tabs -------------------
        page.goto('%s/games/%d/teams/%d/tools' % (BASE, GAME, TEAM),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(5500)
        record['observed']['tabs_present'] = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div.ant-tabs-tab').forEach(
                t => out.push(t.textContent.trim()));
            return out;
        }""")
        step('3 the tools page shows its tabs', 'observed',
             record['observed']['tabs_present'])

        for name, expected in (('forces', EXPECT['forces']),
                               ('pestle', EXPECT['pestle']),
                               ('entry', EXPECT['entry'])):
            label = TABS[name]
            try:
                page.click('div.ant-tabs-tab:has-text("%s")' % label,
                           timeout=20000)
                page.wait_for_timeout(4000)
            except Exception as exc:
                step('3 open the %s tab (%r)' % (name, label), 'fail',
                     str(exc)[:140])
                continue
            # Porter's and PESTLE mount their label cards only inside
            # `{market && (...)}`: a market must be chosen before the five
            # force cards or six PESTLE cards exist at all. The entry matrix
            # has no such gate. Not selecting one is why both panels came back
            # empty in BOTH languages with no raw key on screen -- the cards
            # were never mounted, rather than mounted and untranslated.
            if name in ('forces', 'pestle'):
                try:
                    # Scope to the ACTIVE pane. AntD keeps previously-opened
                    # tab panes mounted, so after choosing a market on the
                    # Porter's tab, `.ant-select-selector`.first resolves to
                    # that pane's now-hidden select and the click times out --
                    # which is exactly how the PESTLE step failed.
                    page.locator(
                        '.ant-tabs-tabpane-active .ant-select-selector'
                    ).first.click(timeout=10000)
                    page.wait_for_timeout(1200)
                    page.locator(
                        '.ant-select-dropdown:not(.ant-select-dropdown-hidden)'
                        ' .ant-select-item-option'
                    ).first.click(timeout=10000)
                    page.wait_for_timeout(3000)
                    record['observed']['%s_market_selected' % name] = True
                except Exception as exc:
                    step('3 %s: choose a market first' % name, 'fail',
                         str(exc)[:140])
            text = body_text(page)
            gone = [x for x in expected if x not in text]
            record['observed']['%s_missing' % name] = gone
            step('3 strategy_tools %s: every label renders' % name,
                 'pass' if not gone else 'fail',
                 'missing: %s' % gone if gone else ', '.join(expected))
            step('3 strategy_tools %s: no raw key text' % name,
                 'fail' if raw_keys_in(text) else 'pass', raw_keys_in(text))
            shot(page, '82-strategy-%s' % name)

        browser.close()
    return finish()


def finish():
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'observed_only': sum(1 for s in record['steps']
                             if s['outcome'] == 'observed'),
        'console_errors': len([c for c in record['console']
                               if c['type'] == 'error']),
        'network_errors': len(record['network']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / ('browser-label-maps-%s.json' % LANG)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print('record: %s' % out)
    return 0 if record['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
