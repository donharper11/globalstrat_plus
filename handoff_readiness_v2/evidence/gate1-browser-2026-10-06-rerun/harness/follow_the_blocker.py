"""Do what the Decision Summary tells the team to do, and see if it can lock.

    follow_the_blocker.py <lang> <team-index> <round>

This is the walkthrough's answer to the question integrator decision 13 was
written for, and it is asked the way a player would ask it -- **from the
pages**, not through the API.

The Decision Summary refuses a round that commits more than the team can
fund. Since the decision-13 repair the refusal also says what to do: how much
to cut, which commitment is the largest one that can be cut, and -- for a
team in financial distress, whose new debt lenders will not extend -- to
raise equity instead. This driver reads that sentence, does exactly what it
says on the Finance page (types into the equity box, types the budgets down),
reads the sentence again, and repeats until the lock is offered or the
platform has nothing left to suggest. Then it presses the lock button.

Every figure it types comes from `budget_summary`, which is the same
assessment the sentence is written from, so the driver is not guessing.
"""
import json
import math
import pathlib
import sys

from walk import (BASE, Recorder, api, modal_text, set_number, sign_in,
                  sync_playwright, visible_text)

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
R = Recorder('follow-blocker-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
SUMM = DEC + 'summary/'
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
    body = api(page, 'GET', SUMM)['body'] or {}
    return (body.get('can_lock'), body.get('lock_blockers') or [],
            body.get('budget_summary') or {})


def to_million(x):
    """Round a shortfall UP to the next whole million: the equity box steps in
    millions, so that is the figure a player can actually type."""
    return int(math.ceil(max(x, 0) / 1000000.0) * 1000000)


def clear_financing(page):
    """Zero the debt, the repayment and the dividend from the Capital tab.

    A team in financial distress is refused new debt, and while the refused
    debt is still decided it also reduces the amount of equity the financing
    route will accept -- so the first thing to do is take it off the round.
    """
    nums = pane(page).locator('.ant-input-number-input')
    if nums.count() < 4:
        return False
    for i in (0, 1, 3):
        set_number(page, nums.nth(i), 0)
        page.wait_for_timeout(600)
    page.wait_for_timeout(2500)
    return True


def main():
    attempts = []
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
        if (api(page, 'GET', DEC)['body'] or {}).get('status') == 'locked':
            R.step('round %d is already locked for this team' % ROUND, 'observed')
            browser.close()
            return R.finish()

        can, blockers, bs = summary(page)
        R.observe('as_played', {'can_lock': can, 'blockers': blockers,
                                'budget_summary': bs})
        R.step('the round as the team played it does not fit its funds',
               'observed',
               'cash %s, committed %s; %s'
               % (bs.get('cash_on_hand'), bs.get('committed_total'),
                  json.dumps(blockers, ensure_ascii=False)[:400]))

        for attempt in range(5):
            if can:
                break
            can, blockers, bs = summary(page)
            if can:
                break
            available = float(bs.get('total_available') or 0)
            committed = float(bs.get('committed_total')
                              or bs.get('total_allocated') or 0)
            shortfall = committed - available
            step = {'attempt': attempt, 'available': available,
                    'committed': committed, 'shortfall': shortfall,
                    'blockers': blockers}
            # 1. The sentence's own first instruction: raise equity. (Debt is
            #    refused outright for a company in distress and the blocker
            #    says so, so equity is what it asks for.)
            page.goto(BASE + '/games/%d/teams/%d/decisions/finance' % (GID, TID),
                      wait_until='domcontentloaded')
            page.wait_for_timeout(5000)
            tab(page, T('finance.capital_management'))
            page.wait_for_timeout(1500)
            if attempt == 0:
                step['financing_cleared'] = clear_financing(page)
                can, blockers, bs = summary(page)
                available = float(bs.get('total_available') or 0)
                committed = float(bs.get('committed_total')
                                  or bs.get('total_allocated') or 0)
                shortfall = committed - available
                step['shortfall_after_clearing_debt'] = shortfall
            nums = pane(page).locator('.ant-input-number-input')
            if nums.count() >= 4 and shortfall > 0:
                # A round figure is what a player types first; the box itself
                # steps in millions. Both are recorded, and the exact
                # shortfall is tried second, because the financing route caps
                # an equity raise at the shortfall to the cent (V2-024).
                rounded = to_million(shortfall)
                set_number(page, nums.nth(2), rounded)
                page.wait_for_timeout(3000)
                stored = ((api(page, 'GET', DEC)['body'] or {}).get('financing')
                          or {}).get('new_equity')
                step['round_figure_typed'] = rounded
                step['round_figure_box'] = nums.nth(2).input_value()
                step['round_figure_stored'] = stored
                step['refusal_on_screen'] = [
                    l.strip() for l in visible_text(page).splitlines()
                    if 'equity' in l.lower() or '股本' in l][:6]
                R.screen(page, 'v4-blocker-t%d-r%d-%d-equity-round'
                         % (TEAM_IX, ROUND, attempt),
                         'a round $%dM typed into the equity box' % (rounded // 1000000))
                if float(stored or 0) < rounded:
                    exact = math.floor(shortfall * 100) / 100.0
                    set_number(page, nums.nth(2), exact)
                    page.wait_for_timeout(3000)
                    step['exact_typed'] = exact
                    step['exact_stored'] = (
                        (api(page, 'GET', DEC)['body'] or {}).get('financing')
                        or {}).get('new_equity')
                    R.screen(page, 'v4-blocker-t%d-r%d-%d-equity-exact'
                             % (TEAM_IX, ROUND, attempt),
                             'the exact shortfall typed into the equity box')
            can, blockers, bs = summary(page)
            step['after_equity'] = {'can_lock': can, 'blockers': blockers,
                                    'total_available': bs.get('total_available')}
            if not can:
                # 2. Whatever is still refused: bring the declared budgets up
                #    to the spending already committed, then down to fit.
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
                    step['budgets_set_to'] = wanted
                    R.screen(page, 'v4-blocker-t%d-r%d-%d-budgets'
                             % (TEAM_IX, ROUND, attempt),
                             'the declared budgets set to the spending already made')
                can, blockers, bs = summary(page)
                step['after_budgets'] = {'can_lock': can, 'blockers': blockers}
            if not can and any(('debt-to-equity' in b) or ('资产负债率' in b)
                               for b in blockers):
                # The ratio ceiling. Equity is what should lower it, and it is
                # the very thing that trips it, because a company whose equity
                # is negative has a NEGATIVE ratio and passes. Borrowing --
                # which the ceiling exists to prevent -- keeps the ratio
                # negative, so that is what the product actually accepts. It
                # is driven here because it is a thing a player can do on the
                # page, and because the alternative is a team that cannot
                # submit; the perversity is a finding, not a fix.
                step['de_ceiling_hit'] = blockers
                tab(page, T('finance.capital_management'))
                page.wait_for_timeout(1500)
                nums = pane(page).locator('.ant-input-number-input')
                if nums.count() >= 4:
                    set_number(page, nums.nth(2), 0)          # drop the equity
                    page.wait_for_timeout(1500)
                    need = max(float(bs.get('committed_total') or 0)
                               - float(bs.get('cash_on_hand') or 0), 0)
                    set_number(page, nums.nth(0), to_million(need))
                    page.wait_for_timeout(3000)
                    step['debt_typed'] = to_million(need)
                    step['debt_stored'] = (
                        (api(page, 'GET', DEC)['body'] or {}).get('financing')
                        or {}).get('new_debt')
                    R.screen(page, 'v4-blocker-t%d-r%d-%d-debt'
                             % (TEAM_IX, ROUND, attempt),
                             'debt raised because equity is what trips the '
                             'debt-to-equity ceiling')
                can, blockers, bs = summary(page)
                step['after_debt'] = {'can_lock': can, 'blockers': blockers}
            attempts.append(step)

        R.observe('attempts', attempts)
        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.observe('summary_text', visible_text(page)[:2000])
        R.screen(page, 'v4-blocker-t%d-r%d-summary' % (TEAM_IX, ROUND))
        can, blockers, bs = summary(page)
        R.step('following the Decision Summary\'s own instructions makes the '
               'lock available (W-CE3-02, decision 13)',
               'pass' if can else 'fail',
               'after %d attempt(s): can_lock=%s; what is still refused: %s'
               % (len(attempts), can,
                  json.dumps(blockers, ensure_ascii=False)[:600]))
        if can:
            lock = page.locator(
                'button', has_text=T('summary_page.lock_submit_round', round=ROUND))
            pressed = False
            if lock.count() and lock.first.is_enabled():
                lock.first.click()
                page.wait_for_timeout(1200)
                R.observe('lock_modal', modal_text(page))
                confirm = page.locator(
                    '.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary')
                if confirm.count():
                    confirm.last.click()
                    page.wait_for_timeout(5000)
                pressed = True
            status = (api(page, 'GET', DEC)['body'] or {}).get('status')
            R.screen(page, 'v4-blocker-t%d-r%d-locked' % (TEAM_IX, ROUND))
            R.step('the team presses the lock button and the round is submitted',
                   'pass' if status == 'locked' else 'fail',
                   'button pressed=%s, submission status=%s' % (pressed, status))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
