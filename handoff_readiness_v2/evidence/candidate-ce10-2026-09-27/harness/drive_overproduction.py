"""Make a team build far more stock than its markets will buy, from the page.

    drive_overproduction.py <lang> <team-index> <round> <units>

Why the walkthrough needs it: the whole point of integrator decision 13 is
that a team whose cash has gone negative can still raise financing and lock
the next round. Something has to take the team's cash negative first, and it
has to be something a player can actually do. Building stock is exactly that:
the production volume is a box on the Marketing page, and cost of goods is
charged at resolution, outside `funding_need.decision_outlays`, so nothing
the lock checks refuses it. The team simply makes a large operating loss --
the ordinary way a company runs out of money.

This is an auditor's deliberate act and is recorded as one. It types a number
into a box the product offers; it does not touch the database.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, set_number, sign_in, sync_playwright,
                  visible_text)

LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
UNITS = int(sys.argv[4]) if len(sys.argv) > 4 else 400000
BLANK_PRICE = len(sys.argv) > 5 and sys.argv[5] == 'blank-price'
SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[min(1, len(members) - 1)]
R = Recorder('overproduce-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
R.observe('units_per_row', UNITS)
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)


def pane(page):
    return page.locator('.ant-tabs-tabpane-active').last


def rows(page):
    d = api(page, 'GET', DEC)['body']
    return {(r.get('team_product'), r.get('market')): r
            for r in (d.get('marketing_decisions') or [])}


def tab_labels(tabs_root):
    """Return only this Tabs component's labels, never nested product tabs."""
    tabs = tabs_root.locator(
        ':scope > .ant-tabs-nav [role="tab"]')
    return [(tabs.nth(i).inner_text() or '').strip()
            for i in range(tabs.count())]


def select_tab(page, tabs_root, label):
    """Select an AntD tab through its visible tab or normal overflow menu."""
    tabs = tabs_root.locator(
        ':scope > .ant-tabs-nav [role="tab"]')
    matches = tabs.filter(has_text=label)
    if matches.count() != 1:
        raise AssertionError(
            'expected one direct tab %r, found %d among %r'
            % (label, matches.count(), tab_labels(tabs_root)))

    tab = matches.first
    if tab.is_visible():
        tab.click()
    else:
        more = tabs_root.locator(
            ':scope > .ant-tabs-nav .ant-tabs-nav-more:visible')
        if more.count() != 1:
            raise AssertionError(
                'tab %r is hidden and the AntD overflow control is unavailable'
                % label)
        more.click()
        page.wait_for_timeout(400)
        menu = page.locator('.ant-tabs-dropdown:visible')
        choice = menu.get_by_role('menuitem', name=label, exact=True)
        if choice.count() != 1 or not choice.first.is_visible():
            raise AssertionError(
                'tab %r is hidden but not offered by the visible overflow menu'
                % label)
        choice.first.click()

    page.wait_for_timeout(600)
    active = tabs_root.locator(
        ':scope > .ant-tabs-nav .ant-tabs-tab-active')
    if active.count() != 1 or label not in (active.first.inner_text() or ''):
        raise AssertionError('tab %r did not become active' % label)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'), rec=R)
        R.step('%s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.wait_for_timeout(3000)
        for _ in range(6):
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if b.count() == 0:
                break
            b.last.click()
            page.wait_for_timeout(1000)
        page.goto(BASE + '/games/%d/teams/%d/decisions/marketing' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(6000)
        R.observe('before', list(rows(page).values()))
        outer_tabs = page.locator('.ant-tabs').first
        market_labels = tab_labels(outer_tabs)
        R.observe('market_tabs', market_labels)
        touched = 0
        for market_label in market_labels or [None]:
            if market_label is not None:
                select_tab(page, outer_tabs, market_label)
                page.wait_for_timeout(2500)
            market_pane = outer_tabs.locator(
                ':scope > .ant-tabs-content-holder > .ant-tabs-content '
                '> .ant-tabs-tabpane-active')
            inner_tabs = market_pane.locator(':scope > .ant-tabs').first
            product_labels = (tab_labels(inner_tabs)
                              if inner_tabs.count() else [])
            for product_label in product_labels or [None]:
                if product_label is not None:
                    select_tab(page, inner_tabs, product_label)
                    page.wait_for_timeout(1500)
                nums = pane(page).locator('.ant-input-number-input')
                if nums.count() < 2:
                    continue
                set_number(page, nums.nth(1), UNITS)
                page.wait_for_timeout(1500)
                if BLANK_PRICE:
                    # A blank price is the product's own way of saying "not for
                    # sale this round" -- the Marketing page explains it in
                    # those words. Producing nothing is not enough to make a
                    # firm commercially inactive, because stock built in an
                    # earlier round still sells.
                    set_number(page, nums.nth(0), '')
                    page.wait_for_timeout(1500)
                page.wait_for_timeout(2500)
                touched += 1
        R.screen(page, 'v4-overproduce-t%d-r%d' % (TEAM_IX, ROUND),
                 '%d units typed into every production-volume box' % UNITS)
        after = rows(page)
        R.observe('after', list(after.values()))
        big = [r for r in after.values()
               if int(float(r.get('production_volume') or 0)) >= UNITS]
        R.step('the production volume the page stored is the number typed',
               'pass' if big else 'fail',
               '%d rows touched, %d stored at %d units'
               % (touched, len(big), UNITS))
        R.observe('summary_text', visible_text(page)[:600])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
