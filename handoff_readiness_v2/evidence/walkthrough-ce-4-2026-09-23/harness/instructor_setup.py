"""Part 1, in English: the instructor builds the whole game from the console.

course -> section -> game (8 teams) -> roster CSV -> team assignment (with a
refused sixth member) -> team configuration -> activate -> schedule ->
deadline -> extend -> pause/resume -> operator event -> student logins ->
grading tab -> every remaining panel. Mutating, so it runs ONCE. Writes
game.json for the later drivers.
"""
import json
import sys
import time

from walk import (BASE, EVIDENCE, SCRATCH, Recorder, api, body_text,
                  click_tab, fx, modal_text, pick_select, popconfirm_ok,
                  set_number, sign_in, sync_playwright, toast)

LANG = 'en'
R = Recorder('instructor-setup', LANG)
COURSE_CODE, COURSE_NAME = 'CE26', 'Global Strategy Practicum'
SECTION_CODE, SECTION_NAME = 'CE26-A', 'Heat A'
GAME_NAME = 'CE 2026 Heat A'


def A(page):
    """AntD keeps inactive tab panes mounted (hidden): scope to the active one."""
    return page.locator('.ant-tabs-tabpane-active')


def card(page, text):
    return page.locator('.ant-card', has_text=text).first


def vmodal(page):
    """The modal that is actually open: AntD leaves closed ones mounted."""
    return page.locator('.ant-modal-wrap:visible .ant-modal-content').last


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)

        page.goto(BASE + '/instructor/login', wait_until='domcontentloaded')
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        R.screen(page, 'i00-instructor-login')
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG, rec=R)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        existing = api(page, 'GET', '/api/games/')
        glist0 = (existing['body'] or {}).get('games') or []
        resumed = any(x.get('game_name') == GAME_NAME for x in glist0)
        R.observe('resumed', resumed)
        if resumed:
            page.locator('.ant-card', has_text=COURSE_CODE).last.click(); page.wait_for_timeout(2500)
            page.locator('.ant-card', has_text=SECTION_CODE).last.click(); page.wait_for_timeout(5000)
            GID = next(x['game_id'] for x in glist0 if x.get('game_name') == GAME_NAME)
            R.step('resumed on the existing game', 'observed', 'game %s; creation steps were recorded by the first run' % GID)
        else:
            GID = build(page)
            if GID is None:
                browser.close(); return R.finish()
        control(page, GID, resumed)
        browser.close()
    return R.finish()


