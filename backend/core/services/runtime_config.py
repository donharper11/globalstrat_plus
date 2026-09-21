"""The effective, NON-SECRET runtime configuration, and a digest of it (A-04).

The source digest says which code ran. It does not say how that code was
configured: ``settings`` reads the process environment and a gitignored
``backend/.env``, neither of which is source, so two processes on identical
bytes can route a narrative to different models, run under different
timezones, or differ on whether the clean-build guard is on at all. This module
records that, beside the source digest, on every resolution manifest.

**What may appear here is an explicit allow-list.** Nothing is discovered by
iterating ``settings`` or ``os.environ``: a value is recorded only because a
person put its name in ``RECORDED_SETTINGS`` or wrote a derived entry below,
having judged it not to be a credential. ``LLM_GATEWAY_KEY``, ``SECRET_KEY``,
``JWT_SECRET_KEY`` and the database password are deliberately absent, and the
gateway URL is reduced to scheme, host, port and path, because a URL can carry
a password or an ``?api_key=`` that the variable's name would not warn of.
``test_runtime_provenance`` fails if a secret-shaped name joins the list or a
secret's value reaches the record.

**Where it is stored.** ``ResolutionManifest.environment`` -- host description,
outside ``input_sha256``, ``output_sha256`` and ``narrative_sha256`` by design
(see DETERMINISM_BOUNDARY.md), so this moves no hashed envelope and
``MANIFEST_SCHEMA_VERSION`` is unchanged. The competitive hash has been shown
not to depend on the model at all; this is a record for explaining a narrative
difference or a configuration dispute, not an input to a hash.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

from django.conf import settings

# Plain settings recorded as they stand. Each one changes competitive,
# narrative or provenance behaviour, and none is a credential.
RECORDED_SETTINGS = (
    'ENVIRONMENT',
    'IS_PRODUCTION',
    'DEBUG',
    'TIME_ZONE',
    'USE_TZ',
    'LANGUAGE_CODE',
    'COMPETITION_REQUIRE_CLEAN_BUILD',
    'COMPETITION_RAG_AFFECTS_COHERENCE',
    'COMPETITION_RECOVERY_ENABLED',
    'SC_ENGINE_STRICT',
    'QDRANT_HOST',
    'QDRANT_PORT',
    'QDRANT_COLLECTION',
    'EMBEDDING_MODEL',
    'EMBEDDING_DIMENSION',
    'TEXTBOOK_COLLECTION',
    'TEXTBOOK_EMBEDDING_MODEL',
)

# A name matching this never belongs in RECORDED_SETTINGS.
SECRET_SHAPED = re.compile(
    r'KEY|SECRET|PASSWORD|PASSWD|TOKEN|CREDENTIAL|DSN|COOKIE|SIGNING', re.I)


def _plain(value):
    """JSON-safe, deterministic rendering of a settings value."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    return str(value)


def sanitised_endpoint(url):
    """Scheme, host, port and path only -- never userinfo, query or fragment."""
    url = str(url or '').strip()
    if not url:
        return ''
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        port = f':{parts.port}' if parts.port else ''
    except ValueError:
        return '<unparseable>'
    if not host:
        return '<unparseable>'
    return f'{parts.scheme}://{host}{port}{parts.path}'


def llm_routing():
    """The model each purpose is *effectively* sent to, overrides applied."""
    from core.engine.llm_runner import MODEL_BY_PURPOSE, model_for_purpose
    overrides = getattr(settings, 'LLM_PURPOSE_MODELS', None) or {}
    routing = {purpose: model_for_purpose(purpose)
               for purpose in sorted(MODEL_BY_PURPOSE)}
    # An override naming a purpose the code does not know routes nothing, but
    # it is still a statement about this deployment, so it is kept visible.
    unknown = {str(purpose): str(model) for purpose, model
               in sorted(overrides.items(), key=lambda item: str(item[0]))
               if purpose not in MODEL_BY_PURPOSE}
    return routing, unknown


def runtime_configuration():
    """The allow-listed effective configuration, as a plain dict."""
    from core.engine import llm_runner
    record = {name: _plain(getattr(settings, name, None))
              for name in RECORDED_SETTINGS}
    routing, unknown = llm_routing()
    record['llm_purpose_routing'] = routing
    record['llm_purpose_overrides_unknown'] = unknown
    record['llm_gateway_endpoint'] = sanitised_endpoint(
        getattr(settings, 'LLM_GATEWAY_URL', ''))
    # Whether a model is reachable at all changes every narrative. Recorded as
    # a boolean: that a credential exists is not the credential.
    record['llm_gateway_configured'] = bool(llm_runner.llm_configured())
    record['llm_max_concurrent'] = llm_runner.MAX_CONCURRENT
    record['llm_timeout_per_call'] = llm_runner.TIMEOUT_PER_CALL
    record['throttle_rates'] = _plain(
        (getattr(settings, 'REST_FRAMEWORK', None) or {})
        .get('DEFAULT_THROTTLE_RATES', {}))
    return record


def runtime_configuration_digest(record=None):
    record = runtime_configuration() if record is None else record
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True)
    return hashlib.sha256(raw.encode('ascii')).hexdigest()


_installed = {}


def installed_packages_digest():
    """Digest of the distributions this interpreter can import.

    ``requirements.txt`` is inside the source digest, but it is a statement of
    intent: the service may run a distribution package (gunicorn does) or a
    newer wheel than the pin. This is what is actually installed. Cached,
    because it cannot change under a running process in any way that matters
    more than the modules already imported.
    """
    if _installed:
        return _installed
    from importlib import metadata
    rows = set()
    for distribution in metadata.distributions():
        name = (distribution.metadata.get('Name') or '').strip().lower()
        if name:
            rows.add(f'{name}=={distribution.version}')
    ordered = sorted(rows)
    _installed.update({
        'sha256': hashlib.sha256('\n'.join(ordered).encode('utf-8')).hexdigest(),
        'count': len(ordered)})
    return _installed


def requirements_digest():
    """SHA-256 of ``backend/requirements.txt`` alone, or '' if absent.

    Already covered by the source digest; recorded separately so a dependency
    change can be told apart from a code change without the two trees in hand.
    """
    import pathlib
    path = pathlib.Path(settings.BASE_DIR) / 'requirements.txt'
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ''
