"""W-CE2-08: the AI Coach alerts follow the instructor's own language.

verify_coach_language.py set      -- sign in to the console, click the header
                                     language switch to 中文, and confirm the
                                     SERVER stored it (before a round is
                                     processed; the alerts are written then)
verify_coach_language.py read <round>
                                  -- open the AI Coach panel and record the
                                     language of the alerts written for that
                                     round

Walkthrough 2 recorded 23 distinct English coach sentences whatever the
console's language, because `get_instructor_language(game)` read the game
creator's enrolment and an instructor made from the console has none — the
header switch changed the browser and nothing on the server.

The alerts are stored prose written in Phase 2 with no request in scope, so
they follow the instructor's stored preference AT THE MOMENT THE ROUND IS
PROCESSED. That is why this driver has two halves: the switch is clicked
before the round, the panel is read after it.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, click_tab, fx, sign_in, sync_playwright,
                  visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
PHASE = sys.argv[1]
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else None
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
LANG = 'zh-CN'
R = Recorder('verify-coach-language-%s%s' % (PHASE, '-r%d' % ROUND if ROUND else ''), LANG)


def han(text):
    return sum(1 for ch in (text or '') if '一' <= ch <= '鿿')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        # The console is entered in English, exactly as an instructor would,
        # and the switch is what changes the language.
        ok = sign_in(page, '/instructor/login', fx['instructor'], 'en')
        R.step('instructor signs in (in English)', 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)

        if PHASE == 'set':
            before = api(page, 'GET', '/api/user/preferences/')
            R.observe('preference_before', before)
            switch = page.locator('button', has_text='中文')
            R.observe('switch_controls', switch.count())
            R.step('the console header carries the language switch',
                   'pass' if switch.count() else 'fail', '%d controls' % switch.count())
            if switch.count():
                switch.first.click()
                page.wait_for_timeout(4000)
            local = page.evaluate("() => localStorage.getItem('gs_language')")
            after = api(page, 'GET', '/api/user/preferences/')
            R.observe('preference_after', after)
            R.observe('gs_language', local)
            R.step('the switch changes the interface', 'pass' if local == LANG else 'fail', local)
            R.step('the switch is recorded on the SERVER for an instructor with no enrolment (W-CE2-08)',
                   'pass' if after['status'] == 200
                   and (after['body'] or {}).get('language') == LANG else 'fail',
                   json.dumps(after)[:300])
            R.screen(page, 'v-coach-console-switched', 'the console after the switch to 中文')
        else:
            page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
            page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(6000)
            page.locator('.ant-card', has_text=G.get('course_code', 'CE26')).last.click()
            page.wait_for_timeout(3000)
            page.locator('.ant-card', has_text=G.get('section_code', 'CE26-A')).last.click()
            page.wait_for_timeout(6000)
            click_tab(page, 'AI 教练', 'AI Coach')
            page.wait_for_timeout(6000)
            R.screen(page, 'v-coach-panel-r%s' % ROUND, 'the AI Coach panel, console in Chinese')
            text = page.locator('.ant-tabs-tabpane-active').last.inner_text()
            R.observe('coach_panel_text', text[:3000])
            alerts = api(page, 'GET', '/api/games/%d/instructor/alerts/' % GID)
            R.observe('coach_api_status', alerts['status'])
            body = alerts['body'] if isinstance(alerts['body'], dict) else {}
            rows = body.get('alerts') or body.get('results') or []
            if isinstance(rows, list):
                mine = [a for a in rows if not ROUND or a.get('round_number') == ROUND]
            else:
                mine = []
            R.observe('alerts_for_round', mine[:20])
            sentences = [(a.get('title') or '') + ' ' + (a.get('detail') or '') for a in mine]
            chinese = [s for s in sentences if han(s)]
            R.step('the AI Coach wrote alerts for round %s' % ROUND,
                   'pass' if mine else 'fail', '%d alerts; api=%s' % (len(mine), alerts['status']))
            R.step('the alerts a Chinese-reading instructor reads are Chinese (W-CE2-08)',
                   'pass' if mine and len(chinese) == len(sentences) else 'fail',
                   '%d of %d alerts carry Chinese; first=%r'
                   % (len(chinese), len(sentences), sentences[0][:220] if sentences else None))
            R.step('the panel itself is Chinese', 'pass' if han(text) > 20 else 'fail',
                   '%d Han characters on the panel' % han(text))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