def build(page):
    if True:
        R.screen(page, 'i01-console-empty', 'no course yet')

        # ---- course ------------------------------------------------------
        c = card(page, 'My Courses')
        c.locator('input').nth(0).fill(COURSE_CODE)
        c.locator('input').nth(1).fill(COURSE_NAME)
        c.locator('button', has_text='Create').first.click()
        R.observe('course_toast', toast(page))
        page.wait_for_timeout(2500)
        page.locator('.ant-card', has_text=COURSE_CODE).last.click()
        page.wait_for_timeout(2500)
        R.step('course created and selected', 'pass' if COURSE_CODE in body_text(page) else 'fail', R.record['observed'].get('course_toast'))
        R.screen(page, 'i02-course-created')

        # ---- section -----------------------------------------------------
        s = card(page, 'Sections')
        s.locator('input').nth(0).fill(SECTION_CODE)
        s.locator('input').nth(1).fill(SECTION_NAME)
        s.locator('button', has_text='Create').first.click()
        R.observe('section_toast', toast(page))
        page.wait_for_timeout(2500)
        page.locator('.ant-card', has_text=SECTION_CODE).last.click()
        page.wait_for_timeout(4000)
        R.step('section created and selected', 'pass' if 'Managing' in body_text(page) else 'fail', R.record['observed'].get('section_toast'))
        R.screen(page, 'i03-section-selected', 'Step 1 create-a-game card should show')

        # ---- game --------------------------------------------------------
        g = card(page, 'Step 1: Create a Game')
        label = pick_select(page, g.locator('.ant-select').first, 'Consumer Electronics')
        R.step('scenario picked', 'pass' if label else 'fail', label)
        page.wait_for_timeout(1500)
        g.locator('input.ant-input').first.fill(GAME_NAME)
        set_number(page, g.locator('.ant-input-number-input').first, 8)
        R.screen(page, 'i04-create-game-form')
        g.locator('button', has_text='Create Game & Teams').first.click()
        t = toast(page)
        R.observe('create_game_toast', t)
        page.wait_for_timeout(5000)
        games = api(page, 'GET', '/api/games/?section_id=%s' % section_id(page))
        R.observe('games_after_create', games)
        glist = (games['body'] or {}).get('games') or []
        game = next((x for x in glist if x.get('name') == GAME_NAME or x.get('game_name') == GAME_NAME), glist[0] if glist else None)
        R.step('game created with 8 teams from the console',
               'pass' if game and t and '8 teams' in (t or '') else 'fail',
               'toast=%r game=%s' % (t, json.dumps(game)[:300] if game else None))
        R.screen(page, 'i05-game-created', 'roster + team assignment cards should appear')
        if not game:
            return None
        GID = game.get('game_id') or game.get('id')

        # ---- roster CSV --------------------------------------------------
        page.locator('.ant-collapse-header', has_text='Bulk Upload (CSV)').first.click()
        page.wait_for_timeout(800)
        page.locator('input[type="file"]').first.set_input_files(str(SCRATCH / 'roster.csv'))
        page.wait_for_timeout(4000)
        up_modal = modal_text(page)
        up_toast = toast(page, 10)
        panel_txt = None
        try:
            alerts = page.locator('.ant-alert:visible')
            panel_txt = ' | '.join((alerts.nth(i).inner_text() or '').replace('\n', ' ')
                                   for i in range(alerts.count()))[:600]
        except Exception as exc:
            panel_txt = 'unreadable: %s' % str(exc)[:80]
        R.observe('roster_upload_modal', up_modal)
        R.observe('roster_upload_toast', up_toast)
        R.observe('roster_upload_panel', panel_txt)
        R.step('the roster upload announces its outcome',
               'pass' if (panel_txt and any(ch.isdigit() for ch in panel_txt)) or up_modal or up_toast else 'fail',
               'panel=%r modal=%r toast=%r' % (panel_txt, (up_modal or '')[:120], up_toast))
        R.screen(page, 'i06-roster-uploaded', 'upload outcome as announced')
        if up_modal:
            page.keyboard.press('Escape'); page.wait_for_timeout(800)
            okb = page.locator('.ant-modal-confirm-btns .ant-btn-primary, .ant-modal-footer .ant-btn-primary')
            if okb.count():
                okb.last.click(); page.wait_for_timeout(800)
        roster = api(page, 'GET', '/api/roster/?section_id=%s' % section_id(page))
        rows = roster['body'] if isinstance(roster['body'], list) else []
        R.step('roster CSV upload enrolled 27 students', 'pass' if len(rows) == 27 else 'fail',
               'enrolled=%d modal=%r toast=%r' % (len(rows), (up_modal or '')[:200], up_toast))

        # ---- team assignment ---------------------------------------------
        teams_api = api(page, 'GET', '/api/games/%s/teams/' % GID)
        R.observe('teams', teams_api['body'])
        tlist = teams_api['body'].get('teams') if isinstance(teams_api['body'], dict) else teams_api['body']
        tlist = tlist or []
        picker = card(page, 'Select a team')
        refused_seen = None
        for i, team in enumerate(tlist):
            want = 6 if i == 0 else 3        # sixth member of team 1 must be refused
            pick_select(page, picker.locator('.ant-select').first, team.get('team_name') or team.get('name'))
            page.wait_for_timeout(1200)
            for n in range(want):
                arrow = page.locator('.ant-card', has_text='Unassigned Students').first.locator('button', has_text='→')
                if arrow.count() == 0:
                    R.step('assign member %d of %s' % (n + 1, team.get('team_name')), 'fail', 'no unassigned pool button')
                    break
                arrow.first.click()
                page.wait_for_timeout(1800)
                if i == 0 and n == 5:
                    refused_seen = {'toast': toast(page, 15), 'modal': modal_text(page)}
                    R.screen(page, 'i07-sixth-member-refused', 'the refusal an instructor sees')
                    if refused_seen['modal']:
                        okb = page.locator('.ant-modal-confirm-btns .ant-btn-primary, .ant-modal-footer .ant-btn-primary')
                        if okb.count(): okb.last.click(); page.wait_for_timeout(800)
            page.wait_for_timeout(800)
        roster = api(page, 'GET', '/api/roster/?section_id=%s' % section_id(page))
        rows = roster['body'] if isinstance(roster['body'], list) else []
        by_team = {}
        for r in rows:
            by_team.setdefault(r.get('team_id'), []).append(r)
        counts = {k: len(v) for k, v in by_team.items()}
        R.observe('members_by_team', counts)
        R.observe('sixth_member_refusal', refused_seen)
        first_id = tlist[0].get('team_id') or tlist[0].get('id')
        R.step('sixth member refused; team 1 holds 5, others 3',
               'pass' if counts.get(first_id) == 5 and all(counts.get(t.get('team_id') or t.get('id')) == 3 for t in tlist[1:]) else 'fail',
               json.dumps(counts))
        R.step('the refusal is shown to the instructor in business language',
               'pass' if refused_seen and (('maximum' in (refused_seen['toast'] or '') + (refused_seen['modal'] or '')) or 'allows' in (refused_seen['toast'] or '') + (refused_seen['modal'] or '')) else 'fail',
               json.dumps(refused_seen, ensure_ascii=False)[:400])
        R.screen(page, 'i08-teams-assigned')
        return GID


