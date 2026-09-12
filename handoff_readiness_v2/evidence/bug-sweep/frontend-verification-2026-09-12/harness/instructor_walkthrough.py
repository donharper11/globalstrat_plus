"""CRV2-13 instructor walkthrough: game identity on round actions, and caps.

Items 6 and 7. The lifecycle is driven forward for real (close -> process ->
advance) because item 4 needs a processed round, so this script must run once
and in order.

Every confirmation is opened and its visible title captured before it is
accepted: item 6 is a claim about what the operator is asked, and only the
rendered text answers it.
"""
import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-a0ae8bfea94e98414/handoff_readiness_v2/evidence/bug-sweep'
    '/frontend-verification-2026-09-12')
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ADVANCE = '--advance' in sys.argv
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
GAME_NAME = fixture['game_name']
SECTION = fixture['section_id']
INSTRUCTOR = fixture['instructor']
PASSWORD = fixture['password']

record = {'language': LANG, 'game': GAME, 'game_name': GAME_NAME,
          'steps': [], 'console': [], 'network': [], 'confirmations': {},
          'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:600]})
    print(f'  {outcome.upper():<12} {name}'
          f'{" — " + str(detail)[:220] if detail else ""}', flush=True)


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f'{name}-{LANG}.png'
    page.screenshot(path=str(path), full_page=True)
    record['screenshots'].append(path.name)
    return path.name


def click_text(page, text):
    el = page.locator(f'text={text}').first
    if el.count() == 0:
        return False
    el.click()
    page.wait_for_timeout(2500)
    return True


def open_popconfirm(page, button_text):
    """Click a button guarded by a Popconfirm, return the confirmation text."""
    btn = page.locator('button', has_text=button_text).first
    if btn.count() == 0:
        return None, None
    btn.click()
    page.wait_for_timeout(1200)
    pop = page.locator('.ant-popconfirm').last
    text = pop.inner_text() if pop.count() else ''
    return btn, text


def confirm_popconfirm(page):
    ok = page.locator('.ant-popconfirm .ant-btn-primary').last
    if ok.count():
        ok.click()
        page.wait_for_timeout(6000)


def open_modal(page, button_text):
    btn = page.locator('button', has_text=button_text).first
    if btn.count() == 0:
        return None
    btn.click()
    page.wait_for_timeout(1500)
    modal = page.locator('.ant-modal-content').last
    return modal.inner_text() if modal.count() else ''


def close_modal(page):
    x = page.locator('.ant-modal-close').last
    if x.count():
        try:
            x.click()
        except Exception:
            pass
    page.wait_for_timeout(900)


def names_game(text):
    return bool(text) and GAME_NAME in text


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})

        # Unreachable from this sandbox; a pending font request stops the page
        # settling. Decoration, not behaviour under test.
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())

        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:400]})
            if m.type in ('error', 'warning') else None))
        page.on('requestfailed', lambda r: record['network'].append(
            {'url': r.url[:220], 'failure': (r.failure or '')}))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:220], 'status': r.status}) if r.status >= 400 else None)

        page.goto(f'{BASE}/instructor/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        page.fill('input#username, input[name="username"]', INSTRUCTOR)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        token = page.evaluate("() => localStorage.getItem('access_token')")
        step('instructor signed in', 'pass' if token else 'fail')
        if not token:
            browser.close()
            return finish()

        page.goto(f'{BASE}/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        click_text(page, 'CRV213')
        page.wait_for_timeout(2500)
        click_text(page, 'CRV213-01')
        page.wait_for_timeout(6000)
        tabs = page.locator('.ant-tabs-tab').all_inner_texts()
        record['tabs'] = tabs
        step('instructor reached the game from course and section',
             'pass' if tabs else 'fail', ' | '.join(tabs)[:300])
        shot(page, '10-instructor-dashboard')

        # The round console lives on Game Control.
        for label in ('Game Control', '游戏控制'):
            if click_text(page, label):
                break
        page.wait_for_timeout(4000)
        body = page.inner_text('body')
        card = page.locator('.ant-card', has_text='Round Control').first
        if card.count() == 0:
            card = page.locator('.ant-card', has_text='回合控制').first
        title = ''
        if card.count():
            head = card.locator('.ant-card-head-title').first
            title = head.inner_text() if head.count() else ''
        record['confirmations']['round_control_title'] = title
        step('ITEM 6 round console names the game',
             'pass' if names_game(title) else 'fail', title[:200])
        shot(page, '11-item6-round-control-card')

        # ---- every confirmation that can act on this round ---------------
        checks = {}

        for key, label in (('close', 'Close round now'),
                           ('close_zh', '立即关闭')):
            btn, text = open_popconfirm(page, label)
            if text:
                checks['close'] = text
                shot(page, '12-item6-confirm-close')
                page.keyboard.press('Escape')
                page.wait_for_timeout(700)
                break

        for label in ('Set deadline', 'Change deadline', '设置截止', '更改截止'):
            text = open_modal(page, label)
            if text:
                checks['deadline'] = text
                shot(page, '13-item6-confirm-set-deadline')
                close_modal(page)
                break

        for label in ('Close & process now', 'Close &amp; process now',
                      '关闭并结算'):
            text = open_modal(page, label)
            if text:
                checks['close_and_process'] = text
                shot(page, '14-item6-confirm-close-and-process')
                close_modal(page)
                break

        # Extend Deadline is a separate control on the dashboard, not part of
        # RoundControlCard, and it also acts on the round.
        for label in ('Extend Deadline', '延长截止时间'):
            text = open_modal(page, label)
            if text:
                checks['extend'] = text
                shot(page, '15-item6-confirm-extend-deadline')
                close_modal(page)
                break

        # ---- drive the lifecycle forward ---------------------------------
        btn, text = open_popconfirm(page, 'Close round now')
        if not text:
            btn, text = open_popconfirm(page, '立即关闭')
        if text:
            checks['close'] = text
            confirm_popconfirm(page)
        page.wait_for_timeout(6000)
        shot(page, '16-round-closed')

        for label in ('Run post-round processing', '运行回合结算', '回合结算'):
            btn, text = open_popconfirm(page, label)
            if text:
                checks['process'] = text
                shot(page, '17-item6-confirm-process')
                confirm_popconfirm(page)
                break
        page.wait_for_timeout(20000)

        # Reopen only exists while the round is closed; capture it if the
        # console still offers it.
        for label in ('Reopen round', '重新开放'):
            text = open_modal(page, label)
            if text:
                checks['reopen'] = text
                shot(page, '18-item6-confirm-reopen')
                close_modal(page)
                break

        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        for label in ('Game Control', '游戏控制'):
            if click_text(page, label):
                break
        page.wait_for_timeout(4000)
        shot(page, '19-round-processed')

        for label in ('Advance to round', 'Finish game', '推进到', '结束'):
            btn, text = open_popconfirm(page, label)
            if text:
                checks['advance'] = text
                shot(page, '20-item6-confirm-advance')
                page.keyboard.press('Escape')
                break

        record['confirmations'].update(checks)
        for key in ('close', 'process', 'advance', 'deadline',
                    'close_and_process', 'reopen', 'extend'):
            text = checks.get(key)
            if text is None:
                step(f'ITEM 6 confirmation names the game: {key}',
                     'not-verified', 'control not reached in this state')
            else:
                step(f'ITEM 6 confirmation names the game: {key}',
                     'pass' if names_game(text) else 'fail',
                     text.replace('\n', ' / ')[:220])

        # ---------------- Item 7: cohort cap refusals ---------------------
        # The sixth member of a five-member team, through the API the roster
        # screen calls, issued from the instructor's own browser session.
        team_a = fixture['team_a_id']
        spare = fixture['spare_student']
        spare_id = None
        roster = page.evaluate("""async (s) => {
            const t = localStorage.getItem('access_token');
            const r = await fetch('/api/roster/?section_id=' + s,
                                  {headers: {Authorization: 'Bearer ' + t}});
            return {status: r.status, body: await r.json().catch(() => null)};
        }""", SECTION)
        for row in (roster.get('body') or []):
            if row.get('username') == spare or row.get('student_id') == spare:
                spare_id = row.get('user_id') or row.get('student_id')
        record['roster_probe'] = {'status': roster.get('status'),
                                  'spare_user_id': spare_id}

        if spare_id is None:
            spare_id = fixture.get('spare_user_id')
        sixth = page.evaluate("""async (args) => {
            const t = localStorage.getItem('access_token');
            const r = await fetch('/api/team-management/', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json',
                          Authorization: 'Bearer ' + t},
                body: JSON.stringify({action: 'assign', assignments: [
                    {user_id: args.user, team_id: args.team}]}),
            });
            return {status: r.status, body: await r.text()};
        }""", {'user': spare_id, 'team': team_a})
        record['item7_sixth_member'] = sixth
        names_cap = ('maximum this section allows' in (sixth.get('body') or '')
                     or '已达本班级允许的上限' in (sixth.get('body') or ''))
        step('ITEM 7 sixth team member refused in business language',
             'pass' if sixth.get('status', 0) >= 400 and names_cap else 'fail',
             f'HTTP {sixth.get("status")} {str(sixth.get("body"))[:260]}')

        ninth = page.evaluate("""async (s) => {
            const t = localStorage.getItem('access_token');
            const r = await fetch('/api/games/create/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json',
                          Authorization: 'Bearer ' + t},
                body: JSON.stringify({scenario_id: 1, num_teams: 9,
                                      name: 'CRV2-13 ninth firm probe',
                                      section_id: s}),
            });
            return {status: r.status, body: await r.text()};
        }""", SECTION)
        record['item7_ninth_firm'] = ninth
        names_cap9 = ('runs at most' in (ninth.get('body') or '')
                      or '最多可运行' in (ninth.get('body') or ''))
        step('ITEM 7 ninth firm refused in business language',
             'pass' if ninth.get('status', 0) >= 400 and names_cap9 else 'fail',
             f'HTTP {ninth.get("status")} {str(ninth.get("body"))[:260]}')
        shot(page, '21-item7-cohort-caps')

        browser.close()
    return finish()


def finish():
    errors = [c for c in record['console'] if c['type'] == 'error']
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'not_verified': sum(1 for s in record['steps']
                            if s['outcome'] == 'not-verified'),
        'console_errors': len(errors),
        'network_errors': len(record['network']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / f'instructor-walkthrough-{LANG}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print(f'record: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
