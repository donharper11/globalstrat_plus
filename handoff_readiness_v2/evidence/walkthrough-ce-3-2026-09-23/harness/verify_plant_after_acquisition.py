"""W-CE2-01, the round-level case: a plant built where an acquisition already
brought one.

verify_plant_after_acquisition.py <team-index> <round>          (queue it)
verify_plant_after_acquisition.py <team-index> <round> after    (read the result)

Walkthrough 2's P0 was a build and an acquisition in the SAME round: both
engine steps wrote a `team_plant` row with the natural key
(team, market, construction_started_round) and the round could not be
snapshotted at all. The decision boundary now refuses that pair
(verify_plant_collision.py).

What remains, and what the brief asks to see resolve, is the same market one
round later: the acquisition has COMPLETED and its plant is operational, and
the team now builds a plant of its own there. The construction start differs,
so the natural key differs; the round must process.

The Market Strategy page does not offer Build Plant in a market where the team
already holds a plant, so the build is made through the decision route the
page itself saves with, and the page is photographed beside it. Everything
written is this team's own draft.
"""
import json
import pathlib
import sys

from walk import BASE, Recorder, api, sign_in, sync_playwright, visible_text

SCRATCH = pathlib.Path(__file__).resolve().parent
TEAM_IX = int(sys.argv[1])
ROUND = int(sys.argv[2])
PHASE = sys.argv[3] if len(sys.argv) > 3 else 'queue'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('verify-plant-after-acquisition-t%d-r%d-%s' % (TEAM_IX, ROUND, PHASE), 'en')
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
STRAT = '/api/games/%d/teams/%d/context/strategy/' % (GID, TID)


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
        strat = api(page, 'GET', STRAT)['body'] or {}
        home = next((m for m in (strat.get('markets') or []) if m.get('is_home_market')), None)
        mine = [t for t in (strat.get('acquisition_targets') or []) if t.get('acquired_by_self')]
        R.observe('home_market', home)
        R.observe('acquisitions_this_team_owns', [(t.get('target_name'), t.get('market_name'),
                                                   t.get('includes_plant')) for t in mine])
        home_id = (home or {}).get('id') or (home or {}).get('market_id')

        page.goto(BASE + '/games/%d/teams/%d/decisions/market-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        tabs = page.locator('.ant-tabs-tab')
        for i in range(tabs.count()):
            if (home or {}).get('name') and home['name'] in (tabs.nth(i).text_content() or ''):
                tabs.nth(i).click(); page.wait_for_timeout(2500)
                break
        pane = page.locator('.ant-tabs-tabpane-active').last
        R.observe('home_pane_text', pane.inner_text()[:1200])
        offered = pane.locator('button', has_text='Build Plant').count()
        R.observe('build_plant_offered_where_a_plant_exists', offered)
        R.step('the page does not offer a second plant in a market that already holds one',
               'pass' if offered == 0 else 'observed', '%d Build Plant controls' % offered)
        R.screen(page, 'v-paa-t%d-r%d-home-market' % (TEAM_IX, ROUND),
                 'the home market, where the acquisition already brought a plant')

        if PHASE == 'queue':
            saved = api(page, 'PATCH', DEC + 'plants/', {'plant_decisions': [
                {'market': home_id, 'action': 'build', 'capacity_units': 0,
                 'contract_mfg_volume': 0}]})
            R.observe('plant_saved', saved)
            rows = (api(page, 'GET', DEC)['body'] or {}).get('plant_decisions') or []
            R.step('a plant build in the market of the completed acquisition is accepted',
                   'pass' if saved['status'] < 400 and rows else 'fail',
                   '%s %s' % (saved['status'], json.dumps(rows)[:250]))
        else:
            # After the round: the round processed, and the plants in that
            # market are the acquisition's and the build's, not a collision.
            R.observe('final_home_pane', visible_text(page)[:1500])
            res = api(page, 'GET', '/api/games/%d/teams/%d/results/round/%d/' % (GID, TID, ROUND))
            R.observe('results_status', res['status'])
            R.step('the round the build was made in produced results for this team',
                   'pass' if res['status'] == 200 and (res['body'] or {}).get('performance') else 'fail',
                   'HTTP %s' % res['status'])
            R.screen(page, 'v-paa-t%d-r%d-after' % (TEAM_IX, ROUND), 'after the round processed')
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
