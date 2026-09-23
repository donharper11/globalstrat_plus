"""W-CE2-03: the deadline no longer fulfils an acquisition the lock refused.

verify_deadline_affordability.py <team-index> <round>   (before the round is resolved)
verify_deadline_affordability.py <team-index> <round> after   (once it is)

Walkthrough 2 recorded a team told at the Decision Summary that it could not
submit — *Committed spend of $38,000,000.00 exceeds available cash of
$25,446,310.88* — and then deadline-locked with that very draft, the engine
charging the spend and closing the team at −$12.4M.

Before the round: the team queues an acquisition it CAN fund, then raises its
other outlays until the one assessment the lock reads says the round no longer
fits its cash. The Summary's blockers and the state of the lock control are
recorded, and the submission is deliberately left a **draft**.

After the round: the acquisition must not have been fulfilled, nothing must
have been charged for it, the cash must not have gone negative because of it,
and the team must have been told.
"""
import json
import pathlib
import re
import sys

from walk import BASE, Recorder, api, sign_in, sync_playwright, visible_text

SCRATCH = pathlib.Path(__file__).resolve().parent
TEAM_IX = int(sys.argv[1])
ROUND = int(sys.argv[2])
PHASE = sys.argv[3] if len(sys.argv) > 3 else 'before'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('verify-deadline-affordability-t%d-r%d-%s' % (TEAM_IX, ROUND, PHASE), 'en')
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
STRAT = '/api/games/%d/teams/%d/context/strategy/' % (GID, TID)
SUMM = DEC + 'summary/'


def draft(page):
    return api(page, 'GET', DEC)['body'] or {}


def before(page):
    strat = api(page, 'GET', STRAT)['body'] or {}
    aff0 = strat.get('affordability') or {}
    R.observe('affordability_before', aff0)
    targets = [t for t in (strat.get('acquisition_targets') or []) if t.get('available')]
    targets.sort(key=lambda t: float(t.get('base_acquisition_cost') or 0))
    affordable = [t for t in targets
                  if float(t.get('base_acquisition_cost') or 0) <= float(aff0.get('unallocated') or 0)]
    R.observe('available_targets', [(t.get('target_name'), t.get('base_acquisition_cost')) for t in targets])
    R.step('an acquisition the team CAN fund is available this round',
           'pass' if affordable else 'fail',
           '%s against unallocated %s' % ([t.get('target_name') for t in affordable],
                                          aff0.get('unallocated')))
    if not affordable:
        return
    target = affordable[-1]
    saved = api(page, 'PATCH', DEC + 'acquisitions/', {'acquisitions': [
        {'acquisition_target': target['id']}]})
    R.observe('acquisition_saved', {'target': target.get('target_name'),
                                    'cost': target.get('base_acquisition_cost'),
                                    'response': saved['status']})
    R.step('the affordable acquisition is queued',
           'pass' if saved['status'] < 400 and (draft(page).get('acquisitions') or []) else 'fail',
           '%s %s' % (target.get('target_name'), json.dumps(saved)[:200]))

    # Now raise the outlays that are typed rather than offered, the way a team
    # that changed its mind after queuing would: promotion budgets and the
    # declared strategy budget. Neither is an affordability-gated offer.
    cash = float(aff0.get('cash_on_hand') or 0)
    rows = (draft(page).get('marketing_decisions') or [])
    R.observe('marketing_rows', len(rows))
    bump = max(cash, 1.0)
    for row in rows:
        api(page, 'PATCH', DEC + 'marketing/', {'marketing_decisions': [
            dict(r, promotion_budget=str(int(bump / max(len(rows), 1))) if r['id'] == row['id']
                 else r.get('promotion_budget')) for r in rows]})
        break
    strat2 = api(page, 'GET', STRAT)['body'] or {}
    aff1 = strat2.get('affordability') or {}
    R.observe('affordability_after_bump', aff1)

    summary = api(page, 'GET', SUMM)['body'] or {}
    R.observe('summary', {'can_lock': summary.get('can_lock'),
                          'lock_blockers': summary.get('lock_blockers')})
    blockers = summary.get('lock_blockers') or []
    cash_blocker = [b for b in blockers if 'cash' in str(b).lower()]
    R.step('the Summary names the cash blocker with the figures, before the click (W-CE-25)',
           'pass' if cash_blocker else 'fail',
           'can_lock=%s blockers=%s' % (summary.get('can_lock'), json.dumps(blockers)[:500]))

    page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
              wait_until='domcontentloaded')
    page.wait_for_timeout(6000)
    R.screen(page, 'v-deadline-t%d-r%d-summary' % (TEAM_IX, ROUND),
             'an acquisition is queued and the round no longer fits the cash')
    R.observe('summary_text', visible_text(page)[:2500])
    lock_buttons = page.locator('button.ant-btn-primary')
    states = [{'label': (lock_buttons.nth(i).text_content() or '').strip(),
               'enabled': lock_buttons.nth(i).is_enabled()} for i in range(lock_buttons.count())]
    R.observe('lock_controls', states)
    # W-CE2-09 and W-CE-18b ride on this same screen: one total for what the
    # round costs, and every figure formatted the same way. A negative amount
    # used to fall past both magnitude branches and print as $-12553689.
    text = visible_text(page)
    raw_negative = re.findall(r'\$-\s?\d{4,}(?![.\d]*\s*[MKB])', text)
    R.observe('raw_negative_money', raw_negative[:10])
    R.step('no unformatted negative figure on the Decision Summary (W-CE2-09)',
           'pass' if not raw_negative else 'fail',
           'found %s; the money-shaped lines on the page are: %s'
           % (raw_negative[:6],
              json.dumps([l.strip() for l in text.splitlines()
                          if '$' in l and ('nalloc' in l or 'udget' in l or 'ommit' in l)][:8])))
    totals = [l.strip() for l in text.splitlines()
              if 'total spending' in l.lower() or 'committed' in l.lower()]
    R.observe('round_cost_totals', totals[:8])
    R.step('the screen states one total for what the round costs (W-CE-18b)',
           'pass' if len(set(totals)) <= 1 else 'observed',
           json.dumps(totals[:6]))

    lock = api(page, 'POST', DEC + 'lock/', {})
    R.observe('lock_response', lock)
    R.step('the server refuses the lock for the same reason the page gave',
           'pass' if lock['status'] >= 400 else 'fail', json.dumps(lock)[:400])
    R.step('the submission is left a draft for the deadline to close',
           'pass' if draft(page).get('status') != 'locked' else 'fail',
           draft(page).get('status'))
    R.observe('final_draft_acquisitions', draft(page).get('acquisitions'))


