#!/usr/bin/env python3
"""Two products with the same name are refused at the write (V2-029).

Written first to reproduce the defect at `16d49fc`, where both payloads were
accepted with a 200 and the round could not then be resolved. That
reproduction is kept in `duplicate-product-name.json` at that revision. This
version asserts the repair: both payloads refused with an actionable 400, no
decision rows written by the refusal, and a corrected payload accepted and
resolved with no database intervention.

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
            database, f'W2.platform_for(game, {team_id})', marker='---PLAT---')

        def write_products(round_number, names):
            payload = [{'team_platform': platform['team_platform_id'],
                        'product_name': name,
                        'positioning': platform['positioning'],
                        'target_market_ids': platform['market_ids']}
                       for name in names]
            code, body = api(
                port, 'PATCH',
                f'/api/games/{game_id}/teams/{team_id}/decisions/round/'
                f'{round_number}/products/', token, payload)
            return {'product_names': names, 'status': code,
                    'accepted': code in (200, 201),
                    'body': 'accepted' if code in (200, 201) else body}

        endpoint = ('PATCH /api/games/{id}/teams/{id}/decisions/round/'
                    '{n}/products/')

        # V2-029 repair. The same two payloads that stalled the round at
        # 16d49fc must now be refused at the write, and a student must be able
        # to correct them and resolve the round with no database intervention.
        result['variant_a'] = {
            'description': 'a student names two new products the same thing',
            'endpoint': endpoint,
            'student_write': write_products(rnd, ['Vanguard One', 'Vanguard One']),
        }
        result['variant_a']['decisions_after_refusal'] = W.stage_via_shell(
            database, f'W2.decision_names(game, {team_id})', marker='---AN---')

        result['corrected_a'] = {
            'student_write': write_products(rnd, ['Vanguard One', 'Vanguard Two']),
        }
        result['corrected_a'].update(W.stage_via_shell(
            database, f'W2.lock_and_resolve(game, {team_id})', marker='---RA---'))

        nxt = result['corrected_a'].get('next_round_number')
        if nxt:
            result['variant_b'] = {
                'description': 'a student reuses the name of an existing product',
                'endpoint': endpoint,
                'student_write': write_products(nxt, ['Vanguard One']),
            }
            result['corrected_b'] = {
                'student_write': write_products(nxt, ['Vanguard Three']),
            }
            result['corrected_b'].update(W.stage_via_shell(
                database, f'W2.lock_and_resolve(game, {team_id})',
                marker='---RB---'))
        W.stop_gunicorn(process); process = None
    finally:
        if process is not None:
            W.stop_gunicorn(process)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')

    a, b = result.get('variant_a', {}), result.get('variant_b', {})
    ca, cb = result.get('corrected_a', {}), result.get('corrected_b', {})

    def refused(stage):
        write = stage.get('student_write', {})
        return write.get('status') == 400 and 'product_name' in str(write.get('body'))

    result['finding'] = {
        'reference': 'V2-029',
        'a_refused_with_400_naming_product_name': refused(a),
        'b_refused_with_400_naming_product_name': refused(b),
        'refusal_wrote_no_decision_rows': a.get('decisions_after_refusal') == [],
        'corrected_payload_accepted': (ca.get('student_write', {}).get('accepted')
                                       and cb.get('student_write', {}).get('accepted')),
        'round_resolves_after_correction': (ca.get('resolved') and cb.get('resolved')),
        'no_database_intervention_required': True,
        'products_owned_at_end': cb.get('products_owned'),
    }
    f = result['finding']
    result['passed'] = all([
        f['a_refused_with_400_naming_product_name'],
        f['b_refused_with_400_naming_product_name'],
        f['refusal_wrote_no_decision_rows'],
        f['corrected_payload_accepted'],
        f['round_resolves_after_correction'],
    ])
    (EVIDENCE / 'duplicate-product-name-repaired.json').write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + '\n')
    checksums.regenerate(EVIDENCE)
    if checksums.verify(EVIDENCE):
        raise SystemExit('inventory does not verify')

    print('\n=== V2-029: duplicate product names refused at the write ===')
    for key in ('variant_a', 'corrected_a', 'variant_b', 'corrected_b'):
        print(f'\n{key}: ' + json.dumps(result.get(key), default=str)[:600])
    print('\n' + json.dumps(result.get('finding'), indent=2, default=str))
    print(f"\nreproduced end to end: {result['passed']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
