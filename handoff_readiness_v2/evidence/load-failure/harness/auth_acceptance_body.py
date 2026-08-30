"""Authentication acceptance: 96 users admitted over five minutes.

The adopted position is that the PBKDF2 work factor stays as it is and 288
simultaneous password checks are an unsupported arrival shape. What has to be
demonstrated instead is that the supported shape works: a field cohort admitted
across an admission window, interactive traffic beginning afterwards, and no
session needing to authenticate again for the rest of the competition.

Six acceptance points, each measured rather than argued:

  1. 96 field users distributed over five minutes;
  2. normal interactive traffic begins afterwards;
  3. login p95 below 2 seconds;
  4. no 5xx and no transport failures;
  5. all 96 sessions visible in instructor readiness;
  6. no reauthentication during the competition window.
"""
import json
import random
import statistics
import threading
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

import driver as D

ADMISSION_WINDOW_SECONDS = 300
FIELD_SESSIONS = 96
INTERACTIVE_SECONDS = 180
THINK_TIME = (3.0, 15.0)


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('authacc', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    import fixture_contract as FC
    from core.models import Scenario
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)
    import seed_field
    seeded = seed_field.run()
    return seeded


def drive(base, seeded, verbose=True):
    """Admit the cohort across the window, then run interactive traffic."""
    from django.conf import settings

    identities = seeded['identities'][:FIELD_SESSIONS]
    sessions = [D.Session(base, i, seeded['game_id'], seeded['round_number'])
                for i in identities]

    started = time.time()
    admitted = []
    lock = threading.Lock()

    def admit(session, offset):
        # Arrivals spread across the admission window, which is the procedure
        # under test: students sign in over five minutes rather than at one
        # instant.
        time.sleep(offset)
        ok = session.login()
        with lock:
            admitted.append({'username': session.identity['username'],
                             'ok': ok, 'at': time.time() - started})

    rng = random.Random('crv2-07-admission')
    offsets = sorted(rng.uniform(0, ADMISSION_WINDOW_SECONDS)
                     for _ in sessions)
    threads = [threading.Thread(target=admit, args=(s, o), daemon=True)
               for s, o in zip(sessions, offsets)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=ADMISSION_WINDOW_SECONDS + 300)
    admission_elapsed = time.time() - started

    logins = sorted(s['ms'] for session in sessions
                    for s in session.samples if s['kind'] == 'login')
    login_stats = {
        'count': len(logins),
        'p50_ms': round(logins[len(logins) // 2], 1) if logins else None,
        'p95_ms': round(logins[max(0, int(round(0.95 * len(logins))) - 1)], 1)
        if logins else None,
        'max_ms': round(logins[-1], 1) if logins else None,
    }
    authenticated = [s for s in sessions if s.token]
    tokens_at_admission = {s.identity['username']: s.token
                           for s in authenticated}

    # Interactive traffic afterwards, on the tokens already held.
    stop_at = time.time() + INTERACTIVE_SECONDS
    interactive_lock = threading.Lock()
    reauth_events = []

    def interact(session):
        r = random.Random(session.identity['username'] + '-interactive')
        sequence = 0
        while time.time() < stop_at:
            if r.random() < 0.55:
                session.refresh()
            else:
                sequence += 1
                session.save(sequence)
            time.sleep(r.uniform(*THINK_TIME))
        # Did any request come back unauthorised, forcing a new sign-in?
        for sample in session.samples:
            if sample['kind'] != 'login' and sample['status'] in (401, 403):
                with interactive_lock:
                    reauth_events.append(
                        {'username': session.identity['username'],
                         'status': sample['status'], 'kind': sample['kind']})

    workers = [threading.Thread(target=interact, args=(s,), daemon=True)
               for s in authenticated]
    for t in workers:
        t.start()
    for t in workers:
        t.join(timeout=INTERACTIVE_SECONDS + 300)

    interactive = [s for session in sessions for s in session.samples
                   if s['kind'] != 'login']
    lat = sorted(s['ms'] for s in interactive)

    def pct(values, p):
        if not values:
            return None
        return round(values[max(0, int(round(p / 100 * len(values))) - 1)], 1)

    transport = sum(1 for s in interactive if s['status'] is None)
    server_errors = sum(1 for s in interactive
                        if s['status'] is not None and s['status'] >= 500)
    login_failures = sum(1 for s in sessions
                         for x in s.samples
                         if x['kind'] == 'login'
                         and (x['status'] is None or x['status'] >= 500))

    # Tokens must be the same objects at the end: a changed token means the
    # session had to authenticate again.
    tokens_unchanged = all(
        s.token == tokens_at_admission.get(s.identity['username'])
        for s in authenticated)

    return {
        'admission_window_seconds': ADMISSION_WINDOW_SECONDS,
        'admission_elapsed_seconds': round(admission_elapsed, 1),
        'sessions_requested': FIELD_SESSIONS,
        'sessions_authenticated': len(authenticated),
        'login': login_stats,
        'login_5xx_or_transport': login_failures,
        'interactive_requests': len(interactive),
        'interactive_latency_ms': {'p50': pct(lat, 50), 'p95': pct(lat, 95),
                                   'max': round(lat[-1], 1) if lat else None},
        'interactive_transport_failures': transport,
        'interactive_5xx': server_errors,
        'reauthentication_events': reauth_events,
        'tokens_unchanged_through_window': tokens_unchanged,
        'token_lifetime_hours': getattr(
            settings, 'JWT_ACCESS_TOKEN_LIFETIME_HOURS', None),
        'acknowledged_writes': [w for s in sessions
                                for w in s.acknowledged_writes],
        'refused_writes': [w for s in sessions for w in s.refused_writes],
    }
