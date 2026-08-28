"""Resolution manifests: what a round was given, and what it produced.

Schema version 2 (GSP-CRV2-01). Version 1 recorded decision-event ids, six
audit metadata fields, the active team ids and a scenario id on the input
side, and financials / performance / leaderboard rows on the output side. That
was not enough to reconstruct or defend a round: it could not show the
decision payloads that were accepted, the scenario constants the maths used,
the market and event state the round started from, or the team state carried
into the next round.

Version 2 replaces both envelopes with canonical snapshots taken through
``core.services.manifest_sections`` — a reviewed, complete inventory of the
tables that carry competitive state — serialised through
``core.services.canonical_json`` so the bytes do not move with the machine.

Reading old manifests
---------------------
Version-1 rows stay readable and keep their stored hashes. They are never
re-interpreted as version 2: ``require_schema_version`` refuses, so a v1 hash
can never be compared against a v2 hash and called a match. Anything that
needs the expanded envelope has to say so and gets a clear error on old rows.
"""
import hashlib
import json
import locale
import os
import pathlib
import platform
import re
import subprocess
import sys
import time

import django
from django.conf import settings
from django.db import connection
from django.utils import timezone

from core.models import DecisionAuditEvent, ResolutionManifest
from core.services.canonical_json import (
    canonical_dumps, canonical_sha256, canonicalize)
from core.services.manifest_sections import (
    CONFIG_SECTION_NAMES, INPUT_SECTIONS, NARRATIVE_SECTIONS, OUTPUT_SECTIONS,
)
from core.services.manifest_snapshot import build_snapshot


MANIFEST_SCHEMA_VERSION = 2
MANIFEST_KIND = 'globalstrat.resolution-manifest'

_UNRESOLVED_REVISIONS = {'', 'unknown', 'unset', 'none', 'null', 'dev', 'development'}


class ManifestSchemaError(RuntimeError):
    """A manifest is not the schema version the caller requires."""


class ManifestVerificationError(RuntimeError):
    """A rebuilt manifest does not match the recorded one."""

    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report or {}


# ---------------------------------------------------------------------------
# Build provenance
# ---------------------------------------------------------------------------

def resolve_code_revision():
    """Return an auditable build revision or fail before resolution starts."""
    configured = str(getattr(settings, 'GIT_REVISION', '') or
                     os.environ.get('GIT_REVISION', '')).strip()
    if configured:
        if (configured.lower() in _UNRESOLVED_REVISIONS or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+:/@-]{0,63}', configured)):
            raise RuntimeError('GIT_REVISION is not a valid release identifier.')
        return configured

    if getattr(settings, 'IS_PRODUCTION', False):
        raise RuntimeError(
            'Production resolution requires an explicit GIT_REVISION for the '
            'deployed immutable build.')

    repository = pathlib.Path(settings.BASE_DIR).resolve().parent
    try:
        revision = subprocess.run(
            ['git', '-C', str(repository), 'rev-parse', 'HEAD'], check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', '-C', str(repository), 'status', '--porcelain',
             '--untracked-files=no'], check=True, capture_output=True, text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            'Cannot determine the code revision. Set GIT_REVISION to the '
            'deployed commit or immutable build identifier.') from exc
    if not revision or len(revision) > 58:
        raise RuntimeError('Git returned an invalid code revision.')
    return f'{revision}-dirty' if dirty else revision


def migration_state():
    """Applied migrations, ordered, with a digest.

    This is schema state, not machine state: it is read from the database
    being resolved, so a replay of a restored snapshot sees exactly the same
    list. That is why the digest is safe to put inside the input hash while
    the code revision — a property of the *host*, not of the input — is not.
    """
    from django.db import DatabaseError, transaction
    from django.db.migrations.recorder import MigrationRecorder
    recorder = MigrationRecorder(connection)
    applied, present = [], False
    # A savepoint, because a failed statement would otherwise poison the
    # resolution transaction this runs inside. The table is genuinely absent
    # under the project's test runner, which builds the schema from the models
    # instead of replaying migrations.
    try:
        with transaction.atomic():
            present = recorder.has_table()
            if present:
                applied = list(recorder.migration_qs.order_by('app', 'name')
                               .values_list('app', 'name'))
    except DatabaseError:
        applied, present = [], False
    rows = [f'{app}.{name}' for app, name in applied]
    return {'table_present': present, 'count': len(rows),
            'sha256': canonical_sha256(rows), 'applied': rows}


