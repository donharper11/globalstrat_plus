#!/usr/bin/env python3
"""Run the authentication acceptance profile against a disposable stack."""
import json, pathlib, subprocess, sys, time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402
import stack  # noqa: E402

THRESHOLDS = {'login_p95_ms': 2000, 'login_failures': 0,
              'interactive_5xx': 0, 'interactive_transport_failures': 0,
              'sessions_visible_in_readiness': 96}


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    with stack.disposable_stack('auth') as (base, database, seeded):
        body = (
            'import sys, json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            f'sys.path.insert(0, {str(EVIDENCE.parent / "adversarial-balance" / "harness")!r})\n'
            'import auth_acceptance_body, json as j\n'
            f'seeded = j.loads(open("/tmp/auth-seed.json").read())\n'
            f'report = auth_acceptance_body.drive({base!r}, seeded)\n'
            'print("---AUTH-JSON---")\n'
            'print(json.dumps(report, default=str))\n')
        pathlib.Path('/tmp/auth-seed.json').write_text(json.dumps(seeded))
        result = R.manage(database, 'shell', '-c', body, timeout=3600)
        marker = '---AUTH-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-4000:])
            raise SystemExit('the authentication profile did not run')
        report = json.loads(
            result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        # Instructor readiness: are all 96 sessions visible to the instructor?
        # The token is minted inside the stack's own process; this runner is
        # not a Django process and importing core here crashed the run after
        # the full nine-minute drive had already completed.
        inst_body = (
            'import json\n'
            'from core.authentication import create_access_token\n'
            'from core.models import User\n'
            'u = User.objects.get(username="load_instructor")\n'
            'print("---TOK---")\n'
            'print(create_access_token(u))\n')
        tok_out = R.manage(database, 'shell', '-c', inst_body, timeout=300)
        token = tok_out.stdout.split('---TOK---', 1)[1].strip().splitlines()[0]
        req = urllib.request.Request(
            f"{base}/api/games/{seeded['game_id']}/instructor/dashboard/")
        req.add_header('Authorization', f'Bearer {token}')
        with urllib.request.urlopen(req, timeout=60) as response:
            dashboard = json.loads(response.read())
        members = []
        for team in (dashboard.get('teams') or []):
            members.extend(team.get('members') or [])
        report['readiness'] = {
            'status': 200,
            'teams_listed': len(dashboard.get('teams') or []),
            'members_visible': len(members),
            'expected_members': THRESHOLDS['sessions_visible_in_readiness'],
        }

        recon_body = (
            'import sys, json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            'import reconcile\n'
            'ack = json.loads(open("/tmp/ack.json").read())\n'
            'ref = json.loads(open("/tmp/ref.json").read())\n'
            'print("---RECON---")\n'
            'print(json.dumps(reconcile.run(ack, ref), default=str))\n')
        pathlib.Path('/tmp/ack.json').write_text(
            json.dumps(report.pop('acknowledged_writes')))
        pathlib.Path('/tmp/ref.json').write_text(
            json.dumps(report.pop('refused_writes')))
        recon = R.manage(database, 'shell', '-c', recon_body, timeout=600)
        report['reconciliation'] = json.loads(
            recon.stdout.split('---RECON---', 1)[1].strip().splitlines()[0])

    breaches = []
    if report['sessions_authenticated'] != THRESHOLDS['sessions_visible_in_readiness']:
        breaches.append(f"only {report['sessions_authenticated']} of 96 "
                        f"sessions authenticated")
    if (report['login']['p95_ms'] or 0) > THRESHOLDS['login_p95_ms']:
        breaches.append(f"login p95 {report['login']['p95_ms']} ms exceeds "
                        f"{THRESHOLDS['login_p95_ms']} ms")
    if report['login_5xx_or_transport'] > 0:
        breaches.append(f"{report['login_5xx_or_transport']} login failures")
    if report['interactive_5xx'] or report['interactive_transport_failures']:
        breaches.append('interactive 5xx or transport failures')
    if report['readiness']['members_visible'] < THRESHOLDS['sessions_visible_in_readiness']:
        breaches.append(
            f"instructor readiness shows "
            f"{report['readiness']['members_visible']} members, expected 96")
    if report['reauthentication_events']:
        breaches.append(
            f"{len(report['reauthentication_events'])} reauthentication events")
    if not report['tokens_unchanged_through_window']:
        breaches.append('a session token changed during the window')
    if not report['reconciliation']['reconciles']:
        breaches.append('write reconciliation failed')
    report['threshold_breaches'] = breaches
    report['passed'] = not breaches

    (EVIDENCE / 'auth-acceptance.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    bad = checksums.verify(EVIDENCE)
    if bad:
        raise SystemExit(f'inventory does not verify: {bad}')

    print(f"\nadmission window : {report['admission_window_seconds']}s "
          f"(elapsed {report['admission_elapsed_seconds']}s)")
    print(f"authenticated    : {report['sessions_authenticated']}/96")
    print(f"login            : p50 {report['login']['p50_ms']} ms  "
          f"p95 {report['login']['p95_ms']} ms  max {report['login']['max_ms']} ms")
    print(f"login failures   : {report['login_5xx_or_transport']}")
    print(f"interactive      : {report['interactive_requests']} requests, "
          f"{report['interactive_latency_ms']}")
    print(f"interactive errs : {report['interactive_5xx']} 5xx, "
          f"{report['interactive_transport_failures']} transport")
    print(f"readiness        : {report['readiness']}")
    print(f"reauthentication : {len(report['reauthentication_events'])} events; "
          f"tokens unchanged {report['tokens_unchanged_through_window']}")
    print(f"token lifetime   : {report['token_lifetime_hours']} hours")
    print(f"reconciliation   : {report['reconciliation']['reconciles']} "
          f"({report['reconciliation']['acknowledged_writes']} writes)")
    print(f"\nbreaches         : {breaches or 'none'}")
    print(f"PASSED           : {report['passed']}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
