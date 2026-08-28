"""Regenerate the checked-in sensitive-read route inventory.

`test_audit_integrity.ReadInventoryTests` compares the live URL conf against
`core/services/read_inventory.json`. Registering a view that serves decision
rows or audit payloads changes the live inventory and fails that test, which
makes an unlogged disclosure route a review event rather than a silent gap.
"""
import json
import pathlib

from django.core.management.base import BaseCommand

from core.services.read_inventory import INVENTORY_PATH, build_inventory


class Command(BaseCommand):
    help = 'Rewrite core/services/read_inventory.json from the live URL conf.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true',
                            help='Exit non-zero if the file is out of date.')

    def handle(self, *args, **options):
        inventory = build_inventory()
        rendered = json.dumps(inventory, indent=2, sort_keys=True) + '\n'
        path = pathlib.Path(INVENTORY_PATH)
        current = path.read_text(encoding='utf-8') if path.exists() else ''
        if options['check']:
            if current != rendered:
                self.stderr.write(self.style.ERROR(
                    f'{path} is out of date; run dump_read_inventory.'))
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS('Read inventory is current.'))
            return
        path.write_text(rendered, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Wrote {path}: {inventory["total_sensitive_routes"]} sensitive '
            f'read routes ({inventory["audit_routes"]} audit, '
            f'{inventory["decision_routes"]} decisions), '
            f'{inventory["logged"]} logged, {inventory["exempt"]} exempt.'))
