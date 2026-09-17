"""Drive all three Class A screens, in one language, and read the rendered DOM.

Each of the three defects rendered a raw translation key to a user. So each is
asserted the same way, twice over: the raw key must be ABSENT, and the authored
sentence must be PRESENT. Asserting only the sentence would pass on a page that
happened to contain it; asserting only the key's absence would pass on a page
that failed to render at all.

  1. topbar.over                     -- the over-budget chip, in the app chrome
  2. communications_page.max_words   -- the word-limit tag, round 2 assignment
  3. strategy_tools.swot_placeholder -- the SWOT textarea placeholder, read
     from the placeholder ATTRIBUTE rather than body text, plus the four
     quadrant labels it interpolates

Run as:  browser_classA.py <en|zh-CN>
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
WORDS = fx['assignment']['word_limit']

EXPECT = {
    'en': {
        'over': 'over budget',
        'words': 'Maximum %d words' % WORDS,
        'swot_tab': 'SWOT Analysis',
        'quadrants': ['Strengths', 'Weaknesses', 'Opportunities', 'Threats'],
        'placeholder': 'List your strengths here, one per line.',
    },
    'zh-CN': {
        'over': '超出预算',
        'words': '最多 %d 字' % WORDS,
        'swot_tab': 'SWOT分析',
        'quadrants': ['优势', '劣势', '机会', '威胁'],
        'placeholder': '在此列出贵公司的优势，每行一项。',
    },
}[LANG]

RAW = {'over': 'topbar.over',
       'words': 'communications_page.max_words',
       'swot': 'strategy_tools.swot'}

record = {'language': LANG, 'steps': [], 'console': [], 'network': [],
          'screenshots': [], 'observed': {}}


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


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:250]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:200], 'status': r.status})
            if r.status >= 400 else None)

        page.goto(BASE + '/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', fx['student'])
        page.fill('input#password, input[name="password"]', fx['password'])
        page.click('button[type="submit"]')
        page.wait_for_timeout(6000)
        if not page.evaluate("() => localStorage.getItem('access_token')"):
            step('sign in', 'fail', fx['student'])
            browser.close()
            return finish()
        step('sign in', 'pass', fx['student'])

        # ---- 1. topbar.over: the over-budget chip -------------------------
        page.goto(BASE + '/', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        chrome = page.inner_text('body')
        record['observed']['topbar_chip'] = page.evaluate("""() => {
            const el = document.querySelector('.ds-topbar-budget-chip');
            return el ? el.innerText.replace(/\\s+/g, ' ').trim() : null;
        }""")
        step('1 topbar.over: raw key absent',
             'fail' if RAW['over'] in chrome else 'pass')
        step('1 topbar.over: chip reads the sentence',
             'pass' if EXPECT['over'] in chrome else 'fail',
             record['observed']['topbar_chip'])
        shot(page, '60-topbar-over-budget')

        # ---- 2. communications_page.max_words ------------------------------
        page.goto('%s/games/%d/teams/%d/decisions/communications'
                  % (BASE, GAME, TEAM), wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        comms = page.inner_text('body')
        record['observed']['word_limit_tag'] = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.ant-tag').forEach(t => out.push(t.innerText.trim()));
            return out;
        }""")
        step('2 max_words: raw key absent',
             'fail' if RAW['words'] in comms else 'pass')
        step('2 max_words: tag reads the sentence',
             'pass' if EXPECT['words'] in comms else 'fail',
             record['observed']['word_limit_tag'])
        shot(page, '61-communications-word-limit')

        # ---- 3. the SWOT panel --------------------------------------------
        page.goto('%s/games/%d/teams/%d/tools' % (BASE, GAME, TEAM),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        try:
            page.click('div.ant-tabs-tab:has-text("%s")' % EXPECT['swot_tab'],
                       timeout=15000)
        except Exception as exc:
            step('3 open the SWOT tab', 'fail', str(exc)[:160])
        page.wait_for_timeout(3000)
        swot = page.inner_text('body')
        placeholders = page.evaluate("""() => Array.from(
            document.querySelectorAll('textarea')).map(t => t.placeholder)""")
        record['observed']['swot_placeholders'] = placeholders
        record['observed']['swot_titles'] = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.ant-card-head-title').forEach(
                t => out.push(t.innerText.trim()));
            return out;
        }""")
        step('3 swot: no strategy_tools.swot* key on screen',
             'fail' if RAW['swot'] in swot else 'pass')
        missing_q = [q for q in EXPECT['quadrants'] if q not in swot]
        step('3 swot: all four quadrant labels render',
             'pass' if not missing_q else 'fail',
             'missing: %s' % missing_q if missing_q
             else ', '.join(EXPECT['quadrants']))
        step('3 swot: placeholder reads the sentence with the quadrant',
             'pass' if any(EXPECT['placeholder'] == ph for ph in placeholders)
             else 'fail', placeholders[:4])
        shot(page, '62-swot-placeholder')

        browser.close()
    return finish()


def finish():
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'console_errors': len([c for c in record['console']
                               if c['type'] == 'error']),
        'network_errors': len(record['network']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / ('browser-class-a-%s.json' % LANG)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print('record: %s' % out)
    return 0 if record['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
