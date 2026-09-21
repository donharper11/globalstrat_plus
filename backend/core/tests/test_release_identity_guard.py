"""A-03: the advertised revision must name the code that is running.

Production is a git checkout whose ``GIT_REVISION`` is typed by hand. On
2026-09-21 the running backend advertised ``0fd9a39`` while the tree on disk was
a later commit, and ``check_release_identity`` had been logging that every
fifteen minutes for days without anything acting on it. Resolution believed the
configured value verbatim, so every round would have been stamped with a commit
that did not produce it.

Every test here builds a real, throwaway git checkout in a temporary directory
and points ``BASE_DIR`` at its ``backend/`` -- the repository this test file
lives in is never consulted, and nothing is mocked except where the point of
the test is that git itself is unusable.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.services import build_identity as B

OTHER_COMMIT = 'a' * 40


def _git(root, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(
        ['git', '-C', str(root), '-c', 'user.name=test',
         '-c', 'user.email=test@example.invalid', '-c', 'commit.gpgsign=false',
         *args],
        check=True, capture_output=True, text=True, env=env).stdout.strip()


class CheckoutCase(SimpleTestCase):
    """A disposable deployment: ``<tmp>/backend`` inside a one-commit repo."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix='release-identity-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.backend = self.root / 'backend'
        self.backend.mkdir()
        (self.backend / 'engine.py').write_text('RATE = 1\n')
        (self.backend / 'requirements.txt').write_text('Django==5.2.4\n')
        settings_override = override_settings(BASE_DIR=self.backend)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def make_checkout(self):
        _git(self.root, 'init', '-q')
        return self.commit('release')

    def commit(self, message):
        _git(self.root, 'add', '-A')
        _git(self.root, 'commit', '-q', '-m', message)
        return _git(self.root, 'rev-parse', 'HEAD')

    def identity(self, revision):
        tree = B.source_tree_digest()
        return {'code_revision': revision,
                'code_revision_is_dirty': revision.endswith('-dirty'),
                'source_tree_sha256': tree['sha256'],
                'source_file_count': tree['file_count'],
                'source_root': tree['root']}


@override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=True)
class ResolutionGuardTests(CheckoutCase):
    """``require_identified_build`` with the clean-build flag on."""

    def test_a_stale_advertised_revision_is_refused(self):
        """The 2026-09-21 production state: a real-looking hash that is not HEAD."""
        self.make_checkout()
        with self.assertRaisesRegex(RuntimeError, 'drifted'):
            B.require_identified_build(self.identity(OTHER_COMMIT))

    def test_the_matching_clean_checkout_is_accepted(self):
        head = self.make_checkout()
        identity = self.identity(head)
        self.assertEqual(B.require_identified_build(identity), identity)

    def test_a_label_that_is_not_a_commit_is_refused(self):
        self.make_checkout()
        for label in ('release-2026.09', 'abc123', 'HEAD', 'A' * 40):
            with self.subTest(label=label):
                with self.assertRaisesRegex(RuntimeError, 'not a full commit hash'):
                    B.require_identified_build(self.identity(label))

    def test_head_with_a_modified_tracked_file_is_refused(self):
        """GIT_REVISION set by hand never carries `-dirty`, so the suffix test
        alone could not see this."""
        head = self.make_checkout()
        (self.backend / 'engine.py').write_text('RATE = 2\n')
        with self.assertRaisesRegex(RuntimeError, 'uncommitted changes'):
            B.require_identified_build(self.identity(head))

    def test_a_checkout_git_cannot_read_is_refused_not_waved_through(self):
        """"git failed" must not be read as "immutable build"."""
        head = self.make_checkout()
        identity = self.identity(head)
        with mock.patch('subprocess.run', side_effect=OSError('no git')):
            with self.assertRaisesRegex(RuntimeError, 'cannot be verified'):
                B.require_identified_build(identity)

    def test_an_immutable_build_keeps_todays_behaviour(self):
        """No `.git` anywhere above the code: nothing to compare against."""
        self.assertIsNone(B._find_git_marker(self.root))
        identity = self.identity(OTHER_COMMIT)
        self.assertEqual(B.require_identified_build(identity), identity)

    def test_code_changed_on_disk_after_the_process_started_is_refused(self):
        """Committed, clean, advertised correctly -- and still not what is
        loaded, because the process started before the change."""
        self.make_checkout()
        B.source_tree_digest()                       # the process "starts"
        (self.backend / 'engine.py').write_text('RATE = 3\n')
        new_head = self.commit('hotfix deployed without a restart')
        with override_settings(GIT_REVISION=new_head):
            with self.assertRaisesRegex(
                    RuntimeError, 'changed since this process started'):
                B.require_identified_build()

    def test_the_refusal_tells_the_operator_what_to_do(self):
        self.make_checkout()
        with self.assertRaises(RuntimeError) as caught:
            B.require_identified_build(self.identity(OTHER_COMMIT))
        message = str(caught.exception)
        for needle in ('git rev-parse HEAD', 'GIT_REVISION', 'Restart',
                       'narrative worker', 'check_release_identity',
                       OTHER_COMMIT[:12]):
            self.assertIn(needle, message)

    def test_the_uncommitted_suffix_is_still_refused_with_its_own_message(self):
        head = self.make_checkout()
        with self.assertRaisesRegex(RuntimeError, 'uncommitted working tree'):
            B.require_identified_build(self.identity(f'{head}-dirty'))


