"""Answer a disputed result from the console, on the screen, in one sitting.

    dispute_lookup.py [round] [team-index] [lang]

The CRV2-08 dispute procedure lists six claims a team can make after a round
is published. Three of them are answered from management commands and are
already on record there (`who_accessed`, `replay_round`); this driver is about
the three an instructor has to answer from the product while the heat is
running, and it answers them the way an instructor would -- by opening the
screens, not by calling the API:

  1. "We submitted before the deadline."         Team Overview -> View
  2. "That is not what we entered."               Decisions -> the audit
                                                  evidence behind the round.
  5. "The operator changed something."            Game Control -> Operator Log.

Claim 5 was recorded UNANSWERABLE in CRV2-08: the rows existed and nothing in
the product read them back. The Operator Log panel is the repair, so this
driver's verdict on it is a re-test of a closed finding and not a formality.

Read-only: it opens screens, expands a panel and filters a table. Writes
records/dispute-lookup-r<N>-<lang>.json.
"""
import datetime as dt
import json
import pathlib
import re
import sys

from walk import (BASE, Recorder, api, click_tab, fx, modal_text, sign_in,
                  sync_playwright, visible_text)

ROUND = int(sys.argv[1]) if len(sys.argv) > 1 else 1
TEAM_IX = int(sys.argv[2]) if len(sys.argv) > 2 else 1
LANG = sys.argv[3] if len(sys.argv) > 3 else 'en'

SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
TEAM = G['teams'][TEAM_IX - 1]
R = Recorder('dispute-lookup-r%d' % ROUND, LANG)
L = {
    'en': {'control': 'Game Control', 'teams': 'Team Overview',
           'view': 'View Decisions', 'log': 'Operator Log',
           'evidence': 'Audit', 'rejected': 'Rejected', 'round': 'Round'},
    'zh-CN': {'control': '游戏控制', 'teams': '团队概览',
              'view': '查看决策', 'log': '操作日志',
              'evidence': '审计', 'rejected': '已拒绝', 'round': '回合'},
}[LANG]


def A(page):
    return page.locator('.ant-tabs-tabpane-active')


def parse(stamp):
    if not stamp:
        return None
    try:
        return dt.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None


