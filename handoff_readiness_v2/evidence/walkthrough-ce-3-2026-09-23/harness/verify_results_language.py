"""Walkthrough 3: what a reader is told on the Round Results screen, per language.

verify_results_language.py <round>

Language is NOT decided by `Accept-Language`: R43 and the W-CE2-05 repair make
the platform answer in the language the *reader's own stored enrolment*
states, which the sign-in and the in-game switch write. So the two readings
below are made by two different members of the SAME team — a member who signs
in in English and a member who signs in in Simplified Chinese — and compared
on the same round's results.

  * W-CE-14   the performance index against the leaderboard's, and the
              shareholder return as a ratio rather than a runaway percentage;
  * W-CE2-06  every market name the response carries, wherever it sits, so an
              English name on a Chinese screen is visible without reading a
              screenshot;
  * W-CE2-07  the Strategic Scorecard sentences (`coherence.breakdown`), which
              the engine stores in English and the reader is served in their
              own language;
  * the price-adjustment notices, which interpolate a market name.

Read-only. Writes records/verify-results-r<N>.json.
"""
import json
import pathlib
import re
import sys

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
HAN = re.compile(r'[一-鿿]')
LATIN_RUN = re.compile(r'\b[A-Z]?[a-z]{3,}(?:\s+[A-Za-z]{2,}){1,}\b')
# team index -> (member index that reads in English, member index that reads in Chinese)
READERS = json.loads((SCRATCH / 'readers.json').read_text())
out = {'round': ROUND, 'teams': {}, 'checks': []}


def check(name, ok, detail=''):
    out['checks'].append({'name': name, 'outcome': 'pass' if ok else 'fail',
                          'detail': str(detail)[:900]})
    print('  %-5s %s -- %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:300]))


def market_names(payload):
    """Every market name in the response, with the path it sits at."""
    found = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ('market_name', 'market') and isinstance(value, str) and value:
                    found.setdefault(value, set()).add(path + '.' + key)
                else:
                    walk(value, path + '.' + key)
        elif isinstance(node, list):
            for item in node:
                walk(item, path + '[]')
    walk(payload, '')
    return {k: sorted(v) for k, v in found.items()}


def scorecard(payload):
    breakdown = ((payload or {}).get('coherence') or {}).get('breakdown') or {}
    if not isinstance(breakdown, dict):
        return {}
    return {k: v.get('feedback') for k, v in breakdown.items()
            if isinstance(v, dict) and v.get('feedback')}


itok = login(G.get('instructor', 'walk_instructor'))
_, lb = call('GET', '/api/games/%d/leaderboard/round/%d/' % (GID, ROUND), token=itok)
entries = (lb.get('rankings') or lb.get('leaderboard') or lb.get('teams') or []) if isinstance(lb, dict) else []

for ix_s, (en_ix, zh_ix) in READERS.items():
    ix = int(ix_s)
    team = G['teams'][ix - 1]
    tid = team['team_id']
    name = team['team_name']
    members = [r for r in G['roster'] if r.get('team_id') == tid]
    entry = {}
    for lang, mix in (('en', en_ix), ('zh-CN', zh_ix)):
        member = members[mix]
        tok = login(member['username'], member.get('student_id'))
        # State the reader's language the product's own way: the route the
        # in-game switch calls. It writes the enrolment AND the preference row,
        # so the two stores cannot disagree (W-CE2-08's repair).
        ps, pb = call('PUT', '/api/user/preferences/', {'language': lang}, token=tok)
        _, res = call('GET', '/api/games/%d/teams/%d/results/round/%d/' % (GID, tid, ROUND), token=tok)
        entry[lang] = {
            'reader': member['username'],
            'language_set': [ps, pb],
            'performance': (res or {}).get('performance'),
            'shareholder_return': ((res or {}).get('financials') or {}).get('shareholder_return_cumulative'),
            'market_names': market_names(res),
            'scorecard': scorecard(res),
            'price_adjustments': (res or {}).get('price_adjustments'),
        }
    out['teams'][name] = entry
    en, zh = entry['en'], entry['zh-CN']

    me = next((e for e in entries if e.get('team_id') == tid or e.get('team_name') == name), None)
    idx = (en.get('performance') or {}).get('index_value')
    check('%s: performance index on the results route == the leaderboard' % name,
          me is not None and idx is not None and abs(float(me['performance_index']) - float(idx)) < 0.05,
          'leaderboard=%s results=%s' % (me and me.get('performance_index'), idx))
    check('%s: shareholder return is a ratio, not a runaway percentage (W-CE-14)' % name,
          en['shareholder_return'] is not None and -5 <= float(en['shareholder_return']) <= 5,
          'stored=%s' % en['shareholder_return'])

    english_markets = {m: p for m, p in zh['market_names'].items() if not HAN.search(m)}
    check('%s: every market name on the Chinese results is in Chinese (W-CE2-06)' % name,
          not english_markets,
          'english names on the zh read, with where they sit: %s'
          % json.dumps(english_markets, ensure_ascii=False)[:600])

    english_sentences = {k: v for k, v in zh['scorecard'].items()
                         if v and LATIN_RUN.search(v) and not HAN.search(v)}
    check('%s: every Strategic Scorecard sentence is Chinese on a Chinese read (W-CE2-07)' % name,
          bool(zh['scorecard']) and not english_sentences,
          'still English: %s; served in Chinese: %s'
          % (json.dumps(english_sentences, ensure_ascii=False),
             json.dumps([k for k in zh['scorecard'] if k not in english_sentences])))
    check('%s: the English reader still gets the stored English sentences' % name,
          bool(en['scorecard']) and not any(HAN.search(v or '') for v in en['scorecard'].values()),
          json.dumps(en['scorecard'], ensure_ascii=False)[:400])

    zh_notices = json.dumps(zh['price_adjustments'] or [], ensure_ascii=False)
    check('%s: a Chinese price-adjustment notice carries no English market name' % name,
          not (zh['price_adjustments'] and re.search(
              r'(Africa|North America|East Asia|Western Europe|South America)', zh_notices)),
          zh_notices[:400] or 'no price adjustment this round')

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / ('verify-results-r%d.json' % ROUND)).write_text(
    json.dumps(out, indent=1, ensure_ascii=False, default=str) + '\n')
print('record:', RECORDS / ('verify-results-r%d.json' % ROUND))
