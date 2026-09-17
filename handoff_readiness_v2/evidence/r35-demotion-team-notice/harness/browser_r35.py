"""R35 in a real browser: does the demoted team actually SEE the notice?

Two separate questions, deliberately not conflated — the same split the F3
pass used, because F3 was precisely a case where the API was right and no
screen rendered it:

  1. does the API carry the demotion notice for this team; and
  2. is there a screen the demoted team can reach that renders it?

The second is asked by navigating and reading the rendered DOM, not by
inspecting the component source.

Run as:  browser_r35.py <en|zh-CN>
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-ad31a78c64885fc47/handoff_readiness_v2/evidence'
    '/r35-demotion-team-notice')
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
TEAM = fixture['demoted_team_id']
ROUND = fixture['round_number']
STUDENT = fixture['demoted_student']
PASSWORD = fixture['password']

# The heading is the FRONTEND's (a locale key); the sentence is the SERVER'S.
# Both are asserted, because the bug class this closes is "the sentence exists
# and no screen shows it".
HEADING = {'en': 'Your placing in this round’s standings',
           'zh-CN': '贵公司在本回合的排名'}[LANG]
SENTENCE = {'en': 'placed below every firm that did',
            'zh-CN': '未参与竞争'}[LANG]
BAND_HEADING = {'en': 'Price adjustments applied when the round closed',
                'zh-CN': '回合截止时已应用的价格调整'}[LANG]

record = {'language': LANG, 'round': ROUND, 'steps': [], 'console': [],
          'network': [], 'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:900]})
    print(f'  {outcome.upper():<9} {name}'
          f'{" — " + str(detail)[:240] if detail else ""}', flush=True)


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f'{name}-{LANG}.png'
    page.screenshot(path=str(path), full_page=True)
    record['screenshots'].append(path.name)
    return path.name


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        # External fonts are unreachable from this sandbox and a pending font
        # request stops the page settling, so they are aborted deliberately.
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:400]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:220], 'status': r.status})
            if r.status >= 400 else None)

        page.goto(f'{BASE}/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', STUDENT)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        token = page.evaluate("() => localStorage.getItem('access_token')")
        step('the demoted team signs in', 'pass' if token else 'fail', STUDENT)
        if not token:
            browser.close()
            return finish()

        # ---- 1. what the API carries for this team ------------------------
        got = page.evaluate("""async (p) => {
            const t = localStorage.getItem('access_token');
            const r = await fetch(p, {headers: {Authorization: 'Bearer ' + t,
                'Accept-Language': localStorage.getItem('gs_language') || 'en'}});
            return {status: r.status, body: await r.json().catch(() => null)};
        }""", f'/api/games/{GAME}/teams/{TEAM}/results/round/{ROUND}/')
        body = got['body'] or {}
        notices = body.get('inactivity_notices')
        record['inactivity_notices'] = notices
        record['price_adjustments'] = body.get('price_adjustments')
        step('the results API carries a demotion notice',
             'pass' if notices else 'fail',
             f'HTTP {got["status"]}, {len(notices or [])} notice(s)')
        for n in (notices or []):
            step(f'  notice rank={n.get("rank")} '
                 f'index={n.get("performance_index")}', 'observed',
                 n.get('message'))
        step('the key is present even when reading it as a list',
             'pass' if 'inactivity_notices' in body else 'fail')

        # ---- 2. is there a screen the team can reach that renders it? ------
        reached = {}
        for path in (f'/games/{GAME}/teams/{TEAM}/results',
                     f'/games/{GAME}/teams/{TEAM}/results/{ROUND}'):
            page.goto(f'{BASE}{path}', wait_until='domcontentloaded')
            page.wait_for_timeout(4000)
            text = page.inner_text('body')
            reached[path] = {
                'url_after': page.url,
                'heading_on_screen': HEADING in text,
                'server_sentence_on_screen': SENTENCE in text,
                'band_notice_on_screen': BAND_HEADING in text,
            }
            shot(page, f'40-results{path.replace("/", "_")}')
        record['route_probe'] = reached
        rendered = [v for v in reached.values()
                    if v['heading_on_screen'] and v['server_sentence_on_screen']]
        step('R35 a reachable results screen renders the demotion notice',
             'pass' if rendered else 'fail',
             '; '.join(f'{k} -> heading={v["heading_on_screen"]} '
                       f'sentence={v["server_sentence_on_screen"]}'
                       for k, v in reached.items()))

        # The landing dashboard is where a team actually arrives after a round.
        page.goto(f'{BASE}/', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        text = page.inner_text('body')
        record['dashboard'] = {
            'heading_on_screen': HEADING in text,
            'server_sentence_on_screen': SENTENCE in text,
        }
        step('the landing dashboard shows it too',
             'pass' if HEADING in text and SENTENCE in text else 'fail')
        shot(page, '41-dashboard')

        # ---- 3. the exact rendered text, quoted from the DOM ---------------
        page.goto(f'{BASE}/games/{GAME}/teams/{TEAM}/results/{ROUND}',
                  wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        quoted = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.ant-alert').forEach(a => {
                out.push(a.innerText.replace(/\\s+/g, ' ').trim());
            });
            return out;
        }""")
        record['alerts_on_screen'] = quoted
        step('the sentence on screen is quoted from the DOM',
             'pass' if any(SENTENCE in q for q in quoted) else 'fail',
             ' || '.join(quoted)[:800])

        browser.close()
    return finish()


def finish():
    errors = [c for c in record['console'] if c['type'] == 'error']
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'console_errors': len(errors),
        'network_errors': len(record['network']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / f'browser-{LANG}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print(f'record: {out}')
    return 0 if record['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
