#!/usr/bin/env python3
"""Three students, real logins, one instructor watching readiness change.

The rework's acceptance walkthrough. Everything goes through the running
server: students authenticate at `/api/auth/login/` and make an authenticated
request so the heartbeat sets `last_seen_at`, and the instructor reads
`/api/games/{id}/instructor/session-readiness/` between each step. Nothing is
asserted from the database directly, because the claim under test is what an
instructor can see before opening a round.

Seven stages, each recorded with what readiness reported:

  1. three expected participants, none signed in;
  2. two signed in -> 2 authenticated, 1 missing, ready false;
  3. the third signs in -> 3 authenticated, 0 missing, ready true;
  4. a session idled past the timeout is not counted active;
  5. a logged-out session is not counted active;
  6. another cohort's session cannot satisfy this one;
  7. a duplicate session is surfaced, not double-counted.
"""
import json, pathlib, subprocess, sys
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402
import stack  # noqa: E402


def call(base, path, token=None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f'{base}{path}', data=data,
                                 method='POST' if data else 'GET')
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:300].decode('utf-8', 'replace')


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    stages = []
    with stack.disposable_stack('readywalk') as (base, database, seeded):
        game_id = seeded['game_id']
        # One team, three of its members: a cohort small enough to read.
        cohort = [i for i in seeded['identities']
                  if i['team_id'] == seeded['identities'][0]['team_id']][:3]
        team_id = cohort[0]['team_id']

        prep = (
            'import json\n'
            'from core.models.course import Enrollment\n'
            f'keep = {[c["user_id"] for c in cohort]!r}\n'
            f'Enrollment.objects.filter(team_id={team_id}).exclude('
            'user_id__in=keep).update(is_active=False)\n'
            'print("---PREP---")\n'
            'print(json.dumps({"kept": keep}))\n')
        R.manage(database, 'shell', '-c', prep, timeout=300)

        status, body = call(base, '/api/auth/login/', payload={
            'username': seeded['instructor']['username'],
            'password': seeded['instructor']['password']})
        if status != 200:
            raise SystemExit(f'instructor login failed: {status} {body}')
        instructor_token = body['access']

        def readiness():
            s, b = call(
                base,
                f'/api/games/{game_id}/instructor/session-readiness/'
                f'?teams={team_id}',
                instructor_token)
            return s, b

        def record(stage, note):
            s, b = readiness()
            entry = {'stage': stage, 'note': note, 'status': s,
                     'roster': b.get('roster') if isinstance(b, dict) else None,
                     'sessions': b.get('sessions') if isinstance(b, dict) else None,
                     'ready': b.get('ready') if isinstance(b, dict) else None,
                     'blocking_reasons': b.get('blocking_reasons')
                     if isinstance(b, dict) else None}
            stages.append(entry)
            print(f"  {stage}: {entry['sessions']} ready={entry['ready']}",
                  flush=True)
            return entry

        def student_login(identity):
            s, b = call(base, '/api/auth/login/', payload={
                'username': identity['username'],
                'password': identity['password']})
            if s != 200:
                raise SystemExit(f"student login failed: {s} {b}")
            token = b['access']
            # An authenticated request so the heartbeat records last_seen_at.
            call(base, f"/api/games/{game_id}/teams/{identity['team_id']}"
                       f"/decisions/round/{seeded['round_number']}/summary/",
                 token)
            return token

        record('1_none_signed_in', 'three expected, nobody authenticated')

        tokens = {}
        for identity in cohort[:2]:
            tokens[identity['username']] = student_login(identity)
        record('2_two_signed_in', 'two authenticated, one missing')

        tokens[cohort[2]['username']] = student_login(cohort[2])
        record('3_all_signed_in', 'third signs in, cohort complete')

        # Idle: age one session past the timeout, in the database, because
        # waiting fifteen minutes in a walkthrough is not a test.
        idle = (
            'from django.utils import timezone\n'
            'from core.models.auth_models import UserSession\n'
            f'cut = timezone.now() - timezone.timedelta('
            'minutes=UserSession.IDLE_TIMEOUT_MINUTES + 5)\n'
            f'UserSession.objects.filter(user_id={cohort[2]["user_id"]}).update('
            'last_seen_at=cut)\n'
            'print("---IDLE---")\n')
        R.manage(database, 'shell', '-c', idle, timeout=300)
        record('4_one_idled_out', 'a session idle past the timeout')

        # Logged out: restore freshness, then mark logout.
        out = (
            'from django.utils import timezone\n'
            'from core.models.auth_models import UserSession\n'
            f'UserSession.objects.filter(user_id={cohort[2]["user_id"]}).update('
            'last_seen_at=timezone.now(), logout_at=timezone.now())\n'
            'print("---OUT---")\n')
        R.manage(database, 'shell', '-c', out, timeout=300)
        record('5_one_logged_out', 'a session explicitly logged out')

        # Another cohort: move that session to a different game id.
        foreign = (
            'from django.utils import timezone\n'
            'from core.models.auth_models import UserSession\n'
            f'UserSession.objects.filter(user_id={cohort[2]["user_id"]}).update('
            f'last_seen_at=timezone.now(), logout_at=None, game_id={game_id + 999})\n'
            'print("---FOREIGN---")\n')
        R.manage(database, 'shell', '-c', foreign, timeout=300)
        record('6_session_belongs_to_another_cohort',
               "another cohort's session cannot satisfy this one")

        # Duplicate: the third signs in again here, and the second opens a
        # second browser.
        student_login(cohort[2])
        student_login(cohort[1])
        dup = (
            'import json\n'
            'from core.models.auth_models import UserSession\n'
            f'rows = UserSession.objects.filter(user_id={cohort[1]["user_id"]}'
            f', game_id={game_id}).count()\n'
            'print("---DUP---")\n'
            'print(json.dumps({"sessions_for_second_student": rows}))\n')
        dup_out = R.manage(database, 'shell', '-c', dup, timeout=300)
        record('7_duplicate_session', 'one participant with two live sessions')

    report = {'code_revision': revision, 'stages': stages}

    def stage(name):
        return next(s for s in stages if s['stage'].startswith(name))

    checks = {
        'three_expected': stage('1')['roster']['expected_participants'] == 3,
        'two_authenticated_one_missing_not_ready': (
            stage('2')['sessions']['authenticated'] == 2
            and stage('2')['sessions']['missing'] == 1
            and stage('2')['ready'] is False),
        'three_authenticated_none_missing_ready': (
            stage('3')['sessions']['authenticated'] == 3
            and stage('3')['sessions']['missing'] == 0
            and stage('3')['ready'] is True),
        'idle_not_counted_active': (
            stage('4')['sessions']['authenticated'] == 2
            and stage('4')['sessions']['stale'] >= 1
            and stage('4')['ready'] is False),
        'logged_out_not_counted_active': (
            stage('5')['sessions']['authenticated'] == 2
            and stage('5')['sessions']['stale'] >= 1
            and stage('5')['ready'] is False),
        'foreign_cohort_session_does_not_satisfy': (
            stage('6')['sessions']['authenticated'] == 2
            and stage('6')['ready'] is False),
        'duplicates_surfaced_not_double_counted': (
            stage('7')['sessions']['authenticated'] == 3
            and stage('7')['sessions']['duplicate_sessions'] >= 1
            and stage('7')['ready'] is False),
    }
    report['checks'] = checks
    report['failed_checks'] = [k for k, v in checks.items() if not v]
    report['passed'] = not report['failed_checks']

    (EVIDENCE / 'session-readiness-walkthrough.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    if checksums.verify(EVIDENCE):
        raise SystemExit('inventory does not verify')

    print('\n=== readiness walkthrough ===')
    for s in stages:
        print(f"  {s['stage']:<40} {s['sessions']}  ready={s['ready']}")
    print('\nchecks:')
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nPASSED: {report['passed']}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
