"""Resize an equity raise to the shortfall it actually finances, then lock.

    fix_equity_and_lock.py <lang> <team-index> <round>

Disclosed as an auditor's intervention. Round 5 refused to process because two
teams had locked an equity raise the engine then rejected: the raise was
sized, and accepted, against the committed spend of the moment it was saved,
and the team afterwards reduced a commitment -- which the same Decision
Summary told it to do -- so the stored raise ended up above the cap with no
screen saying so.

There is no control in the product for "resize the equity to what the engine
will accept": the Decision Summary shows no blocker, because by its own rule
there is nothing wrong. So this driver does from the Finance page what the
engine's refusal asks for -- zero the raise, read the shortfall that is left,
type exactly that -- and locks.
"""
import json
import math
import pathlib
import sys

from walk import (BASE, Recorder, api, set_number, sign_in, sync_playwright,
                  visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('fix-equity-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales'
                     / ('%s.json' % LANG)).read_text())


def T(key, **kw):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    for k, v in kw.items():
        cur = cur.replace('{{%s}}' % k, str(v))
    return cur


def pane(page):
    return page.locator('.ant-tabs-tabpane-active').last


def tab(page, label):
    t = page.locator('.ant-tabs-tab', has_text=label)
    if t.count():
        t.first.click()
        page.wait_for_timeout(1800)
        return True
    return False


def summary(page):
    b = api(page, 'GET', DEC + 'summary/')['body'] or {}
    return (b.get('can_lock'), b.get('lock_blockers') or [],
            b.get('budget_summary') or {})


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'), rec=R)
        R.step('%s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.wait_for_timeout(3000)
        for _ in range(6):
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if not b.count():
                break
            b.last.click()
            page.wait_for_timeout(1200)
        before = (api(page, 'GET', DEC)['body'] or {}).get('financing') or {}
        can, blockers, bs = summary(page)
        R.observe('before', {'financing': before, 'can_lock': can,
                             'blockers': blockers, 'budget_summary': bs})
        R.step('the Decision Summary shows nothing wrong with the round the '
               'engine refused to score', 'observed',
               'can_lock=%s blockers=%s stored equity=%s'
               % (can, json.dumps(blockers, ensure_ascii=False)[:200],
                  before.get('new_equity')))
        page.goto(BASE + '/games/%d/teams/%d/decisions/finance' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        tab(page, T('finance.capital_management'))
        page.wait_for_timeout(1500)
        nums = pane(page).locator('.ant-input-number-input')
        if nums.count() < 4:
            R.step('the capital boxes are offered', 'fail',
                   '%d boxes' % nums.count())
            browser.close()
            return R.finish()
        set_number(page, nums.nth(2), 0)
        page.wait_for_timeout(3000)
        can, blockers, bs = summary(page)
        need = (float(bs.get('committed_total') or 0)
                - float(bs.get('cash_on_hand') or 0))
        exact = math.floor(max(need, 0) * 100) / 100.0
        R.observe('shortfall_without_the_raise', exact)
        set_number(page, nums.nth(2), exact)
        page.wait_for_timeout(3500)
        after = (api(page, 'GET', DEC)['body'] or {}).get('financing') or {}
        R.observe('after', after)
        R.step('the equity raise is resized to the shortfall it finances',
               'pass' if abs(float(after.get('new_equity') or 0) - exact) < 0.02
               else 'fail',
               'was %s, now %s, shortfall %.2f'
               % (before.get('new_equity'), after.get('new_equity'), exact))
        R.screen(page, 'v4-fix-equity-t%d-r%d' % (TEAM_IX, ROUND))
        # Whatever else the Summary still refuses: bring the declared budgets
        # up to the spending already made, which is what its own sentence
        # asks for. Then resize the raise again, because raising a declared
        # budget raises committed spend and therefore the shortfall.
        can, blockers, bs = summary(page)
        if not can:
            tab(page, T('finance.budget_allocation'))
            page.wait_for_timeout(1500)
            boxes = pane(page).locator('input.ant-input')
            wanted = [float(bs.get('rd_spent') or 0),
                      float(bs.get('marketing_spent') or 0),
                      float(bs.get('strategy_spent') or 0)]
            if boxes.count() >= 3:
                for i in range(3):
                    set_number(page, boxes.nth(i), int(wanted[i]))
                    page.wait_for_timeout(500)
                page.wait_for_timeout(3500)
                R.observe('budgets_set_to', wanted)
            tab(page, T('finance.capital_management'))
            page.wait_for_timeout(1500)
            nums = pane(page).locator('.ant-input-number-input')
            set_number(page, nums.nth(2), 0)
            page.wait_for_timeout(2500)
            can, blockers, bs = summary(page)
            need = (float(bs.get('committed_total') or 0)
                    - float(bs.get('cash_on_hand') or 0))
            exact = math.floor(max(need, 0) * 100) / 100.0
            set_number(page, nums.nth(2), exact)
            page.wait_for_timeout(3500)
            R.observe('second_pass', {
                'shortfall': exact,
                'financing': (api(page, 'GET', DEC)['body'] or {}).get('financing')})
        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.observe('summary_text', visible_text(page)[:1200])
        can, blockers, bs = summary(page)
        if can:
            lock = page.locator('button', has_text=T(
                'summary_page.lock_submit_round', round=ROUND))
            if lock.count() and lock.first.is_enabled():
                lock.first.click()
                page.wait_for_timeout(1200)
                confirm = page.locator(
                    '.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary')
                if confirm.count():
                    confirm.last.click()
                    page.wait_for_timeout(5000)
        status = (api(page, 'GET', DEC)['body'] or {}).get('status')
        R.step('the team locks round %d again' % ROUND,
               'pass' if status == 'locked' else 'fail',
               'status=%s can_lock=%s blockers=%s'
               % (status, can, json.dumps(blockers, ensure_ascii=False)[:250]))
        R.screen(page, 'v4-fix-equity-t%d-r%d-locked' % (TEAM_IX, ROUND))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
