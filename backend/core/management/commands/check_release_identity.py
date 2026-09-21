"""Does the revision this process advertises match the code it is running?

`GIT_REVISION` is set by hand in the deployment environment, because production
is meant to be an immutable build. This deployment is a git checkout, so the two
can drift apart silently: edit the tree, restart, and every round resolved from
then on is stamped with a commit that is not the code that produced it. Nobody
notices until a dispute asks for the round to be replayed, which is the worst
possible moment to find out.

Found drifted on 2026-09-16: production advertised a revision absent from the
repository entirely (a pre-V2-048-rewrite hash), while running today's code.
Found drifted again on 2026-09-21, having been reported by this command every
fifteen minutes for days with nothing acting on it (A-03). Detection was never
the missing part; enforcement was. The comparison now lives in
`core.services.build_identity.release_identity` and resolution itself calls
it, so this command reports exactly what a round would be refused for.

Exit 0 when they agree, 1 when they do not. Run it after every deploy, and on a
timer whose failure is *visible*: a unit line prefixed with `-` records the
failure and alerts nobody.

A fresh `manage.py` process has, by construction, just loaded the code on disk,
so this cannot see a long-running worker that started before the tree changed.
Resolution checks that for itself (`build_identity.loaded_source_drift`).
"""
from django.core.management.base import BaseCommand

from core.services.build_identity import release_identity


class Command(BaseCommand):
    help = 'Verify GIT_REVISION matches the checked-out code.'

    def add_arguments(self, parser):
        parser.add_argument('--quiet', action='store_true',
                            help='Say nothing when it agrees.')

    def handle(self, *args, **options):
        report = release_identity()
        if not report['ok']:
            self.stderr.write(self.style.ERROR(
                f"[{report['status']}] {report['message']}"))
            raise SystemExit(1)
        if not options['quiet']:
            self.stdout.write(self.style.SUCCESS(report['message']))
