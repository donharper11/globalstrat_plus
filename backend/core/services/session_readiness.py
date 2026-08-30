"""Who is actually signed in, as distinct from who is on the roster.

CRV2-07. The instructor dashboard reports roster membership: it enumerates
`Enrollment` rows and answers "who is in this class". An operator deciding
whether to open a round needs a different question answered — "who is signed in
and working right now" — and reading a roster count as a session count is how a
round gets opened with a third of the cohort still locked out.

The two are kept separately named here and everywhere they surface. Roster is
expected participants; readiness is authenticated ones.

Active is `UserSession.active_qs`: no `logout_at`, and `last_seen_at` within
`UserSession.IDLE_TIMEOUT_MINUTES`. That definition already existed and is not
redefined here.
"""
from django.utils import timezone


def _display(name, username, email):
    return name or username or email or '(unnamed)'


def readiness(game, cohort_team_ids=None):
    """Session readiness for one game.

    `cohort_team_ids` narrows the expected set to specific teams; by default
    every active team in the game is expected.
    """
    from core.models import Team, User
    from core.models.auth_models import UserSession
    from core.models.course import Enrollment

    teams = Team.objects.filter(game=game, participation_status='active')
    if cohort_team_ids is not None:
        teams = teams.filter(id__in=list(cohort_team_ids))
    team_by_id = {t.id: t for t in teams.order_by('id')}

    enrollments = list(Enrollment.objects.filter(
        team_id__in=list(team_by_id), is_active=True))
    expected_user_ids = {e.user_id for e in enrollments}
    team_of_user = {e.user_id: e.team_id for e in enrollments}

    users = {u.user_id: u for u in
             User.objects.filter(user_id__in=list(expected_user_ids))}

    # Sessions for this game only. A session belonging to another game or
    # section cannot satisfy this cohort, so the game filter is the boundary.
    active = list(UserSession.active_qs(game_id=game.id))
    sessions_by_user = {}
    for session in active:
        sessions_by_user.setdefault(session.user_id, []).append(session)

    authenticated_ids = expected_user_ids & set(sessions_by_user)
    missing_ids = expected_user_ids - set(sessions_by_user)

    # Stale: a session row exists for the user in this game but is not active —
    # idled out or explicitly logged out. Reported so an instructor can tell
    # "never arrived" from "was here and dropped".
    cutoff = timezone.now() - timezone.timedelta(
        minutes=UserSession.IDLE_TIMEOUT_MINUTES)
    stale = []
    for session in UserSession.objects.filter(
            game_id=game.id, user_id__in=list(missing_ids)):
        if session.logout_at is not None:
            reason = 'logged out'
        elif session.last_seen_at < cutoff:
            reason = f'idle over {UserSession.IDLE_TIMEOUT_MINUTES} minutes'
        else:
            continue
        stale.append({
            'user_id': session.user_id,
            'name': _display(session.display_name, session.username, ''),
            'team_id': team_of_user.get(session.user_id),
            'reason': reason,
            'last_seen_at': session.last_seen_at.isoformat(),
        })

    # Duplicates are surfaced, never folded into the authenticated count: two
    # browsers open is one participant, and counting it as two would let a
    # cohort look complete while somebody is still locked out.
    duplicates = [
        {'user_id': user_id,
         'name': _display(sessions[0].display_name, sessions[0].username, ''),
         'team_id': team_of_user.get(user_id),
         'session_count': len(sessions)}
        for user_id, sessions in sorted(sessions_by_user.items())
        if user_id in expected_user_ids and len(sessions) > 1]

    def describe(user_id):
        user = users.get(user_id)
        return {
            'user_id': user_id,
            'name': _display(getattr(user, 'display_name', ''),
                             getattr(user, 'username', ''),
                             getattr(user, 'email', '')),
            'team_id': team_of_user.get(user_id),
            'team_name': getattr(
                team_by_id.get(team_of_user.get(user_id)), 'name', None),
        }

    unexpected = sorted(set(sessions_by_user) - expected_user_ids)

    return {
        'game_id': game.id,
        'idle_timeout_minutes': UserSession.IDLE_TIMEOUT_MINUTES,
        'roster': {
            'teams': len(team_by_id),
            'expected_participants': len(expected_user_ids),
        },
        'sessions': {
            'authenticated': len(authenticated_ids),
            'missing': len(missing_ids),
            'stale': len(stale),
            'duplicate_sessions': len(duplicates),
            'active_sessions_total': len(active),
            'unexpected_active_sessions': len(unexpected),
        },
        'authenticated_participants': [describe(u) for u in sorted(authenticated_ids)],
        'missing_participants': [describe(u) for u in sorted(missing_ids)],
        'stale_participants': sorted(stale, key=lambda s: s['user_id']),
        'duplicate_participants': duplicates,
        # Ready only when every expected participant holds exactly one usable
        # session. Duplicates block it: the instructor is told to resolve them
        # rather than have them silently absorbed.
        'ready': bool(expected_user_ids)
                 and not missing_ids
                 and not duplicates,
        'blocking_reasons': (
            ([] if expected_user_ids else ['no expected participants'])
            + ([f'{len(missing_ids)} participant(s) not authenticated']
               if missing_ids else [])
            + ([f'{len(duplicates)} participant(s) with more than one active '
                f'session'] if duplicates else [])),
    }
