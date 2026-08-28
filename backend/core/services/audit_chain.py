"""Forward hash chain over the append-only audit records.

Why a chain and not only privileges: the application connects as the owner of
its tables, and a table owner can drop the triggers that refuse `UPDATE` and
`DELETE`. Privileges and triggers stop the application; they cannot stop
whoever holds the maintenance credentials. The chain is the part that survives
that, because every entry commits to the one before it and the head is copied
outside the database. A privileged edit made with the triggers disabled leaves
the rows looking fine and the recomputation disagreeing with the exported
anchor, which is the difference between "we believe nothing changed" and "we can
show nothing changed".

Sealing is a separate, serialized pass rather than a trigger on the audit write
itself. A trigger would have to read and lock the chain head inside whatever
transaction happened to be writing the audit row, which puts a global lock
underneath the operator-lifecycle locks that GSP-CRV2-02 certified — a lock
ordering that can deadlock. `schedule_seal()` runs the pass in `on_commit`,
after the writing transaction has released everything, so the chain lock is
never held together with a row lock.
"""
import hashlib
import pathlib

from django.db import connection, models, transaction
from django.utils import timezone

from core.models import (
    AuditChainEntry, DecisionAuditEvent, OperatorAuditEvent, ResolutionManifest,
    SensitiveReadEvent,
)
from core.models.audit_integrity import GENESIS_SHA256
from core.services.canonical_json import canonical_sha256, canonicalize

# One lock for the whole chain. Taken only by the seal pass, never while a
# lifecycle or decision lock is held.
CHAIN_LOCK_KEY = 0x6773705F61756469 % (2 ** 31)

RECOVERY_AUDIT_TABLE = 'recovery_audit_file'

# Which columns of each audit row the chain commits to. Everything a dispute
# could turn on is here; the large manifest bodies are represented by the
# digests that already cover them.
PROJECTIONS = {
    'competition_decision_audit_event': (
        DecisionAuditEvent,
        ('id', 'game_id', 'team_id', 'round_id', 'user_id', 'action',
         'endpoint', 'payload', 'payload_sha256', 'request_id', 'created_at'),
    ),
    'competition_operator_audit_event': (
        OperatorAuditEvent,
        ('id', 'game_id', 'round_id', 'user_id', 'action', 'outcome',
         'conflict', 'reason', 'before', 'after', 'request_id', 'created_at'),
    ),
    'competition_resolution_manifest': (
        ResolutionManifest,
        ('id', 'game_id', 'round_id', 'schema_version', 'seed', 'input_sha256',
         'input_section_digests', 'output_sha256', 'output_section_digests',
         'narrative_sha256', 'decision_event_count', 'code_revision',
         'source_tree_sha256', 'created_at', 'completed_at'),
    ),
    'competition_sensitive_read_event': (
        SensitiveReadEvent,
        ('id', 'actor_user_id', 'username', 'game_id_read', 'team_id_read',
         'round_number_read', 'category', 'route', 'endpoint', 'method',
         'status_code', 'outcome', 'request_id', 'created_at'),
    ),
}

# Sealed in this order within one pass, so a chain rebuilt from the same rows
# in the same pass produces the same digests.
SEAL_ORDER = (
    'competition_decision_audit_event',
    'competition_operator_audit_event',
    'competition_resolution_manifest',
    'competition_sensitive_read_event',
)


def row_digest(table, instance):
    """The canonical digest of one audit row's immutable projection."""
    _model, fields = PROJECTIONS[table]
    body = {'table': table}
    for field in fields:
        body[field] = getattr(instance, field)
    return canonical_sha256(canonicalize(body))


def entry_digest(prev_sha256, table, source_id, row_sha256):
    raw = f'{prev_sha256}\n{table}\n{source_id}\n{row_sha256}\n'
    return hashlib.sha256(raw.encode('ascii')).hexdigest()


def head():
    """The last sealed entry, or None."""
    return AuditChainEntry.objects.order_by('-seq').first()


def _pending(table):
    """Unsealed rows of one audit table, oldest first.

    An anti-join rather than a Python set difference: sealing runs after every
    audit write, and a pass that reads the whole audit history to find the one
    new row would get slower for exactly as long as the competition ran.
    """
    model, _fields = PROJECTIONS[table]
    queryset = model.objects.all()
    if table == 'competition_resolution_manifest':
        # A manifest row is written twice: once before the round is resolved
        # and once when it completes. Sealing the first write would commit to a
        # row that is *supposed* to change, so only completed manifests are
        # chained.
        queryset = queryset.filter(completed_at__isnull=False)
    sealed = AuditChainEntry.objects.filter(
        source_table=table).values('source_id')
    return queryset.exclude(pk__in=models.Subquery(sealed)).order_by('id')


def recovery_audit_state():
    """Digest and line count of the recovery audit file, or None if absent."""
    from core.services.competition_backup import backup_root
    path = pathlib.Path(backup_root()) / 'recovery-audit.jsonl'
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return {
        'path': str(path),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'lines': raw.count(b'\n'),
    }


