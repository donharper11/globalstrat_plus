"""Students & Logins: issue every missing student password in one go (EN).

Split out of instructor_setup.py because that driver's first attempt clicked
the per-row "Reset to ID" instead of the panel's "Set all to student ID".
"""
import json

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  popconfirm_ok, sign_in, sync_playwright, toast)

R = Recorder('instructor-bulk-reset', 'en')
G = json.loads((R.record['base'] and (__import__('pathlib').Path(__file__).resolve().parent / 'game.json')).read_text())


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        ok = sign_in(page, '/instructor/login', fx['instructor'], 'en')
        R.step('instructor signs in', 'pass' if ok else 'fail')
        page.goto(BASE + '/instructor', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G['course_code']).last.click(); page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click(); page.wait_for_timeout(5000)
        click_tab(page, 'Students & Logins'); page.wait_for_timeout(4000)
        b = page.locator('.ant-tabs-tabpane-active button', has_text='Set all to student ID')
        R.step('bulk reset control offered', 'pass' if b.count() else 'fail')
        b.first.click(); page.wait_for_timeout(1000)
        R.observe('popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
        popconfirm_ok(page, 5000)
        R.observe('toast', toast(page, 20))
        R.observe('modal', (modal_text(page) or '')[:600])
        page.wait_for_timeout(2000)
        R.screen(page, 'i24b-bulk-password-reset', 'after Set all to student ID')
        accts = api(page, 'GET', '/api/instructor/student-accounts/?game_id=%s' % G['game_id'])
        rows = (accts['body'] or {}).get('students') or []   # the first run read the wrong key and reported 0 accounts; records/student-accounts-after-bulk-reset.txt is the API evidence
        missing = [r for r in rows if r.get('needs_password')]
        R.step('every enrolled student can now log in', 'pass' if rows and not missing else 'fail',
               '%d accounts, %d still without a password; toast=%r' % (len(rows), len(missing), R.record['observed'].get('toast')))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
