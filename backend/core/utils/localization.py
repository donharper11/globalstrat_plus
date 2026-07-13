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


def get_user_language(request):
    """Extract language preference: Accept-Language header first, then enrollment."""
    header_lang = _lang_from_header(request)
    if header_lang:
        return header_lang
    from core.models.course import Enrollment
    try:
        enrollment = Enrollment.objects.filter(
            user_id=request.user.id, is_active=True
        ).first()
        return enrollment.language if enrollment and enrollment.language else 'en'
    except:
        return 'en'


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
