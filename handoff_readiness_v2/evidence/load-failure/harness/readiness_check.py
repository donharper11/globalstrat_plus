#!/usr/bin/env python3
"""Can the instructor see the whole cohort before round 1 opens?

Split out from the authentication profile because it is independent of the
traffic drive: the dashboard enumerates enrolled members, so the question is
whether the instructor sees all 96, not whether they happen to be mid-request.
Re-running a nine-minute drive to re-ask a two-minute question would be waste.

The instructor authenticates through the real login endpoint rather than having
a token minted for them. The first attempt minted one inside `manage shell`,
which never receives the DJANGO_SECRET_KEY the stack runs with, so the token
was signed with one key and validated against another and came back 403
"Invalid token". Using the endpoint is both correct and what an instructor
actually does.
"""
import json, pathlib, subprocess, sys
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import stack  # noqa: E402

EXPECTED_MEMBERS = 96
EXPECTED_TEAMS = 24


def call(base, path, token=None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f'{base}{path}', data=data,
                                 method='POST' if data else 'GET')
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:400].decode('utf-8', 'replace')


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    with stack.disposable_stack('readiness') as (base, database, seeded):
        status, body = call(base, '/api/auth/login/', payload={
            'username': seeded['instructor']['username'],
            'password': seeded['instructor']['password']})
        report = {'code_revision': revision,
                  'instructor_login_status': status,
                  'expected_teams': EXPECTED_TEAMS,
                  'expected_members': EXPECTED_MEMBERS}
        if status != 200:
            report['error'] = body
            report['passed'] = False
        else:
            token = body['access']
            status, dashboard = call(
                base, f"/api/games/{seeded['game_id']}/instructor/dashboard/",
                token)
            report['dashboard_status'] = status
            if status != 200:
                report['error'] = dashboard
                report['passed'] = False
            else:
                teams = dashboard.get('teams') or []
                members = [m for t in teams for m in (t.get('members') or [])]
                # The seeder enrols twelve identities per team so the margin
                # profile has separate identities; the field cohort is the
                # first four of each. Readiness is asked of the field cohort.
                report['teams_listed'] = len(teams)
                report['members_visible'] = len(members)
                report['distinct_members'] = len(set(members))
                report['covers_field_cohort'] = (
                    len(teams) >= EXPECTED_TEAMS
                    and len(members) >= EXPECTED_MEMBERS)
                report['sample_team'] = (
                    {'name': teams[0].get('name'),
                     'members': (teams[0].get('members') or [])[:4]}
                    if teams else None)
                report['passed'] = report['covers_field_cohort']

    (EVIDENCE / 'instructor-readiness.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    bad = checksums.verify(EVIDENCE)
    if bad:
        raise SystemExit(f'inventory does not verify: {bad}')

    print(f"\ninstructor login : {report['instructor_login_status']}")
    print(f"dashboard        : {report.get('dashboard_status')}")
    print(f"teams listed     : {report.get('teams_listed')} "
          f"(expected >= {EXPECTED_TEAMS})")
    print(f"members visible  : {report.get('members_visible')} "
          f"(expected >= {EXPECTED_MEMBERS}, distinct "
          f"{report.get('distinct_members')})")
    print(f"sample team      : {report.get('sample_team')}")
    print(f"error            : {report.get('error')}")
    print(f"PASSED           : {report['passed']}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
