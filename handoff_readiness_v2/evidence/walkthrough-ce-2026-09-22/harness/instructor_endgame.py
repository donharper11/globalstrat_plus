"""After the last played round: grading again, then the destructive flows.

instructor_endgame.py <lang>

  1. Grading & Export: Calculate Grades on 4 rounds of results, exports.
  2. Delete Game (reason) on a game that has a record -> must be refused.
  3. mark_competition.py marks the heat (the console cannot); Delete Game
     again -> must be refused as a competition heat.
  4. Reset to Setup (reason) -> what happens is recorded.
  5. Archive Game (reason) -> what happens is recorded.
"""
import json
import pathlib
import subprocess
import sys

from walk import (BASE, EVIDENCE, SCRATCH, Recorder, api, click_tab, fx,
                  modal_text, pick_select, sign_in, sync_playwright, toast)

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('instructor-endgame', LANG)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales' / ('%s.json' % LANG)).read_text())


def T(key):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    return cur


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def reasoned(page, label, reason, name):
    """Click a ReasonedAction button, type the reason, confirm; return toast."""
    click_tab(page, T('instructor.game_control')); page.wait_for_timeout(2500)
    b = A(page).locator('button', has_text=label)
    vis = [i for i in range(b.count()) if b.nth(i).is_visible()]
    if not vis:
        R.step('%s offered' % name, 'fail', 'button not on screen'); return None
    b.nth(vis[0]).click(); page.wait_for_timeout(1000)
    R.observe('%s_modal' % name, modal_text(page))
    page.locator('.ant-modal-wrap:visible textarea').first.fill(reason)
    page.wait_for_timeout(500)
    R.screen(page, 'end-%s-modal' % name)
    page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary').last.click()
    t = toast(page, 25)
    R.observe('%s_toast' % name, t)
    page.wait_for_timeout(3000)
    R.screen(page, 'end-%s-after' % name)
    return t


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        page.goto(BASE + '/instructor', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G['course_code']).last.click(); page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click(); page.wait_for_timeout(6000)

        # 1. grading on real results
        click_tab(page, T('instructor.grading_export')); page.wait_for_timeout(3000)
        pick_select(page, A(page).locator('.ant-select').nth(0), G['course_code']); page.wait_for_timeout(1200)
        pick_select(page, A(page).locator('.ant-select').nth(1), G['section_code']); page.wait_for_timeout(2500)
        cg = A(page).locator('button', has_text=T('instructor.calculate_grades'))
        if cg.count() and cg.first.is_enabled():
            cg.first.click(); R.observe('calc_toast', toast(page, 15)); page.wait_for_timeout(3000)
        R.screen(page, 'end-grading-after-4-rounds')
        rows = A(page).locator('table').nth(2).locator('tbody tr')
        grades = [rows.nth(i).text_content() for i in range(min(rows.count(), 8))]
        R.observe('grade_rows', grades)
        dash = api(page, 'GET', '/api/games/%s/instructor/dashboard/' % GID)['body']
        R.observe('dashboard_teams', [(t.get('team_name'), t.get('performance_index')) for t in (dash.get('teams') or [])])
        R.step('grades calculated on played rounds', 'pass' if grades and any(g for g in grades) else 'fail', '%s | %s' % (R.record['observed'].get('calc_toast'), grades[:3]))
        for label in (T('instructor.export_team_summary'), T('instructor.export_team_grades'), T('instructor.export_student_grades')):
            b = A(page).locator('button', has_text=label)
            try:
                with page.expect_download(timeout=8000) as dl:
                    b.first.click()
                d = dl.value
                path = EVIDENCE / 'exports' / ('final-' + d.suggested_filename)
                d.save_as(str(path))
                R.step('export after 4 rounds: %s' % label, 'pass', '%s (%d bytes)' % (path.name, path.stat().st_size))
            except Exception as exc:
                R.step('export after 4 rounds: %s' % label, 'fail', str(exc)[:120])

        # 2. delete on a game with a record
        t = reasoned(page, T('instructor.delete_game'), 'Walkthrough: attempting to delete a game that has a record.', 'delete-has-record')
        still = api(page, 'GET', '/api/games/%s/round-control/' % GID)['status']
        R.step('delete refused for a game with a record (game still exists)', 'pass' if still == 200 and t and ('record' in t or '记录' in t) else 'fail', 'toast=%r round-control=%s' % (t, still))

        # 3. mark as a competition heat (no console control exists), delete again
        mk = subprocess.run([sys.executable, str(SCRATCH / 'mark_competition.py'), str(GID)], capture_output=True, text=True)
        R.observe('mark_competition', (mk.stdout + mk.stderr)[-400:])
        t = reasoned(page, T('instructor.delete_game'), 'Walkthrough: attempting to delete a competition heat.', 'delete-competition')
        still = api(page, 'GET', '/api/games/%s/round-control/' % GID)['status']
        R.step('delete refused for a competition heat (game still exists)', 'pass' if still == 200 and t and ('competition' in t or '竞赛' in t) else 'fail', 'toast=%r round-control=%s' % (t, still))
        click_tab(page, T('instructor.operator_log')); page.wait_for_timeout(3500)
        R.screen(page, 'end-operator-log-refusals')

        # 4. reset to setup
        t = reasoned(page, T('instructor.reset_to_setup'), 'Walkthrough: resetting the heat at the end of the audit.', 'reset')
        st = api(page, 'GET', '/api/games/?section_id=%s' % G['section_id'])['body']
        g = next((x for x in (st.get('games') or []) if x.get('game_id') == GID), {})
        R.observe('game_after_reset', g)
        R.step('reset outcome recorded', 'observed', 'toast=%r status=%s current_round=%s' % (t, g.get('status'), g.get('current_round')))

        # 5. archive
        t = reasoned(page, T('instructor.archive_game'), 'Walkthrough: archiving the heat at the end of the audit.', 'archive')
        st = api(page, 'GET', '/api/games/?section_id=%s' % G['section_id'])['body']
        g = next((x for x in (st.get('games') or []) if x.get('game_id') == GID), {})
        R.observe('game_after_archive', g)
        R.step('archive outcome recorded', 'observed', 'toast=%r status=%s' % (t, g.get('status')))
        click_tab(page, T('instructor.courses_sections')); page.wait_for_timeout(3000)
        R.screen(page, 'end-courses-after-archive', 'the section after archiving its game')
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
