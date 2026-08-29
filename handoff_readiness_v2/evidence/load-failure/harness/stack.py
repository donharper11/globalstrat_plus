"""A disposable integrated stack: own database, own gunicorn, own port.

The production backend serves 8002 against `globalstrat_plus`. Nothing here
touches either. Every run creates a database, migrates it, seeds a field-sized
cohort, starts gunicorn with the same worker configuration the deployment uses,
and drops the database afterwards.

The worker count is deliberately not raised for the test. Three sync workers is
what `backend/gunicorn.conf.py` deploys, so three is what the field profile has
to survive; measuring a stack tuned for the measurement would say nothing about
the deployment.
"""
import contextlib
import json
import os
import pathlib
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parents[4] / 'backend'
ADVERSARIAL = HERE.parents[1] / 'adversarial-balance' / 'harness'
sys.path.insert(0, str(ADVERSARIAL))
import inventory_run as R  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for(url, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code          # any HTTP answer means it is serving
        except Exception as exc:     # not listening yet
            last = exc
            time.sleep(0.5)
    raise SystemExit(f'stack never answered at {url}: {last}')


@contextlib.contextmanager
def disposable_stack(label, seed=True):
    """Yield (base_url, database, seeded) with everything torn down after."""
    database = f'gsp_load_{label}_{time.strftime("%H%M%S")}'
    port = free_port()
    print(f'Creating disposable database {database}', flush=True)
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    process = None
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)

        seeded = None
        if seed:
            body = (
                'import sys, json\n'
                f'sys.path.insert(0, {str(HERE)!r})\n'
                f'sys.path.insert(0, {str(ADVERSARIAL)!r})\n'
                'import seed_field\n'
                'print("---SEED---")\n'
                'print(json.dumps(seed_field.run(), default=str))\n'
            )
            result = R.manage(database, 'shell', '-c', body, timeout=1800)
            if '---SEED---' not in result.stdout:
                print(result.stdout[-4000:]); print(result.stderr[-4000:])
                raise SystemExit('seeding failed')
            seeded = json.loads(
                result.stdout.split('---SEED---', 1)[1].strip().splitlines()[0])
            print(f"Seeded game {seeded['game_id']}: {seeded['teams']} teams, "
                  f"{len(seeded['identities'])} identities", flush=True)

        env = dict(os.environ, DB_NAME=database, PYTHONUNBUFFERED='1',
                   GLOBALSTRAT_ENV='production')
        log = open(HERE.parent / f'gunicorn-{label}.log', 'w')
        process = subprocess.Popen(
            ['gunicorn', '-c', 'gunicorn.conf.py',
             '-b', f'127.0.0.1:{port}', 'globalstrat.wsgi:application'],
            cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid)
        base = f'http://127.0.0.1:{port}'
        wait_for(f'{base}/api/auth/login/')
        print(f'Stack up on {base} (pid {process.pid}, 3 sync workers)',
              flush=True)
        yield base, database, seeded
    finally:
        if process is not None:
            with contextlib.suppress(Exception):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=30)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}', flush=True)
