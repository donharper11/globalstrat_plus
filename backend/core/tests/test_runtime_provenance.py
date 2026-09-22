"""A-04: dependency pins and effective configuration are part of provenance.

Two things sat outside the certified source digest: ``requirements.txt`` (not a
source suffix) and everything ``settings`` reads from the environment and a
gitignored ``.env`` -- including which model each purpose is routed to.

The second half of this file is about what must NOT happen: no secret may be
recorded or hashed, and none of this may enter a hashed manifest envelope.
"""
import json
import pathlib
import shutil
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.services import build_identity as B

SECRETS = {
    'SECRET_KEY': 'sk-django-THIS-MUST-NEVER-APPEAR',
    'JWT_SECRET_KEY': 'jwt-THIS-MUST-NEVER-APPEAR',
    'LLM_GATEWAY_KEY': 'gw-THIS-MUST-NEVER-APPEAR',
    'LLM_GATEWAY_URL': ('https://svc-user:urlpw-MUST-NEVER-APPEAR@gateway.'
                        'example:4000/v1/chat/completions'
                        '?api_key=qs-MUST-NEVER-APPEAR#frag-MUST-NEVER-APPEAR'),
}


class RequirementsInDigestTests(SimpleTestCase):
    def tree(self, files):
        root = pathlib.Path(tempfile.mkdtemp(prefix='provenance-'))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, body in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
        return root

    def test_a_changed_dependency_pin_changes_the_source_digest(self):
        before = B.source_tree_digest(self.tree(
            {'a.py': 'x = 1\n', 'requirements.txt': 'Django==5.2.4\n'}),
            refresh=True)
        after = B.source_tree_digest(self.tree(
            {'a.py': 'x = 1\n', 'requirements.txt': 'Django==4.2.0\n'}),
            refresh=True)
        self.assertEqual(before['file_count'], 2)
        self.assertNotEqual(before['sha256'], after['sha256'])

    def test_other_text_files_are_still_not_source(self):
        base = B.source_tree_digest(self.tree({'a.py': 'x = 1\n'}), refresh=True)
        noisy = B.source_tree_digest(self.tree(
            {'a.py': 'x = 1\n', 'notes.txt': 'n\n', '.env': 'K=v\n'}),
            refresh=True)
        self.assertEqual(base['sha256'], noisy['sha256'])

    def test_the_real_requirements_file_is_in_the_real_digest(self):
        names = {relative for relative, _absolute in B.iter_source_files()}
        self.assertIn('requirements.txt', names)
        self.assertNotIn('.env', names)


