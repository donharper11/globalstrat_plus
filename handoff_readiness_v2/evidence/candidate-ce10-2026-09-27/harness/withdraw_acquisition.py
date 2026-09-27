"""Withdraw an unaffordable queued acquisition through the student UI.

Usage: withdraw_acquisition.py <lang> <team-index> <round>

This is a normal draft correction, not an operator recovery.  It exists to
capture the exact player path for the R3 guidance defect: Summary names an
unaffordable acquisition as a generic strategy budget, while Finance rightly
refuses equity for an acquisition that has not yet been fulfilled.
"""
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, modal_text, sign_in, sync_playwright,
                  visible_text)


LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('withdraw-acquisition-t%d-r%d' % (TEAM_IX, ROUND), LANG)
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales'
                     / ('%s.json' % LANG)).read_text())


def T(key, **values):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    for name, value in values.items():
        cur = cur.replace('{{%s}}' % name, str(value))
    return cur


def tab(page, label):
    item = page.locator('.ant-tabs-tab', has_text=label)
    if not item.count():
        return False
    item.first.click()
    page.wait_for_timeout(1800)
    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'), rec=R)
        R.step('%s signs in' % STUDENT['username'],
               'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.wait_for_timeout(3000)
        for _ in range(6):
            button = page.locator(
                '.ant-modal-wrap:visible .ant-modal-content button')
            if not button.count():
                break
            button.last.click()
            page.wait_for_timeout(1000)

        before_draft = api(page, 'GET', DEC)['body'] or {}
        before_summary = api(page, 'GET', DEC + 'summary/')['body'] or {}
        before = before_draft.get('acquisitions') or []
        R.observe('before', {
            'acquisitions': before,
            'can_lock': before_summary.get('can_lock'),
            'lock_blockers': before_summary.get('lock_blockers'),
            'budget_summary': before_summary.get('budget_summary'),
        })
        R.step('an acquisition is queued while Summary refuses affordability',
               'pass' if before and not before_summary.get('can_lock') else 'fail',
               json.dumps(R.record['observed']['before'],
                          ensure_ascii=False)[:1000])

        page.goto(BASE + '/games/%d/teams/%d/decisions/corporate-strategy'
                  % (GID, TID), wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        reached = tab(page, T('corporate_strategy.ma'))
        R.step('M&A decisions are reachable from Corporate Strategy',
               'pass' if reached else 'fail')
        R.observe('ma_draft', (api(page, 'GET', DEC)['body'] or {}).get(
            'acquisitions'))
        R.observe('ma_context', api(
            page, 'GET', '/api/games/%d/teams/%d/context/strategy/'
            % (GID, TID))['body'])
        R.observe('ma_buttons', [
            (page.locator('button').nth(i).text_content() or '').strip()
            for i in range(page.locator('button').count())
        ])
        R.observe('ma_text', visible_text(page)[-5000:])
        # Ant Design inserts a visual space between two Chinese characters
        # ("撤 回"), so match the localized word with optional whitespace.
        withdraw_label = T('corporate_strategy.withdraw')
        withdraw_pattern = re.compile(
            r'\s*'.join(map(re.escape, withdraw_label)), re.I)
        withdraw = page.locator('button', has_text=withdraw_pattern)
        offered = withdraw.count() and withdraw.first.is_enabled()
        R.step('the queued acquisition offers a Withdraw action',
               'pass' if offered else 'fail',
               'count=%d' % withdraw.count())
        R.screen(page, 'r%d-t%d-acquisition-before-withdraw'
                 % (ROUND, TEAM_IX))
        if offered:
            withdraw.first.click()
            page.wait_for_timeout(4500)

        after_draft = api(page, 'GET', DEC)['body'] or {}
        after_summary = api(page, 'GET', DEC + 'summary/')['body'] or {}
        after = after_draft.get('acquisitions') or []
        R.observe('after', {
            'acquisitions': after,
            'can_lock': after_summary.get('can_lock'),
            'lock_blockers': after_summary.get('lock_blockers'),
            'budget_summary': after_summary.get('budget_summary'),
        })
        R.step('Withdraw removes the draft acquisition through the product',
               'pass' if len(after) < len(before) else 'fail',
               json.dumps(R.record['observed']['after'],
                          ensure_ascii=False)[:1000])
        R.screen(page, 'r%d-t%d-acquisition-after-withdraw'
                 % (ROUND, TEAM_IX))

        page.goto(BASE + '/games/%d/teams/%d/decisions/summary'
                  % (GID, TID), wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        lock = page.locator(
            'button', has_text=T('summary_page.lock_submit_round', round=ROUND))
        if not lock.count():
            # The localized string contains the interpolated round number.
            lock = page.locator('button').filter(has_text=str(ROUND))
        enabled = lock.count() and lock.first.is_enabled()
        R.step('lock is offered after the student withdraws the commitment',
               'pass' if enabled else 'fail',
               json.dumps(after_summary.get('lock_blockers'),
                          ensure_ascii=False)[:500])
        if enabled:
            lock.first.click()
            page.wait_for_timeout(1200)
            R.observe('lock_modal', modal_text(page))
            confirm = page.locator(
                '.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary')
            if confirm.count():
                confirm.last.click()
                page.wait_for_timeout(4500)
        status = (api(page, 'GET', DEC)['body'] or {}).get('status')
        R.step('round locks through the normal student confirmation',
               'pass' if status == 'locked' else 'fail', status)
        R.screen(page, 'r%d-t%d-locked-after-withdraw'
                 % (ROUND, TEAM_IX))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
