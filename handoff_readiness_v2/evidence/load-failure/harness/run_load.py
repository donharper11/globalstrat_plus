#!/usr/bin/env python3
"""Run one load profile against a disposable stack and report against thresholds.

Profiles: smoke (development, no evidence), field (96 sessions), margin (288).
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
# checksums.py and inventory_run.py live with the adversarial-balance harness;
# reused rather than copied so the two evidence directories cannot drift.
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import driver  # noqa: E402
import inventory_run as R  # noqa: E402
import stack  # noqa: E402

PROFILES = {
    'smoke': {'sessions': 8, 'duration': 20, 'evidence': False},
    'field': {'sessions': 96, 'duration': 180, 'evidence': True},
    'margin': {'sessions': 288, 'duration': 180, 'evidence': True},
}

THRESHOLDS = {
    'p95_ms': 2000, 'max_ms': 10000, 'error_rate_pct': 0.5,
    'db_connections': 80, 'lock_waits': 0, 'deadlocks': 0,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=sorted(PROFILES))
    args = parser.parse_args()
    spec = PROFILES[args.profile]

    if spec['evidence']:
        dirty = subprocess.run(
            ['git', 'status', '--porcelain', '--untracked-files=no'],
            cwd=REPO, capture_output=True, text=True).stdout.strip()
        if dirty:
            raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                             + '\n  '.join(dirty.splitlines()))
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()

    with stack.disposable_stack(args.profile) as (base, database, seeded):
        identities = seeded['identities'][:spec['sessions']]
        print(f"Driving {len(identities)} sessions for {spec['duration']}s",
              flush=True)
        result = driver.run_profile(
            base, identities, seeded['game_id'], seeded['round_number'],
            spec['duration'], database=database)

        # Server-side timing straight from gunicorn's access log, so a slow
        # request can be attributed to the server or to the client that
        # observed it.
        access = EVIDENCE / f'gunicorn-{args.profile}.log'
        server_side = {'parsed': 0}
        if access.exists():
            durations = []
            for line in access.read_text(errors='replace').splitlines():
                parts = line.rsplit(' ', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    durations.append(int(parts[1]) / 1000.0)
            if durations:
                durations.sort()
                server_side = {
                    'parsed': len(durations),
                    'p50_ms': round(durations[len(durations) // 2], 1),
                    'p95_ms': round(durations[max(0, int(round(0.95 * len(durations))) - 1)], 1),
                    'max_ms': round(durations[-1], 1),
                    'over_10s': sum(1 for d in durations if d > 10000),
                }
        result['server_side_timing'] = server_side

        # Database state, read from the server while the stack is still up.
        body = (
            'import sys, json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            'import db_probe\n'
            'print("---DB---")\n'
            f'print(json.dumps(db_probe.run({database!r}), default=str))\n')
        probe = R.manage(database, 'shell', '-c', body, timeout=300)
        db = (json.loads(probe.stdout.split('---DB---', 1)[1].strip().splitlines()[0])
              if '---DB---' in probe.stdout else {'error': 'db probe failed'})

        body = (
            'import sys, json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            'import reconcile\n'
            'ack = json.loads(open("/tmp/ack.json").read())\n'
            'ref = json.loads(open("/tmp/ref.json").read())\n'
            'print("---RECON---")\n'
            'print(json.dumps(reconcile.run(ack, ref), default=str))\n')
        pathlib.Path('/tmp/ack.json').write_text(
            json.dumps(result['acknowledged_writes']))
        pathlib.Path('/tmp/ref.json').write_text(
            json.dumps(result['refused_writes']))
        recon = R.manage(database, 'shell', '-c', body, timeout=600)
        reconciliation = (
            json.loads(recon.stdout.split('---RECON---', 1)[1].strip().splitlines()[0])
            if '---RECON---' in recon.stdout
            else {'error': 'reconciliation failed', 'reconciles': False})

    lat = result['latency_ms']
    breaches = []
    if result['sessions_authenticated'] < spec['sessions']:
        breaches.append(
            f"only {result['sessions_authenticated']} of {spec['sessions']} "
            f"sessions authenticated; the profile never reached its "
            f"concurrency and measures the driver, not the product")
    if lat['p95'] is not None and lat['p95'] > THRESHOLDS['p95_ms']:
        breaches.append(f"p95 {lat['p95']} ms exceeds {THRESHOLDS['p95_ms']} ms")
    if lat['max'] is not None and lat['max'] > THRESHOLDS['max_ms']:
        breaches.append(f"max {lat['max']} ms exceeds {THRESHOLDS['max_ms']} ms")
    if (result['error_rate_pct'] or 0) > THRESHOLDS['error_rate_pct']:
        breaches.append(
            f"error rate {result['error_rate_pct']}% exceeds "
            f"{THRESHOLDS['error_rate_pct']}%")
    peak = result.get('db_connections_peak')
    if peak is None:
        breaches.append('database connections were never sampled during the '
                        'run, so saturation is unmeasured')
    elif peak > THRESHOLDS['db_connections']:
        breaches.append(f"peak connections {peak} exceeds "
                        f"{THRESHOLDS['db_connections']}")
    if db.get('deadlocks', 0) > THRESHOLDS['deadlocks']:
        breaches.append(f"{db['deadlocks']} deadlocks")
    if not reconciliation.get('reconciles'):
        breaches.append('write reconciliation failed')

    report = {
        'profile': args.profile, 'code_revision': revision,
        'thresholds': THRESHOLDS, 'spec': spec,
        'scenario': seeded['scenario'], 'teams': seeded['teams'],
        'result': {k: v for k, v in result.items()
                   if k not in ('acknowledged_writes', 'refused_writes')},
        'database': db,
        'reconciliation': reconciliation,
        'threshold_breaches': breaches,
        'passed': not breaches,
    }

    print(f"\n=== {args.profile} ===")
    print(f"sessions        : {result['sessions_authenticated']}/"
          f"{spec['sessions']} authenticated")
    print(f"requests        : {result['requests_total']} in "
          f"{result['elapsed_seconds']}s  ({result['throughput_rps']} rps)")
    print(f"latency ms      : p50 {lat['p50']}  p95 {lat['p95']}  "
          f"p99 {lat['p99']}  max {lat['max']}")
    print(f"per-kind p95    : {result['per_kind_p95']}")
    print(f"per-kind max    : {result['per_kind_max']}")
    print(f"per-phase p95   : {result['per_phase_p95']}")
    print(f"sign-in window  : {result.get('sign_in_window_seconds')}s "
          f"(excluded from the measured window)")
    print(f"login           : {result.get('login')}")
    print(f"checkpoints     : {result.get('checkpoints')}")
    print(f"slow db windows : {result.get('slow_activity_window_count')}")
    for window in (result.get('slow_activity_windows') or [])[:4]:
        print(f"  at {window['seconds_into_run']:>6.1f}s  "
              f"{window['connections']} active")
        for row in window['slow'][:3]:
            print(f"      {row['seconds']:>6.2f}s {row['state']:<12} "
                  f"{row['wait_type']}/{row['wait_event']:<16} {row['query'][:80]}")
    ss = result.get('server_side_timing', {})
    print(f"server-side     : {ss}")
    print(f"slowest seconds : "
          f"{[(b['second'], b['requests'], b['max_ms']) for b in result['slowest_seconds'][:5]]}")
    print(f"slowest 8       :")
    for row in result['slowest_requests'][:8]:
        print(f"    {row['ms']:>9.1f} ms  {row['kind']:<8} {row['phase']:<13} "
              f"at {row['seconds_into_run']:>6.1f}s  status {row['status']}")
    print(f"status          : {result['status_distribution']}")
    print(f"errors          : {result['transport_failures']} transport, "
          f"{result['server_errors']} 5xx  -> {result['error_rate_pct']}%")
    print(f"business 4xx    : {result['business_refusals_4xx']} (not errors)")
    print(f"db connections  : peak {result.get('db_connections_peak')}, "
          f"mean {result.get('db_connections_mean')} over "
          f"{result.get('db_connection_samples')} samples during load")
    print(f"db after run    : {db}")
    print(f"reconciliation  : acknowledged "
          f"{reconciliation.get('acknowledged_writes')}, lost "
          f"{reconciliation.get('lost_write_count')}, duplicated "
          f"{reconciliation.get('duplicated_write_count')}, unexplained "
          f"{reconciliation.get('unexplained_row_count')}, refused-but-kept "
          f"{reconciliation.get('refused_but_recorded_count')}  -> "
          f"{reconciliation.get('reconciles')}")
    print(f"\nbreaches        : {breaches or 'none'}")
    print(f"PASSED          : {report['passed']}")

    if spec['evidence']:
        (EVIDENCE / f'load-{args.profile}.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')
        print(f"\nwrote {EVIDENCE / f'load-{args.profile}.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
    else:
        print('\nno evidence written: development smoke')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
