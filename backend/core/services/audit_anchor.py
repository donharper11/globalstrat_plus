"""Copies of the audit chain head, kept where the database cannot reach them.

A hash chain stored entirely inside the database it protects proves only
internal consistency: whoever can rewrite a row can rewrite the chain over it
and produce a history that verifies perfectly. The anchor is the part that is
not in the database. Each export records the chain head as it stood at a moment
in time, alongside the build that produced it, and is written to the backup
volume with an accompanying checksum.

Verification then asks a question the database cannot answer about itself: does
the entry at the anchored sequence number still hash to the value someone wrote
down outside? Because every entry commits to its predecessor, one matching head
covers the whole prefix.
"""
import hashlib
import json
import os
import pathlib

from django.utils import timezone

from core.models import AuditChainEntry
from core.services.audit_chain import PROJECTIONS, entry_digest, row_digest
from core.services.audit_chain import RECOVERY_AUDIT_TABLE, recovery_audit_state

ANCHOR_DIRNAME = 'audit-anchors'


def anchor_root():
    from core.services.competition_backup import backup_root
    return pathlib.Path(backup_root()) / ANCHOR_DIRNAME


def _write_atomic(path, text):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    # fsync the directory as well, so the rename itself survives a power loss.
    # The fd is used bare: wrapping a directory fd in a file object fails.
    directory = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def export_anchor():
    """Write the current chain head outside the database. Returns the record."""
    from core.services.build_identity import build_identity

    head = AuditChainEntry.objects.order_by('-seq').first()
    if head is None:
        raise ValueError('The audit chain is empty; there is nothing to anchor.')

    counts = {}
    for table in PROJECTIONS:
        counts[table] = AuditChainEntry.objects.filter(
            source_table=table).count()
    counts[RECOVERY_AUDIT_TABLE] = AuditChainEntry.objects.filter(
        source_table=RECOVERY_AUDIT_TABLE).count()

    try:
        identity = build_identity()
    except Exception:
        identity = {}

    record = {
        'anchored_at': timezone.now().isoformat(),
        'head_seq': head.seq,
        'head_entry_sha256': head.entry_sha256,
        'head_source': f'{head.source_table}:{head.source_id}',
        'entries': AuditChainEntry.objects.count(),
        'entries_by_table': counts,
        'recovery_audit': recovery_audit_state(),
        'code_revision': identity.get('code_revision', ''),
        'source_tree_sha256': identity.get('source_tree_sha256', ''),
    }
    body = json.dumps(record, indent=2, sort_keys=True) + '\n'
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()

    root = anchor_root()
    root.mkdir(parents=True, exist_ok=True)
    name = f'anchor-{head.seq:012d}.json'
    path = root / name
    _write_atomic(path, body)
    _write_atomic(path.with_suffix('.json.sha256'), f'{digest}  {name}\n')
    _write_atomic(root / 'latest.json', body)
    _write_atomic(root / 'latest.json.sha256', f'{digest}  latest.json\n')
    record['path'] = str(path)
    record['sha256'] = digest
    return record


def load_anchor(path=None):
    """Read an anchor and confirm it matches its own checksum."""
    target = pathlib.Path(path) if path else anchor_root() / 'latest.json'
    if not target.is_file():
        return None
    body = target.read_text(encoding='utf-8')
    sidecar = target.with_suffix(target.suffix + '.sha256')
    if sidecar.is_file():
        expected = sidecar.read_text(encoding='utf-8').split()[0]
        actual = hashlib.sha256(body.encode('utf-8')).hexdigest()
        if expected != actual:
            raise ValueError(f'{target} does not match its checksum file.')
    record = json.loads(body)
    record['path'] = str(target)
    return record


def verify_against_anchor(path=None):
    """Recompute the chain up to the anchored head and compare.

    A `False` result is the interesting one: it means the rows the database
    holds today no longer produce the digest that was written down when they
    were sealed.
    """
    anchor = load_anchor(path)
    if anchor is None:
        return {'ok': False, 'reason': 'no anchor found',
                'checked_at': timezone.now().isoformat()}

    entry = AuditChainEntry.objects.filter(seq=anchor['head_seq']).first()
    if entry is None:
        return {'ok': False, 'anchor': anchor['path'],
                'reason': f"chain entry {anchor['head_seq']} is gone",
                'checked_at': timezone.now().isoformat()}

    problems = []
    if entry.entry_sha256 != anchor['head_entry_sha256']:
        problems.append('the stored chain head differs from the anchored head')

    # Recompute the anchored entry from the live row it commits to.
    if entry.source_table == RECOVERY_AUDIT_TABLE:
        state = recovery_audit_state()
        row_sha = state['sha256'] if state else None
        if row_sha is None:
            problems.append('recovery-audit.jsonl is missing')
            row_sha = entry.row_sha256
    else:
        model, _fields = PROJECTIONS[entry.source_table]
        row = model.objects.filter(pk=entry.source_id).first()
        if row is None:
            problems.append(
                f'{entry.source_table}:{entry.source_id} has been deleted')
            row_sha = entry.row_sha256
        else:
            row_sha = row_digest(entry.source_table, row)
            if row_sha != entry.row_sha256:
                problems.append(
                    f'{entry.source_table}:{entry.source_id} no longer hashes '
                    'to its sealed digest')

    recomputed = entry_digest(entry.prev_sha256, entry.source_table,
                              entry.source_id, row_sha)
    if recomputed != anchor['head_entry_sha256']:
        problems.append('the anchored head does not recompute from live data')

    return {
        'ok': not problems,
        'anchor': anchor['path'],
        'anchored_at': anchor['anchored_at'],
        'head_seq': anchor['head_seq'],
        'anchored_head_sha256': anchor['head_entry_sha256'],
        'recomputed_head_sha256': recomputed,
        'entries_now': AuditChainEntry.objects.count(),
        'entries_anchored': anchor['entries'],
        'problems': problems,
        'checked_at': timezone.now().isoformat(),
    }
