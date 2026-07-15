"""
Single source of truth for "who is calling this request?".

Previously each module resolved the caller itself and every one of them
accepted an unverified `X-User-Id` header (or even a `?user_id=` query param)
as proof of identity. That let anyone become any user — including an
instructor — by sending a small integer, with no login at all:

    curl 'http://host/api/games/83/instructor/dashboard/?user_id=1'   # -> 200

Identity now comes only from a signed JWT (see core.authentication). The
`X-User-Id` header is still sent by the frontend for backward compatibility,
but it is no longer trusted for identity — it is ignored.
"""

from core.models import User


def get_request_user(request):
    """
    Return the custom core.models.User for the authenticated caller, or None.

    Only a valid, signed JWT establishes identity.
    """
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    user_id = getattr(user, 'user_id', None)
    if user_id is None:
        return None

    return User.objects.filter(user_id=user_id).first()


def get_request_user_id(request):
    """Return the authenticated caller's user_id, or None. Avoids a DB hit."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return getattr(user, 'user_id', None)


def get_request_role(request):
    """Return the authenticated caller's lowercased role, or None."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return (getattr(user, 'role', '') or '').lower()


def is_instructor(request):
    return get_request_role(request) in ('instructor', 'admin')
