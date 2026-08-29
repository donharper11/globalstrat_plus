"""Regenerate the evidence inventory. Called by every run that writes evidence.

The last rework failed on exactly this: a rerun rewrote `characterisation.json`
without refreshing its digest, and `v2-023-gate.json` was never added at all,
because the inventory was maintained by hand and nothing regenerated it. Any
run that writes an artifact now rewrites the inventory in the same breath, so
the two cannot drift apart.

Convention, matching the file it replaces: evidence artifacts only, `./`
prefix, JSON before TXT, alphabetical within each group. The harness is source
rather than evidence -- git tracks it, and every artifact records the harness
revision it was produced at.
"""
import hashlib
import pathlib


def regenerate(evidence_dir):
    evidence = pathlib.Path(evidence_dir)
    names = (sorted(p.name for p in evidence.glob('*.json'))
             + sorted(p.name for p in evidence.glob('*.txt')))
    lines = []
    for name in names:
        digest = hashlib.sha256((evidence / name).read_bytes()).hexdigest()
        lines.append(f'{digest}  ./{name}')
    (evidence / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    return names


def verify(evidence_dir):
    """Recompute every digest and return the names that do not match."""
    evidence = pathlib.Path(evidence_dir)
    recorded = {}
    for line in (evidence / 'SHA256SUMS').read_text().splitlines():
        digest, _, name = line.partition('  ')
        recorded[name.lstrip('./')] = digest
    bad = []
    for name, digest in recorded.items():
        path = evidence / name
        if not path.exists():
            bad.append(f'{name}: MISSING')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad.append(f'{name}: FAILED')
    present = {p.name for p in evidence.glob('*.json')} | {
        p.name for p in evidence.glob('*.txt')}
    for name in sorted(present - set(recorded)):
        bad.append(f'{name}: NOT IN INVENTORY')
    return bad
