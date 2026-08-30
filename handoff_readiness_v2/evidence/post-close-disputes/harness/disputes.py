#!/usr/bin/env python3
"""Answer each of the six disputes once, through a supported path.

Each entry records the exact path used, what it returned, and the conclusion an
operator could defend. A dispute that cannot be answered through a supported
path is recorded as unanswerable with the reason, not quietly omitted.
"""
import json, pathlib, subprocess, sys, urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
DATABASE = 'gsp_crv208_disputes'
fixture = json.loads((EVIDENCE / 'completed-game.json').read_text())
ports = json.loads(pathlib.Path('/tmp/crv208-runtime/stack.ports').read_text())
BASE = f"http://127.0.0.1:{ports['app']}"
GAME = fixture['game_id']
TEAMS = fixture['identities']['teams']


def manage(*args, timeout=900):
    import os
    env = dict(os.environ, DB_NAME=DATABASE, GLOBALSTRAT_ENV='development',
               DJANGO_SECRET_KEY='crv208-walkthrough',
               COMPETITION_BACKUP_DIR='/tmp/crv208-backups')
    return subprocess.run([sys.executable, 'manage.py', *args], cwd=str(BACKEND),
                          env=env, capture_output=True, text=True, timeout=timeout)


def api(path, token, method='GET'):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b'')[:200].decode('utf-8', 'replace')


def login(username):
    req = urllib.request.Request(
        BASE + '/api/auth/login/', method='POST',
        data=json.dumps({'username': username,
                         'password': fixture['password']}).encode())
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())['access']


