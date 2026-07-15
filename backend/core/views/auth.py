from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.models import User, Enrollment, Section, SimulationInstance, Course
from core.utils.localization import get_localized_field
from core.utils.passwords import (
    hash_password as _hash_password,
    verify_password,
    upgrade_hash_if_needed,
)


def _verify_password(plain, stored_hash):
    """Back-compat shim: True if the password matches. Prefer verify_password."""
    ok, _ = verify_password(plain, stored_hash)
    return ok


def _build_enrollment_context(enrollment):
    """Build enrollment context dict from an Enrollment record."""
    section = enrollment.section
    course = section.course
    instance = SimulationInstance.objects.filter(section_id=section.section_id).first()
    language = enrollment.language or 'en'
    team_name = None
    home_market_code = None
    home_market_name = None
    if enrollment.team_id:
        from core.models import Team
        team = Team.objects.filter(id=enrollment.team_id).select_related('home_market').first()
        team_name = team.name if team else None
        if team and team.home_market:
            home_market_code = team.home_market.code
            home_market_name = get_localized_field(team.home_market, 'name', language)
    # Resolve game from simulation instance, or fallback to Game.section_id
    game_id = None
    game_name = None
    from core.models import Game
    if instance and instance.game_id:
        game = Game.objects.filter(id=instance.game_id).first()
        if game:
            game_id = game.id
            game_name = game.name
    if not game_id:
        # Fallback: find game linked to this section directly
        game = Game.objects.filter(section_id=section.section_id).order_by('-id').first()
        if game:
            game_id = game.id
            game_name = game.name

    return {
        'section_id': section.section_id,
        'section_code': section.section_code,
        'section_name': section.section_name,
        'instance_id': instance.instance_id if instance else None,
        'game_id': game_id,
        'game_name': game_name,
        'course_id': course.course_id,
        'course_code': course.course_code,
        'course_name': course.course_name,
        'team_id': enrollment.team_id,
        'team_name': team_name,
        'home_market_code': home_market_code,
        'home_market_name': home_market_name,
        'onboarding_completed': enrollment.onboarding_completed,
        'language': enrollment.language or 'en',
    }


def _user_payload(user, enrollment=None):
    """Build user payload with optional enrollment context."""
    payload = {
        'user_id': user.user_id,
        'username': user.username,
        'display_name': user.display_name,
        'role': user.role,
        'team_id': None,
        'team_name': None,
    }

    # Find enrollments for this user
    enrollments = Enrollment.objects.filter(
        user_id=user.user_id, is_active=True,
    ).select_related('section', 'section__course')

    active_enrollments = []
    for enr in enrollments:
        if enr.section.is_active and enr.section.course.is_active:
            active_enrollments.append(enr)

    if enrollment:
        # Specific enrollment selected
        ctx = _build_enrollment_context(enrollment)
        payload.update(ctx)
    elif len(active_enrollments) == 1:
        # Auto-select single enrollment
        ctx = _build_enrollment_context(active_enrollments[0])
        payload.update(ctx)
    elif len(active_enrollments) > 1:
        # Multiple enrollments — return list for picker
        payload['enrollments'] = [
            _build_enrollment_context(e) for e in active_enrollments
        ]
        payload['requires_section_selection'] = True
    else:
        # No enrollment — check if instructor
        role = (user.role or '').lower()
        if role in ('instructor', 'admin'):
            # Instructor gets their courses + resolve game_id from first active section
            courses = Course.objects.filter(
                instructor_id=user.user_id, is_active=True
            )
            if courses.exists():
                payload['courses'] = list(courses.values(
                    'course_id', 'course_code', 'course_name',
                    'academic_year', 'semester',
                ))
                # Find game_id from first section's simulation instance
                first_section = Section.objects.filter(
                    course__in=courses, is_active=True
                ).first()
                if first_section:
                    instance = SimulationInstance.objects.filter(
                        section_id=first_section.section_id
                    ).first()
                    if instance and instance.game_id:
                        from core.models import Game
                        game = Game.objects.filter(id=instance.game_id).first()
                        if game:
                            payload['game_id'] = game.id
                            payload['game_name'] = game.name
                            payload['instance_id'] = instance.instance_id

    # CC-16: Include scenario-configured sidebar labels (localized)
    game_id = payload.get('game_id')
    if game_id:
        from core.models import Game
        from core.models.scenario import ScenarioConfig
        try:
            _game = Game.objects.select_related('scenario').get(id=game_id)
            # CC-10: expose scenario_id so the frontend can load scenario-scoped
            # supply-chain content (e.g. /scenarios/<id>/suppliers/).
            payload['scenario_id'] = _game.scenario_id
            language = payload.get('language', 'en')
            raw_labels = {}
            for cfg in ScenarioConfig.objects.filter(
                scenario=_game.scenario,
                config_key__startswith='sidebar_label_',
            ):
                key = cfg.config_key.replace('sidebar_label_', '')
                raw_labels[key] = cfg.config_value
            # Build localized sidebar labels: for zh-CN, prefer _zh variants
            sidebar_labels = {}
            for key, value in raw_labels.items():
                if key.endswith('_zh'):
                    # Skip _zh keys here; they are used as overrides below
                    continue
                if language == 'zh-CN':
                    sidebar_labels[key] = raw_labels.get(f'{key}_zh') or value
                else:
                    sidebar_labels[key] = value
            if sidebar_labels:
                payload['sidebar_labels'] = sidebar_labels
        except Game.DoesNotExist:
            pass

    return payload


