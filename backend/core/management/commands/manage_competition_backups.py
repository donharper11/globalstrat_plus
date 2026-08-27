import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.services.competition_backup import inspect_backups, prune_expired_backups


class Command(BaseCommand):
    help = 'Inspect competition backups and optionally prune verified expired dumps.'

    def add_arguments(self, parser):
        parser.add_argument('--retention-days', type=int)
        parser.add_argument('--delete-expired', action='store_true')
        parser.add_argument('--reason', default='')
        parser.add_argument('--confirm', default='')

    def handle(self, *args, **options):
        days = (getattr(settings, 'COMPETITION_BACKUP_RETENTION_DAYS', 30)
                if options['retention_days'] is None
                else options['retention_days'])
        if days < 1:
            raise CommandError('--retention-days must be at least 1.')
        if options['delete_expired']:
            try:
                deleted = prune_expired_backups(
                    retention_days=days, reason=options['reason'],
                    confirm=options['confirm'])
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {len(deleted)} verified expired backup(s).'))
            return
        records = inspect_backups(days)
        self.stdout.write(json.dumps({
            'retention_days': days, 'backup_count': len(records),
            'expired_count': sum(item['expired'] for item in records),
            'invalid_count': sum(not item['valid'] for item in records),
            'backups': records,
        }, indent=2, sort_keys=True))
