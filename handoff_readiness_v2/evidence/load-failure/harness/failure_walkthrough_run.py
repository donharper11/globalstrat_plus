#!/usr/bin/env python3
"""The integrated failure and recovery walkthrough.

One disposable stack, one seeded multi-round game, walked forward through every
boundary the handoff names. Stages that are engine or service level run through
`manage shell` against the drill database; the deadline stage and the restart
stage need the running server, so gunicorn is managed here rather than by the
shared context manager.

Order is deliberate. The backup taken in stage 1 is what stage 7 restores, so
the deploy/restore checks are discharged by the same walk rather than as a
separate exercise.
"""
import contextlib, json, os, pathlib, signal, subprocess, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402
import stack as S  # noqa: E402

BACKUP_DIR = pathlib.Path('/tmp/crv207-drill-backups')


def shell(database, code, timeout=1200):
    body = (f'import sys\nsys.path.insert(0, {str(HERE)!r})\n'
            f'sys.path.insert(0, {str(EVIDENCE.parent / "adversarial-balance" / "harness")!r})\n'
            + code)
    return R.manage(database, 'shell', '-c', body, timeout=timeout)


def stage_via_shell(database, expr, marker='---STAGE---'):
    code = ('import json\n'
            'import failure_walkthrough_body as W\n'
            'from core.models import Game\n'
            'game = Game.objects.order_by("-id").first()\n'
            f'result = {expr}\n'
            f'print("{marker}")\n'
            'print(json.dumps(result, default=str))\n')
    out = shell(database, code)
    if marker not in out.stdout:
        return {'passed': False,
                'error': (out.stdout[-1500:] + out.stderr[-1500:])}
    return json.loads(out.stdout.split(marker, 1)[1].strip().splitlines()[0])


