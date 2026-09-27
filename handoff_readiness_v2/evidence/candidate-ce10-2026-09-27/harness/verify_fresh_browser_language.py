"""What a Chinese-speaking player gets on a browser that has never been used.

    verify_fresh_browser_language.py <username> [password] [expected-lang]

The platform now writes a person's language to the server: the login page's
switch, the in-game switch and `AuthContext.login` all reach
`PUT /api/user/preferences/`, and the enrolment row is what the analyst, the
Phase 2 prose and the team documents are written in (R43).

This asks the other half of the question, which no earlier walkthrough asked:
**is the stored language ever read back?** The browser is opened clean --
nothing in `localStorage`, no `gs_language`, exactly what a student gets at a
different machine on the second day of a heat -- the person signs in, and the
driver records

  * what the server says their language is,
  * what `localStorage.gs_language` holds afterwards,
  * what language the interface is actually in, and
  * what language the server-rendered prose comes back in (the AI Coach for
    an instructor, the dashboard and the round results for a student), which
    follows the `Accept-Language` header `api/client.js` builds from that
    same empty `localStorage`.

Nothing is changed: the driver never presses the switch.
"""
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, modal_text, server_language,
                  sync_playwright, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
USERNAME = sys.argv[1]
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else USERNAME
EXPECTED = sys.argv[3] if len(sys.argv) > 3 else 'zh-CN'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('fresh-browser-%s' % USERNAME, EXPECTED)
HAN = re.compile(r'[一-鿿]')
member = next((r for r in G['roster'] if r.get('username') == USERNAME), None)
TID = (member or {}).get('team_id')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        context = browser.new_context(viewport={'width': 1500, 'height': 1000},
                                      locale='en-US')
        page = context.new_page()
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        route = '/login' if member else '/instructor/login'
        page.goto(BASE + route, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        R.observe('gs_language_before_sign_in',
                  page.evaluate("() => localStorage.getItem('gs_language')"))
        R.screen(page, 'v4-fresh-%s-01-login' % USERNAME,
                 'a browser that has never been used, nothing in localStorage')
        page.fill('input#username, input[name="username"]', USERNAME)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(6000)
        signed_in = bool(page.evaluate("() => localStorage.getItem('access_token')"))
        R.step('%s signs in on a clean browser' % USERNAME,
               'pass' if signed_in else 'fail')
        if not signed_in:
            browser.close()
            return R.finish()
        server = server_language(page)
        stored = page.evaluate("() => localStorage.getItem('gs_language')")
        R.observe('server_language', server)
        R.observe('gs_language_after_sign_in', stored)
        R.step('the server still holds this person\'s language',
               'pass' if server == EXPECTED else 'fail',
               'server says %r, expected %r' % (server, EXPECTED))
        first = modal_text(page) or ''
        if first:
            R.observe('post_login_modal', first[:1500])
            R.screen(page, 'v4-fresh-%s-02-post-login-modal' % USERNAME)
            R.step('the first screen after sign-in is in the language the '
                   'server holds for this person',
                   'pass' if bool(HAN.search(first)) == EXPECTED.startswith('zh')
                   else 'fail',
                   '%d Chinese characters in the modal; it begins %r'
                   % (len(HAN.findall(first)), first[:160]))
            for _ in range(6):
                if not modal_text(page):
                    break
                b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
                if b.count():
                    b.last.click()
                    page.wait_for_timeout(1200)
                else:
                    page.keyboard.press('Escape')
                    page.wait_for_timeout(800)
        if TID:
            page.goto(BASE + '/games/%d/teams/%d/decisions/finance' % (GID, TID),
                      wait_until='domcontentloaded')
        else:
            page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        text = visible_text(page)
        R.observe('interface_text', text[:1200])
        R.screen(page, 'v4-fresh-%s-03-interface' % USERNAME)
        han = len(HAN.findall(text))
        R.step('the interface is in the language the server holds',
               'pass' if (han > 30) == EXPECTED.startswith('zh') else 'fail',
               '%d Chinese characters on the screen; localStorage.gs_language '
               'is %r, and nothing in the product ever sets it from the '
               'language the server holds' % (han, stored))
        # Server-rendered prose, fetched the way the page fetches it.
        if TID:
            got = api(page, 'GET', '/api/games/%d/teams/%d/results/round/1/'
                      % (GID, TID))
        else:
            got = api(page, 'GET', '/api/games/%d/instructor/alerts/' % GID)
        blob = json.dumps(got.get('body'), ensure_ascii=False)
        R.observe('served_prose_sample', blob[:800])
        served_han = len(HAN.findall(blob))
        R.step('the prose the server renders comes back in that language too',
               'pass' if (served_han > 20) == EXPECTED.startswith('zh')
               else 'fail',
               '%d Chinese characters in the served payload' % served_han)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
