"""The two questions `check-participant-strings` does not ask.

    bilingual_coverage_scan.py [--json]

The Stage-5 control (`backend/scripts/check-participant-strings`) is nine
assertions and they are good ones, but the ten-round browser pass walked into
three gaps between them, each of which put English on a Chinese player's
screen:

* **A4's scope is eight backend files.** `cc32d_views.py:38` serves
  `'preferences': p.preferences` — a JSONField blob of
  ``{feature, weight, description}`` dicts — straight through, while every
  field beside it in the same dict literal goes through
  `get_localized_field`. `get_localized_field` cannot reach inside a
  JSONField, so a Chinese reader gets the partner's name and description in
  Chinese and the preferences next to them in English. The module is not in
  scope and nothing checks the other view modules.
* **No assertion looks at rendered JSX that never calls `t()` at all.** A9 is
  the frontend twin of A4, and it catches `t('key', 'Fallback')` — a
  hard-coded fallback *inside* a catalogue call. It cannot see
  ``<Title level={5}>Open FX hedge positions</Title>``, which is not a
  catalogue call at all. Nine assertions pass over it.
* **Nothing asserts that scenario-authored content HAS a `_zh` sibling.** A7
  asks whether a scenario-authored name is localised rather than interpolated
  raw — a mechanism question about the in-scope files. It does not ask whether
  the authored content exists in both languages. The YAML pattern is
  established (126 `name_zh`, 96 `description_zh` in the competition scenario)
  which is exactly why the omissions are invisible: the mechanism is right
  everywhere and the content is missing in places.

This script asks the two coverage questions, so the numbers in the report are
reproducible and so the owner has the implementation if the checks are wanted
in `check-participant-strings` as A10 and A11. It asserts nothing and fails
nothing; it counts.

**A10's count is a FLOOR, deliberately.** The filter drops anything carrying
JS punctuation or an operator, because an AntD
``items={[{key, label, children}]}`` array otherwise buries the prose forty
hits deep. One string this costs is known and named rather than left to be
rediscovered: `pages/FinancePage.js:760` renders
``{…}% audit risk/round — expected audit cost ~{…} per audit.`` and, on the
next line, `` ` Expected value over ${roundsRemaining} remaining rounds: ` ``,
with the verdict beside them going through `t()` properly. It was read off a
zh-CN tax page in this pass. A count that is honest about being a floor is
worth more than one that pads itself with component structure.

Proper nouns are named individually rather than pattern-matched: a company,
a statute or a product is legitimately Latin on a Chinese screen, and the
whole value of this count is that nothing else hides behind that excuse.
"""
import collections
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parents[3]
SRC = REPO / 'frontend' / 'globalstrat-frontend' / 'src'
SCENARIOS = REPO / 'backend' / 'scenarios'

# Authored fields whose values a player reads, each with an established
# `<field>_zh` sibling elsewhere in the same file.
TRANSLATABLE = ('name', 'description', 'prompt_text', 'description_template')
# Paths whose values are proper nouns. Stated one by one, with the reason.
PROPER_NOUN_PATHS = {
    'suppliers[]:name': 'a manufacturer\'s registered name',
    'compliance_regimes[]:name': 'the name of a statute',
}

WORDS = re.compile(r'\b[A-Za-z][a-z]{2,}\b')
CODE_NOISE = {'div', 'span', 'true', 'false', 'null', 'const', 'return',
              'className', 'style', 'length', 'map', 'filter', 'Number',
              'Math', 'round', 'toFixed', 'props', 'key'}
JSX_NODE = re.compile(r'>([^<>{}]{8,400}?)<', re.S)
JSX_TITLE = re.compile(r'\btitle="([^"]{6,120})"')
# Prose with values interpolated into it -- the shape FinancePage's tax
# sentence takes. The braces are removed and what is left is judged as prose,
# because that is what a reader sees between the numbers.
JSX_MIXED = re.compile(r'>([^<>]{12,400}?)<', re.S)
# Operators mean the regex caught an expression between two tags, not copy.
CODE_SHAPES = re.compile(r'=>|===|!==|\|\||&&|\?\.|;\s|\breturn\b')
# For prose with values interpolated into it, the de-braced remainder must
# read as a sentence. An AntD `items={[{key, label, children}]}` array is the
# shape this would otherwise drown in -- 40-odd hits, every one of them a
# component's own structure rather than anything a reader sees -- so anything
# carrying JS punctuation or a structural identifier is dropped.
NOT_PROSE = re.compile(r"[{}\[\]:'`=]|\b(?:key|label|icon|children|items|"
                       r"color|onClick|okText|style|value|render)\b")


