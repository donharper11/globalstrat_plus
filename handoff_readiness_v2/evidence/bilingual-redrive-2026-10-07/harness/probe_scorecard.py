"""W-CE2-07 probe: the Strategic Scorecard sentences, read twice per language.

probe_scorecard.py <round> [team-id ...]

`RoundResultCoherence.breakdown` is a hashed manifest field, so the stored
sentence must stay English and only the served copy may change. This reads
en -> zh -> en for each team so that a read that mutates what is stored would
show as an English read that comes back Chinese. Read-only.
"""
import json
import pathlib
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
ROUND = int(sys.argv[1])
TIDS = [int(x) for x in sys.argv[2:]] or [t['team_id'] for t in G['teams'][:4]]


def read(tid, tok, lang):
    _, res = call('GET', '/api/games/%d/teams/%d/results/round/%d/' % (GID, tid, ROUND),
                  token=tok, lang=lang)
    breakdown = ((res or {}).get('coherence') or {}).get('breakdown') or {}
    sentences = {k: v.get('feedback') for k, v in breakdown.items()
                 if isinstance(v, dict) and v.get('feedback')}
    markets = sorted({d.get('market') for v in breakdown.values()
                      if isinstance(v, dict)
                      for d in (v.get('details') or []) if isinstance(d, dict) and d.get('market')})
    return sentences, markets


for tid in TIDS:
    member = [r for r in G['roster'] if r.get('team_id') == tid][0]
    tok = login(member['username'], member.get('student_id'))
    print('--- team %d (%s)' % (tid, member['username']))
    for label, lang in (('1 en ', 'en'), ('2 zh ', 'zh-CN'), ('3 en ', 'en')):
        sentences, markets = read(tid, tok, lang)
        print('  %s sentences=%s' % (label, json.dumps(sentences, ensure_ascii=False)))
        print('       markets inside the breakdown=%s' % json.dumps(markets, ensure_ascii=False))
