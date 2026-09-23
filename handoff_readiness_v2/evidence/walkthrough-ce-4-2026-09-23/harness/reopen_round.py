"""Reopen a closed round from the console: reopen_round.py <lang> <round> <deadline>

Used once in this walkthrough, and disclosed as an auditor's intervention:
round 5 closed with all eight teams locked and then refused to process, so
there was no way forward except to reopen it, have the two teams whose equity
the engine rejected change it, and close it again. The control is the
console's own *Reopen round*, which asks for a new deadline.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text, sign_in,
                  sync_playwright, toast)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 5
DEADLINE = sys.argv[3] if len(sys.argv) > 3 else '2026-10-09 18:00:00'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('reopen-round%d' % ROUND, LANG)
L = {'en': {'control': 'Game Control', 'reopen': 'Reopen round'},
     'zh-CN': {'control': '游戏控制', 'reopen': '重新开放回合'}}[LANG]


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
        ro = A(page).locator('button', has_text=L['reopen'])
        R.step('the console offers *Reopen round*', 'pass' if ro.count() else 'fail')
        if not ro.count():
            browser.close()
            return R.finish()
        ro.first.click()
        page.wait_for_timeout(1500)
        R.observe('reopen_modal', modal_text(page))
        picker = page.locator('.ant-modal-content .ant-picker input').first
        if picker.count():
            picker.click()
            page.keyboard.press('Control+a')
            page.keyboard.type(DEADLINE)
            page.keyboard.press('Enter')
            page.wait_for_timeout(800)
        R.screen(page, 'v4-reopen-r%d-modal' % ROUND)
        page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary'
                     ).last.click()
        R.observe('reopen_toast', toast(page, 15))
        page.wait_for_timeout(5000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % GID)['body']
        R.observe('round_control_after', rc)
        rnd = (rc or {}).get('round') or {}
        R.step('round %d is open again' % ROUND,
               'pass' if rnd.get('status') == 'open' else 'fail',
               json.dumps(rnd)[:250])
        R.screen(page, 'v4-reopen-r%d-after' % ROUND)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
