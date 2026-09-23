"""What a team cannot take out of its round, and whether financing helps.

probe_irreducible_commitment.py <lang> <team-index> <round>

By round 5 not one of the four playing teams could lock. This asks why, from
the figures the platform itself publishes:

  * set every declared budget to 0, the dividend to 0 and every promotion
    budget to 0 — everything a student can reach on a decision screen;
  * read `budget_status` / `affordability`, which is `rd_costs.budget_assessment`,
    the one calculator the lock refuses on, and record what is left;
  * then raise new debt, which is what the blocker's own sentence asks for,
    and read the same figures again.

Read-write on this team's own draft only.
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
R = Recorder('probe-irreducible-commitment-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
SUMM = DEC + 'summary/'


def summary(page):
    return api(page, 'GET', SUMM)['body'] or {}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG, password=STUDENT.get('student_id'))
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        api(page, 'PUT', '/api/user/preferences/', {'language': LANG})

        # everything a student can reach, set to nothing
        api(page, 'PATCH', DEC + 'budget/', {'budget_allocation': {
            'rd_budget': '0', 'marketing_budget': '0', 'strategy_budget': '0'}})
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '0', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        rows = (api(page, 'GET', DEC)['body'] or {}).get('marketing_decisions') or []
        if rows:
            api(page, 'PATCH', DEC + 'marketing/', {'marketing_decisions': [
                dict(r, promotion_budget='0') for r in rows]})
        api(page, 'PATCH', DEC + 'plants/', {'plant_decisions': []})
        api(page, 'PATCH', DEC + 'partnerships/', {'partnerships': []})
        api(page, 'PATCH', DEC + 'acquisitions/', {'acquisitions': []})
        api(page, 'PATCH', DEC + 'esg/', {'esg': {
            'environmental_investment': '0', 'social_investment': '0',
            'governance_commitments': []}})

        body = summary(page)
        budget = body.get('budget_summary') or {}
        R.observe('budget_summary_stripped', budget)
        R.observe('blockers_stripped', body.get('lock_blockers'))
        R.step('with every reachable decision at zero the round still commits money',
               'observed',
               'committed_total=%s of which strategy=%s talent=%s compliance=%s; cash=%s'
               % (budget.get('committed_total'), budget.get('strategy_spent'),
                  budget.get('talent_committed'), budget.get('compliance_committed'),
                  budget.get('total_available')))
        R.step('the lock is still refused with nothing a student can reduce left',
               'pass' if body.get('can_lock') is False else 'fail',
               json.dumps(body.get('lock_blockers'), ensure_ascii=False)[:500])
        zero_dividend = [b for b in (body.get('lock_blockers') or [])
                         if '$0.00' in str(b) and ('dividend' in str(b).lower() or '股利' in str(b))]
        R.observe('zero_dividend_blocker', zero_dividend)
        R.step('a dividend of $0.00 is not reported as exceeding anything',
               'pass' if not zero_dividend else 'fail',
               json.dumps(zero_dividend, ensure_ascii=False)[:300])

        # now do what the blocker's sentence asks: raise financing
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '25000000', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        body2 = summary(page)
        budget2 = body2.get('budget_summary') or {}
        R.observe('budget_summary_after_debt', budget2)
        R.observe('blockers_after_debt', body2.get('lock_blockers'))
        R.step('raising $25,000,000 of new debt changes the available-cash figure',
               'pass' if str(budget2.get('total_available')) != str(budget.get('total_available'))
               else 'fail',
               'available before=%s after=%s; committed before=%s after=%s'
               % (budget.get('total_available'), budget2.get('total_available'),
                  budget.get('committed_total'), budget2.get('committed_total')))
        R.step('with the financing raised, the lock is offered',
               'pass' if body2.get('can_lock') else 'fail',
               json.dumps(body2.get('lock_blockers'), ensure_ascii=False)[:500])
        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.screen(page, 'v-irreducible-t%d-r%d' % (TEAM_IX, ROUND),
                 'everything a student can reach set to zero, then $25M of debt raised')
        R.observe('summary_text', visible_text(page)[:2000])
        # leave the draft as it was found, financing-wise
        api(page, 'PATCH', DEC + 'financing/', {'financing': {
            'new_debt': '0', 'debt_repayment': '0', 'new_equity': '0',
            'dividend_per_share': '0'}})
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
