"""Instructor resolves one round through the console: instructor_round.py <lang> <round> [path]

path: 'console' (default)  Close round now -> Run post-round processing -> Advance
      'force'              Close & process now (reason) -> Advance
      'lifecycle'          the Game Lifecycle card's Advance Round modal
Screens the dashboard before and after, the Team Overview and a decision
drill-down after processing, and the Operator Log.
"""
import json
import pathlib
import sys
import time

from walk import (BASE, Recorder, api, click_tab, fx, modal_text,
                  popconfirm_ok, sign_in, sync_playwright, toast)

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 1
PATH = sys.argv[3] if len(sys.argv) > 3 else 'console'
G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
GID = G['game_id']
R = Recorder('instructor-round%d-%s' % (ROUND, PATH), LANG)
L = {
    'en': {'control': 'Game Control', 'close': 'Close round now', 'process': 'Run post-round processing',
           'advance': 'Advance to round', 'finish': 'Finish game', 'reopen': 'Reopen round',
           'force': 'Close & process now', 'teams': 'Team Overview', 'view': 'View Decisions',
           'log': 'Operator Log', 'lifecycle_advance': 'Advance Round', 'briefings': 'Briefings',
           'coach': 'AI Coach', 'research': 'Research Monitor'},
    'zh-CN': {'control': '游戏控制', 'close': '立即关闭回合', 'process': '运行回合结算',
              'advance': '推进到第', 'finish': '结束游戏', 'reopen': '重新开放回合',
              'force': '立即关闭并结算', 'teams': '团队概览', 'view': '查看决策',
              'log': '操作日志', 'lifecycle_advance': '推进回合', 'briefings': '简报',
              'coach': 'AI 教练', 'research': '研究监控'},
}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def rc(page):
    return api(page, 'GET', '/api/games/%s/round-control/' % GID)['body']


