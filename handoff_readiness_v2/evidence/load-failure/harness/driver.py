"""The load driver: authenticated sessions doing the traffic students generate.

One thread per session, each with its own identity and its own token. Traffic
is weighted the way a decision round actually behaves -- mostly reading the
current state back, regularly saving, locking near the end -- and every save
carries a unique `X-Request-ID`.

That header is what makes write reconciliation possible. `record_decision_event`
writes one append-only `DecisionAuditEvent` per accepted save and stores the
request id, so afterwards the driver can ask two exact questions: did every
acknowledged write leave exactly one row, and does every row trace to an
acknowledged write. Last-write-wins on the decision row itself cannot answer
either.

Business refusals are not errors. A save after the deadline, or against a
locked submission, is the product working; those are counted and reported
separately from transport failures and 5xx.
"""
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid


def _request(method, url, token=None, payload=None, request_id=None,
             timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if request_id:
        req.add_header('X-Request-ID', request_id)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # The whole body: truncating it to 400 bytes for diagnostics cut
            # the access token mid-string, so every login parsed as malformed
            # JSON and no session authenticated. Error bodies are truncated at
            # the point of recording instead.
            body = response.read()
            return {'status': response.status,
                    'ms': (time.perf_counter() - started) * 1000,
                    'body': body}
    except urllib.error.HTTPError as exc:
        return {'status': exc.code, 'ms': (time.perf_counter() - started) * 1000,
                'body': exc.read()[:400]}   # diagnostics only, never parsed
    except Exception as exc:
        # Transport failure: no HTTP answer at all. Distinct from a 4xx, and
        # counted against the error budget.
        return {'status': None, 'ms': (time.perf_counter() - started) * 1000,
                'error': f'{type(exc).__name__}: {exc}'[:200]}


class Session:
    def __init__(self, base, identity, game_id, round_number):
        self.base = base
        self.identity = identity
        self.game_id = game_id
        self.round_number = round_number
        self.token = None
        self.phase = 'steady'
        self.samples = []
        self.acknowledged_writes = []
        self.refused_writes = []
        self.login_failed = None

    def record(self, kind, result):
        # `at` is seconds since the profile began, so a slow request can be
        # placed against what else was happening -- the final-minute burst in
        # particular. A max with no timestamp cannot be diagnosed.
        self.samples.append({'kind': kind, 'status': result['status'],
                             'ms': result['ms'], 'at': time.time(),
                             'phase': self.phase,
                             'error': result.get('error')})

    def login(self):
        result = _request('POST', f'{self.base}/api/auth/login/', payload={
            'username': self.identity['username'],
            'password': self.identity['password']})
        self.record('login', result)
        if result['status'] != 200:
            self.login_failed = result.get('error') or result['status']
            return False
        try:
            self.token = json.loads(result['body'])['access']
        except (ValueError, KeyError) as exc:
            # A 200 whose body cannot yield a token is a driver fault, not a
            # product one, and must be visible as such rather than as a silent
            # unauthenticated session.
            self.login_failed = f'200 but no usable token: {exc}'
            return False
        return True

    def refresh(self):
        team = self.identity['team_id']
        self.record('refresh', _request(
            'GET',
            f'{self.base}/api/games/{self.game_id}/teams/{team}/decisions/'
            f'round/{self.round_number}/summary/', self.token))

    def save(self, sequence):
        """One budget write, uniquely identified, with its outcome recorded."""
        team = self.identity['team_id']
        request_id = f"load-{self.identity['username']}-{sequence}-{uuid.uuid4().hex[:8]}"
        payload = {'rd_budget': f'{1_000_000 + sequence}',
                   'marketing_budget': '3000000',
                   'strategy_budget': '1000000', 'research_budget': '500000'}
        result = _request(
            'PATCH',
            f'{self.base}/api/games/{self.game_id}/teams/{team}/decisions/'
            f'round/{self.round_number}/budget/',
            self.token, payload, request_id)
        self.record('save', result)
        entry = {'request_id': request_id, 'status': result['status'],
                 'team_id': team}
        if result['status'] is not None and 200 <= result['status'] < 300:
            self.acknowledged_writes.append(entry)
        else:
            self.refused_writes.append(entry)

    def lock(self):
        team = self.identity['team_id']
        request_id = f"lock-{self.identity['username']}-{uuid.uuid4().hex[:8]}"
        result = _request(
            'POST',
            f'{self.base}/api/games/{self.game_id}/teams/{team}/decisions/'
            f'round/{self.round_number}/lock/', self.token, {}, request_id)
        self.record('lock', result)

    def run(self, duration, final_minute_writes):
        if not self.login():
            return
        deadline = time.time() + duration
        sequence = 0
        rng = random.Random(self.identity['username'])
        while time.time() < deadline:
            roll = rng.random()
            if roll < 0.55:
                self.refresh()
            else:
                sequence += 1
                self.save(sequence)
            time.sleep(rng.uniform(0.05, 0.35))
        # Final-minute traffic: every session writes hard at the deadline, and
        # one member per team attempts the lock, which is what actually happens
        # in the last sixty seconds of a round.
        self.phase = 'final-minute'
        for _ in range(final_minute_writes):
            sequence += 1
            self.save(sequence)
        if self.identity['member_index'] == 0:
            self.lock()


def sample_activity(database, stop, samples, interval=2.0):
    """What the database connections are actually doing, twice a second.

    Four hypotheses for the stall have now been eliminated by measurement --
    the final-minute burst, per-game lock contention, worker cold start and a
    WAL checkpoint. Rather than propose a fifth, this records state, wait event
    and query for every connection whenever any of them has been running longer
    than two seconds, which is what a stall looks like from inside the server.
    """
    import subprocess
    query = (
        "SELECT state, coalesce(wait_event_type,''), coalesce(wait_event,''), "
        "round(extract(epoch from (now() - query_start))::numeric, 2), "
        "left(regexp_replace(query, '\\s+', ' ', 'g'), 110) "
        "FROM pg_stat_activity WHERE datname = '" + database + "' "
        "AND state <> 'idle' ORDER BY query_start")
    while not stop.is_set():
        try:
            out = subprocess.run(
                ['psql', 'postgresql://donwh:***REMOVED-CREDENTIAL-V2-048***@192.168.50.38/postgres',
                 '-tAc', query], capture_output=True, text=True, timeout=10)
            rows = [r for r in out.stdout.strip().splitlines() if r.strip()]
            parsed = []
            for row in rows:
                parts = row.split('|')
                if len(parts) >= 5:
                    parsed.append({'state': parts[0], 'wait_type': parts[1],
                                   'wait_event': parts[2],
                                   'seconds': float(parts[3] or 0),
                                   'query': parts[4]})
            slow = [p for p in parsed if p['seconds'] > 2.0]
            if slow:
                samples.append({'at': time.time(), 'connections': len(parsed),
                                'slow': slow[:6]})
        except Exception:
            pass
        stop.wait(interval)


def sample_checkpoints(stop, samples, interval=2.0):
    """Checkpoint activity while the load runs.

    A WAL-triggered checkpoint flushes dirty buffers and can stall writes for
    seconds. The server-side stall at field load was about ten seconds with
    throughput collapsing during it, which is the shape a checkpoint makes, and
    the hypothesis is worth testing rather than asserting.
    """
    import subprocess
    query = ("SELECT checkpoints_timed, checkpoints_req, "
             "checkpoint_write_time, checkpoint_sync_time "
             "FROM pg_stat_bgwriter")
    while not stop.is_set():
        try:
            out = subprocess.run(
                ['psql', 'postgresql://donwh:***REMOVED-CREDENTIAL-V2-048***@192.168.50.38/postgres',
                 '-tAc', query], capture_output=True, text=True, timeout=10)
            parts = out.stdout.strip().split('|')
            if len(parts) == 4:
                samples.append({'at': time.time(),
                                'timed': int(parts[0]), 'requested': int(parts[1]),
                                'write_ms': float(parts[2]),
                                'sync_ms': float(parts[3])})
        except Exception:
            pass
        stop.wait(interval)


def sample_database(database, stop, samples, interval=2.0):
    """Peak database use has to be sampled while the load runs.

    The first field run read connection count after the profile finished and
    recorded 1, which is an idle stack rather than a peak. This samples on a
    thread until told to stop.
    """
    import subprocess
    query = ("SELECT count(*) FROM pg_stat_activity WHERE datname = "
             f"'{database}'")
    while not stop.is_set():
        try:
            out = subprocess.run(
                ['psql', 'postgresql://donwh:***REMOVED-CREDENTIAL-V2-048***@192.168.50.38/postgres',
                 '-tAc', query], capture_output=True, text=True, timeout=10)
            value = out.stdout.strip()
            if value.isdigit():
                samples.append(int(value))
        except Exception:
            pass
        stop.wait(interval)


def run_profile(base, identities, game_id, round_number, duration,
                final_minute_writes=3, verbose=True, database=None):
    sessions = [Session(base, identity, game_id, round_number)
                for identity in identities]
    threads = [threading.Thread(target=s.run,
                                args=(duration, final_minute_writes),
                                daemon=True) for s in sessions]
    connection_samples = []
    checkpoint_samples = []
    activity_samples = []
    stop = threading.Event()
    sampler = checkpointer = activity_sampler = None
    if database:
        sampler = threading.Thread(target=sample_database,
                                   args=(database, stop, connection_samples),
                                   daemon=True)
        sampler.start()
        checkpointer = threading.Thread(target=sample_checkpoints,
                                        args=(stop, checkpoint_samples),
                                        daemon=True)
        checkpointer.start()
        activity_sampler = threading.Thread(
            target=sample_activity, args=(database, stop, activity_samples),
            daemon=True)
        activity_sampler.start()

    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=duration + 600)
    elapsed = time.time() - started
    stop.set()
    for thread in (sampler, checkpointer, activity_sampler):
        if thread:
            thread.join(timeout=15)

    samples = [s for session in sessions for s in session.samples]
    interactive = [s for s in samples if s['kind'] in ('refresh', 'save', 'lock')]
    latencies = sorted(s['ms'] for s in interactive)

    def pct(p):
        if not latencies:
            return None
        index = min(len(latencies) - 1, int(round(p / 100 * len(latencies))) - 1)
        return round(latencies[max(0, index)], 1)

    statuses = {}
    for s in samples:
        key = str(s['status']) if s['status'] is not None else 'transport-failure'
        statuses[key] = statuses.get(key, 0) + 1

    transport = sum(1 for s in interactive if s['status'] is None)
    server_errors = sum(1 for s in interactive
                        if s['status'] is not None and s['status'] >= 500)
    business_refusals = sum(1 for s in interactive
                            if s['status'] is not None
                            and 400 <= s['status'] < 500)

    # Logins were recorded from the first run and reported in none of them.
    # Password verification is PBKDF2 at Django's default iteration count, so
    # 96 simultaneous logins are a large, purely CPU-bound burst -- and every
    # slow request in every run has been in the window just after it.
    logins = sorted(s['ms'] for s in samples if s['kind'] == 'login')
    login_stats = {
        'count': len(logins),
        'p50_ms': round(logins[len(logins) // 2], 1) if logins else None,
        'p95_ms': round(logins[max(0, int(round(0.95 * len(logins))) - 1)], 1)
        if logins else None,
        'max_ms': round(logins[-1], 1) if logins else None,
        'total_cpu_seconds_if_serial': round(sum(logins) / 1000, 1)
        if logins else None,
    }

    slowest = sorted(interactive, key=lambda x: -x['ms'])[:15]
    origin = min((s['at'] for s in samples), default=0)

    # Per-second buckets: one stall and a periodic stutter look identical in a
    # max, and the top-N list only shows the worst window. This shows whether
    # throughput collapses during the slow period, which separates a server
    # stall from a client that stopped issuing requests.
    buckets = {}
    for sample in interactive:
        second = int(sample['at'] - origin)
        bucket = buckets.setdefault(second, [])
        bucket.append(sample['ms'])
    timeline = [
        {'second': second, 'requests': len(values),
         'max_ms': round(max(values), 1),
         'p95_ms': round(sorted(values)[max(0, int(round(0.95 * len(values))) - 1)], 1)}
        for second, values in sorted(buckets.items())]
    checkpoints = {}
    if checkpoint_samples:
        first, last = checkpoint_samples[0], checkpoint_samples[-1]
        checkpoints = {
            'timed_during_run': last['timed'] - first['timed'],
            'requested_during_run': last['requested'] - first['requested'],
            'write_ms_during_run': round(last['write_ms'] - first['write_ms'], 1),
            'sync_ms_during_run': round(last['sync_ms'] - first['sync_ms'], 1),
            'seconds_when_checkpoint_started': [
                round(b['at'] - origin, 1)
                for a, b in zip(checkpoint_samples, checkpoint_samples[1:])
                if (b['timed'] + b['requested']) > (a['timed'] + a['requested'])],
        }

    return {
        'login': login_stats,
        'slow_activity_windows': [
            {'seconds_into_run': round(sample['at'] - origin, 1),
             'connections': sample['connections'], 'slow': sample['slow']}
            for sample in activity_samples][:12],
        'slow_activity_window_count': len(activity_samples),
        'checkpoints': checkpoints,
        'timeline_per_second': timeline,
        'slowest_seconds': sorted(timeline, key=lambda b: -b['max_ms'])[:8],
        'slowest_requests': [
            {'kind': s['kind'], 'ms': round(s['ms'], 1),
             'status': s['status'], 'phase': s['phase'],
             'seconds_into_run': round(s['at'] - origin, 1)}
            for s in slowest],
        'per_kind_max': {
            kind: round(max((x['ms'] for x in interactive
                             if x['kind'] == kind), default=0), 1)
            for kind in ('refresh', 'save', 'lock')},
        'per_phase_p95': {
            phase: round(sorted(x['ms'] for x in interactive
                                if x['phase'] == phase)[
                max(0, int(round(0.95 * len([x for x in interactive
                                             if x['phase'] == phase]))) - 1)], 1)
            for phase in ('steady', 'final-minute')
            if any(x['phase'] == phase for x in interactive)},
        'db_connection_samples': len(connection_samples),
        'db_connections_peak': max(connection_samples) if connection_samples else None,
        'db_connections_mean': (round(sum(connection_samples)
                                      / len(connection_samples), 1)
                                if connection_samples else None),
        'sessions_requested': len(identities),
        'sessions_authenticated': sum(1 for s in sessions if s.token),
        'login_failures': [s.login_failed for s in sessions if s.login_failed][:5],
        'elapsed_seconds': round(elapsed, 1),
        'requests_total': len(samples),
        'interactive_requests': len(interactive),
        'throughput_rps': round(len(samples) / elapsed, 1) if elapsed else None,
        'latency_ms': {'p50': pct(50), 'p95': pct(95), 'p99': pct(99),
                       'max': round(latencies[-1], 1) if latencies else None},
        'status_distribution': statuses,
        'transport_failures': transport,
        'server_errors': server_errors,
        'business_refusals_4xx': business_refusals,
        'error_rate_pct': round(
            100 * (transport + server_errors) / len(interactive), 4)
        if interactive else None,
        'acknowledged_writes': [w for s in sessions
                                for w in s.acknowledged_writes],
        'refused_writes': [w for s in sessions for w in s.refused_writes],
        'per_kind_p95': {
            kind: round(sorted(x['ms'] for x in interactive
                               if x['kind'] == kind)[
                min(len([x for x in interactive if x['kind'] == kind]) - 1,
                    max(0, int(round(0.95 * len([x for x in interactive
                                                 if x['kind'] == kind]))) - 1))], 1)
            for kind in ('refresh', 'save', 'lock')
            if any(x['kind'] == kind for x in interactive)},
    }
