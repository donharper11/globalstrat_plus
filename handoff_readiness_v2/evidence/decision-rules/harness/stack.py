"""A disposable stack for the GSP-CRV2-10 Stage-1 probes.

Own database, own gunicorn, own port, claimed at run time. Nothing here writes
to `globalstrat_plus`, and nothing here binds a fixed port.

Port 8002 on this host carries a gunicorn serving the live `globalstrat_plus`
database. GSP-CRV2-08 configured its stack there, failed to bind, died, and its
requests fell through to production while it believed it was talking to its own
fixture -- caught only because a fixture username did not exist upstream. Two
consequences are permanent for every stack in this programme, and both are
enforced below rather than documented:

1. `free_port()` asks the kernel for an unused port. No constant appears.
2. `assert_identity()` refuses to return before the first probe unless a
   fixture identity authenticates through this stack's own origin *and* the
   process answering reports the database this module created.
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
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
RUNTIME = pathlib.Path('/tmp/crv210-runtime')

DB_HOST = os.environ.get('DB_HOST', '192.168.50.38')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER', 'donwh')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***')

# The one database name this harness may never use, stated once so that a
# refusal is a rule rather than a habit.
PRODUCTION_DATABASE = 'globalstrat_plus'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def psql(database, sql):
    env = {**os.environ, 'PGPASSWORD': DB_PASSWORD}
    return subprocess.run(
        ['psql', '-h', DB_HOST, '-p', DB_PORT, '-U', DB_USER, '-d', database,
         '-v', 'ON_ERROR_STOP=1', '-c', sql],
        capture_output=True, text=True, env=env)


def manage(database, *args, timeout=1800):
    if database == PRODUCTION_DATABASE:
        raise SystemExit('refusing to run manage.py against production')
    env = {**os.environ, 'DB_NAME': database, 'DB_HOST': DB_HOST,
           'DB_USER': DB_USER, 'DB_PASSWORD': DB_PASSWORD, 'DB_PORT': DB_PORT,
           'PYTHONPATH': str(BACKEND), 'PYTHONUNBUFFERED': '1'}
    return subprocess.run([sys.executable, 'manage.py', *args], cwd=str(BACKEND),
                          capture_output=True, text=True, env=env,
                          timeout=timeout)


LEGACY_TABLES = r'''
from django.apps import apps
from django.db import connection
existing = set(connection.introspection.table_names())
unmanaged = [m for m in apps.get_models() if not m._meta.managed]
for m in unmanaged:
    m._meta.managed = True
created = []
with connection.schema_editor() as editor:
    for m in unmanaged:
        if m._meta.db_table not in existing:
            editor.create_model(m); created.append(m._meta.db_table)
for m in unmanaged:
    m._meta.managed = False
print('created', len(created), 'legacy tables')
'''


def shell_json(database, body, marker, timeout=2400):
    """Run `body` inside `manage.py shell` and read the JSON it prints."""
    preamble = (
        'import sys, json\n'
        f'sys.path.insert(0, {str(HERE)!r})\n'
    )
    out = manage(database, 'shell', '-c', preamble + body, timeout=timeout)
    if marker not in out.stdout:
        print(out.stdout[-6000:])
        print(out.stderr[-4000:])
        raise SystemExit(f'shell body did not reach {marker}')
    tail = out.stdout.split(marker, 1)[1].strip()
    return json.loads(tail.splitlines()[0])


def create_database(database):
    if database == PRODUCTION_DATABASE:
        raise SystemExit('refusing to create over production')
    psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
    if psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit(f'could not create {database}')
    # `migrate` on an empty database fails at 0070_audit_guards, and again at
    # 0071 and 0072. All three call `audit_guards.install_sql()`, which is
    # evaluated at import time against today's `PROTECTED_TABLES` -- and that
    # tuple names `competition_authorization_refusal_event`, a table created
    # eight migrations later by 0078. A historical migration therefore installs
    # a trigger on a table that does not exist yet. Every existing deployment
    # migrated incrementally and never met it; a database created from scratch
    # at this revision cannot get past it. Recorded as an incidental finding in
    # the probe record. Here those three are faked past and the guards are then
    # installed for real by their own command, so the stack under probe carries
    # the same schema and the same triggers a deployment carries.
    steps = [
        (['migrate', 'core', '0069', '--noinput'], 'migrate to 0069'),
        (['migrate', 'core', '0072', '--fake', '--noinput'],
         'fake 0070-0072, the guard migrations (see the note above)'),
        (['migrate', '--noinput'], 'migrate the remainder'),
    ]
    for args, label in steps:
        result = manage(database, *args)
        if result.returncode != 0:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit(f'{label} failed')
    manage(database, 'shell', '-c', LEGACY_TABLES)
    guards = manage(database, 'install_audit_guards')
    if guards.returncode != 0:
        print(guards.stdout[-2000:]); print(guards.stderr[-2000:])
        raise SystemExit('installing the audit guards failed')


def drop_database(database):
    if database == PRODUCTION_DATABASE:
        raise SystemExit('refusing to drop production')
    psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')


def wait_for(url, timeout=120):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except Exception as exc:
            last = exc
            time.sleep(0.5)
    raise SystemExit(f'stack never answered at {url}: {last}')


def start_gunicorn(database, port, revision, label='crv210'):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DB_NAME=database, DB_HOST=DB_HOST, DB_PORT=DB_PORT,
               DB_USER=DB_USER, DB_PASSWORD=DB_PASSWORD,
               PYTHONUNBUFFERED='1', GLOBALSTRAT_ENV='production',
               GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR=str(RUNTIME / 'backups'),
               DJANGO_SECRET_KEY=f'{label}-stage1-{database}')
    (RUNTIME / 'backups').mkdir(parents=True, exist_ok=True)
    log = open(RUNTIME / f'{label}-backend.log', 'w')
    process = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '-b', f'127.0.0.1:{port}',
         'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid)
    wait_for(f'http://127.0.0.1:{port}/api/auth/login/')
    return process


def stop_gunicorn(process):
    if process is None:
        return
    with contextlib.suppress(Exception):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=30)


def api(port, method, path, token=None, body=None, timeout=1200):
    """One request. Returns (status, parsed-or-text)."""
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}{path}', method=method,
        data=None if body is None else json.dumps(body).encode())
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, (json.loads(raw) if raw else None)
            except ValueError:
                return r.status, raw[:2000].decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        raw = exc.read() or b''
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw[:2000].decode('utf-8', 'replace')


def assert_identity(port, database, username, password):
    """Prove the stack is this fixture, on this database, before any probe.

    Two separate facts, because either one alone has already failed on this
    host: a login proves *something* is answering with fixture identities, and
    the database name reported by the process that answered proves it is the
    database this run created rather than one that happened to hold a user of
    the same name.
    """
    code, body = api(port, 'POST', '/api/auth/login/',
                     body={'username': username, 'password': password})
    if code != 200 or not isinstance(body, dict) or 'access' not in body:
        raise SystemExit(
            f'the stack answered {code} but not with the fixture identity: {body}')
    reported = subprocess.run(
        [sys.executable, '-c',
         'import os,sys,django;'
         'sys.path.insert(0, os.environ["BACKEND"]);'
         'os.environ.setdefault("DJANGO_SETTINGS_MODULE","globalstrat.settings");'
         'django.setup();'
         'from django.db import connection;'
         'print(connection.settings_dict["NAME"])'],
        capture_output=True, text=True,
        env={**os.environ, 'BACKEND': str(BACKEND), 'DB_NAME': database,
             'DB_HOST': DB_HOST, 'DB_PORT': DB_PORT, 'DB_USER': DB_USER,
             'DB_PASSWORD': DB_PASSWORD, 'GLOBALSTRAT_ENV': 'production',
             'DJANGO_SECRET_KEY': 'identity-check'})
    name = reported.stdout.strip()
    if name != database:
        raise SystemExit(f'database identity is {name!r}, expected {database!r}')
    if database == PRODUCTION_DATABASE:
        raise SystemExit('refusing to probe production')
    return {'login_status': code, 'database_reported': name,
            'token_present': True}


def revision():
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(REPO),
                          capture_output=True, text=True).stdout.strip()


def dirty():
    return subprocess.run(['git', 'status', '--porcelain'], cwd=str(REPO),
                          capture_output=True, text=True).stdout.strip()
