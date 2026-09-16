"""Does the revision this process advertises match the code it is running?

`GIT_REVISION` is set by hand in the deployment environment, because production
is meant to be an immutable build. This deployment is a git checkout, so the two
can drift apart silently: edit the tree, restart, and every round resolved from
then on is stamped with a commit that is not the code that produced it. Nobody
notices until a dispute asks for the round to be replayed, which is the worst
possible moment to find out.

Found drifted on 2026-09-16: production advertised a revision absent from the
repository entirely (a pre-V2-048-rewrite hash), while running today's code.

Exit 0 when they agree, 1 when they do not. Run it wherever a stale value would
matter — the audit-anchor timer runs it every fifteen minutes.
"""
import pathlib
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand


def _git(*args):
    root = pathlib.Path(settings.BASE_DIR).resolve().parent
    try:
        result = subprocess.run(
            ['git', '-C', str(root), *args],
            capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


class Command(BaseCommand):
    help = 'Verify GIT_REVISION matches the checked-out code.'

    def add_arguments(self, parser):
        parser.add_argument('--quiet', action='store_true',
                            help='Say nothing when it agrees.')

    def handle(self, *args, **options):
        advertised = str(getattr(settings, 'GIT_REVISION', '') or '').strip()
        head = _git('rev-parse', 'HEAD')
        dirty = bool(_git('status', '--porcelain', '--untracked-files=no'))

        if not advertised:
            self.stderr.write(self.style.ERROR(
                'GIT_REVISION is unset. In production, resolution refuses to '
                'run without it; everywhere else the revision is guessed from '
                'the working tree.'))
            raise SystemExit(1)

        if not head:
            # Not a checkout: an immutable build is the case GIT_REVISION was
            # designed for, and there is nothing to compare against.
            if not options['quiet']:
                self.stdout.write(f'Release {advertised[:12]}: no git checkout '
                                  'to compare against (immutable build).')
            return

        if advertised != head:
            self.stderr.write(self.style.ERROR(
                f'Release identity has drifted: this process advertises '
                f'{advertised[:12]}, the code on disk is {head[:12]}. Every '
                f'round resolved now is stamped with the wrong commit. Update '
                f'GIT_REVISION in the deployment environment and restart.'))
            raise SystemExit(1)

        if dirty:
            self.stderr.write(self.style.ERROR(
                f'Release {advertised[:12]} matches HEAD, but the working tree '
                f'has uncommitted changes: the commit hash alone does not '
                f'describe the running code.'))
            raise SystemExit(1)

        if not options['quiet']:
            self.stdout.write(self.style.SUCCESS(
                f'Release identity verified: {advertised[:12]}, clean tree.'))
