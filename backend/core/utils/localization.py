def get_localized_field(obj, field_name, language):
    """Return the localized version of a field, falling back to English."""
    if language == 'zh-CN':
        zh_value = getattr(obj, f'{field_name}_zh', '')
        if zh_value:
            return zh_value
    return getattr(obj, field_name, '')


def _lang_from_header(request):
    """Check Accept-Language header for a supported language."""
    accept = request.headers.get('Accept-Language', '') if request else ''
    if accept in ('zh-CN', 'zh'):
        return 'zh-CN'
    return None


# Resolved language, memoised per request object. Named like
# `auth_context._CACHE_ATTR` because it is the same idea: a per-request fact
# that several guards and views each ask for independently.
_LANGUAGE_CACHE_ATTR = '_core_user_language'


def get_user_language(request):
    """Extract language preference: Accept-Language header first, then enrollment.

    Memoised on the request (V2-069.4). Without the cache the enrollment
    lookup ran once per caller, and a client that sends no `Accept-Language`
    header paid a database query in every permission check as well as in the
    view body — `views/decisions.py` alone asks twenty-four times.
    The resolved value cannot change within one request, so caching it changes
    no answer, only how often the answer is computed.
    """
    cached = getattr(request, _LANGUAGE_CACHE_ATTR, None)
    if cached is not None:
        return cached

    header_lang = _lang_from_header(request)
    if header_lang:
        language = header_lang
    else:
        from core.models.course import Enrollment
        try:
            enrollment = Enrollment.objects.filter(
                user_id=request.user.id, is_active=True
            ).first()
            language = enrollment.language if enrollment and enrollment.language else 'en'
        except:  # noqa: E722 - preserved from the pre-CRV2-12 behaviour
            language = 'en'

    try:
        setattr(request, _LANGUAGE_CACHE_ATTR, language)
    except (AttributeError, TypeError):
        # A request-like object that refuses attributes (or `None`) still gets
        # the right answer; it simply does not get the saving.
        pass
    return language


def get_team_language(team):
    """Get the language preference for a team (from first enrolled student)."""
    from core.models.course import Enrollment
    from django.db import transaction
    try:
        # Savepoint so a query failure (e.g. missing enrollment table in a test
        # DB) is contained and cannot poison the caller's transaction.
        with transaction.atomic():
            enrollment = Enrollment.objects.filter(
                team_id=team.team_id if hasattr(team, 'team_id') else team.id,
                is_active=True
            ).exclude(language='').first()
            return enrollment.language if enrollment and enrollment.language else 'en'
    except Exception:
        return 'en'


def get_instructor_language(game):
    """Get the language preference for the instructor who created/owns the game.

    Looks up the game creator's enrollment record (instructors are enrolled
    with is_active=True). Falls back to 'en' if not found.
    """
    from core.models.course import Enrollment
    from django.db import transaction
    try:
        # Savepoint so a query failure (e.g. missing enrollment table in a test
        # DB) is contained and cannot poison the caller's transaction.
        with transaction.atomic():
            instructor_user_id = game.created_by_id
            enrollment = Enrollment.objects.filter(
                user_id=instructor_user_id,
                is_active=True,
            ).exclude(language='').first()
            return enrollment.language if enrollment and enrollment.language else 'en'
    except Exception:
        return 'en'
