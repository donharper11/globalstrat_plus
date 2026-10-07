"""Cut the round back until it fits the cash, then lock: lock_within_cash.py <lang> <team-index> <round>

`student_play.py` commits the same budgets every round whatever the team's
cash, which is a driver's behaviour, not a player's. Before concluding that a
team *cannot* lock, this does what a player would: reads the blockers, drops
the declared budgets, the dividend and the promotion budgets until the one
assessment the lock reads says the round fits, and then locks from the
Decision Summary.

If the lock is still refused after every outlay the screens can reach has
been set to zero, that is the platform refusing, not the driver overspending,
and the record says so.
"""
import json
import pathlib
import sys

from walk import BASE, Recorder, api, sign_in, sync_playwright, visible_text

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
R = Recorder('lock-within-cash-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
SUMM = DEC + 'summary/'


def state(page):
    body = api(page, 'GET', SUMM)['body'] or {}
    return body.get('can_lock'), (body.get('lock_blockers') or [])


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG, password=STUDENT.get('student_id'), rec=R)
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        api(page, 'PUT', '/api/user/preferences/', {'language': LANG})
        fin = api(page, 'GET', '/api/games/%d/teams/%d/context/finance/' % (GID, TID))['body'] or {}
        cash = float(fin.get('cash_on_hand') or 0)
        R.observe('cash_on_hand', cash)
        can, blockers = state(page)
        R.observe('blockers_as_played', blockers)
        R.step('the round as played does not fit the cash', 'observed',
               'can_lock=%s %s' % (can, json.dumps(blockers, ensure_ascii=False)[:400]))

        # what a player does: cut the dividend, then the declared budgets, then
        # the promotion budgets, reading the blockers back each time.
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '0', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        steps = []
        for budget in (2000000, 500000, 0):
            share = str(int(max(budget, 0) / 3))
            api(page, 'PATCH', DEC + 'budget/', {'budget_allocation': {
                'rd_budget': share, 'marketing_budget': share, 'strategy_budget': share}})
            can, blockers = state(page)
            steps.append({'budget_each': share, 'can_lock': can,
                          'blockers': blockers})
            if can:
                break
        if not can:
            rows = (api(page, 'GET', DEC)['body'] or {}).get('marketing_decisions') or []
            if rows:
                api(page, 'PATCH', DEC + 'marketing/', {'marketing_decisions': [
                    dict(r, promotion_budget='0') for r in rows]})
                can, blockers = state(page)
                steps.append({'promotion_budgets': 0, 'can_lock': can, 'blockers': blockers})
        R.observe('reduction_steps', steps)
        R.step('cutting the round back to what the cash allows makes the lock available',
               'pass' if can else 'fail',
               'final blockers: %s' % json.dumps(blockers, ensure_ascii=False)[:500])

        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.screen(page, 'x-lwc-t%d-r%d-summary' % (TEAM_IX, ROUND),
                 'after cutting the round back to the cash')
        R.observe('summary_text', visible_text(page)[:1800])
        if can:
            lock = api(page, 'POST', DEC + 'lock/', {})
            R.observe('lock_response', lock)
            status = (api(page, 'GET', DEC)['body'] or {}).get('status')
            R.step('the team locks round %d' % ROUND, 'pass' if status == 'locked' else 'fail',
                   'status=%s response=%s' % (status, json.dumps(lock)[:300]))
            page.reload(wait_until='domcontentloaded'); page.wait_for_timeout(5000)
            R.screen(page, 'x-lwc-t%d-r%d-locked' % (TEAM_IX, ROUND), 'locked')
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
