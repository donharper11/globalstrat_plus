"""
Instructor account management: set/reset student passwords, and see who is
currently logged in.

All views here are instructor/admin only.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User
from core.models.auth_models import UserSession
from core.models.course import Enrollment, Section
from core.permissions import IsInstructor
from core.utils.passwords import (
    default_password_for, hash_password, validate_password,
)


def _visible_users_qs(request):
    """
    Students an instructor may administer.

    Admins see everyone. An instructor sees students enrolled in sections of
    the courses they own, so one instructor can't reset another cohort's
    passwords.

    Courses with no instructor_id are treated as unowned and are visible to
    any instructor. Course.instructor_id is nullable and is genuinely NULL in
    practice — the GS-PILOT course carrying the live 15-student cohort has no
    owner. Scoping strictly to owned courses therefore made the pilot's
    students administrable by nobody, which is worse than the isolation it
    buys: an unowned course is already visible to every instructor through
    the unfiltered /courses/ endpoint.
    """
    role = (getattr(request.user, 'role', '') or '').lower()
    qs = User.objects.exclude(role__iexact='admin')

    if role == 'admin':
        return qs

    from django.db.models import Q
    from core.models.course import Course

    course_ids = Course.objects.filter(
        Q(instructor_id=request.user.user_id) | Q(instructor_id__isnull=True),
    ).values_list('course_id', flat=True)
    section_ids = Section.objects.filter(
        course_id__in=list(course_ids),
    ).values_list('section_id', flat=True)
    user_ids = Enrollment.objects.filter(
        section_id__in=list(section_ids),
    ).values_list('user_id', flat=True)
    return qs.filter(user_id__in=list(user_ids))


def _user_row(user):
    has_pw = bool(user.password_hash)
    return {
        'user_id': user.user_id,
        'username': user.username,
        'display_name': user.display_name,
        'student_id': user.student_id,
        'email': user.email,
        'role': user.role,
        'has_password': has_pw,
        # True when the account still has no password and so cannot log in.
        'needs_password': not has_pw,
        'default_password': default_password_for(user),
    }


class StudentAccountListView(APIView):
    """GET /api/instructor/student-accounts/ — roster with password status."""
    permission_classes = [IsInstructor]

    def get(self, request):
        qs = _visible_users_qs(request)

        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(display_name__icontains=search)
                | Q(student_id__icontains=search)
                | Q(email__icontains=search)
            )

        game_id = request.query_params.get('game_id')
        if game_id:
            try:
                from core.models import Game
                game = Game.objects.filter(pk=int(game_id)).first()
                if game and game.section_id:
                    ids = Enrollment.objects.filter(
                        section_id=game.section_id,
                    ).values_list('user_id', flat=True)
                    qs = qs.filter(user_id__in=list(ids))
            except (TypeError, ValueError):
                pass

        qs = qs.order_by('username')[:500]
        users = list(qs)

        # Annotate with live session state in one query.
        active = {
            s.user_id: s
            for s in UserSession.active_qs().filter(
                user_id__in=[u.user_id for u in users],
            )
        }

        rows = []
        for u in users:
            row = _user_row(u)
            session = active.get(u.user_id)
            row['is_online'] = session is not None
            row['online_minutes'] = session.duration_minutes if session else None
            rows.append(row)

        return Response({'count': len(rows), 'students': rows})


class StudentPasswordResetView(APIView):
    """
    POST /api/instructor/student-accounts/<user_id>/password/

    Body: {"password": "..."}          -> set an explicit password
          {"reset_to_default": true}   -> reset to the student's student_id
    """
    permission_classes = [IsInstructor]

    def post(self, request, user_id):
        user = _visible_users_qs(request).filter(user_id=user_id).first()
        if not user:
            return Response(
                {'error': 'Student not found, or not in one of your courses.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if (user.role or '').lower() in ('instructor', 'admin'):
            # Guard against an instructor resetting a peer's password.
            if (getattr(request.user, 'role', '') or '').lower() != 'admin':
                return Response(
                    {'error': 'Only an admin can reset an instructor password.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        reset_to_default = request.data.get('reset_to_default', False)

        if reset_to_default:
            new_password = default_password_for(user)
            if not new_password:
                return Response(
                    {'error': 'This account has no student_id or username to '
                              'derive a default password from. Set one explicitly.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            new_password = request.data.get('password') or ''
            err = validate_password(new_password)
            if err:
                return Response({'error': err},
                                status=status.HTTP_400_BAD_REQUEST)

        user.password_hash = hash_password(new_password)
        user.save(update_fields=['password_hash'])

        return Response({
            'message': f'Password updated for {user.username}.',
            'user_id': user.user_id,
            'username': user.username,
            # Echoed so the instructor can read it out to the student. This is
            # the only moment it exists in plain text.
            'password': new_password,
            'was_reset_to_default': bool(reset_to_default),
        })


class BulkPasswordResetView(APIView):
    """
    POST /api/instructor/student-accounts/bulk-reset/

    Body: {"user_ids": [1,2,3]}  or  {"only_missing": true}
    Resets each account to its default password (student_id).
    """
    permission_classes = [IsInstructor]

    def post(self, request):
        qs = _visible_users_qs(request).exclude(role__iexact='instructor')

        user_ids = request.data.get('user_ids')
        only_missing = request.data.get('only_missing', False)

        if user_ids:
            qs = qs.filter(user_id__in=user_ids)
        elif only_missing:
            qs = qs.filter(Q(password_hash='') | Q(password_hash__isnull=True))
        else:
            return Response(
                {'error': 'Provide user_ids, or only_missing=true.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated, skipped = [], []
        for user in qs:
            pw = default_password_for(user)
            if not pw:
                skipped.append({'user_id': user.user_id,
                                'username': user.username,
                                'reason': 'no student_id or username'})
                continue
            user.password_hash = hash_password(pw)
            user.save(update_fields=['password_hash'])
            updated.append({'user_id': user.user_id,
                            'username': user.username,
                            'password': pw})

        return Response({
            'message': f'Reset {len(updated)} password(s) to the student ID default.',
            'updated_count': len(updated),
            'skipped_count': len(skipped),
            'updated': updated,
            'skipped': skipped,
        })


class ActiveSessionsView(APIView):
    """
    GET /api/instructor/active-sessions/?game_id=&include_recent=

    Who is logged in right now and for how long. include_recent=1 also returns
    sessions that ended within the last hour, so an instructor can see who has
    just dropped off.
    """
    permission_classes = [IsInstructor]

    def get(self, request):
        game_id = request.query_params.get('game_id')
        try:
            game_id = int(game_id) if game_id else None
        except (TypeError, ValueError):
            game_id = None

        active = list(UserSession.active_qs(game_id=game_id))

        def row(s, online):
            return {
                'session_id': s.id,
                'user_id': s.user_id,
                'username': s.username,
                'display_name': s.display_name or s.username,
                'role': s.role,
                'team_id': s.team_id,
                'team_name': s.team_name,
                'game_id': s.game_id,
                'login_at': s.login_at.isoformat(),
                'last_seen_at': s.last_seen_at.isoformat(),
                'duration_minutes': s.duration_minutes,
                'idle_minutes': s.idle_minutes,
                'is_online': online,
                'ip_address': s.ip_address,
            }

        payload = {
            'now': timezone.now().isoformat(),
            'idle_timeout_minutes': UserSession.IDLE_TIMEOUT_MINUTES,
            'active_count': len(active),
            'active': [row(s, True) for s in active],
        }

        if request.query_params.get('include_recent') in ('1', 'true', 'True'):
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            recent_qs = UserSession.objects.filter(
                last_seen_at__gte=cutoff,
            ).exclude(id__in=[s.id for s in active]).order_by('-last_seen_at')
            if game_id is not None:
                recent_qs = recent_qs.filter(game_id=game_id)
            payload['recent'] = [row(s, False) for s in recent_qs[:100]]

        return Response(payload)
