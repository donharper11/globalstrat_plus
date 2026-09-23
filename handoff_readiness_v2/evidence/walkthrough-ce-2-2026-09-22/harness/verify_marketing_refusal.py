"""W-CE-04: a refused marketing row must name the product it is about.

verify_marketing_refusal.py <lang> <team-index> <round>

The repair (`b0d3c35`) names the row in the refusal: "<product> in <market>:
<sentence>". The path a player takes to it is a product-market row that has
promotion spend and no campaign focus -- which is what a brand-new product's
row looks like before the student picks a focus. This driver fills price,
volume and promotion on a row that has no stored decision, leaves the focus
alone, and records what the server says and what the page shows.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, set_number, sign_in, sync_playwright,
                  visible_text)

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
R = Recorder('verify-marketing-refusal-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)


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

        ctx = api(page, 'GET', '/api/games/%d/teams/%d/context/marketing/' % (GID, TID))['body']
        pms = (ctx or {}).get('product_markets') or []
        stored = {(int(r.get('team_product')), int(r.get('market'))): r
                  for r in (api(page, 'GET', DEC)['body'].get('marketing_decisions') or [])}
        R.observe('rows_stored', len(stored))
        target = None
        for pm in pms:
            for mk in (pm.get('markets') or []):
                key = (int(pm.get('product_id')), int(mk.get('market_id')))
                if key not in stored:
                    target = (pm, mk)
                    break
            if target:
                break
        if not target:
            R.step('a product-market row with no decision yet is available', 'fail',
                   'every row already has a decision; the refusal path needs a fresh row')
            browser.close(); return R.finish()
        pm, mk = target
        pname = pm.get('product_name')
        mname = mk.get('market__name') or mk.get('market_name')
        R.observe('target_row', {'product': pname, 'market': mname})

        page.goto(BASE + '/games/%d/teams/%d/decisions/marketing' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        # The tab bar is flat: the market, then one tab per product in it.
        tabs = page.locator('.ant-tabs-tab')
        labels = [(tabs.nth(i).text_content() or '').strip() for i in range(tabs.count())]
        R.observe('tab_labels', labels)
        picked_p = None
        for i, label in enumerate(labels):
            if pname and pname in label:
                tabs.nth(i).click(); page.wait_for_timeout(2500)
                picked_p = label
                break
        R.observe('product_tab', picked_p)
        if picked_p is None:
            R.step('the row under test can be reached on the marketing page', 'fail',
                   'no tab named %r among %s' % (pname, json.dumps(labels, ensure_ascii=False)[:300]))
            browser.close(); return R.finish()
        R.screen(page, 'v-wce04-%d-r%d-00-row-before' % (TEAM_IX, ROUND),
                 'a product-market row with no campaign focus chosen yet')

        pane = page.locator('.ant-tabs-tabpane-active').last
        nums = pane.locator('.ant-input-number-input')
        R.observe('inputs_on_row', nums.count())
        if nums.count() >= 4:
            set_number(page, nums.nth(0), 500)
            page.wait_for_timeout(600)
            set_number(page, nums.nth(1), 4000)
            page.wait_for_timeout(600)
            set_number(page, nums.nth(3), 150000)      # promotion, no focus chosen
        page.wait_for_timeout(6000)
        text = visible_text(page)
        refusals = [x for x in R.record['refused'] if 'marketing' in x['url']]
        R.observe('server_refusals', refusals)
        notice = [l.strip() for l in text.splitlines()
                  if 'focus' in l.lower() or '焦点' in l or 'not saved' in l.lower()
                  or '未保存' in l or (pname and pname in l and ':' in l)]
        R.observe('notice_lines', notice[:8])
        R.screen(page, 'v-wce04-%d-r%d-01-refusal' % (TEAM_IX, ROUND),
                 'what the student is told about the refused row')
        body = ' '.join(x.get('body', '') for x in refusals)
        named = bool(pname and (pname in body or any(pname in l for l in notice)))
        R.step('the refused marketing row names its product (W-CE-04)',
               'pass' if refusals and named else ('fail' if refusals else 'observed'),
               'product=%r refusal=%s notice=%s'
               % (pname, json.dumps([x['body'][:220] for x in refusals], ensure_ascii=False)[:400],
                  json.dumps(notice[:4], ensure_ascii=False)[:300]))
        shown_once = len([l for l in notice if 'focus' in l.lower() or '焦点' in l])
        R.step('the refusal is shown once, not twice (W-CE-04)',
               'pass' if shown_once <= 1 else 'fail', '%d notices on the page' % shown_once)
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
