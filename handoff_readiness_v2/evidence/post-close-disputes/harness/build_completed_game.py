#!/usr/bin/env python3
"""Build the one reusable completed game CRV2-08 walks through.

Everything a dispute has to be answered from is written the way the product
writes it: student saves go through the decision endpoints, locks through the
lock endpoint, and every lifecycle action through round-control. Seeding the
same rows with the ORM would produce an audit trail that exists only because
this script wrote it, which is no evidence at all that the product records
anything.

The database is kept, not dropped. The walkthrough reuses it, and so may
CRV2-09.

Seeded into it, as the handoff requires: a normal submission, a saved edit, a
late save refused at the deadline, operator actions, and a team that never
submits so a default/empty state is real rather than contrived.
"""
import json, os, pathlib, subprocess, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
LOAD_HARNESS = EVIDENCE.parent / 'load-failure' / 'harness'
sys.path.insert(0, str(LOAD_HARNESS))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import inventory_run as R          # noqa: E402
import stack as S                  # noqa: E402
import failure_walkthrough_run as W  # noqa: E402

DATABASE = 'gsp_crv208_disputes'
PASSWORD = 'crv208-pass'
BACKUPS = pathlib.Path('/tmp/crv208-backups')
FIXTURE = EVIDENCE / 'completed-game.json'


def api(port, method, path, token=None, body=None):
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}{path}', method=method,
        data=None if body is None else json.dumps(body).encode())
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() or b'')[:300].decode('utf-8', 'replace')


def shell(code, marker):
    body = (f'import sys\nsys.path.insert(0, {str(HERE)!r})\n'
            f'sys.path.insert(0, {str(LOAD_HARNESS)!r})\n'
            f'sys.path.insert(0, {str(EVIDENCE.parent / "adversarial-balance" / "harness")!r})\n'
            'import json\nimport seed_bodies as B\n'
            'from core.models import Game\n'
            'game = Game.objects.order_by("-id").first()\n'
            f'result = {code}\n'
            f'print("{marker}")\nprint(json.dumps(result, default=str))\n')
    out = R.manage(DATABASE, 'shell', '-c', body, timeout=1200)
    if marker not in out.stdout:
        raise SystemExit(f'{code} failed:\n{out.stdout[-2500:]}\n{out.stderr[-1500:]}')
    return json.loads(out.stdout.split(marker, 1)[1].strip().splitlines()[0])