def scenario_gaps():
    out = {}
    for path in sorted(SCENARIOS.glob('*.yaml')):
        try:
            import yaml
            doc = yaml.safe_load(path.open())
        except Exception as exc:                     # pragma: no cover
            out[path.name] = {'unreadable': str(exc)[:120]}
            continue
        missing = collections.Counter()
        examples = {}

        def walk(node, where):
            if isinstance(node, dict):
                for base in TRANSLATABLE:
                    value = node.get(base)
                    if isinstance(value, str) and value.strip():
                        sibling = node.get(base + '_zh')
                        if not (isinstance(sibling, str) and sibling.strip()):
                            key = (where or 'root') + ':' + base
                            missing[key] += 1
                            examples.setdefault(key, value[:90])
                for key, value in node.items():
                    walk(value, (where + '.' + str(key)) if where else str(key))
            elif isinstance(node, list):
                for item in node:
                    walk(item, where + '[]')

        walk(doc, '')
        proper = {k: n for k, n in missing.items() if k in PROPER_NOUN_PATHS}
        player = {k: n for k, n in missing.items() if k not in PROPER_NOUN_PATHS}
        out[path.name] = {
            'player_facing_strings_with_no_zh': sum(player.values()),
            'proper_nouns_excused': sum(proper.values()),
            'by_place': dict(sorted(player.items(), key=lambda kv: -kv[1])),
            'examples': {k: examples[k] for k in player},
        }
    return out


def rendered_english():
    """JSX text and title attributes that never reach the catalogue."""
    found = []
    for path in sorted(SRC.rglob('*.js')):
        rel = str(path.relative_to(SRC))
        if '.test.' in rel or rel.startswith(('locales/', 'api/')):
            continue
        text = path.read_text(errors='replace')
        # Anything inside a t() call is catalogue-bound by construction.
        text = re.sub(r"t\(\s*'[^']*'", "t('K'", text)
        text = re.sub(r't\(\s*"[^"]*"', 't("K"', text)
        text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
        text = re.sub(r'(?m)^\s*//.*$', ' ', text)
        for match in JSX_NODE.finditer(text):
            body = ' '.join(match.group(1).split())
            if body.startswith(('/', 'http')) or '=>' in body or '===' in body:
                continue
            words = [w for w in WORDS.findall(body)
                     if w.lower() not in CODE_NOISE]
            # Three ordinary words and no operators is prose, not an
            # expression the regex caught between two tags.
            if len(words) >= 3 and not CODE_SHAPES.search(body):
                found.append({'file': rel, 'kind': 'jsx-text',
                              'text': body[:120]})
        for match in JSX_MIXED.finditer(text):
            raw = match.group(1)
            if '{' not in raw:
                continue                      # already covered above
            body = ' '.join(re.sub(r'\{[^{}]*\}', ' ', raw).split())
            words = [w for w in WORDS.findall(body)
                     if w.lower() not in CODE_NOISE]
            if (len(words) >= 3 and not CODE_SHAPES.search(body)
                    and not NOT_PROSE.search(body)):
                found.append({'file': rel, 'kind': 'jsx-text-with-values',
                              'text': body[:120]})
        for match in JSX_TITLE.finditer(text):
            body = ' '.join(match.group(1).split())
            words = [w for w in WORDS.findall(body)
                     if w.lower() not in CODE_NOISE]
            if len(words) >= 2:
                found.append({'file': rel, 'kind': 'title-attribute',
                              'text': body[:120]})
    return found


def main():
    scenarios = scenario_gaps()
    frontend = rendered_english()
    report = {'scenarios': scenarios, 'rendered_english_outside_catalogue':
              frontend}
    if '--json' in sys.argv:
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 0
    print('A11 — scenario content with no Chinese sibling')
    for name, data in scenarios.items():
        if 'unreadable' in data:
            print('  %-44s %s' % (name, data['unreadable']))
            continue
        print('  %-44s %4d player-facing   (%d proper nouns excused)'
              % (name, data['player_facing_strings_with_no_zh'],
                 data['proper_nouns_excused']))
        for place, count in list(data['by_place'].items())[:6]:
            print('        %4d  %-52s %r'
                  % (count, place[:52], data['examples'][place][:60]))
    print('\nA10 — rendered English that never reaches the catalogue')
    by_file = collections.Counter(x['file'] for x in frontend)
    for rel, count in by_file.most_common():
        print('  %-48s %d' % (rel, count))
        for item in [x for x in frontend if x['file'] == rel][:4]:
            print('        [%s] %r' % (item['kind'], item['text'][:88]))
    print('\n%d strings in %d files' % (len(frontend), len(by_file)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
