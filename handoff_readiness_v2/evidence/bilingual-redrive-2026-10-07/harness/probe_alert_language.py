"""Every AI Coach alert of the whole game, read twice, in both languages.

    probe_alert_language.py

W-CE2-08 was about alerts that were English whatever the console said, and
walkthrough 3 left a named condition on the repair: an alert written before
the switch stayed English for ever, because the sentence was stored. The
repairs give an alert a render context, so the question is no longer "what
language was it written in" but "does each reader get their own language".

This reads the whole game's alerts as a Chinese-reading instructor and again
as an English-reading one, from the console's own route with the
`Accept-Language` header `api/client.js` sends, and counts the ones that come
back in the other language. It also counts sentinel numbers printed as
figures.
"""
import json
import pathlib

from apicall import call, login

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
G = json.loads((SCRATCH / 'game.json').read_text())
GID = G['game_id']
out = {'checks': [], 'by_language': {}}


def check(name, ok, detail=''):
    out['checks'].append({'name': name, 'outcome': 'pass' if ok else 'fail',
                          'detail': str(detail)[:900]})
    print('  %-4s %s -- %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:260]))


def han(text):
    return sum(1 for c in (text or '') if '一' <= c <= '鿿')


tok = login(G.get('instructor', 'walk_instructor'))
for lang in ('zh-CN', 'en'):
    s, body = call('GET', '/api/games/%d/instructor/alerts/' % GID,
                   token=tok, lang=lang)
    rows = (body or {}).get('alerts') or (body or {}).get('results') or []
    wrong = []
    for a in rows:
        text = (a.get('title') or '') + ' ' + (a.get('detail') or '')
        if (lang == 'zh-CN') != (han(text) > 0):
            wrong.append({'round': a.get('round_number'),
                          'type': a.get('alert_type'),
                          'title': a.get('title'),
                          'detail': (a.get('detail') or '')[:200]})
    sentinel = [{'round': a.get('round_number'), 'title': a.get('title')}
                for a in rows
                if '99999' in ((a.get('title') or '') + (a.get('detail') or ''))]
    out['by_language'][lang] = {'alerts': len(rows), 'wrong_language': wrong,
                                'sentinel_figures': sentinel}
    check('every alert reads in the language of the instructor reading them '
          '(%s)' % lang, not wrong,
          '%d alerts, %d in the other language; e.g. %s'
          % (len(rows), len(wrong),
             json.dumps(wrong[:3], ensure_ascii=False)[:500]))
    check('no sentinel figure is printed to the instructor as a number (%s)'
          % lang, not sentinel,
          '%d alerts carry 99999; e.g. %s'
          % (len(sentinel), json.dumps(sentinel[:3], ensure_ascii=False)[:400]))

RECORDS.mkdir(parents=True, exist_ok=True)
(RECORDS / 'probe-alert-language.json').write_text(
    json.dumps(out, indent=1, ensure_ascii=False) + '\n')
print('record:', RECORDS / 'probe-alert-language.json')
