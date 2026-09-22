"""Does typing 5000000 into the Loan Amount box store $5? probe_loan_input.py <team-index>

Three ways a person enters the number: typed key by key, typed with a slow
cadence, and pasted. The stored financing row is read back after each.
"""
import json
import sys

from walk import (BASE, SCRATCH, Recorder, api, sign_in, sync_playwright)

TEAM_IX = int(sys.argv[1]) if len(sys.argv) > 1 else 1
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']; TID = G['teams'][TEAM_IX - 1]['team_id']
m = [r for r in G['roster'] if r.get('team_id') == TID][2]
R = Recorder('probe-loan-input-t%d' % TEAM_IX, 'en')
DEC = '/api/games/%d/teams/%d/decisions/round/1/' % (GID, TID)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        sign_in(page, '/login', m['username'], 'en', password=m.get('student_id'))
        page.wait_for_timeout(2500)
        page.goto(BASE + '/games/%d/teams/%d/decisions/finance' % (GID, TID), wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        page.locator('.ant-tabs-tab', has_text='Capital Management').first.click(); page.wait_for_timeout(1500)
        box = page.locator('.ant-tabs-tabpane-active .ant-input-number-input').first
        for label, action in (('typed fast', lambda: page.keyboard.type('5000000', delay=20)),
                              ('typed slowly', lambda: page.keyboard.type('6000000', delay=250)),
                              ('pasted', lambda: box.fill('7000000'))):
            box.click(); page.keyboard.press('Control+a'); page.keyboard.press('Backspace')
            page.wait_for_timeout(300)
            action()
            shown_before_blur = box.input_value()
            page.keyboard.press('Tab'); page.wait_for_timeout(2500)
            shown = box.input_value()
            fin = (api(page, 'GET', DEC)['body'].get('financing') or {})
            R.observe(label, {'box_before_blur': shown_before_blur, 'box_after_blur': shown, 'stored_new_debt': fin.get('new_debt')})
            R.step('loan amount %s' % label, 'observed', 'box before blur %r, after blur %r, stored %s' % (shown_before_blur, shown, fin.get('new_debt')))
            R.screen(page, 'probe-loan-%s' % label.replace(' ', '-'))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