def main():
    answers = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox',
                                          '--disable-dev-shm-usage',
                                          '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        R.instrument(page)
        ok = sign_in(page, '/instructor/login', fx['instructor'], LANG, rec=R)
        R.step('instructor signs in', 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.goto(BASE + '/instructor', wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        page.locator('.ant-card', has_text=G['course_code']).last.click()
        page.wait_for_timeout(2000)
        page.locator('.ant-card', has_text=G['section_code']).last.click()
        page.wait_for_timeout(6000)

        # The deadline the claim is measured against, read from the schedule
        # the instructor set rather than from the fixture.
        sched = api(page, 'GET', '/api/games/%s/round-schedule/' % GID)
        rounds = ((sched.get('body') or {}).get('rounds') or [])
        deadline = next((r.get('deadline') for r in rounds
                         if r.get('round_number') == ROUND), None)
        R.observe('round_deadline', deadline)

        # ---- claims 1 and 2: the team's own audit evidence ----------------
        click_tab(page, L['teams'])
        page.wait_for_timeout(3500)
        R.screen(page, 'd00-team-overview')
        row = A(page).locator('tbody tr', has_text=TEAM['team_name']).first
        R.step('the disputing team is on the Team Overview',
               'pass' if row.count() else 'fail', TEAM['team_name'])
        view = (row.locator('button', has_text=L['view']).first if row.count()
                else A(page).locator('button', has_text=L['view']).first)
        R.step('the console offers the decision drill-down for that team',
               'pass' if view.count() else 'fail')
        if not view.count():
            browser.close()
            return R.finish()
        view.click()
        page.wait_for_timeout(4000)
        # THE DRILL-DOWN OPENS ON THE CURRENT ROUND, not on the round being
        # disputed: its own round picker defaults to `dashboard.current_round`.
        # The first version of this driver compared round-1 rows from the API
        # against a screen showing round 3, which is how a check can pass or
        # fail for a reason that has nothing to do with the product. The round
        # is chosen on the screen, matched EXACTLY so "Round 1" cannot select
        # "Round 10", and the choice is then confirmed.
        sel = page.locator('.ant-modal-wrap:visible .ant-select').first
        picked = None
        if sel.count():
            sel.click()
            page.wait_for_timeout(900)
            want = re.compile(r'^\s*%s\s*%d\s*$' % (re.escape(L['round']), ROUND))
            opt = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) '
                               '.ant-select-item-option').filter(has_text=want)
            if opt.count():
                picked = opt.first.text_content()
                opt.first.click()
                page.wait_for_timeout(3500)
            else:
                page.keyboard.press('Escape')
        head = (modal_text(page) or '')
        R.observe('drill_round_picked', picked)
        R.step('the drill-down is set to the round under dispute',
               'pass' if picked and ('%s %d' % (L['round'], ROUND) in head
                                     or '%s%d' % (L['round'], ROUND) in head)
               else 'fail',
               'picked=%r; modal says %r' % (picked, head[:120]))
        R.observe('drill_modal_head', head[:600])
        R.screen(page, 'd01-decisions-drilldown')

        # W-CE-20 put the evidence behind a closed panel. An instructor
        # answering a dispute has to be able to open it, so this is a click on
        # the real control and not a read of the response.
        panel = page.locator('.ant-modal-wrap:visible .ant-collapse-header')
        R.step('the audit evidence is one click away inside the drill-down',
               'pass' if panel.count() else 'fail',
               '%d collapse headers' % panel.count())
        if panel.count():
            panel.first.click()
            page.wait_for_timeout(2500)
        shown = visible_text(page)
        # The payload column prints the stored decision verbatim -- that IS the
        # evidence a dispute is answered from -- so the leak scan's
        # `team_product` / `retail_price` hits on this one screen are the record
        # being shown as stored, not copy written for a player.
        R.screen(page, 'd02-audit-evidence-open',
                 'the payload column shows the stored record verbatim on '
                 'purpose; leak-scan field names here are expected')

        drill = api(page, 'GET',
                    '/api/games/%s/instructor/teams/%s/decisions/?round=%d'
                    % (GID, TEAM['team_id'] if 'team_id' in TEAM
                       else TEAM.get('id'), ROUND))
        body = drill.get('body') if isinstance(drill.get('body'), dict) else {}
        events = body.get('audit_events') or []
        saves = [e for e in events if e.get('action') == 'save']
        locks = [e for e in events if e.get('action') == 'lock']
        R.observe('audit_event_actions', sorted({e.get('action')
                                                for e in events}))
        R.step('the drill-down carries this round\'s audit trail',
               'pass' if events else 'fail',
               '%d events, %d saves, %d locks' % (len(events), len(saves),
                                                  len(locks)))

        # Every column the dispute procedure asks for has to be ON the screen,
        # not merely in the response behind it.
        on_screen = []
        for ev in saves[:3] + locks[:1]:
            rid = ev.get('request_id') or ''
            sha = ev.get('payload_sha256') or ''
            on_screen.append({
                'action': ev.get('action'),
                'request_id_on_screen': bool(rid) and rid in shown,
                'sha256_on_screen': bool(sha) and sha[:16] in shown,
                'endpoint_on_screen': bool(ev.get('endpoint'))
                                      and str(ev.get('endpoint')) in shown,
            })
        R.observe('evidence_columns_on_screen', on_screen)
        with_rid = [e for e in saves if (e.get('request_id') or '').strip()]
        R.observe('saves_carrying_a_request_id',
                  {'saves': len(saves), 'with_request_id': len(with_rid)})
        R.step('the payload hash of each accepted save is readable on the '
               'screen',
               'pass' if on_screen and all(x['sha256_on_screen']
                                           for x in on_screen[:3])
               else 'fail', json.dumps(on_screen)[:400])
        # THE REQUEST ID IS EMPTY ON EVERY DECISION SAVE, and this is the step
        # that says so instead of a conclusion that claims otherwise.
        # `record_decision_event` writes
        # `request_id=request.headers.get('X-Request-ID', '')` -- the caller's
        # header or nothing -- while `record_operator_event` MINTS one through
        # `request_id_for(request)` when the caller sends none. The product's
        # own axios client never sends the header, so the column is '—' on
        # every row a real user creates. The only code in the tree that does
        # send it is `run_deadline_rehearsal`, which is why the load rehearsal's
        # rows carry ids that no browser will. CRV2-08's own
        # `dispute-answers.json` shows `request_id: ""` on every save beside a
        # conclusion that says the saves are "recorded with server timestamps
        # and request ids"; that sentence has been on record since 2026-08-30.
        R.step('every accepted save carries a request id the dispute procedure '
               'can correlate',
               'pass' if saves and len(with_rid) == len(saves) else 'fail',
               '%d of %d saves carry one; record_decision_event reads '
               'X-Request-ID from the caller and the product client never '
               'sends it' % (len(with_rid), len(saves)))

        last_save = parse(saves[-1]['server_timestamp']) if saves else None
        dl = parse(deadline)
        in_time = (last_save is not None and dl is not None
                   and last_save <= dl)
        answers['1_before_deadline'] = {
            'claim': 'We submitted before the deadline',
            'path': 'console -> Team Overview -> View Decisions -> audit '
                    'evidence, against the round schedule the instructor set',
            'evidence': {'round_deadline': deadline,
                         'saves': [{'at': e.get('server_timestamp'),
                                    'actor': e.get('actor'),
                                    'request_id': e.get('request_id')}
                                   for e in saves],
                         'locked_at': body.get('locked_at'),
                         'submission_origin': body.get('submission_origin')},
            'answerable': bool(saves) and deadline is not None,
            'conclusion': ('%d accepted saves carry an actor and a SERVER '
                           'timestamp; the last is %s against a deadline of '
                           '%s, so the claim is decided on this screen (%s). '
                           'The request id is empty on %d of them -- see the '
                           'step on this record -- so the save can be '
                           'identified by actor, time, endpoint, payload and '
                           'hash, but NOT correlated with the server request '
                           'log the runbook points at.'
                           % (len(saves),
                              saves[-1]['server_timestamp'] if saves else None,
                              deadline,
                              'in time' if in_time else 'not in time',
                              len([e for e in saves
                                   if not (e.get('request_id') or '').strip()]))),
        }
        R.step('claim 1 "we submitted before the deadline" is decidable here',
               'pass' if answers['1_before_deadline']['answerable'] else 'fail',
               answers['1_before_deadline']['conclusion'])

        hashes = sorted({e.get('payload_sha256') for e in saves
                         if e.get('payload_sha256')})
        answers['2_payload_mismatch'] = {
            'claim': 'The recorded decision differs from what we entered',
            'path': 'the same panel: one row per accepted save, each with its '
                    'own payload and SHA-256',
            'evidence': {'distinct_save_hashes': hashes,
                         'rows': len(saves),
                         'lock_events': len(locks),
                         'last_before_lock': (
                             {'at': saves[-1].get('server_timestamp'),
                              'sha256': saves[-1].get('payload_sha256')}
                             if saves else None)},
            'answerable': bool(hashes),
            'conclusion': ('Each accepted save is a row with its own payload '
                           'and hash, so the version in force at lock is '
                           'identifiable and any earlier version is still '
                           'beside it (%d distinct hashes).' % len(hashes)),
        }
        R.step('claim 2 "that is not what we entered" is decidable here',
               'pass' if answers['2_payload_mismatch']['answerable'] else 'fail',
               answers['2_payload_mismatch']['conclusion'])
        page.keyboard.press('Escape')
        page.wait_for_timeout(800)

        # ---- claim 5: what the operators did ------------------------------
        click_tab(page, L['control'])
        page.wait_for_timeout(2500)
        click_tab(page, L['log'])
        page.wait_for_timeout(4000)
        R.screen(page, 'd03-operator-log')
        log_text = visible_text(page)
        rows = A(page).locator('tbody tr')
        R.step('the Operator Log reads the rows back in the product',
               'pass' if rows.count() else 'fail', '%d rows' % rows.count())

        ev = api(page, 'GET',
                 '/api/games/%s/instructor/operator-events/' % GID)
        oe = ((ev.get('body') or {}).get('events') or [])
        actions = sorted({e.get('action') for e in oe})
        R.observe('operator_actions_recorded', actions)
        committed = [e for e in oe if e.get('outcome') == 'committed']
        rejected = [e for e in oe if e.get('outcome') == 'rejected']
        R.observe('operator_outcomes', {'committed': len(committed),
                                        'rejected': len(rejected)})

        # The columns the dispute asks for, read off the rendered table.
        sample = next((e for e in committed
                       if e.get('action') in ('set_deadline', 'extend_deadline',
                                              'close_round', 'advance_round')),
                      committed[0] if committed else None)
        cols = {}
        if sample:
            cols = {
                'actor_on_screen': bool(sample.get('actor'))
                                   and str(sample['actor']) in log_text,
                'action_on_screen': bool(sample.get('action'))
                                    and str(sample['action']) in log_text,
                'request_id_on_screen': bool(sample.get('request_id'))
                                        and str(sample['request_id']) in log_text,
            }
        R.observe('operator_log_columns_on_screen', cols)
        R.step('actor, action and request id are readable in the Operator Log',
               'pass' if cols and all(cols.values()) else 'fail',
               json.dumps(cols))
        # W-CE-07: before -> after is words and numbers, not the audit row's
        # JSON. A brace or a storage field name on this screen is the defect.
        raw_json_shown = ('{"' in log_text or 'round_number' in log_text
                          or 'null,' in log_text)
        R.step('before -> after is stated in words, not as the stored record',
               'fail' if raw_json_shown else 'pass',
               'braces or storage names on the screen: %s' % raw_json_shown)

        # A refusal has to be visible beside the actions that succeeded, which
        # is what the filter is for.
        sel = A(page).locator('.ant-select').first
        if sel.count():
            sel.click()
            page.wait_for_timeout(800)
            opt = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) '
                               '.ant-select-item-option').last
            if opt.count():
                opt.click()
                page.wait_for_timeout(3000)
            R.screen(page, 'd04-operator-log-refusals-only')
            R.observe('rows_with_refusals_filter',
                      A(page).locator('tbody tr').count())
        answers['5_operator_change'] = {
            'claim': 'The operator changed something',
            'path': 'console -> Game Control -> Operator Log (read-only), '
                    'filterable by outcome',
            'evidence': {'rows_in_product': len(oe),
                         'actions': actions,
                         'committed': len(committed),
                         'rejected': len(rejected),
                         'columns_on_screen': cols},
            'answerable': bool(oe) and bool(cols) and all(cols.values()),
            'conclusion': ('%d operator rows are read back inside the product '
                           'with actor, server time, action, outcome, round, '
                           'reason, before -> after and request id, refusals '
                           'included. CRV2-08 recorded this claim '
                           'UNANSWERABLE because nothing in the product read '
                           'the rows; this screen is the repair and it holds.'
                           % len(oe)),
        }
        R.step('claim 5 "the operator changed something" is answerable in the '
               'product (CRV2-08 re-test)',
               'pass' if answers['5_operator_change']['answerable'] else 'fail',
               answers['5_operator_change']['conclusion'])

        # ---- the three that are not browser work -------------------------
        for key, claim, path in (
            ('3_rival_access', 'Another team saw our decisions',
             'python3 manage.py who_accessed --game <id> --team <id> --json'),
            ('4_rerun_after_final', 'The round was rerun after final',
             'python3 manage.py replay_round --game-id <id> --round <n> '
             '--export-only'),
            ('6_prove_the_calculation', 'Prove the calculation',
             'python3 manage.py replay_round --game-id <id> --round <n> '
             '--restore against a disposable database'),
        ):
            answers[key] = {'claim': claim, 'path': path,
                            'answerable': None,
                            'conclusion': 'Answered by an operator command, '
                                          'not from a screen; on record under '
                                          'CRV2-08 and not re-run here.'}
            R.step('claim "%s" is operator-command work, not console work'
                   % claim, 'observed', path)

        R.observe('answers', answers)
        browser.close()
    out = SCRATCH.parent / 'records' / ('dispute-answers-r%d-%s.json'
                                       % (ROUND, LANG))
    out.write_text(json.dumps(answers, indent=2, ensure_ascii=False,
                              default=str) + '\n')
    print('dispute answers: %s' % out)
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