def wait_processed(page, timeout=900):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        b = rc(page)
        r = b.get('round') or {}
        last = (r.get('status'), r.get('processing_status'))
        if r.get('status') == 'processed' and r.get('processing_status') in ('RESULTS_AVAILABLE', 'FULLY_COMPLETE', 'FAILED'):
            return b
        # The lifecycle card's Advance Round is the legacy one-step route: it
        # processes the round AND opens the next, so the console never shows
        # this round as 'processed'; the next round being open is the signal.
        if PATH == 'lifecycle' and r.get('round_number') == ROUND + 1 and r.get('status') == 'open':
            return b
        page.wait_for_timeout(5000)
    R.step('round processing finished', 'fail', 'still %r after %ds' % (last, timeout))
    return rc(page)


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
        click_tab(page, L['control']); page.wait_for_timeout(4000)
        pre = rc(page)
        R.observe('round_control_before', pre)
        R.screen(page, 'r%d-00-control-before-close' % ROUND, 'teams locked: %s/%s' % ((pre.get('round') or {}).get('teams_locked'), (pre.get('round') or {}).get('teams_total')))
        rnd = pre.get('round') or {}
        if PATH == 'reprocess':
            # The round is already closed (a previous processing attempt failed);
            # only "Run post-round processing" is driven.
            R.step('round %d is closed and awaiting processing' % ROUND,
                   'pass' if rnd.get('round_number') == ROUND and rnd.get('status') == 'closed' else 'fail',
                   json.dumps(rnd)[:200])
        else:
            R.step('round %d is the open round before resolve' % ROUND, 'pass' if rnd.get('round_number') == ROUND and rnd.get('status') == 'open' else 'fail', json.dumps(rnd)[:200])

        if PATH == 'console':
            A(page).locator('button', has_text=L['close']).first.click(); page.wait_for_timeout(1000)
            R.observe('close_popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
            R.screen(page, 'r%d-01-close-confirm' % ROUND)
            popconfirm_ok(page, 4000)
            R.observe('close_toast', toast(page, 10))
            page.wait_for_timeout(3000)
            b = rc(page)
            R.step('round closed from the console', 'pass' if (b.get('round') or {}).get('status') == 'closed' else 'fail', 'toast=%r status=%s' % (R.record['observed'].get('close_toast'), (b.get('round') or {}).get('status')))
            click_tab(page, L['control']); page.wait_for_timeout(3000)
            R.screen(page, 'r%d-02-closed' % ROUND)
            # Reopen modal: opened and cancelled, so the wording is on record.
            ro = A(page).locator('button', has_text=L['reopen'])
            if ro.count():
                ro.first.click(); page.wait_for_timeout(1000)
                R.observe('reopen_modal', modal_text(page))
                R.screen(page, 'r%d-03-reopen-modal' % ROUND)
                page.keyboard.press('Escape'); page.wait_for_timeout(800)
            A(page).locator('button', has_text=L['process']).first.click(); page.wait_for_timeout(1000)
            R.observe('process_popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
            popconfirm_ok(page, 3000)
            R.observe('process_toast', toast(page, 10))
        elif PATH == 'force':
            A(page).locator('button', has_text=L['force']).first.click(); page.wait_for_timeout(1000)
            R.observe('force_modal', modal_text(page))
            page.locator('.ant-modal-content textarea').first.fill('Walkthrough: closing round %d early for the audit.' % ROUND)
            page.wait_for_timeout(500)
            R.screen(page, 'r%d-01-force-modal' % ROUND)
            page.locator('.ant-modal-footer .ant-btn-primary').last.click()
            R.observe('force_toast', toast(page, 10))
        elif PATH == 'reprocess':
            A(page).locator('button', has_text=L['process']).first.click(); page.wait_for_timeout(1000)
            R.observe('process_popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
            popconfirm_ok(page, 3000)
            R.observe('process_toast', toast(page, 10))
        elif PATH == 'lifecycle':
            A(page).locator('button', has_text=L['lifecycle_advance']).first.click(); page.wait_for_timeout(1000)
            R.observe('advance_modal', modal_text(page))
            R.screen(page, 'r%d-01-lifecycle-advance-modal' % ROUND)
            page.locator('.ant-modal-footer .ant-btn-primary').last.click()
            page.wait_for_timeout(4000)
            R.observe('advance_result_modal', modal_text(page))

        done = wait_processed(page)
        R.observe('round_control_processed', done)
        rd = done.get('round') or {}
        sched = api(page, 'GET', '/api/games/%s/round-schedule/' % GID)['body']
        srow = next((x for x in ((sched or {}).get('rounds') or []) if x.get('round_number') == ROUND), {})
        R.observe('schedule_row', srow)
        R.step('round %d processed' % ROUND, 'pass' if srow.get('status') == 'processed' or (rd.get('round_number') == ROUND and rd.get('status') == 'processed' and rd.get('processing_status') != 'FAILED') else 'fail',
               'schedule=%s processing=%s narrative_error=%r phase1=%s' % (srow.get('status'), rd.get('processing_status'), rd.get('narrative_error'), rd.get('phase_1_duration')))
        R.observe('narrative_error', rd.get('narrative_error'))
        page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(5000)
        page.locator('.ant-card', has_text=G['course_code']).last.click(); page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click(); page.wait_for_timeout(6000)
        click_tab(page, L['control']); page.wait_for_timeout(4000)
        R.screen(page, 'r%d-04-processed' % ROUND, 'processing status as shown')

        # Team Overview after processing + a decision drill-down.
        click_tab(page, L['teams']); page.wait_for_timeout(4000)
        R.screen(page, 'r%d-05-team-overview' % ROUND)
        rows = A(page).locator('tbody tr')
        R.observe('team_overview_rows', rows.count())
        dash = api(page, 'GET', '/api/games/%s/instructor/dashboard/' % GID)['body']
        R.observe('dashboard_teams', [(t.get('team_name'), t.get('performance_index'), t.get('cash_on_hand'), t.get('total_revenue'), t.get('decision_status')) for t in (dash.get('teams') or [])])
        vd = A(page).locator('button', has_text=L['view'])
        if vd.count():
            vd.first.click(); page.wait_for_timeout(3500)
            R.observe('drill_modal', (modal_text(page) or '')[:1200])
            R.screen(page, 'r%d-06-decision-drill' % ROUND)
            page.keyboard.press('Escape'); page.wait_for_timeout(800)
        for tab, nm in ((L['briefings'], 'r%d-07-briefings' % ROUND), (L['research'], 'r%d-08-research-monitor' % ROUND), (L['coach'], 'r%d-09-ai-coach' % ROUND)):
            if click_tab(page, tab):
                page.wait_for_timeout(3500); R.screen(page, nm)

        # Advance
        if PATH != 'lifecycle':
            click_tab(page, L['control']); page.wait_for_timeout(3000)
            adv = A(page).locator('button', has_text=L['advance'])
            if adv.count() == 0:
                adv = A(page).locator('button', has_text=L['finish'])
            R.step('advance control offered after processing', 'pass' if adv.count() else 'fail')
            if adv.count():
                adv.first.click(); page.wait_for_timeout(1000)
                R.observe('advance_popconfirm', page.locator('.ant-popover:not(.ant-popover-hidden)').last.text_content() if page.locator('.ant-popover:not(.ant-popover-hidden)').count() else None)
                R.screen(page, 'r%d-10-advance-confirm' % ROUND)
                popconfirm_ok(page, 5000)
                R.observe('advance_toast', toast(page, 10))
        page.wait_for_timeout(3000)
        after = rc(page)
        R.observe('round_control_after_advance', after)
        ra = after.get('round') or {}
        R.step('round %d open after advance' % (ROUND + 1), 'pass' if ra.get('round_number') == ROUND + 1 and ra.get('status') == 'open' else 'fail', json.dumps(ra)[:200])
        click_tab(page, L['control']); page.wait_for_timeout(3000)
        R.screen(page, 'r%d-11-next-round-open' % ROUND)
        click_tab(page, L['log']); page.wait_for_timeout(4000)
        R.screen(page, 'r%d-12-operator-log' % ROUND)
        # W-CE-07: the before -> after column must read as words, not JSON.
        rows = A(page).locator('tbody tr')
        texts = [(rows.nth(i).inner_text() or '').replace('\n', ' | ')[:300]
                 for i in range(min(rows.count(), 6))]
        R.observe('operator_log_rows', texts)
        json_shaped = [t for t in texts if '{"' in t or '": ' in t]
        R.step('operator log states before -> after in words (W-CE-07)',
               'pass' if texts and not json_shaped else 'fail',
               json.dumps(json_shaped or texts[:2], ensure_ascii=False)[:400])
        # W-CE-20: the drill-down must lead with the decisions, not the audit table.
        drill = R.record['observed'].get('drill_modal') or ''
        if drill:
            audit_at = drill.find('Submission audit evidence')
            if audit_at < 0:
                audit_at = drill.find('\u63d0\u4ea4\u5ba1\u8ba1')
            R.observe('drill_audit_offset', audit_at)
            R.step('the decision drill-down leads with the decisions (W-CE-20)',
                   'pass' if audit_at != 0 else 'fail',
                   'audit table at offset %s of the modal text' % audit_at)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