def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    BACKUPS.mkdir(parents=True, exist_ok=True)
    os.environ['COMPETITION_BACKUP_DIR'] = str(BACKUPS)
    # The stack runs GLOBALSTRAT_ENV=production, which refuses to resolve a
    # round without an auditable build revision. That refusal is correct; the
    # seeder just has to say which revision it is running.
    os.environ['GIT_REVISION'] = revision

    print(f'Rebuilding {DATABASE}', flush=True)
    R.psql('postgres', f'DROP DATABASE IF EXISTS {DATABASE} WITH (FORCE)')
    if R.psql('postgres', f'CREATE DATABASE {DATABASE}').returncode != 0:
        raise SystemExit('could not create the database')
    R.manage(DATABASE, 'migrate', '--noinput')
    R.manage(DATABASE, 'shell', '-c', R.LEGACY_TABLES)

    seeded = shell(f'B.seed_identities(game, {PASSWORD!r})', '---SEED---')
    print(f"game {seeded['game_id']}, teams {[t['name'] for t in seeded['teams']]}",
          flush=True)

    port = S.free_port()
    W.BACKUP_DIR = BACKUPS
    process = W.start_gunicorn(DATABASE, port, 'crv208')
    record = {'code_revision': revision, 'database': DATABASE, 'port': port,
              'password': PASSWORD, 'rounds': []}
    try:
        _, tok = api(port, 'POST', '/api/auth/login/',
                     body={'username': seeded['instructor'],
                           'password': PASSWORD})
        instructor = tok['access']
        students = {}
        for team in seeded['teams']:
            _, t = api(port, 'POST', '/api/auth/login/',
                       body={'username': team['student'], 'password': PASSWORD})
            students[team['id']] = t['access']

        team_a, team_b, team_c = seeded['teams']
        for round_number in (1, 2, 3):
            events = {'round': round_number, 'actions': []}

            def note(what, status, detail=''):
                events['actions'].append(
                    {'what': what, 'status': status, 'detail': str(detail)[:400]})
                print(f'  r{round_number} {what}: {status} '
                      f'{str(detail)[:300] if status >= 300 else ""}', flush=True)

            # An operator sets the deadline through the supported control, so
            # an OperatorAuditEvent exists for dispute 5 to be asked about.
            code, body = api(port, 'POST', f'/api/games/{seeded["game_id"]}/round-control/deadline/',
                             instructor, {'minutes_from_now': 90})
            note('operator set_deadline', code, body)

            budget = {'rd_budget': '1000000', 'marketing_budget': '500000',
                      'strategy_budget': '250000'}
            base = (f'/api/games/{seeded["game_id"]}/teams/{{team}}/decisions/'
                    f'round/{round_number}/')

            # Team A: an ordinary single save.
            code, _ = api(port, 'PATCH', base.format(team=team_a['id']) + 'budget/',
                          students[team_a['id']], budget)
            note(f"{team_a['name']} normal save", code)

            # Team B: a save, then an edit of the same round. Two audit rows
            # with different payload hashes is what dispute 2 is answered from.
            code, _ = api(port, 'PATCH', base.format(team=team_b['id']) + 'budget/',
                          students[team_b['id']], budget)
            note(f"{team_b['name']} first save", code)
            edited = dict(budget, rd_budget='1750000')
            code, _ = api(port, 'PATCH', base.format(team=team_b['id']) + 'budget/',
                          students[team_b['id']], edited)
            note(f"{team_b['name']} edited save", code)

            # Team C never submits in round 2, so the default/empty state and
            # the defaulted_missing origin are real.
            if round_number != 2:
                code, _ = api(port, 'PATCH', base.format(team=team_c['id']) + 'budget/',
                              students[team_c['id']], budget)
                note(f"{team_c['name']} normal save", code)

            # The lock validator requires a complete submission: portfolio,
            # marketing mix, strategy mix and any mandatory communication. Fill
            # that in, then lock through the endpoint so the lock itself, and
            # its refusal or acceptance, are the product's own.
            locking = (team_a, team_b) if round_number == 2 else seeded['teams']
            for team in locking:
                shell(f"B.complete_submission(game, {team['id']}, {round_number})",
                      f'---FILL{team["id"]}R{round_number}---')
            for team in locking:
                code, body = api(port, 'POST', base.format(team=team['id']) + 'lock/',
                                 students[team['id']])
                note(f"{team['name']} lock", code, body)

            # Round 2 carries the deadline event: the deadline is moved into
            # the past and a student saves anyway.
            if round_number == 2:
                code, _ = api(port, 'POST',
                              f'/api/games/{seeded["game_id"]}/round-control/deadline/',
                              instructor, {'minutes_from_now': -1})
                note('operator moved deadline into the past', code)
                code, body = api(port, 'PATCH',
                                 base.format(team=team_c['id']) + 'budget/',
                                 students[team_c['id']], budget)
                note('late save after deadline', code, str(body)[:120])

            code, body = api(port, 'POST', f'/api/games/{seeded["game_id"]}/round-control/close/',
                             instructor, {'reason': 'Seeding the CRV2-08 walkthrough game'})
            note('operator close', code, body)
            code, body = api(port, 'POST', f'/api/games/{seeded["game_id"]}/round-control/process/',
                             instructor, {})
            note('operator process', code, str(body)[:120])
            if round_number < 3:
                code, body = api(port, 'POST',
                                 f'/api/games/{seeded["game_id"]}/round-control/advance/',
                                 instructor, {})
                note('operator advance', code, body)
            record['rounds'].append(events)
    finally:
        W.stop_gunicorn(process)

    record.update(shell('B.describe(game)', '---DESC---'))
    record['identities'] = seeded
    FIXTURE.write_text(json.dumps(record, indent=2, sort_keys=True,
                                  default=str) + '\n')
    print(f'\nwrote {FIXTURE.name}')
    print(json.dumps(record.get('summary', {}), indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
