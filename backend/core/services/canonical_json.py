"""Environment-independent canonical JSON for competition hashing.

GSP-CRV2-01 requirement 4: the bytes we hash must not change because the
machine changed. Four representation hazards are neutralised here:

* **Decimal representation.** ``Decimal('1234.5600')``, ``Decimal('1234.56')``
  and ``Decimal('1.23456E+3')`` are the same number but three different
  strings. A driver, a column's ``decimal_places``, or a ``quantize()`` in a
  code path can produce any of them. Every ``Decimal`` is emitted as its
  exponent-free, trailing-zero-free plain-string form.
* **Locale.** Number and date formatting must never consult ``LC_NUMERIC`` or
  ``LC_TIME``. Nothing here uses ``str.format`` locale specifiers, ``%``
  date formatting or ``locale``-aware conversion, and ``json.dumps`` is called
  with ``ensure_ascii=True`` so the output is pure ASCII regardless of the
  filesystem or terminal encoding.
* **Timezone.** ``TZ`` on the host changes what Python renders for an aware
  datetime and what a naive datetime means. Aware datetimes are converted to
  UTC and rendered with a fixed microsecond precision; naive datetimes are
  read as UTC (the project runs ``USE_TZ=True``, so a naive value can only
  come from a non-DB source) and tagged so the difference is visible.
* **Dictionary / mapping iteration order.** Mapping keys are coerced to
  strings and sorted by Unicode code point, which is the same order on every
  platform and under every collation.

Float values are rendered through ``repr``, which in CPython 3 is the
shortest string that round-trips the exact IEEE-754 double, so it depends on
the bits and not on the platform. ``-0.0`` is folded to ``0.0`` and
non-finite values are tagged rather than emitted as the non-standard JSON
literals ``NaN`` / ``Infinity``.

Numbers are emitted as *strings*, never as JSON numbers. That is deliberate:
a JSON number would re-introduce the encoder's own float formatting into the
hashed bytes. A column's type is fixed by the schema, so a numeric field can
never legitimately hold the string form of a different value.
"""
import datetime
import decimal
import hashlib
import json
import uuid


NONFINITE_PREFIX = '!nonfinite:'
NAIVE_DATETIME_SUFFIX = '!naive'


def normalize_decimal(value):
    """Render a Decimal in a form that no longer carries its exponent.

    ``Decimal('1234.5600')`` -> ``'1234.56'``; ``Decimal('1.2E+3')`` ->
    ``'1200'``; ``Decimal('-0.000')`` -> ``'0'``.
    """
    if not value.is_finite():
        return f'{NONFINITE_PREFIX}{value}'
    normalized = value.normalize()
    if normalized == 0:
        # normalize() maps every zero to 0E+n; collapse the whole family.
        return '0'
    _sign, _digits, exponent = normalized.as_tuple()
    if exponent > 0:
        # 1.2E+3 -> 1200, so the plain form never contains an exponent.
        normalized = normalized.quantize(decimal.Decimal(1))
    return format(normalized, 'f')


def normalize_float(value):
    """Render a float from its bits, not from the platform's formatter."""
    if value != value or value in (float('inf'), float('-inf')):
        return f'{NONFINITE_PREFIX}{value}'
    if value == 0.0:
        return '0.0'  # folds -0.0
    return repr(value)


def normalize_datetime(value):
    """Render a datetime as UTC ISO-8601 with fixed microsecond precision."""
    if value.tzinfo is None:
        return (value.isoformat(timespec='microseconds') +
                NAIVE_DATETIME_SUFFIX)
    utc = value.astimezone(datetime.timezone.utc)
    return utc.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def canonicalize(value):
    """Convert an arbitrary value into JSON-safe, environment-free data."""
    if value is None or isinstance(value, bool) or isinstance(value, str):
        return value
    if isinstance(value, int):
        # Python ints are exact and their decimal form is locale-free.
        return str(value)
    if isinstance(value, float):
        return normalize_float(value)
    if isinstance(value, decimal.Decimal):
        return normalize_decimal(value)
    if isinstance(value, datetime.datetime):
        return normalize_datetime(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, datetime.time):
        return value.isoformat(timespec='microseconds')
    if isinstance(value, datetime.timedelta):
        # total_seconds() is a float; go through Decimal so the text is exact.
        return normalize_decimal(
            decimal.Decimal(value.days) * 86400 +
            decimal.Decimal(value.seconds) +
            decimal.Decimal(value.microseconds).scaleb(-6))
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, dict):
        # Sorting by the code-point order of the string key is collation- and
        # locale-independent, unlike sorting mixed key types.
        return {key: canonicalize(item)
                for key, item in sorted(
                    ((_canonical_key(k), v) for k, v in value.items()),
                    key=lambda pair: pair[0])}
    if isinstance(value, (set, frozenset)):
        # A set has no order of its own; impose one on the rendered members.
        return sorted((canonical_dumps(item) for item in value))
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    raise TypeError(
        f'{type(value).__name__} has no canonical representation; add one to '
        f'core.services.canonical_json rather than falling back to str().')


def _canonical_key(key):
    if isinstance(key, str):
        return key
    rendered = canonicalize(key)
    if isinstance(rendered, str):
        return rendered
    return canonical_dumps(rendered)


def canonical_dumps(value):
    """Serialise to the exact bytes-as-text that get hashed."""
    return json.dumps(canonicalize(value), sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False)


def canonical_sha256(value):
    """SHA-256 of the canonical serialisation."""
    return hashlib.sha256(canonical_dumps(value).encode('utf-8')).hexdigest()
