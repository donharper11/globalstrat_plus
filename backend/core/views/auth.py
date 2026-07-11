import hashlib

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.models import User, Enrollment, Section, SimulationInstance, Course
from core.utils.localization import get_localized_field


def _verify_password(plain, stored_hash):
    """
    Check a plain-text password against the stored hash.
    Uses SHA-256 hex digest (simple but adequate for a classroom sim).
    """
    return hashlib.sha256(plain.encode()).hexdigest() == stored_hash


def _hash_password(plain):
    """Create a SHA-256 hex digest of a plain-text password."""
    return hashlib.sha256(plain.encode()).hexdigest()


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
    Username-only login for students.
    Instructor and Admin accounts require a password.
    Students/email/student_id can also be used for lookup.
    """

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()
        section_id = request.data.get('section_id')  # For multi-enrollment

        if not username:
            return Response(
                {'error': 'Username is required.'},
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

        if not user:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        role = (user.role or '').lower()

        # Instructor / Admin accounts require a password
        if role in ('instructor', 'admin'):
            if not password:
                return Response(
                    {'error': 'Password is required for instructor accounts.',
                     'requires_password': True},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not _verify_password(password, user.password_hash):
                return Response(
                    {'error': 'Invalid password.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

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
        return Response(payload)


class CurrentUserView(APIView):
    """Return user info by user_id (for session validation)."""

    def get(self, request):
        user_id = request.query_params.get('user_id')
        section_id = request.query_params.get('section_id')
        if not user_id:
            return Response(
                {'error': 'user_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(
            user_id=user_id,
        ).first()
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
        from core.models.course import Enrollment
        user_id = request.user.id
        try:
            return Enrollment.objects.filter(user_id=user_id, is_active=True).first()
        except:
            return None
