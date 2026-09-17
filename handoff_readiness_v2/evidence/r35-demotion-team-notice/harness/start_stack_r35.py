"""Backend + built frontend on ONE origin, against the disposable database.

Same-origin because the frontend's API base is `/api`: serving the build and
proxying `/api` from one port is what the deployment does, and a walkthrough
that needs CORS configured specially is not a walkthrough of the product.

Ports are claimed at run time. Port 8002 carries the production gunicorn
against the real database; binding there would silently read live data.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORKTREE = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                        '/agent-ad31a78c64885fc47')
BACKEND = WORKTREE / 'backend'
BUILD = WORKTREE / 'frontend' / 'globalstrat-frontend' / 'build'
SERVE_APP = (WORKTREE / 'handoff_readiness_v2' / 'evidence'
             / 'post-close-disputes' / 'harness' / 'serve_app.py')
SCRATCH = pathlib.Path(__file__).resolve().parent
RUNTIME = SCRATCH / 'runtime'


def db_env():
    env = {}
    for line in (SCRATCH / 'dbenv').read_text().splitlines():
        if line.startswith('export '):
            key, _, value = line[len('export '):].partition('=')
            env[key] = value
    return env


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for(url, timeout=180):
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


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    backend_port, app_port = free_port(), free_port()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE,
                              capture_output=True, text=True).stdout.strip()

    # GLOBALSTRAT_ENV=production so middleware and settings match the
    # deployment. That guard refuses to boot without explicit secrets, which is
    # the control working; disposable values are supplied rather than weakening
    # it.
    env = dict(os.environ, **db_env(), PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production', GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR=str(RUNTIME / 'backups'),
               COMPETITION_REQUIRE_CLEAN_BUILD='false',
               DJANGO_SECRET_KEY='r35-demotion-notice-verification')

    backend_log = open(RUNTIME / 'backend.log', 'w')
    backend = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py',
         '-b', f'127.0.0.1:{backend_port}', 'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=backend_log,
        stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    wait_for(f'http://127.0.0.1:{backend_port}/api/auth/login/')

    app_log = open(RUNTIME / 'app.log', 'w')
    app = subprocess.Popen(
        [sys.executable, str(SERVE_APP), str(BUILD),
         f'http://127.0.0.1:{backend_port}', str(app_port)],
        stdout=app_log, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    wait_for(f'http://127.0.0.1:{app_port}/')

    # Prove the stack serves THIS fixture, not something else answering here.
    fixture = json.loads((SCRATCH / 'fixture.json').read_text())
    body = json.dumps({'username': fixture['demoted_student'],
                       'password': fixture['password']}).encode()
    req = urllib.request.Request(
        f'http://127.0.0.1:{app_port}/api/auth/login/', data=body,
        method='POST')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read())
    if 'access' not in payload:
        raise SystemExit('the stack answered but not with the fixture')

    (RUNTIME / 'stack.pids').write_text(f'{backend.pid}\n{app.pid}\n')
    (RUNTIME / 'stack.ports').write_text(json.dumps(
        {'backend': backend_port, 'app': app_port}) + '\n')
    print(f'backend pid {backend.pid} on {backend_port}')
    print(f'app     pid {app.pid} on {app_port}')
    print(f'fixture identity confirmed: game {fixture["game_id"]} '
          f'({fixture["game_name"]}), demoted team '
          f'{fixture["demoted_team_name"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