def control(page, GID, resumed):
    if True:
        # ---- game control: team configuration ----------------------------
        click_tab(page, 'Game Control')
        page.wait_for_timeout(4000)
        R.screen(page, 'i09-game-control-setup', 'game in setup, before activation')
        cfg0 = api(page, 'GET', '/api/games/%s/instructor/team-config/' % GID)
        configured = ((cfg0['body'] or {}).get('teams') or [{}])[0].get('team_name') == 'Aurora Devices'
    if not configured:
        A(page).locator('button', has_text='Expand').first.click()
        page.wait_for_timeout(3000)
        page.locator('.ant-radio-button-wrapper', has_text='Random').first.click()
        page.wait_for_timeout(2500)
        R.observe('random_toast', toast(page, 10))
        # Walkthrough 2: team 1's home market is set to Africa BY HAND, so the
        # student's Market Strategy can be checked against what the console said
        # (W-CE-21). pick_select matches the option by its rendered market name.
        cfg_table = A(page).locator('table').filter(
            has=page.locator('thead', has_text='HOME MARKET')).first
        row1 = cfg_table.locator('tbody tr').first
        picked = pick_select(page, row1.locator('.ant-select').first, 'Africa')
        R.observe('home_market_picked', picked)
        page.wait_for_timeout(800)
        name_box = page.locator('table input[type="text"]').first
        name_box.fill('Aurora Devices'); name_box.press('Tab')
        page.wait_for_timeout(600)
        R.screen(page, 'i10-team-config-edited', 'random home markets previewed, team 1 renamed')
        A(page).locator('button', has_text='Save Configuration').first.click()
        R.observe('team_config_toast', toast(page))
        page.wait_for_timeout(4000)
        cfg = api(page, 'GET', '/api/games/%s/instructor/team-config/' % GID)
        R.observe('team_config_after', cfg['body'])
        ct = (cfg['body'] or {}).get('teams') or []
        R.step('team 1 home market set to Africa from the console',
               'pass' if ct and ct[0].get('home_market_code') == 'AFR' else 'fail',
               'team 1 -> %s / %s' % (ct[0].get('home_market_code') if ct else None,
                                      ct[0].get('home_market_name') if ct else None))
        R.step('team configuration saved (home markets + rename)',
               'pass' if ct and ct[0].get('team_name') == 'Aurora Devices' and all(x.get('home_market_code') for x in ct) else 'fail',
               json.dumps([(x.get('team_name'), x.get('home_market_code')) for x in ct])[:300])
        R.screen(page, 'i11-team-config-saved')
    st0 = api(page, 'GET', '/api/games/%s/round-control/' % GID)
    already_active = st0['status'] == 200 and st0['body'].get('game_status') in ('active', 'paused')
    if not already_active:
        # ---- activate ----------------------------------------------------
        A(page).locator('button', has_text='Activate Game').first.click()
        page.wait_for_timeout(1000)
        R.observe('activate_popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
        popconfirm_ok(page, 5000)
        R.observe('activate_toast', toast(page, 10))
        page.wait_for_timeout(3000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        R.observe('round_control_after_activate', rc['body'])
        R.step('game activated; round 1 open',
               'pass' if rc['status'] == 200 and (rc['body'].get('round') or {}).get('status') == 'open' else 'fail',
               json.dumps(rc['body'])[:300])
        R.screen(page, 'i12-game-activated', 'NOTE which tab the console is on after Activate')
        active_tab = page.locator('.ant-tabs-tab-active').first.text_content() if page.locator('.ant-tabs-tab-active').count() else None
        R.observe('tab_after_activate', active_tab)
        R.step('console stays on Game Control after Activate', 'pass' if active_tab and 'Game Control' in active_tab else 'fail', 'active tab after Activate: %r' % active_tab)
    if True:
        click_tab(page, 'Game Control'); page.wait_for_timeout(3000)
        R.screen(page, 'i12b-game-control-active')

        # ---- schedule ------------------------------------------------------
        qs = page.locator('.ant-card', has_text='Quick Schedule').last   # innermost: the outer Round Schedule card also matches
        qs.locator('input[type="datetime-local"]').first.fill('2026-09-22T18:00')
        page.wait_for_timeout(400)
        qs.locator('button', has_text='Generate & Save').first.click()
        R.observe('schedule_toast', toast(page))
        page.wait_for_timeout(3000)
        sched = api(page, 'GET', '/api/games/%s/round-schedule/' % GID)
        rounds = (sched['body'] or {}).get('rounds') or []
        R.step('round schedule generated and saved for every playable round',
               'pass' if rounds and all(r.get('deadline') for r in rounds if r.get('round_number', 0) > 0) else 'fail',
               R.record['observed'].get('schedule_toast'))
        R.screen(page, 'i13-round-schedule')

        # ---- round 1 deadline via the round console ------------------------
        rcc = card(page, 'Round control')
        btn = rcc.locator('button', has_text='deadline').first
        btn.click(); page.wait_for_timeout(1200)
        R.observe('deadline_modal', modal_text(page))
        picker_in = page.locator('.ant-modal-content .ant-picker input').first
        picker_in.click(); page.keyboard.press('Control+a')
        page.keyboard.type('2026-09-25 18:00:00'); page.keyboard.press('Enter')
        page.wait_for_timeout(600)
        R.screen(page, 'i14-set-deadline-modal')
        page.locator('.ant-modal-footer .ant-btn-primary').last.click()
        R.observe('deadline_toast', toast(page))
        page.wait_for_timeout(3000)
        rc = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        dl = (rc['body'].get('round') or {}).get('deadline')
        R.step('round 1 deadline set from the console', 'pass' if dl and dl.startswith('2026-09-25') else 'fail', 'deadline=%s toast=%r' % (dl, R.record['observed'].get('deadline_toast')))

        if not (dl and dl.startswith('2026-09-25')):
            # Walkthrough 2: the refusal named a stale round. Reload the console
            # (what the refusal tells the instructor to do) and repeat, so the
            # record says whether the control works at all or only after a refresh.
            R.observe('deadline_first_attempt', {'deadline': dl, 'toast': R.record['observed'].get('deadline_toast')})
            page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(6000)
            click_tab(page, 'Game Control'); page.wait_for_timeout(4000)
            rcc2 = card(page, 'Round control')
            b2 = rcc2.locator('button', has_text='deadline').first
            b2.click(); page.wait_for_timeout(1500)
            pk = page.locator('.ant-modal-wrap:visible .ant-picker input').first
            pk.click(); page.keyboard.press('Control+a')
            page.keyboard.type('2026-09-25 18:00:00'); page.keyboard.press('Enter')
            page.wait_for_timeout(600)
            vmodal(page).locator('.ant-modal-footer .ant-btn-primary').last.click()
            R.observe('deadline_toast_after_refresh', toast(page))
            page.wait_for_timeout(3000)
            rc3 = api(page, 'GET', '/api/games/%s/round-control/' % GID)
            dl3 = (rc3['body'].get('round') or {}).get('deadline')
            R.observe('deadline_after_refresh', dl3)
            R.step('round 1 deadline set from the console after a page refresh',
                   'pass' if dl3 and dl3.startswith('2026-09-25') else 'fail',
                   'deadline=%s toast=%r' % (dl3, R.record['observed'].get('deadline_toast_after_refresh')))
            dl = dl3
        tab_now = page.locator('.ant-tabs-tab-active').first.text_content() if page.locator('.ant-tabs-tab-active').count() else None
        R.observe('tab_after_set_deadline', tab_now)
        R.step('console stays on Game Control after a round-control action', 'pass' if tab_now and 'Game Control' in tab_now else 'fail', 'active tab after Save deadline: %r' % tab_now)
        R.screen(page, 'i14b-after-set-deadline')
        click_tab(page, 'Game Control'); page.wait_for_timeout(2500)

        # ---- extend deadline ---------------------------------------------
        A(page).locator('button', has_text='Extend Deadline').first.click()
        page.wait_for_timeout(1200)
        R.observe('extend_modal', modal_text(page))
        R.screen(page, 'i15-extend-deadline-modal')
        page.locator('.ant-modal-footer .ant-btn-primary').last.click()
        page.wait_for_timeout(3500)
        err = modal_text(page)
        R.observe('extend_result_modal', err)
        rc2 = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        dl2 = (rc2['body'].get('round') or {}).get('deadline')
        R.step('extend deadline moved the round 1 deadline', 'pass' if dl2 and dl2 != dl else 'fail', 'before=%s after=%s modal=%r' % (dl, dl2, err))
        if err and 'Error' in err:
            page.keyboard.press('Escape'); page.wait_for_timeout(500)
            okb = page.locator('.ant-modal-confirm-btns .ant-btn-primary')
            if okb.count(): okb.last.click(); page.wait_for_timeout(500)
        R.observe('tab_after_extend', page.locator('.ant-tabs-tab-active').first.text_content() if page.locator('.ant-tabs-tab-active').count() else None)
        R.screen(page, 'i16-after-extend')
        click_tab(page, 'Game Control'); page.wait_for_timeout(2500)

        # ---- pause / resume ----------------------------------------------
        click_tab(page, 'Game Control'); page.wait_for_timeout(2000)
        A(page).locator('button', has_text='Pause Game').first.click(); page.wait_for_timeout(900)
        popconfirm_ok(page, 2000)
        R.observe('pause_toast', toast(page))
        page.wait_for_timeout(2500)
        R.screen(page, 'i17-paused')
        st = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        R.step('pause is reflected by the server', 'pass' if st['body'].get('game_status') == 'paused' else 'fail', st['body'].get('game_status'))
        click_tab(page, 'Game Control'); page.wait_for_timeout(2000)
        A(page).locator('button', has_text='Resume Game').first.click(); page.wait_for_timeout(900)
        popconfirm_ok(page, 2000)
        R.observe('resume_toast', toast(page))
        page.wait_for_timeout(2500)
        st = api(page, 'GET', '/api/games/%s/round-control/' % GID)
        R.step('resume is reflected by the server', 'pass' if st['body'].get('game_status') == 'active' else 'fail', st['body'].get('game_status'))
        R.screen(page, 'i18-resumed')

        # ---- operator event ------------------------------------------------
        click_tab(page, 'Event Manager')
        page.wait_for_timeout(3000)
        R.screen(page, 'i19-event-manager')
        A(page).locator('button', has_text='Inject Event').first.click(); page.wait_for_timeout(1200)
        lbl = pick_select(page, page.locator('.ant-modal-content .ant-select').first)
        page.wait_for_timeout(800)
        R.screen(page, 'i20-inject-event-modal')
        page.locator('.ant-modal-footer .ant-btn-primary').last.click()
        R.observe('inject_toast', toast(page))
        page.wait_for_timeout(3000)
        R.step('operator event injected from the console', 'pass' if R.record['observed'].get('inject_toast') and 'fail' not in R.record['observed']['inject_toast'].lower() else 'fail', 'template=%r toast=%r' % (lbl, R.record['observed'].get('inject_toast')))
        R.screen(page, 'i21-event-injected')

        # ---- operator log ------------------------------------------------
        click_tab(page, 'Operator Log'); page.wait_for_timeout(4000)
        R.screen(page, 'i22-operator-log')
        R.step('operator log lists the actions taken', 'pass' if page.locator('.ant-tabs-tabpane-active tbody tr').count() >= 3 else 'fail', '%d rows' % page.locator('.ant-tabs-tabpane-active tbody tr').count())

        # ---- student logins: bulk reset missing passwords ------------------
        click_tab(page, 'Students & Logins'); page.wait_for_timeout(4000)
        R.screen(page, 'i23-students-logins')
        bulk = page.locator('.ant-tabs-tabpane-active button', has_text='Reset')
        if bulk.count() == 0:
            bulk = page.locator('.ant-tabs-tabpane-active button.ant-btn-primary')
        bulk.first.click(); page.wait_for_timeout(1000)
        popconfirm_ok(page, 4000)
        reveal = modal_text(page)
        R.observe('bulk_reset_modal', (reveal or '')[:1500])
        R.screen(page, 'i24-passwords-issued')
        R.step('student passwords issued in bulk from the console', 'pass' if reveal and 's2601' in reveal else 'fail', (reveal or '')[:200])
        okb = page.locator('.ant-modal-footer .ant-btn-primary')
        if okb.count(): okb.last.click(); page.wait_for_timeout(800)

        # ---- team overview + drill --------------------------------------------
        click_tab(page, 'Team Overview'); page.wait_for_timeout(3500)
        R.screen(page, 'i25-team-overview')
        vd = page.locator('.ant-tabs-tabpane-active button', has_text='View Decisions')
        if vd.count():
            vd.first.click(); page.wait_for_timeout(3000)
            R.observe('drill_modal', (modal_text(page) or '')[:600])
            R.screen(page, 'i26-team-decisions-drill')
            page.keyboard.press('Escape'); page.wait_for_timeout(600)

        # ---- grading tab --------------------------------------------------
        click_tab(page, 'Grading & Export'); page.wait_for_timeout(3000)
        pick_select(page, page.locator('.ant-tabs-tabpane-active .ant-select').nth(0), COURSE_CODE)
        page.wait_for_timeout(1500)
        pick_select(page, page.locator('.ant-tabs-tabpane-active .ant-select').nth(1), SECTION_CODE)
        page.wait_for_timeout(2500)
        R.screen(page, 'i27-grading-before-rubric')
        cr = A(page).locator('button', has_text='Create Default Rubric')
        if cr.count():
            cr.first.click(); R.observe('rubric_toast', toast(page)); page.wait_for_timeout(3000)
        R.screen(page, 'i28-grading-rubric')
        cg = A(page).locator('button', has_text='Calculate Grades')
        R.observe('calculate_grades_enabled', cg.first.is_enabled() if cg.count() else None)
        if cg.count() and cg.first.is_enabled():
            cg.first.click(); R.observe('calc_toast_round0', toast(page)); page.wait_for_timeout(3000)
        R.screen(page, 'i29-grading-calculated-round0')
        # W-CE-12: the override control the first walkthrough could not find.
        ov = A(page).locator('table button', has_text='Override')
        R.observe('override_buttons', ov.count())
        if ov.count() and ov.first.is_enabled():
            ov.first.click(); page.wait_for_timeout(1500)
            R.observe('override_modal', (modal_text(page) or '')[:600])
            R.screen(page, 'i29b-grading-override-modal', 'the override an instructor is offered')
            m = vmodal(page)
            sb = m.locator('.ant-input-number-input').first
            if sb.count():
                set_number(page, sb, 88)
            ta = m.locator('textarea')
            if ta.count():
                ta.first.fill('Walkthrough 2: override driven from the console.')
            page.wait_for_timeout(500)
            m.locator('.ant-modal-footer .ant-btn-primary').last.click()
            R.observe('override_toast', toast(page, 15))
            page.wait_for_timeout(4000)
            R.screen(page, 'i29c-grading-after-override')
            gr = api(page, 'GET', '/api/grades/?instance_id=%s' % GID)
            R.observe('grades_after_override', json.dumps(gr['body'])[:900] if gr else None)
            R.step('grading override saved from the console',
                   'pass' if (R.record['observed'].get('override_toast') or '') and 'fail' not in (R.record['observed'].get('override_toast') or '').lower() else 'fail',
                   R.record['observed'].get('override_toast'))
            if modal_text(page):
                page.keyboard.press('Escape'); page.wait_for_timeout(600)
        else:
            R.step('grading override control offered on the Team Grades table', 'fail',
                   '%d override buttons' % ov.count())
        for label in ('Export Team Summary CSV', 'Export Team Grades CSV', 'Export Student Grades CSV'):
            b = A(page).locator('button', has_text=label)
            if not b.count():
                R.step('export: %s' % label, 'fail', 'button missing'); continue
            try:
                with page.expect_download(timeout=8000) as dl_info:
                    b.first.click()
                d = dl_info.value
                path = EVIDENCE / 'exports' / d.suggested_filename
                path.parent.mkdir(parents=True, exist_ok=True)
                d.save_as(str(path))
                size = path.stat().st_size
                R.step('export: %s' % label, 'pass' if size > 0 else 'fail', '%s (%d bytes)' % (d.suggested_filename, size))
            except Exception as exc:
                R.step('export: %s' % label, 'fail', 'no download: %s; toast=%r' % (str(exc)[:120], toast(page, 5)))
        R.screen(page, 'i30-grading-exports')

        # ---- the remaining panels ---------------------------------------------
        for tab, name in (('Briefings', 'i31-briefings'), ('Research Monitor', 'i32-research-monitor'),
                          ('AI Coach', 'i33-ai-coach'), ('Supply Chain', 'i34-supply-chain')):
            if click_tab(page, tab):
                page.wait_for_timeout(3500); R.screen(page, name)
            else:
                R.step('reach tab %s' % tab, 'fail')

        # ---- record the game for the later drivers ----------------------------
        finish_record(page, GID)


def finish_record(page, GID):
    if True:
        teams_api = api(page, 'GET', '/api/games/%s/teams/' % GID)
        tl = teams_api['body'].get('teams') if isinstance(teams_api['body'], dict) else teams_api['body']
        roster = api(page, 'GET', '/api/roster/?section_id=%s' % section_id(page))
        out = {'game_id': GID, 'game_name': GAME_NAME, 'section_id': section_id(page),
               'course_code': COURSE_CODE, 'section_code': SECTION_CODE,
               'teams': tl, 'roster': roster['body']}
        (SCRATCH / 'game.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))


_SECTION = {}


def section_id(page):
    if 'id' not in _SECTION:
        r = api(page, 'GET', '/api/courses/')
        courses = r['body'] if isinstance(r['body'], list) else (r['body'] or {}).get('results') or (r['body'] or {}).get('courses') or []
        course = next((c for c in courses if c.get('course_code') == COURSE_CODE), None)
        s = api(page, 'GET', '/api/sections/?course_id=%s' % (course or {}).get('course_id'))
        secs = s['body'] if isinstance(s['body'], list) else (s['body'] or {}).get('results') or (s['body'] or {}).get('sections') or []
        sec = next((x for x in secs if x.get('section_code') == SECTION_CODE), None)
        _SECTION['id'] = (sec or {}).get('section_id')
        R.observe('section_lookup', {'courses': r['status'], 'sections': s['status'], 'section_id': _SECTION['id']})
    return _SECTION['id']


if __name__ == '__main__':
    raise SystemExit(main())
