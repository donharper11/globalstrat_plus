"""Read-only student tour: student_tour.py <lang> <team-index 1..8> <tag> [round]

Signs in as the first member of the team, visits every student screen that is
not a decision form (dashboard, notifications, news, research, competitors,
tools, financial reports, results, leaderboard, team activity, forecast) and
the decision screens themselves without changing anything. Used before play
and after every resolved round so that what a player sees is on record in
both languages. <tag> is prefixed to screen names (e.g. 'pre', 'after-r1').
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, fx, modal_text, sign_in,
                  sync_playwright, toast, visible_text)

LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
TAG = sys.argv[3]
ROUND = int(sys.argv[4]) if len(sys.argv) > 4 else None
G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[0]['username']
R = Recorder('student-tour-t%d-%s' % (TEAM_IX, TAG), LANG)
R.observe('student', STUDENT)
R.observe('team', team.get('team_name'))

SCREENS = [
    ('dashboard', '/'),
    ('news', '/games/%d/teams/%d/news'),
    ('research', '/games/%d/teams/%d/research'),
    ('competitors', '/games/%d/teams/%d/competitors'),
    ('tools', '/games/%d/teams/%d/tools'),
    ('financial-reports', '/games/%d/teams/%d/financial-reports'),
    ('forecast', '/games/%d/teams/%d/forecast'),
    ('team-activity', '/games/%d/teams/%d/team-activity'),
    ('results', '/games/%d/teams/%d/results'),
    ('leaderboard', '/games/%d/leaderboard'),
    ('d-rd', '/games/%d/teams/%d/decisions/rd'),
    ('d-products', '/games/%d/teams/%d/decisions/products'),
    ('d-marketing', '/games/%d/teams/%d/decisions/marketing'),
    ('d-corporate', '/games/%d/teams/%d/decisions/corporate-strategy'),
    ('d-market', '/games/%d/teams/%d/decisions/market-strategy'),
    ('d-finance', '/games/%d/teams/%d/decisions/finance'),
    ('d-communications', '/games/%d/teams/%d/decisions/communications'),
    ('d-summary', '/games/%d/teams/%d/decisions/summary'),
    ('d-sourcing', '/games/%d/teams/%d/decisions/sourcing'),
    ('d-logistics', '/games/%d/teams/%d/decisions/logistics'),
    ('d-trade-finance', '/games/%d/teams/%d/decisions/trade-finance'),
    ('d-inventory', '/games/%d/teams/%d/decisions/inventory'),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.goto(BASE + '/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(2000)
        R.screen(page, 's-%s-00-login' % TAG)
        ok = sign_in(page, '/login', STUDENT, LANG)
        R.step('student %s signs in' % STUDENT, 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.wait_for_timeout(3000)
        # Onboarding, if it appears, is a screen too.
        if modal_text(page):
            R.observe('post_login_modal', modal_text(page)[:800])
            R.screen(page, 's-%s-01-post-login-modal' % TAG)
            btn = page.locator('.ant-modal-footer .ant-btn-primary, .ant-modal-content button.ant-btn-primary')
            for _ in range(6):
                if btn.count() == 0 or not modal_text(page):
                    break
                btn.last.click(); page.wait_for_timeout(1200)
            if modal_text(page):
                page.keyboard.press('Escape'); page.wait_for_timeout(800)
        # Notifications bell, if present in the top bar.
        bell = page.locator('.anticon-bell').first
        if bell.count():
            bell.click(); page.wait_for_timeout(1500)
            R.screen(page, 's-%s-02-notifications' % TAG, 'notifications opened from the bell')
            page.keyboard.press('Escape'); page.wait_for_timeout(500)
        else:
            R.step('notifications control present in the top bar', 'fail', 'no bell icon found')
        for name, route in SCREENS:
            url = route % ((GID, TID) if route.count('%d') == 2 else ((GID,) if route.count('%d') == 1 else ()))
            page.goto(BASE + url, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            text = visible_text(page)
            R.observe('text_len_%s' % name, len(text))
            R.screen(page, 's-%s-10-%s' % (TAG, name))
            if len(text.strip()) < 40:
                R.step('screen %s renders' % name, 'fail', 'nearly empty page')
        if ROUND:
            page.goto(BASE + '/games/%d/teams/%d/results/%d' % (GID, TID, ROUND), wait_until='domcontentloaded')
            page.wait_for_timeout(6000)
            R.screen(page, 's-%s-11-results-round%d' % (TAG, ROUND))
            # Results tabs, each one.
            tabs = page.locator('.ant-tabs-tab')
            for i in range(min(tabs.count(), 8)):
                try:
                    label = tabs.nth(i).text_content().strip()
                    tabs.nth(i).click(); page.wait_for_timeout(2500)
                    R.screen(page, 's-%s-12-results-tab%d' % (TAG, i), label)
                except Exception as exc:
                    R.step('results tab %d' % i, 'fail', str(exc)[:120])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