def seal_pending(limit=None):
    """Append every unsealed audit row to the chain. Returns the count added.

    Idempotent: rows already in the chain are skipped, so a catch-up run after a
    crash adds only what the crash left behind.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [CHAIN_LOCK_KEY])
        current = head()
        seq = current.seq if current else 0
        prev = current.entry_sha256 if current else GENESIS_SHA256
        batch = []

        def append(table, source_id, digest):
            nonlocal seq, prev
            seq += 1
            entry = AuditChainEntry(
                seq=seq, source_table=table, source_id=source_id,
                row_sha256=digest, prev_sha256=prev,
                entry_sha256=entry_digest(prev, table, source_id, digest))
            prev = entry.entry_sha256
            batch.append(entry)

        for table in SEAL_ORDER:
            for row in _pending(table):
                if limit is not None and len(batch) >= limit:
                    break
                append(table, row.pk, row_digest(table, row))
            if limit is not None and len(batch) >= limit:
                break

        recovery = recovery_audit_state()
        if recovery is not None and (limit is None or len(batch) < limit):
            last_file = (AuditChainEntry.objects
                         .filter(source_table=RECOVERY_AUDIT_TABLE)
                         .order_by('-seq').first())
            if last_file is None or last_file.row_sha256 != recovery['sha256']:
                append(RECOVERY_AUDIT_TABLE, recovery['lines'],
                       recovery['sha256'])

        if batch:
            AuditChainEntry.objects.bulk_create(batch)
    return len(batch)


def schedule_seal():
    """Seal after the writing transaction commits, never inside it.

    Registered at most once per transaction. Resolving a round writes an audit
    row per team, and a callback per row would take the chain lock a dozen
    times to seal a dozen rows one pass could have taken. Deduplication reads
    the pending-callback list rather than setting a flag: Django discards that
    list when a transaction rolls back, so a rejected operator action cannot
    leave a stale "already scheduled" marker that suppresses the next seal.
    """
    connection_ = transaction.get_connection()
    for entry in getattr(connection_, 'run_on_commit', ()):
        if entry[1] is _seal_after_commit:
            return
    transaction.on_commit(_seal_after_commit)


def _seal_after_commit():
    try:
        seal_pending()
    except Exception:  # pragma: no cover - sealing must never break a write
        # A failed seal leaves rows unsealed; the next pass or
        # `manage.py seal_audit_chain` picks them up. Losing the audit row
        # itself would be worse than losing its tamper evidence.
        import logging
        logging.getLogger(__name__).exception('Audit chain seal failed')


def verify_chain():
    """Recompute every entry from the live rows. Returns a report dict."""
    problems = []
    prev = GENESIS_SHA256
    expected_seq = 0
    checked = 0
    caches = {}
    for table in SEAL_ORDER:
        model, _fields = PROJECTIONS[table]
        caches[table] = {row.pk: row for row in model.objects.all()}

    for entry in AuditChainEntry.objects.order_by('seq').iterator():
        expected_seq += 1
        if entry.seq != expected_seq:
            problems.append({
                'seq': entry.seq, 'kind': 'sequence_gap',
                'detail': f'expected seq {expected_seq}, found {entry.seq}'})
            expected_seq = entry.seq
        if entry.prev_sha256 != prev:
            problems.append({
                'seq': entry.seq, 'kind': 'broken_link',
                'detail': 'prev_sha256 does not match the previous entry'})
        if entry.source_table == RECOVERY_AUDIT_TABLE:
            recovery = recovery_audit_state()
            if recovery is None:
                problems.append({
                    'seq': entry.seq, 'kind': 'missing_recovery_audit',
                    'detail': 'recovery-audit.jsonl is gone'})
            row_sha = entry.row_sha256
        else:
            row = caches.get(entry.source_table, {}).get(entry.source_id)
            if row is None:
                problems.append({
                    'seq': entry.seq, 'kind': 'row_deleted',
                    'detail': (f'{entry.source_table}:{entry.source_id} is no '
                               'longer present')})
                row_sha = entry.row_sha256
            else:
                row_sha = row_digest(entry.source_table, row)
                if row_sha != entry.row_sha256:
                    problems.append({
                        'seq': entry.seq, 'kind': 'row_modified',
                        'detail': (f'{entry.source_table}:{entry.source_id} no '
                                   'longer hashes to its sealed digest')})
        # Recomputed from what the entry itself claims, not from the live
        # row: otherwise a modified row reports both `row_modified` and
        # `entry_forged`, and the second one is an echo of the first. Kept
        # separate, `entry_forged` means somebody edited the chain.
        recomputed = entry_digest(entry.prev_sha256, entry.source_table,
                                  entry.source_id, entry.row_sha256)
        if recomputed != entry.entry_sha256:
            problems.append({
                'seq': entry.seq, 'kind': 'entry_forged',
                'detail': 'entry_sha256 does not match its own inputs'})
        prev = entry.entry_sha256
        checked += 1

    unsealed = {table: _pending(table).count() for table in SEAL_ORDER}
    return {
        'checked_at': timezone.now().isoformat(),
        'entries': checked,
        'head_sha256': prev,
        'unsealed': unsealed,
        'unsealed_total': sum(unsealed.values()),
        'problems': problems,
        'ok': not problems,
    }