class LoginView(APIView):
    """
    Password login for every account, students included.

    Lookup is by username, email, or student_id. Students are issued a default
    password equal to their student_id (see core.utils.passwords).
    """

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        section_id = request.data.get('section_id')  # For multi-enrollment

        if not username:
            return Response(
                {'error': 'Username is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {'error': 'Password is required.', 'requires_password': True},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up by username, email, or student_id
        user = User.objects.filter(
            username__iexact=username,
        ).first()
        if not user:
            user = User.objects.filter(
                email__iexact=username,
            ).first()
        if not user:
            user = User.objects.filter(
                student_id=username,
            ).first()

        # Generic message so login can't be used to enumerate valid usernames.
        invalid = Response(
            {'error': 'Invalid username or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

        if not user:
            return invalid

        role = (user.role or '').lower()

        # Every account requires a password, students included.
        if not user.password_hash:
            # No password on file: the account cannot be logged into until an
            # instructor sets one. Never fall through to an unauthenticated login.
            return Response(
                {'error': 'No password is set for this account. '
                          'Please ask your instructor to reset it.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ok, needs_upgrade = verify_password(password, user.password_hash)
        if not ok:
            return invalid
        if needs_upgrade:
            upgrade_hash_if_needed(user, password)

        # Students must have a team assignment (check Enrollment, not User)
        if role == 'student':
            has_team = Enrollment.objects.filter(
                user_id=user.user_id, is_active=True,
            ).exclude(team_id__isnull=True).exists()
            if not has_team:
                return Response(
                    {'error': 'Your account has not been assigned to a team yet. Please contact your instructor.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # If section_id provided, look up specific enrollment
        enrollment = None
        if section_id:
            enrollment = Enrollment.objects.filter(
                user_id=user.user_id, section_id=section_id, is_active=True,
            ).select_related('section', 'section__course').first()

        # Build payload and add JWT access token
        from core.authentication import create_access_token
        payload = _user_payload(user, enrollment)
        payload['access'] = create_access_token(user)

        # Record the session so instructors can see who is logged in.
        try:
            payload['session_id'] = _open_session(request, user, payload)
        except Exception:
            pass  # session telemetry must never block a login

        return Response(payload)


def _open_session(request, user, payload):
    """Create a UserSession row for this login. Returns its id."""
    from core.models.auth_models import UserSession

    xff = request.headers.get('X-Forwarded-For', '')
    ip = (xff.split(',')[0].strip() if xff
          else request.META.get('REMOTE_ADDR', '') or '')

    session = UserSession.objects.create(
        user_id=user.user_id,
        username=user.username or '',
        display_name=user.display_name or '',
        role=user.role or '',
        game_id=payload.get('game_id'),
        team_id=payload.get('team_id'),
        team_name=payload.get('team_name') or '',
        ip_address=ip[:64],
        user_agent=(request.headers.get('User-Agent', '') or '')[:300],
    )
    return session.id


class LogoutView(APIView):
    """POST — close the caller's session so they stop showing as logged in."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        from core.models.auth_models import UserSession

        session_id = (request.data.get('session_id')
                      or request.headers.get('X-Session-Id'))
        qs = UserSession.objects.filter(
            user_id=request.user.user_id, logout_at__isnull=True,
        )
        if session_id:
            qs = qs.filter(pk=session_id)
        closed = qs.update(logout_at=timezone.now())
        return Response({'closed': closed})


class CurrentUserView(APIView):
    """
    Return the authenticated caller's own user info (for session validation).

    Previously this accepted any user_id as a query param with no
    authentication, which let anyone read any account's full profile and
    enrollment context. It now only ever describes the caller.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get('section_id')

        user = User.objects.filter(user_id=request.user.user_id).first()
        if not user:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment = None
        if section_id:
            enrollment = Enrollment.objects.filter(
                user_id=user.user_id, section_id=section_id, is_active=True,
            ).select_related('section', 'section__course').first()

        return Response(_user_payload(user, enrollment))


class LanguagePreferenceView(APIView):
    """GET/PUT user language preference."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollment = self._get_enrollment(request)
        if not enrollment:
            return Response({'language': 'en'})
        return Response({'language': enrollment.language or 'en'})

    def put(self, request):
        language = request.data.get('language', 'en')
        if language not in ('en', 'zh-CN'):
            return Response({'error': 'Unsupported language'}, status=400)
        enrollment = self._get_enrollment(request)
        if enrollment:
            enrollment.language = language
            enrollment.save(update_fields=['language'])
        return Response({'language': language})

    def _get_enrollment(self, request):
        # JWTUser exposes user_id, not id — request.user.id raised AttributeError
        # here, so this view never resolved an enrollment.
        from core.models.course import Enrollment
        user_id = getattr(request.user, 'user_id', None)
        if not user_id:
            return None
        return Enrollment.objects.filter(
            user_id=user_id, is_active=True,
        ).first()
