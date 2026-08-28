"""Recompute the audit chain and compare it with the external anchor.

Exits non-zero when the history no longer verifies, so it can be a scheduled
check rather than something someone remembers to read.
"""
import json

from django.core.management.base import BaseCommand
from django.db import connection

from core.services.audit_anchor import verify_against_anchor
from core.services.audit_chain import verify_chain
from core.services.audit_guards import missing_guards


class Command(BaseCommand):
    help = 'Verify audit-record tamper evidence (chain, anchor and guards).'

    def add_arguments(self, parser):
        parser.add_argument('--anchor', default=None,
                            help='Anchor file to compare against.')
        parser.add_argument('--skip-anchor', action='store_true')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        chain = verify_chain()
        guards = missing_guards(connection)
        anchor = (None if options['skip_anchor']
                  else verify_against_anchor(options['anchor']))
        report = {
            'chain': chain,
            'anchor': anchor,
            'missing_guards': guards,
            'ok': (chain['ok'] and not guards
                   and (anchor is None or anchor['ok'])),
        }
        if options['json']:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True,
                                         default=str))
        else:
            self.stdout.write(
                f"Chain: {chain['entries']} entries, "
                f"{chain['unsealed_total']} unsealed, "
                f"{len(chain['problems'])} problems.")
            for problem in chain['problems'][:20]:
                self.stdout.write(self.style.ERROR(
                    f"  #{problem['seq']} {problem['kind']}: {problem['detail']}"))
            for guard in guards:
                self.stdout.write(self.style.ERROR(
                    f"  guard {guard['table']}: {guard['problem']}"))
            if anchor is not None:
                state = 'matches' if anchor['ok'] else 'DOES NOT MATCH'
                self.stdout.write(f"Anchor: {state} ({anchor.get('anchor')})")
                for problem in anchor.get('problems', []):
                    self.stdout.write(self.style.ERROR(f'  {problem}'))
            self.stdout.write(
                self.style.SUCCESS('Audit integrity verified.') if report['ok']
                else self.style.ERROR('AUDIT INTEGRITY FAILED.'))
        if not report['ok']:
            raise SystemExit(1)
