"""Guarded full-database recovery followed by deterministic round reprocessing."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.models import Game, OperatorAuditEvent, ResolutionManifest, Round, User
from core.services.competition_backup import (
    append_recovery_audit, restore_database, verify_backup,
)


class Command(BaseCommand):
    help = 'Restore a pre-resolution backup and optionally re-run that round.'

    def add_arguments(self, parser):
        parser.add_argument('--game-id', type=int, required=True)
        parser.add_argument('--round', type=int, required=True, dest='round_number')
        parser.add_argument('--actor', required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--confirm', required=True)
        parser.add_argument('--restore-only', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if not getattr(settings, 'COMPETITION_RECOVERY_ENABLED', False):
            raise CommandError(
                'Recovery is disabled. Enter maintenance mode and set '
                'COMPETITION_RECOVERY_ENABLED=true.')
        game_id, round_number = options['game_id'], options['round_number']
        token = f'RESTORE-GAME-{game_id}-ROUND-{round_number}'
        if options['confirm'] != token:
            raise CommandError(f'Confirmation mismatch; expected {token}.')
        reason = options['reason'].strip()
        if len(reason) < 10:
            raise CommandError(
                'A specific recovery reason of at least 10 characters is required.')
        actor = User.objects.filter(
            username=options['actor'], role__in=['instructor', 'admin']).first()
        if not actor:
            raise CommandError('Actor must name an instructor or admin account.')
        manifest = ResolutionManifest.objects.select_related('game', 'round').filter(
            game_id=game_id, round__round_number=round_number).first()
        if not manifest:
            raise CommandError('No resolution manifest exists for that game and round.')
        verified = verify_backup(manifest.backup_path)
        intent = {
            'action': 'restore_round_intent', 'actor': actor.username,
            'reason': reason, 'game_id': game_id, 'round_number': round_number,
            'backup_path': verified['path'], 'backup_sha256': verified['sha256'],
            'input_sha256': manifest.input_sha256, 'dry_run': options['dry_run'],
        }
        audit_path = append_recovery_audit(intent)
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Validated recovery plan; durable audit: {audit_path}'))
            return

        restore_database(verified['path'])
        connection.connect()
        game = Game.objects.get(pk=game_id)
        round_obj = Round.objects.get(game=game, round_number=round_number)
        actor = User.objects.get(username=options['actor'])
        OperatorAuditEvent.objects.create(
            game=game, round=round_obj, user=actor, action='restore_round', reason=reason,
            before={'backup_path': verified['path'],
                    'backup_sha256': verified['sha256']},
            after={'database_restored': True}, request_id='management-command')
        append_recovery_audit({**intent, 'action': 'restore_round_complete'})

        if not options['restore_only']:
            from core.engine.advance_round import process_round
            result = process_round(game_id)
            round_obj.refresh_from_db()
            OperatorAuditEvent.objects.create(
                game=game, round=round_obj, user=actor, action='rerun_round',
                reason=reason, before={'input_sha256': manifest.input_sha256},
                after=result, request_id='management-command')
            append_recovery_audit(
                {**intent, 'action': 'rerun_round_complete', 'result': result})
        self.stdout.write(self.style.SUCCESS('Competition recovery completed.'))
