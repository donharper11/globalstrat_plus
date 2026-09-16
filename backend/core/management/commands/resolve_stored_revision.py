"""Translate a stored `code_revision` into a commit that still exists.

Why this is needed. The V2-048 history rewrite (2026-09-04) rewrote every commit
in this repository to purge a credential, which changed every commit hash. Rounds
resolved before that date stored the *pre-rewrite* hash in
`competition_resolution_manifest.code_revision`, and those hashes now resolve to
nothing: `git cat-file` reports them absent, and `recover_competition_round`
refuses a manifest whose revision differs from the running build (RD-03). Read
literally, every round stored before the rewrite looked unreconstructable.

They are not. filter-repo wrote a commit map, old hash to new, and it is
committed beside this code at the path below — deliberately, because the copy
filter-repo leaves in `.git/filter-repo/` is not in the repository, is not
backed up, and does not survive a fresh clone. Losing it is what would make
those rounds genuinely unrecoverable.

    manage.py resolve_stored_revision <sha>        # one revision
    manage.py resolve_stored_revision --all-stored # every revision in the table
"""
import pathlib
import subprocess

from django.core.management.base import BaseCommand, CommandError

MAP_PATH = ('handoff_readiness_v2/evidence/v2-048/commit-map-2026-09-04.txt')


def _repo_root():
    from django.conf import settings
    return pathlib.Path(settings.BASE_DIR).resolve().parent


def _load_map():
    path = _repo_root() / MAP_PATH
    if not path.exists():
        raise CommandError(
            f'The V2-048 commit map is missing at {path}. Without it a '
            'pre-rewrite code_revision cannot be translated, and rounds '
            'resolved before 2026-09-04 cannot be tied to a commit.')
    mapping = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 40 and len(parts[1]) == 40:
            mapping[parts[0]] = parts[1]
    return mapping


def _exists(revision):
    if not revision:
        return False
    try:
        return subprocess.run(
            ['git', '-C', str(_repo_root()), 'cat-file', '-t', revision],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() == 'commit'
    except (OSError, subprocess.SubprocessError):
        return False


def resolve(stored):
    """Return (status, revision). Status is one of present/translated/unknown."""
    stored = (stored or '').strip()
    base = stored[:-len('-dirty')] if stored.endswith('-dirty') else stored
    if _exists(base):
        return 'present', base
    translated = _load_map().get(base)
    if translated and _exists(translated):
        return 'translated', translated
    return 'unknown', base


class Command(BaseCommand):
    help = 'Translate a stored code_revision into a commit that still exists.'

    def add_arguments(self, parser):
        parser.add_argument('revision', nargs='?')
        parser.add_argument('--all-stored', action='store_true',
                            help='Report every distinct revision in the manifest table.')

    def handle(self, *args, **options):
        if options['all_stored']:
            from core.models import ResolutionManifest
            stored = (ResolutionManifest.objects
                      .values_list('code_revision', flat=True).distinct())
            rows = sorted({(s or '').strip() for s in stored})
            unknown = 0
            for value in rows:
                if not value:
                    self.stdout.write(self.style.WARNING(
                        '(empty)            no revision was recorded at all'))
                    unknown += 1
                    continue
                status, revision = resolve(value)
                line = f'{value[:12]}  {status:<11} {revision[:12]}'
                if status == 'unknown':
                    unknown += 1
                    self.stdout.write(self.style.ERROR(line))
                elif status == 'translated':
                    self.stdout.write(self.style.WARNING(line))
                else:
                    self.stdout.write(self.style.SUCCESS(line))
            if unknown:
                raise CommandError(
                    f'{unknown} stored revision(s) cannot be tied to a commit. '
                    'A round stored against one of these cannot be replayed '
                    'against the code that produced it.')
            self.stdout.write(self.style.SUCCESS(
                'Every stored revision resolves to a commit in this repository.'))
            return

        if not options['revision']:
            raise CommandError('Give a revision, or --all-stored.')
        status, revision = resolve(options['revision'])
        if status == 'unknown':
            raise CommandError(
                f'{options["revision"]} is not a commit here and is not in the '
                'V2-048 commit map.')
        self.stdout.write(self.style.SUCCESS(f'{status}: {revision}'))
