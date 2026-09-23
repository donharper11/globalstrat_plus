"""A round that was locked by every team and cannot be scored.

    probe_round_wont_process.py <lang> <round>

Round 5 of this walkthrough closed with all eight teams locked and then
refused to process: *Round 5 cannot be scored: 2 equity raise(s) exceed the
funding shortfall they claim to finance.* Nothing on any student screen said
so -- the Decision Summary offered the lock and the server accepted it.

This driver presses *Run post-round processing* from the console and records
what the operator is shown, what the route answers, and the two teams'
figures, so the refusal is on record as an operator sees it rather than only
in a log file.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  popconfirm_ok, sign_in, sync_playwright, toast, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 5
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('round-wont-process-r%d' % ROUND, LANG)
L = {'en': {'control': 'Game Control', 'process': 'Run post-round processing'},
     'zh-CN': {'control': '游戏控制', 'process': '运行回合结算'}}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG, rec=R)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        card = page.locator('.ant-card', has_text=G['section_code']).last
        if card.count():
            card.click()
            page.wait_for_timeout(6000)
        click_tab(page, L['control'])
        page.wait_for_timeout(4000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % GID)['body']
        R.observe('round_control', rc)
        rnd = (rc or {}).get('round') or {}
        R.step('round %d is closed with every team locked' % ROUND,
               'pass' if rnd.get('status') == 'closed'
               and rnd.get('teams_pending') == 0 else 'observed',
               'status=%s locked=%s/%s next_action=%s'
               % (rnd.get('status'), rnd.get('teams_locked'),
                  rnd.get('teams_total'), rnd.get('next_action')))
        R.screen(page, 'v4-wont-process-00-closed')
        btn = A(page).locator('button', has_text=L['process'])
        if not btn.count():
            R.step('the console offers post-round processing', 'fail',
                   'no processing button on the round control card')
            browser.close()
            return R.finish()
        btn.first.click()
        page.wait_for_timeout(1200)
        R.screen(page, 'v4-wont-process-01-confirm')
        popconfirm_ok(page, 8000)
        page.wait_for_timeout(6000)
        shown = toast(page, 20) or modal_text(page) or ''
        R.observe('what_the_operator_is_shown', shown[:1200])
        R.observe('page_text', visible_text(page)[:2000])
        R.screen(page, 'v4-wont-process-02-refused')
        refused = [x for x in R.record['refused']
                   if '/round-control/process/' in x['url']]
        R.observe('process_refusals', refused)
        after = api(page, 'GET', '/api/games/%s/round-control/' % GID)['body']
        R.observe('round_control_after', after)
        still = ((after or {}).get('round') or {}).get('status')
        R.step('the round processes when every team has locked it',
               'pass' if still == 'processed' else 'fail',
               'status is still %r; the route answered %s; the operator was '
               'shown: %r'
               % (still,
                  json.dumps([x['status'] for x in refused]),
                  shown[:400]))
        for x in refused:
            R.step('the refusal names what has to change', 'observed',
                   x['body'][:700])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
