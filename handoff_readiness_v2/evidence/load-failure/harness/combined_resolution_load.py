#!/usr/bin/env python3
"""Drive deadline traffic while the real instructor process route runs.

This fills the one deliberately-unmeasured CRV2-07 condition.  It is not a
second generic capacity search: fixed field and margin profiles are available
only for a frozen candidate, while ``smoke`` proves the harness against an
isolated generated PostgreSQL stack during development.
"""
import argparse
import json
import multiprocessing
import pathlib
import statistics
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import driver  # noqa: E402
import inventory_run as R  # noqa: E402
import reconcile  # noqa: E402
import stack  # noqa: E402


PROFILES = {
    # The smoke still resolves a complete 24-firm game.  It limits actors and
    # timing only, so it catches route/auth/fixture/reconciliation defects
    # without claiming a capacity result.
    'smoke': {'sessions': 8, 'duration': 5, 'resolution_window': 5,
              'release_evidence': False},
    'field': {'sessions': 96, 'duration': 180, 'resolution_window': 30,
              'release_evidence': True},
    'margin': {'sessions': 288, 'duration': 180, 'resolution_window': 30,
               'release_evidence': True},
}
THRESHOLDS = {
    'interactive_p95_ms': 2000,
    'interactive_max_ms': 10000,
    'error_rate_pct': 0.5,
    'db_connections': 80,
    'deadlocks': 0,
    'lost_or_duplicated_or_unexplained_writes': 0,
}


def _actor(session, ready, start, deadline, final_ready, final_release,
           resolution_end, think_time):
    """One authentic client through steady traffic, close race and Phase 1."""
    authenticated = session.login()
    # Keep every barrier whole even if a login fails.  The coordinator will
    # reject the profile as inadmissible instead of hanging and calling it a
    # pass on an incomplete cohort.
    ready.wait()
    start.wait()
    if not authenticated:
        return session

    import random
    rng = random.Random(session.identity['username'])
    # A short, deterministic spread models people arriving at controls at
    # different moments; the final deadline barrier is intentionally a burst.
    time.sleep(rng.uniform(0, think_time[1]))
    while time.time() < deadline.deadline:
        if rng.random() < 0.55:
            session.refresh()
        else:
            session.save(rng.randrange(1, 10_000_000))
        time.sleep(rng.uniform(*think_time))

    session.phase = 'deadline-burst'
    final_ready.wait()
    final_release.wait()
    for sequence in range(3):
        session.save(20_000_000 + sequence)
    if session.identity['member_index'] == 0:
        session.lock()

    # Keep refresh and save traffic flowing while the instructor's synchronous
    # Phase 1 owns the lifecycle boundary.  Writes after close are expected
    # 4xx refusals; refresh remains a real request under contention.
    session.phase = 'resolution'
    while time.time() < resolution_end.resolution_end:
        if rng.random() < 0.7:
            session.refresh()
        else:
            session.save(rng.randrange(30_000_000, 40_000_000))
        time.sleep(rng.uniform(*think_time))
    return session


def _shard(args):
    (base, identities, game_id, round_number, ready, start, deadline,
     final_ready, final_release, resolution_end, think_time) = args
    sessions = [driver.Session(base, identity, game_id, round_number)
                for identity in identities]
    threads = [threading.Thread(
        target=_actor,
        args=(session, ready, start, deadline, final_ready, final_release,
              resolution_end, think_time), daemon=True)
        for session in sessions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1200)
    return {
        'samples': [sample for session in sessions for sample in session.samples],
        'acknowledged': [row for session in sessions
                         for row in session.acknowledged_writes],
        'refused': [row for session in sessions for row in session.refused_writes],
        'authenticated': sum(bool(session.token) for session in sessions),
        'login_failures': [session.login_failed for session in sessions
                           if session.login_failed],
    }


def request_resolution(base, instructor, game_id, result):
    payload = {
        'force': True,
        'reason': 'CRV2-07 disposable deadline and resolution rehearsal',
    }
    login = driver._request('POST', f'{base}/api/auth/login/', payload={
        'username': instructor['username'], 'password': instructor['password']})
    result['login'] = {'status': login['status'], 'ms': round(login['ms'], 1)}
    if login['status'] != 200:
        result['status'] = login['status']
        return
    try:
        token = json.loads(login['body'])['access']
    except (ValueError, KeyError):
        result['status'] = 'invalid_login_body'
        return
    reply = driver._request(
        'POST', f'{base}/api/games/{game_id}/round-control/process/', token,
        payload, request_id='combined-resolution-instructor')
    result.update({
        'status': reply['status'], 'ms': round(reply['ms'], 1),
        'body': reply.get('body', b'')[:500].decode('utf-8', 'replace'),
    })


