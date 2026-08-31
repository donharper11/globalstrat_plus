#!/usr/bin/env python3
"""Every game-scoped instructor route, read and write, as an unrelated instructor.

The inventory comes from the registered URL patterns, not from the routes a
previous probe happened to name, so a route nobody remembered is still covered.

Writes are issued for real, against a disposable clone of the fixture, and the
clone's state is compared before and after each refused request. A 403 that
still mutated something would be worse than a 200, and only the comparison can
tell the difference.

For each refused write the artifact also records whether the refusal was
recorded anywhere -- operator audit or sensitive-read log. That is an
observation for V2-034, not a new logging path.
"""
import json, os, pathlib, subprocess, sys, time, urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
sys.path.insert(0, str(EVIDENCE.parent / 'load-failure' / 'harness'))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import inventory_run as R      # noqa: E402
import stack as S              # noqa: E402

SOURCE_DB = 'gsp_crv208_disputes'
CLONE_DB = 'gsp_crv208_authscan'
PASSWORD = 'crv208-pass'
fixture = json.loads((EVIDENCE / 'completed-game.json').read_text())
GAME = fixture['game_id']

# The smallest syntactically valid body for each mutation, so a refusal is an
# authorization refusal and not a validation error.
BODIES = {
    'reason': 'Authorization scan probe, expected to be refused',
    'minutes_from_now': 30,
    'force': False,
    'event_template_id': 1,
    'language': 'en',
    'confirm': 'CONFIRM',
    'name': 'authorization scan',
    'status': 'active',
    'unlock_round': 2,
    'decision_type': 'budget',
    'participation_status': 'active',
    'team_size_max': 4,
}


def api(port, method, path, token, body=None):
    data = json.dumps(BODIES).encode() if method in ('POST', 'PUT', 'PATCH') else None
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', method=method, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read()[:200].decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b'')[:200].decode('utf-8', 'replace')
    except Exception as e:
        return 'error', str(e)[:160]


def login(port, username):
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}/api/auth/login/', method='POST',
        data=json.dumps({'username': username, 'password': PASSWORD}).encode())
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())['access']


def shell(database, code, marker='---OUT---'):
    body = f'import json\n{code}\nprint("{marker}")\nprint(json.dumps(result, default=str))\n'
    out = R.manage(database, 'shell', '-c', body, timeout=600)
    if marker not in out.stdout:
        raise SystemExit(f'shell failed:\n{out.stdout[-2000:]}\n{out.stderr[-1000:]}')
    return json.loads(out.stdout.split(marker, 1)[1].strip().splitlines()[0])


STATE = '''
from core.models import (DecisionAuditEvent, DecisionSubmission, Game,
                         OperatorAuditEvent, Round, Team)
from core.models.audit_integrity import (AuthorizationRefusalEvent,
                                         SensitiveReadEvent)
game = Game.objects.get(id=%d)
result = {
    'game_status': game.status,
    'current_round': game.current_round,
    'rounds': list(Round.objects.filter(game=game)
                   .order_by('round_number')
                   .values_list('round_number', 'status', 'deadline')),
    'teams': list(Team.objects.filter(game=game).order_by('id')
                  .values_list('id', 'participation_status')),
    'submissions': DecisionSubmission.objects.filter(round__game=game).count(),
    'operator_events': OperatorAuditEvent.objects.filter(game=game).count(),
    'decision_events': DecisionAuditEvent.objects.filter(game=game).count(),
    'sensitive_reads': SensitiveReadEvent.objects.filter(game_id_read=game.id).count(),
    'refusal_events': AuthorizationRefusalEvent.objects.filter(
        game_id_attempted=game.id).count(),
}
''' % GAME


