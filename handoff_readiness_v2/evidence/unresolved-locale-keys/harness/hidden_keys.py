"""Keys referenced INDIRECTLY -- through a label map or a template literal.

A8 reads `t('literal')`. These reach `t()` as a variable, so A8 cannot see
them. This enumerates the candidates by a different route: any string literal
in the frontend that LOOKS like an i18n key and whose first segment is a real
top-level namespace in the catalogue, excluding the ones already written
directly inside a t() call.
"""
import json, pathlib, re
base = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees/agent-ad31a78c64885fc47')
root = base / 'frontend/globalstrat-frontend/src'

def flat(d, p=''):
    out = {}
    for k, v in d.items():
        n = (p + '.' + k) if p else k
        if isinstance(v, dict): out.update(flat(v, n))
        else: out[n] = v
    return out

raw = json.loads((root / 'locales/en.json').read_text(encoding='utf-8'))
cat = flat(raw)
namespaces = set(raw.keys())
SUF = ('_zero','_one','_two','_few','_many','_other','_plural')
def resolves(k):
    return k in cat or any(k + s in cat for s in SUF)

KEYLIKE = re.compile(r"""['"]([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)['"]""")
DIRECT = re.compile(r"""\bt\(\s*['"]([A-Za-z0-9_.:\-]+)['"]""")

direct, indirect = set(), {}
for f in sorted(list(root.rglob('*.js')) + list(root.rglob('*.jsx'))):
    if 'node_modules' in str(f): continue
    rel = f.relative_to(root)
    for i, line in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        for m in DIRECT.finditer(line):
            direct.add(m.group(1))
        for m in KEYLIKE.finditer(line):
            k = m.group(1)
            if k.split('.')[0] in namespaces:
                indirect.setdefault(k, []).append('%s:%d' % (rel, i))

candidates = {k: v for k, v in indirect.items() if k not in direct}
missing = {k: v for k, v in candidates.items() if not resolves(k)}
print('indirect key-like literals in real namespaces :', len(candidates))
print('of those, MISSING from the catalogue          :', len(missing))
print('')
by_ns = {}
for k in sorted(missing):
    by_ns.setdefault(k.split('.')[0], []).append(k)
for ns, keys in sorted(by_ns.items()):
    print('  %s  (%d)' % (ns, len(keys)))
    for k in keys:
        print('      %-46s %s' % (k, missing[k][0]))
