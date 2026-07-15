"""
Give accounts that have no password a default one, so they can log in now that
a password is required.

Default = the student's student_id, falling back to their username.

    python3 manage.py set_default_passwords --dry-run
    python3 manage.py set_default_passwords
    python3 manage.py set_default_passwords --all      # also reset existing
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import User
from core.utils.passwords import default_password_for, hash_password


class Command(BaseCommand):
    help = 'Set default passwords (= student_id) for accounts without one.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change without writing.')
        parser.add_argument('--all', action='store_true',
                            help='Also reset accounts that already have a '
                                 'password. Destructive — will lock out anyone '
                                 'using a password they chose.')
        parser.add_argument('--include-instructors', action='store_true',
                            help='Include instructor/admin accounts. Off by '
                                 'default so a real instructor password is '
                                 'never clobbered.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        qs = User.objects.all()
        if not options['include_instructors']:
            qs = qs.exclude(role__iexact='instructor').exclude(role__iexact='admin')
        if not options['all']:
            qs = qs.filter(Q(password_hash='') | Q(password_hash__isnull=True))

        total = qs.count()
        if not total:
            self.stdout.write('Nothing to do — every account already has a password.')
            return

        self.stdout.write(
            f'{"[dry-run] " if dry_run else ""}Setting default passwords for '
            f'{total} account(s).'
        )

        updated = skipped = 0
        for user in qs.order_by('username'):
            pw = default_password_for(user)
            if not pw:
                self.stdout.write(self.style.WARNING(
                    f'  SKIP {user.username!r} (id={user.user_id}) — '
                    f'no student_id or username to derive a password from.'
                ))
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  would set {user.username!r} -> {pw!r}')
            else:
                user.password_hash = hash_password(pw)
                user.save(update_fields=['password_hash'])
            updated += 1

        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {updated} account(s). {skipped} skipped.'
        ))
        if not dry_run and updated:
            self.stdout.write(
                'Each student logs in with their student ID as both username '
                'and password. Tell them to expect that.'
            )
