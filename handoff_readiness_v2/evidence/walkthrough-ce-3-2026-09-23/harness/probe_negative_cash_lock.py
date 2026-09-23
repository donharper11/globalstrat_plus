"""W-CE-23's unchanged remainder: can a team whose cash is negative lock at all?

probe_negative_cash_lock.py <team-index> <round>

`WALK_CE_STUDENT_NUMBERS_2026-09-22.md` §8.1 and `WALK_CE2_ROUND_BLOCKERS
_2026-09-23.md` §7.3 both put this to the owner and it is unruled: the
affordability check compares committed spend with cash on hand and ignores
the financing the team has decided, while the sentence beside it tells the
team to raise financing.

This asks the question on the real game: with the team's cash negative, strip
the round back to nothing — every declared budget zero, no dividend, no
outlay — and see whether the lock is offered. Then add the financing the
blocker asks for and ask again. Read-write on this team's own draft only.
"""
import json
import pathlib
import sys

from walk import BASE, Recorder, api, sign_in, sync_playwright, visible_text

SCRATCH = pathlib.Path(__file__).resolve().parent
TEAM_IX = int(sys.argv[1])
ROUND = int(sys.argv[2])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('probe-negative-cash-lock-t%d-r%d' % (TEAM_IX, ROUND), 'en')
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
SUMM = DEC + 'summary/'


def blockers(page):
    body = api(page, 'GET', SUMM)['body'] or {}
    return body.get('can_lock'), (body.get('lock_blockers') or [])


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], 'en', password=STUDENT.get('student_id'))
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        api(page, 'PUT', '/api/user/preferences/', {'language': 'en'})
        fin = api(page, 'GET', '/api/games/%d/teams/%d/context/finance/' % (GID, TID))['body'] or {}
        R.observe('cash_on_hand', fin.get('cash_on_hand'))
        can0, b0 = blockers(page)
        R.observe('blockers_as_played', b0)
        R.step('the team starts the probe unable to lock', 'pass' if can0 is False else 'observed',
               json.dumps(b0)[:400])

        # 1. strip the round back to nothing
        api(page, 'PATCH', DEC + 'budget/', {'budget_allocation': {
            'rd_budget': '0', 'marketing_budget': '0', 'strategy_budget': '0'}})
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '0', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        api(page, 'PATCH', DEC + 'plants/', {'plant_decisions': []})
        api(page, 'PATCH', DEC + 'partnerships/', {'partnerships': []})
        api(page, 'PATCH', DEC + 'acquisitions/', {'acquisitions': []})
        api(page, 'PATCH', DEC + 'esg/', {'esg': {
            'environmental_investment': '0', 'social_investment': '0',
            'governance_commitments': []}})
        api(page, 'PATCH', DEC + 'compliance-investments/', {'compliance_investments': []})
        can1, b1 = blockers(page)
        R.observe('blockers_with_nothing_committed', b1)
        R.step('with nothing committed at all, the lock is offered',
               'pass' if can1 else 'fail', json.dumps(b1)[:500])
        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.screen(page, 'v-negcash-t%d-r%d-stripped' % (TEAM_IX, ROUND),
                 'negative cash, nothing committed')
        R.observe('summary_text_stripped', visible_text(page)[:2000])

        # 2. raise the financing the blocker asks for
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '30000000', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        can2, b2 = blockers(page)
        R.observe('blockers_after_raising_debt', b2)
        R.step('raising the financing the sentence asks for clears the cash blocker',
               'pass' if not any('cash' in str(x).lower() for x in b2) else 'fail',
               json.dumps(b2)[:500])
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.screen(page, 'v-negcash-t%d-r%d-after-financing' % (TEAM_IX, ROUND),
                 'after raising $30M of debt')
        R.observe('summary_text_after_financing', visible_text(page)[:2000])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