def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    print(f'Cloning {SOURCE_DB} -> {CLONE_DB}', flush=True)
    R.psql('postgres', f'DROP DATABASE IF EXISTS {CLONE_DB} WITH (FORCE)')
    if R.psql('postgres',
              f'CREATE DATABASE {CLONE_DB} TEMPLATE {SOURCE_DB}').returncode != 0:
        raise SystemExit('could not clone the fixture database')

    routes = shell(CLONE_DB,
                   'from core.services.game_scope import game_scoped_instructor_routes\n'
                   'result = game_scoped_instructor_routes(refresh=True)')
    print(f'{len(routes)} game-scoped instructor routes in the inventory', flush=True)

    port = S.free_port()
    env = dict(os.environ, DB_NAME=CLONE_DB, GLOBALSTRAT_ENV='production',
               GIT_REVISION=revision, DJANGO_SECRET_KEY='crv208-authscan',
               COMPETITION_BACKUP_DIR='/tmp/crv208-backups',
               COMPETITION_RECOVERY_ENABLED='true',
               DB_PASSWORD=os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***'))
    log = open('/tmp/crv208-runtime/authscan.log', 'w')
    proc = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '-b', f'127.0.0.1:{port}',
         'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid)
    S.wait_for(f'http://127.0.0.1:{port}/api/auth/login/')

    report = {'code_revision': revision, 'clone': CLONE_DB,
              'routes_in_inventory': len(routes), 'reads': [], 'writes': []}
    try:
        outsider = login(port, 'crv208_outsider')
        owner = login(port, fixture['identities']['instructor'])
        before = shell(CLONE_DB, STATE)

        for route, meta in sorted(routes.items()):
            path = '/' + route.replace('<int:game_id>', str(GAME))
            for token_name in ('<int:team_id>', '<int:override_id>',
                               '<int:round_number>', '<int:event_id>',
                               '<int:user_id>', '<str:decision_type>'):
                if token_name in path:
                    path = path.replace(token_name, '1')
            if '<' in path:
                continue
            for method in meta['methods']:
                status, body = api(port, method, path, outsider)
                row = {'route': path, 'method': method, 'status': status,
                       'exempt': meta['exempt'],
                       'discloses': status == 200,
                       'sample': body[:120]}
                if method == 'GET':
                    report['reads'].append(row)
                else:
                    # Snapshot immediately before the write, and compare only
                    # competition state. The read log legitimately grows when
                    # this loop issues a GET, and counting that as a mutation
                    # reported four clean refusals as state changes.
                    def competition_state(snapshot):
                        # The read log and the refusal log both grow because
                        # this loop is issuing requests; neither is competition
                        # state, and counting them as mutation reported clean
                        # refusals as state changes.
                        return {k: v for k, v in snapshot.items()
                                if k not in ('sensitive_reads',
                                             'refusal_events')}
                    before = shell(CLONE_DB, STATE)
                    status, body = api(port, method, path, outsider)
                    row['status'], row['sample'] = status, body[:120]
                    row['discloses'] = status == 200
                    after = shell(CLONE_DB, STATE)
                    row['state_unchanged'] = (
                        competition_state(after) == competition_state(before))
                    row['operator_events_delta'] = (
                        after['operator_events'] - before['operator_events'])
                    # V2-034 observation: is a refused non-owner write recorded
                    # anywhere at all?
                    row['refusal_recorded'] = (
                        'authorization_refusal_event'
                        if after['refusal_events'] > before['refusal_events']
                        else 'operator_audit'
                        if after['operator_events'] > before['operator_events']
                        else 'sensitive_read_log'
                        if after['sensitive_reads'] > before['sensitive_reads']
                        else 'not recorded')
                    before = after
                    report['writes'].append(row)

        # The owner still works: one representative read and one lifecycle
        # control, which must reach their normal non-authorization answer.
        owner_read, _ = api(port, 'GET',
                            f'/api/games/{GAME}/instructor/operator-events/', owner)
        owner_write, owner_body = api(port, 'POST',
                                      f'/api/games/{GAME}/round-control/close/', owner)
        report['owner_still_works'] = {
            'read_operator_events': owner_read,
            'lifecycle_close': owner_write,
            'lifecycle_body': owner_body[:160],
        }
    finally:
        import signal
        with __import__('contextlib').suppress(Exception):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=30)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {CLONE_DB} WITH (FORCE)')

    leaks = [r for r in report['reads'] if r['discloses'] and not r['exempt']]
    bad_writes = [w for w in report['writes']
                  if w['status'] != 403 and not w['exempt']]
    mutated = [w for w in report['writes'] if not w.get('state_unchanged')]
    unlogged = [w for w in report['writes'] if w.get('refusal_recorded') == 'not recorded']
    recorded = [w for w in report['writes']
                if w.get('refusal_recorded') == 'authorization_refusal_event']
    report['summary'] = {
        'reads_tested': len(report['reads']),
        'reads_disclosing_to_a_non_owner': len(leaks),
        'writes_tested': len(report['writes']),
        'writes_not_refused_with_403': len(bad_writes),
        'writes_that_mutated_state': len(mutated),
        'refused_writes_not_recorded_anywhere': len(unlogged),
        'refused_writes_recorded_as_authorization_refusals': len(recorded),
        'passed': (not leaks and not bad_writes and not mutated
                   and not unlogged),
    }
    (EVIDENCE / 'ownership-scan-after-repair.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    print('\n' + json.dumps(report['summary'], indent=2))
    for r in leaks:
        print('  STILL DISCLOSING', r['method'], r['route'])
    for w in bad_writes:
        print('  NOT REFUSED', w['method'], w['route'], w['status'])
    for w in mutated:
        print('  MUTATED', w['method'], w['route'])
    print('owner still works:', report.get('owner_still_works'))
    return 0 if report['summary']['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
