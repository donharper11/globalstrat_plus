"""Set the open round's deadline to a future time, from the console.

The schedule `instructor_setup.py` generates starts at a fixed 2026-09-22, so
every round after the first opens with a deadline that has already passed.
The product then correctly refuses every write -- *"The deadline for this
round has passed. Your decisions are locked."* -- and a walkthrough that plays
into that measures the refusal and nothing else. Rounds 2 and 3 of the
2026-10-06 candidate run produced 183 failed steps for exactly this reason,
against zero in round 1, whose deadline was in the future.

This runs before the teams play. It uses the console's own *Set deadline*
control rather than writing the row, so the operator path is exercised, and
it sets an absolute time rather than clicking *Extend Deadline* repeatedly --
a round six days overdue would need seven clicks, and the point is a
deliberate deadline, not an accumulation.

    set_round_deadline.py <round> [hours-ahead]
"""
import datetime as dt
import json
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text, sign_in,
                  sync_playwright, toast)

ROUND = int(sys.argv[1])
HOURS = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
R = Recorder('set-deadline-r%d' % ROUND, 'en')
import pathlib

G = json.loads((pathlib.Path(__file__).resolve().parent
                / 'game.json').read_text())
GID = G['game_id']


def card(page, text):
    return page.locator('.ant-card', has_text=text).first


def main():
    target = (dt.datetime.now(dt.timezone.utc)
              + dt.timedelta(hours=HOURS)).astimezone()
    typed = target.strftime('%Y-%m-%d %H:%M:%S')
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        if not sign_in(page, '/instructor/login', fx['instructor'], 'en', rec=R):
            R.step('instructor signs in', 'fail', 'sign-in refused')
            browser.close()
            return R.finish()
        R.step('instructor signs in', 'pass', '')
        # Same route the round driver takes: the Round control card only
        # exists once a section's console is open on its control tab.
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G['course_code']).last.click()
        page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click()
        page.wait_for_timeout(6000)
        click_tab(page, 'Game Control')
        page.wait_for_timeout(4000)

        before = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        dl_before = (before['body'].get('round') or {}).get('deadline')
        rnd_before = (before['body'].get('round') or {}).get('round_number')
        R.step('the open round is the one being given a deadline',
               'pass' if rnd_before == ROUND else 'fail',
               'console reports round %s, asked for %s' % (rnd_before, ROUND))

        rcc = card(page, 'Round control')
        btn = rcc.locator('button', has_text='deadline').first
        if not btn.count():
            R.step('set-deadline control is offered', 'fail', 'no button')
            browser.close()
            return R.finish()
        R.step('set-deadline control is offered', 'pass', '1')
        btn.click()
        page.wait_for_timeout(1200)
        R.observe('deadline_modal', modal_text(page))
        picker = page.locator('.ant-modal-content .ant-picker input').first
        picker.click()
        page.keyboard.press('Control+a')
        page.keyboard.type(typed)
        page.keyboard.press('Enter')
        page.wait_for_timeout(600)
        R.screen(page, 'deadline-r%d-modal' % ROUND)
        page.locator('.ant-modal-footer .ant-btn-primary').last.click()
        R.observe('deadline_toast', toast(page))
        page.wait_for_timeout(3000)

        after = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        dl_after = (after['body'].get('round') or {}).get('deadline')
        R.observe('deadline_before', dl_before)
        R.observe('deadline_after', dl_after)
        moved = bool(dl_after) and dl_after != dl_before
        future = False
        if dl_after:
            parsed = dt.datetime.fromisoformat(dl_after.replace('Z', '+00:00'))
            future = parsed > dt.datetime.now(dt.timezone.utc)
        R.step('round %d deadline set from the console' % ROUND,
               'pass' if moved else 'fail',
               'before=%s after=%s typed=%s' % (dl_before, dl_after, typed))
        R.step('round %d deadline is now in the future' % ROUND,
               'pass' if future else 'fail', 'after=%s' % dl_after)
        R.screen(page, 'deadline-r%d-set' % ROUND)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
