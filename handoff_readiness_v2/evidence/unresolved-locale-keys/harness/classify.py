import json, re, pathlib
base = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees/agent-ad31a78c64885fc47')
root = base / 'frontend/globalstrat-frontend/src'

def flat(d, p=''):
    out = {}
    for k, v in d.items():
        n = (p + '.' + k) if p else k
        if isinstance(v, dict): out.update(flat(v, n))
        else: out[n] = v
    return out

en = flat(json.loads((root/'locales/en.json').read_text(encoding='utf-8')))
SUF = ('_zero','_one','_two','_few','_many','_other','_plural')
def resolves(k):
    return k in en or any(k+s in en for s in SUF)

call = re.compile(r"\bt\(\s*(['\"])([A-Za-z0-9_.:\-]+)\1\s*(,?)\s*(.?)")
rows = []
for f in sorted(list(root.rglob('*.js')) + list(root.rglob('*.jsx'))):
    if 'node_modules' in str(f): continue
    rel = f.relative_to(root)
    for i, line in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        for m in call.finditer(line):
            k = m.group(2)
            if resolves(k): continue
            nxt = m.group(4)
            if m.group(3) != ',':
                kind = 'BARE (no 2nd arg)'
            elif nxt in ("'", '"'):
                kind = 'defaultValue (string)'
            elif nxt == '{':
                kind = 'options only -> KEY LEAKS'
            else:
                kind = 'other: ' + repr(nxt)
            rows.append((kind, k, '%s:%d' % (rel, i), line.strip()[:110]))

rows.sort()
leak = [r for r in rows if 'LEAK' in r[0] or 'BARE' in r[0]]
dflt = [r for r in rows if 'defaultValue' in r[0]]
print('=== A: renders the RAW KEY to a user (genuine leak):', len(leak), '===')
for kind, k, where, line in leak:
    print('  %-34s %-28s %s' % (k, where, line))
print('')
print('=== B: resolves via defaultValue (EN fine; zh-CN sees English):', len(dflt), '===')
for kind, k, where, line in dflt:
    print('  %-34s %s' % (k, where))
print('')
print('totals: leak=%d defaultValue=%d all=%d' % (len(leak), len(dflt), len(rows)))
