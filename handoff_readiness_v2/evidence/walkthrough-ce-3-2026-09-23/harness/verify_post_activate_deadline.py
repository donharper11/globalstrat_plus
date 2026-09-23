"""Does the round console work straight after Activate, without a refresh?

verify_post_activate_deadline.py

The first pass of `instructor_setup.py` on this walkthrough hit a refusal here:
Activate Game, then Round control › Set deadline in the same page session, and
the server answered *The game has moved to round 1; this request was for round
0. Refresh the console and repeat the action if it is still what you want.*
The resumed run could not record it again (the game was already active), so
this driver reproduces it from scratch in its own section: a new section, a new
two-team game, Activate, then Set deadline without reloading -- and then again
after a reload, so the record says whether the control works at all or only
after a refresh. The game it creates is left in setup-with-one-round-open and
is not part of the walkthrough's heat.
"""
import json

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  pick_select, popconfirm_ok, set_number, sign_in,
                  sync_playwright, toast)

LANG = 'en'
R = Recorder('verify-post-activate-deadline', LANG)
SECTION_CODE, SECTION_NAME = 'CE26-B', 'Heat B'
GAME_NAME = 'CE 2026 Heat B'


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def card(page, text):
    return page.locator('.ant-card', has_text=text).first


def set_deadline(page, tag):
    rcc = card(page, 'Round control')
    btn = rcc.locator('button', has_text='deadline').first
    btn.click(); page.wait_for_timeout(1500)
    R.observe('deadline_modal_%s' % tag, modal_text(page))
    picker = page.locator('.ant-modal-wrap:visible .ant-picker input').first
    picker.click(); page.keyboard.press('Control+a')
    page.keyboard.type('2026-09-28 18:00:00'); page.keyboard.press('Enter')
    page.wait_for_timeout(600)
    page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary').last.click()
    t = toast(page, 15)
    R.observe('deadline_toast_%s' % tag, t)
    page.wait_for_timeout(3000)
    R.screen(page, 'v-activate-deadline-%s' % tag, 'Set deadline %s' % tag)
    return t


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        page.locator('.ant-card', has_text='CE26').last.click()
        page.wait_for_timeout(2500)

        # a section of its own, so the walkthrough's heat is untouched
        s = card(page, 'Sections')
        s.locator('input').nth(0).fill(SECTION_CODE)
        s.locator('input').nth(1).fill(SECTION_NAME)
        s.locator('button', has_text='Create').first.click()
        page.wait_for_timeout(2500)
        page.locator('.ant-card', has_text=SECTION_CODE).last.click()
        page.wait_for_timeout(4000)
        g = card(page, 'Step 1: Create a Game')
        pick_select(page, g.locator('.ant-select').first, 'Consumer Electronics')
        page.wait_for_timeout(1500)
        g.locator('input.ant-input').first.fill(GAME_NAME)
        set_number(page, g.locator('.ant-input-number-input').first, 2)
        g.locator('button', has_text='Create Game & Teams').first.click()
        R.observe('create_toast', toast(page))
        page.wait_for_timeout(5000)
        games = api(page, 'GET', '/api/games/')
        glist = (games['body'] or {}).get('games') or []
        game = next((x for x in glist if x.get('game_name') == GAME_NAME), None)
        R.step('a second game exists to test the sequence on',
               'pass' if game else 'fail', json.dumps(game)[:200] if game else None)
        if not game:
            browser.close(); return R.finish()
        gid = game.get('game_id')

        click_tab(page, 'Game Control'); page.wait_for_timeout(4000)
        A(page).locator('button', has_text='Activate Game').first.click()
        page.wait_for_timeout(1000)
        popconfirm_ok(page, 5000)
        R.observe('activate_toast', toast(page, 10))
        page.wait_for_timeout(3000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        R.observe('round_after_activate', rc['body'].get('round'))
        R.step('the game is active with round 1 open',
               'pass' if (rc['body'].get('round') or {}).get('status') == 'open' else 'fail',
               json.dumps(rc['body'].get('round'))[:200])
        R.screen(page, 'v-activate-deadline-activated', 'straight after Activate Game')

        # 1: without reloading
        click_tab(page, 'Game Control'); page.wait_for_timeout(3000)
        t1 = set_deadline(page, 'no-refresh')
        rc1 = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        dl1 = (rc1['body'].get('round') or {}).get('deadline')
        refused = [x for x in R.record['refused'] if 'deadline' in x['url']]
        R.observe('deadline_refusals', refused)
        R.step('Set deadline works straight after Activate, with no refresh',
               'pass' if dl1 and dl1.startswith('2026-09-28') else 'fail',
               'deadline=%s toast=%r refusals=%s'
               % (dl1, t1, json.dumps([x['body'][:200] for x in refused], ensure_ascii=False)[:300]))

        # 2: after a reload
        page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(6000)
        page.locator('.ant-card', has_text='CE26').last.click(); page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=SECTION_CODE).last.click(); page.wait_for_timeout(5000)
        click_tab(page, 'Game Control'); page.wait_for_timeout(4000)
        t2 = set_deadline(page, 'after-refresh')
        rc2 = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        dl2 = (rc2['body'].get('round') or {}).get('deadline')
        R.step('Set deadline works after a page refresh',
               'pass' if dl2 and dl2.startswith('2026-09-28') else 'fail',
               'deadline=%s toast=%r' % (dl2, t2))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
