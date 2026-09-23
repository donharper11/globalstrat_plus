"""W-CE2-02: a queued commitment can be withdrawn, and what cannot be funded
is not offered.

verify_withdraw.py <lang> <team-index> <round>

Walkthrough 2 recorded that an acquisition, a plant build and a partnership
could be added and never taken back: the card turned into a status tag and no
screen offered a cancel, so a team that queued more than it could fund was
refused the lock with no way to clear the blocker. It also recorded an
*Acquire — $25.0M* button offered to a team holding $23.4M.

This drives the real buttons on the real pages:

  1. Market Strategy — queue a plant build, read the card, click Withdraw,
     confirm the row is gone from the stored draft and the Build Plant offer
     is back;
  2. Market Strategy — queue a partnership, click Withdraw, same;
  3. Corporate Strategy — queue an acquisition, click Withdraw, same;
  4. Corporate Strategy — a target costing more than the team's unallocated
     cash: the Acquire control must be disabled and the figures must be on
     the card beside it.

Writes records/verify-withdraw-t<N>-r<R>-<lang>.json.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, sign_in, sync_playwright, visible_text)

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
R = Recorder('verify-withdraw-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
R.observe('student', STUDENT['username'])
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
STRAT = '/api/games/%d/teams/%d/context/strategy/' % (GID, TID)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales' / ('%s.json' % LANG)).read_text())


def T(key):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    return cur


def draft(page):
    return api(page, 'GET', DEC)['body'] or {}


def pane(page):
    return page.locator('.ant-tabs-tabpane-active').last


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
        api(page, 'PATCH', DEC + 'plants/', {'plant_decisions': []})
        api(page, 'PATCH', DEC + 'partnerships/', {'partnerships': []})
        api(page, 'PATCH', DEC + 'acquisitions/', {'acquisitions': []})

        # ---- Market Strategy ------------------------------------------------
        page.goto(BASE + '/games/%d/teams/%d/decisions/market-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        strat = api(page, 'GET', STRAT)['body'] or {}
        home = next((m for m in (strat.get('markets') or []) if m.get('is_home_market')), None)
        R.observe('affordability', strat.get('affordability'))
        R.step('the strategy context publishes an affordability block (W-CE2-02)',
               'pass' if isinstance(strat.get('affordability'), dict)
               and 'unallocated' in (strat.get('affordability') or {}) else 'fail',
               json.dumps(strat.get('affordability'))[:300])
        # A market that already holds a plant offers no Build control, so the
        # withdrawal is driven on the first market tab that does offer one.
        tabs = page.locator('.ant-tabs-tab')
        order = []
        for i in range(tabs.count()):
            label = (tabs.nth(i).text_content() or '')
            if (home or {}).get('name') and home['name'] in label:
                order.insert(0, i)
            else:
                order.append(i)
        chosen, bp = None, None
        for i in order:
            tabs.nth(i).click(); page.wait_for_timeout(2500)
            candidate = pane(page).locator('button', has_text=T('market_strategy.build_plant'))
            if candidate.count() and candidate.first.is_enabled():
                chosen, bp = i, candidate
                break
        R.observe('plant_tab', {'index': chosen,
                                'label': (tabs.nth(chosen).text_content() or '').strip() if chosen is not None else None})
        R.step('a market that offers Build Plant was found to drive the withdrawal on',
               'pass' if chosen is not None else 'fail',
               'tabs=%s' % json.dumps([(tabs.nth(i).text_content() or '').strip()
                                       for i in range(tabs.count())], ensure_ascii=False))
        if bp is None:
            bp = pane(page).locator('button', has_text=T('market_strategy.build_plant'))
        R.observe('build_plant_offered_before', bp.count())
        if bp.count():
            bp.first.click(); page.wait_for_timeout(4000)
        rows = draft(page).get('plant_decisions') or []
        R.step('1: a plant build is queued', 'pass' if rows else 'fail', json.dumps(rows)[:200])
        R.screen(page, 'v-wd-t%d-r%d-01-plant-queued' % (TEAM_IX, ROUND))
        queued_tag = T('market_strategy.plant_queued') in pane(page).inner_text()
        R.step('1: the card says the plant build is queued, instead of offering the button again',
               'pass' if queued_tag and not pane(page).locator(
                   'button', has_text=T('market_strategy.build_plant')).count() else 'fail',
               'tag=%s build_button_still_offered=%s'
               % (queued_tag, pane(page).locator('button', has_text=T('market_strategy.build_plant')).count()))
        wd = pane(page).locator('button', has_text=T('market_strategy.withdraw'))
        R.observe('plant_withdraw_controls', wd.count())
        R.step('1: a Withdraw control is offered for the queued plant', 'pass' if wd.count() else 'fail',
               '%d controls' % wd.count())
        if wd.count():
            wd.first.click(); page.wait_for_timeout(4000)
        after = draft(page).get('plant_decisions') or []
        R.step('1: Withdraw removes the queued plant from the stored draft',
               'pass' if not after else 'fail', json.dumps(after)[:200])
        R.screen(page, 'v-wd-t%d-r%d-02-plant-withdrawn' % (TEAM_IX, ROUND))
        R.step('1: the Build Plant offer is back after the withdrawal',
               'pass' if pane(page).locator(
                   'button', has_text=T('market_strategy.build_plant')).count() else 'fail')

        plus = pane(page).locator('button', has_text='+ ')
        R.observe('partnership_offers', plus.count())
        if plus.count():
            plus.first.click(); page.wait_for_timeout(4000)
        prows = draft(page).get('partnerships') or []
        R.step('2: a partnership is queued', 'pass' if prows else 'fail', json.dumps(prows)[:200])
        R.screen(page, 'v-wd-t%d-r%d-03-partnership-queued' % (TEAM_IX, ROUND))
        pwd = pane(page).locator('button', has_text=T('market_strategy.withdraw'))
        R.step('2: a Withdraw control is offered for the queued partnership',
               'pass' if pwd.count() else 'fail', '%d controls' % pwd.count())
        if pwd.count():
            pwd.first.click(); page.wait_for_timeout(4000)
        pafter = draft(page).get('partnerships') or []
        R.step('2: Withdraw removes the queued partnership from the stored draft',
               'pass' if not pafter else 'fail', json.dumps(pafter)[:200])
        R.screen(page, 'v-wd-t%d-r%d-04-partnership-withdrawn' % (TEAM_IX, ROUND))

        # ---- Corporate Strategy › M&A --------------------------------------
        page.goto(BASE + '/games/%d/teams/%d/decisions/corporate-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        tab = page.locator('.ant-tabs-tab', has_text=T('corporate_strategy.ma'))
        if tab.count():
            tab.first.click(); page.wait_for_timeout(3000)
        strat = api(page, 'GET', STRAT)['body'] or {}
        targets = strat.get('acquisition_targets') or []
        unallocated = ((strat.get('affordability') or {}).get('unallocated'))
        R.observe('unallocated', unallocated)
        R.observe('targets', [{k: t.get(k) for k in
                  ('target_name', 'base_acquisition_cost', 'available', 'locked_reasons')}
                  for t in targets])
        acq = pane(page).locator('button', has_text=T('corporate_strategy.acquire'))
        enabled = [i for i in range(acq.count()) if acq.nth(i).is_enabled()]
        disabled = [i for i in range(acq.count()) if not acq.nth(i).is_enabled()]
        R.observe('acquire_buttons', {'total': acq.count(), 'enabled': len(enabled),
                                      'disabled': len(disabled)})
        R.screen(page, 'v-wd-t%d-r%d-05-ma-offers' % (TEAM_IX, ROUND))
        pane_text = pane(page).inner_text()
        R.observe('ma_pane_text', pane_text[:2500])
        # 4: an offer the team cannot fund is disabled and says so
        unaffordable = [t for t in targets if t.get('available')
                        and unallocated is not None
                        and float(t.get('base_acquisition_cost') or 0) > float(unallocated)]
        R.observe('unaffordable_available_targets', [t.get('target_name') for t in unaffordable])
        if unaffordable:
            notice = T('corporate_strategy.not_affordable').split('{{')[0].strip()
            R.step('4: an acquisition the team cannot fund is disabled, with the figures beside it',
                   'pass' if len(disabled) >= len(unaffordable) and (notice in pane_text or not notice)
                   else 'fail',
                   'unaffordable=%s disabled_buttons=%d notice_on_card=%s'
                   % ([t.get('target_name') for t in unaffordable], len(disabled), notice in pane_text))
        else:
            R.step('4: an acquisition the team cannot fund is disabled', 'observed',
                   'every available target is affordable this round (unallocated=%s)' % unallocated)
        if enabled:
            acq.nth(enabled[0]).click(); page.wait_for_timeout(4500)
        arows = draft(page).get('acquisitions') or []
        R.step('3: an acquisition is queued', 'pass' if arows else 'fail', json.dumps(arows)[:200])
        R.screen(page, 'v-wd-t%d-r%d-06-acquisition-queued' % (TEAM_IX, ROUND))
        awd = pane(page).locator('button', has_text=T('corporate_strategy.withdraw'))
        R.step('3: a Withdraw control is offered for the queued acquisition',
               'pass' if awd.count() else 'fail', '%d controls' % awd.count())
        if awd.count():
            awd.first.click(); page.wait_for_timeout(4500)
        aafter = draft(page).get('acquisitions') or []
        R.step('3: Withdraw removes the queued acquisition from the stored draft',
               'pass' if not aafter else 'fail', json.dumps(aafter)[:200])
        R.screen(page, 'v-wd-t%d-r%d-07-acquisition-withdrawn' % (TEAM_IX, ROUND))
        R.observe('final_draft', {k: draft(page).get(k) for k in
                                  ('plant_decisions', 'partnerships', 'acquisitions')})
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
