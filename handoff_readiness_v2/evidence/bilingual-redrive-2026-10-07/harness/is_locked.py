"""Has this team locked this round? is_locked.py <team-index> <round>

Prints the stored submission status, so a shell step can ask without parsing a
record. Read-only, as the team's own member -- the same answer the student's
own page is served.
"""
import json
import pathlib
import sys

from apicall import call, login

G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
ix, rnd = int(sys.argv[1]), int(sys.argv[2])
team = G['teams'][ix - 1]
members = [r for r in G['roster'] if r.get('team_id') == team['team_id']]
# The same member the lock driver uses. The first roster row for a team is not
# always one the team's own API accepts (team 1 carries the refused sixth
# assignment), and a 403 would read as "not locked".
member = members[min(1, len(members) - 1)]
# A student's password is their student id, issued in bulk from the console.
token = login(member['username'], member.get('student_id') or member['username'])
status, body = call('GET', '/api/games/%d/teams/%d/decisions/round/%d/'
                    % (G['game_id'], team['team_id'], rnd), token=token)
print((body or {}).get('status') if isinstance(body, dict) else 'HTTP %s' % status)
