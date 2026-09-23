"""W-CE2-01: two plants in one market, at the save and at the round.

verify_plant_collision.py <team-index> <round>

Walkthrough 2 recorded a round that could not be processed at all: a team
built a plant in the same market as an acquisition it completed, both engine
steps wrote a `team_plant` row with the same natural key, and every console
control answered 500 with the round stuck at `closed / FAILED`.

This drives the repaired boundary from the browser, in both languages:

  A. queue a plant build in the home market, then try to queue the
     acquisition of a target that brings a plant in that same market:
     the save is refused and the refusal names the market;
  B. the same two decisions in the other order: plant withdrawn,
     acquisition queued, then Build Plant refused, naming the market;
  C. the same refusals read in Simplified Chinese, by putting the acting
     student's language through the route the in-game switch calls;
  D. a second Build Plant in a market that already has one queued
     (the input-snapshot collision the repair also names);
  E. that a refused save leaves the draft exactly as it was.

The round-level case the brief asks for — a plant built in the market of an
acquisition that has ALREADY completed — is driven by the walkthrough itself
in the round after this one and checked by check_round.py.

Writes only this team's own draft decisions, the way a student would.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, sign_in, sync_playwright, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
TEAM_IX = int(sys.argv[1])
ROUND = int(sys.argv[2])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('verify-plant-collision-t%d-r%d' % (TEAM_IX, ROUND), 'en')
R.observe('team', team.get('team_name'))
R.observe('student', STUDENT['username'])
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
STRAT = '/api/games/%d/teams/%d/context/strategy/' % (GID, TID)


def draft(page):
    return api(page, 'GET', DEC)['body'] or {}


def set_language(page, lang):
    return api(page, 'PUT', '/api/user/preferences/', {'language': lang})


def save_plants(page, rows):
    return api(page, 'PATCH', DEC + 'plants/', {'plant_decisions': rows})


def save_acquisitions(page, rows):
    return api(page, 'PATCH', DEC + 'acquisitions/', {'acquisitions': rows})


def refusal_text(response):
    body = response.get('body')
    if isinstance(body, dict):
        for key in ('detail', 'error', 'message', 'plant_decisions', 'acquisitions'):
            value = body.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return ' | '.join(str(v) for v in value)
        return json.dumps(body, ensure_ascii=False)[:600]
    return str(body)[:600]


def han(text):
    return any('一' <= ch <= '鿿' for ch in text or '')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], 'en', password=STUDENT.get('student_id'), rec=R)
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        set_language(page, 'en')

        strat = api(page, 'GET', STRAT)['body'] or {}
        home = next((m for m in (strat.get('markets') or []) if m.get('is_home_market')), None)
        targets = strat.get('acquisition_targets') or []
        R.observe('home_market', home)
        R.observe('targets', [{k: t.get(k) for k in
                  ('id', 'target_name', 'market_id', 'market_name', 'includes_plant',
                   'base_acquisition_cost', 'available', 'locked_reasons')} for t in targets])
        if not home:
            R.step('the team has a home market to build in', 'fail'); browser.close(); return R.finish()
        home_id = home.get('id') or home.get('market_id')
        target = next((t for t in targets
                       if t.get('market_id') == home_id and t.get('includes_plant')
                       and t.get('available')), None)
        R.step('a target that brings a plant in the home market is available this round',
               'pass' if target else 'fail',
               'home=%s target=%s' % (home.get('name'), target and target.get('target_name')))
        if not target:
            browser.close(); return R.finish()

        save_plants(page, [])
        save_acquisitions(page, [])

        # --- A. plant first, then the acquisition -------------------------
        a0 = save_plants(page, [{'market': home_id, 'action': 'build',
                                 'capacity_units': 0, 'contract_mfg_volume': 0}])
        R.observe('A_plant_saved', a0)
        R.step('A: a plant build in the home market is saved', 'pass' if a0['status'] < 400 else 'fail',
               json.dumps(a0)[:300])
        a1 = save_acquisitions(page, [{'acquisition_target': target['id']}])
        R.observe('A_acquisition_refused', a1)
        text_a = refusal_text(a1)
        R.step('A: the acquisition save is refused while a plant is queued in that market',
               'pass' if a1['status'] == 400 else 'fail', '%s %s' % (a1['status'], text_a[:300]))
        R.step('A: the refusal names the market and the target',
               'pass' if (home.get('name') or '') in text_a and (target.get('target_name') or '') in text_a
               else 'fail', text_a[:400])
        d_a = draft(page)
        R.step('A: the refused save changed nothing (E)',
               'pass' if not (d_a.get('acquisitions') or []) and len(d_a.get('plant_decisions') or []) == 1
               else 'fail',
               'plants=%s acquisitions=%s' % (json.dumps(d_a.get('plant_decisions'))[:200],
                                              json.dumps(d_a.get('acquisitions'))[:200]))

        # --- D. a second build in the same market -------------------------
        d1 = save_plants(page, [
            {'market': home_id, 'action': 'build', 'capacity_units': 0, 'contract_mfg_volume': 0},
            {'market': home_id, 'action': 'build', 'capacity_units': 0, 'contract_mfg_volume': 0}])
        R.observe('D_two_builds_refused', d1)
        text_d = refusal_text(d1)
        R.step('D: two plant builds in one market are refused, naming the market',
               'pass' if d1['status'] == 400 and (home.get('name') or '') in text_d else 'fail',
               '%s %s' % (d1['status'], text_d[:300]))

        # --- C. the same refusals in Simplified Chinese -------------------
        set_language(page, 'zh-CN')
        strat_zh = api(page, 'GET', STRAT)['body'] or {}
        home_zh = next((m for m in (strat_zh.get('markets') or []) if m.get('is_home_market')), None)
        market_zh = (home_zh or {}).get('name')
        target_zh = next((t for t in (strat_zh.get('acquisition_targets') or [])
                          if t.get('id') == target['id']), {})
        R.observe('home_market_zh', home_zh)
        c1 = save_acquisitions(page, [{'acquisition_target': target['id']}])
        text_c = refusal_text(c1)
        R.observe('C_acquisition_refused_zh', c1)
        R.step('C: the same refusal is Chinese for a Chinese-reading student',
               'pass' if c1['status'] == 400 and han(text_c) else 'fail', text_c[:400])
        R.step('C: the Chinese refusal names the market in Chinese',
               'pass' if market_zh and market_zh in text_c else 'fail',
               'market=%r target=%r refusal=%r'
               % (market_zh, target_zh.get('target_name'), text_c[:300]))
        c2 = save_plants(page, [
            {'market': home_id, 'action': 'build', 'capacity_units': 0, 'contract_mfg_volume': 0},
            {'market': home_id, 'action': 'build', 'capacity_units': 0, 'contract_mfg_volume': 0}])
        text_c2 = refusal_text(c2)
        R.observe('C_two_builds_refused_zh', c2)
        R.step('C: two builds in one market are refused in Chinese, naming the market',
               'pass' if c2['status'] == 400 and han(text_c2) and (market_zh or '') in text_c2
               else 'fail', text_c2[:400])
        set_language(page, 'en')

        # --- B. the other order -------------------------------------------
        b0 = save_plants(page, [])
        R.step('B: the queued plant is withdrawn (W-CE2-02)',
               'pass' if b0['status'] < 400 and not (draft(page).get('plant_decisions') or []) else 'fail',
               json.dumps(b0)[:200])
        b1 = save_acquisitions(page, [{'acquisition_target': target['id']}])
        R.observe('B_acquisition_saved', b1)
        R.step('B: with no plant queued the acquisition saves',
               'pass' if b1['status'] < 400 and (draft(page).get('acquisitions') or []) else 'fail',
               json.dumps(b1)[:300])
        b2 = save_plants(page, [{'market': home_id, 'action': 'build',
                                 'capacity_units': 0, 'contract_mfg_volume': 0}])
        text_b = refusal_text(b2)
        R.observe('B_plant_refused', b2)
        R.step('B: the plant build is then refused, naming the market',
               'pass' if b2['status'] == 400 and (home.get('name') or '') in text_b else 'fail',
               '%s %s' % (b2['status'], text_b[:300]))

        page.goto(BASE + '/games/%d/teams/%d/decisions/market-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        R.screen(page, 'v-collision-t%d-r%d-market-strategy' % (TEAM_IX, ROUND),
                 'an acquisition bringing a plant in this market is queued')
        R.observe('market_strategy_text', visible_text(page)[:1500])
        page.goto(BASE + '/games/%d/teams/%d/decisions/corporate-strategy' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        R.screen(page, 'v-collision-t%d-r%d-corporate' % (TEAM_IX, ROUND), 'the queued acquisition')
        R.observe('final_draft', {k: draft(page).get(k) for k in ('plant_decisions', 'acquisitions')})
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
