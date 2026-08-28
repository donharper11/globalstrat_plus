"""Write the current audit-chain head outside the database.

Run after each round resolves and before any privileged maintenance. The
anchor is what a later verification is compared against, so an anchor taken
after a tampering event proves nothing — the schedule matters as much as the
command.
"""
import json

from django.core.management.base import BaseCommand

from core.services.audit_anchor import export_anchor
from core.services.audit_chain import seal_pending


class Command(BaseCommand):
    help = 'Seal pending audit rows and export the chain head to the backup volume.'

    def add_arguments(self, parser):
        parser.add_argument('--no-seal', action='store_true',
                            help='Anchor the head as-is without sealing first.')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        sealed = 0 if options['no_seal'] else seal_pending()
        record = export_anchor()
        record['sealed_before_export'] = sealed
        if options['json']:
            self.stdout.write(json.dumps(record, indent=2, sort_keys=True,
                                         default=str))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Anchored head #{record['head_seq']} "
            f"({record['head_entry_sha256'][:16]}…) to {record['path']}"))
