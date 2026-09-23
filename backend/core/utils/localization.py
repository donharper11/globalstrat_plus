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


SUPPORTED_LANGUAGES = ('en', 'zh-CN')


def _stated_language(user_id):
    """The language this user has stated, or None.

    Two stores, because a student and an instructor state it in different
    places: the enrolment the sign-in and the in-game switch write for an
    enrolled user, and `UserLanguagePreference` for anyone -- including an
    instructor created from the console, who has no enrolment at all. The
    preference row is the explicit choice, so it is read first; the two are
    written together by `PUT /api/user/preferences/` and cannot disagree
    unless an older row predates that route.
    """
    if not user_id:
        return None
    from django.db import transaction
    from core.models.course import Enrollment
    from core.models.preferences import UserLanguagePreference
    try:
        # Savepoint so a query failure (e.g. a missing table in a test DB) is
        # contained and cannot poison the caller's transaction.
        with transaction.atomic():
            stated = (UserLanguagePreference.objects
                      .filter(user_id=user_id).exclude(language='')
                      .values_list('language', flat=True).first())
            if stated:
                return stated
            return (Enrollment.objects
                    .filter(user_id=user_id, is_active=True)
                    .exclude(language='')
                    .values_list('language', flat=True).first())
    except Exception:
        return None


def _game_owner_ids(game):
    """The user ids that could hold the owning instructor's language.

    `Game.created_by` is a Django auth user, and `GameCreateView` records the
    first superuser whenever the caller is a `JWTUser` -- which is every
    instructor signing in to the console. So the creator row does not identify
    the instructor for a console-created game (W-CE2-08). The instructor who
    owns the game in practice is the one who owns its course, reached through
    the game's section; the creator id stays as the fallback, so every game
    recorded the older way answers exactly as before.
    """
    ids = []
    try:
        from django.db import transaction
        from core.models.course import Course, Section
        if game.section_id:
            with transaction.atomic():
                course_id = (Section.objects
                             .filter(section_id=game.section_id)
                             .values_list('course_id', flat=True).first())
                if course_id:
                    owner = (Course.objects.filter(course_id=course_id)
                             .values_list('instructor_id', flat=True).first())
                    if owner:
                        ids.append(owner)
    except Exception:
        pass
    created_by = getattr(game, 'created_by_id', None)
    if created_by and created_by not in ids:
        ids.append(created_by)
    return ids


def get_instructor_language(game):
    """Get the language preference for the instructor who owns the game.

    Read at generation time: the AI Coach alerts and the Phase-2 instructor
    narratives are stored prose, written once with no request in scope, so
    they follow the stored preference of the instructor who owns the game
    rather than the language of whoever later opens the panel. Falls back to
    'en' when nobody has stated one, and never raises.
    """
    try:
        for user_id in _game_owner_ids(game):
            stated = _stated_language(user_id)
            if stated in SUPPORTED_LANGUAGES:
                return stated
        return 'en'
    except Exception:
        return 'en'
