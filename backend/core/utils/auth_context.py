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

Works in two contexts:

  * inside a DRF view, where DRF has already run JWTAuthentication and
    populated request.user; and
  * inside Django middleware, where it has NOT. Django's AuthenticationMiddleware
    only populates request.user from the *session*, so a JWT-authenticated
    caller looks anonymous there. Middleware that trusted request.user was
    therefore dead code that silently allowed everything. When request.user is
    not authenticated we decode the bearer token ourselves, and cache it on the
    request so the work is done once.
"""

from core.models import User

_CACHE_ATTR = '_core_auth_payload'


def _jwt_payload(request):
    """
    Decode and verify the bearer token on a raw HttpRequest. Returns the JWT
    payload dict, or None. Cached per request.
    """
    cached = getattr(request, _CACHE_ATTR, False)
    if cached is not False:
        return cached

    payload = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        import jwt
        from django.conf import settings
        try:
            payload = jwt.decode(
                auth_header[7:],
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except Exception:
            payload = None  # expired/invalid — treat as anonymous

    setattr(request, _CACHE_ATTR, payload)
    return payload


def get_request_user_id(request):
    """Return the authenticated caller's user_id, or None. Avoids a DB hit."""
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        uid = getattr(user, 'user_id', None)
        if uid is not None:
            return uid

    payload = _jwt_payload(request)
    return payload.get('user_id') if payload else None


def get_request_role(request):
    """Return the authenticated caller's lowercased role, or None."""
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        role = getattr(user, 'role', None)
        if role is not None:
            return (role or '').lower()

    payload = _jwt_payload(request)
    if not payload:
        return None
    # Trust the signed role claim; it is minted by create_access_token.
    return (payload.get('role') or '').lower()


def get_request_user(request):
    """
    Return the custom core.models.User for the authenticated caller, or None.

    Only a valid, signed JWT establishes identity.
    """
    user_id = get_request_user_id(request)
    if user_id is None:
        return None
    return User.objects.filter(user_id=user_id).first()


def is_instructor(request):
    return get_request_role(request) in ('instructor', 'admin')