class DevelopmentBehaviourTests(CheckoutCase):
    """With the flag off -- development, tests, most harnesses -- nothing moves."""

    @override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=False)
    def test_nothing_is_checked_when_the_flag_is_off(self):
        self.make_checkout()
        for revision in (OTHER_COMMIT, 'rev-under-test', 'abc-dirty'):
            identity = self.identity(revision)
            with mock.patch('subprocess.run',
                            side_effect=AssertionError('git was consulted')):
                self.assertEqual(B.require_identified_build(identity), identity)

    @override_settings(COMPETITION_REQUIRE_CLEAN_BUILD=True, GIT_REVISION='',
                       IS_PRODUCTION=False)
    def test_a_guessed_revision_on_a_clean_checkout_still_resolves(self):
        """A harness that turns the flag on without naming a revision gets HEAD
        guessed for it, as before, and HEAD is by construction not drifted."""
        head = self.make_checkout()
        with mock.patch.dict(os.environ, {'GIT_REVISION': ''}):
            identity = B.require_identified_build()
        self.assertEqual(identity['code_revision'], head)


class StartupDigestTests(CheckoutCase):
    """The digest must describe the loaded code, so it is taken at start."""

    def test_app_startup_takes_the_digest_before_anything_can_change(self):
        from django.apps import apps
        before = B._digest_tree(str(self.backend)) if hasattr(
            B, '_digest_tree') else None
        apps.get_app_config('core').ready()
        (self.backend / 'engine.py').write_text('RATE = 99\n')
        recorded = B.source_tree_digest()
        after = B.source_tree_digest(refresh=True)
        self.assertNotEqual(recorded['sha256'], after['sha256'],
                            'the digest was taken after the edit, so it '
                            'describes the disk and not the loaded code')
        if before is not None:
            self.assertEqual(recorded['sha256'], before['sha256'])

    def test_priming_twice_keeps_the_first_digest(self):
        first = B.prime_source_tree_digest()
        (self.backend / 'engine.py').write_text('RATE = 5\n')
        second = B.prime_source_tree_digest()
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertIsNotNone(B.loaded_source_drift())


