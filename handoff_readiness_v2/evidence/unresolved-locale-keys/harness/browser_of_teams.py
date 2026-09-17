"""Does the results screen still say `results_page.of_teams`, or a sentence?

The defect was visible, not theoretical: the Leaderboard Position tile rendered
`#3 results_page.of_teams` in English and in Chinese. So the fix is proved the
same way it was found -- by reading the rendered DOM, in both languages.

Three things are asserted, the third because a fix that quietly breaks the
neighbouring feature is not a fix:

  1. the raw key `results_page.of_teams` appears NOWHERE on the page;
  2. the tile reads the authored sentence, with the count interpolated;
  3. R35's demotion notice still renders on the same screen.

Run as:  browser_of_teams.py <en|zh-CN>
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
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']
GAME = fixture['game_id']
TEAM = fixture['demoted_team_id']
ROUND = fixture['round_number']
STUDENT = fixture['demoted_student']
PASSWORD = fixture['password']
TEAMS = len(fixture['students']) // 3  # three members a team in this fixture

RAW_KEY = 'results_page.of_teams'
EXPECTED = {'en': 'of %d teams' % TEAMS,
            'zh-CN': '共 %d 支队伍' % TEAMS}[LANG]
# R35's notice, so this pass also proves the neighbouring feature still renders.
R35_SENTENCE = {'en': 'placed below every firm that did',
                'zh-CN': '未参与竞争'}[LANG]

record = {'language': LANG, 'expected_suffix': EXPECTED, 'steps': [],
          'console': [], 'network': [], 'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:900]})
    print('  %-9s %s%s' % (outcome.upper(), name,
                           ' -- ' + str(detail)[:220] if detail else ''))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:300]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:200], 'status': r.status})
            if r.status >= 400 else None)

        page.goto(BASE + '/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', STUDENT)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        token = page.evaluate("() => localStorage.getItem('access_token')")
        step('a student signs in', 'pass' if token else 'fail', STUDENT)
        if not token:
            browser.close()
            return finish()

        page.goto('%s/games/%d/teams/%d/results/%d' % (BASE, GAME, TEAM, ROUND),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(4500)
        text = page.inner_text('body')

        record['raw_key_on_screen'] = RAW_KEY in text
        step('the raw key is gone from the screen',
             'fail' if RAW_KEY in text else 'pass',
             'still present' if RAW_KEY in text else RAW_KEY)

        record['sentence_on_screen'] = EXPECTED in text
        step('the tile reads the authored sentence',
             'pass' if EXPECTED in text else 'fail', EXPECTED)

        record['r35_still_renders'] = R35_SENTENCE in text
        step('R35 demotion notice still renders beside it',
             'pass' if R35_SENTENCE in text else 'fail')

        # Quote the tile itself out of the DOM, not the whole page.
        tile = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.ant-statistic').forEach(s => {
                const t = s.innerText.replace(/\\s+/g, ' ').trim();
                if (/#/.test(t)) out.push(t);
            });
            return out;
        }""")
        record['leaderboard_tile'] = tile
        step('the tile text, quoted from the DOM',
             'pass' if any(EXPECTED in t for t in tile) else 'fail',
             ' || '.join(tile)[:300])

        SHOTS.mkdir(parents=True, exist_ok=True)
        shot = SHOTS / ('50-results-of-teams-%s.png' % LANG)
        page.screenshot(path=str(shot), full_page=True)
        record['screenshots'].append(shot.name)

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
    out = EVIDENCE / ('browser-of-teams-%s.json' % LANG)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print('record: %s' % out)
    return 0 if record['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
