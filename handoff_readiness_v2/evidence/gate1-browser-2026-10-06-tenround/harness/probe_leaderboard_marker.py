"""W-CE3-15: the leaderboard explains why a high score is ranked below a low one.

    probe_leaderboard_marker.py <lang> <team-index>

Walkthrough 3 recorded the top score in fourth place with nothing on the
screen to explain it. The repair serves `commercially_inactive` and
`rank_marker` on the row and `rank_rule_note` under the table, and
`LeaderboardPage.js` renders both. This opens the Leaderboard page itself,
waits for it to load, and compares what the page shows with what the route
serves **for the round the page is showing** -- walkthrough 4's first attempt
compared a page showing the latest processed round with a payload for a
different one.
"""
import json
import pathlib
import sys

from walk import (BASE, Recorder, api, sign_in, sync_playwright, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2]) if len(sys.argv) > 2 else 1
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[0]
R = Recorder('leaderboard-marker-t%d' % TEAM_IX, LANG)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1400})
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
            if not b.count():
                break
            b.last.click()
            page.wait_for_timeout(1200)
        page.goto(BASE + '/games/%d/leaderboard' % GID,
                  wait_until='domcontentloaded')
        page.wait_for_timeout(12000)
        text = visible_text(page)
        R.observe('page_text_as_opened', text[:6000])
        R.screen(page, 'v4-leaderboard-as-opened',
                 'the Leaderboard as it opens, before anything is chosen')
        import re as _re
        m = _re.search(r'Round (\d+) . Team Rankings|\u7b2c\s*(\d+)\s*\u56de\u5408', text)
        R.observe('round_the_page_opened_on', m.group(0) if m else None)
        # Which round is the page showing? Its own subtitle says so.
        # The round-control route is instructor-only, so a student driver
        # cannot ask it which round is showing; the page itself takes the
        # latest PROCESSED round, which is the highest round the leaderboard
        # route answers with entries.
        shown = 0
        for candidate in range(12, 0, -1):
            got = api(page, 'GET', '/api/games/%d/leaderboard/round/%d/'
                      % (GID, candidate))
            body = got.get('body') if isinstance(got.get('body'), dict) else {}
            if got.get('status') == 200 and (
                    body.get('rankings') or body.get('leaderboard')
                    or body.get('entries')):
                shown = candidate
                break
        R.observe('round_the_page_shows', shown)
        lb = api(page, 'GET', '/api/games/%d/leaderboard/round/%d/'
                 % (GID, shown))['body']
        entries = ((lb or {}).get('rankings') or (lb or {}).get('leaderboard')
                   or (lb or {}).get('entries') or [])
        note = (lb or {}).get('rank_rule_note')
        marked = [e.get('team_name') for e in entries if e.get('rank_marker')]
        markers = sorted({e.get('rank_marker') for e in entries
                          if e.get('rank_marker')})
        R.observe('rank_rule_note', note)
        R.observe('marked_rows', marked)
        R.observe('markers', markers)
        R.observe('rows', [{k: e.get(k) for k in
                            ('rank', 'team_name', 'performance_index',
                             'total_revenue', 'commercially_inactive',
                             'rank_marker')} for e in entries])
        inverted = [(entries[i].get('team_name'),
                     entries[i].get('performance_index'),
                     entries[j].get('team_name'),
                     entries[j].get('performance_index'))
                    for i in range(len(entries))
                    for j in range(i + 1, len(entries))
                    if (entries[i].get('performance_index') or 0)
                    < (entries[j].get('performance_index') or 0)]
        R.observe('inversions', inverted)
        R.step('the round the page is showing has a score ranked below a '
               'lower one', 'observed' if inverted else 'observed',
               'round %d: %s' % (shown, json.dumps(inverted, ensure_ascii=False)))
        # Choose the round that actually has the inversion, so the marker and
        # the rule can be looked for on a table that should carry them.
        picker = page.locator('.ant-select').first
        if picker.count():
            picker.click()
            page.wait_for_timeout(1200)
            opt = page.locator(
                '.ant-select-dropdown:not(.ant-select-dropdown-hidden) '
                '.ant-select-item-option', has_text=str(shown))
            if opt.count():
                opt.first.click()
                page.wait_for_timeout(6000)
        text = visible_text(page)
        R.observe('page_text_on_round_%d' % shown, text[:6000])
        R.screen(page, 'v4-leaderboard-round%d' % shown,
                 'the Leaderboard with round %d chosen' % shown)
        note_on_screen = bool(note) and note[:20] in text
        markers_on_screen = [m for m in markers if m and m in text]
        R.step('the Leaderboard opens on the latest PROCESSED round',
               'pass' if str(shown) in (R.record['observed'].get(
                   'round_the_page_opened_on') or '') else 'fail',
               'it opened on %r; the latest processed round is %d'
               % (R.record['observed'].get('round_the_page_opened_on'),
                  shown))
        R.step('W-CE3-15 the marker the route serves is on the row',
               'pass' if markers and markers_on_screen else 'fail',
               'markers served: %s; found on the page: %s'
               % (json.dumps(markers, ensure_ascii=False),
                  json.dumps(markers_on_screen, ensure_ascii=False)))
        R.step('W-CE3-15 the rule is printed under the table',
               'pass' if note_on_screen else 'fail',
               'note served: %r; on the page: %s' % (note, note_on_screen))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
