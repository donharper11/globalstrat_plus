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
        self.samples = []
        self.acknowledged_writes = []
        self.refused_writes = []
        self.login_failed = None

    def record(self, kind, result):
        self.samples.append({'kind': kind, 'status': result['status'],
                             'ms': result['ms'],
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
        for _ in range(final_minute_writes):
            sequence += 1
            self.save(sequence)
        if self.identity['member_index'] == 0:
            self.lock()


def run_profile(base, identities, game_id, round_number, duration,
                final_minute_writes=3, verbose=True):
    sessions = [Session(base, identity, game_id, round_number)
                for identity in identities]
    threads = [threading.Thread(target=s.run,
                                args=(duration, final_minute_writes),
                                daemon=True) for s in sessions]
    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=duration + 600)
    elapsed = time.time() - started

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

    return {
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
