"""Verified PostgreSQL snapshot taken immediately before round resolution."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import connection


# A newer pg_dump (17/18) writes GUCs such as `transaction_timeout` that an
# older server (16) rejects on restore. Those SET failures do not touch the
# restored data, so they must not fail an otherwise-clean recovery.
_BENIGN_RESTORE_ERROR = re.compile(
    r'unrecognized configuration parameter|errors ignored on restore', re.I)


def _restore_stderr_is_benign(stderr):
    """True when pg_restore's only complaints are cross-version SET no-ops.

    Every genuine error line (anything reported as an error that is not a
    benign version-skew SET) makes this return False so the caller can fail.
    """
    for line in (stderr or '').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        is_error = 'error:' in lowered or lowered.startswith('pg_restore: error')
        if not is_error:
            # warnings, DETAIL/HINT and "Command was:" context lines
            continue
        if _BENIGN_RESTORE_ERROR.search(stripped):
            continue
        return False
    return True


def backup_root():
    return pathlib.Path(getattr(
        settings, 'COMPETITION_BACKUP_DIR',
        settings.BASE_DIR / 'competition_backups')).resolve()


def verify_backup(backup_path):
    """Validate that a dump is inside the configured root and matches SHA-256."""
    root = backup_root()
    target = pathlib.Path(backup_path).resolve()
    if root != target.parent and root not in target.parents:
        raise ValueError('Backup path is outside COMPETITION_BACKUP_DIR.')
    if not target.is_file() or target.stat().st_size == 0:
        raise ValueError('Backup file is missing or empty.')
    checksum = target.with_suffix(target.suffix + '.sha256')
    if not checksum.is_file():
        raise ValueError('Backup checksum file is missing.')
    expected = checksum.read_text(encoding='utf-8').split()[0]
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError('Backup checksum does not match.')
    return {'path': str(target), 'sha256': actual, 'size': target.stat().st_size}


def append_recovery_audit(payload):
    """Write an audit record that survives restoration of the database itself."""
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'recovery-audit.jsonl'
    record = {'timestamp': datetime.now(timezone.utc).isoformat(), **payload}
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return str(path)


def restore_database(backup_path):
    """Restore a verified custom-format dump into the configured database.

    Restores onto a freshly recreated public schema rather than relying on
    `pg_restore --clean`. Dropping the schema first means no FK-referenced
    object survives to block a dependency-ordered object drop, and the restore
    then tolerates only benign cross-version SET failures (see
    ``_restore_stderr_is_benign``). Any other pg_restore error is fatal.
    """
    verified = verify_backup(backup_path)
    db = connection.settings_dict
    env = os.environ.copy()
    env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
    conn_args = []
    if db.get('HOST'): conn_args += ['--host', str(db['HOST'])]
    if db.get('PORT'): conn_args += ['--port', str(db['PORT'])]
    if db.get('USER'): conn_args += ['--username', str(db['USER'])]
    connection.close()
    # Clean slate: no surviving object can block the restore's object creation.
    subprocess.run(
        ['psql', *conn_args, '--dbname', str(db['NAME']),
         '--set', 'ON_ERROR_STOP=on',
         '--command', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'],
        env=env, check=True, timeout=120, capture_output=True)
    result = subprocess.run(
        ['pg_restore', '--no-owner', *conn_args, '--dbname', str(db['NAME']),
         verified['path']],
        env=env, timeout=600, capture_output=True, text=True)
    if result.returncode != 0 and not _restore_stderr_is_benign(result.stderr):
        raise RuntimeError(
            f'pg_restore failed while restoring {verified["path"]}:\n'
            f'{(result.stderr or "").strip()}')
    return verified


def backup_before_resolution(game_id, round_number):
    db = connection.settings_dict
    # Django creates disposable test DBs; a physical backup adds no recovery value.
    if str(db.get('NAME', '')).startswith('test_'):
        return 'test-database://transactional'
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = root / f'game-{game_id}-round-{round_number}-{stamp}.dump'
    env = os.environ.copy()
    env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
    cmd = ['pg_dump', '--format=custom', '--no-owner', '--file', str(target)]
    if db.get('HOST'): cmd += ['--host', str(db['HOST'])]
    if db.get('PORT'): cmd += ['--port', str(db['PORT'])]
    if db.get('USER'): cmd += ['--username', str(db['USER'])]
    cmd += [str(db['NAME'])]
    subprocess.run(cmd, env=env, check=True, timeout=300, capture_output=True)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError('Pre-resolution backup was not created.')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum = target.with_suffix(target.suffix + '.sha256')
    checksum.write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    return str(target)


def inspect_backups(retention_days=None, now=None):
    """Inventory managed dumps without changing them."""
    days = (getattr(settings, 'COMPETITION_BACKUP_RETENTION_DAYS', 30)
            if retention_days is None else retention_days)
    if not isinstance(days, int) or days < 1:
        raise ValueError('Backup retention must be a positive number of days.')
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    root = backup_root()
    if not root.exists():
        return []
    records = []
    for target in sorted(root.glob('game-*-round-*.dump')):
        modified = datetime.fromtimestamp(target.stat().st_mtime, timezone.utc)
        record = {
            'path': str(target.resolve()), 'modified_at': modified.isoformat(),
            'expired': modified < cutoff, 'valid': False,
        }
        try:
            record.update(verify_backup(target))
            record['valid'] = True
        except (OSError, ValueError) as exc:
            record['error'] = str(exc)
        records.append(record)
    return records


def prune_expired_backups(*, retention_days, reason, confirm):
    """Delete verified expired dump/checksum pairs behind explicit safeguards."""
    if not getattr(settings, 'COMPETITION_BACKUP_PRUNE_ENABLED', False):
        raise ValueError('Backup pruning is disabled by configuration.')
    if len(reason.strip()) < 10:
        raise ValueError('A specific pruning reason of at least 10 characters is required.')
    token = f'DELETE-BACKUPS-OLDER-THAN-{retention_days}-DAYS'
    if confirm != token:
        raise ValueError(f'Confirmation mismatch; expected {token}.')
    candidates = [record for record in inspect_backups(retention_days)
                  if record['expired'] and record['valid']]
    audit = {
        'action': 'backup_prune_intent', 'reason': reason.strip(),
        'retention_days': retention_days,
        'backups': [{'path': item['path'], 'sha256': item['sha256'],
                     'size': item['size']} for item in candidates],
    }
    append_recovery_audit(audit)
    deleted = []
    for item in candidates:
        current = verify_backup(item['path'])
        if current['sha256'] != item['sha256']:
            raise ValueError(f"Backup changed during pruning: {item['path']}")
        target = pathlib.Path(item['path'])
        target.unlink()
        target.with_suffix(target.suffix + '.sha256').unlink()
        deleted.append(item)
    append_recovery_audit({**audit, 'action': 'backup_prune_complete',
                           'deleted_count': len(deleted)})
    return deleted
