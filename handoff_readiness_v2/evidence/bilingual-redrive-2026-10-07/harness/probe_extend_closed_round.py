"""The control an instructor reaches for when a round has already closed.

    probe_extend_closed_round.py [lang]

A team asks for more time. The deadline has passed, so the round is closed --
which on competition day is the ordinary case, because the deadline scheduler
closes it within the minute. The console's *Extend Deadline* button is still
offered, and `InstructorExtendDeadlineView` reopens a closed round as a side
effect, so it demands a written reason the way every other reopen does
(`require_reason`, tested in `CloseVersusExtendTests`). **The modal has no
reason box**: it carries an hours spinner and nothing else.

So this driver asks what the instructor is actually shown, and whether the
product tells them what to do instead. It then drives the control that does
work -- *Reopen round*, which asks for a reason and a new deadline -- so the
record carries the dead end and the way out together.

It builds its own section and a two-team game (the pattern
`verify_post_activate_deadline.py` uses) so the walkthrough's heat is not
touched. Nothing here is part of the ten-round pass.
"""
import json
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text, pick_select,
                  popconfirm_ok, set_number, sign_in, sync_playwright, toast,
                  visible_text)

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
SECTION_CODE, SECTION_NAME = 'CE26-C', 'Heat C'
GAME_NAME = 'CE 2026 Heat C'
R = Recorder('probe-extend-closed-round', LANG)
L = {
    'en': {'control': 'Game Control', 'activate': 'Activate Game',
           'close': 'Close round now', 'extend': 'Extend Deadline',
           'reopen': 'Reopen round'},
    'zh-CN': {'control': '游戏控制', 'activate': '激活游戏',
              'close': '立即关闭回合', 'extend': '延长截止时间',
              'reopen': '重新开放回合'},
}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def card(page, text):
    return page.locator('.ant-card', has_text=text).first


def vmodal(page):
    return page.locator('.ant-modal-wrap:visible .ant-modal-content').last


def dismiss_modals(page, tries=6):
    """Close every modal that is open, and say how many there were.

    A refused extend leaves TWO stacked: the Extend dialog, which the failed
    request does not close, and the error Modal over it. One Escape closes one
    of them, and the leftover `.ant-modal-wrap` then intercepts every click on
    the page behind it -- which is what stopped the first run of this probe
    from reaching the control that actually works.
    """
    seen = 0
    for _ in range(tries):
        open_now = page.locator('.ant-modal-wrap:visible').count()
        if not open_now:
            break
        seen = max(seen, open_now)
        ok = page.locator('.ant-modal-confirm-btns .ant-btn-primary')
        if ok.count():
            ok.last.click()
        else:
            cancel = page.locator('.ant-modal-wrap:visible .ant-modal-footer '
                                  '.ant-btn:not(.ant-btn-primary)')
            if cancel.count():
                cancel.last.click()
            else:
                page.keyboard.press('Escape')
        page.wait_for_timeout(900)
    return seen


