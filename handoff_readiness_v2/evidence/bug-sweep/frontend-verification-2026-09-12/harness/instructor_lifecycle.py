"""Item 6, continued: the confirmations only reachable in later round states.

The first instructor pass captured close, set-deadline, close-and-process and
extend, then lost the thread because it looked for the process button before
the console had re-rendered. This one asks the API what state the round is
actually in, captures whatever confirmation that state offers, performs the
action, and goes round again -- so process, reopen and advance are reached
wherever the fixture happens to be.
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
STOP_AFTER = sys.argv[2] if len(sys.argv) > 2 else 'advance'
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
GAME_NAME = fixture['game_name']
INSTRUCTOR = fixture['instructor']
PASSWORD = fixture['password']

record = {'language': LANG, 'game_name': GAME_NAME, 'steps': [],
          'console': [], 'network': [], 'confirmations': {},
          'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:700]})
    print(f'  {outcome.upper():<13} {name}'
          f'{" — " + str(detail)[:230] if detail else ""}', flush=True)


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f'{name}-{LANG}.png'
    page.screenshot(path=str(path), full_page=True)
    record['screenshots'].append(path.name)
    return path.name


def names_game(text):
    return bool(text) and GAME_NAME in text


def click_text(page, text):
    el = page.locator(f'text={text}').first
    if el.count() == 0:
        return False
    el.click()
    page.wait_for_timeout(2500)
    return True


def goto_console(page):
    page.goto(f'{BASE}/instructor', wait_until='domcontentloaded')
    page.wait_for_timeout(4500)
    click_text(page, 'CRV213')
    page.wait_for_timeout(2000)
    click_text(page, 'CRV213-01')
    page.wait_for_timeout(6000)
    for label in ('Game Control', '游戏控制'):
        if click_text(page, label):
            break
    page.wait_for_timeout(4000)


def state(page):
    got = page.evaluate("""async (g) => {
        const t = localStorage.getItem('access_token');
        const r = await fetch('/api/games/' + g + '/round-control/', {
            headers: {Authorization: 'Bearer ' + t,
                      'Accept-Language': localStorage.getItem('gs_language') || 'en'}});
        return await r.json();
    }""", GAME)
    return got


def capture_popconfirm(page, labels, key, shot_name):
    for label in labels:
        btn = page.locator('button', has_text=label).first
        if btn.count() == 0:
            continue
        btn.click()
        page.wait_for_timeout(1400)
        pop = page.locator('.ant-popconfirm').last
        text = pop.inner_text() if pop.count() else ''
        if text:
            record['confirmations'][key] = text
            shot(page, shot_name)
            return text
    return None


def confirm_popconfirm(page):
    ok = page.locator('.ant-popconfirm .ant-btn-primary').last
    if ok.count():
        ok.click()
        page.wait_for_timeout(8000)
        return True
    return False


def capture_modal(page, labels, key, shot_name):
    for label in labels:
        btn = page.locator('button', has_text=label).first
        if btn.count() == 0:
            continue
        btn.click()
        page.wait_for_timeout(1600)
        modal = page.locator('.ant-modal-content').last
        text = modal.inner_text() if modal.count() else ''
        if text:
            record['confirmations'][key] = text
            shot(page, shot_name)
            close = page.locator('.ant-modal-close').last
            if close.count():
                try:
                    close.click()
                except Exception:
                    pass
            page.wait_for_timeout(900)
            return text
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:400]})
            if m.type in ('error', 'warning') else None))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:220], 'status': r.status}) if r.status >= 400 else None)

        page.goto(f'{BASE}/instructor/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        page.fill('input#username, input[name="username"]', INSTRUCTOR)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        if not page.evaluate("() => localStorage.getItem('access_token')"):
            step('instructor signed in', 'fail')
            browser.close()
            return finish()
        step('instructor signed in', 'pass')

        goto_console(page)

        for _ in range(4):
            info = state(page)
            rnd = (info or {}).get('round') or {}
            status = rnd.get('status')
            step(f'round {rnd.get("round_number")} state', 'observed',
                 f'status={status} next={rnd.get("next_action")}')

            card = page.locator('.ant-card', has_text='Round Control').first
            if card.count() == 0:
                card = page.locator('.ant-card', has_text='回合控制').first
            if card.count():
                head = card.locator('.ant-card-head-title').first
                title = head.inner_text() if head.count() else ''
                record['confirmations']['round_control_title'] = title
                step('ITEM 6 round console names the game',
                     'pass' if names_game(title) else 'fail', title[:160])
                shot(page, f'40-round-control-{status}')

            if status == 'open':
                capture_popconfirm(page, ['Close round now', '立即关闭'],
                                   'close', '41-confirm-close')
                confirm_popconfirm(page)
            elif status == 'closed':
                capture_modal(page, ['Reopen round', '重新开放'],
                              'reopen', '42-confirm-reopen')
                capture_popconfirm(
                    page, ['Run post-round processing', '运行回合结算',
                           '回合结算'], 'process', '43-confirm-process')
                confirm_popconfirm(page)
                page.wait_for_timeout(22000)
            elif status == 'processed':
                capture_popconfirm(
                    page, ['Advance to round', 'Finish game', '推进到', '结束'],
                    'advance', '44-confirm-advance')
                if STOP_AFTER == 'advance':
                    confirm_popconfirm(page)
                break
            else:
                break

            page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            for label in ('Game Control', '游戏控制'):
                if click_text(page, label):
                    break
            page.wait_for_timeout(4000)

        for key in ('close', 'process', 'advance', 'reopen'):
            text = record['confirmations'].get(key)
            if text is None:
                step(f'ITEM 6 confirmation names the game: {key}',
                     'not-verified', 'state not reached in this run')
            else:
                step(f'ITEM 6 confirmation names the game: {key}',
                     'pass' if names_game(text) else 'fail',
                     text.replace('\n', ' / ')[:230])

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
    out = EVIDENCE / f'instructor-lifecycle-{LANG}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print(f'record: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
