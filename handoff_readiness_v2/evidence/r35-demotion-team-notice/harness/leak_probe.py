"""Production grain: can a rival account reach this team's demotion notice?

The focused test asserts this against the middleware in-process. This asks the
running stack, over HTTP, through the same origin a browser uses.

It also reads back the OTHER demoted firm -- the one that outscored nobody
above it -- to show the second wording variant on a real resolved round.
"""
import json
import pathlib
import urllib.error
import urllib.request

SP = pathlib.Path('/tmp/claude-1000/-home-ubuntu-projects-globalstrat-'
                  '/1cb17cc8-9a2a-4eff-a5cd-1faf83b7de0e/scratchpad')
fx = json.loads((SP / 'fixture.json').read_text())
ports = json.loads((SP / 'runtime' / 'stack.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']
RND = fx['round_number']
GAME = fx['game_id']


def login(username):
    body = json.dumps({'username': username,
                       'password': fx['password']}).encode()
    request = urllib.request.Request(
        BASE + '/api/auth/login/', data=body, method='POST')
    request.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())['access']


def get(token, path, language='en'):
    request = urllib.request.Request(BASE + path)
    request.add_header('Authorization', 'Bearer ' + token)
    request.add_header('Accept-Language', language)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:300].decode('utf-8', 'replace')


def results_path(team_id):
    return '/api/games/%d/teams/%d/results/round/%d/' % (GAME, team_id, RND)


own_team = fx['demoted_team_id']
own_token = login(fx['demoted_student'])
rival_token = login(fx['rival_student'])

print('--- a rival (a firm that COMPETED) reaching the demoted team ---')
status, body = get(rival_token, results_path(own_team))
print('  status=%s body=%s' % (status, str(body)[:160]))
print('  REFUSED: %s' % (status == 403))

print('--- the owning team reading its own ---')
status, body = get(own_token, results_path(own_team))
notices = body.get('inactivity_notices') if isinstance(body, dict) else None
print('  status=%s notices=%s' % (status, len(notices or [])))
print('  message=%s' % ((notices or [{}])[0].get('message', '')[:140]))

print('--- the rival reading ITS OWN results (it competed: expect empty) ---')
status, body = get(rival_token, results_path(fx['rival_team_id']))
if isinstance(body, dict):
    print('  status=%s key_present=%s notices=%s' % (
        status, 'inactivity_notices' in body,
        len(body.get('inactivity_notices') or [])))

print('--- the OTHER demoted firm, which outscored nobody above it ---')
if fx.get('plain_demoted_student'):
    token = login(fx['plain_demoted_student'])
    status, body = get(token, results_path(fx['plain_demoted_team_id']))
    notices = body.get('inactivity_notices') or []
    message = notices[0]['message'] if notices else ''
    print('  status=%s notices=%s outscored=%s' % (
        status, len(notices),
        notices[0].get('outscored_a_firm_ranked_above') if notices else None))
    print('  price_adjustments=%s' % len(body.get('price_adjustments') or []))
    print('  message=%s' % message)
    print('  claims no lost place: %s' % ('lower than yours' not in message))
