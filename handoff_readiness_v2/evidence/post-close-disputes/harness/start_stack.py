#!/usr/bin/env python3
"""Bring up the CRV2-08 stack: backend on 8002, app on 8003, one origin."""
import os, pathlib, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BUILD = REPO / 'frontend' / 'globalstrat-frontend' / 'build'
# Pids, ports and server logs are machine state, not evidence; they do not
# belong in the repository.
RUNTIME = pathlib.Path('/tmp/crv208-runtime')
sys.path.insert(0, str(EVIDENCE.parent / 'load-failure' / 'harness'))
import stack as S  # noqa: E402

DATABASE = 'gsp_crv208_disputes'
# Ports are claimed at run time, never fixed. Port 8002 already carries a
# gunicorn serving the real globalstrat_plus database: binding there fails
# silently enough that requests land on that server instead, and a walkthrough
# would have been reading live data while reporting on the fixture.
BACKEND_PORT, APP_PORT = S.free_port(), S.free_port()


def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, DB_NAME=DATABASE, PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production', GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR='/tmp/crv208-backups',
               DJANGO_SECRET_KEY='crv208-walkthrough',
               DB_PASSWORD=os.environ['DB_PASSWORD'])
    RUNTIME.mkdir(parents=True, exist_ok=True)
    backend_log = open(RUNTIME / 'stack-backend.log', 'w')
    backend = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '-b', f'127.0.0.1:{BACKEND_PORT}',
         'globalstrat.wsgi:application'],
        cwd=str(REPO / 'backend'), env=env, stdout=backend_log,
        stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    S.wait_for(f'http://127.0.0.1:{BACKEND_PORT}/api/auth/login/')
    app_log = open(RUNTIME / 'stack-app.log', 'w')
    app = subprocess.Popen(
        [sys.executable, str(HERE / 'serve_app.py'), str(BUILD),
         f'http://127.0.0.1:{BACKEND_PORT}', str(APP_PORT)],
        stdout=app_log, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
    S.wait_for(f'http://127.0.0.1:{APP_PORT}/')
    print(f'backend pid {backend.pid} on {BACKEND_PORT}')
    print(f'app     pid {app.pid} on {APP_PORT}')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / 'stack.pids').write_text(f'{backend.pid}\n{app.pid}\n')
    (RUNTIME / 'stack.ports').write_text(
        f'{{"backend": {BACKEND_PORT}, "app": {APP_PORT}, '
        f'"database": "{DATABASE}"}}\n')
    # Prove the stack is serving the fixture, not something else that happened
    # to answer on this port.
    import json as _json, urllib.request as _u
    req = _u.Request(f'http://127.0.0.1:{APP_PORT}/api/auth/login/',
                     data=_json.dumps({'username': 'crv208_student_1',
                                       'password': 'crv208-pass'}).encode(),
                     method='POST')
    req.add_header('Content-Type', 'application/json')
    with _u.urlopen(req, timeout=60) as r:
        if 'access' not in _json.loads(r.read()):
            raise SystemExit('the stack answered but not with the fixture')
    print('fixture identity confirmed through the app origin')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