def _os_release():
    try:
        for line in pathlib.Path('/etc/os-release').read_text().splitlines():
            if line.startswith('PRETTY_NAME='):
                return line.split('=', 1)[1].strip().strip('"')
    except OSError:
        pass
    return ''


def _system_timezone():
    """The host's timezone, read before Django's normalisation can hide it."""
    try:
        return pathlib.Path('/etc/timezone').read_text().strip()
    except OSError:
        pass
    try:
        return os.readlink('/etc/localtime').split('zoneinfo/')[-1]
    except OSError:
        return ''


def environment_fingerprint():
    """Everything about the host that a cross-environment replay must vary.

    Deliberately outside every hash. It is recorded so an operator can prove
    two matching runs really did happen on differently configured machines.
    """
    try:
        db_version = connection.cursor().connection.server_version
    except Exception:
        db_version = None
    from core.services.build_identity import build_identity
    identity = build_identity()
    return {
        'code_revision': identity['code_revision'],
        'source_tree_sha256': identity['source_tree_sha256'],
        'source_file_count': identity['source_file_count'],
        'python': sys.version.split()[0],
        'python_build': ' '.join(platform.python_build()),
        'django': django.get_version(),
        'platform': platform.platform(),
        'os_release': _os_release(),
        'libc': ' '.join(platform.libc_ver()),
        'machine': platform.machine(),
        'node': platform.node(),
        # Django assigns os.environ['TZ'] from settings.TIME_ZONE and calls
        # tzset(), so the *process* timezone is normalised no matter what the
        # host is set to. The host's own setting is recorded separately, which
        # is what makes a cross-environment replay meaningful.
        'system_timezone': _system_timezone(),
        'tz_env': os.environ.get('TZ', ''),
        'time_tzname': list(time.tzname),
        'django_time_zone': str(getattr(settings, 'TIME_ZONE', '')),
        'current_timezone': str(timezone.get_current_timezone()),
        'lc_all': os.environ.get('LC_ALL', ''),
        'lang': os.environ.get('LANG', ''),
        'locale': [part or '' for part in locale.getlocale()],
        'preferred_encoding': locale.getpreferredencoding(False),
        'filesystem_encoding': sys.getfilesystemencoding(),
        'hash_seed': os.environ.get('PYTHONHASHSEED', ''),
        'database': connection.settings_dict.get('NAME', ''),
        'database_server_version': db_version,
    }


# ---------------------------------------------------------------------------
# Durable content-addressed manifest bodies
# ---------------------------------------------------------------------------

def manifest_store_root():
    from core.services.competition_backup import backup_root
    return backup_root() / 'manifests'


