from django.contrib.auth.models import User as DjangoUser
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import (DecisionAuditEvent, Game, ResolutionManifest, Round,
                         Scenario, Team, User)
from core.models.scenario import FirmStarterProfile, MarketDefinition


class CompetitionAuditTests(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username='owner-hardening')
        self.user = User.objects.create(username='hardening-student', role='student', password_hash='x')
        scenario = Scenario.objects.create(name='Hardening', industry_label='Test', description='d',
                                           starting_cash=1000, num_rounds=2)
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HM', description='d', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=0, entry_cost_base=0, tax_rate=0,
            regulatory_difficulty=1, infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Starter', description='d', home_market=market,
            starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(scenario=scenario, name='Hardening game', current_round=1,
                                        status='active', created_by=owner)
        self.round = Round.objects.create(game=self.game, round_number=1, status='open',
                                          opened_at=timezone.now())
        self.team = Team.objects.create(game=self.game, name='T', firm_starter_profile=profile,
                                        performance_index=100, cash_on_hand=1000,
                                        total_equity=1000)

    def test_audit_event_hashes_payload_and_is_immutable(self):
        event = DecisionAuditEvent.objects.create(
            game=self.game, team=self.team, round=self.round, user=self.user,
            action='save', endpoint='/test', payload={'b': 2, 'a': 1})
        self.assertEqual(len(event.payload_sha256), 64)
        event.action = 'tampered'
        with self.assertRaises(ValueError):
            event.save()

    def test_submission_origin_distinguishes_missing_from_deliberate_empty(self):
        """V-1: an instructor can tell a never-submitted/defaulted team apart from
        a team that produced a (possibly empty) draft, without the database."""
        from core.views.results_api import classify_submission_origin
        from core.models import DecisionSubmission
        from django.utils import timezone

        r2 = Round.objects.create(game=self.game, round_number=2, status='closed',
                                  opened_at=timezone.now())
        r3 = Round.objects.create(game=self.game, round_number=3, status='closed',
                                  opened_at=timezone.now())
        r4 = Round.objects.create(game=self.game, round_number=4, status='open',
                                  opened_at=timezone.now())

        # No submission at all.
        self.assertEqual(
            classify_submission_origin(self.game, self.team, self.round, None),
            'no_submission')

        # Never submitted -> defaulted at close (empty locked shell + audit action).
        s1 = DecisionSubmission.objects.create(team=self.team, round=self.round,
                                               status='locked')
        DecisionAuditEvent.objects.create(
            game=self.game, team=self.team, round=self.round, user=None,
            action='missing_submission_defaulted', endpoint='engine:close_round',
            payload={})
        self.assertEqual(
            classify_submission_origin(self.game, self.team, self.round, s1),
            'defaulted_missing')

        # Deliberate empty: had a draft that was auto-locked at the deadline.
        s2 = DecisionSubmission.objects.create(team=self.team, round=r2,
                                               status='locked')
        DecisionAuditEvent.objects.create(
            game=self.game, team=self.team, round=r2, user=None,
            action='deadline_lock', endpoint='engine:close_round', payload={})
        self.assertEqual(
            classify_submission_origin(self.game, self.team, r2, s2),
            'deadline_locked')

        # Team locked its own submission (no close-time default/deadline event).
        s3 = DecisionSubmission.objects.create(team=self.team, round=r3,
                                               status='locked')
        self.assertEqual(
            classify_submission_origin(self.game, self.team, r3, s3),
            'student_locked')

        # Draft, still open.
        s4 = DecisionSubmission.objects.create(team=self.team, round=r4,
                                               status='draft')
        self.assertEqual(
            classify_submission_origin(self.game, self.team, r4, s4), 'draft')

    def test_jwt_wrapper_exposes_pk_for_drf_throttling(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.user)}')
        response = client.get('/api/auth/me/')
        self.assertNotEqual(response.status_code, 500)

    def test_supply_chain_wrapper_always_fails_closed(self):
        from core.engine.advance_round import _run_sc_step
        context = Mock(game=self.game, round_number=1, log=[])
        with override_settings(SC_ENGINE_STRICT=False):
            with self.assertRaisesRegex(RuntimeError, 'engine broke'):
                _run_sc_step('test', Mock(side_effect=RuntimeError('engine broke')),
                             context)

    def test_recovery_requires_maintenance_mode(self):
        with self.assertRaisesRegex(CommandError, 'Recovery is disabled'):
            call_command('recover_competition_round', game_id=self.game.id,
                         round_number=1, actor='nobody', reason='specific reason',
                         confirm=f'RESTORE-GAME-{self.game.id}-ROUND-1', dry_run=True)

    def test_recovery_dry_run_verifies_and_writes_durable_audit(self):
        instructor = User.objects.create(
            username='recovery-instructor', role='instructor', password_hash='x')
        del instructor
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / 'round.dump'
            dump.write_bytes(b'test backup')
            digest = hashlib.sha256(dump.read_bytes()).hexdigest()
            dump.with_suffix('.dump.sha256').write_text(
                f'{digest}  {dump.name}\n', encoding='utf-8')
            ResolutionManifest.objects.create(
                game=self.game, round=self.round, seed='s' * 64,
                input_manifest={}, input_sha256='i' * 64,
                backup_path=str(dump), code_revision='rev-under-test')
            with override_settings(COMPETITION_RECOVERY_ENABLED=True,
                                   COMPETITION_BACKUP_DIR=directory,
                                   GIT_REVISION='rev-under-test'):
                call_command(
                    'recover_competition_round', game_id=self.game.id,
                    round_number=1, actor='recovery-instructor',
                    reason='Correct a verified scoring defect',
                    confirm=f'RESTORE-GAME-{self.game.id}-ROUND-1', dry_run=True)
            records = [json.loads(line) for line in
                       (Path(directory) / 'recovery-audit.jsonl').read_text().splitlines()]
            self.assertEqual(records[-1]['action'], 'restore_round_intent')
            self.assertEqual(records[-1]['backup_sha256'], digest)
            self.assertTrue(records[-1]['dry_run'])
            self.assertEqual(records[-1]['manifest_code_revision'], 'rev-under-test')

    def test_recovery_refuses_code_revision_mismatch(self):
        User.objects.create(
            username='rev-instructor', role='instructor', password_hash='x')
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / 'round.dump'
            dump.write_bytes(b'test backup')
            digest = hashlib.sha256(dump.read_bytes()).hexdigest()
            dump.with_suffix('.dump.sha256').write_text(
                f'{digest}  {dump.name}\n', encoding='utf-8')
            ResolutionManifest.objects.create(
                game=self.game, round=self.round, seed='s' * 64,
                input_manifest={}, input_sha256='i' * 64,
                backup_path=str(dump), code_revision='old-build')
            with override_settings(COMPETITION_RECOVERY_ENABLED=True,
                                   COMPETITION_BACKUP_DIR=directory,
                                   GIT_REVISION='new-build'):
                with self.assertRaisesRegex(CommandError, 'does not.*match'):
                    call_command(
                        'recover_competition_round', game_id=self.game.id,
                        round_number=1, actor='rev-instructor',
                        reason='Correct a verified scoring defect',
                        confirm=f'RESTORE-GAME-{self.game.id}-ROUND-1', dry_run=True)
                # Explicit override lets it proceed (validation only, dry-run).
                call_command(
                    'recover_competition_round', game_id=self.game.id,
                    round_number=1, actor='rev-instructor',
                    reason='Correct a verified scoring defect',
                    confirm=f'RESTORE-GAME-{self.game.id}-ROUND-1', dry_run=True,
                    allow_code_revision_mismatch=True)

    def test_restore_stderr_classifier_separates_benign_from_real(self):
        from core.services.competition_backup import _restore_stderr_is_benign
        benign = (
            'pg_restore: error: could not execute query: ERROR:  unrecognized '
            'configuration parameter "transaction_timeout"\n'
            'Command was: SET transaction_timeout = 0;\n'
            'pg_restore: warning: errors ignored on restore: 1')
        self.assertTrue(_restore_stderr_is_benign(benign))
        self.assertTrue(_restore_stderr_is_benign(''))
        real = (benign + '\npg_restore: error: could not execute query: '
                'ERROR:  relation "team" already exists')
        self.assertFalse(_restore_stderr_is_benign(real))
