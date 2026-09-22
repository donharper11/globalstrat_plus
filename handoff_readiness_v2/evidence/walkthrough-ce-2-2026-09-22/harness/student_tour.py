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
        ok = sign_in(page, '/login', STUDENT, LANG, password=members[0].get('student_id') or STUDENT)
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
        # Any modal still open (onboarding, a briefing) is dismissed first: it
        # would swallow the clicks the two checks below make.
        for _ in range(6):
            if not modal_text(page):
                break
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if b.count():
                b.last.click(); page.wait_for_timeout(1200)
            else:
                page.keyboard.press('Escape'); page.wait_for_timeout(800)
        R.observe('modal_still_open_before_topbar_checks', modal_text(page))
        # W-CE-10: the decorative bell was removed. If one is present it must
        # do something; if none is present that is the repair, recorded.
        bell = page.locator('.anticon-bell')
        R.observe('bell_icons_in_topbar', bell.count())
        if bell.count():
            before = page.url
            bell.first.click(); page.wait_for_timeout(1500)
            opened = bool(modal_text(page)) or page.url != before or page.locator('.ant-dropdown:visible, .ant-popover:not(.ant-popover-hidden)').count() > 0
            R.screen(page, 's-%s-02-notifications' % TAG, 'the bell was clicked')
            R.step('the top-bar bell does something when clicked', 'pass' if opened else 'fail',
                   'url=%s modal=%r' % (page.url, (modal_text(page) or '')[:120]))
            page.keyboard.press('Escape'); page.wait_for_timeout(500)
        else:
            R.step('no decorative bell in the student top bar (W-CE-10)', 'pass', 'no bell icon in the shell')
        # W-CE-11: the language switch inside the game.
        topbar_text = visible_text(page)[:400]
        R.observe('topbar_text', topbar_text)
        sw = page.locator('header button, .ant-layout-header button').filter(has_text='中文') if LANG == 'en' else page.locator('header button, .ant-layout-header button').filter(has_text='EN')
        alt = page.locator('button', has_text='中文' if LANG == 'en' else 'EN')
        switch = sw if sw.count() else alt
        R.observe('language_switch_buttons', switch.count())
        if switch.count():
            switch.first.click(); page.wait_for_timeout(2500)
            after_lang = page.evaluate("() => localStorage.getItem('gs_language')")
            R.observe('language_after_switch', after_lang)
            R.screen(page, 's-%s-03-language-switched' % TAG, 'after the in-game language switch')
            R.step('a student can change language inside the game (W-CE-11)',
                   'pass' if after_lang and not after_lang.startswith(LANG.split('-')[0]) else 'fail',
                   'gs_language now %r' % after_lang)
            # back to the language this tour is recording
            switch2 = page.locator('button', has_text='EN' if LANG == 'en' else '中文')
            if switch2.count():
                switch2.first.click(); page.wait_for_timeout(2500)
            R.observe('language_restored', page.evaluate("() => localStorage.getItem('gs_language')"))
        else:
            R.step('a student can change language inside the game (W-CE-11)', 'fail',
                   'no language control in the student shell')
        for name, route in SCREENS:
            url = route % ((GID, TID) if route.count('%d') == 2 else ((GID,) if route.count('%d') == 1 else ()))
            page.goto(BASE + url, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            text = visible_text(page)
            R.observe('text_len_%s' % name, len(text))
            R.screen(page, 's-%s-10-%s' % (TAG, name))
            if len(text.strip()) < 40:
                R.step('screen %s renders' % name, 'fail', 'nearly empty page')
            if name == 'team-activity':
                calls = [c for c in R.record['api'] if '/changes/' in str(c.get('url'))]
                R.observe('team_activity_text', text[:400])
                R.observe('team_activity_changes_calls', calls)
                R.step('no student page calls the instructor-only changes route (W-CE-09)',
                       'pass' if not calls else 'fail', json.dumps(calls)[:300])
                nav = visible_text(page)
                R.observe('sidebar_has_team_activity',
                          'Team Activity' in nav or '\u56e2\u961f\u52a8\u6001' in nav)
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
