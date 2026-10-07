"""The last round, and the control that ends the game.

    finish_game.py <lang> <round>

Walkthrough 3 could not reach this: `components/RoundControlCard.js` renders
*Finish game* in place of *Advance* only when `current_round >= total_rounds`,
this scenario authors ten rounds and that pass played six. This driver closes
and processes the last round from the console and then presses whatever the
card offers in place of *Advance*, recording what the game does afterwards --
whether results, statements and the leaderboard are still readable, and what
the round control says.
"""
import json
import pathlib
import sys
import time

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  popconfirm_ok, sign_in, sync_playwright, toast, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 10
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('finish-game-r%d' % ROUND, LANG)
L = {
    'en': {'control': 'Game Control', 'close': 'Close round now',
           'process': 'Run post-round processing', 'advance': 'Advance to round',
           'finish': 'Finish game'},
    'zh-CN': {'control': '游戏控制', 'close': '立即关闭回合',
              'process': '运行回合结算', 'advance': '推进到第',
              'finish': '结束游戏'},
}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def rc(page):
    return api(page, 'GET', '/api/games/%s/round-control/' % GID)['body']


def wait_processed(page, timeout=900):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        b = rc(page)
        r = b.get('round') or {}
        last = (r.get('status'), r.get('processing_status'))
        if r.get('status') == 'processed' and r.get('processing_status') in (
                'FULLY_COMPLETE', 'RESULTS_AVAILABLE'):
            return True
        page.wait_for_timeout(4000)
    R.step('the last round finishes processing', 'fail',
           'still %r after %ds' % (last, timeout))
    return False


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
        before = rc(page)
        R.observe('round_control_before', before)
        rnd = (before or {}).get('round') or {}
        R.step('round %d is the open round, and it is the last one' % ROUND,
               'pass' if rnd.get('round_number') == ROUND
               and before.get('total_rounds') == ROUND else 'fail',
               'round=%s total_rounds=%s' % (rnd.get('round_number'),
                                             before.get('total_rounds')))
        R.screen(page, 'end4-00-last-round-open')

        if rnd.get('status') == 'open':
            A(page).locator('button', has_text=L['close']).first.click()
            page.wait_for_timeout(1000)
            R.screen(page, 'end4-01-close-confirm')
            popconfirm_ok(page, 4000)
            R.observe('close_toast', toast(page, 10))
            page.wait_for_timeout(3000)
        b = rc(page)
        R.step('the last round closed from the console',
               'pass' if ((b.get('round') or {}).get('status')
                          in ('closed', 'processed')) else 'fail',
               (b.get('round') or {}).get('status'))
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        if ((rc(page).get('round') or {}).get('status')) == 'closed':
            pr = A(page).locator('button', has_text=L['process'])
            if pr.count():
                pr.first.click()
                page.wait_for_timeout(1000)
                R.screen(page, 'end4-02-process-confirm')
                popconfirm_ok(page, 6000)
                R.observe('process_toast', toast(page, 15))
        wait_processed(page)
        after = rc(page)
        R.observe('round_control_processed', after)
        R.step('round %d processed' % ROUND,
               'pass' if ((after.get('round') or {}).get('status')
                          == 'processed') else 'fail',
               json.dumps((after.get('round') or {}))[:250])
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        card = page.locator('.ant-card', has_text=G['section_code']).last
        if card.count():
            card.click()
            page.wait_for_timeout(6000)
        click_tab(page, L['control'])
        page.wait_for_timeout(4000)
        R.screen(page, 'end4-03-after-processing')
        text = visible_text(page)
        R.observe('round_control_text', text[:1500])
        adv = A(page).locator('button', has_text=L['advance'])
        fin = A(page).locator('button', has_text=L['finish'])
        R.observe('advance_buttons', adv.count())
        R.observe('finish_buttons', fin.count())
        R.step('the console offers *Finish game* in place of *Advance* on the '
               'last round',
               'pass' if fin.count() and not adv.count() else 'fail',
               'advance buttons=%d finish buttons=%d' % (adv.count(), fin.count()))
        if fin.count():
            fin.first.click()
            page.wait_for_timeout(1200)
            R.observe('finish_confirm',
                      page.locator('.ant-popover:not(.ant-popover-hidden)').last
                      .text_content()
                      if page.locator('.ant-popover:not(.ant-popover-hidden)').count()
                      else modal_text(page))
            R.screen(page, 'end4-04-finish-confirm')
            if not popconfirm_ok(page, 6000):
                ok_btn = page.locator(
                    '.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary')
                if ok_btn.count():
                    ok_btn.last.click()
                    page.wait_for_timeout(6000)
            R.observe('finish_toast', toast(page, 15))
            page.wait_for_timeout(4000)
            R.screen(page, 'end4-05-after-finish')
        state = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        R.observe('round_control_after_finish', state['body'])
        status = (state['body'] or {}).get('game_status')
        R.step('the game reports itself finished',
               'pass' if status in ('completed', 'finished', 'ended') else 'fail',
               'game_status=%r' % status)
        # Everything a player and an instructor still need after the end.
        for label, path in (
                ('round 1 results', '/api/games/%d/teams/1/results/round/1/' % GID),
                ('last round results',
                 '/api/games/%d/teams/1/results/round/%d/' % (GID, ROUND)),
                ('leaderboard',
                 '/api/games/%d/leaderboard/round/%d/' % (GID, ROUND)),
                ('financial reports',
                 '/api/games/%d/teams/1/financial-reports/history/' % GID)):
            got = api(page, 'GET', path)
            R.step('%s is still readable after the game is finished' % label,
                   'pass' if got['status'] == 200 else 'fail',
                   'HTTP %s' % got['status'])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
