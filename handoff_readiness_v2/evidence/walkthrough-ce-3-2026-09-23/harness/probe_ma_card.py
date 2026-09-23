"""Read-only: what the M&A card offers, and what it says when it does not.

probe_ma_card.py <lang> <team-index> <round>

W-CE2-02's second half: an *Acquire — $25.0M* button was offered to a team
holding $23.4M. Since the repair an offer the team cannot fund is disabled
with the figures beside it. This reads the card without changing a single
decision: the button states, the enabled/disabled state of each, the
affordability block the context publishes, and the exact sentences on the
card.
"""
import json
import pathlib
import sys

from walk import BASE, Recorder, api, sign_in, sync_playwright

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
R = Recorder('probe-ma-card-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales' / ('%s.json' % LANG)).read_text())


def T(key):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    return cur


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1200})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG, password=STUDENT.get('student_id'))
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        api(page, 'PUT', '/api/user/preferences/', {'language': LANG})
        page.goto(BASE + '/games/%d/teams/%d/decisions/corporate-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        tab = page.locator('.ant-tabs-tab', has_text=T('corporate_strategy.ma'))
        if tab.count():
            tab.first.click(); page.wait_for_timeout(3000)
        pane = page.locator('.ant-tabs-tabpane-active').last
        strat = api(page, 'GET', '/api/games/%d/teams/%d/context/strategy/' % (GID, TID))['body'] or {}
        aff = strat.get('affordability') or {}
        targets = strat.get('acquisition_targets') or []
        R.observe('affordability', aff)
        R.observe('targets', [{k: t.get(k) for k in
                  ('target_name', 'market_name', 'base_acquisition_cost', 'available',
                   'min_round_available', 'locked_reasons')} for t in targets])
        acq = pane.locator('button', has_text=T('corporate_strategy.acquire'))
        states = [{'label': (acq.nth(i).text_content() or '').strip(),
                   'enabled': acq.nth(i).is_enabled()} for i in range(acq.count())]
        R.observe('acquire_buttons', states)
        text = pane.inner_text()
        R.observe('ma_pane_text', text[:3000])
        R.screen(page, 'v-ma-card-t%d-r%d' % (TEAM_IX, ROUND), 'the M&A card as it stands')

        unallocated = aff.get('unallocated')
        available = [t for t in targets if t.get('available')]
        unaffordable = [t for t in available if unallocated is not None
                        and float(t.get('base_acquisition_cost') or 0) > float(unallocated)]
        R.observe('unaffordable_available', [t.get('target_name') for t in unaffordable])
        # the sentence the card must carry, with its placeholders removed
        stem = T('corporate_strategy.not_affordable').split('{{')[0].strip()
        if unaffordable:
            all_disabled = all(not s['enabled'] for s in states)
            R.step('an acquisition the team cannot fund is offered disabled, not enabled (W-CE2-02)',
                   'pass' if states and all_disabled else 'fail',
                   'unallocated=%s unaffordable=%s buttons=%s'
                   % (unallocated, [t.get('target_name') for t in unaffordable], json.dumps(states, ensure_ascii=False)))
            R.step('the card states the figures beside the disabled offer',
                   'pass' if stem and stem in text else 'fail',
                   'looking for %r; card says: %s' % (stem, ' / '.join(
                       l for l in text.splitlines() if stem and stem[:6] in l)[:300]))
        else:
            R.step('an acquisition the team cannot fund is offered disabled', 'observed',
                   'nothing available this round costs more than the unallocated %s' % unallocated)
        for t in targets:
            if not t.get('available'):
                R.step('unavailable target %r says why' % t.get('target_name'),
                       'pass' if t.get('locked_reasons') else 'fail',
                       json.dumps(t.get('locked_reasons'), ensure_ascii=False)[:200])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