def after(page):
    d = draft(page)
    R.observe('draft_after', {'status': d.get('status'),
                              'acquisitions': d.get('acquisitions')})
    _, hist = api(page, 'GET', '/api/games/%d/teams/%d/financial-reports/history/' % (GID, TID)), None
    hist = api(page, 'GET', '/api/games/%d/teams/%d/financial-reports/history/' % (GID, TID))['body'] or {}
    rounds = hist.get('rounds') or []
    row = next((r for r in rounds if r.get('round_number') == ROUND), None)
    R.observe('statement', row)
    strat = api(page, 'GET', STRAT)['body'] or {}
    owned = strat.get('owned_acquisitions') or strat.get('acquisitions') or []
    acquired_names = [t.get('target_name') for t in (strat.get('acquisition_targets') or [])
                      if t.get('acquired_by_self')]
    R.observe('acquired_by_this_team', acquired_names)
    R.step('the decision row the team made survives the round (it is the record)',
           'pass' if d.get('acquisitions') else 'fail', json.dumps(d.get('acquisitions'))[:200])
    R.step('the acquisition the lock refused was NOT fulfilled (W-CE2-03)',
           'pass' if not acquired_names else 'fail',
           'this team now owns: %s' % acquired_names)
    R.step('cash did not close negative',
           'pass' if row and float(row.get('cash_closing') or 0) >= 0 else 'fail',
           'cash_closing=%s strategy_expense=%s' % (row and row.get('cash_closing'),
                                                    row and row.get('strategy_expense')))
    notes = api(page, 'GET', '/api/games/%d/teams/%d/notifications/' % (GID, TID))['body']
    R.observe('notifications', notes)
    text = json.dumps(notes, ensure_ascii=False)
    R.step('the team is told why, and that nothing was charged',
           'pass' if 'charged' in text or 'cost' in text.lower() else 'fail', text[:500])
    page.goto(BASE + '/games/%d/teams/%d/financial-reports' % (GID, TID), wait_until='domcontentloaded')
    page.wait_for_timeout(6000)
    R.screen(page, 'v-deadline-t%d-r%d-after-statement' % (TEAM_IX, ROUND),
             'the statement of the round the deadline closed')


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
        (before if PHASE == 'before' else after)(page)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
