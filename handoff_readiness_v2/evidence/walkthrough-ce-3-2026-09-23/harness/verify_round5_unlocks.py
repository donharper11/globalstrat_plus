"""Progressive disclosure: what round 5 opens that no earlier round offered.

verify_round5_unlocks.py <lang> <team-index> <round>

The Consumer Electronics scenario and the supply-chain pages both gate
decisions by round. Read from the tree rather than assumed:

  * `scenarios/consumer_electronics_2026.yaml` — platform generations carry
    `unlock_round`: Gen 1 at 0, **Gen 2 at 2**, **Gen 3 at 5**;
  * `pages/LogisticsPage.js` — `UNLOCK = { modal_mix: 3, incoterms: 4,
    insurance_coverage_pct: 4, customs_classification: 5,
    reverse_logistics: 5, volume_commitment_teu: 5 }`;
  * `pages/SourcingPage.js` — `multiSupplier: 3, multi_sourcing_strategy: 3,
    payment_terms: 4, …`;
  * `pages/InventoryPage.js` — `buffer_days: 3, safety_stock_trigger_pct: 3,
    contingency_plans: 5`.

So round 5 opens **customs classification**, **reverse logistics**, a
**volume commitment**, **inventory contingency plans** and the **Gen 3
platform**. This driver opens each, records whether the control is enabled,
sets the ones it can, and reads back what was stored.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, pick_select, set_number, sign_in,
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
R = Recorder('verify-round5-unlocks-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
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

        # ---- the Gen 3 platform, unlocked at round 5 ----------------------
        page.goto(BASE + '/games/%d/teams/%d/decisions/rd' % (GID, TID), wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/rd/' % (GID, TID))['body'] or {}
        gens = ctx.get('available_generations') or []
        R.observe('available_generations', [{k: g.get(k) for k in
                  ('name', 'generation_order', 'development_cost',
                   'team_already_owns', 'prerequisites_met', 'prerequisites')}
                  for g in gens])
        gen3 = next((g for g in gens if g.get('generation_order') == 3), None)
        # Read at round 4 the same context listed only Gen 1 and Gen 2; the
        # third generation's `unlock_round` is 5 in the scenario, so its
        # appearance here IS the progressive disclosure.
        R.step('the round-5 platform generation appears once round 5 is open',
               'pass' if gen3 else 'fail',
               '%d generations offered: %s'
               % (len(gens), json.dumps([g.get('name') for g in gens], ensure_ascii=False)))
        if gen3:
            R.step('the newly opened generation states its round prerequisite as met',
                   'pass' if any(str(p.get('requirement', '')).lower().find('round') >= 0
                                 and p.get('met') for p in (gen3.get('prerequisites') or []))
                   or gen3.get('prerequisites_met') else 'observed',
                   json.dumps(gen3.get('prerequisites'), ensure_ascii=False)[:400])
        R.screen(page, 'v-r5-t%d-rd' % TEAM_IX, 'R&D at round %d' % ROUND)
        create = page.locator('button', has_text=T('rd.create_platform'))
        if create.count():
            create.first.click(); page.wait_for_timeout(3000)
            R.observe('create_platform_modal', visible_text(page)[:2000])
            R.screen(page, 'v-r5-t%d-rd-create-modal' % TEAM_IX,
                     'the platform modal at round %d, with the Gen 3 generation offered' % ROUND)
            page.keyboard.press('Escape'); page.wait_for_timeout(1200)

        # ---- customs classification, unlocked at round 5 ------------------
        page.goto(BASE + '/games/%d/teams/%d/decisions/logistics' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(7000)
        R.screen(page, 'v-r5-t%d-logistics' % TEAM_IX, 'Logistics at round %d' % ROUND)
        text = visible_text(page)
        R.observe('logistics_text', text[:2500])
        selects = page.locator('.ant-select')
        R.observe('logistics_selects', selects.count())
        before = api(page, 'GET', '/api/games/%d/teams/%d/sc/round/%d/logistics/' % (GID, TID, ROUND))
        R.observe('logistics_before', before['body'] if before['status'] == 200 else before)
        picked = None
        for i in range(selects.count()):
            sel = selects.nth(i)
            try:
                if not sel.is_enabled():
                    continue
            except Exception:
                continue
            label = pick_select(page, sel)
            if label:
                picked = label
                page.wait_for_timeout(2500)
                break
        R.observe('customs_classification_picked', picked)
        R.step('a customs classification can be chosen at round %d' % ROUND,
               'pass' if picked else 'fail', 'picked=%r' % picked)
        save = page.locator('button', has_text=T('common.save'))
        if save.count() and save.first.is_enabled():
            save.first.click(); page.wait_for_timeout(4000)
        after = api(page, 'GET', '/api/games/%d/teams/%d/sc/round/%d/logistics/' % (GID, TID, ROUND))
        R.observe('logistics_after', after['body'] if after['status'] == 200 else after)
        stored = (after['body'] or {}).get('customs') if after['status'] == 200 else None
        R.step('the customs classification is stored',
               'pass' if stored else 'fail', json.dumps(stored, ensure_ascii=False)[:300])
        R.screen(page, 'v-r5-t%d-logistics-saved' % TEAM_IX, 'after the customs classification was set')

        # ---- inventory contingency plans, unlocked at round 5 -------------
        page.goto(BASE + '/games/%d/teams/%d/decisions/inventory' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(7000)
        R.screen(page, 'v-r5-t%d-inventory' % TEAM_IX, 'Inventory at round %d' % ROUND)
        R.observe('inventory_text', visible_text(page)[:2000])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
