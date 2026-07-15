"""
Central password hashing/verification for the custom core.models.User model.

History: passwords were stored as unsalted SHA-256 hex digests, and student
accounts were allowed to log in with no password at all. Both are fixed here.

New passwords are hashed with Django's default hasher (PBKDF2). Legacy SHA-256
digests still verify, and are transparently re-hashed to PBKDF2 the next time
the account logs in successfully, so no existing account is locked out.
"""
import hashlib
import re

from django.contrib.auth.hashers import check_password, make_password

# A legacy hash is exactly 64 lowercase hex chars (SHA-256 hex digest).
# Django hashes always look like "<algorithm>$<iterations>$<salt>$<hash>".
_LEGACY_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')

MIN_PASSWORD_LENGTH = 6


def is_legacy_hash(stored_hash):
    """True if stored_hash is an old unsalted SHA-256 hex digest."""
    return bool(stored_hash) and bool(_LEGACY_SHA256_RE.match(stored_hash))


def hash_password(plain):
    """Hash a plain-text password with Django's default hasher (PBKDF2)."""
    return make_password(plain)


def verify_password(plain, stored_hash):
    """
    Check a plain-text password against a stored hash.

    Returns (is_valid, needs_upgrade). needs_upgrade is True when the password
    was correct but is still stored as a legacy SHA-256 digest, so the caller
    should re-hash it. A blank stored_hash never verifies — an account with no
    password set cannot be logged into.
    """
    if not plain or not stored_hash:
        return False, False

    if is_legacy_hash(stored_hash):
        # compare_digest to avoid leaking timing information.
        import hmac
        legacy = hashlib.sha256(plain.encode()).hexdigest()
        if hmac.compare_digest(legacy, stored_hash):
            return True, True
        return False, False

    try:
        return check_password(plain, stored_hash), False
    except Exception:
        return False, False


def upgrade_hash_if_needed(user, plain):
    """
    Re-hash a legacy password to PBKDF2 after a successful login.
    Best-effort: never raises, since a failure here must not block login.
    """
    try:
        if is_legacy_hash(user.password_hash):
            user.password_hash = hash_password(plain)
            user.save(update_fields=['password_hash'])
    except Exception:
        pass


def default_password_for(user):
    """
    The default password issued to a student account.

    Policy (set 2026-07-15): the student's own student_id, falling back to the
    username when no student_id is recorded. Every real student in this
    deployment has username == student_id, so both agree in practice.
    """
    student_id = (getattr(user, 'student_id', '') or '').strip()
    if student_id:
        return student_id
    return (user.username or '').strip()


def validate_password(plain):
    """
    Return an error string if the password is unacceptable, else None.
    Deliberately permissive: this is a classroom sim, and the default
    passwords are student IDs, which must remain valid.
    """
    if not plain or not plain.strip():
        return 'Password cannot be blank.'
    if len(plain) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    return None
