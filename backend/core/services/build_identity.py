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

It also owns the question "does the advertised revision name the code that is
running?" (``release_identity``). One implementation serves both the
resolution-time guard and ``manage.py check_release_identity``, so the check an
operator runs is exactly the check resolution enforces.
"""
import hashlib
import os
import pathlib
import re
import subprocess
import time

from django.conf import settings


# Directories that are not runtime source: caches, build output, operator data
# whose contents change on every resolution, and vendored assets.
EXCLUDED_DIRECTORY_NAMES = frozenset({
    '__pycache__', '.git', '.pytest_cache', '.mypy_cache', 'node_modules',
    'competition_backups', 'staticfiles', 'media', '.venv', 'venv',
})

# Suffixes that change how a round resolves.
SOURCE_SUFFIXES = ('.py', '.json', '.yaml', '.yml', '.cfg', '.toml', '.ini')

# Files that decide what runs without carrying a source suffix (A-04). The
# dependency pins are the obvious one: two trees identical in every `.py` file
# but pinned to different framework versions do not describe the same build.
SOURCE_FILE_NAMES = frozenset({'requirements.txt'})

# Files matching a source suffix that are nonetheless data, not source.
EXCLUDED_FILE_NAMES = frozenset({'db.sqlite3'})

# A full commit hash: SHA-1 today, SHA-256 for a repository that has moved.
# An abbreviation is not accepted: it is ambiguous by construction, and the
# recovery check (RD-03) compares stored revisions as whole strings.
COMMIT_ID = re.compile(r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')

_cache = {}
# The digest of the default root as it stood when this process started, and
# when that was. Python reads a module's bytes once, so a process keeps running
# the code it started with however the disk changes afterwards. The digest that
# names a round's code therefore has to be taken at start -- not at the first
# resolution, which may be days later and after someone has edited the tree.
_startup = {}


def source_root():
    """The tree whose contents decide how a round resolves."""
    return pathlib.Path(settings.BASE_DIR).resolve()


def _operator_data_directories():
    """Configured directories the running system writes into.

    `competition_backups` is excluded by name, which covers the default. An
    operator who points `COMPETITION_BACKUP_DIR` at another directory inside
    this tree would otherwise have every resolution write manifest `.json`
    bodies into the digested tree, and the start-of-process drift check would
    then refuse the NEXT resolution for a change that is data, not code.
    """
    configured = getattr(settings, 'COMPETITION_BACKUP_DIR', None)
    return {pathlib.Path(configured).resolve()} if configured else set()


def iter_source_files(root=None):
    """Every runtime source file, as (posix relative path, absolute path)."""
    root = pathlib.Path(root) if root else source_root()
    operator_data = _operator_data_directories()
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in place so os.walk does not descend into excluded trees.
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in EXCLUDED_DIRECTORY_NAMES
            and (pathlib.Path(dirpath) / name).resolve() not in operator_data)
        for filename in sorted(filenames):
            if filename in EXCLUDED_FILE_NAMES:
                continue
            if (not filename.endswith(SOURCE_SUFFIXES)
                    and filename not in SOURCE_FILE_NAMES):
                continue
            absolute = pathlib.Path(dirpath) / filename
            yield absolute.relative_to(root).as_posix(), absolute


def source_tree_digest(root=None, refresh=False):
    """Content digest of the runtime source tree.

    The digest is over ``<path>\\n<sha256 of bytes>\\n`` per file, sorted by
    path, so it depends on file contents and names only — never on mtimes,
    inode order, or whether the checkout came from git.

    Cached per root. For the default root the cache is filled at process start
    (``prime_source_tree_digest``), so what this returns describes the code the
    process loaded rather than whatever is on disk when somebody first asks.
    """
    root = str(pathlib.Path(root).resolve()) if root else str(source_root())
    if not refresh and root in _cache:
        return _cache[root]
    result = _digest_tree(root)
    _cache[root] = result
    return result


def _digest_tree(root):
    """Hash the tree at ``root`` as it is on disk now. Never cached."""
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
    return {'root': root, 'sha256': digest.hexdigest(), 'file_count': count}


def prime_source_tree_digest():
    """Take the source digest now, at process start. Called from AppConfig.

    Idempotent: the first call in a process wins, so a later call cannot move
    the recorded digest onto a tree the process never loaded. Costs one walk of
    ``backend/`` (about 20 ms for ~430 files) and must never stop a process
    from starting, so every failure is swallowed; the digest is then taken at
    first use, which is what happened before this existed.
    """
    try:
        root = str(source_root())
        if root not in _startup:
            _startup[root] = {**source_tree_digest(), 'taken_at': time.time(),
                              'pid': os.getpid()}
        return _startup[root]
    except Exception:
        return None


def loaded_source_drift():
    """How the tree on disk differs from the one this process started with.

    ``None`` when they agree. The git comparison in ``release_identity``
    describes the *disk*; this is what ties the disk to the *process*. Without
    it, a tree edited and committed after the workers started verifies clean
    against HEAD while the old code keeps resolving rounds.
    """
    started = source_tree_digest()
    now = _digest_tree(started['root'])
    if now['sha256'] == started['sha256']:
        return None
    return {'loaded_sha256': started['sha256'], 'disk_sha256': now['sha256'],
            'loaded_file_count': started['file_count'],
            'disk_file_count': now['file_count']}


# ---------------------------------------------------------------------------
# Release identity: does the advertised revision name the code on disk?
# ---------------------------------------------------------------------------

def repository_root():
    """The directory a deployment checkout would be rooted at."""
    return pathlib.Path(settings.BASE_DIR).resolve().parent


def _find_git_marker(start):
    """The nearest ``.git`` at or above ``start`` (a directory, or a worktree's
    pointer file), or ``None``.

    Found by looking, not by asking git, so that a checkout whose git cannot
    answer is told apart from an immutable build.
    """
    start = pathlib.Path(start)
    for directory in (start, *start.parents):
        if (directory / '.git').exists():
            return directory / '.git'
    return None


def _git(root, *args):
    """(ok, stdout). ``ok`` is False when git could not run or refused."""
    try:
        result = subprocess.run(
            ['git', '-C', str(root), *args],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False, ''
    return result.returncode == 0, result.stdout.strip()


def checkout_state(root=None):
    """What git says about the tree the code is running from.

    ``is_checkout`` is decided by the presence of ``.git``, never by whether
    git answered: reading "git failed" as "immutable build" would let a missing
    binary or an unreadable repository switch the comparison off.
    """
    root = pathlib.Path(root) if root else repository_root()
    if _find_git_marker(root) is None:
        return {'is_checkout': False, 'readable': False, 'head': '',
                'dirty': False, 'dirty_paths': []}
    ok_head, head = _git(root, 'rev-parse', 'HEAD')
    ok_status, status = _git(root, 'status', '--porcelain',
                             '--untracked-files=no')
    paths = [line[3:] for line in status.splitlines() if line.strip()]
    return {'is_checkout': True,
            'readable': bool(ok_head and ok_status and head),
            'head': head, 'dirty': bool(paths), 'dirty_paths': paths}


# Statuses ``release_identity`` reports. Only the first two are acceptable.
VERIFIED, IMMUTABLE = 'verified', 'immutable'
UNSET, INVALID, DIRTY, DRIFTED, UNVERIFIABLE = (
    'unset', 'invalid', 'dirty', 'drifted', 'unverifiable')

OPERATOR_PROCEDURE = (
    'To fix: (1) in the deployment checkout run `git status` and '
    '`git rev-parse HEAD`; commit or discard every tracked change so the tree '
    'is clean at the release commit. (2) Set GIT_REVISION in the deployment '
    'environment file to that full 40-character hash. (3) Restart the backend '
    'AND the narrative worker so every process loads that code and that value. '
    '(4) Run `python3 manage.py check_release_identity` and confirm it exits 0 '
    'before resolving a round.')


def release_identity(advertised=None, root=None):
    """Compare the advertised revision with the code on disk.

    Returns ``{'status', 'ok', 'advertised', 'head', 'message'}``. ``message``
    is written for the operator who has to act on it.
    """
    if advertised is None:
        advertised = getattr(settings, 'GIT_REVISION', '')
    advertised = str(advertised or '').strip()
    report = {'advertised': advertised, 'head': ''}

    def done(status, message, ok=False):
        return {**report, 'status': status, 'ok': ok, 'message': message}

    if not advertised:
        return done(UNSET, 'GIT_REVISION is unset, so nothing names the code '
                           'that is running. ' + OPERATOR_PROCEDURE)
    if advertised.endswith('-dirty'):
        return done(DIRTY, f'The build identifies itself as {advertised}: an '
                           f'uncommitted working tree. The commit hash alone '
                           f'cannot identify the modifications. '
                           + OPERATOR_PROCEDURE)
    if not COMMIT_ID.fullmatch(advertised):
        return done(INVALID, f'The advertised revision {advertised!r} is not a '
                             f'full commit hash (40 or 64 lowercase hex '
                             f'characters). A label, a tag or an abbreviation '
                             f'cannot be checked against the code, and '
                             f'recovery compares revisions as whole strings. '
                             + OPERATOR_PROCEDURE)

    state = checkout_state(root)
    report['head'] = state['head']
    if not state['is_checkout']:
        # An immutable build: GIT_REVISION is the only statement of identity
        # there is, which is the case it was designed for. The source digest
        # still pins the bytes.
        return done(IMMUTABLE, f'Release {advertised[:12]}: no git checkout to '
                               f'compare against (immutable build).', ok=True)
    if not state['readable']:
        return done(UNVERIFIABLE,
                    f'The code is running from a git checkout, but git could '
                    f'not report HEAD and the tree status, so the advertised '
                    f'revision {advertised[:12]} cannot be verified. Check '
                    f'that git is installed and that the service user can read '
                    f'the repository (run `git status` in the checkout as '
                    f'that user; see git\'s safe.directory). '
                    + OPERATOR_PROCEDURE)
    if advertised != state['head']:
        return done(DRIFTED,
                    f'Release identity has drifted: this process advertises '
                    f'{advertised[:12]}, the code on disk is '
                    f'{state["head"][:12]}. Every round resolved now would be '
                    f'stamped with the wrong commit. ' + OPERATOR_PROCEDURE)
    if state['dirty']:
        shown = ', '.join(state['dirty_paths'][:5])
        return done(DIRTY,
                    f'Release {advertised[:12]} matches HEAD, but the working '
                    f'tree has uncommitted changes to tracked files ({shown}): '
                    f'the commit hash alone does not describe the running '
                    f'code. ' + OPERATOR_PROCEDURE)
    return done(VERIFIED, f'Release identity verified: {advertised[:12]}, '
                          f'clean tree.', ok=True)


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
    whether a round may be *scored* from an unnamed working tree. With the flag
    off nothing here runs and git is never consulted.

    "Identified" means three things. Until A-03 only the first was tested, and
    a hand-set ``GIT_REVISION`` never carries the suffix it looks for:

    1. the revision does not admit to being dirty;
    2. the revision is a full commit hash and, when the code is running from a
       git checkout, it *is* HEAD and no tracked file differs from it. (Not a
       checkout -- an immutable build -- means there is nothing to compare, and
       the advertised value stands, as before.)
    3. the tree on disk is still the tree this process started from, so what
       git says about the disk is also true of the loaded code.
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
    report = release_identity(identity['code_revision'])
    if not report['ok']:
        raise RuntimeError(
            f"Refusing to resolve: the release identity is "
            f"{report['status']}. {report['message']} "
            f"(COMPETITION_REQUIRE_CLEAN_BUILD=false switches this check off, "
            f"and is for non-competition environments only.) Source tree "
            f"digest: {identity['source_tree_sha256']}.")
    drift = loaded_source_drift()
    if drift:
        raise RuntimeError(
            f"Refusing to resolve: the code on disk has changed since this "
            f"process started (loaded {drift['loaded_sha256'][:12]}, "
            f"{drift['loaded_file_count']} files; on disk "
            f"{drift['disk_sha256'][:12]}, {drift['disk_file_count']} files). "
            f"This process is still running the old code, so neither the "
            f"revision nor the digest would describe what scored the round. "
            f"To fix: restart the backend AND the narrative worker, then run "
            f"`python3 manage.py check_release_identity` and confirm it exits "
            f"0 before resolving.")
    return identity
