"""W-CE3-13 / W-CE2-09 / W-CE-18b: what the Decision Summary says about money.

    probe_summary_wording.py <lang> <team-index> <round>

Walkthrough 3 recorded a team that was $30.0M **over**-committed being told
that amount was *not yet committed*, written `$-30.0M` rather than -$30.0M,
and W-CE-18b before it recorded two different totals for what a round costs.
This reads the Budget Summary block on the real screen, in the state the team
is actually in, and records every money line on it verbatim.
"""
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, sign_in, sync_playwright, visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
ROUND = int(sys.argv[3])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
team = G['teams'][TEAM_IX - 1]
TID = team['team_id']
members = [r for r in G['roster'] if r.get('team_id') == TID]
STUDENT = members[0]
R = Recorder('summary-wording-t%d-r%d' % (TEAM_IX, ROUND), LANG)
R.observe('team', team.get('team_name'))
DEC = '/api/games/%d/teams/%d/decisions/round/%d/' % (GID, TID, ROUND)
# An unformatted negative: a minus inside or before the dollars with no
# magnitude suffix, e.g. `$-30000000` or `$-12553689`.
RAW_NEGATIVE = re.compile(r'\$-\d{4,}(?![.\d]*[KMB])')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1200})
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
        page.goto(BASE + '/games/%d/teams/%d/decisions/summary' % (GID, TID),
                  wait_until='domcontentloaded')
        page.wait_for_timeout(7000)
        text = visible_text(page)
        R.observe('summary_text', text[:4000])
        R.screen(page, 'v4-wording-t%d-r%d-summary' % (TEAM_IX, ROUND))
        s = api(page, 'GET', DEC + 'summary/')['body'] or {}
        bs = s.get('budget_summary') or {}
        R.observe('budget_summary', bs)
        R.observe('lock_blockers', s.get('lock_blockers'))
        money_lines = [l.strip() for l in text.splitlines() if '$' in l]
        R.observe('money_lines', money_lines[:25])
        available = float(bs.get('total_available') or 0)
        committed = float(bs.get('committed_total') or 0)
        over = committed - available
        R.observe('over_committed_by', over)
        raw = RAW_NEGATIVE.findall(text)
        R.observe('unformatted_negatives', raw)
        R.step('W-CE2-09 no unformatted negative anywhere on the Decision '
               'Summary', 'pass' if not raw else 'fail',
               'found: %s' % json.dumps(raw[:6]))
        # W-CE3-13: the sentence about the overrun.
        claim = [l for l in money_lines
                 if 'not yet committed' in l.lower() or '尚未承诺' in l]
        R.observe('unallocated_sentence', claim)
        if over > 0:
            R.step('W-CE3-13 a team that is over-committed is not told the '
                   'overrun is "not yet committed"',
                   'pass' if not claim else 'fail',
                   'over-committed by %.2f; the screen says: %s'
                   % (over, json.dumps(claim, ensure_ascii=False)[:400]))
        else:
            R.step('W-CE3-13 the team is not over-committed in this round',
                   'observed',
                   'available %.2f, committed %.2f; the line reads %s'
                   % (available, committed,
                      json.dumps(claim, ensure_ascii=False)[:300]))
        # W-CE-18b: one total for what the round costs.
        totals = sorted({m for m in re.findall(r'\$-?[\d,]+(?:\.\d+)?[KMB]?', text)})
        R.observe('every_money_figure_on_the_screen', totals[:40])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
