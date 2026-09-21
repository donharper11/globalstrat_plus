"""V2-128: an evidence harness must not write into the live backup root."""
import importlib.util
import pathlib
import tempfile
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

HANDOFF = pathlib.Path(settings.BASE_DIR).parent / 'handoff_readiness_v2'
FIXTURES = ('determinism_fixture.py', 'v6_envelope_fixture.py',
            'r34_inactivity_fixture.py')


def _helper():
    spec = importlib.util.spec_from_file_location(
        'harness_isolation', HANDOFF / 'harness_isolation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessBackupIsolationTests(SimpleTestCase):

    def test_the_default_backup_root_is_refused(self):
        live = pathlib.Path(settings.BASE_DIR) / 'competition_backups'
        with override_settings(COMPETITION_BACKUP_DIR=live), \
                mock.patch.dict('os.environ', {}, clear=False) as env:
            env.pop('COMPETITION_BACKUP_DIR', None)
            with self.assertRaises(SystemExit) as refused:
                _helper().require_disposable_backup_dir()
        self.assertIn('V2-128', str(refused.exception))

    def test_naming_the_live_root_explicitly_is_still_refused(self):
        live = pathlib.Path(settings.BASE_DIR) / 'competition_backups' / 'x'
        with override_settings(COMPETITION_BACKUP_DIR=live), \
                mock.patch.dict('os.environ',
                                {'COMPETITION_BACKUP_DIR': str(live)}):
            with self.assertRaises(SystemExit):
                _helper().require_disposable_backup_dir()

    def test_a_disposable_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as scratch, \
                override_settings(COMPETITION_BACKUP_DIR=scratch), \
                mock.patch.dict('os.environ',
                                {'COMPETITION_BACKUP_DIR': scratch}):
            self.assertEqual(_helper().require_disposable_backup_dir(),
                             pathlib.Path(scratch).resolve())

    def test_every_fixture_that_resolves_a_round_calls_the_refusal(self):
        for name in FIXTURES:
            source = (HANDOFF / name).read_text()
            main = source[source.index('\ndef main():'):]
            self.assertIn('require_disposable_backup_dir()',
                          main[:600], name)
