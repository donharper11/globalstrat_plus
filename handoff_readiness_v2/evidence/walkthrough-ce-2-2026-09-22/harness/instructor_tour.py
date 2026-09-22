"""Read-only instructor tour: instructor_tour.py <lang> <tag>

Visits every console tab and opens every confirmation and modal without
committing anything (Escape / Cancel), so each screen an instructor can reach
is on record in the given language. Used for zh-CN and after each round.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  sign_in, sync_playwright)

LANG = sys.argv[1]
TAG = sys.argv[2] if len(sys.argv) > 2 else 'tour'
G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
GID = G['game_id']
R = Recorder('instructor-tour-%s' % TAG, LANG)
WT = pathlib.Path(__file__).resolve().parents[4]
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


def popover_text(page):
    el = page.locator('.ant-popover:not(.ant-popover-hidden)')
    return el.last.text_content() if el.count() else None


def open_and_cancel_button(page, label, name, kind='popconfirm'):
    b = A(page).locator('button', has_text=label)
    vis = [i for i in range(b.count()) if b.nth(i).is_visible() and b.nth(i).is_enabled()]
    if not vis:
        R.step('%s control offered' % name, 'observed', 'not offered in this state')
        return
    try:
        b.nth(vis[0]).click(timeout=8000); page.wait_for_timeout(1000)
    except Exception as exc:
        R.step('%s control clickable' % name, 'fail', str(exc)[:160]); return
    text = popover_text(page) if kind == 'popconfirm' else modal_text(page)
    R.observe('confirm:%s' % name, text)
    R.screen(page, '%s-%s' % (TAG, name), 'confirmation opened and cancelled')
    page.keyboard.press('Escape'); page.wait_for_timeout(700)
    cancel = page.locator('.ant-modal-wrap:visible .ant-modal-footer button').first
    if modal_text(page) and cancel.count():
        cancel.click(timeout=5000); page.wait_for_timeout(600)
    if modal_text(page):
        x = page.locator('.ant-modal-close').last
        if x.count():
            x.click(); page.wait_for_timeout(500)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        page.goto(BASE + '/instructor/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(2000)
        R.screen(page, '%s-i00-login' % TAG)
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        page.goto(BASE + '/instructor', wait_until='domcontentloaded'); page.wait_for_timeout(3500)
        R.screen(page, '%s-i01-courses' % TAG)
        page.locator('.ant-card', has_text=G['course_code']).last.click(); page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click(); page.wait_for_timeout(6000)
        R.screen(page, '%s-i02-section-roster' % TAG)
        # Roster edit row + bulk upload collapse opened (not submitted)
        page.locator('.ant-collapse-header').first.click(); page.wait_for_timeout(800)
        R.screen(page, '%s-i03-roster-bulk-upload' % TAG)
        # Assignment picker opened
        sel = page.locator('.ant-card', has_text=T('instructor.select_team_pick_students')).first.locator('.ant-select').first
        if sel.count():
            sel.click(); page.wait_for_timeout(800)
            R.screen(page, '%s-i04-assign-picker-open' % TAG)
            page.keyboard.press('Escape'); page.wait_for_timeout(400)
        # Game control
        click_tab(page, T('instructor.game_control')); page.wait_for_timeout(4000)
        R.screen(page, '%s-i10-game-control' % TAG)
        open_and_cancel_button(page, T('instructor.pause_game'), 'i11-pause-confirm')
        open_and_cancel_button(page, T('instructor.extend_deadline'), 'i12-extend-modal', 'modal')
        click_tab(page, T('instructor.game_control')); page.wait_for_timeout(1500)
        open_and_cancel_button(page, T('instructor.advance_round'), 'i13-advance-modal', 'modal')
        click_tab(page, T('instructor.game_control')); page.wait_for_timeout(1500)
        open_and_cancel_button(page, T('instructor.reset_to_setup'), 'i14-reset-modal', 'modal')
        open_and_cancel_button(page, T('instructor.archive_game'), 'i15-archive-modal', 'modal')
        open_and_cancel_button(page, T('instructor.delete_game'), 'i16-delete-modal', 'modal')
        rcc = page.locator('.ant-card', has_text=T('instructor.rc_close_now')).first
        open_and_cancel_button(page, T('instructor.rc_close_now'), 'i17-close-round-confirm')
        open_and_cancel_button(page, T('instructor.rc_close_and_process'), 'i18-close-and-process-modal', 'modal')
        open_and_cancel_button(page, T('instructor.rc_change_deadline'), 'i19-change-deadline-modal', 'modal')
        exp = A(page).locator('button', has_text=T('instructor.expand'))
        if exp.count():
            exp.first.click(); page.wait_for_timeout(2500)
            R.screen(page, '%s-i20-team-configuration' % TAG)
        for key, name in (('accounts', 'i21-students-logins'), ('grading', 'i22-grading'), ('teams', 'i23-team-overview'),
                          ('operator_log', 'i24-operator-log'), ('supply_chain', 'i25-supply-chain'), ('events', 'i26-event-manager'),
                          ('briefings', 'i27-briefings'), ('research', 'i28-research-monitor'), ('alerts', 'i29-ai-coach')):
            label = {'accounts': T('instructor.students_logins'), 'grading': T('instructor.grading_export'), 'teams': T('instructor.team_overview'),
                     'operator_log': T('instructor.operator_log'), 'supply_chain': T('instructor.supply_chain'), 'events': T('instructor.event_manager'),
                     'briefings': T('instructor.briefings'), 'research': T('instructor.research_monitor'), 'alerts': T('instructor.ai_coach')}[key]
            if not click_tab(page, label):
                R.step('reach tab %s (%s)' % (key, label), 'fail', 'tab not found'); continue
            page.wait_for_timeout(3500)
            if key == 'grading':
                A(page).locator('.ant-select').nth(0).click(); page.wait_for_timeout(600)
                opt = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option').first
                if opt.count(): opt.click(); page.wait_for_timeout(1200)
                A(page).locator('.ant-select').nth(1).click(); page.wait_for_timeout(600)
                opt = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option').first
                if opt.count(): opt.click(); page.wait_for_timeout(2500)
            R.screen(page, '%s-%s' % (TAG, name))
            if key == 'grading':
                e = A(page).locator('button', has_text=T('instructor.edit_rubric'))
                if e.count():
                    e.first.click(); page.wait_for_timeout(1000); R.screen(page, '%s-i22b-rubric-editor' % TAG); page.keyboard.press('Escape'); page.wait_for_timeout(500)
            if key == 'teams':
                v = A(page).locator('button', has_text=T('instructor.view_decisions'))
                if v.count():
                    v.first.click(); page.wait_for_timeout(3000); R.screen(page, '%s-i23b-decision-drill' % TAG); page.keyboard.press('Escape'); page.wait_for_timeout(500)
            if key == 'events':
                open_and_cancel_button(page, T('instructor.inject_event'), 'i26b-inject-event-modal', 'modal')
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
