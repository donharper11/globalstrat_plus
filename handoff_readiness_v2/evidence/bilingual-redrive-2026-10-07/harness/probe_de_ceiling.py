"""The debt-to-equity ceiling a team with negative equity cannot clear.

    probe_de_ceiling.py <lang> <team-index> <round>

Integrator decision 13 says the lock must always be reachable, and the
affordability blocker was repaired so that it is: a team whose cash has gone
negative can raise equity and submit. This driver asks the same question of
the blocker beside it -- *The projected debt-to-equity ratio of N exceeds the
maximum of 2.0. Adjust financing.* -- and tries, from the real pages, every
financing adjustment the product offers:

  * raise more equity (the only lever that lifts the denominator),
  * borrow (the lever the sentence's word "financing" also covers),
  * repay debt (the lever that lowers the numerator).

It records what each one does, and what the Finance page shows the team about
the ratio it is being refused for.
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
R = Recorder('probe-de-ceiling-t%d-r%d' % (TEAM_IX, ROUND), LANG)
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


def financing(page):
    return (api(page, 'GET', DEC)['body'] or {}).get('financing') or {}


def main():
    tried = []
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

        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        can, blockers, bs = summary(page)
        R.observe('blockers', blockers)
        R.observe('budget_summary', bs)
        R.screen(page, 'v4-de-t%d-r%d-summary' % (TEAM_IX, ROUND),
                 'the Decision Summary as the team left it')
        R.step('the round is refused, and the reason given is the '
               'debt-to-equity ceiling', 'observed',
               json.dumps(blockers, ensure_ascii=False)[:400])

        page.goto(BASE + '/games/%d/teams/%d/decisions/finance' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/finance/'
                  % (GID, TID))['body'] or {}
        R.observe('finance_context', ctx)
        tab(page, T('finance.capital_management'))
        page.wait_for_timeout(2000)
        text = visible_text(page)
        R.observe('capital_tab_text', text[:2000])
        R.screen(page, 'v4-de-t%d-r%d-capital' % (TEAM_IX, ROUND))
        ratios = ctx.get('key_ratios') or {}
        cap = ctx.get('capital') or {}
        fin = ctx.get('financial') or {}
        R.step('the ratio the team is refused for is shown to the team',
               'pass' if ratios.get('debt_to_equity') is not None else 'fail',
               'the Finance page serves key_ratios.debt_to_equity=%r, with '
               'total_debt=%s and total_equity=%s'
               % (ratios.get('debt_to_equity'), fin.get('total_debt'),
                  fin.get('total_equity')))
        R.observe('ceiling', cap.get('max_de_ratio'))
        R.observe('available_credit', cap.get('available_credit'))
        R.observe('max_total_debt', cap.get('max_total_debt'))
        R.observe('share_price', cap.get('share_price'))

        nums = pane(page).locator('.ant-input-number-input')
        if nums.count() >= 4:
            short = (float(bs.get('committed_total') or 0)
                     - float(bs.get('total_available') or 0))
            for label, box, value in (
                    ('more equity', 2, max(short, 0) + 10000000),
                    ('new debt', 0, 10000000),
                    ('debt repayment', 1, 5000000)):
                set_number(page, nums.nth(box), int(value))
                page.wait_for_timeout(3000)
                stored = financing(page)
                can2, blockers2, bs2 = summary(page)
                onscreen = [l.strip() for l in visible_text(page).splitlines()
                            if '$' in l and ('equity' in l.lower() or 'debt' in l.lower()
                                             or '股' in l or '债' in l)][:4]
                tried.append({'lever': label, 'typed': int(value),
                              'box': nums.nth(box).input_value(),
                              'stored': stored, 'can_lock': can2,
                              'blockers': blockers2, 'on_screen': onscreen})
                R.screen(page, 'v4-de-t%d-r%d-%s'
                         % (TEAM_IX, ROUND, label.replace(' ', '-')),
                         '%s of %d typed' % (label, int(value)))
                set_number(page, nums.nth(box), 0)
                page.wait_for_timeout(2000)
        R.observe('levers_tried', tried)
        cleared = [t for t in tried if t['can_lock']]
        R.step('some financing adjustment the product offers clears the '
               'debt-to-equity blocker',
               'pass' if cleared else 'fail',
               'levers tried: %s'
               % json.dumps([{'lever': t['lever'], 'stored_equity':
                              (t['stored'] or {}).get('new_equity'),
                              'stored_debt': (t['stored'] or {}).get('new_debt'),
                              'can_lock': t['can_lock']} for t in tried],
                            ensure_ascii=False)[:600])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
