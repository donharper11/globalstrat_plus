"""Ad-hoc API probe against the disposable stack: apicall.py <user> <METHOD> <path> [json-body]

Signs in as <user> (fixture password) and prints status + body. Used to check
server state independently of what a screen shows.
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

SCRATCH = pathlib.Path(__file__).resolve().parent
fx = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']


def call(method, path, body=None, token=None, lang=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    if lang:
        req.add_header('Accept-Language', lang)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        status = e.code
    try:
        return status, json.loads(txt)
    except Exception:
        return status, txt


def login(user, password=None):
    s, b = call('POST', '/api/auth/login/', {'username': user, 'password': password or fx['password']})
    return b.get('access') if isinstance(b, dict) else None


if __name__ == '__main__':
    user, method, path = sys.argv[1:4]
    body = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    pw = None
    if ':' in user:
        user, pw = user.split(':', 1)
    tok = login(user, pw)
    s, b = call(method, path, body, tok)
    print(s)
    print(json.dumps(b, indent=1, ensure_ascii=False)[:6000] if not isinstance(b, str) else b[:3000])
