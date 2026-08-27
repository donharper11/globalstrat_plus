"""Verified PostgreSQL snapshot taken immediately before round resolution."""
import hashlib
import json
import os
import pathlib
import subprocess
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import connection


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
    """Restore a verified custom-format dump into the configured database."""
    verified = verify_backup(backup_path)
    db = connection.settings_dict
    env = os.environ.copy()
    env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
    cmd = ['pg_restore', '--clean', '--if-exists', '--no-owner', '--exit-on-error']
    if db.get('HOST'): cmd += ['--host', str(db['HOST'])]
    if db.get('PORT'): cmd += ['--port', str(db['PORT'])]
    if db.get('USER'): cmd += ['--username', str(db['USER'])]
    cmd += ['--dbname', str(db['NAME']), verified['path']]
    connection.close()
    subprocess.run(cmd, env=env, check=True, timeout=600, capture_output=True)
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