class RecoveryComparisonTests(TestCase):
    """RD-03 compares the stored revision with the running one. That is only
    meaningful if the running one is true."""

    def setUp(self):
        import hashlib
        from core.models import ResolutionManifest, User
        from core.models.core import Round
        from core.tests.test_durable_narratives import build_game
        self.root = pathlib.Path(tempfile.mkdtemp(prefix='release-recovery-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.backend = self.root / 'backend'
        self.backend.mkdir()
        (self.backend / 'engine.py').write_text('RATE = 1\n')
        _git(self.root, 'init', '-q')
        _git(self.root, 'add', '-A')
        _git(self.root, 'commit', '-q', '-m', 'release')
        self.head = _git(self.root, 'rev-parse', 'HEAD')
        self.backups = self.root / 'backups'
        self.backups.mkdir()
        dump = self.backups / 'round.dump'
        dump.write_bytes(b'test backup')
        digest = hashlib.sha256(dump.read_bytes()).hexdigest()
        dump.with_suffix('.dump.sha256').write_text(f'{digest}  {dump.name}\n')
        self.game, _teams = build_game(f'recovery-{id(self)}')
        round_obj = Round.objects.create(
            game=self.game, round_number=1, status='closed',
            opened_at=timezone.now())
        User.objects.create(username='identity-instructor', role='instructor',
                            password_hash='x')
        # The stored round claims the stale revision -- exactly what a drifted
        # production would have written, and would now "match".
        ResolutionManifest.objects.create(
            game=self.game, round=round_obj, seed='s' * 64, input_manifest={},
            input_sha256='i' * 64, backup_path=str(dump),
            code_revision=OTHER_COMMIT)

    def recover(self, **extra):
        call_command(
            'recover_competition_round', game_id=self.game.id, round_number=1,
            actor='identity-instructor',
            reason='Correct a verified scoring defect',
            confirm=f'RESTORE-GAME-{self.game.id}-ROUND-1', dry_run=True,
            stdout=StringIO(), **extra)

    def settings_for(self, strict):
        return override_settings(
            BASE_DIR=self.backend, COMPETITION_RECOVERY_ENABLED=True,
            COMPETITION_BACKUP_DIR=self.backups, GIT_REVISION=OTHER_COMMIT,
            COMPETITION_REQUIRE_CLEAN_BUILD=strict)

    def test_a_drifted_build_cannot_match_a_manifest_by_sharing_its_lie(self):
        from django.core.management.base import CommandError
        with self.settings_for(strict=True):
            with self.assertRaisesRegex(CommandError, 'cannot be trusted'):
                self.recover()

    def test_the_override_still_lets_an_incident_restore_proceed(self):
        import json
        with self.settings_for(strict=True):
            self.recover(allow_code_revision_mismatch=True)
        records = [json.loads(line) for line in
                   (self.backups / 'recovery-audit.jsonl').read_text().splitlines()]
        self.assertEqual(records[-1]['running_release_identity'], 'drifted')
        self.assertTrue(records[-1]['code_revision_override'])

    def test_with_the_flag_off_recovery_behaves_as_before(self):
        with self.settings_for(strict=False):
            self.recover()


class CheckReleaseIdentityCommandTests(CheckoutCase):
    """`manage.py check_release_identity` -- the same logic, as an exit code."""

    def run_command(self, **options):
        out, err = StringIO(), StringIO()
        code = 0
        try:
            call_command('check_release_identity', stdout=out, stderr=err,
                         **options)
        except SystemExit as exit_:
            code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_verified(self):
        head = self.make_checkout()
        with override_settings(GIT_REVISION=head):
            code, out, _err = self.run_command()
        self.assertEqual(code, 0)
        self.assertIn('Release identity verified', out)

    def test_quiet_says_nothing_when_it_agrees(self):
        head = self.make_checkout()
        with override_settings(GIT_REVISION=head):
            code, out, err = self.run_command(quiet=True)
        self.assertEqual((code, out, err), (0, '', ''))

    def test_drift_exits_nonzero_and_names_both_commits(self):
        head = self.make_checkout()
        with override_settings(GIT_REVISION=OTHER_COMMIT):
            code, _out, err = self.run_command(quiet=True)
        self.assertEqual(code, 1)
        self.assertIn('drifted', err)
        self.assertIn(OTHER_COMMIT[:12], err)
        self.assertIn(head[:12], err)

    def test_a_modified_tracked_file_exits_nonzero(self):
        head = self.make_checkout()
        (self.backend / 'engine.py').write_text('RATE = 2\n')
        with override_settings(GIT_REVISION=head):
            code, _out, err = self.run_command()
        self.assertEqual(code, 1)
        self.assertIn('uncommitted changes', err)

    def test_unset_exits_nonzero(self):
        self.make_checkout()
        with override_settings(GIT_REVISION=''):
            code, _out, err = self.run_command()
        self.assertEqual(code, 1)
        self.assertIn('GIT_REVISION is unset', err)

    def test_an_immutable_build_exits_zero(self):
        with override_settings(GIT_REVISION=OTHER_COMMIT):
            code, out, _err = self.run_command()
        self.assertEqual(code, 0)
        self.assertIn('immutable build', out)

    def test_a_label_is_refused_even_on_an_immutable_build(self):
        with override_settings(GIT_REVISION='release-2026.09'):
            code, _out, err = self.run_command()
        self.assertEqual(code, 1)
        self.assertIn('not a full commit hash', err)

    def test_unusable_git_in_a_checkout_exits_nonzero(self):
        head = self.make_checkout()
        with override_settings(GIT_REVISION=head):
            with mock.patch('subprocess.run', side_effect=OSError('no git')):
                code, _out, err = self.run_command()
        self.assertEqual(code, 1)
        self.assertIn('cannot be verified', err)

    def test_the_command_and_the_guard_agree(self):
        """One implementation: whatever the command fails, resolution refuses."""
        self.make_checkout()
        with override_settings(GIT_REVISION=OTHER_COMMIT,
                               COMPETITION_REQUIRE_CLEAN_BUILD=True):
            code, _out, err = self.run_command()
            with self.assertRaises(RuntimeError) as caught:
                B.require_identified_build()
        self.assertEqual(code, 1)
        report = B.release_identity(OTHER_COMMIT)
        self.assertIn(report['message'], err.replace('\n', ' ') + ' ')
        self.assertIn(report['message'], str(caught.exception))


class OperatorDataIsNotSourceTests(SimpleTestCase):
    """A backup directory inside the tree must not read as a code change."""

    def test_a_renamed_backup_directory_inside_the_tree_is_not_hashed(self):
        import json
        import tempfile
        from django.test import override_settings
        from core.services import build_identity
        with tempfile.TemporaryDirectory() as tree:
            root = pathlib.Path(tree)
            (root / 'engine.py').write_text('x = 1\n')
            store = root / 'round_dumps' / 'manifests'
            store.mkdir(parents=True)
            with override_settings(COMPETITION_BACKUP_DIR=root / 'round_dumps'):
                before = build_identity.source_tree_digest(root, refresh=True)
                (store / 'body.json').write_text(json.dumps({'round': 1}))
                after = build_identity.source_tree_digest(root, refresh=True)
                self.assertEqual(before, after)
                # Control: a real source change still moves the digest.
                (root / 'engine.py').write_text('x = 2\n')
                self.assertNotEqual(
                    after, build_identity.source_tree_digest(root, refresh=True))