def _pct(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[max(0, int(round(p / 100 * len(values))) - 1)], 1)


def summarize(shards):
    samples = [sample for shard in shards for sample in shard['samples']]
    interactive = [sample for sample in samples
                   if sample['kind'] in ('refresh', 'save', 'lock')]
    latency = [sample['ms'] for sample in interactive]
    statuses = {}
    for sample in interactive:
        key = str(sample['status']) if sample['status'] is not None else 'transport-failure'
        statuses[key] = statuses.get(key, 0) + 1
    transport = sum(sample['status'] is None for sample in interactive)
    server = sum(sample['status'] is not None and sample['status'] >= 500
                 for sample in interactive)
    business = sum(sample['status'] is not None and 400 <= sample['status'] < 500
                   for sample in interactive)
    by_phase = {}
    for phase in ('steady', 'deadline-burst', 'resolution'):
        rows = [sample['ms'] for sample in interactive if sample['phase'] == phase]
        if rows:
            by_phase[phase] = {'requests': len(rows), 'p95_ms': _pct(rows, 95),
                               'max_ms': round(max(rows), 1)}
    return {
        'sessions_authenticated': sum(shard['authenticated'] for shard in shards),
        'login_failures': [failure for shard in shards
                           for failure in shard['login_failures']][:10],
        'interactive_requests': len(interactive),
        'latency_ms': {'p50': _pct(latency, 50), 'p95': _pct(latency, 95),
                       'max': round(max(latency), 1) if latency else None},
        'phase_latency': by_phase,
        'status_distribution': statuses,
        'transport_failures': transport,
        'server_errors': server,
        'business_refusals_4xx': business,
        'error_rate_pct': round(100 * (transport + server) / len(interactive), 4)
        if interactive else None,
        'acknowledged_writes': [row for shard in shards for row in shard['acknowledged']],
        'refused_writes': [row for shard in shards for row in shard['refused']],
    }


def shell_json(database, marker, code, timeout=900):
    output = R.manage(database, 'shell', '-c', code, timeout=timeout)
    if marker not in output.stdout:
        raise RuntimeError((output.stdout[-3000:] + output.stderr[-3000:]).strip())
    return json.loads(output.stdout.split(marker, 1)[1].strip().splitlines()[0])


