"""Drive the three open interface defects in one language, and read the DOM.

Each defect is asserted twice over, the way the CRV2-13 locale pass settled on:
the raw translation key must be ABSENT, and the authored sentence must be
PRESENT. Asserting only the sentence would pass on a page that happened to
contain it; asserting only the key's absence would pass on a page that failed
to render at all.

  V2-064  a student's edit is refused while an operator holds the game lock.
          The lock is held for real, by `lock_game_for_lifecycle`, from a
          separate process -- see hold_lock.py -- so the 409 the student
          receives is the product's own refusal and not a stub.
  V2-105  the Extend Deadline confirmation names the game; the pause toast
          comes from the catalogue.
  V2-080  the operator-actions panel's column headers come from the catalogue.

NO VISUAL CLAIM IS MADE ABOUT CHINESE GLYPHS. This sandbox has no CJK font, so
the zh-CN screenshots show missing-glyph boxes. The standard here is exact
string equality against the rendered DOM, and the comparisons below use
textContent -- never innerText, which reflects the design system's CSS
`text-transform` and has produced a false failure on this programme before.

Run as:  browser_defects.py <en|zh-CN>
"""
import json
import pathlib
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = SCRATCH.parent
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
fx = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']
GAME, TEAM, GAME_NAME = fx['game_id'], fx['team_id'], fx['game_name']

EXPECT = {
    'en': {
        'not_saved': 'Your last change was not saved',
        'lifecycle': 'An instructor is changing this round right now, so '
                     'nothing was saved. Your edit is still on screen and '
                     'will be sent again in a moment.',
        'retry_now': 'Retry now',
        'extend_title': 'Extend round deadline — ' + GAME_NAME,
        'paused': 'Game paused',
        'operator_headers': ['Time (server)', 'Actor', 'Action', 'Outcome',
                             'Round', 'Reason', 'Before → after',
                             'Request ID'],
        # The TAB is instructor.operator_log; the CARD inside it is
        # instructor.operator_events. Two different keys, both asserted.
        'operator_tab': 'Operator Log',
        'operator_card': 'Operator actions',
        'control_tab': 'Game Control',
        'extend_button': 'Extend Deadline',
        'pause_button': 'Pause Game',
    },
    'zh-CN': {
        'not_saved': '您的最近一次修改未能保存',
        'lifecycle': '教师正在调整本回合，'
                     '因此未保存任何内容。'
                     '您的修改仍在屏幕上，'
                     '稍后将自动重新提交。',
        'retry_now': '立即重试',
        'extend_title': '延长回合截止时间 — ' + GAME_NAME,
        'paused': '游戏已暂停',
        'operator_headers': ['时间（服务器）',
                             '操作人', '操作', '结果',
                             '回合', '原因',
                             '变更前 → 变更后',
                             '请求 ID'],
        'operator_tab': '操作日志',
        'operator_card': '操作记录',
        'control_tab': '游戏控制',
        'extend_button': '延长截止时间',
        'pause_button': '暂停游戏',
    },
}[LANG]

# Any of these appearing on screen means a key rendered instead of a sentence.
RAW_PREFIXES = ['decision_save.', 'instructor.extend_deadline',
                'instructor.game_paused', 'game_status.not_saved']

record = {'language': LANG, 'game': GAME_NAME, 'steps': [], 'console': [],
          'network': [], 'screenshots': [], 'observed': {},
          'visual_claim': 'none - no CJK font in this sandbox; the standard '
                          'here is string equality against the rendered DOM '
                          '(textContent, not innerText)'}


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
    """textContent, NOT innerText -- see the module docstring."""
    return page.evaluate("() => document.body.textContent")


def instrument(page):
    page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
    page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
    page.on('console', lambda m: (
        record['console'].append({'type': m.type, 'text': m.text[:250]})
        if m.type in ('error', 'warning') else None))
    page.on('response', lambda r: record['network'].append(
        {'url': r.url[:200], 'status': r.status}) if r.status >= 400 else None)


def sign_in(page, route, username):
    page.goto(BASE + route, wait_until='domcontentloaded')
    page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
    page.reload(wait_until='domcontentloaded')
    page.wait_for_timeout(2500)
    page.fill('input#username, input[name="username"]', username)
    page.fill('input#password, input[name="password"]', fx['password'])
    page.click('button[type="submit"]')
    page.wait_for_timeout(7000)
    return bool(page.evaluate("() => localStorage.getItem('access_token')"))


def no_raw_keys(text):
    return [p for p in RAW_PREFIXES if p in text]


