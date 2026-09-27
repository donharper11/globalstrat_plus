"""Fail unless the candidate round is open and all four teams self-locked."""
import json
import pathlib
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
game = json.loads((SCRATCH / 'game.json').read_text())
token = login(game.get('instructor', 'walk_instructor'))

rc_status, rc = call('GET', '/api/games/%d/round-control/' % game['game_id'], token=token)
dash_status, dash = call('GET', '/api/games/%d/instructor/dashboard/' % game['game_id'], token=token)
rows = (dash or {}).get('teams') or []
checks = {
    'round_control_http_200': rc_status == 200,
    'dashboard_http_200': dash_status == 200,
    'exactly_four_teams': len(rows) == 4,
    'round_is_open': ((rc or {}).get('round') or {}).get('round_number') == ROUND
                     and ((rc or {}).get('round') or {}).get('status') == 'open',
    'all_four_self_locked': len(rows) == 4
                            and all(row.get('decision_status') == 'locked' for row in rows),
}
out = {
    'round': ROUND,
    'checks': checks,
    'round_control': rc,
    'teams': [{k: row.get(k) for k in ('team_id', 'team_name', 'decision_status')}
              for row in rows],
}
RECORDS.mkdir(parents=True, exist_ok=True)
path = RECORDS / ('ready-round%d.json' % ROUND)
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
for name, ok in checks.items():
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
print('record:', path)
raise SystemExit(0 if all(checks.values()) else 1)
