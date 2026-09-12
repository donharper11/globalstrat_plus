"""Bring up the CRV2-13 stack: backend + built frontend on ONE origin.

Same-origin on purpose, and for the same reason CRV2-08 gave: the frontend's
default API base is `/api`, so serving the build and proxying `/api` from a
single port is what the deployment does. A walkthrough that needs CORS
configured specially is not a walkthrough of the product.

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

WORKTREE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees/agent-a0ae8bfea94e98414')
BACKEND = WORKTREE / 'backend'
BUILD = WORKTREE / 'frontend' / 'globalstrat-frontend' / 'build'
SERVE_APP = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/handoff_readiness_v2/evidence'
    '/post-close-disputes/harness/serve_app.py')
RUNTIME = pathlib.Path(
    '/tmp/claude-1000/-home-ubuntu-projects-globalstrat-'
    '/1cb17cc8-9a2a-4eff-a5cd-1faf83b7de0e/scratchpad/runtime')

DB = dict(DB_NAME='gsp_crv213', DB_HOST='127.0.0.1', DB_PORT='55432',
          DB_USER='postgres', DB_PASSWORD='crv213pass')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


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


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    backend_port, app_port = free_port(), free_port()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE,
                              capture_output=True, text=True).stdout.strip()

    # GLOBALSTRAT_ENV=production so middleware/settings match the deployment.
    # That guard refuses to boot without explicit secrets, which is the control
    # working, so disposable values are supplied rather than weakening it.
    env = dict(os.environ, **DB, PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production', GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR=str(RUNTIME / 'backups'),
               COMPETITION_REQUIRE_CLEAN_BUILD='false',
               DJANGO_SECRET_KEY='crv213-frontend-verification')

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

    # Prove the stack serves the fixture, not something else answering here.
    fixture = json.loads((RUNTIME.parent / 'fixture.json').read_text())
    body = json.dumps({'username': fixture['students'][0]['username'],
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
        {'backend': backend_port, 'app': app_port,
         'database': DB['DB_NAME']}) + '\n')
    print(f'backend pid {backend.pid} on {backend_port}')
    print(f'app     pid {app.pid} on {app_port}')
    print(f'fixture identity confirmed: game {fixture["game_id"]} '
          f'({fixture["game_name"]})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
