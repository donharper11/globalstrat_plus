"""Append any unsealed audit rows to the forward hash chain.

Sealing normally happens on its own, after each audit write commits. This
command is the catch-up: rows written while the process was killed, rows
inserted by raw SQL or a data migration, and the periodic sweep that picks up
read events between audit writes.
"""
import json

from django.core.management.base import BaseCommand

from core.services.audit_chain import head, seal_pending, verify_chain


class Command(BaseCommand):
    help = 'Seal unsealed audit records into the tamper-evidence chain.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None,
                            help='Seal at most this many entries.')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        added = seal_pending(limit=options['limit'])
        current = head()
        report = {
            'sealed': added,
            'head_seq': current.seq if current else 0,
            'head_sha256': current.entry_sha256 if current else '',
            'unsealed_remaining': verify_chain()['unsealed_total'],
        }
        if options['json']:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Sealed {added} entries; head #{report['head_seq']} "
            f"{report['head_sha256'][:16]}…, "
            f"{report['unsealed_remaining']} still unsealed."))
