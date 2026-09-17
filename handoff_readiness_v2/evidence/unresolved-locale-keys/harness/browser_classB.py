"""Class B: does the operator events panel read Chinese for a Chinese instructor?

The defect was invisible in English by construction -- a hard-coded `t()`
fallback renders the English word whether or not the key exists -- so the only
thing that proves the fix is reading the RENDERED labels in each language.

**No visual claim is made.** This sandbox has no CJK font, so Chinese appears
in screenshots as missing-glyph boxes. The standard used here is string
equality against the rendered DOM: the label text pulled out of the live page,
compared to the authored catalogue string. Screenshots are kept as a record of
layout, not as evidence of the glyphs.

Run as:  browser_classB.py <en|zh-CN>
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
INSTRUCTOR = 'classa_instructor'

# Exactly the strings authored in the catalogues.
EXPECT = {
    'en': {
        'tab': 'Operator Log',
        'card': 'Operator actions',
        'filter': 'All outcomes',
        'options': ['Committed', 'Refused'],
        'columns': ['Time (server)', 'Actor', 'Action', 'Outcome', 'Round',
                    'Reason', 'Before → after', 'Request ID'],
        'supply_chain': 'Supply Chain',
    },
    'zh-CN': {
        'tab': '操作日志',
        'card': '操作记录',
        'filter': '全部结果',
        'options': ['已执行', '已拒绝'],
        'columns': ['时间（服务器）', '操作人', '操作', '结果', '回合',
                    '原因', '变更前 → 变更后', '请求 ID'],
        'supply_chain': '供应链',
    },
}[LANG]

record = {'language': LANG, 'steps': [], 'console': [], 'network': [],
          'screenshots': [], 'observed': {},
          'visual_claim': 'none - no CJK font in this sandbox; the standard '
                          'here is string equality against the rendered DOM'}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:600]})
    print('  %-9s %s%s' % (outcome.upper(), name,
                           ' -- ' + str(detail)[:220] if detail else ''))


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

        page.goto(BASE + '/instructor/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', INSTRUCTOR)
        page.fill('input#password, input[name="password"]', fx['password'])
        page.click('button[type="submit"]')
        page.wait_for_timeout(7000)
        if not page.evaluate("() => localStorage.getItem('access_token')"):
            step('instructor signs in', 'fail', INSTRUCTOR)
            browser.close()
            return finish()
        step('instructor signs in', 'pass', '%s (%s)' % (INSTRUCTOR, page.url))
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(7000)

        body = page.inner_text('body')
        record['observed']['tab_present'] = EXPECT['tab'] in body
        step('the Operator Log tab label is translated',
             'pass' if EXPECT['tab'] in body else 'fail', EXPECT['tab'])
        step('the Supply Chain tab label is translated',
             'pass' if EXPECT['supply_chain'] in body else 'fail',
             EXPECT['supply_chain'])

        # Open the Operator Log tab.
        try:
            page.click('div.ant-tabs-tab:has-text("%s")' % EXPECT['tab'],
                       timeout=20000)
            page.wait_for_timeout(3500)
        except Exception as exc:
            step('open the Operator Log tab', 'fail', str(exc)[:160])
            browser.close()
            return finish()

        panel = page.inner_text('body')
        record['observed']['card_title'] = EXPECT['card'] in panel
        step('the panel card title is translated',
             'pass' if EXPECT['card'] in panel else 'fail', EXPECT['card'])
        step('the outcome filter label is translated',
             'pass' if EXPECT['filter'] in panel else 'fail', EXPECT['filter'])

        # The table mounts asynchronously behind a loading spinner. Query it
        # before it mounts and the header list is simply empty, which reads as
        # "not translated" when the real cause is that nothing is there yet.
        try:
            page.wait_for_selector('th.ant-table-cell', timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        # textContent, NOT innerText. The design system uppercases table
        # headers with CSS `text-transform`, and Chromium's innerText reflects
        # that, so innerText returns 'TIME (SERVER)' where the catalogue says
        # 'Time (server)'. textContent is the authored string, which is what
        # this assertion is about; the uppercase is presentation. Chinese has
        # no case, so this only ever affected the English run.
        probe = page.evaluate("""() => {
            const out = {text: [], rendered: []};
            document.querySelectorAll('th.ant-table-cell').forEach(h => {
                out.text.push(h.textContent.trim());
                out.rendered.push(h.innerText.trim());
            });
            return out;
        }""")
        headers = probe['text']
        record['observed']['column_headers'] = headers
        record['observed']['column_headers_as_rendered'] = probe['rendered']
        missing = [c for c in EXPECT['columns'] if c not in headers]
        step('every column header is translated',
             'pass' if not missing else 'fail',
             'missing: %s' % missing if missing else ', '.join(headers))

        # The two filter options only exist once the select is opened.
        try:
            page.click('.ant-select-selector', timeout=10000)
            page.wait_for_timeout(1500)
            options = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('.ant-select-item-option-content')
                    .forEach(o => out.push(o.innerText.trim()));
                return out;
            }""")
        except Exception:
            options = []
        record['observed']['filter_options'] = options
        missing_opts = [o for o in EXPECT['options'] if o not in options]
        step('both outcome options are translated',
             'pass' if not missing_opts else 'fail',
             'missing: %s' % missing_opts if missing_opts else options)

        # No key text anywhere on the panel.
        leaked = [k for k in ('instructor.operator_events', 'instructor.actor',
                              'instructor.action', 'instructor.outcome',
                              'instructor.reason', 'instructor.before_after',
                              'instructor.request_id', 'instructor.time_server',
                              'instructor.all_outcomes', 'instructor.committed',
                              'instructor.rejected', 'instructor.operator_log',
                              'instructor.supply_chain')
                  if k in panel]
        record['observed']['leaked_keys'] = leaked
        step('no instructor.* key text on screen',
             'fail' if leaked else 'pass', leaked)

        SHOTS.mkdir(parents=True, exist_ok=True)
        path = SHOTS / ('70-operator-log-%s.png' % LANG)
        page.screenshot(path=str(path), full_page=True)
        record['screenshots'].append(path.name)

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
    out = EVIDENCE / ('browser-class-b-%s.json' % LANG)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print('record: %s' % out)
    return 0 if record['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
