"""Backend + built frontend on one origin, for the CE walkthrough.

Adapted from evidence/open-interface-defects/harness/start_stack.py. Ports are
ephemeral (8002 carries production against the real database on this host).
Phase 2 narratives must not reach a model: every LLM URL points at an
unreachable port so the template fallback is what the walkthrough sees.
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

SCRATCH = pathlib.Path(__file__).resolve().parent
WORKTREE = SCRATCH.parents[3]
BACKEND = WORKTREE / 'backend'
BUILD = WORKTREE / 'frontend' / 'globalstrat-frontend' / 'build'
SERVE_APP = (WORKTREE / 'handoff_readiness_v2' / 'evidence'
             / 'post-close-disputes' / 'harness' / 'serve_app.py')
RUNTIME = SCRATCH / 'runtime'
UNREACHABLE = 'http://127.0.0.1:9/v1/chat/completions'


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


def wait_for(url, timeout=900):
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
    raise SystemExit('stack never answered at %s: %s' % (url, last))


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not BUILD.is_dir():
        raise SystemExit('no build at %s -- run npm run build first' % BUILD)
    backend_port, app_port = free_port(), free_port()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE,
                              capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, **db_env(), PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production', GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR=str(RUNTIME / 'backups'),
               COMPETITION_REQUIRE_CLEAN_BUILD='false',
               COMPETITION_RECOVERY_ENABLED='true',
               LLM_GATEWAY_URL=UNREACHABLE, NARRATIVE_LLM_URL=UNREACHABLE,
               DASHSCOPE_COMPATIBLE_URL=UNREACHABLE,
               DASHSCOPE_MODEL='unreachable-endpoint',
               DJANGO_SECRET_KEY='walkthrough-ce-2026-09-23')
    for stale in ('DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_PORT'):
        env[stale] = db_env()[stale]

    backend_log = open(RUNTIME / 'backend.log', 'w')
    backend = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '--timeout', '600',
         '-b', '127.0.0.1:%d' % backend_port, 'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=backend_log,
        stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    wait_for('http://127.0.0.1:%d/api/auth/login/' % backend_port)

    app_log = open(RUNTIME / 'app.log', 'w')
    app = subprocess.Popen(
        [sys.executable, str(SERVE_APP), str(BUILD),
         'http://127.0.0.1:%d' % backend_port, str(app_port)],
        stdout=app_log, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    wait_for('http://127.0.0.1:%d/' % app_port)

    fixture = json.loads((SCRATCH / 'fixture.json').read_text())
    body = json.dumps({'username': fixture['instructor'],
                       'password': fixture['password']}).encode()
    request = urllib.request.Request(
        'http://127.0.0.1:%d/api/auth/login/' % app_port, data=body,
        method='POST')
    request.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read())
    if 'access' not in payload:
        raise SystemExit('the stack answered but not with the fixture')

    (RUNTIME / 'stack.pids').write_text('%d\n%d\n' % (backend.pid, app.pid))
    (RUNTIME / 'stack.ports').write_text(json.dumps(
        {'backend': backend_port, 'app': app_port}) + '\n')
    print('backend pid %d on %d' % (backend.pid, backend_port))
    print('app     pid %d on %d' % (app.pid, app_port))
    print('fixture identity confirmed: instructor %s on scenario %s'
          % (fixture['instructor'], fixture['scenario_name']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