def store_manifest_body(body, label):
    """Write a canonical manifest body to a content-addressed file.

    The database row keeps the same bytes, so the manifest is self-contained;
    this copy is what survives losing the database. The digest in the filename
    is computed over the same canonical bytes as ``canonical_sha256``, so a
    stored body's name *is* the ``input_sha256`` / ``output_sha256`` it belongs
    to and the two can be matched without opening the file.
    """
    if str(connection.settings_dict.get('NAME', '')).startswith('test_'):
        # Django's disposable test databases; a durable copy adds no recovery
        # value and would litter the operator's backup directory.
        return 'test-database://transactional'
    raw = canonical_dumps(body).encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    root = manifest_store_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        target = root / f'{label}-{digest}.json'
        if not target.exists():
            tmp = target.with_suffix('.json.partial')
            with tmp.open('wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            tmp.replace(target)
        return str(target)
    except OSError:
        # The database copy is authoritative; an unavailable store must not
        # stop a competition round from resolving.
        return ''


# ---------------------------------------------------------------------------
# Envelope construction
# ---------------------------------------------------------------------------

def rng_seed_inputs(game, round_obj):
    """The values the engine's seeded RNG is actually derived from.

    ``core.engine.rng.get_rng`` keys every stream on
    ``(game.section_id or game.id, round_number, operation_id)`` and most
    operation ids embed a row's primary key. Those are surrogate values, so
    they are recorded here explicitly rather than hidden: replay is exact for
    a restored database, and a rebuilt-from-scratch database would draw a
    different stream. See handoff_readiness_v2/DETERMINISM_BOUNDARY.md.
    """
    return {
        'rng_class_id': game.section_id or game.id,
        'rng_class_id_source': 'game.section_id' if game.section_id else 'game.id',
        'round_number': round_obj.round_number,
        'game_id': game.id,
        'game_section_id': game.section_id,
        'scenario_id': game.scenario_id,
        'sc_seed_expression': 'sha256(f"{game_id}-{round_number}-{scenario_id}") % 2**32',
    }


def derive_seed(seed_inputs):
    return hashlib.sha256(canonical_dumps(seed_inputs).encode('utf-8')).hexdigest()


def build_input_manifest(game, round_obj):
    """The complete, canonical description of what this round was given."""
    snapshot = build_snapshot(INPUT_SECTIONS, 'input', game.scenario_id, game.id)
    if snapshot.unmapped_references:
        raise ManifestVerificationError(
            'Manifest sections reference rows with no natural key: '
            f'{snapshot.unmapped_references[:5]}. Add the model to '
            'manifest_sections.EXTERNAL_KEYS or snapshot it as a section.')
    seed_inputs = rng_seed_inputs(game, round_obj)
    body = {
        'kind': MANIFEST_KIND,
        'envelope': 'input',
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'game': f'game({json.dumps(game.name)})',
        'round_number': round_obj.round_number,
        'seed_inputs': seed_inputs,
        'seed': derive_seed(seed_inputs),
        'migrations': migration_state(),
        'sections': snapshot.rows,
        'section_digests': snapshot.section_digests(),
        'field_inventory_sha256': canonical_sha256(snapshot.field_inventory()),
    }
    # Canonicalise once, here: the manifest is stored in a JSONField and read
    # back by tools that must see exactly the bytes that were hashed.
    return canonicalize(body), snapshot


def build_output_manifest(round_obj):
    """The competitive result plus a separately hashed narrative envelope."""
    from core.services.manifest_snapshot import identity_closure
    game = round_obj.game
    # A competitive row points at configuration it does not itself contain —
    # a team's starter profile, a game's scenario, a market. Without those in
    # the snapshot their foreign keys would fall back to surrogate ids and the
    # competitive hash would move with unrelated sequence activity. Pull in
    # what identity requires; keep only the competitive sections in the body.
    competitive_names = {section.name for section in OUTPUT_SECTIONS}
    competitive = build_snapshot(
        identity_closure(OUTPUT_SECTIONS, INPUT_SECTIONS), 'output',
        game.scenario_id, game.id)
    config = build_snapshot(
        tuple(s for s in INPUT_SECTIONS if s.name in CONFIG_SECTION_NAMES),
        'input', game.scenario_id, game.id)
    # Narrative sections reference the game, team and market. Without those in
    # the same snapshot their foreign keys cannot be tokenised and would fall
    # back to surrogate ids, so pull in whatever identity requires and keep
    # only the narrative sections in the body.
    from core.services.manifest_snapshot import identity_closure
    narrative_names = {section.name for section in NARRATIVE_SECTIONS}
    narrative = build_snapshot(
        identity_closure(NARRATIVE_SECTIONS, INPUT_SECTIONS + NARRATIVE_SECTIONS),
        'output', game.scenario_id, game.id)
    for snapshot in (competitive, config, narrative):
        if snapshot.unmapped_references:
            raise ManifestVerificationError(
                'Manifest sections reference rows with no natural key: '
                f'{snapshot.unmapped_references[:5]}.')

    body = {
        'kind': MANIFEST_KIND,
        'envelope': 'output',
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'game': f'game({json.dumps(game.name)})',
        'round_number': round_obj.round_number,
        'sections': {name: rows for name, rows in competitive.rows.items()
                     if name in competitive_names},
        'section_digests': {name: digest for name, digest
                            in competitive.section_digests().items()
                            if name in competitive_names},
        # Proves resolution did not rewrite its own configuration: these must
        # equal the digests the input manifest recorded for the same sections.
        'config_digests': config.section_digests(),
        'field_inventory_sha256': canonical_sha256(competitive.field_inventory()),
    }
    # `rows` carries a narrative section's non-prose columns; the prose itself
    # is separated out by the snapshot and lives in `narrative_rows`. Both
    # belong in the narrative envelope — hashing only the former would make
    # "the narrative differed" untestable, because the text would not be in it.
    narrative_body = {
        'kind': MANIFEST_KIND,
        'envelope': 'narrative',
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'round_number': round_obj.round_number,
        'sections': {name: rows for name, rows in narrative.rows.items()
                     if name in narrative_names},
        'prose': {name: rows for name, rows in narrative.narrative_rows.items()
                  if name in narrative_names},
        # Narrative fields on rows that are otherwise competitive: event and
        # government-action text, agent-cycle template prose.
        'inline_narrative': {name: rows for name, rows
                             in competitive.narrative_rows.items()
                             if name in competitive_names},
        'section_digests': {name: digest for name, digest
                            in narrative.section_digests().items()
                            if name in narrative_names},
        'prose_digests': {name: digest for name, digest
                          in narrative.narrative_digests().items()
                          if name in narrative_names},
    }
    return canonicalize(body), canonicalize(narrative_body)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def prepare_manifest(game, round_obj, backup_path):
    """Record the exact input state, before a single value is mutated."""
    from core.services.build_identity import require_identified_build
    # Fails closed before anything is written: a round scored from an
    # unidentifiable build could not be reconstructed afterwards.
    identity = require_identified_build()
    body, _snapshot = build_input_manifest(game, round_obj)
    input_sha256 = canonical_sha256(body)
    audit_events = DecisionAuditEvent.objects.filter(
        game=game, round=round_obj).count()
    return ResolutionManifest.objects.update_or_create(
        round=round_obj,
        defaults={
            'game': game,
            'schema_version': MANIFEST_SCHEMA_VERSION,
            'seed': body['seed'],
            'input_manifest': body,
            'input_sha256': input_sha256,
            'input_section_digests': body['section_digests'],
            'input_body_path': store_manifest_body(
                body, f'game-{game.id}-round-{round_obj.round_number}-input'),
            'environment': environment_fingerprint(),
            'backup_path': backup_path,
            'code_revision': identity['code_revision'],
            'source_tree_sha256': identity['source_tree_sha256'],
            'output_manifest': {},
            'output_sha256': '',
            'narrative_sha256': '',
            'output_section_digests': {},
            'decision_event_count': audit_events,
        },
    )[0]


def complete_manifest(round_obj):
    """Record everything the round published and carried forward."""
    body, narrative_body = build_output_manifest(round_obj)
    manifest = ResolutionManifest.objects.get(round=round_obj)
    manifest.schema_version = MANIFEST_SCHEMA_VERSION
    manifest.output_manifest = body
    manifest.output_sha256 = canonical_sha256(body)
    manifest.narrative_manifest = narrative_body
    manifest.narrative_sha256 = canonical_sha256(narrative_body)
    manifest.output_section_digests = body['section_digests']
    manifest.output_body_path = store_manifest_body(
        body, f'game-{manifest.game_id}-round-{round_obj.round_number}-output')
    manifest.completed_at = timezone.now()
    manifest.save(update_fields=[
        'schema_version', 'output_manifest', 'output_sha256',
        'narrative_manifest', 'narrative_sha256', 'output_section_digests',
        'output_body_path', 'completed_at'])
    # The manifest is only tamper-evident once it is final: the row is written
    # twice by design, and chaining the pre-resolution write would commit to a
    # state that is supposed to change.
    from core.services.audit_chain import schedule_seal
    schedule_seal()
    return manifest


# ---------------------------------------------------------------------------
# Reading and verifying
# ---------------------------------------------------------------------------

def envelope_schema_version(body):
    """The schema version of a stored envelope.

    Canonical serialisation renders every number as a string, so a stored
    envelope carries ``"2"`` rather than ``2``. Read it through this helper
    instead of comparing the raw value.
    """
    try:
        return int(body.get('schema_version'))
    except (AttributeError, TypeError, ValueError):
        return None


def require_schema_version(manifest, version=MANIFEST_SCHEMA_VERSION):
    """Refuse to read an old manifest as if it were the new envelope."""
    stored = getattr(manifest, 'schema_version', 1) or 1
    if stored != version:
        raise ManifestSchemaError(
            f'Resolution manifest for round '
            f'{getattr(manifest.round, "round_number", "?")} is schema version '
            f'{stored}; this operation requires version {version}. A version-1 '
            f'manifest covers a narrower envelope and its hashes are not '
            f'comparable with version-{version} hashes.')
    return manifest


def diff_sections(expected, actual, max_rows=8):
    """Per-section differences between two manifest ``sections`` mappings."""
    report = {}
    for name in sorted(set(expected) | set(actual)):
        left = {row['_key']: row for row in expected.get(name, [])}
        right = {row['_key']: row for row in actual.get(name, [])}
        if canonical_dumps(expected.get(name, [])) == canonical_dumps(
                actual.get(name, [])):
            continue
        missing = sorted(set(left) - set(right))
        added = sorted(set(right) - set(left))
        changed = []
        for key in sorted(set(left) & set(right)):
            fields = {
                column: {'expected': left[key][column], 'actual': right[key][column]}
                for column in sorted(set(left[key]) | set(right[key]))
                if left[key].get(column) != right[key].get(column)
            }
            if fields:
                changed.append({'row': key, 'fields': fields})
        report[name] = {
            'missing_rows': missing[:max_rows], 'missing_count': len(missing),
            'added_rows': added[:max_rows], 'added_count': len(added),
            'changed_rows': changed[:max_rows], 'changed_count': len(changed),
        }
    return report


def verify_input_state(manifest, expected_body=None):
    """Rebuild the input manifest from the live database and compare.

    Called before any mutation. ``expected_body`` lets a caller verify against
    a manifest exported before a restore, when the database that held the
    original row has since been overwritten.
    """
    require_schema_version(manifest)
    expected = expected_body if expected_body is not None else manifest.input_manifest
    if envelope_schema_version(expected) != MANIFEST_SCHEMA_VERSION:
        raise ManifestSchemaError(
            'The recorded input body is not a version-'
            f'{MANIFEST_SCHEMA_VERSION} envelope.')
    game = manifest.game
    round_obj = manifest.round
    actual, _snapshot = build_input_manifest(game, round_obj)

    expected_sha = canonical_sha256(expected)
    actual_sha = canonical_sha256(actual)
    section_diffs = {}
    scalar_diffs = {}
    if expected_sha != actual_sha:
        section_diffs = diff_sections(expected.get('sections', {}),
                                      actual.get('sections', {}))
        for field_name in ('seed', 'seed_inputs', 'migrations', 'round_number',
                           'game', 'field_inventory_sha256'):
            if expected.get(field_name) != actual.get(field_name):
                scalar_diffs[field_name] = {'expected': expected.get(field_name),
                                            'actual': actual.get(field_name)}
    return {
        'matches': expected_sha == actual_sha,
        'expected_sha256': expected_sha,
        'actual_sha256': actual_sha,
        'recorded_sha256': manifest.input_sha256,
        'section_diffs': section_diffs,
        'scalar_diffs': scalar_diffs,
    }
