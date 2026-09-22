"""Aggregate the per-screen leak scans across records: leak_summary.py [glob]

Proper nouns the product legitimately shows in Latin script (team, product,
person and course names from this game) are removed so what remains is copy.
"""
import glob
import json
import pathlib
import sys

RECORDS = pathlib.Path(__file__).resolve().parent.parent / 'records'
pattern = sys.argv[1] if len(sys.argv) > 1 else '*zh-CN.json'
G = json.loads((pathlib.Path(__file__).resolve().parent / 'game.json').read_text())
NAMES = {t['team_name'] for t in G['teams']} | {r.get('display_name') for r in G['roster']} | {
    'Nova Circuit Base Platform', 'Apex Devices Base Platform', 'North America', 'Western Europe', 'East Asia',
    'South America', 'Africa', 'Walkthrough Instructor', 'Global Strategy Practicum', 'Consumer Electronics',
    'Nexus One', 'Nexus Lite', 'CE 2026 Heat A', 'Heat A', 'GlobalStrat', 'Granite Investments',
    'GreenHorizon Partners', 'Velocity Capital', 'PioneerTech Solutions', 'AsiaElec Manufacturing',
    'EuroGreen Devices', 'AfriConnect Mobile', 'TechSul Eletr'}
agg = {}
for path in sorted(RECORDS.glob(pattern)):
    r = json.loads(path.read_text())
    for l in r.get('leaks', []):
        for x in l['leaks']:
            key = x.get('english') or x.get('raw_key') or x.get('field_name') or x.get('junk')
            if not key or any(n and n in key for n in NAMES):
                continue
            kind = 'english' if 'english' in x else next(k for k in x if k != 'context' and k != 'n')
            agg.setdefault((kind, key), set()).add('%s:%s' % (path.stem, l['screen']))
rows = sorted(agg.items(), key=lambda kv: -len(kv[1]))
for (kind, key), screens in rows:
    print('%-10s %3d  %-70s  e.g. %s' % (kind, len(screens), repr(key)[:70], sorted(screens)[0]))
print('%d distinct items' % len(rows))
