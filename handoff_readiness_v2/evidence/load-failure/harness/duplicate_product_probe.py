#!/usr/bin/env python3
"""Two products with the same name permanently block a game's resolution.

Found while diagnosing stage 6 of the failure walkthrough, which failed on a
SnapshotError rather than on the database loss it was injecting. The
SnapshotError is not a harness artifact.

`manifest_sections` declares team_product's natural key as (team_id, name).
The schema does not enforce that pair, `DecisionProductCreate.product_name` is
free text with no uniqueness validation on the write path, and
`_process_product_creates` creates the row unconditionally. `prepare_manifest`
runs inside the resolution transaction *before* `_run_phase_1`, so the round
that creates the duplicate resolves normally and every later round refuses.

This probe drives the student HTTP write path, so reachability is demonstrated
rather than argued.
"""
import json, os, pathlib, subprocess, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums, inventory_run as R, stack as S  # noqa: E402
import failure_walkthrough_run as W  # noqa: E402


def api(port, method, path, token=None, body=None):
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}{path}', method=method,
        data=None if body is None else json.dumps(body).encode())
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() or b'')[:400].decode('utf-8', 'replace')


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree')

    database = f'gsp_dupname_{time.strftime("%H%M%S")}'
    port = S.free_port()
    process = None
    backups = pathlib.Path(f'/tmp/{database}-backups')
    backups.mkdir(parents=True, exist_ok=True)
    os.environ['COMPETITION_BACKUP_DIR'] = str(backups)
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    result = {'code_revision': revision}
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        seed = W.shell(database,
                       'import json, seed_field\n'
                       'seeded = seed_field.run(teams=None, members_per_team=2)\n'
                       'print("---SEED---")\n'
                       'print(json.dumps(seeded, default=str))\n', timeout=1800)
        if '---SEED---' not in seed.stdout:
            raise SystemExit('seeding failed:\n' + seed.stdout[-2500:]
                             + '\n' + seed.stderr[-2000:])
        seeded = json.loads(seed.stdout.split('---SEED---', 1)[1].strip().splitlines()[0])
        W.BACKUP_DIR = backups
        process = W.start_gunicorn(database, port, 'dupname')

        student = seeded['identities'][0]
        _, tok = api(port, 'POST', '/api/auth/login/',
                     body={'username': student['username'],
                           'password': seeded['password']})
        token = tok['access']
        game_id, team_id = seeded['game_id'], student['team_id']
        rnd = seeded['round_number']

        # A team's own platform is needed to name a product create.
        platform = W.stage_via_shell(
            database,
            f'W2.platform_for(game, {team_id})', marker='---PLAT---')

        # Two creates, one name. Nothing on this path objects.
        payload = [{'team_platform': platform['team_platform_id'],
                    'product_name': 'Vanguard One',
                    'positioning': platform['positioning'],
                    'target_market_ids': platform['market_ids']},
                   {'team_platform': platform['team_platform_id'],
                    'product_name': 'Vanguard One',
                    'positioning': platform['positioning'],
                    'target_market_ids': platform['market_ids']}]
        write_status, write_body = api(
            port, 'PATCH',
            f'/api/games/{game_id}/teams/{team_id}/decisions/round/{rnd}/products/',
            token, payload)
        result['student_write'] = {
            'endpoint': f'PATCH /api/games/{{id}}/teams/{{id}}/decisions/'
                        f'round/{{n}}/products/',
            'identical_product_names': 'Vanguard One',
            'status': write_status,
            'accepted': write_status in (200, 201),
            'body': write_body if write_status not in (200, 201) else 'accepted',
        }
        W.stop_gunicorn(process); process = None

        result['resolution'] = W.stage_via_shell(
            database, 'W2.resolve_twice(game)', marker='---RESOLVE---')
    finally:
        if process is not None:
            W.stop_gunicorn(process)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')

    res = result.get('resolution', {})
    result['finding'] = {
        'reachable_by_a_student': result['student_write']['accepted'],
        'round_creating_the_duplicate_resolves': res.get('first_round_processed'),
        'next_round_refuses': res.get('second_round_blocked'),
        'refusal_is_permanent': res.get('retry_also_blocked'),
        'documented_operator_recovery': False,
    }
    result['passed'] = all([
        result['finding']['reachable_by_a_student'],
        result['finding']['round_creating_the_duplicate_resolves'],
        result['finding']['next_round_refuses'],
        result['finding']['refusal_is_permanent'],
    ])
    (EVIDENCE / 'duplicate-product-name.json').write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + '\n')
    checksums.regenerate(EVIDENCE)
    if checksums.verify(EVIDENCE):
        raise SystemExit('inventory does not verify')

    print('\n=== duplicate product name: resolution blocked ===')
    print(json.dumps(result.get('student_write'), indent=2)[:600])
    print(json.dumps(res, indent=2, default=str)[:1400])
    print(f"\nreproduced end to end: {result['passed']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
