"""`manage.py resolve_stored_revision` -- the V2-048 translation, under test.

The command had no tests. It is the only thing that ties a round resolved
before the 2026-09-04 history rewrite to a commit that still exists, so what it
reports is what an auditor is told about those rounds.

The repository is a throwaway one built per test; the commit map is a temporary
file. The one test that reads the real, committed map says so.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.management.commands import resolve_stored_revision as R

PRE_REWRITE = 'b' * 40      # a hash the repository has never contained
NOWHERE = 'c' * 40


def _git(root, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(
        ['git', '-C', str(root), '-c', 'user.name=test',
         '-c', 'user.email=test@example.invalid', '-c', 'commit.gpgsign=false',
         *args],
        check=True, capture_output=True, text=True, env=env).stdout.strip()


class RepositoryMixin:
    def build_repository(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix='stored-revision-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'file.txt').write_text('one\n')
        _git(self.root, 'init', '-q')
        _git(self.root, 'add', '-A')
        _git(self.root, 'commit', '-q', '-m', 'one')
        self.head = _git(self.root, 'rev-parse', 'HEAD')
        map_path = self.root / R.MAP_PATH
        map_path.parent.mkdir(parents=True)
        map_path.write_text(
            'old                                      new\n'
            f'{PRE_REWRITE} {self.head}\n'
            f'{"d" * 40} {"e" * 40}\n')       # maps to a commit that is absent
        patcher = mock.patch.object(R, '_repo_root', return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)


class ResolveTests(RepositoryMixin, SimpleTestCase):
    def setUp(self):
        self.build_repository()

    def test_a_commit_that_exists_is_present(self):
        self.assertEqual(R.resolve(self.head), ('present', self.head))

    def test_a_pre_rewrite_hash_translates_through_the_map(self):
        self.assertEqual(R.resolve(PRE_REWRITE), ('translated', self.head))

    def test_the_dirty_suffix_is_stripped_before_lookup(self):
        self.assertEqual(R.resolve(f'{PRE_REWRITE}-dirty'),
                         ('translated', self.head))
        self.assertEqual(R.resolve(f'{self.head}-dirty'), ('present', self.head))

    def test_a_hash_in_neither_place_is_unknown(self):
        self.assertEqual(R.resolve(NOWHERE), ('unknown', NOWHERE))

    def test_a_mapping_to_a_commit_that_is_absent_is_unknown(self):
        """The map alone proves nothing; the target has to exist here."""
        self.assertEqual(R.resolve('d' * 40), ('unknown', 'd' * 40))

    def test_an_empty_revision_is_unknown(self):
        self.assertEqual(R.resolve('')[0], 'unknown')
        self.assertEqual(R.resolve(None)[0], 'unknown')

    def test_a_missing_map_is_an_error_not_an_empty_translation(self):
        (self.root / R.MAP_PATH).unlink()
        with self.assertRaisesRegex(CommandError, 'commit map is missing'):
            R.resolve(PRE_REWRITE)

    def test_the_command_reports_one_revision(self):
        out = StringIO()
        call_command('resolve_stored_revision', PRE_REWRITE, stdout=out)
        self.assertIn(f'translated: {self.head}', out.getvalue())

    def test_the_command_fails_on_an_unknown_revision(self):
        with self.assertRaisesRegex(CommandError, 'not in the V2-048 commit map'):
            call_command('resolve_stored_revision', NOWHERE, stdout=StringIO())

    def test_the_command_needs_an_argument(self):
        with self.assertRaisesRegex(CommandError, 'Give a revision'):
            call_command('resolve_stored_revision', stdout=StringIO())


class CommittedMapTests(SimpleTestCase):
    """The real file, as committed. Losing it is what would make the
    pre-rewrite rounds genuinely unrecoverable (V2-054)."""

    def test_the_committed_map_parses_and_carries_the_six_production_hashes(self):
        mapping = R._load_map()
        self.assertGreater(len(mapping), 400)
        for stored in ('1189a50d41a502955f77fc505610165735ba6fac',
                       '3ffba4d363535346b8ea3aca3f813360762b8034',
                       '564bb3c38e75bc8581ddbf2dc01bb62bf6b431d3',
                       '7df03edfcd4f8962494a853ee0bc5cb25bb23377',
                       '61c43da4a864ca6022d1e088c11a4f9f09246399',
                       '30cc26e93c7fb1e3edc23c19e54c051f6194067c'):
            with self.subTest(stored=stored[:12]):
                self.assertRegex(mapping.get(stored, ''), r'^[0-9a-f]{40}$')


class AllStoredTests(RepositoryMixin, TestCase):
    def setUp(self):
        from core.models import ResolutionManifest
        from core.models.core import Round
        from core.tests.test_durable_narratives import build_game
        self.build_repository()
        self.game, _teams = build_game(f'stored-rev-{id(self)}')
        self.Manifest, self.Round = ResolutionManifest, Round
        self.number = 0

    def store(self, revision):
        self.number += 1
        round_obj = self.Round.objects.create(
            game=self.game, round_number=self.number, status='closed',
            opened_at=timezone.now())
        return self.Manifest.objects.create(
            game=self.game, round=round_obj, seed='s' * 64, input_manifest={},
            input_sha256='i' * 64, code_revision=revision)

    def run_all(self):
        out = StringIO()
        call_command('resolve_stored_revision', all_stored=True, stdout=out)
        return out.getvalue()

    def test_every_revision_resolving_exits_clean(self):
        self.store(self.head)
        self.store(PRE_REWRITE)
        self.store(f'{PRE_REWRITE}-dirty')
        output = self.run_all()
        self.assertIn('present', output)
        self.assertIn('translated', output)
        self.assertIn('Every stored revision resolves', output)

    def test_an_empty_revision_fails_the_run(self):
        """V2-120: nine production rows record nothing, and nothing translates."""
        self.store(self.head)
        self.store('')
        with self.assertRaisesRegex(CommandError, '1 stored revision'):
            self.run_all()

    def test_an_unknown_revision_fails_the_run(self):
        self.store(NOWHERE)
        with self.assertRaisesRegex(CommandError, 'cannot be tied to a commit'):
            self.run_all()
