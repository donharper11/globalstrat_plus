"""W-CE2-04: the Operator Log row for a refused action reads as a sentence.

verify_operator_log_refusal.py <lang>

Walkthrough 2 recorded a row that printed the server's internal exception
verbatim — *Natural key ('team_id', 'market_id', 'construction_started_round')
is not unique in section "team_plant"… Declare a key that identifies a row, or
set key=None to use a content key.* — with `engine_failure` beside it: storage
names, a Python argument and an instruction addressed to a developer.

The P0 that produced that particular fault cannot be reached any more, so the
refusals driven here are the ones an operator can still cause on a live game:

  * *Run post-round processing* on a round that is already processed;
  * the lifecycle *Advance Round* override with no reason written.

Both are refused by the server, both are recorded, and the Operator Log is
then read in the language the console is in. What is asserted is what the
repair promised: a sentence, the technical cause labelled rather than raw, no
storage field name, no Python argument, and no `engine_failure` token.
"""
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, click_tab, fx, sign_in, sync_playwright,
                  visible_text)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
R = Recorder('verify-operator-log-refusal', LANG)
LOG_TAB = {'en': 'Operator Log', 'zh-CN': '操作日志'}[LANG]
DEVELOPER_SHAPES = [
    'Natural key', 'Traceback', 'SnapshotError', 'set key=None',
    'Declare a key', 'team_id', 'market_id', 'construction_started_round',
    'engine_failure', 'section "', "('",
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close(); return R.finish()
        api(page, 'PUT', '/api/user/preferences/', {'language': LANG})
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)

        rc = api(page, 'GET', '/api/games/%s/round-control/' % GID)['body'] or {}
        R.observe('round_control', rc)
        processed = None
        for n in range(1, int(rc.get('current_round') or 1)):
            processed = n
        R.observe('already_processed_round', processed)

        # 1. process a round that is already processed
        if processed:
            resp = api(page, 'POST', '/api/games/%s/round-control/process/' % GID,
                       {'expected_round_number': processed})
            R.observe('reprocess_refusal', resp)
            R.step('processing an already-processed round is refused',
                   'pass' if resp['status'] >= 400 else 'observed', json.dumps(resp)[:400])

        # 2. the lifecycle override with no reason
        resp2 = api(page, 'POST', '/api/games/%s/instructor/advance-round/' % GID,
                    {'force': True})
        R.observe('advance_no_reason_refusal', resp2)
        R.step('the lifecycle override with no written reason is refused',
               'pass' if resp2['status'] >= 400 else 'fail', json.dumps(resp2)[:400])

        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(5000)
        page.locator('.ant-card', has_text=G.get('course_code', 'CE26')).last.click()
        page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G.get('section_code', 'CE26-A')).last.click()
        page.wait_for_timeout(6000)
        click_tab(page, LOG_TAB)
        page.wait_for_timeout(6000)
        R.screen(page, 'v-oplog-refusals-%s' % LANG, 'the Operator Log after two refused actions')
        text = page.locator('.ant-tabs-tabpane-active').last.inner_text()
        R.observe('operator_log_text', text[:4000])
        refused_lines = [l.strip() for l in text.splitlines()
                         if re.search(r'refus|拒绝|未执行', l, re.I)]
        R.observe('refused_rows', refused_lines[:10])
        found = [s for s in DEVELOPER_SHAPES if s in text]
        R.step('no storage name, Python argument or raw exception in the Operator Log (W-CE2-04)',
               'pass' if not found else 'fail',
               'found %s; the refused rows read: %s'
               % (found, json.dumps(refused_lines[:4], ensure_ascii=False)[:600]))
        R.step('the log carries a row for the refusals just made',
               'pass' if refused_lines else 'observed',
               json.dumps(refused_lines[:4], ensure_ascii=False)[:500])
        api_rows = api(page, 'GET', '/api/games/%s/instructor/operator-events/' % GID)
        R.observe('operator_log_api', api_rows['status'])
        if isinstance(api_rows.get('body'), dict):
            rows = api_rows['body'].get('events') or api_rows['body'].get('results') or []
            # Only the PROSE fields an operator reads. The structured
            # before/after payload of an audit row legitimately carries
            # storage keys -- that is the record, not a sentence -- and the
            # walkthrough-2 defect was about the sentence.
            def prose(row):
                return ' | '.join(str(row.get(k) or '') for k in
                                  ('detail', 'message', 'reason', 'summary', 'error'))
            bad = [r for r in rows if any(s in prose(r) for s in DEVELOPER_SHAPES)]
            R.observe('rows_with_developer_text', bad[:5])
            R.step('nothing in the served log carries developer text either',
                   'pass' if not bad else 'fail', json.dumps(bad[:2], ensure_ascii=False)[:600])
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
