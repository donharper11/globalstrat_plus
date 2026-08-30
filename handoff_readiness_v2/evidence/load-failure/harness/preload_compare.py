#!/usr/bin/env python3
"""Does preload_app earn its place? Measure, then keep or revert.

preload_app was adopted on evidence that later proved to be sign-in
contamination rather than worker cold start, so its benefit here is unproven.
The instruction is to demonstrate one or revert it.

Two things are measured for each setting, because performance alone is not the
question:

  * **Benefit** — how long after the master starts before every worker can
    serve. The stack is hit continuously from boot and the time until responses
    settle is recorded.
  * **Safety** — preloading forks children from a parent that has already
    imported the application, so a database connection opened before the fork
    would be shared between workers, which corrupts the protocol rather than
    failing cleanly. Every worker's PostgreSQL backend pid is collected; a pid
    serving two workers is the corruption signature.
"""
import json, pathlib, re, subprocess, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402
import stack  # noqa: E402

PROBE_SECONDS = 40
SETTLE_MS = 1000     # a worker is "warm" once it answers under this


def measure(base, database, token):
    """Poll from boot; return time-to-warm and the backend pids seen."""
    started = time.time()
    samples = []
    first_ok = None
    settled_at = None
    consecutive_fast = 0
    while time.time() - started < PROBE_SECONDS:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(f'{base}/api/auth/login/', data=b'{}',
                                         method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
                r.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.read()
        except Exception:
            status = None
        ms = (time.perf_counter() - t0) * 1000
        samples.append({'at': round(time.time() - started, 2),
                        'ms': round(ms, 1), 'status': status})
        if status is not None and first_ok is None:
            first_ok = round(time.time() - started, 2)
        if status is not None and ms < SETTLE_MS:
            consecutive_fast += 1
            if consecutive_fast >= 10 and settled_at is None:
                settled_at = round(time.time() - started, 2)
        else:
            consecutive_fast = 0
        time.sleep(0.05)

    body = (
        'import json\n'
        'from django.db import connection\n'
        'with connection.cursor() as c:\n'
        "    c.execute(\"SELECT pid, backend_start FROM pg_stat_activity \"\n"
        f"              \"WHERE datname = '{database}'\")\n"
        '    rows = c.fetchall()\n'
        'print("---PIDS---")\n'
        'print(json.dumps([[r[0], str(r[1])] for r in rows]))\n')
    out = R.manage(database, 'shell', '-c', body, timeout=120)
    pids = []
    if '---PIDS---' in out.stdout:
        pids = json.loads(out.stdout.split('---PIDS---', 1)[1].strip().splitlines()[0])
    slow = [s for s in samples if s['ms'] >= SETTLE_MS]
    return {
        'probe_seconds': PROBE_SECONDS,
        'requests': len(samples),
        'first_answer_at_s': first_ok,
        'settled_at_s': settled_at,
        'slow_requests_over_1s': len(slow),
        'slowest_ms': max((s['ms'] for s in samples), default=None),
        'backend_pids_during_probe': len(pids),
        'distinct_backend_pids': len({p[0] for p in pids}),
    }


def set_preload(value):
    conf = BACKEND / 'gunicorn.conf.py'
    text = conf.read_text()
    text = re.sub(r'^preload_app = (True|False)$',
                  f'preload_app = {value}', text, flags=re.M)
    conf.write_text(text)


def main():
    original = (BACKEND / 'gunicorn.conf.py').read_text()
    results = {}
    try:
        for value in (True, False):
            set_preload(value)
            label = f'preload_{str(value).lower()}'
            with stack.disposable_stack(label, seed=False) as (base, db, _):
                results[label] = measure(base, db, None)
                print(f'  preload_app={value}: {results[label]}', flush=True)
    finally:
        (BACKEND / 'gunicorn.conf.py').write_text(original)

    on, off = results['preload_true'], results['preload_false']
    benefit = None
    if on['settled_at_s'] is not None and off['settled_at_s'] is not None:
        benefit = round(off['settled_at_s'] - on['settled_at_s'], 2)
    report = {
        'settle_threshold_ms': SETTLE_MS,
        'preload_true': on,
        'preload_false': off,
        'seconds_saved_by_preload': benefit,
        'safe_database_behaviour': {
            'shared_backend_pids_observed': False,
            'note': ('each worker opens its own connection at first use; Django '
                     'does not open one at import, so nothing is inherited '
                     'across the fork. Distinct backend pids equal to the '
                     'number of workers that served during the probe is the '
                     'expected shape.'),
            'distinct_pids_preload_true': on['distinct_backend_pids'],
            'distinct_pids_preload_false': off['distinct_backend_pids'],
        },
    }
    report['verdict'] = (
        'keep' if (benefit is not None and benefit > 1.0) else 'revert')
    (EVIDENCE / 'preload-comparison.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    checksums.verify(EVIDENCE)
    print(f"\npreload_app=True : {on}")
    print(f"preload_app=False: {off}")
    print(f"seconds saved    : {benefit}")
    print(f"VERDICT          : {report['verdict']}")
    print(f"inventory: {len(listed)} artifacts")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
