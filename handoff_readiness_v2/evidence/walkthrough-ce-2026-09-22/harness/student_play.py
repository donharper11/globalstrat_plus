"""A student team plays one round through every decision screen.

student_play.py <lang> <team-index 1..8> <round> [profile]

profile 'probe' (team 1): the edge cases too -- an over-allocated budget, an
out-of-band price kept, a blank price on a product with no history, an
over-limit memo, a refused analyst question, an autosave refused while an
operator holds the game lock. profile 'plain': ordinary decisions only.

Labels are resolved from the product's own locale catalogues (T(key)), so the
same driver runs in English and in Simplified Chinese.
"""
import json
import pathlib
import subprocess
import sys

from walk import (BASE, SCRATCH, Recorder, api, modal_text, pick_select,
                  set_number, sign_in, sync_playwright, toast, visible_text)

LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
PROFILE = sys.argv[4] if len(sys.argv) > 4 else 'plain'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]['username']      # second member: the tour used the first
SID = members[min(1, len(members) - 1)].get('student_id') or STUDENT
R = Recorder('student-play-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('student', STUDENT); R.observe('team', team.get('team_name')); R.observe('profile', PROFILE)
WT = SCRATCH.parents[3]
LOCALE = json.loads((WT / 'frontend/globalstrat-frontend/src/locales' / ('%s.json' % LANG)).read_text())
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
P = 'p%d' % TEAM_IX


def T(key, **kw):
    cur = LOCALE
    for part in key.split('.'):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return key
    for k, v in kw.items():
        cur = cur.replace('{{%s}}' % k, str(v))
    return cur


def goto(page, path, wait=4500):
    page.goto(BASE + '/games/%d/teams/%d/%s' % (GID, TID, path), wait_until='domcontentloaded')
    page.wait_for_timeout(wait)


def tab(page, label):
    t = page.locator('.ant-tabs-tab', has_text=label)
    if t.count():
        t.first.click(); page.wait_for_timeout(1500); return True
    return False


def pane(page):
    return page.locator('.ant-tabs-tabpane-active').last


def draft(page):
    return api(page, 'GET', DEC)['body']


def panel(page, title):
    return page.locator('.panel-card', has_text=title).first


def money_input(page, label):
    """A MoneyTextInput / InputNumber found by its label text within the active pane."""
    return page.locator('input').filter(has=page.locator('xpath=..')).first


# ------------------------------------------------------------------------
def finance(page):
    goto(page, 'decisions/finance')
    R.screen(page, '%s-r%d-10-finance-budget' % (P, ROUND))
    ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/finance/' % (GID, TID))['body']
    R.observe('finance_context', {k: ctx.get(k) for k in ('operating_budget', 'operating_budget_available', 'cash_on_hand', 'total_debt', 'budget_source')} if isinstance(ctx, dict) else ctx)
    # The three budget boxes are plain Inputs (MoneyTextInput) inside the BUDGET ALLOCATION panel.
    boxes = pane(page).locator('input.ant-input')
    n = boxes.count()
    R.observe('finance_budget_inputs', n)
    if n < 3:
        R.step('finance: three budget inputs offered', 'fail', '%d inputs' % n); return
    values = [3000000, 2500000, 1500000] if PROFILE == 'probe' else [2500000, 2500000, 1500000]
    for i, v in enumerate(values):
        boxes.nth(i).click(); page.keyboard.press('Control+a'); page.keyboard.type(str(v)); page.keyboard.press('Tab')
        page.wait_for_timeout(1500)
    page.wait_for_timeout(2500)
    d = draft(page)
    ba = d.get('budget_allocation') or {}
    R.observe('budget_saved', ba)
    R.step('finance: budget allocation saved as entered', 'pass' if [int(float(ba.get(k) or 0)) for k in ('rd_budget', 'marketing_budget', 'strategy_budget')] == values else 'fail', json.dumps(ba)[:200])
    R.screen(page, '%s-r%d-11-finance-budget-saved' % (P, ROUND))
    if PROFILE == 'probe':
        boxes.nth(0).click(); page.keyboard.press('Control+a'); page.keyboard.type('9000000'); page.keyboard.press('Tab')
        page.wait_for_timeout(3000)
        txt = visible_text(page)
        over = ('exceeds' in txt) or ('超出' in txt) or ('超过' in txt)
        R.observe('over_allocation_text', [l for l in txt.splitlines() if 'exceed' in l or '超' in l][:3])
        R.screen(page, '%s-r%d-12-finance-over-allocated' % (P, ROUND), 'R&D set to 9,000,000 against a 7.5M operating budget')
        d2 = draft(page); ba2 = d2.get('budget_allocation') or {}
        R.step('finance: over-allocation is flagged on screen', 'pass' if over else 'fail', 'stored rd_budget=%s' % ba2.get('rd_budget'))
        R.observe('over_allocation_stored', ba2)
        boxes.nth(0).click(); page.keyboard.press('Control+a'); page.keyboard.type(str(values[0])); page.keyboard.press('Tab')
        page.wait_for_timeout(3000)
    # Capital tab
    tab(page, T('finance.capital_management'))
    page.wait_for_timeout(1500)
    nums = pane(page).locator('.ant-input-number-input')
    R.observe('capital_inputs', nums.count())
    if nums.count() >= 4:
        if PROFILE == 'probe':
            set_number(page, nums.nth(0), 5000000)      # typed key by key, as a person does
        else:
            nums.nth(0).click(); nums.nth(0).fill('5000000'); page.keyboard.press('Tab')
        page.wait_for_timeout(1500)
        set_number(page, nums.nth(3), 0.5); page.wait_for_timeout(2500)
        fin = (draft(page).get('financing') or {})
        R.observe('financing_saved', fin)
        R.step('finance: loan and dividend saved as entered', 'pass' if int(float(fin.get('new_debt') or 0)) == 5000000 and abs(float(fin.get('dividend_per_share') or 0) - 0.5) < 1e-6 else 'fail', json.dumps(fin)[:200])
    else:
        R.step('finance: capital inputs offered', 'fail', '%d inputs' % nums.count())
    R.screen(page, '%s-r%d-13-finance-capital' % (P, ROUND))
    # Tax tab
    tab(page, T('finance.tax_structure'))
    page.wait_for_timeout(1500)
    R.screen(page, '%s-r%d-14-finance-tax' % (P, ROUND))
    before = api(page, 'GET', '/api/games/%d/teams/%d/context/tax-structure/' % (GID, TID))['body']
    cur = (before or {}).get('current') or {}
    cards = pane(page).locator('.ant-card')
    R.observe('tax_cards', cards.count())
    target = None
    for i in range(cards.count()):
        txt = cards.nth(i).text_content() or ''
        if cards.nth(i).locator('.ant-tag', has_text=T('finance.current')).count():
            continue                      # the structure already in force
        names = [s['name'] for s in (before or {}).get('structures') or [] if s.get('name') and s['name'] != cur.get('name')]
        if any(nm in txt for nm in names) and cards.nth(i).locator('.ant-card').count() == 0:
            target = cards.nth(i); break
    if target is not None:
        target.click(); page.wait_for_timeout(3500)
        after = api(page, 'GET', '/api/games/%d/teams/%d/context/tax-structure/' % (GID, TID))['body']
        R.observe('tax_after', (after or {}).get('current'))
        R.step('finance: tax structure switched from the screen', 'pass' if ((after or {}).get('current') or {}).get('code') != cur.get('code') else 'fail', '%s -> %s' % (cur.get('code'), ((after or {}).get('current') or {}).get('code')))
        R.screen(page, '%s-r%d-15-finance-tax-switched' % (P, ROUND))
    else:
        R.step('finance: another tax structure offered', 'fail', 'no selectable structure card')


def rd(page):
    goto(page, 'decisions/rd')
    R.screen(page, '%s-r%d-20-rd' % (P, ROUND))
    inv = page.locator('button', has_text='Invest next level')
    R.observe('rd_upgrade_buttons', inv.count())
    if inv.count():
        enabled = [i for i in range(inv.count()) if inv.nth(i).is_enabled()]
        if enabled:
            inv.nth(enabled[0]).click()
            R.observe('rd_toast', toast(page, 15)); page.wait_for_timeout(2500)
            R.screen(page, '%s-r%d-21a-rd-upgrade-clicked' % (P, ROUND), 'what the student sees after Invest next level')
            d = draft(page); items = d.get('rd_investments') or []
            R.observe('rd_saved', items)
            R.step('rd: feature upgrade saved', 'pass' if items else 'fail', json.dumps(items)[:200])
        else:
            R.step('rd: an affordable upgrade is offered', 'fail', 'all upgrade buttons disabled')
    R.screen(page, '%s-r%d-21-rd-after-upgrade' % (P, ROUND))
    # Create platform modal: opened, filled, attempted.
    cp = page.locator('button', has_text=T('rd.create_platform'))
    if cp.count() and cp.first.is_enabled():
        cp.first.click(); page.wait_for_timeout(1500)
        page.locator('.ant-modal-content input.ant-input').first.fill('Aurora Gen2 Core')
        radios = page.locator('.ant-modal-content .ant-radio-wrapper')
        if radios.count():
            radios.first.click(); page.wait_for_timeout(600)
        sl = page.locator('.ant-modal-content .ant-slider')
        if sl.count():
            sl.first.click(); page.wait_for_timeout(400)
        R.observe('platform_modal', (modal_text(page) or '')[:700])
        R.screen(page, '%s-r%d-22-rd-create-platform-modal' % (P, ROUND))
        create = page.locator('.ant-modal-content button', has_text=T('rd.create_platform_btn'))
        can = create.count() and create.first.is_enabled()
        R.observe('platform_create_enabled', bool(can))
        if can:
            create.first.click(); page.wait_for_timeout(4000)
            R.observe('platform_toast', toast(page, 10))
            pd = draft(page).get('platform_developments') or []
            R.step('rd: platform creation saved', 'pass' if pd else 'fail', json.dumps(pd)[:200])
        else:
            R.step('rd: platform creation blocked (reason shown in modal)', 'observed', (modal_text(page) or '')[-250:])
            page.keyboard.press('Escape'); page.wait_for_timeout(800)
        R.screen(page, '%s-r%d-23-rd-after-platform' % (P, ROUND))


def products(page):
    goto(page, 'decisions/products')
    R.screen(page, '%s-r%d-30-products' % (P, ROUND))
    btn = page.locator('button', has_text=T('products_page.create_new_product'))
    if draft(page).get('product_creates'):
        R.step('products: new product already in this draft (re-run)', 'observed'); R.screen(page, '%s-r%d-32-products-after-create' % (P, ROUND)); return
    if btn.count() and btn.first.is_enabled():
        btn.first.click(); page.wait_for_timeout(1500)
        m = page.locator('.ant-modal-content').last
        m.locator('input.ant-input').first.fill('Nova %s R%d' % (team.get('team_name', '').split()[0], ROUND))
        pick_select(page, m.locator('.ant-select').nth(0))
        m.locator('.ant-radio-button-wrapper', has_text=T('products_page.pos_mainstream')).first.click()
        pick_select(page, m.locator('.ant-select').nth(1))
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
        R.screen(page, '%s-r%d-31-products-create-modal' % (P, ROUND))
        page.locator('.ant-modal-footer .ant-btn-primary').last.click(); page.wait_for_timeout(4000)
        R.observe('product_modal_after', modal_text(page))
        pc = draft(page).get('product_creates') or []
        R.observe('product_creates', pc)
        R.step('products: new product saved from the modal', 'pass' if pc else 'fail', json.dumps(pc)[:200] + ' modal=%r' % (modal_text(page) or '')[:150])
        if modal_text(page):
            page.keyboard.press('Escape'); page.wait_for_timeout(600)
    else:
        R.step('products: create control offered', 'fail')
    R.screen(page, '%s-r%d-32-products-after-create' % (P, ROUND))


def products_retire(page):
    goto(page, 'decisions/products')
    if draft(page).get('product_retires'):
        R.step('products: retirement already in this draft (re-run)', 'observed'); return
    rows = page.locator('table tbody tr.ant-table-row')
    R.observe('product_rows', rows.count())
    if rows.count() < 2:
        R.step('products: a second product exists to retire', 'fail', '%d rows' % rows.count()); return
    rows.nth(rows.count() - 1).click(); page.wait_for_timeout(1500)
    R.observe('edit_modal', (modal_text(page) or '')[:400])
    R.screen(page, '%s-r%d-33-products-edit-modal' % (P, ROUND))
    b = page.locator('.ant-modal-content button', has_text=T('products_page.retire_end_of_round'))
    if b.count():
        b.first.click(); page.wait_for_timeout(3500)
        pr = draft(page).get('product_retires') or []
        R.observe('product_retires', pr)
        R.step('products: retire at end of round saved', 'pass' if pr else 'fail', json.dumps(pr)[:200])
    else:
        R.step('products: retire control offered in the edit modal', 'fail')
    if modal_text(page):
        page.keyboard.press('Escape'); page.wait_for_timeout(600)
    R.screen(page, '%s-r%d-34-products-after-retire' % (P, ROUND))


def marketing(page):
    goto(page, 'decisions/marketing', 5000)
    R.screen(page, '%s-r%d-40-marketing' % (P, ROUND))
    ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/marketing/' % (GID, TID))['body']
    bands = ctx.get('price_bands') or {}
    pms = ctx.get('product_markets') or []
    R.observe('price_bands', bands)
    R.observe('product_markets', pms[:6])
    if not pms:
        R.step('marketing: product-market rows offered', 'fail'); return
    inner = page.locator('.ant-tabs-tabpane-active .ant-tabs-tab')   # product tabs live inside the market pane
    R.observe('inner_product_tabs', inner.count())

    def fill_row(price, volume=5000, promo=200000):
        p = pane(page)
        nums = p.locator('.ant-input-number-input')
        set_number(page, nums.nth(0), price); page.wait_for_timeout(400)
        set_number(page, nums.nth(1), volume); page.wait_for_timeout(400)
        sel = p.locator('.ant-select').first
        if sel.count():
            pick_select(page, sel)
        tags = p.locator('.ant-tag[style*="cursor"]')
        if tags.count() and '\u2713' not in (tags.first.text_content() or ''):
            tags.first.click(); page.wait_for_timeout(300)     # a second click would deselect it
        cb = p.locator('.ant-checkbox-input')
        if cb.count() and not cb.first.is_checked():
            cb.first.click(); page.wait_for_timeout(500)
        nums = p.locator('.ant-input-number-input')
        if nums.count() >= 4:
            set_number(page, nums.nth(3), promo)
        page.wait_for_timeout(3500)

    first = pms[0]
    def pm_key(pm):
        mk = (pm.get('markets') or [{}])[0].get('market_id')
        return '%s_%s' % (pm.get('product_id'), mk)
    key = pm_key(first)
    band = bands.get(key) or {}
    in_band = int(band.get('anchor') or 300)
    if inner.count() > 1:
        inner.first.click(); page.wait_for_timeout(800)
    fill_row(in_band)
    row = next((r for r in (draft(page).get('marketing_decisions') or []) if r.get('team_product') == first.get('product_id')), None)
    R.observe('marketing_row_in_band', row)
    R.step('marketing: in-band price, volume, promotion saved', 'pass' if row and int(float(row.get('retail_price') or 0)) == in_band and int(row.get('production_volume') or 0) == 5000 else 'fail', json.dumps(row)[:300])
    R.screen(page, '%s-r%d-41-marketing-in-band' % (P, ROUND))
    if PROFILE == 'probe' and band:
        oob = int(float(band['max']) * 3)
        set_number(page, pane(page).locator('.ant-input-number-input').nth(0), oob); page.wait_for_timeout(1200)
        txt = pane(page).inner_text()
        R.observe('oob_text', [l for l in txt.splitlines() if 'range' in l.lower() or '区间' in l or '范围' in l][:4])
        R.screen(page, '%s-r%d-42-marketing-out-of-band' % (P, ROUND), 'price %d against band %s-%s' % (oob, band.get('min'), band.get('max')))
        page.wait_for_timeout(3500)
        row = next((r for r in (draft(page).get('marketing_decisions') or []) if r.get('team_product') == first.get('product_id')), None)
        R.observe('marketing_row_oob', row)
        alerted = (T('marketing.price_out_of_band')[:20] in txt) or (T('marketing.price_band_range', min='', max='')[:8] in txt)
        R.step('marketing: out-of-band price is flagged and kept', 'pass' if alerted and row and int(float(row.get('retail_price') or 0)) == oob else 'fail', 'stored=%s flagged=%s' % (row and row.get('retail_price'), alerted))
        R.observe('oob_price', oob)
        # Blank price on the second product-market, if any.
        if inner.count() > 1:
            inner.nth(1).click(); page.wait_for_timeout(1000)
            second = pms[1] if len(pms) > 1 else None
            fill_row(100, volume=3000, promo=50000)
            set_number(page, pane(page).locator('.ant-input-number-input').nth(0), None); page.wait_for_timeout(1200)
            txt2 = pane(page).inner_text()
            R.observe('blank_text', [l for l in txt2.splitlines() if 'price' in l.lower() or '价格' in l][:5])
            R.screen(page, '%s-r%d-43-marketing-blank-price' % (P, ROUND))
            page.wait_for_timeout(3500)
            row2 = next((r for r in (draft(page).get('marketing_decisions') or []) if second and r.get('team_product') == second.get('product_id')), None)
            R.observe('marketing_row_blank', row2)
            R.step('marketing: blank price is explained and stored as blank', 'pass' if row2 is not None and row2.get('retail_price') is None and (T('marketing.price_blank', floor='')[:12] in txt2 or T('marketing.price_blank_not_for_sale')[:12] in txt2) else 'fail', json.dumps(row2)[:200])
    else:
        # Every other product-market gets a sane price too.
        for i in range(1, min(inner.count(), len(pms))):
            inner.nth(i).click(); page.wait_for_timeout(1000)
            pm = pms[i]; b = bands.get(pm_key(pm)) or {}
            fill_row(int(b.get('anchor') or 250), volume=4000, promo=100000)
    R.screen(page, '%s-r%d-44-marketing-final' % (P, ROUND))


def market_strategy(page):
    goto(page, 'decisions/market-strategy', 5000)
    R.screen(page, '%s-r%d-50-market-strategy' % (P, ROUND))
    tabs = page.locator('.ant-tabs-tab')
    R.observe('market_tabs', [tabs.nth(i).text_content() for i in range(tabs.count())])
    # Enter the first market that is not entered.
    entered_label = T('market_strategy.not_entered')
    d0 = draft(page)
    for i in range(tabs.count() if not d0.get('market_entries') else 0):
        if entered_label in (tabs.nth(i).text_content() or ''):
            tabs.nth(i).click(); page.wait_for_timeout(1500)
            cards = pane(page).locator('.ant-card.ant-card-hoverable')
            R.observe('entry_mode_cards', cards.count())
            if cards.count():
                cards.first.click(); page.wait_for_timeout(3500)
                me = draft(page).get('market_entries') or []
                R.observe('market_entries', me)
                R.step('market strategy: market entry saved', 'pass' if me else 'fail', json.dumps(me)[:200])
                R.screen(page, '%s-r%d-51-market-entry' % (P, ROUND))
            break
    # Home market: build plant, partnership, compliance investment.
    tabs.first.click(); page.wait_for_timeout(1500)
    bp = pane(page).locator('button', has_text=T('market_strategy.build_plant'))
    if d0.get('plant_decisions'):
        R.step('market strategy: plant already in this draft (re-run)', 'observed')
    elif bp.count() and bp.first.is_enabled():
        bp.first.click(); page.wait_for_timeout(3500)
        pl = draft(page).get('plant_decisions') or []
        R.step('market strategy: plant build saved', 'pass' if pl else 'fail', json.dumps(pl)[:200])
    else:
        R.step('market strategy: build-plant control offered on the home market', 'observed', 'not offered (plant may already exist)')
    plus = pane(page).locator('button', has_text='+ ')
    if d0.get('partnerships'):
        R.step('market strategy: partnership already in this draft (re-run)', 'observed')
    elif plus.count():
        plus.first.click(); page.wait_for_timeout(3500)
        pt = draft(page).get('partnerships') or []
        R.step('market strategy: partnership saved', 'pass' if pt else 'fail', json.dumps(pt)[:200])
    else:
        R.step('market strategy: partnership options offered', 'fail', 'no + option button')
    R.screen(page, '%s-r%d-52-market-home' % (P, ROUND))
    # Compliance investment lives on a FOREIGN entered market.
    found = False
    for i in range(1, tabs.count()):
        tabs.nth(i).click(); page.wait_for_timeout(1500)
        ci = pane(page).locator('.ant-card', has_text=T('market_strategy.compliance_investment'))
        if ci.count():
            box = ci.first.locator('.ant-input-number-input').first
            if box.count():
                set_number(page, box, 250000); page.wait_for_timeout(3500)
                cinv = draft(page).get('compliance_investments') or []
                R.observe('compliance_investments', cinv)
                R.step('market strategy: compliance investment saved', 'pass' if cinv and any(int(float(c.get('investment_amount') or 0)) == 250000 for c in cinv) else 'fail', json.dumps(cinv)[:200])
                R.screen(page, '%s-r%d-53-compliance-investment' % (P, ROUND))
                found = True
                break
    if not found:
        R.step('market strategy: compliance investment control reachable', 'observed', 'no foreign market is entered yet, so the control is not offered this round')


def corporate(page):
    goto(page, 'decisions/corporate-strategy', 5000)
    R.screen(page, '%s-r%d-60-corporate-talent' % (P, ROUND))
    nums = pane(page).locator('.ant-input-number-input')
    R.observe('talent_inputs', nums.count())
    if nums.count() >= 2:
        set_number(page, nums.nth(0), 60); page.wait_for_timeout(800)
        set_number(page, nums.nth(1), 100000); page.wait_for_timeout(3500)
        tal = (api(page, 'GET', '/api/games/%d/teams/%d/context/talent/' % (GID, TID))['body'] or {}).get('draft') or {}
        R.observe('talent_saved', tal)
        R.step('corporate: talent headcount and training saved', 'pass' if int(tal.get('rd_headcount') or 0) == 60 else 'fail', json.dumps(tal)[:200])
    coll = pane(page).locator('.ant-collapse-header', has_text=T('corporate_strategy.staff_allocation'))
    if coll.count():
        coll.first.click(); page.wait_for_timeout(1200)
        alloc = pane(page).locator('.ant-collapse-content-active .ant-input-number-input')
        R.observe('allocation_inputs', alloc.count())
        if alloc.count() >= 2:
            set_number(page, alloc.nth(1), 5); page.wait_for_timeout(3500)
            ta = draft(page).get('talent_allocations') or []
            R.observe('talent_allocations', ta)
            R.step('corporate: talent allocation saved', 'pass' if ta else 'fail', json.dumps(ta)[:200])
        R.screen(page, '%s-r%d-61-corporate-allocation' % (P, ROUND))
    else:
        R.step('corporate: staff allocation reachable', 'fail', 'collapse header not found')
    # M&A
    tab(page, T('corporate_strategy.ma')); page.wait_for_timeout(1500)
    R.screen(page, '%s-r%d-62-corporate-ma' % (P, ROUND))
    acq = pane(page).locator('button', has_text=T('corporate_strategy.acquire'))
    if acq.count():
        ok = [i for i in range(acq.count()) if acq.nth(i).is_enabled()]
        if ok:
            acq.nth(ok[0]).click(); page.wait_for_timeout(3500)
            a = draft(page).get('acquisitions') or []
            R.step('corporate: acquisition queued', 'pass' if a else 'fail', json.dumps(a)[:200])
        else:
            R.step('corporate: an acquisition is affordable', 'observed', 'all acquire buttons disabled')
    else:
        R.step('corporate: acquisition targets offered', 'fail')
    # ESG
    tab(page, T('corporate_strategy.esg')); page.wait_for_timeout(1500)
    nums = pane(page).locator('.ant-input-number-input')
    if nums.count() >= 2:
        set_number(page, nums.nth(0), 500000); page.wait_for_timeout(600)
        set_number(page, nums.nth(1), 250000); page.wait_for_timeout(800)
    cbs = pane(page).locator('.ant-checkbox-input')
    if cbs.count() and not cbs.first.is_checked():
        cbs.first.click(); page.wait_for_timeout(3500)
    esg = draft(page).get('esg') or {}
    R.observe('esg_saved', esg)
    R.step('corporate: ESG investment and a commitment saved', 'pass' if int(float(esg.get('environmental_investment') or 0)) == 500000 and (esg.get('governance_commitments') or []) else 'fail', json.dumps(esg)[:250])
    R.screen(page, '%s-r%d-63-corporate-esg' % (P, ROUND))
    # Org structure
    tab(page, T('corporate_strategy.organization')); page.wait_for_timeout(1500)
    R.screen(page, '%s-r%d-64-corporate-org' % (P, ROUND))
    sw = pane(page).locator('button', has_text=T('corporate_strategy.switch'))
    oc0 = api(page, 'GET', '/api/games/%d/teams/%d/context/org-structure/' % (GID, TID))['body']
    if isinstance(oc0, dict) and oc0.get('transitioning'):
        R.step('corporate: org switch already pending (re-run)', 'observed')
    elif sw.count():
        ok = [i for i in range(sw.count()) if sw.nth(i).is_enabled()]
        if ok:
            sw.nth(ok[0]).click(); page.wait_for_timeout(1200)
            R.observe('org_modal', (modal_text(page) or '')[:500])
            R.screen(page, '%s-r%d-65-corporate-org-modal' % (P, ROUND))
            page.locator('.ant-modal-footer button').last.click(); page.wait_for_timeout(4000)
            R.observe('org_after_modal', modal_text(page))
            oc = api(page, 'GET', '/api/games/%d/teams/%d/context/org-structure/' % (GID, TID))['body']
            R.observe('org_context_after', {k: oc.get(k) for k in ('current_structure', 'transitioning', 'transition_to', 'pending_structure')} if isinstance(oc, dict) else oc)
            R.step('corporate: org structure switch accepted', 'pass' if isinstance(oc, dict) and (oc.get('transitioning') or oc.get('pending_structure') or oc.get('transition_to')) else 'observed', json.dumps(R.record['observed']['org_context_after'])[:200])
            if modal_text(page):
                page.keyboard.press('Escape'); page.wait_for_timeout(600)
        else:
            R.step('corporate: an org switch is affordable', 'observed', 'all switch buttons disabled')
    R.screen(page, '%s-r%d-66-corporate-org-after' % (P, ROUND))


def communications(page):
    goto(page, 'decisions/communications', 5000)
    R.screen(page, '%s-r%d-70-communications' % (P, ROUND))
    start = page.locator('button', has_text=T('communications_page.start_writing'))
    if start.count() == 0:
        start = page.locator('button', has_text=T('communications_page.continue_editing'))
    if start.count() == 0:
        R.step('communications: an assignment is offered', 'observed', 'no assignment this round'); return
    start.first.click(); page.wait_for_timeout(1500)
    ta = page.locator('textarea').first
    limit_txt = visible_text(page)
    import re
    m = re.search(r'(\d+)\s*(words|字|词)', limit_txt) or re.search(r'(words|字|词)[^\d]{0,6}(\d+)', limit_txt)
    limit = int(m.group(1) if m and m.group(1).isdigit() else (m.group(2) if m else 120))
    R.observe('word_limit_seen', limit)
    over = ' '.join(['Aurora'] * (limit + 15))
    ta.fill(over); page.wait_for_timeout(2500)
    txt = visible_text(page)
    over_flag = (T('communications_page.over_limit') in txt)
    submit = page.locator('button', has_text=T('communications_page.submit_for_evaluation'))
    R.observe('over_limit_line', [l for l in txt.splitlines() if T('communications_page.word_count') in l][:2])
    R.step('communications: over-limit memo is flagged and cannot be submitted', 'pass' if over_flag and submit.count() and not submit.first.is_enabled() else 'fail', 'flag=%s submit_enabled=%s' % (over_flag, submit.count() and submit.first.is_enabled()))
    R.screen(page, '%s-r%d-71-communications-over-limit' % (P, ROUND))
    memo = ('We are Aurora Devices. This round we invest in our platform, enter a new market carefully, '
            'and keep prices inside the range our customers expect. ' * 3)[:600]
    words = memo.split()[:max(20, limit - 5)]
    ta.fill(' '.join(words)); page.wait_for_timeout(2500)
    dialogs = []
    page.once('dialog', lambda d: (dialogs.append(d.message), d.accept()))
    submit = page.locator('button', has_text=T('communications_page.submit_for_evaluation'))
    if submit.count() and submit.first.is_enabled():
        submit.first.click(); page.wait_for_timeout(15000)
        R.observe('comm_dialog', dialogs)
        R.observe('comm_after_submit', visible_text(page)[:600])
        subs = api(page, 'GET', '/api/games/%d/teams/%d/communications/history/' % (GID, TID))['body']
        R.observe('comm_history', json.dumps(subs)[:500])
        R.step('communications: memo submitted and an evaluation shown', 'pass' if not dialogs and (T('communications_page.submitted_this_round') in visible_text(page)) else 'fail', 'dialog=%s' % dialogs)
    else:
        R.step('communications: submit enabled for an in-limit memo', 'fail')
    R.screen(page, '%s-r%d-72-communications-submitted' % (P, ROUND))


def research(page):
    goto(page, 'research', 5000)
    R.screen(page, '%s-r%d-80-research-segments' % (P, ROUND))
    buy = page.locator('button', has_text=T('market_research.buy_report'))
    if buy.count():
        R.observe('buy_label', buy.first.text_content())
        buy.first.click(); page.wait_for_timeout(4000)
        R.observe('buy_toast', toast(page, 10))
        R.step('research: report bought and delivered', 'pass' if page.locator('button', has_text=T('market_research.buy_report')).count() == 0 else 'fail', R.record['observed'].get('buy_toast'))
        R.screen(page, '%s-r%d-81-research-bought' % (P, ROUND))
    else:
        R.step('research: paywall offered on the segments report', 'observed', 'report already available')
    tab(page, T('market_research.ask_analyst')); page.wait_for_timeout(2000)
    R.screen(page, '%s-r%d-82-research-analyst' % (P, ROUND))
    ta = page.locator('textarea').first
    ask = page.locator('button', has_text=T('market_research.ask'))
    if ta.count() and ask.count():
        ta.fill('Which segment in our home market is growing fastest and what price do they expect?')
        page.wait_for_timeout(500)
        ask.first.click(); page.wait_for_timeout(12000)
        refusal = page.locator('[data-testid="analyst-refusal"]')
        R.observe('analyst_refusal', refusal.first.text_content() if refusal.count() else None)
        R.observe('analyst_toast', toast(page, 5))
        q = api(page, 'GET', '/api/games/%d/teams/%d/research/queries/' % (GID, TID))['body']
        R.observe('analyst_queries', json.dumps(q)[:600])
        R.step('research: analyst answers or refuses visibly (no model behind this stack)', 'pass' if refusal.count() or (q.get('queries') if isinstance(q, dict) else None) else 'fail', R.record['observed'].get('analyst_refusal') or 'answered')
        R.screen(page, '%s-r%d-83-research-analyst-asked' % (P, ROUND))
        if PROFILE == 'probe':
            # Ask until the quota refuses.
            for i in range(4):
                ta = page.locator('textarea').first
                if ta.count() == 0 or not ta.is_enabled():
                    break
                ta.fill('Follow-up %d: which channel reaches premium buyers?' % (i + 1)); page.wait_for_timeout(400)
                ask = page.locator('button', has_text=T('market_research.ask'))
                if ask.count() == 0 or not ask.first.is_enabled():
                    break
                ask.first.click(); page.wait_for_timeout(8000)
            R.observe('analyst_quota_toast', toast(page, 5))
            R.observe('analyst_quota_line', [l for l in visible_text(page).splitlines() if T('market_research.queries_this_round') in l][:2])
            R.screen(page, '%s-r%d-84-research-analyst-quota' % (P, ROUND))


def autosave_refused(page):
    """An operator holds the lifecycle lock while the student edits finance."""
    goto(page, 'decisions/finance', 4500)
    holder = subprocess.Popen([sys.executable, str(SCRATCH / 'hold_lock.py'), str(GID), '8'], cwd=str(SCRATCH), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    held = holder.stdout.readline().strip()
    R.observe('lock_holder', held)
    boxes = pane(page).locator('input.ant-input')
    boxes.nth(2).click(); page.keyboard.press('Control+a'); page.keyboard.type('1750000'); page.keyboard.press('Tab')
    page.wait_for_timeout(5000)
    txt = visible_text(page)
    shown = T('decision_save.not_saved_title') in txt
    R.observe('autosave_refusal_alert', [l for l in txt.splitlines() if T('decision_save.not_saved_title') in l or T('decision_save.retry_now') in l][:3])
    R.screen(page, '%s-r%d-90-autosave-refused' % (P, ROUND), 'operator lock held; the edit must be shown as not saved')
    R.step('autosave: refusal shown with a retry while an operator holds the game', 'pass' if shown else 'fail', 'refused 409s so far: %d' % len([x for x in R.record['refused'] if x['status'] == 409]))
    holder.wait(timeout=60)
    page.wait_for_timeout(14000)
    txt2 = visible_text(page)
    ba = draft(page).get('budget_allocation') or {}
    R.step('autosave: the edit is retried and lands after the operator is done', 'pass' if T('decision_save.not_saved_title') not in txt2 and int(float(ba.get('strategy_budget') or 0)) == 1750000 else 'fail', 'strategy_budget=%s notice_still_shown=%s' % (ba.get('strategy_budget'), T('decision_save.not_saved_title') in txt2))
    R.screen(page, '%s-r%d-91-autosave-retried' % (P, ROUND))


def summary_lock(page):
    goto(page, 'decisions/summary', 5000)
    R.screen(page, '%s-r%d-95-summary' % (P, ROUND))
    s = api(page, 'GET', DEC + 'summary/')['body']
    R.observe('summary', {k: s.get(k) for k in ('can_lock', 'lock_blockers')} if isinstance(s, dict) else s)
    R.observe('summary_categories', {k: (v or {}).get('status') for k, v in ((s.get('categories') or {}).items() if isinstance(s, dict) else [])})
    notes = page.locator('textarea').first
    if notes.count() and notes.is_enabled():
        notes.fill('Round %d: platform first, one new market, prices inside the band.' % ROUND)
    lock = page.locator('button', has_text=T('summary_page.lock_submit_round', round=ROUND))
    R.observe('lock_button_enabled', lock.count() and lock.first.is_enabled())
    if lock.count() and lock.first.is_enabled():
        lock.first.click(); page.wait_for_timeout(1200)
        R.observe('lock_modal', modal_text(page))
        R.screen(page, '%s-r%d-96-lock-confirm' % (P, ROUND))
        page.locator('.ant-modal-footer .ant-btn-primary').last.click(); page.wait_for_timeout(5000)
        R.observe('lock_modal_after', modal_text(page))
        st = api(page, 'GET', DEC)['body']
        R.step('summary: decisions locked from the screen', 'pass' if st.get('status') == 'locked' else 'fail', 'status=%s modal_after=%r' % (st.get('status'), (modal_text(page) or '')[:200]))
        R.screen(page, '%s-r%d-97-locked' % (P, ROUND))
    else:
        R.step('summary: lock offered after the required decisions', 'fail', 'blockers=%s categories=%s' % (R.record['observed'].get('summary'), R.record['observed'].get('summary_categories')))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT, LANG, password=SID)
        R.step('student %s signs in' % STUDENT, 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        page.wait_for_timeout(3000)
        for _ in range(6):
            if not modal_text(page):
                break
            b = page.locator('.ant-modal-content button.ant-btn-primary')
            if b.count():
                b.last.click(); page.wait_for_timeout(1200)
            else:
                page.keyboard.press('Escape'); page.wait_for_timeout(600)
        st = draft(page)
        if st.get('status') == 'locked':
            R.step('round %d already locked for this team' % ROUND, 'observed'); browser.close(); return R.finish()
        finance(page)
        rd(page)
        products(page)
        marketing(page)
        market_strategy(page)
        corporate(page)
        communications(page)
        research(page)
        products_retire(page)
        if PROFILE == 'probe':
            autosave_refused(page)
        summary_lock(page)
        R.observe('final_draft', draft(page))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
