"""Ad-hoc DOM probe used while adapting the drivers for walkthrough 2.

probe_dom.py teamconfig          -- the Team Configuration table (home-market Select)
probe_dom.py student <team-ix>   -- marketing / products / market-strategy controls
probe_dom.py marketing <team-ix>  -- the marketing pane: market tabs and the
                                    controls each product row carries
probe_dom.py results <team-ix> <round> [lang]
                                 -- the Round Results performance block, as a
                                    player reads it (W-CE-14), with a screenshot

Read-only: it signs in, opens a panel and prints what it finds. Kept in the
harness because the locators the drivers use were derived from it.
"""
import json
import pathlib
import sys

from walk import BASE, click_tab, fx, sign_in, sync_playwright, visible_text

WHAT = sys.argv[1] if len(sys.argv) > 1 else 'teamconfig'


def student():
    ix = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
    gid = G['game_id']
    team = G['teams'][ix - 1]
    tid = team['team_id']
    member = [r for r in G['roster'] if r.get('team_id') == tid][1]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        page.on('dialog', lambda d: d.accept())
        sign_in(page, '/login', member['username'], 'en', password=member.get('student_id'))
        page.wait_for_timeout(3000)
        for _ in range(4):
            b = page.locator('.ant-modal-content button.ant-btn-primary')
            if not b.count():
                break
            b.last.click(); page.wait_for_timeout(1000)
        base = BASE + '/games/%d/teams/%d/' % (gid, tid)

        page.goto(base + 'decisions/market-strategy', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        tabs = page.locator('.ant-tabs-tab')
        print('market tabs:')
        for i in range(tabs.count()):
            print('   %d: %r' % (i, (tabs.nth(i).inner_text() or '').replace('\n', ' | ')))
        for i in range(tabs.count()):
            tabs.nth(i).click(); page.wait_for_timeout(1800)
            pane = page.locator('.ant-tabs-tabpane-active').last
            btns = pane.locator('button')
            labels = [(btns.nth(j).inner_text() or '').replace('\n', ' ')[:70] for j in range(min(btns.count(), 14))]
            print('  tab %d buttons: %s' % (i, json.dumps(labels)))

        page.goto(base + 'decisions/products', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        rows = page.locator('table tbody tr.ant-table-row')
        print('product rows: %d' % rows.count())
        for i in range(rows.count()):
            print('   row %d: %s' % (i, (rows.nth(i).inner_text() or '').replace('\n', ' | ')[:120]))
        btns = page.locator('button')
        print('products buttons: %s' % json.dumps(
            [(btns.nth(j).inner_text() or '').replace('\n', ' ')[:40] for j in range(min(btns.count(), 20))]))
        if rows.count():
            rows.last.click(); page.wait_for_timeout(2500)
            wrap = page.locator('.ant-modal-wrap:visible .ant-modal-content')
            print('row click -> modal: %r' % ((wrap.last.inner_text()[:300].replace('\n', ' | ')) if wrap.count() else None))
            mb = wrap.locator('button') if wrap.count() else None
            if mb:
                print('modal buttons: %s' % json.dumps([(mb.nth(j).inner_text() or '')[:40] for j in range(mb.count())]))

        page.goto(base + 'decisions/marketing', wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        pane = page.locator('.ant-tabs-tabpane-active').last
        tags = pane.locator('.ant-tag')
        print('marketing tags in pane: %d' % tags.count())
        for i in range(min(tags.count(), 12)):
            tg = tags.nth(i)
            print('   tag %d: %r style=%r' % (i, (tg.inner_text() or '')[:40],
                                              (tg.get_attribute('style') or '')[:90]))
        print('marketing text head: %s' % visible_text(page)[:700].replace('\n', ' | '))
        browser.close()
    return 0


def marketing():
    ix = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
    gid = G['game_id']
    team = G['teams'][ix - 1]
    tid = team['team_id']
    member = [r for r in G['roster'] if r.get('team_id') == tid][1]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        page.on('dialog', lambda d: d.accept())
        sign_in(page, '/login', member['username'], 'en', password=member.get('student_id'))
        page.wait_for_timeout(3000)
        for _ in range(4):
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if not b.count():
                break
            b.last.click(); page.wait_for_timeout(1000)
        page.goto(BASE + '/games/%d/teams/%d/decisions/marketing' % (gid, tid),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(7000)
        tabs = page.locator('.ant-tabs-tab')
        print('tabs: %s' % json.dumps([(tabs.nth(i).text_content() or '').strip()
                                       for i in range(tabs.count())]))
        for i in range(tabs.count()):
            tabs.nth(i).click(); page.wait_for_timeout(2500)
            pane = page.locator('.ant-tabs-tabpane-active').last
            print('--- tab %d' % i)
            print('   inner tabs: %d' % pane.locator('.ant-tabs-tab').count())
            print('   cards: %d  number-inputs: %d  cursor-tags: %d'
                  % (pane.locator('.ant-card').count(),
                     pane.locator('.ant-input-number-input').count(),
                     pane.locator('.ant-tag[style*="cursor"]').count()))
            print('   text: %s' % (pane.inner_text() or '')[:600].replace('\n', ' | '))
        browser.close()
    return 0


def results():
    ix = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rnd = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    lang = sys.argv[4] if len(sys.argv) > 4 else 'en'
    G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
    gid = G['game_id']
    team = G['teams'][ix - 1]
    tid = team['team_id']
    member = [r for r in G['roster'] if r.get('team_id') == tid][0]
    shots = pathlib.Path(__file__).resolve().parent.parent / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('dialog', lambda d: d.accept())
        sign_in(page, '/login', member['username'], lang, password=member.get('student_id'))
        page.wait_for_timeout(3000)
        for _ in range(4):
            b = page.locator('.ant-modal-content button.ant-btn-primary')
            if not b.count():
                break
            b.last.click(); page.wait_for_timeout(1000)
        page.goto(BASE + '/games/%d/teams/%d/results/%d' % (gid, tid, rnd),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(7000)
        text = visible_text(page)
        want = ('SHAREHOLDER', 'Shareholder', '\u80a1\u4e1c', 'RETURN', 'INDEX', '%')
        lines = [l.strip() for l in text.splitlines() if any(w in l for w in want)]
        raw = [l.strip() for l in text.splitlines() if l.strip()]
        for i, l in enumerate(raw):
            if 'PERFORMANCE INDEX' in l or '\u7ee9\u6548\u6307\u6570' in l:
                print('   --- window around %r:' % l)
                for w in raw[max(0, i - 6): i + 14]:
                    print('       %s' % w[:90])
                break
        print('team %s round %d (%s)' % (team.get('team_name'), rnd, lang))
        for l in lines[:25]:
            print('   %s' % l)
        name = 'v-results-t%d-r%d-%s.jpg' % (ix, rnd, lang)
        page.screenshot(path=str(shots / name), full_page=True, type='jpeg', quality=55)
        print('screenshot: %s' % name)
        browser.close()
    return 0


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        sign_in(page, '/instructor/login', fx['instructor'], 'en')
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(4000)
        page.locator('.ant-card', has_text='CE26').last.click()
        page.wait_for_timeout(2500)
        page.locator('.ant-card', has_text='CE26-A').last.click()
        page.wait_for_timeout(5000)
        click_tab(page, 'Game Control')
        page.wait_for_timeout(4000)
        exp = page.locator('.ant-tabs-tabpane-active button', has_text='Expand')
        print('expand buttons: %d' % exp.count())
        if exp.count():
            exp.first.click()
            page.wait_for_timeout(3500)
        pane = page.locator('.ant-tabs-tabpane-active')
        tables = pane.locator('table')
        print('tables in the active pane: %d' % tables.count())
        for i in range(tables.count()):
            table = tables.nth(i)
            th = table.locator('thead')
            head = (th.first.inner_text() if th.count() else '').replace('\n', ' / ')
            print('  table %d: rows=%d selects=%d head=%s'
                  % (i, table.locator('tbody tr').count(),
                     table.locator('.ant-select').count(), head[:100]))
        rows = pane.locator('table tbody tr')
        print('pane rows: %d' % rows.count())
        if rows.count():
            print('  row0 text: %s' % (rows.first.inner_text() or '')[:160].replace('\n', ' | '))
            print('  row0 selects: %d' % rows.first.locator('.ant-select').count())
        allrows = page.locator('table tbody tr')
        print('page rows: %d; page-row0 selects: %d'
              % (allrows.count(),
                 allrows.first.locator('.ant-select').count() if allrows.count() else -1))
        browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit({'student': student, 'results': results,
                      'marketing': marketing}.get(WHAT, main)())
