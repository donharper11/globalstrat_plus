"""Refusals every evidence harness shares.

V2-128 (the re-audit's A-07). `settings.COMPETITION_BACKUP_DIR` defaults to
`backend/competition_backups`, which on this host is the LIVE backup root:
production runs from this checkout. A harness that resolves a round writes a
pre-resolution dump there unless told otherwise, and three fixtures did not
say otherwise. Nothing was ever found there that should not be, which is luck.

Call `require_disposable_backup_dir()` first thing in a harness's `main()`.
It refuses rather than choosing a temporary directory, because the dump has to
be found again by the replay command that follows, in another process.
"""
import os
from pathlib import Path


def live_backup_root(settings):
    return (Path(settings.BASE_DIR) / 'competition_backups').resolve()


def require_disposable_backup_dir():
    from django.conf import settings
    configured = Path(settings.COMPETITION_BACKUP_DIR).resolve()
    live = live_backup_root(settings)
    explicit = bool(os.environ.get('COMPETITION_BACKUP_DIR', '').strip())
    inside_live = configured == live or live in configured.parents
    if explicit and not inside_live:
        return configured
    raise SystemExit(
        f'REFUSED: this harness would write pre-resolution dumps into '
        f'{configured}, which is the live competition backup root on this '
        f'host (V2-128). Set COMPETITION_BACKUP_DIR to a disposable directory '
        f'outside {live} for this command AND for every resolve or replay '
        f'command that follows it, for example: '
        f'COMPETITION_BACKUP_DIR=$(mktemp -d) python3 <harness> ...')