def select_cohort(identities, sessions, teams=24):
    """Select members evenly across firms, never by the seed list's order."""
    if sessions % teams and sessions > teams:
        raise ValueError(f'{sessions} sessions cannot be evenly spread across {teams} teams')
    grouped = {}
    for identity in identities:
        grouped.setdefault(identity['team_id'], []).append(identity)
    ordered = [grouped[key] for key in sorted(grouped)]
    if len(ordered) != teams:
        raise ValueError(f'expected {teams} seeded teams, got {len(ordered)}')
    # The development smoke takes one member from each of its first eight
    # firms.  Field and margin take 4 / 12 members from every firm.
    per_team = max(1, sessions // teams)
    selected = [member for group in ordered for member in group[:per_team]]
    return selected[:sessions]


def run(profile, think_time=(0.3, 0.8)):
    spec = PROFILES[profile]
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    if spec['release_evidence'] and dirty:
        raise SystemExit('Refusing field/margin certification from a dirty tree. '
                         'Run smoke during development; freeze first for evidence.')

    report = {
        'profile': profile,
        'execution_class': ('release-candidate evidence' if spec['release_evidence']
                            else 'development smoke — not capacity evidence'),
        'code_revision': revision,
        'working_tree_clean': not bool(dirty),
        'thresholds': THRESHOLDS,
        'profile_spec': spec,
        'traffic_inventory': str(EVIDENCE / 'COMBINED_RESOLUTION_INVENTORY.md'),
    }
    with stack.disposable_stack(f'combined-{profile}') as (base, database, seeded):
        identities = select_cohort(seeded['identities'], spec['sessions'],
                                   teams=seeded['teams'])
        manager = multiprocessing.Manager()
        participants = len(identities) + 1  # coordinator joins each barrier
        ready, start, final_ready = (manager.Barrier(participants) for _ in range(3))
        final_release = manager.Event()
        timing = manager.Namespace()
        shards = [identities[index::min(multiprocessing.cpu_count(), max(1, len(identities) // 8))]
                  for index in range(min(multiprocessing.cpu_count(), max(1, len(identities) // 8)))]

        connection_samples = []
        stop = threading.Event()
        sampler = threading.Thread(target=driver.sample_database,
                                   args=(database, stop, connection_samples, 0.25),
                                   daemon=True)
        sampler.start()
        with multiprocessing.Pool(len(shards)) as pool:
            pending = pool.map_async(_shard, [
                (base, shard, seeded['game_id'], seeded['round_number'], ready,
                 start, timing, final_ready, final_release, timing, think_time)
                for shard in shards])
            ready.wait(timeout=600)
            timing.deadline = time.time() + spec['duration']
            timing.resolution_end = timing.deadline + spec['resolution_window']
            start.wait(timeout=600)
            final_ready.wait(timeout=spec['duration'] + 120)
            resolution = {}
            control = threading.Thread(
                target=request_resolution,
                args=(base, seeded['instructor'], seeded['game_id'], resolution),
                daemon=True)
            control.start()
            final_release.set()
            shards_result = pending.get(timeout=spec['duration'] +
                                        spec['resolution_window'] + 600)
            control.join(timeout=600)
            if control.is_alive():
                resolution['status'] = 'timed_out'
        stop.set()
        sampler.join(timeout=20)
        result = summarize(shards_result)
        ack, refused = result.pop('acknowledged_writes'), result.pop('refused_writes')
        pathlib.Path('/tmp/combined-ack.json').write_text(json.dumps(ack))
        pathlib.Path('/tmp/combined-refused.json').write_text(json.dumps(refused))
        reconciliation = shell_json(database, '---RECON---',
            'import sys,json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            'import reconcile\n'
            'print("---RECON---")\n'
            'print(json.dumps(reconcile.run(json.load(open("/tmp/combined-ack.json")), '
            'json.load(open("/tmp/combined-refused.json")))))\n')
        db = shell_json(database, '---DB---',
            'import sys,json\n'
            f'sys.path.insert(0, {str(HERE)!r})\n'
            'import db_probe\n'
            'print("---DB---")\n'
            f'print(json.dumps(db_probe.run({database!r})))\n')
        state = shell_json(database, '---STATE---',
            'import json\nfrom core.models import Game,Round\n'
            f'g=Game.objects.get(id={seeded["game_id"]})\n'
            'r=Round.objects.get(game=g, round_number=g.current_round)\n'
            'print("---STATE---")\n'
            'print(json.dumps({"round_status":r.status,"processing_status":r.processing_status,'
            '"phase_1_duration":r.phase_1_duration}))\n')
        breaches = []
        if result['sessions_authenticated'] != spec['sessions']:
            breaches.append('incomplete authenticated cohort')
        if resolution.get('status') != 200:
            breaches.append(f"Phase-1 process route status {resolution.get('status')}")
        if state['round_status'] != 'processed':
            breaches.append(f"round ended {state['round_status']}, not processed")
        if result['latency_ms']['p95'] is None or result['latency_ms']['p95'] > THRESHOLDS['interactive_p95_ms']:
            breaches.append('interactive p95 threshold breach')
        if result['latency_ms']['max'] is None or result['latency_ms']['max'] > THRESHOLDS['interactive_max_ms']:
            breaches.append('interactive max threshold breach')
        if (result['error_rate_pct'] or 0) > THRESHOLDS['error_rate_pct']:
            breaches.append('transport/5xx error-rate threshold breach')
        if not connection_samples or max(connection_samples) > THRESHOLDS['db_connections']:
            breaches.append('database connection measurement/threshold breach')
        if db.get('deadlocks', 0) > THRESHOLDS['deadlocks']:
            breaches.append('database deadlock threshold breach')
        if not reconciliation.get('reconciles'):
            breaches.append('write reconciliation failed')
        report.update({
            'scenario': seeded['scenario'], 'teams': seeded['teams'],
            'result': result, 'instructor_resolution': resolution,
            'round_state': state, 'database': db,
            'db_connections': {'samples': len(connection_samples),
                               'peak': max(connection_samples) if connection_samples else None,
                               'mean': round(statistics.mean(connection_samples), 2)
                               if connection_samples else None},
            'reconciliation': reconciliation, 'threshold_breaches': breaches,
            'passed': not breaches,
        })
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=sorted(PROFILES))
    parser.add_argument('--output', type=pathlib.Path,
                        help='write a caller-selected development report; never '
                             'writes release evidence/checksums implicitly')
    args = parser.parse_args()
    report = run(args.profile)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, indent=2, sort_keys=True))
    # Smoke output is intentionally not placed in the immutable evidence
    # directory or its checksum manifest.  A frozen release candidate has a
    # separate explicit collection step.
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
