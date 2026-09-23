"""Finish a team's round: complete every marketing row, then lock.

lock_round.py <lang> <team-index> <round>

`student_play.py` drives the interesting paths (edge cases, refusals); a team
that created a product or entered a market during the round is then left with
a product-market row the lock validator asks for. This driver does what a
student would do next: open every product tab on the marketing page, fill the
row where nothing is stored, and lock from the Decision Summary -- recording
the blockers the page lists and any refusal the server answers with (W-CE-25).
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, modal_text, pick_select, set_number,
                  sign_in, sync_playwright, visible_text)

LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('lock-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales' / ('%s.json' % LANG)).read_text())


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


def stored_rows(page):
    d = api(page, 'GET', DEC)['body']
    return {(int(r.get('team_product')), int(r.get('market'))): r
            for r in (d.get('marketing_decisions') or [])}


def complete_marketing(page):
    ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/marketing/' % (GID, TID))['body']
    pms = (ctx or {}).get('product_markets') or []
    bands = (ctx or {}).get('price_bands') or {}
    missing = []
    stored = stored_rows(page)
    for pm in pms:
        for mk in (pm.get('markets') or []):
            key = (int(pm.get('product_id')), int(mk.get('market_id')))
            row = stored.get(key)
            if not row or row.get('retail_price') in (None, '') or not row.get('campaign_focus_feature_ids'):
                missing.append((pm, mk, key))
    R.observe('rows_to_complete', [(pm.get('product_name'),
                                    mk.get('market__name') or mk.get('market_name'))
                                   for pm, mk, _ in missing])
    if not missing:
        R.step('every product-market row already carries a decision', 'pass')
        return
    page.goto(BASE + '/games/%d/teams/%d/decisions/marketing' % (GID, TID),
              wait_until='domcontentloaded')
    page.wait_for_timeout(6000)
    done = []
    for pm, mk, key in missing:
        pname = pm.get('product_name')
        mname = mk.get('market__name') or mk.get('market_name')
        tabs = page.locator('.ant-tabs-tab')
        labels = [(tabs.nth(i).text_content() or '').strip() for i in range(tabs.count())]
        ix = next((i for i, l in enumerate(labels) if pname and pname in l), None)
        reached = False
        if ix is None:
            # a market tab first, then its product tabs
            mix = next((i for i, l in enumerate(labels) if mname and mname in l), None)
            if mix is not None:
                tabs.nth(mix).click(); page.wait_for_timeout(2500)
                tabs = page.locator('.ant-tabs-tab')
                labels = [(tabs.nth(i).text_content() or '').strip() for i in range(tabs.count())]
                ix = next((i for i, l in enumerate(labels) if pname and pname in l), None)
                # MarketingPage renders the product card DIRECTLY, with no
                # inner product tab, when a market holds exactly one product
                # (`items.length === 1`), and the product's name is printed
                # ONLY in that inner tab label -- so with one product the name
                # is nowhere on the page and cannot be matched. The market tab
                # is then itself the row. (That missing name is a finding of
                # its own; see the report's new-defects table.)
                if ix is None:
                    reached = True
                    R.observe('row_reached_without_product_name',
                              (R.record['observed'].get('row_reached_without_product_name') or [])
                              + [[pname, mname]])
        if ix is None and not reached:
            R.step('reach the row %s / %s' % (pname, mname), 'fail',
                   json.dumps(labels, ensure_ascii=False)[:250])
            continue
        if not reached:
            tabs.nth(ix).click(); page.wait_for_timeout(2500)
        band = bands.get('%s_%s' % (pm.get('product_id'), mk.get('market_id'))) or {}
        price = int(band.get('anchor') or 300)
        p = pane(page)
        # The focus goes on FIRST: the page saves the whole section on every
        # change, and a row with promotion and no focus is refused (W-CE-04),
        # which would leave the price unsaved.
        tags = p.locator('.ant-tag[style*="cursor"]')
        chosen = any('\u2713' in (tags.nth(i).text_content() or '')
                     for i in range(tags.count()))
        if tags.count() and not chosen:
            tags.first.click(); page.wait_for_timeout(2500)
        nums = p.locator('.ant-input-number-input')
        if nums.count() >= 4:
            set_number(page, nums.nth(0), price); page.wait_for_timeout(2000)
            set_number(page, nums.nth(1), 3000); page.wait_for_timeout(2000)
        sel = p.locator('.ant-select').first
        if sel.count():
            pick_select(page, sel)
        cb = p.locator('.ant-checkbox-input')
        if cb.count() and not cb.first.is_checked():
            cb.first.click(); page.wait_for_timeout(500)
        nums = p.locator('.ant-input-number-input')
        if nums.count() >= 4:
            set_number(page, nums.nth(3), 100000)
        page.wait_for_timeout(4000)
        after = stored_rows(page).get(key)
        done.append((pname, mname, bool(after and after.get('campaign_focus_feature_ids'))))
    R.observe('rows_completed', done)
    R.step('the rows the lock asks for were completed from the page',
           'pass' if done and all(x[2] for x in done) else 'fail',
           json.dumps(done, ensure_ascii=False)[:300])
    R.screen(page, 'x-t%d-r%d-marketing-completed' % (TEAM_IX, ROUND))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'))
        R.step('student %s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.wait_for_timeout(2500)
        for _ in range(5):
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if not b.count():
                break
            b.last.click(); page.wait_for_timeout(1000)
        if (api(page, 'GET', DEC)['body'] or {}).get('status') == 'locked':
            R.step('round %d already locked for this team' % ROUND, 'observed')
            browser.close(); return R.finish()
        complete_marketing(page)

        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        s = api(page, 'GET', DEC + 'summary/')['body']
        R.observe('summary', {k: s.get(k) for k in ('can_lock', 'lock_blockers')}
                  if isinstance(s, dict) else s)
        txt = visible_text(page)
        R.observe('summary_spend_lines',
                  [l.strip() for l in txt.splitlines()
                   if '$' in l and ('udget' in l or 'pend' in l or 'Unallocated' in l
                                    or '预算' in l or '支出' in l)][:10])
        # W-CE-13: the supply-chain sections must read as optional, not as
        # requirements with a "Fix in ..." link.
        R.observe('summary_optional_lines',
                  [l.strip() for l in txt.splitlines()
                   if T('summary_page.optional') in l or 'Fix in' in l or '前往' in l][:10])
        for name in ('sourcing', 'logistics', 'trade_finance', 'inventory'):
            pass
        R.observe('summary_categories',
                  {k: (v or {}).get('status') for k, v in ((s.get('categories') or {}).items()
                                                           if isinstance(s, dict) else [])})
        R.observe('summary_optional_flags',
                  {k: (v or {}).get('optional') for k, v in ((s.get('categories') or {}).items()
                                                             if isinstance(s, dict) else [])})
        R.step('the supply-chain sections are marked optional on the Summary (W-CE-13)',
               'pass' if all((((s.get('categories') or {}).get(k) or {}).get('optional'))
                             for k in ('sourcing', 'logistics', 'trade_finance', 'inventory'))
               else 'fail',
               json.dumps(R.record['observed'].get('summary_optional_flags'), ensure_ascii=False)[:250])
        R.screen(page, 'x-t%d-r%d-95-summary' % (TEAM_IX, ROUND))
        lock = page.locator('button', has_text=T('summary_page.lock_submit_round', round=ROUND))
        R.observe('lock_button_enabled', lock.count() and lock.first.is_enabled())
        if lock.count() and lock.first.is_enabled():
            lock.first.click(); page.wait_for_timeout(1200)
            R.observe('lock_modal', modal_text(page))
            page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary').last.click()
            page.wait_for_timeout(5000)
            R.observe('lock_modal_after', modal_text(page))
            st = api(page, 'GET', DEC)['body']
            R.step('round %d locked from the screen' % ROUND,
                   'pass' if st.get('status') == 'locked' else 'fail',
                   'status=%s' % st.get('status'))
            refused = [x for x in R.record['refused'] if x['url'].endswith('/lock/')]
            R.observe('lock_refusals', refused)
            R.step('the page never offers a lock the server then refuses (W-CE-25)',
                   'pass' if st.get('status') == 'locked' or not refused else 'fail',
                   json.dumps([x['body'][:200] for x in refused], ensure_ascii=False)[:300])
            R.screen(page, 'x-t%d-r%d-97-locked' % (TEAM_IX, ROUND))
        else:
            R.step('lock offered after the required decisions', 'fail',
                   'blockers=%s' % json.dumps(R.record['observed'].get('summary'), ensure_ascii=False)[:300])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
