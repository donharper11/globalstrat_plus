"""Regenerate the checked-in manifest field inventory.

``test_manifest_determinism`` compares the live registry against the inventory
for the current schema version -- ``core/services/manifest_schema_v<N>.json``,
where N is ``MANIFEST_SCHEMA_VERSION``. Any model that gains, loses or renames
a field changes the live inventory and fails that test, which is what makes
schema drift a review event rather than a silent hash change. Running this
command is the deliberate act of accepting the new shape.

Accepting a shape that changes what a round *hashes to* also means bumping the
version. Version 2's inventory was rewritten twice while still calling itself
version 2, which left no way to reconstruct what an earlier v2 hash was taken
over (V2-052). Superseded definitions are kept under
``core/services/manifest_schema_history/`` and pinned by digest.
"""
import pathlib

from django.core.management.base import BaseCommand

from core.services.manifest_schema import (
    SCHEMA_INVENTORY_PATH, build_schema_inventory,
)
from core.services.canonical_json import canonical_dumps


class Command(BaseCommand):
    help = ('Rewrite the current version\'s manifest field inventory '
            'from the live registry.')

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true',
                            help='Exit non-zero if the file is out of date.')

    def handle(self, *args, **options):
        inventory = build_schema_inventory()
        rendered = canonical_dumps(inventory) + '\n'
        path = pathlib.Path(SCHEMA_INVENTORY_PATH)
        current = path.read_text(encoding='utf-8') if path.exists() else ''
        if options['check']:
            if current != rendered:
                self.stderr.write(self.style.ERROR(
                    f'{path} is out of date; run dump_manifest_schema.'))
                raise SystemExit(1)
            self.stdout.write(self.style.SUCCESS('Manifest schema inventory is current.'))
            return
        path.write_text(rendered, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))
