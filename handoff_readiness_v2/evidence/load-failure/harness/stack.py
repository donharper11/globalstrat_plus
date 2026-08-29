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
BACKEND = HERE.parents[3] / 'backend'  # .../globalstrat+/backend
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
                # Compute first, print the marker afterwards. Printing it
                # first put the seeder's own scenario-loading output between
                # the marker and the JSON, so a failure surfaced as a JSON
                # decode error over unrelated log lines.
                'seeded = seed_field.run()\n'
                'print("---SEED---")\n'
                'print(json.dumps(seeded, default=str))\n'
            )
            result = R.manage(database, 'shell', '-c', body, timeout=1800)
            if '---SEED---' not in result.stdout:
                print(result.stdout[-6000:]); print(result.stderr[-4000:])
                raise SystemExit('seeding failed; see the traceback above')
            tail = result.stdout.split('---SEED---', 1)[1].strip()
            try:
                seeded = json.loads(tail.splitlines()[0])
            except (ValueError, IndexError):
                print(tail[:4000]); print(result.stderr[-2000:])
                raise SystemExit('seeding raised; see the traceback above')
            print(f"Seeded game {seeded['game_id']}: {seeded['teams']} teams, "
                  f"{len(seeded['identities'])} identities", flush=True)

        # GLOBALSTRAT_ENV=production is deliberate: the load profile should
        # exercise the settings the deployment uses, not a debug path. That
        # guard refuses to boot without explicit secrets, which is the control
        # working, so test-only values are supplied for this disposable stack
        # rather than weakening the environment.
        env = dict(os.environ, DB_NAME=database, PYTHONUNBUFFERED='1',
                   GLOBALSTRAT_ENV='production',
                   DJANGO_SECRET_KEY='crv2-07-load-test-key-' + database,
                   DB_PASSWORD=os.environ.get('DB_PASSWORD',
                                              '***REMOVED-CREDENTIAL-V2-048***'))
        log = open(HERE.parent / f'gunicorn-{label}.log', 'w')
        process = subprocess.Popen(
            ['gunicorn', '-c', 'gunicorn.conf.py',
             '-b', f'127.0.0.1:{port}', 'globalstrat.wsgi:application'],
            cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid)
        base = f'http://127.0.0.1:{port}'
        wait_for(f'{base}/api/auth/login/')
        # Read the worker count from the config rather than asserting it: the
        # message said "3 sync workers" for a run that had 17, which is the
        # kind of caption that quietly misdescribes evidence.
        conf = (BACKEND / 'gunicorn.conf.py').read_text()
        workers = next((line.split('=')[1].strip()
                        for line in conf.splitlines()
                        if line.startswith('workers')), '?')
        print(f'Stack up on {base} (pid {process.pid}, {workers} sync workers)',
              flush=True)
        yield base, database, seeded
    finally:
        if process is not None:
            with contextlib.suppress(Exception):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=30)
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}', flush=True)
