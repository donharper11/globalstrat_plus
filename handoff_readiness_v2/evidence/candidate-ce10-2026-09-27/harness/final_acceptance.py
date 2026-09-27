"""Produce the machine-readable acceptance ledger for the candidate run."""
import json
import pathlib

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = SCRATCH.parent
RECORDS = EVIDENCE / 'records'
game = json.loads((SCRATCH / 'game.json').read_text())
checks = {}
details = {}

checks['exactly_four_teams'] = len(game.get('teams') or []) == 4

round_ledgers = []
for round_number in range(1, 10):
    path = RECORDS / ('acceptance-round%d.json' % round_number)
    row = json.loads(path.read_text()) if path.exists() else {}
    round_ledgers.append(row)
checks['rounds_1_to_9_passed_without_repair'] = (
    len(round_ledgers) == 9
    and all(row and all(row.get('checks', {}).values()) for row in round_ledgers))

accounting = []
reasoning = []
for round_number in range(1, 11):
    account_path = RECORDS / ('check-round%d.json' % round_number)
    reason_path = RECORDS / ('reasoning-round%d.json' % round_number)
    account = json.loads(account_path.read_text()) if account_path.exists() else {}
    reason = json.loads(reason_path.read_text()) if reason_path.exists() else {}
    accounting.append(account)
    reasoning.append(reason)
checks['all_ten_round_accounting_ledgers_exist'] = all(accounting)
checks['all_ten_round_accounting_checks_pass'] = all(
    all(row.get('outcome') == 'pass' for row in account.get('checks', []))
    and bool(account.get('checks')) for account in accounting)
checks['all_ten_round_reasoning_ledgers_exist'] = all(reasoning)
checks['all_ten_round_reasoning_checks_pass'] = all(
    all(row.get('outcome') == 'pass' for row in reason.get('checks', []))
    and bool(reason.get('checks')) for reason in reasoning)

residuals = []
carry = []
for account in accounting:
    for row in account.get('reconciliation', {}).values():
        residuals.extend(abs(float(row.get(key) or 0)) for key in (
            'identity_residual', 'gross_profit_residual',
            'operating_income_residual', 'net_income_residual',
            'page_income_statement_gap'))
        if 'cash_carried_between_rounds' in row:
            carry.append(abs(float(row['cash_carried_between_rounds'])))
details['max_accounting_residual'] = max(residuals or [0])
details['max_cash_carry_difference'] = max(carry or [0])
checks['cash_and_accounting_continuity'] = (
    details['max_accounting_residual'] < 0.02
    and details['max_cash_carry_difference'] < 0.02)

langs = {1: 'en', 2: 'en', 3: 'zh-CN', 4: 'en'}
policies = []
for team_index in range(1, 5):
    record = RECORDS / ('student-play-t%d-r1-%s.json'
                        % (team_index, langs[team_index]))
    body = json.loads(record.read_text())
    policies.append(body.get('observed', {}).get('policy'))
details['round1_policies'] = policies
checks['four_declared_strategies_are_distinct'] = (
    len(policies) == 4 and len({json.dumps(p, sort_keys=True) for p in policies}) == 4)

finish_path = RECORDS / 'finish-game-r10-en.json'
finish = json.loads(finish_path.read_text()) if finish_path.exists() else {}
finish_steps = {row.get('name'): row.get('outcome') for row in finish.get('steps', [])}
checks['round10_processed'] = finish_steps.get('round 10 processed') == 'pass'
checks['game_finished_through_console'] = finish_steps.get('the game reports itself finished') == 'pass'
checks['endgame_artifacts_remain_readable'] = all(
    outcome == 'pass' for name, outcome in finish_steps.items()
    if 'still readable after the game is finished' in name)

forbidden = []
process_refusals = []
for path in RECORDS.glob('*.json'):
    try:
        body = json.loads(path.read_text())
    except Exception:
        continue
    for row in body.get('api', []) if isinstance(body, dict) else []:
        url = row.get('url', '')
        method = row.get('method') or row.get('m')
        if method in ('POST', 'PUT', 'PATCH') and any(
                marker in url for marker in ('/reopen/', '/force-close/', '/recover/')):
            forbidden.append({'record': path.name, 'method': method, 'url': url})
        status = row.get('status', row.get('s'))
        if 'round-control/process' in url and isinstance(status, int) and status >= 400:
            process_refusals.append({'record': path.name, 'status': status, 'url': url})
details['forbidden_recovery_calls'] = forbidden
details['processing_refusals'] = process_refusals
checks['zero_reopen_force_or_recovery_calls'] = not forbidden
checks['zero_processing_refusals'] = not process_refusals

browser_records = [
    'student-tour-t1-final-en.json', 'student-tour-t3-final-zh-CN.json',
    'instructor-tour-final-en-en.json', 'instructor-tour-final-zh-zh-CN.json',
    'verify-briefing-t1-m4-en.json', 'verify-briefing-t3-m2-zh-CN.json',
    'fresh-browser-s2609-zh-CN.json', 'fresh-browser-walk_instructor-zh-CN.json',
]
missing = [name for name in browser_records if not (RECORDS / name).exists()]
details['missing_browser_records'] = missing
checks['bilingual_student_and_instructor_browser_evidence'] = not missing
screenshots = list((EVIDENCE / 'screenshots').glob('*.jpg'))
details['screenshot_count'] = len(screenshots)
checks['screenshots_captured'] = bool(screenshots)

token = login(game.get('instructor', 'walk_instructor'))
status, control = call('GET', '/api/games/%d/round-control/' % game['game_id'],
                       token=token)
details['final_round_control'] = control
checks['final_api_reports_completed_game'] = (
    status == 200 and (control or {}).get('game_status') in ('completed', 'finished', 'ended'))

out = {'candidate_commit': '49b547fd30c954c44049b1f34e79e5e3a0d5dd3e',
       'checks': checks, 'details': details}
path = EVIDENCE / 'ACCEPTANCE.json'
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
for name, ok in checks.items():
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
print('record:', path)
raise SystemExit(0 if all(checks.values()) else 1)
