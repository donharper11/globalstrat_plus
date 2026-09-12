"""CRV2-13 item 4 and the results half of item 5, after the round is processed.

Two separate questions, deliberately not conflated:

  1. does the API carry the adjustment notices -- what was submitted, what was
     applied, and the rule; and
  2. is there a screen a student can reach that renders them?

The second is asked by navigating, because `price_adjustments` appears in
exactly one component and a component nothing routes to is not a screen.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-a0ae8bfea94e98414/handoff_readiness_v2/evidence/bug-sweep'
    '/frontend-verification-2026-09-12')
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 1
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
TEAM = fixture['team_a_id']
STUDENT = fixture['students'][0]['username']
PASSWORD = fixture['password']

record = {'language': LANG, 'round': ROUND, 'steps': [], 'console': [],
          'network': [], 'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:900]})
    print(f'  {outcome.upper():<13} {name}'
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
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:400]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:220], 'status': r.status}) if r.status >= 400 else None)

        page.goto(f'{BASE}/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', STUDENT)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        token = page.evaluate("() => localStorage.getItem('access_token')")
        step('student signed in', 'pass' if token else 'fail')
        if not token:
            browser.close()
            return finish()

        # ---- 1. what the API carries -------------------------------------
        got = page.evaluate("""async (p) => {
            const t = localStorage.getItem('access_token');
            const r = await fetch(p, {headers: {Authorization: 'Bearer ' + t,
                                    'Accept-Language': localStorage.getItem('gs_language') || 'en'}});
            return {status: r.status, body: await r.json().catch(() => null)};
        }""", f'/api/games/{GAME}/teams/{TEAM}/results/round/{ROUND}/')
        adjustments = ((got['body'] or {}).get('price_adjustments') or [])
        record['price_adjustments'] = adjustments
        record['results_status'] = got['status']
        step('results API returns price adjustments',
             'pass' if adjustments else 'fail',
             f'HTTP {got["status"]}, {len(adjustments)} notice(s)')
        for a in adjustments:
            step(f'  notice: {a.get("product_name")} / {a.get("market")}',
                 'observed',
                 f'submitted={a.get("submitted_price")} '
                 f'applied={a.get("applied_price")} rule={a.get("rule")} :: '
                 f'{a.get("message")}')

        rules = {a.get('rule') for a in adjustments}
        step('ITEM 4 a notice names submitted, applied and the rule',
             'pass' if any(a.get('rule') and a.get('message')
                           for a in adjustments) else 'fail',
             f'rules present: {sorted(r for r in rules if r)}')
        step('ITEM 5 the unpriceable product is reported not-for-sale',
             'pass' if 'price_band.unpriced_not_offered_for_sale' in rules
             else 'fail',
             'notice present' if
             'price_band.unpriced_not_offered_for_sale' in rules
             else 'no not-for-sale notice in the payload')

        # ---- 2. is there a screen that renders them? ----------------------
        # `price_adjustments` is rendered only by ResultsPage. Try the routes a
        # student could plausibly reach and record what actually appears.
        reached = {}
        for path in (f'/games/{GAME}/teams/{TEAM}/results',
                     f'/games/{GAME}/teams/{TEAM}/results/round/{ROUND}',
                     '/results'):
            page.goto(f'{BASE}{path}', wait_until='domcontentloaded')
            page.wait_for_timeout(3500)
            text = page.inner_text('body')
            marker = any(s in text for s in (
                'Price adjustments applied when the round closed',
                '回合截止时已应用的价格调整'))
            reached[path] = {'url_after': page.url,
                             'shows_adjustments': marker,
                             'text': text[:300].replace('\n', ' / ')}
            shot(page, f'30-results-route{path.replace("/", "_")}')
        record['route_probe'] = reached
        any_screen = any(v['shows_adjustments'] for v in reached.values())
        step('ITEM 4/5 a student-reachable screen renders the notice',
             'pass' if any_screen else 'fail',
             '; '.join(f'{k} -> {v["url_after"].split(BASE)[-1]} '
                       f'(notice: {v["shows_adjustments"]})'
                       for k, v in reached.items()))

        # The dashboard is where a student actually lands after a round.
        page.goto(f'{BASE}/', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        text = page.inner_text('body')
        on_dash = any(s in text for s in (
            'Price adjustments applied when the round closed',
            '回合截止时已应用的价格调整'))
        record['dashboard_shows_adjustments'] = on_dash
        step('ITEM 4 the dashboard shows the adjustment notice',
             'pass' if on_dash else 'fail',
             'not present on the landing dashboard' if not on_dash else '')
        shot(page, '31-dashboard-after-processing')

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
    out = EVIDENCE / f'student-results-{LANG}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print(f'record: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
