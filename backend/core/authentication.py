"""
Custom JWT authentication for GlobalStrat.

Works with the custom core.models.User model (not Django's auth.User).
Uses PyJWT for token creation and verification.
"""

import jwt
import datetime
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JWTUser:
    """
    Lightweight user wrapper so DRF's request.user works.
    Wraps the custom core.models.User instance.
    """

    def __init__(self, user):
        self._user = user
        self.user_id = user.user_id
        self.username = user.username
        self.role = user.role
        self.team_id = None  # Resolved from Enrollment, not User
        self.is_authenticated = True

    def __str__(self):
        return self.username


def create_access_token(user):
    """Generate a JWT access token for the given custom User."""
    now = datetime.datetime.utcnow()
    payload = {
        'user_id': user.user_id,
        'username': user.username,
        'role': user.role or 'student',
        'iat': now,
        'exp': now + datetime.timedelta(
            hours=settings.JWT_ACCESS_TOKEN_LIFETIME_HOURS
        ),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


class JWTAuthentication(BaseAuthentication):
    """
    DRF authentication class that validates Bearer JWT tokens.
    Falls back silently (returns None) so AllowAny endpoints still work.
    """

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None  # No token — let other auth classes or AllowAny handle it

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token.')

        from core.models import User
        try:
            user = User.objects.get(user_id=payload['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')

        return (JWTUser(user), token)