# --------------------------------------------------------------------------
# V2-064
# --------------------------------------------------------------------------
def drive_student(page):
    if not sign_in(page, '/login', fx['student']):
        step('V2-064 student signs in', 'fail', fx['student'])
        return
    step('V2-064 student signs in', 'pass', fx['student'])

    page.goto('%s/games/%d/teams/%d/decisions/finance' % (BASE, GAME, TEAM),
              wait_until='domcontentloaded')
    page.wait_for_timeout(6000)
    shot(page, '10-finance-before-refusal')

    before = body_text(page)
    step('V2-064 no refusal notice before the operator acts',
         'pass' if EXPECT['not_saved'] not in before else 'fail')

    # Hold the SAME lock every exclusive operator action takes.
    holder = subprocess.Popen(
        # Six seconds: long enough to refuse the edit and to let the first
        # automatic retries be refused too, short enough that a later retry
        # lands after the operator is done. The retry budget is 2s/5s/10s, so
        # a lock held longer than ~17s exhausts it and the student is left
        # with the manual Retry -- correct, but not what this step observes.
        [sys.executable, str(SCRATCH / 'hold_lock.py'), str(GAME), '6'],
        cwd=str(SCRATCH), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=_django_env())
    held = holder.stdout.readline().strip()
    if not held.startswith('HELD'):
        step('V2-064 an operator action holds the game lock', 'fail', held)
        holder.kill()
        return
    step('V2-064 an operator action holds the game lock', 'pass', held)

    typed = page.evaluate("""() => {
        const el = document.querySelector('input.ant-input, input.ant-input-number-input');
        return el ? (el.className || 'found') : null;
    }""")
    if not typed:
        step('V2-064 the student edits a decision field', 'fail',
             'no editable input found on the finance screen')
        holder.wait()
        return
    box = page.locator('input.ant-input, input.ant-input-number-input').first
    box.click()
    box.fill('1234567')
    box.press('Enter')
    page.wait_for_timeout(1000)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    step('V2-064 the student edits a decision field', 'pass', typed)

    # The page debounces ~700ms; the refusal then has to reach the screen.
    page.wait_for_timeout(6000)
    during = body_text(page)
    record['observed']['alert_during_lock'] = page.evaluate("""() => {
        const el = document.querySelector('.ant-alert-error');
        return el ? el.textContent.replace(/\\s+/g, ' ').trim() : null;
    }""")
    shot(page, '11-finance-refusal-shown')

    leaked = no_raw_keys(during)
    step('V2-064 no raw translation key on screen',
         'pass' if not leaked else 'fail', leaked)
    step('V2-064 the student is told the edit was NOT saved',
         'pass' if EXPECT['not_saved'] in during else 'fail',
         record['observed']['alert_during_lock'])
    step('V2-064 the notice names the operator action, in this language',
         'pass' if EXPECT['lifecycle'] in during else 'fail')
    step('V2-064 a retry control is offered',
         'pass' if EXPECT['retry_now'] in during else 'fail')
    step('V2-064 the status indicator does not claim a save',
         'pass' if 'game_status.saved' not in during else 'fail')

    # Let the lock go, then let the automatic retry land.
    holder.wait(timeout=60)
    page.wait_for_timeout(14000)
    after = body_text(page)
    record['observed']['alert_after_release'] = page.evaluate("""() => {
        const el = document.querySelector('.ant-alert-error');
        return el ? el.textContent.replace(/\\s+/g, ' ').trim() : null;
    }""")
    shot(page, '12-finance-after-retry')
    step('V2-064 the edit is retried and the notice clears',
         'pass' if EXPECT['not_saved'] not in after else 'fail',
         record['observed']['alert_after_release'])

    # Independent of the screen: the refused write really was re-sent. Each
    # refusal is a separate 409 on the decision route, so more than one means
    # the edit was retried rather than dropped.
    refusals = [n for n in record['network']
                if n['status'] == 409 and '/decisions/' in n['url']]
    record['observed']['decision_refusals'] = len(refusals)
    step('V2-064 the refused write was re-sent, not dropped',
         'pass' if len(refusals) > 1 else 'fail',
         '%d refusals on the decision route: one first attempt and %d '
         'automatic retries' % (len(refusals), max(len(refusals) - 1, 0)))


