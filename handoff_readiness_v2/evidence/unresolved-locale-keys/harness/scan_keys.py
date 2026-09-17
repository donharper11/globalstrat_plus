import json, re, pathlib, collections
base = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees/agent-ad31a78c64885fc47')
root = base / 'frontend/globalstrat-frontend/src'

def flat(d, p=''):
    out = {}
    for k, v in d.items():
        n = (p + '.' + k) if p else k
        if isinstance(v, dict):
            out.update(flat(v, n))
        else:
            out[n] = v
    return out

cats = {}
for lang in ('en', 'zh-CN'):
    cats[lang] = flat(json.loads((root / 'locales' / (lang + '.json')).read_text(encoding='utf-8')))

SUF = ('_zero', '_one', '_two', '_few', '_many', '_other', '_plural')

def resolves(key, cat):
    if key in cat:
        return True
    for s in SUF:
        if key + s in cat:
            return True
    return False

static = re.compile(r"\bt\(\s*(['\"])([A-Za-z0-9_.:\-]+)\1")
dynamic = re.compile(r"\bt\(\s*[`a-zA-Z_$({]")
transre = re.compile(r"i18nKey\s*=\s*(['\"])([A-Za-z0-9_.:\-]+)\1")
defval = re.compile(r"\bt\(\s*['\"][A-Za-z0-9_.:\-]+['\"]\s*,\s*(['\"]|\{[^}]*defaultValue)")

refs = collections.defaultdict(list)
dyn = []
tr = []
dv = 0
ns = set()
files = sorted(list(root.rglob('*.js')) + list(root.rglob('*.jsx')))
for f in files:
    if 'node_modules' in str(f):
        continue
    rel = f.relative_to(root)
    for i, line in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        for m in static.finditer(line):
            k = m.group(2)
            refs[k].append('%s:%d' % (rel, i))
            if ':' in k:
                ns.add(k)
        if dynamic.search(line):
            dyn.append('%s:%d' % (rel, i))
        for m in transre.finditer(line):
            tr.append((m.group(2), '%s:%d' % (rel, i)))
        if defval.search(line):
            dv += 1

print('files scanned               :', len(files))
print('static t() references       :', sum(len(v) for v in refs.values()))
print('distinct static keys        :', len(refs))
print('dynamic/computed t() calls  :', len(dyn), ' <- not statically resolvable')
print('<Trans i18nKey> uses        :', len(tr))
print('t() with defaultValue       :', dv)
print('namespaced ns:key refs      :', len(ns))
print('plural-suffixed keys in en  :', sum(1 for k in cats['en'] if k.endswith(SUF)))
print('en/zh key sets identical    :', set(cats['en']) == set(cats['zh-CN']))
for lang in ('en', 'zh-CN'):
    miss = sorted(k for k in refs if not resolves(k, cats[lang]))
    print('')
    print('UNRESOLVED in %s: %d' % (lang, len(miss)))
    for k in miss:
        print('   %-42s %s  (x%d)' % (k, refs[k][0], len(refs[k])))
if dyn:
    print('')
    print('sample dynamic sites:', dyn[:6])
