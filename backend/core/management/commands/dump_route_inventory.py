"""Regenerate the checked-in registered-route inventory.

`test_operator_concurrency.RouteCoverageTests` compares the live URL conf
against `core/services/route_inventory.json`. Adding, removing or re-guarding a
mutating route changes the live inventory and fails that test, which is what
makes a new bypass a review event rather than a silent gap. Running this
command is the deliberate act of accepting the new shape.
"""
import json
import pathlib

from django.core.management.base import BaseCommand

from core.services.route_inventory import INVENTORY_PATH, build_inventory


class Command(BaseCommand):
    help = 'Rewrite core/services/route_inventory.json from the live URL conf.'

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
                    f'{path} is out of date; run dump_route_inventory.'))
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS('Route inventory is current.'))
            return
        path.write_text(rendered, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Wrote {path}: {inventory["total_mutating_routes"]} mutating routes, '
            f'{inventory["lifecycle_mutating_routes"]} lifecycle-mutating, '
            f'{inventory["guarded"]} guarded, {inventory["exempt"]} exempt, '
            f'{inventory["unguarded"]} unguarded.'))
