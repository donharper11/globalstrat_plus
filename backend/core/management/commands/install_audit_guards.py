"""Install, check or describe the database-level append-only guards.

Needed as a command and not only as a migration because the guards must also
be present on a database that was restored from a dump, rebuilt by the test
runner, or migrated by someone who then dropped a trigger to make a correction.
`--check` is the form worth scheduling.
"""
import json

from django.core.management.base import BaseCommand
from django.db import connection

from core.services.audit_guards import (
    install, installed_triggers, missing_guards, privilege_report,
    provision_app_role_sql,
)


class Command(BaseCommand):
    help = 'Install or verify the append-only triggers on the audit tables.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true',
                            help='Exit non-zero if a guard is missing or disabled.')
        parser.add_argument('--privileges', action='store_true',
                            help='Report who may UPDATE/DELETE each audit table.')
        parser.add_argument('--role-sql', default=None, metavar='ROLE',
                            help='Print the SQL that provisions a least-privilege '
                                 'application role, and exit.')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        if options['role_sql']:
            for statement in provision_app_role_sql(options['role_sql']):
                self.stdout.write(statement)
            return

        if options['privileges']:
            rows = [r for r in privilege_report(connection)
                    if r['update'] or r['delete']]
            if options['json']:
                self.stdout.write(json.dumps(rows, indent=2, sort_keys=True))
                return
            self.stdout.write('Roles that hold UPDATE or DELETE on an audit table:')
            for row in rows:
                owner = ' (owner)' if row['is_owner'] else ''
                self.stdout.write(
                    f"  {row['table']:<40} {row['role']}{owner} "
                    f"update={row['update']} delete={row['delete']}")
            self.stdout.write(
                'Triggers refuse these statements regardless of privilege; an '
                'owner can drop a trigger, which the chain anchor then exposes.')
            return

        if options['check']:
            missing = missing_guards(connection)
            if options['json']:
                self.stdout.write(json.dumps(
                    {'installed': installed_triggers(connection),
                     'missing': missing, 'ok': not missing},
                    indent=2, sort_keys=True))
            if missing:
                for row in missing:
                    self.stderr.write(self.style.ERROR(
                        f"{row['table']}: {row['problem']}"))
                raise SystemExit(1)
            if not options['json']:
                self.stdout.write(self.style.SUCCESS(
                    'All append-only audit guards are installed and enabled.'))
            return

        install(connection)
        rows = installed_triggers(connection)
        self.stdout.write(self.style.SUCCESS(
            f'Installed {len(rows)} append-only guards: '
            + ', '.join(r['table'] for r in rows)))