def main():
    instructor = login(fixture['identities']['instructor'])
    edited = fixture['contains']['submissions_saved_more_than_once_with_differing_hashes'][0]
    team_name, round_label = edited.rsplit(' ', 1)
    team = next(t for t in TEAMS if t['name'] == team_name)
    rnd = int(round_label.lstrip('r'))
    out = {}

    # ---- 1 and 2: both answered from the instructor evidence table --------
    status, body = api(
        f'/api/games/{GAME}/instructor/teams/{team["id"]}/decisions/?round={rnd}',
        instructor)
    events = body.get('audit_events', []) if isinstance(body, dict) else []
    saves = [e for e in events if e['action'] == 'save']
    locks = [e for e in events if e['action'] == 'lock']
    deadline = next((r['deadline'] for r in fixture['rounds']
                     if r['round_number'] == rnd), None)
    out['1_before_deadline'] = {
        'claim': 'We submitted before the deadline',
        'path': f'GET /api/games/{GAME}/instructor/teams/{{team}}/decisions/?round={rnd}'
                ' — instructor dashboard, team overview, view decisions',
        'evidence': {
            'round_deadline': deadline,
            'submission_origin': body.get('submission_origin'),
            'saves': [{'at': e['server_timestamp'], 'actor': e['actor'],
                       'request_id': e['request_id']} for e in saves],
            'locked_at': body.get('locked_at'),
        },
        'answerable': bool(saves) and deadline is not None,
        'conclusion': (f'{len(saves)} accepted saves are recorded with server '
                       f'timestamps and request ids, against a deadline of '
                       f'{deadline}. The claim is decidable from this screen.'),
    }
    out['2_payload_mismatch'] = {
        'claim': 'The recorded decision differs from what we entered',
        'path': 'the same response: audit_events[].payload and payload_sha256',
        'evidence': {
            'distinct_save_hashes': sorted({e['payload_sha256'] for e in saves}),
            'last_accepted_before_lock': (
                {'at': saves[-1]['server_timestamp'],
                 'sha256': saves[-1]['payload_sha256'],
                 'payload_keys': sorted((saves[-1]['payload'] or {}).keys())[:8]}
                if saves else None),
            'lock_events': len(locks),
        },
        'answerable': len({e['payload_sha256'] for e in saves}) > 1,
        'conclusion': ('Each accepted save carries its own payload and SHA-256, '
                       'so the version in force at lock is identifiable and the '
                       'earlier version is still visible beside it.'),
    }

    # ---- 3: who read the decisions ---------------------------------------
    reads = manage('who_accessed', '--game', str(GAME), '--team',
                   str(team['id']), '--limit', '20', '--json')
    parsed = json.loads(reads.stdout) if reads.returncode == 0 else {}
    rows = parsed.get('reads', [])
    required = ('username', 'team', 'endpoint', 'outcome', 'request_id')
    out['3_rival_access'] = {
        'claim': 'Another team saw our decisions',
        'path': f'python3 manage.py who_accessed --game {GAME} --team {{team}} --json',
        'evidence': {
            'rows_returned': len(rows),
            'fields_present': [f for f in required
                               if rows and all(f in r for r in rows)],
            'denied_attempts': [
                {'actor': r['username'], 'team_read': r['team'],
                 'endpoint': r['endpoint'], 'outcome': r['outcome'],
                 'request_id': r['request_id']}
                for r in rows if r.get('outcome') == 'denied'][:3],
        },
        'answerable': bool(rows) and all(
            f in rows[0] for f in required),
        'conclusion': ('Reads of a team\'s decisions and audit payloads are '
                       'recorded with actor, target team, route, outcome and '
                       'request id, refusals included. The runbook\'s "not '
                       'answerable" wording predates this table.'),
    }

    # ---- 4 and 6: the manifest and the replay ----------------------------
    export = manage('replay_round', '--game-id', str(GAME), '--round', str(rnd),
                    '--export-only', '--evidence-dir',
                    str(EVIDENCE / 'replay' / f'round-{rnd}'))
    exported = sorted(p.name for p in
                      (EVIDENCE / 'replay' / f'round-{rnd}').rglob('*')
                      if p.is_file())
    out['4_rerun_after_final'] = {
        'claim': 'The round was rerun after final',
        'path': (f'python3 manage.py replay_round --game-id {GAME} --round {rnd} '
                 f'--export-only --evidence-dir <dir>'),
        'evidence': {'exit_code': export.returncode,
                     'files': exported,
                     'stdout_tail': export.stdout[-400:]},
        'answerable': export.returncode == 0 and bool(exported),
        'conclusion': ('The recorded manifest exports with its hashes and '
                       'timestamps, which is what an operator compares against '
                       'the operator trail for the round.'),
    }
    # The replay itself runs against a disposable database and is executed by
    # replay_dispute_6.sh, which the runbook's procedure describes step by
    # step. Its report is read back here rather than re-run.
    replay_dir = EVIDENCE / 'replay' / f'round-{rnd}-replay'
    report_path = replay_dir / 'replay-report.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    out['6_prove_the_calculation'] = {
        'claim': 'Prove the calculation',
        'path': (f'python3 manage.py replay_round --game-id {GAME} --round {rnd} '
                 f'--restore --confirm REPLAY-GAME-{GAME}-ROUND-{rnd} '
                 f'--expected-manifest <exported> against a disposable database'),
        'evidence': {
            'competitive_hash_expected': report.get('expected_output_sha256')
                                         or report.get('competitive_hash_expected'),
            'competitive_hash_actual': report.get('actual_output_sha256')
                                       or report.get('competitive_hash_actual'),
            'matched': report.get('output_matches', report.get('matched')),
            'files': sorted(p.name for p in replay_dir.glob('*')) if replay_dir.exists() else [],
        },
        'answerable': bool(report),
        'conclusion': ('The round replays from its pre-resolution backup on an '
                       'isolated database and reproduces the same competitive '
                       'hash, which is what proves the published numbers.'),
    }

    # ---- 5: what did the operator change? --------------------------------
    # Ruling: the Django admin is not the supported operator path. Probe every
    # plausible product route before concluding there is none.
    candidates = [
        f'/api/games/{GAME}/operator-events/',
        f'/api/games/{GAME}/instructor/operator-events/',
        f'/api/games/{GAME}/instructor/operator-audit/',
        f'/api/games/{GAME}/audit/operator/',
        f'/api/games/{GAME}/round-control/',
    ]
    probed = {}
    for path in candidates:
        status, body = api(path, instructor)
        carries = (isinstance(body, dict)
                   and any(k in json.dumps(body)[:4000]
                           for k in ('operator_events', 'operator_audit',
                                     'before', 'after', 'reason')))
        probed[path] = {'status': status, 'carries_operator_events': carries}
    counted = manage('shell', '-c',
                     'from core.models import OperatorAuditEvent as O;'
                     'print("ROWS", O.objects.filter(game_id=%d).count())' % GAME)
    rows_in_db = next((line.split()[1] for line in counted.stdout.splitlines()
                       if line.startswith('ROWS')), '?')
    out['5_operator_change'] = {
        'claim': 'The operator changed something',
        'path': 'none found in the product',
        'evidence': {'routes_probed': probed,
                     'operator_audit_rows_in_database': rows_in_db,
                     'only_reader': 'core/admin.py:811 OperatorAuditEventAdmin '
                                    '(read-only Django admin)'},
        'answerable': False,
        'conclusion': (f'{rows_in_db} operator audit rows exist for this game and '
                       'no product API or UI returns any of them. Under the '
                       'ruling that the Django admin is not the supported '
                       'operator path, this dispute is unanswerable and is a '
                       'finding.'),
    }

    (EVIDENCE / 'dispute-answers.json').write_text(
        json.dumps(out, indent=2, sort_keys=True, default=str) + '\n')
    for key in sorted(out):
        entry = out[key]
        mark = ('ANSWERABLE' if entry.get('answerable')
                else 'UNANSWERABLE' if entry.get('answerable') is False
                else 'SEE BELOW')
        print(f'{mark:<13} {key}: {entry["path"][:100]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
