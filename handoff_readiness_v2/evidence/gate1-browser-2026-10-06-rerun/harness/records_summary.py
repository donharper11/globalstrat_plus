"""Totals across every record: steps, screens, console errors (excluding the
harness's aborted font requests), and every distinct refused API call."""
import json
import pathlib
from collections import Counter

RECORDS = pathlib.Path(__file__).resolve().parent.parent / 'records'
tot = Counter()
console = Counter()
refused = Counter()
rows = []
for path in sorted(RECORDS.glob('*.json')):
    r = json.loads(path.read_text())
    if 'summary' not in r:
        continue
    s = r['summary']
    errs = [c for c in r.get('console', []) if c['type'] in ('error', 'pageerror') and 'ERR_FAILED' not in c['text']]
    for c in errs:
        console[c['text'][:110]] += 1
    for x in r.get('refused', []):
        refused[(x['method'], x['url'].split('?')[0][:90], x['status'])] += 1
    rows.append((path.stem, s['passed'], s['failed'], s.get('observed', 0), s['screens'], s.get('screens_with_leaks', 0), len(errs), s['api_calls'], s['api_refused']))
    for k in ('passed', 'failed', 'observed', 'screens', 'api_calls', 'api_refused'):
        tot[k] += s.get(k, 0)
    tot['console_errors'] += len(errs)
print('%-38s %5s %5s %5s %6s %5s %5s %6s %5s' % ('record', 'pass', 'fail', 'obs', 'screen', 'leak', 'cons', 'api', 'refus'))
for row in rows:
    print('%-38s %5d %5d %5d %6d %5d %5d %6d %5d' % row)
print('TOTAL', dict(tot))
print('\nCONSOLE ERRORS (non-font):')
for k, n in console.most_common():
    print(' %4d  %s' % (n, k))
print('\nREFUSED API CALLS (distinct):')
for (m, u, st), n in sorted(refused.items(), key=lambda kv: -kv[1]):
    print(' %4d  %s %s -> %s' % (n, m, u, st))
