"""Give the open round a deadline that has not already passed, from the console.

    extend_deadline.py <round> [hours] [lang]

WHY THIS DRIVER EXISTS. The seeded round schedule carries fixed late-September
dates, so in the 2026-10-06 candidate run every round after the first opened
*already closed*: the product correctly refused every write with "The deadline
for this round has passed", and rounds 2-3 therefore measured the deadline
refusal and nothing else (183 failed steps, none of them a product defect).

The repair is the instructor's own control, not a database edit: the console's
*Extend Deadline* button, whose route gives the full extension from `now` when
the stored deadline is already in the past
(`InstructorExtendDeadlineView`). Driving it per round means the fixture is
corrected THROUGH a product path that is itself under test, and the record
says so.

Idempotent and safe to call on a round whose deadline is already comfortably
ahead: it then records `observed` and presses nothing.

Writes records/extend-deadline-r<N>-<lang>.json.
"""
import datetime as dt
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  set_number, sign_in, sync_playwright, toast)

ROUND = int(sys.argv[1])
HOURS = int(sys.argv[2]) if len(sys.argv) > 2 else 24
LANG = sys.argv[3] if len(sys.argv) > 3 else 'en'
# The margin that makes a round playable. A round whose deadline is nearer than
# this gets the extension; four teams through every decision screen is a long
# wall-clock job and a deadline inside it would refuse writes mid-play.
MARGIN_HOURS = 6

G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
GID = G['game_id']
R = Recorder('extend-deadline-r%d' % ROUND, LANG)
L = {
    'en': {'control': 'Game Control', 'extend': 'Extend Deadline'},
    'zh-CN': {'control': '游戏控制', 'extend': '延长截止时间'},
}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def vmodal(page):
    return page.locator('.ant-modal-wrap:visible .ant-modal-content').last


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse(stamp):
    if not stamp:
        return None
    try:
        return dt.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError:
        return None


def hours_ahead(stamp):
    when = parse(stamp)
    if when is None:
        return None
    return round((when - now_utc()).total_seconds() / 3600.0, 2)


def round_control(page):
    return api(page, 'GET', '/api/games/%s/round-control/' % GID)['body'] or {}


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
        page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G['course_code']).last.click()
        page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click()
        page.wait_for_timeout(6000)
        click_tab(page, L['control'])
        page.wait_for_timeout(3500)

        before = round_control(page)
        rnd = before.get('round') or {}
        dl_before = rnd.get('deadline')
        ahead_before = hours_ahead(dl_before)
        R.observe('round_control_before', before)
        R.observe('deadline_before', {'deadline': dl_before,
                                      'hours_ahead': ahead_before,
                                      'status': rnd.get('status'),
                                      'round_number': rnd.get('round_number')})
        R.step('round %d is the open round' % ROUND,
               'pass' if rnd.get('round_number') == ROUND
               and rnd.get('status') == 'open' else 'fail',
               'round_number=%s status=%s' % (rnd.get('round_number'),
                                              rnd.get('status')))
        # The finding this driver answers, stated as a step so the record of
        # every round says whether the round opened already expired.
        R.step('the deadline round %d opened with' % ROUND, 'observed',
               'deadline=%s, %s hours from now%s'
               % (dl_before, ahead_before,
                  ' -- already expired when the round opened'
                  if (ahead_before or 0) <= 0 else ''))
        R.screen(page, 'x%d-00-before-extend' % ROUND,
                 'deadline %s (%sh ahead)' % (dl_before, ahead_before))

        if ahead_before is not None and ahead_before >= MARGIN_HOURS:
            R.step('deadline already %sh ahead, nothing extended'
                   % ahead_before, 'observed', dl_before)
            browser.close()
            return R.finish()

        btn = A(page).locator('button', has_text=L['extend']).first
        if not btn.count():
            btn = page.locator('button:visible', has_text=L['extend']).first
        R.step('the console offers Extend Deadline on the open round',
               'pass' if btn.count() else 'fail')
        if not btn.count():
            browser.close()
            return R.finish()
        btn.click()
        page.wait_for_timeout(1500)
        R.observe('extend_modal', modal_text(page))
        # The modal carries an hours InputNumber (1..168) and no reason box.
        num = vmodal(page).locator('.ant-input-number-input').first
        R.step('the extend modal asks for a number of hours',
               'pass' if num.count() else 'fail')
        if num.count():
            set_number(page, num, HOURS)
            page.wait_for_timeout(500)
        R.screen(page, 'x%d-01-extend-modal' % ROUND)
        vmodal(page).locator('.ant-modal-footer .ant-btn-primary').last.click()
        R.observe('extend_toast', toast(page, 30))
        page.wait_for_timeout(3500)
        after_modal = modal_text(page)
        R.observe('extend_result_modal', after_modal)

        after = round_control(page)
        rnd2 = after.get('round') or {}
        dl_after = rnd2.get('deadline')
        ahead_after = hours_ahead(dl_after)
        R.observe('deadline_after', {'deadline': dl_after,
                                     'hours_ahead': ahead_after,
                                     'status': rnd2.get('status')})
        R.step('Extend Deadline moved round %d past now' % ROUND,
               'pass' if ahead_after is not None
               and ahead_after >= MARGIN_HOURS else 'fail',
               'before=%s (%sh) after=%s (%sh) toast=%r modal=%r'
               % (dl_before, ahead_before, dl_after, ahead_after,
                  R.record['observed'].get('extend_toast'), after_modal))
        R.step('the round is still open after the extension',
               'pass' if rnd2.get('status') == 'open' else 'fail',
               'status=%s round_number=%s' % (rnd2.get('status'),
                                              rnd2.get('round_number')))
        R.step('extending did not unlock a submission',
               'pass' if not rnd2.get('reopened') else 'fail',
               'teams_locked=%s/%s' % (rnd2.get('teams_locked'),
                                       rnd2.get('teams_total')))
        if after_modal and ('Error' in after_modal or '错误' in after_modal):
            page.keyboard.press('Escape')
            page.wait_for_timeout(500)
            okb = page.locator('.ant-modal-confirm-btns .ant-btn-primary')
            if okb.count():
                okb.last.click()
                page.wait_for_timeout(500)
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        R.screen(page, 'x%d-02-after-extend' % ROUND,
                 'deadline %s (%sh ahead)' % (dl_after, ahead_after))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
