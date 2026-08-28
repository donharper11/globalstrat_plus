"""Identify the source that produced a resolution, precisely enough to redo it.

A commit hash with a `-dirty` suffix names the commit and says only that
*something* else was present. Two different uncommitted patches on the same
HEAD produce the same string, so a manifest carrying one cannot prove which
canonicaliser, section registry, ordering or migration computed its hashes.

This module adds a second, content-derived identifier: a SHA-256 over every
runtime source file under ``backend/`` — path and bytes, sorted by path. It
does not care whether a file is tracked, staged, modified or untracked, so it
survives a dirty tree, a shallow clone, an export with no ``.git`` at all, and
a rebuild from a tarball. Two trees with the same digest run the same code.

``replay_round`` compares the recorded digest with the running one *before* it
touches anything, so a replay against different source fails loudly rather
than producing a hash difference nobody can explain.
"""
import hashlib
import os
import pathlib

from django.conf import settings


# Directories that are not runtime source: caches, build output, operator data
# whose contents change on every resolution, and vendored assets.
EXCLUDED_DIRECTORY_NAMES = frozenset({
    '__pycache__', '.git', '.pytest_cache', '.mypy_cache', 'node_modules',
    'competition_backups', 'staticfiles', 'media', '.venv', 'venv',
})

# Suffixes that change how a round resolves.
SOURCE_SUFFIXES = ('.py', '.json', '.yaml', '.yml', '.cfg', '.toml', '.ini')

# Files matching a source suffix that are nonetheless data, not source.
EXCLUDED_FILE_NAMES = frozenset({'db.sqlite3'})

_cache = {}


def source_root():
    """The tree whose contents decide how a round resolves."""
    return pathlib.Path(settings.BASE_DIR).resolve()


def iter_source_files(root=None):
    """Every runtime source file, as (posix relative path, absolute path)."""
    root = pathlib.Path(root) if root else source_root()
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in place so os.walk does not descend into excluded trees.
        dirnames[:] = sorted(name for name in dirnames
                             if name not in EXCLUDED_DIRECTORY_NAMES)
        for filename in sorted(filenames):
            if filename in EXCLUDED_FILE_NAMES:
                continue
            if not filename.endswith(SOURCE_SUFFIXES):
                continue
            absolute = pathlib.Path(dirpath) / filename
            yield absolute.relative_to(root).as_posix(), absolute


def source_tree_digest(root=None, refresh=False):
    """Content digest of the runtime source tree.

    The digest is over ``<path>\\n<sha256 of bytes>\\n`` per file, sorted by
    path, so it depends on file contents and names only — never on mtimes,
    inode order, or whether the checkout came from git.
    """
    root = str(pathlib.Path(root).resolve()) if root else str(source_root())
    if not refresh and root in _cache:
        return _cache[root]
    digest = hashlib.sha256()
    count = 0
    for relative, absolute in sorted(iter_source_files(root)):
        try:
            body = absolute.read_bytes()
        except OSError:
            # A file that cannot be read cannot be part of a reproducible
            # build; record its absence rather than silently skipping it.
            body = b'<unreadable>'
        digest.update(relative.encode('utf-8'))
        digest.update(b'\n')
        digest.update(hashlib.sha256(body).hexdigest().encode('ascii'))
        digest.update(b'\n')
        count += 1
    result = {'root': root, 'sha256': digest.hexdigest(), 'file_count': count}
    _cache[root] = result
    return result


def build_identity(refresh=False):
    """Everything needed to name — and re-obtain — the running build."""
    from core.services.resolution_manifest import resolve_code_revision
    revision = resolve_code_revision()
    tree = source_tree_digest(refresh=refresh)
    return {
        'code_revision': revision,
        'code_revision_is_dirty': revision.endswith('-dirty'),
        'source_tree_sha256': tree['sha256'],
        'source_file_count': tree['file_count'],
        'source_root': tree['root'],
    }


def require_identified_build(identity=None):
    """Refuse to resolve from a build nobody could obtain again.

    Enforced whenever ``COMPETITION_REQUIRE_CLEAN_BUILD`` is on — the default
    in production. The source digest is recorded either way; this is about
    whether a round may be *scored* from an unnamed working tree.
    """
    identity = identity or build_identity()
    if not getattr(settings, 'COMPETITION_REQUIRE_CLEAN_BUILD',
                   getattr(settings, 'IS_PRODUCTION', False)):
        return identity
    if identity['code_revision_is_dirty']:
        raise RuntimeError(
            f"Refusing to resolve from an uncommitted working tree "
            f"({identity['code_revision']}). The commit hash alone cannot "
            f"identify the modifications, so the round could not be "
            f"reconstructed. Commit the change set, or set "
            f"COMPETITION_REQUIRE_CLEAN_BUILD=false for a non-competition "
            f"environment. Source tree digest: "
            f"{identity['source_tree_sha256']}.")
    return identity
