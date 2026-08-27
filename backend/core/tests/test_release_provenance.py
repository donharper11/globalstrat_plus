import hashlib
import io
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.services.competition_backup import inspect_backups
from core.services.resolution_manifest import resolve_code_revision


def make_backup(root, name='game-1-round-1-20260101T000000000000Z.dump',
                content=b'backup'):
    target = Path(root) / name
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    target.with_suffix('.dump.sha256').write_text(
        f'{digest}  {target.name}\n', encoding='utf-8')
    return target


class ReleaseProvenanceTests(SimpleTestCase):
    @override_settings(GIT_REVISION='release-2026.08.27+abc123')
    def test_explicit_revision_is_used(self):
        self.assertEqual(resolve_code_revision(), 'release-2026.08.27+abc123')

    @override_settings(GIT_REVISION='unknown')
    def test_placeholder_revision_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'not a valid release identifier'):
            resolve_code_revision()

    @override_settings(GIT_REVISION='release revision with spaces')
    def test_malformed_revision_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'not a valid release identifier'):
            resolve_code_revision()

    @override_settings(GIT_REVISION='')
    @patch('core.services.resolution_manifest.subprocess.run')
    def test_git_fallback_marks_dirty_worktree(self, run):
        run.side_effect = [Mock(stdout='a' * 40 + '\n'), Mock(stdout=' M file.py\n')]
        self.assertEqual(resolve_code_revision(), 'a' * 40 + '-dirty')

    @override_settings(GIT_REVISION='')
    @patch('core.services.resolution_manifest.subprocess.run',
           side_effect=subprocess.CalledProcessError(128, 'git'))
    def test_missing_revision_and_git_fails_closed(self, _run):
        with self.assertRaisesRegex(RuntimeError, 'Set GIT_REVISION'):
            resolve_code_revision()

    @override_settings(GIT_REVISION='', IS_PRODUCTION=True)
    def test_production_requires_explicit_revision(self):
        with self.assertRaisesRegex(RuntimeError, 'explicit GIT_REVISION'):
            resolve_code_revision()


class BackupRetentionTests(SimpleTestCase):
    def test_inspection_reports_expired_and_invalid_without_deleting(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(
                COMPETITION_BACKUP_DIR=directory):
            expired = make_backup(directory)
            old = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
            os.utime(expired, (old, old))
            invalid = Path(directory) / 'game-2-round-1-bad.dump'
            invalid.write_bytes(b'no checksum')

            records = inspect_backups(30)

            self.assertEqual(len(records), 2)
            self.assertTrue(records[0]['expired'])
            self.assertTrue(records[0]['valid'])
            self.assertFalse(records[1]['valid'])
            self.assertTrue(expired.exists())
            self.assertTrue(invalid.exists())

    def test_pruning_requires_enable_reason_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(
                COMPETITION_BACKUP_DIR=directory,
                COMPETITION_BACKUP_PRUNE_ENABLED=False):
            make_backup(directory)
            with self.assertRaisesRegex(CommandError, 'disabled'):
                call_command('manage_competition_backups', delete_expired=True,
                             retention_days=30, reason='Planned retention cleanup',
                             confirm='DELETE-BACKUPS-OLDER-THAN-30-DAYS')

    def test_pruning_deletes_only_verified_expired_pairs_and_audits(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(
                COMPETITION_BACKUP_DIR=directory,
                COMPETITION_BACKUP_PRUNE_ENABLED=True):
            expired = make_backup(directory)
            current = make_backup(
                directory, 'game-2-round-1-20260827T000000000000Z.dump', b'current')
            malformed = Path(directory) / 'game-3-round-1-bad.dump'
            malformed.write_bytes(b'malformed')
            old = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
            os.utime(expired, (old, old))

            call_command('manage_competition_backups', delete_expired=True,
                         retention_days=30, reason='Apply approved retention policy',
                         confirm='DELETE-BACKUPS-OLDER-THAN-30-DAYS')

            self.assertFalse(expired.exists())
            self.assertFalse(expired.with_suffix('.dump.sha256').exists())
            self.assertTrue(current.exists())
            self.assertTrue(malformed.exists())
            audit = [json.loads(line) for line in
                     (Path(directory) / 'recovery-audit.jsonl').read_text().splitlines()]
            self.assertEqual([row['action'] for row in audit],
                             ['backup_prune_intent', 'backup_prune_complete'])
            self.assertEqual(audit[-1]['deleted_count'], 1)

    def test_default_command_is_read_only_json_inspection(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(
                COMPETITION_BACKUP_DIR=directory):
            target = make_backup(directory)
            output = io.StringIO()
            call_command('manage_competition_backups', stdout=output)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload['backup_count'], 1)
            self.assertTrue(target.exists())

    def test_explicit_zero_retention_is_rejected(self):
        with self.assertRaisesRegex(CommandError, 'at least 1'):
            call_command('manage_competition_backups', retention_days=0)
