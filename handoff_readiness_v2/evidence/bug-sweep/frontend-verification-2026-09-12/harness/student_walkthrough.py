"""CRV2-13 student pricing walkthrough, in one language, through real Chromium.

Covers items 1, 2, 3 and the pricing-screen half of 5.

Two things this script learned the hard way and now encodes:

* The pricing screen's own default row (no production source market, no
  campaign focus) is REFUSED by the API with 400, and `autoSave` swallows the
  error. So every save is primed with the two fields the serializer demands --
  which a student can do -- and the refusals are counted separately as their
  own finding rather than being allowed to fail the price checks.
* Every PATCH body is captured, because item 3 is a claim about what reaches
  the server. An alert on screen says the student was told something, not that
  the blank was submitted.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-a0ae8bfea94e98414/handoff_readiness_v2/evidence/bug-sweep'
    '/frontend-verification-2026-09-12')
SHOTS = EVIDENCE / 'screenshots'

LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
TEAM = fixture['team_a_id']
ROUND = fixture['current_round']
STUDENT = fixture['students'][0]['username']
PASSWORD = fixture['password']

record = {'language': LANG, 'base': BASE, 'game': GAME, 'team': TEAM,
          'steps': [], 'console': [], 'network': [], 'patches': [],
          'save_responses': [], 'screenshots': []}


def step(name, outcome, detail=''):
    record['steps'].append({'name': name, 'outcome': outcome,
                            'detail': str(detail)[:700]})
    print(f'  {outcome.upper():<12} {name}'
          f'{" — " + str(detail)[:200] if detail else ""}', flush=True)


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f'{name}-{LANG}.png'
    page.screenshot(path=str(path), full_page=True)
    record['screenshots'].append(path.name)
    return path.name


def pane(page):
    """The innermost active tab pane: market tabs wrap product tabs."""
    return page.locator('.ant-tabs-tabpane-active').last


def price_input(page):
    return pane(page).locator('.ant-input-number-input').first


def prepare_row(page):
    """Set the two fields the API requires before any price can be saved.

    `campaign_focus_feature_ids` must hold 1-3 features and
    `production_source_market` may not be null; the screen defaults both to
    empty. A student can set them, so setting them here keeps the price
    checks about price rather than about this defect.
    """
    p = pane(page)
    # Only the campaign-focus tags carry a pointer cursor; the positioning and
    # channel reach/margin tags are decorative.
    tags = p.locator('.ant-tag[style*="cursor"]')
    try:
        if tags.count() and '✓' not in tags.first.inner_text():
            tags.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
    # Always open it and take the first option. Testing the rendered text
    # first looked tidier and silently skipped every row whose placeholder
    # ("Select source") reads like a value, which left the row unsaveable.
    # Re-picking an option already chosen is harmless.
    select = p.locator('.ant-select').first
    try:
        if select.count():
            select.click()
            page.wait_for_timeout(900)
            # antd leaves earlier dropdowns in the DOM, hidden. Taking the
            # first `.ant-select-item-option` anywhere picked an option out of
            # a stale portal and left this row's source market null, which the
            # API then refused.
            option = page.locator(
                '.ant-select-dropdown:not(.ant-select-dropdown-hidden) '
                '.ant-select-item-option').first
            if option.count():
                option.click()
                page.wait_for_timeout(700)
    except Exception:
        pass


def select_product(page, name):
    tab = page.locator('.ant-tabs-tab', has_text=name).last
    tab.click()
    page.wait_for_timeout(1000)
    prepare_row(page)


def set_number(page, locator, value):
    locator.click()
    page.keyboard.press('Control+a')
    if value is None or value == '':
        page.keyboard.press('Backspace')
    else:
        page.keyboard.type(str(value), delay=25)
    page.keyboard.press('Tab')


def settle(page, ms=4500):
    """Past the 2s autosave debounce, with room for the PATCH to land."""
    page.wait_for_timeout(ms)


def api(page, path):
    return page.evaluate("""async (p) => {
        const token = localStorage.getItem('access_token');
        const res = await fetch(p, {headers: token ? {Authorization: 'Bearer ' + token} : {}});
        let body = null;
        try { body = await res.json(); } catch (e) { body = null; }
        return {status: res.status, body};
    }""", path)


def server_row(page, product_id):
    got = api(page, f'/api/games/{GAME}/teams/{TEAM}'
                    f'/decisions/round/{ROUND}/')
    rows = ((got['body'] or {}).get('marketing_decisions') or [])
    return next((r for r in rows if r.get('team_product') == product_id), None)


def pane_text(page):
    try:
        return pane(page).inner_text()
    except Exception:
        return ''


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1100})

        # Google Fonts are unreachable from this sandbox and a pending font
        # request stops the page settling at all. Aborted on purpose; the two
        # ERR_FAILED console errors that result are this harness's, not the
        # product's, and are labelled as such in the report.
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())

        page.on('console', lambda m: (
            record['console'].append({'type': m.type, 'text': m.text[:400]})
            if m.type in ('error', 'warning') else None))
        page.on('requestfailed', lambda r: record['network'].append(
            {'url': r.url[:220], 'failure': (r.failure or '')}))
        page.on('response', lambda r: record['network'].append(
            {'url': r.url[:220], 'status': r.status}) if r.status >= 400 else None)

        def on_request(req):
            if req.method in ('PATCH', 'POST') and '/decisions/round/' in req.url:
                try:
                    record['patches'].append(
                        {'url': req.url[:220], 'method': req.method,
                         'body': (req.post_data or '')[:4000]})
                except Exception:
                    pass

        def on_response(res):
            if '/decisions/round/' in res.url and res.request.method == 'PATCH':
                entry = {'status': res.status}
                if res.status >= 400:
                    try:
                        entry['body'] = res.text()[:500]
                    except Exception:
                        entry['body'] = '<unreadable>'
                record['save_responses'].append(entry)

        page.on('request', on_request)
        page.on('response', on_response)

        # --- language -----------------------------------------------------
        page.goto(f'{BASE}/login', wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        want_zh = LANG.startswith('zh')
        toggle = page.locator('button', has_text='中文' if want_zh else 'EN')
        if toggle.count() > 0:
            try:
                toggle.first.click()
                page.wait_for_timeout(1200)
            except Exception:
                pass
        page.evaluate("(l) => localStorage.setItem('gs_language', l)", LANG)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        body = page.inner_text('body')
        # The toggle itself reads "中文" while the page is in English, so
        # counting raw Han characters would call every English screen Chinese.
        body = body.replace('中文', '')
        has_han = any('一' <= c <= '鿿' for c in body)
        step('login screen renders the requested language',
             'pass' if has_han == want_zh else 'fail',
             f'Chinese characters in page copy: {has_han}')
        shot(page, '00-login')

        page.fill('input#username, input[name="username"]', STUDENT)
        page.fill('input#password, input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        token = page.evaluate("() => localStorage.getItem('access_token')")
        step(f'student {STUDENT} signed in', 'pass' if token else 'fail')
        if not token:
            browser.close()
            return finish()

        ctx = api(page, f'/api/games/{GAME}/teams/{TEAM}/context/marketing/')
        bands = (ctx['body'] or {}).get('price_bands', {})
        record['server_price_bands'] = bands
        step('marketing context returns price_bands',
             'pass' if bands else 'fail', f'keys: {sorted(bands)}')

        page.goto(f'{BASE}/games/{GAME}/teams/{TEAM}/decisions/marketing',
                  wait_until='domcontentloaded')
        page.wait_for_timeout(4000)

        history = [pm for pm in fixture['product_markets']
                   if pm['has_price_history']]
        first, second = history[0], (history[1] if len(history) > 1 else None)
        new_pm = fixture['new_product']
        band = bands.get(first['key'], {})

        # ---------------- Item 1 -------------------------------------------
        select_product(page, first['product_name'])
        text = pane_text(page)
        low = f"{round(float(band.get('min', 0))):,}"
        high = f"{round(float(band.get('max', 0))):,}"
        shown = low in text and high in text
        step('ITEM 1 pricing screen states the legal range',
             'pass' if shown else 'fail',
             f'server band {low}-{high}; screen: '
             f'{text[:180].replace(chr(10), " / ")}')
        record['item1'] = {'band': band, 'shown': shown,
                           'pane_text': text[:600]}
        shot(page, '01-item1-price-band-range')

        # ---------------- Item 2 -------------------------------------------
        out_of_band = int(float(band['max']) * 3)
        set_number(page, pane(page).locator('.ant-input-number-input').nth(1),
                   5000)                      # production volume
        settle(page)
        set_number(page, price_input(page), out_of_band)
        page.wait_for_timeout(1000)
        text = pane_text(page)
        alerted = ('Outside the allowed range' in text or '超出允许区间' in text)
        step('ITEM 2 out-of-band entry raises the alert naming the range',
             'pass' if alerted and shown else 'fail',
             text[:200].replace(chr(10), ' / '))
        shot(page, '02-item2-out-of-band-alert')
        settle(page)
        kept = price_input(page).input_value()
        row = server_row(page, first['product_id'])
        record['item2'] = {'entered': out_of_band, 'input_after': kept,
                           'server_row': row, 'pane_text': text[:600]}
        step('ITEM 2 the number is kept in the box',
             'pass' if str(out_of_band) in kept.replace(',', '') else 'fail',
             f'input shows {kept!r}')
        step('ITEM 2 the out-of-band price is stored, not refused',
             'pass' if row and str(out_of_band) in str(row.get('retail_price'))
             else 'fail',
             f'stored retail_price={row and row.get("retail_price")}')

        # Survives a reload, which is what "kept while the round is open" means.
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(4500)
        select_product(page, first['product_name'])
        reloaded = price_input(page).input_value()
        record['item2']['input_after_reload'] = reloaded
        step('ITEM 2 the out-of-band price survives a reload',
             'pass' if str(out_of_band) in reloaded.replace(',', '') else 'fail',
             f'input shows {reloaded!r}')

        # ---------------- Item 3 -------------------------------------------
        before = len(record['patches'])
        set_number(page, price_input(page), None)
        page.wait_for_timeout(1000)
        text = pane_text(page)
        blank_alerted = ('No price set' in text or '尚未设置价格' in text)
        step('ITEM 3 clearing the price box alerts that it will be priced '
             'at the floor', 'pass' if blank_alerted else 'fail',
             text[:220].replace(chr(10), ' / '))
        shot(page, '03-item3-blank-price-alert')
        settle(page)
        sent = record['patches'][before:]
        null_sent = any('"retail_price":null' in (p['body'] or '')
                        or '"retail_price": null' in (p['body'] or '')
                        for p in sent)
        row = server_row(page, first['product_id'])
        record['item3'] = {'alerted': blank_alerted, 'patches': sent,
                           'server_row_after_clear': row}
        step('ITEM 3 a blank price is sent to the server',
             'pass' if null_sent else 'fail',
             f'{len(sent)} PATCH(es); a null retail_price was sent: {null_sent}')
        step('ITEM 3 the server holds the row with a blank price',
             'pass' if row is not None and row.get('retail_price') is None
             else 'fail',
             f'row present: {row is not None}; '
             f'retail_price={row and row.get("retail_price")}')

        # -- Item 3 edge: the same gesture on a row with no other spend -----
        if second:
            select_product(page, second['product_name'])
            b2 = bands.get(second['key'], {})
            inputs = pane(page).locator('.ant-input-number-input')
            set_number(page, inputs.nth(1), 3000)
            settle(page)
            set_number(page, price_input(page), int(float(b2.get('min', 100))))
            settle(page)
            saved_before = server_row(page, second['product_id'])
            # Now take the production back off, then clear the price: the row
            # has no price, no production and no promotion left.
            inputs = pane(page).locator('.ant-input-number-input')
            set_number(page, inputs.nth(1), 0)
            settle(page)
            before = len(record['patches'])
            set_number(page, price_input(page), None)
            settle(page)
            sent2 = record['patches'][before:]
            mentions = any(f'"team_product":{second["product_id"]}' in (p['body'] or '')
                           for p in sent2)
            row2 = server_row(page, second['product_id'])
            record['item3_edge'] = {
                'product': second['product_name'],
                'row_before': saved_before, 'patches': sent2,
                'row_still_on_server': row2,
                'row_present_in_payload': mentions}
            step('ITEM 3 edge: clearing the price of an otherwise-empty row '
                 'still submits a blank',
                 'pass' if (mentions and row2 is not None
                            and row2.get('retail_price') is None) else 'fail',
                 f'row in PATCH payload: {mentions}; row on server after: '
                 f'{row2 is not None}')
            shot(page, '04-item3-edge-empty-row')

        # ---------------- Item 5, pricing screen ---------------------------
        select_product(page, new_pm['name'])
        page.wait_for_timeout(900)
        text = pane_text(page)
        new_band = bands.get(new_pm['key'])
        promises_floor = ('No price set' in text or '尚未设置价格' in text)
        record['item5_pricing'] = {
            'product': new_pm['name'], 'band': new_band,
            'pane_text': text[:800], 'promises_floor': promises_floor}
        step('ITEM 5 wording shown for a product with no price history',
             'observed',
             f'anchor={new_band and new_band.get("anchor_source")}; '
             f'floor promised on screen: {promises_floor}; '
             f'{text[:200].replace(chr(10), " / ")}')
        shot(page, '05-item5-new-product-pricing-screen')

        # Give it production so the blank row survives to the close, where
        # NOT-FOR-SALE is decided.
        inputs = pane(page).locator('.ant-input-number-input')
        set_number(page, inputs.nth(1), 4000)
        settle(page)
        row = server_row(page, new_pm['id'])
        record['item5_pricing']['server_row'] = row
        step('ITEM 5 the unpriced new product is on the server for the close',
             'pass' if row is not None and row.get('retail_price') is None
             else 'fail',
             f'row present: {row is not None}; '
             f'retail_price={row and row.get("retail_price")}')
        shot(page, '06-marketing-final-state')

        browser.close()
    return finish()


def finish():
    errors = [c for c in record['console'] if c['type'] == 'error']
    refused = [r for r in record['save_responses'] if r['status'] >= 400]
    record['summary'] = {
        'passed': sum(1 for s in record['steps'] if s['outcome'] == 'pass'),
        'failed': sum(1 for s in record['steps'] if s['outcome'] == 'fail'),
        'observed': sum(1 for s in record['steps'] if s['outcome'] == 'observed'),
        'console_errors': len(errors),
        'network_errors': len(record['network']),
        'marketing_saves_refused': len(refused),
        'marketing_saves_total': len(record['save_responses']),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / f'student-walkthrough-{LANG}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('\n' + json.dumps(record['summary'], indent=2))
    print(f'record: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