class RuntimeConfigurationTests(SimpleTestCase):
    def test_model_routing_moves_the_digest(self):
        from core.services.runtime_config import (
            runtime_configuration, runtime_configuration_digest)
        with override_settings(LLM_PURPOSE_MODELS={}):
            default = runtime_configuration()
            default_digest = runtime_configuration_digest()
        with override_settings(
                LLM_PURPOSE_MODELS={'communication_eval': 'some-other-model'}):
            routed = runtime_configuration()
            routed_digest = runtime_configuration_digest()
        self.assertEqual(default['llm_purpose_routing']['communication_eval'],
                         'tutor')
        self.assertEqual(routed['llm_purpose_routing']['communication_eval'],
                         'some-other-model')
        self.assertNotEqual(default_digest, routed_digest)

    def test_the_digest_is_stable_for_one_configuration(self):
        from core.services.runtime_config import runtime_configuration_digest
        self.assertEqual(runtime_configuration_digest(),
                         runtime_configuration_digest())
        self.assertRegex(runtime_configuration_digest(), r'^[0-9a-f]{64}$')

    def test_no_secret_value_is_recorded(self):
        from core.services.runtime_config import runtime_configuration
        with override_settings(**SECRETS):
            rendered = json.dumps(runtime_configuration())
        for needle in ('MUST-NEVER-APPEAR', 'svc-user', 'api_key'):
            self.assertNotIn(needle, rendered)
        self.assertIn('https://gateway.example:4000/v1/chat/completions',
                      rendered)

    def test_no_secret_value_is_hashed(self):
        """Changing only the credentials leaves the digest where it was, so the
        digest cannot be used to confirm a guessed secret."""
        from core.services.runtime_config import runtime_configuration_digest
        with override_settings(**SECRETS):
            first = runtime_configuration_digest()
        rotated = {name: value.replace('MUST-NEVER-APPEAR', 'ROTATED')
                   for name, value in SECRETS.items()}
        with override_settings(**rotated):
            second = runtime_configuration_digest()
        self.assertEqual(first, second)

    def test_no_secret_shaped_name_is_on_the_allow_list(self):
        from core.services.runtime_config import (
            RECORDED_SETTINGS, SECRET_SHAPED)
        for name in RECORDED_SETTINGS:
            self.assertIsNone(SECRET_SHAPED.search(name), name)
        for name in ('SECRET_KEY', 'LLM_GATEWAY_KEY', 'DB_PASSWORD',
                     'JWT_SECRET_KEY', 'DATABASES'):
            self.assertNotIn(name, RECORDED_SETTINGS)

    def test_the_database_settings_are_not_recorded(self):
        from django.conf import settings
        from core.services.runtime_config import runtime_configuration
        rendered = json.dumps(runtime_configuration())
        password = settings.DATABASES['default'].get('PASSWORD') or ''
        if len(password) >= 8:
            self.assertNotIn(password, rendered)
        self.assertNotIn('PASSWORD', rendered.upper())


class RecordedOutsideTheHashTests(TestCase):
    """It is on the manifest row, and in none of the three hashed envelopes."""

    def test_the_envelope_version_did_not_move(self):
        from core.services.manifest_version import MANIFEST_SCHEMA_VERSION
        self.assertEqual(MANIFEST_SCHEMA_VERSION, 7)

    def test_the_fingerprint_carries_the_configuration_digest(self):
        from core.services.resolution_manifest import environment_fingerprint
        fingerprint = environment_fingerprint()
        self.assertRegex(fingerprint['runtime_config_sha256'], r'^[0-9a-f]{64}$')
        self.assertRegex(fingerprint['requirements_sha256'], r'^[0-9a-f]{64}$')
        self.assertRegex(fingerprint['installed_packages_sha256'],
                         r'^[0-9a-f]{64}$')
        self.assertIn('llm_purpose_routing', fingerprint['runtime_config'])

    def test_a_resolved_round_records_it_and_hashes_none_of_it(self):
        from core.engine.advance_round import process_round
        from core.models import DecisionSubmission, ResolutionManifest
        from core.models.core import Round
        from core.services.canonical_json import canonical_dumps, canonical_sha256
        from core.tests.test_durable_narratives import build_game
        game, teams = build_game(f'a04-{id(self)}')
        round_obj = Round.objects.create(
            game=game, round_number=1, status='closed', opened_at=timezone.now())
        for team in teams:
            DecisionSubmission.objects.create(
                team=team, round=round_obj, status='locked',
                locked_at=timezone.now())
        with patch('core.engine.advance_round._run_phase_2'):
            process_round(game.id)
        manifest = ResolutionManifest.objects.get(round=round_obj)
        self.assertRegex(manifest.environment['runtime_config_sha256'],
                         r'^[0-9a-f]{64}$')
        for body in (manifest.input_manifest, manifest.output_manifest,
                     manifest.narrative_manifest):
            rendered = canonical_dumps(body)
            for needle in ('runtime_config', 'llm_purpose_routing',
                           'requirements_sha256', 'installed_packages'):
                self.assertNotIn(needle, rendered)
        # And the stored hashes are still exactly the hash of those bodies.
        self.assertEqual(manifest.input_sha256,
                         canonical_sha256(manifest.input_manifest))
        self.assertEqual(manifest.output_sha256,
                         canonical_sha256(manifest.output_manifest))
