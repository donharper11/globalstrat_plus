"""Copies of the audit chain head, kept where the database cannot reach them.

A hash chain stored entirely inside the database it protects proves only
internal consistency: whoever can rewrite a row can rewrite the chain over it
and produce a history that verifies perfectly. The anchor is the part that is
not in the database. Each export records the chain head as it stood at a moment
in time, alongside the build that produced it, and is written to the backup
volume with an accompanying checksum.

Verification then asks a question the database cannot answer about itself:
replaying every sealed entry from the rows the database holds *today*, does the
chain still arrive at the digest someone wrote down outside? Because each
entry's digest feeds the next, one matching head covers every row beneath it —
but only if the replay reads the live rows. Recomputing the head from the chain
table's own stored fields would prove the chain row was not edited and nothing
at all about the audit rows underneath it.
"""
import hashlib
import json
import os
import pathlib

from django.utils import timezone

from core.models import AuditChainEntry
from core.models.audit_integrity import GENESIS_SHA256
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
    """Rebuild the chain from live rows up to the anchored head and compare.

    The whole prefix is recomputed, not just the anchored entry. An earlier
    version compared the stored head against the anchored head and recomputed
    that one entry from its own stored fields — which proves the chain row was
    not edited and says nothing whatever about the audit rows underneath it. A
    modified row three entries back passed that check. Because each entry's
    digest feeds the next, replaying every entry from the live rows makes the
    final value depend on all of them, which is the property the anchor was
    supposed to have.

    A `False` result is the interesting one: the rows the database holds today
    no longer produce the digest that was written down when they were sealed.
    """
    anchor = load_anchor(path)
    if anchor is None:
        return {'ok': False, 'reason': 'no anchor found',
                'checked_at': timezone.now().isoformat()}

    head_seq = anchor['head_seq']
    entries = list(AuditChainEntry.objects.filter(seq__lte=head_seq)
                   .order_by('seq'))
    problems = []
    if len(entries) != head_seq:
        problems.append(
            f'{head_seq} entries were anchored; {len(entries)} remain')

    caches = {}
    for table, (model, _fields) in PROJECTIONS.items():
        caches[table] = {row.pk: row for row in model.objects.all()}

    recomputed = GENESIS_SHA256
    for entry in entries:
        if entry.source_table == RECOVERY_AUDIT_TABLE:
            state = recovery_audit_state()
            if state is None:
                problems.append(
                    f'#{entry.seq}: recovery-audit.jsonl is missing')
                row_sha = entry.row_sha256
            else:
                row_sha = state['sha256']
                if row_sha != entry.row_sha256 and entry.seq == head_seq:
                    problems.append(
                        f'#{entry.seq}: recovery-audit.jsonl has changed')
                elif row_sha != entry.row_sha256:
                    # Older file entries legitimately describe earlier content.
                    row_sha = entry.row_sha256
        else:
            row = caches.get(entry.source_table, {}).get(entry.source_id)
            if row is None:
                problems.append(
                    f'#{entry.seq}: {entry.source_table}:{entry.source_id} '
                    'has been deleted')
                row_sha = entry.row_sha256
            else:
                row_sha = row_digest(entry.source_table, row)
                if row_sha != entry.row_sha256:
                    problems.append(
                        f'#{entry.seq}: {entry.source_table}:'
                        f'{entry.source_id} no longer hashes to its sealed '
                        'digest')
        recomputed = entry_digest(recomputed, entry.source_table,
                                  entry.source_id, row_sha)

    if recomputed != anchor['head_entry_sha256']:
        problems.append(
            'the chain rebuilt from live rows does not reach the anchored head')

    return {
        'ok': not problems,
        'anchor': anchor['path'],
        'anchored_at': anchor['anchored_at'],
        'head_seq': head_seq,
        'entries_replayed': len(entries),
        'anchored_head_sha256': anchor['head_entry_sha256'],
        'recomputed_head_sha256': recomputed,
        'entries_now': AuditChainEntry.objects.count(),
        'entries_anchored': anchor['entries'],
        'problems': problems,
        'checked_at': timezone.now().isoformat(),
    }