def press_extend(page, gid, tag):
    """Open Extend Deadline, record everything it offers, press OK."""
    btn = A(page).locator('button', has_text=L['extend']).first
    if not btn.count():
        btn = page.locator('button:visible', has_text=L['extend']).first
    offered = bool(btn.count())
    R.step('%s: the console offers Extend Deadline' % tag,
           'pass' if offered else 'fail')
    if not offered:
        return None, None
    btn.click()
    page.wait_for_timeout(1500)
    text = modal_text(page)
    R.observe('extend_modal_%s' % tag, text)
    boxes = vmodal(page).locator('textarea, input[type="text"]')
    R.observe('extend_modal_text_inputs_%s' % tag, boxes.count())
    R.step('%s: the extend modal offers somewhere to write a reason' % tag,
           'pass' if boxes.count() else 'fail',
           '%d textarea/text inputs; modal=%r' % (boxes.count(),
                                                  (text or '')[:200]))
    R.screen(page, 'x-closed-%s-modal' % tag)
    vmodal(page).locator('.ant-modal-footer .ant-btn-primary').last.click()
    page.wait_for_timeout(3500)
    after = modal_text(page)
    R.observe('extend_result_%s' % tag, after)
    R.observe('extend_toast_%s' % tag, toast(page, 8))
    R.screen(page, 'x-closed-%s-result' % tag, (after or '')[:120])
    # Clear whatever is on screen: an error Modal here, a success toast there.
    R.observe('modals_left_open_%s' % tag, dismiss_modals(page))
    rc = api(page, 'GET', '/api/games/%s/round-control/' % gid)
    return after, (rc['body'] or {}).get('round') or {}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox',
                                          '--disable-dev-shm-usage',
                                          '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG, rec=R)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        page.locator('.ant-card', has_text='CE26').last.click()
        page.wait_for_timeout(2500)

        # ---- a section and a game of its own ------------------------------
        existing = api(page, 'GET', '/api/games/')
        glist = ((existing['body'] or {}).get('games') or [])
        game = next((x for x in glist if x.get('game_name') == GAME_NAME), None)
        if game is None:
            s = card(page, 'Sections')
            s.locator('input').nth(0).fill(SECTION_CODE)
            s.locator('input').nth(1).fill(SECTION_NAME)
            s.locator('button', has_text='Create').first.click()
            page.wait_for_timeout(2500)
        page.locator('.ant-card', has_text=SECTION_CODE).last.click()
        page.wait_for_timeout(4000)
        if game is None:
            g = card(page, 'Step 1: Create a Game')
            pick_select(page, g.locator('.ant-select').first,
                        'Consumer Electronics')
            page.wait_for_timeout(1500)
            g.locator('input.ant-input').first.fill(GAME_NAME)
            set_number(page, g.locator('.ant-input-number-input').first, 2)
            g.locator('button', has_text='Create Game & Teams').first.click()
            R.observe('create_toast', toast(page))
            page.wait_for_timeout(5000)
            glist = ((api(page, 'GET', '/api/games/')['body'] or {})
                     .get('games') or [])
            game = next((x for x in glist
                         if x.get('game_name') == GAME_NAME), None)
        R.step('a game of its own exists for this probe',
               'pass' if game else 'fail',
               json.dumps(game)[:200] if game else None)
        if not game:
            browser.close()
            return R.finish()
        gid = game.get('game_id')
        R.observe('probe_game_id', gid)

        click_tab(page, L['control'])
        page.wait_for_timeout(4000)
        act = A(page).locator('button', has_text=L['activate']).first
        if act.count():
            act.click()
            page.wait_for_timeout(1000)
            popconfirm_ok(page, 5000)
            R.observe('activate_toast', toast(page, 10))
            page.wait_for_timeout(3000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        rnd = (rc['body'] or {}).get('round') or {}
        R.step('the game is active with round 1 open',
               'pass' if rnd.get('status') == 'open' else 'fail',
               json.dumps(rnd)[:200])

        # ---- make the round closed, the way the deadline makes it closed --
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        rcc = card(page, 'Round control')
        btn = rcc.locator('button', has_text='deadline').first
        if btn.count():
            btn.click()
            page.wait_for_timeout(1500)
            picker = page.locator('.ant-modal-wrap:visible .ant-picker input').first
            picker.click()
            page.keyboard.press('Control+a')
            page.keyboard.type('2026-09-28 18:00:00')
            page.keyboard.press('Enter')
            page.wait_for_timeout(600)
            page.locator('.ant-modal-wrap:visible .ant-modal-footer '
                         '.ant-btn-primary').last.click()
            R.observe('past_deadline_toast', toast(page, 15))
            page.wait_for_timeout(3000)
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        closer = A(page).locator('button', has_text=L['close']).first
        R.step('the console offers Close round now', 'pass' if closer.count()
               else 'fail')
        if closer.count():
            closer.click()
            page.wait_for_timeout(1200)
            popconfirm_ok(page, 5000)
            R.observe('close_toast', toast(page, 12))
            page.wait_for_timeout(3000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        rnd = (rc['body'] or {}).get('round') or {}
        R.step('round 1 is closed, as the deadline leaves it',
               'pass' if rnd.get('status') == 'closed' else 'fail',
               'status=%s deadline=%s' % (rnd.get('status'),
                                          rnd.get('deadline')))
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)

        # ---- the dead end ------------------------------------------------
        result, after_round = press_extend(page, gid, 'on-a-closed-round')
        refusals = [x for x in R.record['refused']
                    if 'extend-deadline' in x['url']]
        R.observe('extend_refusals', refusals)
        codes = []
        for x in refusals:
            try:
                codes.append(json.loads(x['body']).get('code')
                             or json.loads(x['body']).get('error'))
            except Exception:
                codes.append((x['body'] or '')[:120])
        R.observe('extend_refusal_codes', codes)
        refused = bool(refusals)
        R.step('Extend Deadline on a closed round is refused by the server',
               'pass' if refused else 'fail',
               json.dumps(codes, ensure_ascii=False)[:400])
        # The finding: refused for a reason the modal cannot take. Recorded as
        # a step either way, so a later repair flips it rather than deleting it.
        reason_required = any('reason' in str(c).lower() for c in codes)
        R.step('the instructor is told what to do instead of being refused '
               'for a reason the modal cannot take',
               'fail' if reason_required else 'pass',
               'refusal shown to the operator: %r; names Reopen round: %s'
               % ((result or '')[:200],
                  bool(result) and (L['reopen'].lower() in (result or '').lower())))
        R.observe('round_after_refused_extend', after_round)
        R.step('the refused extension left the round exactly as it was',
               'pass' if (after_round or {}).get('status') == 'closed'
               else 'fail', json.dumps(after_round)[:200])

        # ---- the way out, driven ------------------------------------------
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        ro = A(page).locator('button', has_text=L['reopen']).first
        R.step('the console offers Reopen round on a closed round',
               'pass' if ro.count() else 'fail')
        if ro.count():
            ro.click()
            page.wait_for_timeout(1500)
            R.observe('reopen_modal', modal_text(page))
            ta = page.locator('.ant-modal-wrap:visible textarea').first
            R.step('the reopen modal takes the written reason the extension '
                   'needed', 'pass' if ta.count() else 'fail')
            if ta.count():
                ta.fill('A team asked for more time after the deadline closed '
                        'the round; reopening to extend it.')
            pk = page.locator('.ant-modal-wrap:visible .ant-picker input').first
            if pk.count():
                pk.click()
                page.keyboard.press('Control+a')
                page.keyboard.type('2026-11-01 18:00:00')
                page.keyboard.press('Enter')
                page.wait_for_timeout(600)
            R.screen(page, 'x-closed-reopen-modal')
            vmodal(page).locator('.ant-modal-footer .ant-btn-primary').last.click()
            R.observe('reopen_toast', toast(page, 15))
            page.wait_for_timeout(4000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % gid)
        rnd = (rc['body'] or {}).get('round') or {}
        R.step('Reopen round puts the round back to open with a new deadline',
               'pass' if rnd.get('status') == 'open' else 'fail',
               'status=%s deadline=%s' % (rnd.get('status'),
                                          rnd.get('deadline')))
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        result2, after2 = press_extend(page, gid, 'on-an-open-round')
        R.step('Extend Deadline works once the round is open again',
               'pass' if (after2 or {}).get('status') == 'open'
               and (after2 or {}).get('deadline') != rnd.get('deadline')
               else 'fail',
               'before=%s after=%s' % (rnd.get('deadline'),
                                       (after2 or {}).get('deadline')))
        R.observe('page_text_tail', visible_text(page)[-600:])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
