"""Verify student-safe and instructor reasoning APIs for all four teams."""
import json
import pathlib
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
game = json.loads((SCRATCH / 'game.json').read_text())
gid = game['game_id']
checks = []
students = {}


def check(name, ok, detail=''):
    checks.append({'name': name, 'outcome': 'pass' if ok else 'fail',
                   'detail': str(detail)[:900]})
    print('%s %s -- %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:240]))


def score_keys(node):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if 'score' in key.lower():
                found.append(key)
            found.extend(score_keys(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(score_keys(value))
    return found


check('exactly four teams are evaluated', len(game['teams']) == 4, len(game['teams']))
for index, team in enumerate(game['teams'], start=1):
    members = [row for row in game['roster'] if row.get('team_id') == team['team_id']]
    member = members[0]
    token = login(member['username'], member.get('student_id'))
    lang = 'zh-CN' if index == 3 else 'en'
    status, body = call(
        'GET', '/api/games/%d/teams/%d/rounds/%d/reasoning/'
        % (gid, team['team_id'], ROUND), token=token, lang=lang)
    history_status, history = call(
        'GET', '/api/games/%d/teams/%d/reasoning/history/'
        % (gid, team['team_id']), token=token, lang=lang)
    students[team['team_name']] = {'language': lang, 'status': status,
                                    'body': body, 'history': history}
    check('%s student reasoning is available' % team['team_name'],
          status == 200 and isinstance(body, dict) and body.get('available') is True,
          {'status': status, 'available': (body or {}).get('available')
           if isinstance(body, dict) else None})
    check('%s student response contains qualitative dimensions' % team['team_name'],
          bool((body or {}).get('dimensions')) if isinstance(body, dict) else False,
          list(((body or {}).get('dimensions') or {}).keys()) if isinstance(body, dict) else body)
    leaked = score_keys(body)
    check('%s student response exposes no numeric score fields' % team['team_name'],
          not leaked, leaked)
    rounds = [row.get('round_number') for row in ((history or {}).get('history') or [])]
    check('%s reasoning history carries every completed round' % team['team_name'],
          history_status == 200 and rounds == list(range(1, ROUND + 1)), rounds)

instructor = login(game.get('instructor', 'walk_instructor'))
all_status, all_body = call(
    'GET', '/api/instructor/games/%d/reasoning/?round=%d' % (gid, ROUND),
    token=instructor, lang='en')
comparison_status, comparison = call(
    'GET', '/api/instructor/games/%d/reasoning/comparison/?round=%d' % (gid, ROUND),
    token=instructor, lang='en')
check('instructor reasoning lists all four teams',
      all_status == 200 and len((all_body or {}).get('teams') or []) == 4,
      {'status': all_status, 'teams': len((all_body or {}).get('teams') or [])})
check('instructor comparison lists all four teams',
      comparison_status == 200 and len((comparison or {}).get('comparison') or []) == 4,
      {'status': comparison_status,
       'teams': len((comparison or {}).get('comparison') or [])})

out = {'round': ROUND, 'checks': checks, 'students': students,
       'instructor_all_teams': all_body, 'instructor_comparison': comparison}
RECORDS.mkdir(parents=True, exist_ok=True)
path = RECORDS / ('reasoning-round%d.json' % ROUND)
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
print('record:', path)
raise SystemExit(0 if all(c['outcome'] == 'pass' for c in checks) else 1)