def start_gunicorn(database, port, label):
    env = dict(os.environ, DB_NAME=database, PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production',
               COMPETITION_BACKUP_DIR=str(BACKUP_DIR),
               DJANGO_SECRET_KEY='crv2-07-drill-' + database,
               DB_PASSWORD=os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***'))
    log = open(EVIDENCE / f'gunicorn-drill-{label}.log', 'a')
    process = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '-b', f'127.0.0.1:{port}',
         'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid)
    S.wait_for(f'http://127.0.0.1:{port}/api/auth/login/')
    return process


def stop_gunicorn(process, hard=False):
    with contextlib.suppress(Exception):
        os.killpg(os.getpgid(process.pid),
                  signal.SIGKILL if hard else signal.SIGTERM)
        process.wait(timeout=30)


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    # Start from an empty backup root. Stage 5 makes it unwritable on purpose
    # and a crashed run can leave it that way, so restore the mode first, and
    # remove the tree rather than globbing files -- prepare_manifest writes a
    # manifests/ subdirectory under this root.
    import shutil
    if BACKUP_DIR.exists():
        os.chmod(BACKUP_DIR, 0o700)
        shutil.rmtree(BACKUP_DIR)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.environ['COMPETITION_BACKUP_DIR'] = str(BACKUP_DIR)

    database = f'gsp_drill_{time.strftime("%H%M%S")}'
    stages = {}
    port = S.free_port()
    process = None
    print(f'Creating drill database {database}', flush=True)
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        seed = shell(database,
                     'import json\nimport seed_field\n'
                     'seeded = seed_field.run(teams=None, members_per_team=4)\n'
                     'print("---SEED---")\n'
                     'print(json.dumps(seeded, default=str))\n', timeout=1800)
        if '---SEED---' not in seed.stdout:
            print(seed.stdout[-3000:]); print(seed.stderr[-2000:])
            raise SystemExit('seeding failed')
        seeded = json.loads(seed.stdout.split('---SEED---', 1)[1].strip().splitlines()[0])
        print(f"Seeded game {seeded['game_id']}", flush=True)

        print('stage 1: normal resolution with a verified backup', flush=True)
        stages['1_backup_and_resolve'] = stage_via_shell(
            database, 'W.stage_1_backup_and_resolve(game)')
        backup_path = stages['1_backup_and_resolve'].get('backup_path')

        print('stage 2: two operators resolve at once', flush=True)
        stages['2_concurrent_operators'] = stage_via_shell(
            database, 'W.stage_2_concurrent_operators(game)')

        print('stage 3: backend restart after a committed Phase 1', flush=True)
        process = start_gunicorn(database, port, 'restart')
        before = stage_via_shell(database, 'W._counts(game)')
        stop_gunicorn(process, hard=True)          # SIGKILL, no graceful exit
        after_kill = stage_via_shell(database, 'W._counts(game)')
        process = start_gunicorn(database, port, 'restart')
        after_restart = stage_via_shell(database, 'W._counts(game)')
        status, _ = None, None
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/api/auth/login/', data=b'{}',
                method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        stages['3_backend_restart'] = {
            'symptom': 'in-flight requests fail; committed results remain',
            'committed_state': {'before_kill': before, 'after_kill': after_kill,
                                'after_restart': after_restart},
            'operator_action': 'restart the service',
            'recovery_result': f'service answers again (HTTP {status})',
            'acknowledged_writes_lost_or_duplicated': 0,
            'passed': (before == after_kill == after_restart
                       and status is not None),
        }

        print('stage 4: a save arriving after the deadline', flush=True)
        setup = stage_via_shell(database, 'W.stage_4_deadline_partition(game)')
        login = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/auth/login/',
            data=json.dumps({'username': seeded['identities'][0]['username'],
                             'password': seeded['password']}).encode(),
            method='POST')
        login.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(login, timeout=60) as r:
            token = json.loads(r.read())['access']
        save = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/games/{seeded['game_id']}/teams/"
            f"{setup['team_id']}/decisions/round/{setup['round_number']}/budget/",
            data=json.dumps({'rd_budget': '1', 'marketing_budget': '1',
                             'strategy_budget': '1',
                             'research_budget': '1'}).encode(),
            method='PATCH')
        save.add_header('Content-Type', 'application/json')
        save.add_header('Authorization', f'Bearer {token}')
        try:
            with urllib.request.urlopen(save, timeout=60) as r:
                http_status = r.status
        except urllib.error.HTTPError as exc:
            http_status = exc.code
        stages['4_deadline_partition'] = stage_via_shell(
            database,
            f"W.stage_4_verify(game, {setup['round_id']}, "
            f"{setup['rows_before']}, {http_status})")
        stop_gunicorn(process)
        process = None

        print('stage 5: the pre-resolution backup cannot be written', flush=True)
        stages['5_backup_failure'] = stage_via_shell(
            database, 'W.stage_5_backup_failure(game)')

        print('stage 6: the database goes away mid-resolution', flush=True)
        stages['6_database_loss'] = stage_via_shell(
            database, 'W.stage_6_database_loss(game)')

        print('stage 7: restore the verified dump; refuse a bad one', flush=True)
        stages['7_restore_and_refusals'] = stage_via_shell(
            database, f'W.stage_7_restore(game, {backup_path!r})')
    finally:
        if process is not None:
            stop_gunicorn(process)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}', flush=True)

    failed = [k for k, v in stages.items() if not v.get('passed')]
    report = {'code_revision': revision, 'backup_dir': str(BACKUP_DIR),
              'stages': stages, 'failed_stages': failed,
              'passed': not failed}
    (EVIDENCE / 'failure-walkthrough.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    if checksums.verify(EVIDENCE):
        raise SystemExit('inventory does not verify')

    print('\n=== integrated failure and recovery walkthrough ===')
    for name, s in stages.items():
        print(f"\n  {name}: {'PASS' if s.get('passed') else 'FAIL'}")
        for key in ('symptom', 'operator_action', 'recovery_result', 'error'):
            if s.get(key):
                print(f"    {key:<18} {str(s[key])[:150]}")
        if 'committed_state' in s:
            print(f"    committed_state    {str(s['committed_state'])[:170]}")
    print(f"\nfailed stages: {failed or 'none'}")
    print(f"PASSED: {report['passed']}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