# --------------------------------------------------------------------------
# V2-105 and V2-080
# --------------------------------------------------------------------------
def drive_instructor(page):
    if not sign_in(page, '/instructor/login', fx['instructor']):
        step('V2-105 instructor signs in', 'fail', fx['instructor'])
        return
    step('V2-105 instructor signs in', 'pass', fx['instructor'])

    page.goto(BASE + '/instructor', wait_until='domcontentloaded')
    page.wait_for_timeout(8000)
    shot(page, '20-instructor-dashboard')

    # The lifecycle controls live on the Game Control tab. Clicked by its
    # localized label rather than by index: picking tabs by position has
    # silently opened the wrong one on this programme before.
    control = page.locator('div.ant-tabs-tab', has_text=EXPECT['control_tab'])
    if control.count() == 0:
        step('V2-105 reach the Game Control tab', 'fail',
             'tab %r not found' % EXPECT['control_tab'])
    else:
        control.first.click()
        page.wait_for_timeout(5000)
        step('V2-105 reach the Game Control tab', 'pass',
             EXPECT['control_tab'])
    shot(page, '20b-game-control-tab')

    found = page.locator('button:has-text("%s")' % EXPECT['extend_button']).count()
    if not found:
        step('V2-105 reach the Extend Deadline control', 'fail',
             'button not on screen; dashboard state: '
             + body_text(page)[:300])
    else:
        step('V2-105 reach the Extend Deadline control', 'pass',
             '%d button(s)' % found)
        page.locator('button:has-text("%s")' % EXPECT['extend_button']).first.click()
        page.wait_for_timeout(2500)
        title = page.evaluate("""() => {
            const el = document.querySelector('.ant-modal-title');
            return el ? el.textContent.trim() : null;
        }""")
        record['observed']['extend_modal_title'] = title
        shot(page, '21-extend-deadline-modal')
        step('V2-105 the Extend Deadline confirmation names the game',
             'pass' if title == EXPECT['extend_title'] else 'fail',
             'got %r, wanted %r' % (title, EXPECT['extend_title']))
        step('V2-105 the modal title is not a raw key',
             'pass' if title and 'instructor.' not in title else 'fail', title)
        page.keyboard.press('Escape')
        page.wait_for_timeout(1500)

    # The pause toast, from the catalogue rather than hardcoded English.
    pause = page.locator('button:has-text("%s")' % EXPECT['pause_button'])
    if pause.count() == 0:
        step('V2-105 the pause toast comes from the catalogue', 'fail',
             'pause button not on screen')
    else:
        pause.first.click()
        page.wait_for_timeout(1200)
        ok = page.locator(
            '.ant-popover:not(.ant-popover-hidden) button.ant-btn-primary')
        if ok.count():
            ok.first.click()
        # antd's `message` dismisses itself after about three seconds, so the
        # toast is POLLED rather than read once at a fixed delay: reading it
        # at 3.5s caught it on one run and missed it on the next, which is a
        # property of the harness and not of the product.
        toast = None
        for _ in range(40):
            toast = page.evaluate("""() => {
                const el = document.querySelector('.ant-message-notice-content');
                return el ? el.textContent.trim() : null;
            }""")
            if toast:
                break
            page.wait_for_timeout(200)
        record['observed']['pause_toast'] = toast
        shot(page, '22-pause-toast')
        step('V2-105 the pause toast comes from the catalogue',
             'pass' if toast == EXPECT['paused'] else 'fail',
             'got %r, wanted %r' % (toast, EXPECT['paused']))

    # V2-080: the operator-actions panel.
    tab = page.locator('div.ant-tabs-tab', has_text=EXPECT['operator_tab'])
    if tab.count() == 0:
        step('V2-080 reach the operator-actions panel', 'fail',
             'tab %r not found' % EXPECT['operator_tab'])
        return
    tab.first.click()
    # AntD keeps an opened tab pane MOUNTED when you leave it, so a bare
    # `th.ant-table-cell` resolves to the Game Control tab's hidden tables and
    # waiting for it to be visible times out against elements that exist.
    # Everything here is scoped to the ACTIVE pane for that reason.
    try:
        page.wait_for_selector('.ant-tabs-tabpane-active th.ant-table-cell',
                               timeout=20000)
    except Exception as exc:
        step('V2-080 the operator panel mounts', 'fail', str(exc)[:160])
        return
    page.wait_for_timeout(2000)
    probe = page.evaluate("""() => {
        const out = {text: [], rendered: []};
        document.querySelectorAll(
            '.ant-tabs-tabpane-active th.ant-table-cell').forEach(h => {
            out.text.push(h.textContent.trim());
            out.rendered.push(h.innerText.trim());
        });
        return out;
    }""")
    record['observed']['operator_headers'] = probe['text']
    record['observed']['operator_headers_as_rendered'] = probe['rendered']
    shot(page, '23-operator-actions-panel')
    panel = page.evaluate("""() => {
        const el = document.querySelector('.ant-tabs-tabpane-active');
        return el ? el.textContent : '';
    }""")
    step('V2-080 the panel card title is the catalogued wording',
         'pass' if EXPECT['operator_card'] in panel else 'fail',
         EXPECT['operator_card'])
    missing = [h for h in EXPECT['operator_headers'] if h not in probe['text']]
    step('V2-080 every operator column header is the catalogued wording',
         'pass' if not missing else 'fail',
         'missing: %s; got %s' % (missing, probe['text']))
    step('V2-080 no instructor.* key rendered in the panel',
         'pass' if not any('instructor.' in h for h in probe['text']) else 'fail',
         probe['text'])


def _django_env():
    import os
    env = dict(os.environ)
    for line in (SCRATCH / 'dbenv').read_text().splitlines():
        if line.startswith('export '):
            key, _, value = line[len('export '):].partition('=')
            env[key] = value
    return env


def finish():
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'console_errors': len([c for c in record['console']
                               if c['type'] == 'error']),
        'network_errors': len(record['network']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / ('browser-%s.json' % LANG)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print('record: %s' % out)
    return 0 if record['summary']['failed'] == 0 else 1


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        student = browser.new_page(viewport={'width': 1500, 'height': 1100})
        instrument(student)
        drive_student(student)
        student.close()

        operator = browser.new_page(viewport={'width': 1600, 'height': 1200})
        instrument(operator)
        drive_instructor(operator)
        operator.close()
        browser.close()
    return finish()


if __name__ == '__main__':
    raise SystemExit(main())
